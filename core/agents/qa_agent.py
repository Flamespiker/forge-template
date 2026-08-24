"""
FORGE QA Agent — Stage 4 (QA).

Runs the actual test suite (xUnit for the .NET backend, Jest for the Next.js
frontend) against a checked-out copy of the feature branch, parses the results,
and:
  - Files an ADO Bug for every failing test (title, description, repro steps,
    and severity are all built deterministically from parsed test output —
    Document 3's ADO field mapping marks every Bug field "FORGE (automatic)",
    not agent judgment; Claude is not asked to decide pass/fail or severity).
  - Posts a human-readable test report as a comment on the feature PR in the
    monorepo (forge-demo-apps) — Claude is used only for this one write-up,
    given the already-deterministic parsed results as input.
  - Applies `qa-approved` (all pass), `qa-loop-back` (failures, retry budget
    remaining), or `qc-retry-limit-reached` (failures, retry budget exhausted)
    to the FORGE tracking issue (Document 6's Label Reference: these three
    labels live on the tracking issue, not the monorepo PR).

Unlike every prior stage, QA needs the actual repository contents on disk to
run tests — not just individual file reads via the GitHub Contents API. This
script assumes a local checkout of the monorepo at the feature branch already
exists (passed via --repo-path) — populated by the invoking GitHub Actions
job's own `actions/checkout` step (Phase 4, step 4.5, not yet wired). This
script does not clone anything itself: checkout is the workflow layer's job,
same separation of concerns as every other stage (orchestration lives in
`.github/workflows/`, the stage script does the stage's actual work).

Retry-limit tracking (Document 6: "retries...up to three times before
stopping and escalating") is derived statelessly (ADR-0002 — no agent retains
memory between runs): the current attempt number is 1 + the count of this
agent's own prior comments on this PR (identified by the
`<!-- forge:agent-comment stage=qa ... -->` marker), fetched fresh each run via
get_pr_comments(). There is no separate counter to keep in sync.

KNOWN GAP (flagged, not fixed here — see FORGE-context for detail): ADO Bugs
should link to the relevant parent User Story, but Phase 4's ADO item-creation
step (4.3) has not been built/run for any request yet, so no real User Story
IDs exist. _resolve_parent_story_id() looks for a resolved id mapping at
docs/<request-id>/ado-work-items.json and returns None (logging a warning) if
it isn't there — Bugs are still created, just without a parent link, via
ado_helper.create_bug()'s now-optional parent_story_id. Once Phase 4 exists
and writes real IDs back to that file, this starts resolving automatically —
no change needed here, only a change to what Phase 4 writes.

Severity mapping (Document 3: "Mapped from test failure type...FORGE
(automatic, using a fixed mapping — not AI judgment)") is a deterministic
string/substring classifier, not an LLM call — see _classify_failure_severity().
It is a best-effort heuristic (xUnit/Jest don't expose a clean "was this an
assertion" flag in their standard output), not a perfect classifier; documented
inline as such.

Usage:
    python -m core.agents.qa_agent --issue-number 2 --request-id REQ-2026-01 \\
        --pr-number 5 --repo-path /path/to/forge-demo-apps-checkout
    python -m core.agents.qa_agent --issue-number 2 --request-id REQ-2026-01 \\
        --pr-number 5 --repo-path /path/to/forge-demo-apps-checkout --dry-run

CLI arguments:
    --issue-number   FORGE tracking issue number in forge-template, used to post
                     a failure comment (best-effort) and apply the gate label
                     (required).
    --request-id     FORGE request ID. Used to locate services/<request-id>/
                     within --repo-path, and to look up a parent User Story ID
                     mapping (required).
    --pr-number      The feature PR number in forge-demo-apps, used to post the
                     test report comment and to count prior QA attempts on this
                     PR. Required for a real run; optional for --dry-run.
    --repo-path      Local path to an existing checkout of forge-demo-apps at
                     the feature branch (required — see module docstring;
                     this script does not clone anything itself).
    --dry-run        Run tests, parse results, compute severities, and call
                     Claude for the write-up, but print everything to stdout
                     instead of creating ADO bugs, posting to GitHub, or
                     applying labels.

Per ADR-0011 / Document 6: the invoke_agent() call is wrapped in try/except at
the call site. On failure, a failure comment is posted to the tracking issue
(best-effort, real run only) before the exception is re-raised.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from core.agents.utils.claude_agent_wrapper import invoke_agent
from core.agents.utils.github_helper import (
    get_file_contents,
    get_issue,
    get_pr_comments,
    post_comment,
    post_pr_comment,
    add_label,
)
from core.agents.utils import ado_helper

logger = logging.getLogger(__name__)

_STAGE_NAME = "qa"
_MAX_TOKENS = 4000
_MAX_RETRIES = 3  # Document 6: QA retries implementation failures up to 3 times
_TEST_TIMEOUT_SECONDS = 1800  # 30 min ceiling per test-suite invocation

_SEVERITY_MEDIUM = "3 - Medium"  # assertion failure (Document 3 fixed mapping)
_SEVERITY_HIGH = "2 - High"      # exception/crash, and build/run failures (see below)

# Substrings that mark a failure as an assertion failure (vs. an unhandled
# exception/crash) — a deterministic, not-AI-judgment heuristic per Document 3.
# xUnit's assertion library raises exceptions under the Xunit.Sdk namespace;
# Jest wraps matcher failures in an Error whose message contains "expect(".
# Anything NOT matching one of these markers is treated as an exception/crash
# (severity High) rather than a plain assertion failure (severity Medium).
_ASSERTION_MARKERS = (
    "xunit.sdk",
    "assert.",
    "expect(",
    "assertionerror",
    "expected:",
    "tobe(",
    "toequal(",
    "tocontain(",
    "tohavebeencalled",
)


@dataclass
class TestFailure:
    suite: str          # "backend" or "frontend"
    test_name: str
    message: str
    stack_trace: str


@dataclass
class TestSuiteResult:
    suite: str
    ran: bool            # False if the suite crashed/failed to produce any results at all
    passed: int
    failed: int
    total: int
    failures: list[TestFailure]
    run_failure_message: str | None = None  # set when ran=False and not_applicable=False
    # A real third outcome (Phase 5 pre-flight Fix 3), not a variant of pass or
    # fail: set when this suite was never in scope for this service (no test
    # project/script found on disk), as opposed to being in scope and crashing.
    # Does not count against the retry budget and never files an ADO Bug --
    # see run_qa_agent()'s suite_run_failed / bug-filing logic below.
    not_applicable: bool = False


def _run_shell(command: list[str], cwd: str) -> subprocess.CompletedProcess:
    logger.info("Running: %s (cwd=%s)", " ".join(command), cwd)
    resolved = shutil.which(command[0]) or command[0]
    return subprocess.run(
        [resolved, *command[1:]],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TEST_TIMEOUT_SECONDS,
    )


def _strip_ns(tag: str) -> str:
    """Strip an XML namespace prefix, e.g. '{...}UnitTestResult' -> 'UnitTestResult'."""
    return tag.rsplit("}", 1)[-1]


def _resolve_backend_test_dir(service_root: Path) -> tuple[str | None, str | None]:
    """
    Locate the backend test project's directory.

    Neither Document 3 nor Document 7 mandates a folder layout for backend
    tests -- only that xUnit is the required framework. Test Writer is free
    to place the test project alongside the API code (services/<id>/backend/)
    or in a sibling project (services/<id>/backend.tests/, or any other name
    ending in *.Tests.csproj). Rather than assuming one layout -- which
    previously caused a real backend suite to be reported as a build/compile
    failure because dotnet test was run from the API project's own directory,
    not the test project's -- search for the actual *.Tests.csproj file.

    Returns:
        (resolved_dir, warning). resolved_dir is None when no *.Tests.csproj
        exists anywhere under service_root at all -- callers must treat that
        as backend testing being out of scope for this service (Phase 5
        pre-flight Fix 3's not_applicable outcome), not as a build/compile
        failure to run against a guessed path. warning is None only when
        exactly one test project was found unambiguously.
    """
    seen: set[Path] = set()
    candidates: list[Path] = []
    for pattern in ("**/*.Tests.csproj", "**/*Tests.csproj"):
        for path in sorted(service_root.glob(pattern)):
            if path not in seen:
                seen.add(path)
                candidates.append(path)

    if not candidates:
        return None, (
            f"No *.Tests.csproj found anywhere under {service_root} -- treating "
            "backend testing as not applicable (out of scope) for this service, "
            "rather than guessing a path and reporting a false build/compile "
            "failure."
        )

    if len(candidates) > 1:
        chosen = candidates[0]
        return str(chosen.parent), (
            f"Multiple *.Tests.csproj files found under {service_root}: "
            f"{[str(c) for c in candidates]} -- using the first match "
            f"({chosen}). Consider whether the extra test project(s) are "
            "intentional."
        )

    return str(candidates[0].parent), None


def _run_backend_tests(backend_dir: str) -> TestSuiteResult:
    """
    Run `dotnet test` against the backend project and parse the TRX report.

    Presence of the TRX file (not the process exit code) determines whether the
    suite actually ran: `dotnet test` also exits non-zero when tests merely
    fail, so exit code alone can't distinguish "tests ran, some failed" from
    "the suite never ran at all" (e.g. a compile error).
    """
    with tempfile.TemporaryDirectory() as results_dir:
        trx_path = Path(results_dir) / "qa-results.trx"
        try:
            result = _run_shell(
                [
                    "dotnet", "test",
                    "--logger", f"trx;LogFileName={trx_path.name}",
                    "--results-directory", results_dir,
                ],
                cwd=backend_dir,
            )
        except subprocess.TimeoutExpired:
            return TestSuiteResult(
                suite="backend", ran=False, passed=0, failed=0, total=0,
                failures=[],
                run_failure_message=f"`dotnet test` timed out after {_TEST_TIMEOUT_SECONDS}s.",
            )

        if not trx_path.exists():
            tail = (result.stdout or "")[-3000:] + (result.stderr or "")[-1000:]
            return TestSuiteResult(
                suite="backend", ran=False, passed=0, failed=0, total=0,
                failures=[],
                run_failure_message=(
                    "Backend test suite failed to produce a TRX report — likely a "
                    f"build/compile error, not a test failure. Tail of output:\n\n{tail}"
                ),
            )

        return _parse_trx(trx_path)


def _parse_trx(trx_path: Path) -> TestSuiteResult:
    tree = ET.parse(trx_path)
    root = tree.getroot()

    failures: list[TestFailure] = []
    passed = 0
    failed = 0

    for elem in root.iter():
        if _strip_ns(elem.tag) != "UnitTestResult":
            continue
        outcome = elem.get("outcome", "")
        test_name = elem.get("testName", "unknown")
        if outcome == "Passed":
            passed += 1
            continue
        if outcome != "Failed":
            continue  # skip Skipped/NotExecuted/etc. — neither pass nor fail
        failed += 1

        message = ""
        stack_trace = ""
        for child in elem.iter():
            tag = _strip_ns(child.tag)
            if tag == "Message" and child.text:
                message = child.text.strip()
            elif tag == "StackTrace" and child.text:
                stack_trace = child.text.strip()

        failures.append(
            TestFailure(
                suite="backend",
                test_name=test_name,
                message=message,
                stack_trace=stack_trace,
            )
        )

    total = passed + failed
    return TestSuiteResult(
        suite="backend", ran=True, passed=passed, failed=failed, total=total,
        failures=failures,
    )


def _frontend_test_script_exists(frontend_dir: str) -> bool:
    """
    Phase 5 pre-flight Fix 3: a service where the frontend suite was never in
    scope (e.g. DRYRUN-2026-01, backend-only) has no "test" script in
    package.json -- running `npm test` against it burned QA's full retry
    budget on a non-issue in that run. Checked here so run_qa_agent() can
    record `not_applicable` instead of attempting the run at all.

    Scoped deliberately to inference from what's on disk (missing
    package.json / missing "test" script), not a more thorough explicit
    in-scope/out-of-scope declaration sourced from design.md or a manifest
    field -- that's a real future enhancement (would also need a Design Agent
    change) but out of scope for this fix.
    """
    package_json_path = Path(frontend_dir) / "package.json"
    if not package_json_path.exists():
        return False
    try:
        package_json = json.loads(package_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    test_script = package_json.get("scripts", {}).get("test")
    return bool(test_script and test_script.strip())


def _detect_frontend_test_runner(frontend_dir: str) -> str:
    """
    Returns "vitest" or "jest". Vitest and Jest's CLIs are not flag-compatible
    (Vitest hard-rejects an unrecognized flag like Jest's `--ci` and exits
    before collecting any tests — this is what broke QA for REQ-2026-03,
    whose frontend uses Vitest), so the runner must be detected before
    invocation, not assumed.

    Checks, in order: a vitest.config.{ts,js,mjs} file (the strongest signal —
    only present on a real Vitest project), then "vitest" in package.json's
    devDependencies/dependencies. Defaults to "jest" — the core-layer mandate
    (ADR-0008) and the existing, working behavior for a project like
    REQ-2026-02's frontend that has neither signal.
    """
    frontend_path = Path(frontend_dir)
    if any(
        (frontend_path / f"vitest.config.{ext}").exists()
        for ext in ("ts", "js", "mjs")
    ):
        return "vitest"

    package_json_path = frontend_path / "package.json"
    try:
        package_json = json.loads(package_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "jest"

    deps = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}
    if "vitest" in deps:
        return "vitest"

    return "jest"


def _run_frontend_tests(frontend_dir: str) -> TestSuiteResult:
    """
    Detects the actual frontend test runner (see _detect_frontend_test_runner())
    and invokes it with the correct CLI flags, then parses the resulting JSON
    report.

    - Vitest: `npx vitest run --reporter=json --outputFile=...`. Vitest's `json`
      reporter deliberately mirrors Jest's report schema (numPassedTests,
      numFailedTests, testResults[].assertionResults[] with the same field
      names) — confirmed empirically against a real Vitest run, not assumed —
      so _parse_jest_json() parses both without a separate Vitest-specific
      parser.
    - Jest (fallback/existing behavior): `npm test -- --ci --json
      --outputFile=...`, forwarded through the team's package.json "test"
      script per ADR-0008 — unchanged, since REQ-2026-02's frontend already
      relies on this working.
    """
    runner = _detect_frontend_test_runner(frontend_dir)

    with tempfile.TemporaryDirectory() as results_dir:
        json_path = Path(results_dir) / "frontend-results.json"
        if runner == "vitest":
            command = ["npx", "vitest", "run", "--reporter=json", f"--outputFile={json_path}"]
        else:
            command = ["npm", "test", "--", "--ci", "--json", f"--outputFile={json_path}"]

        try:
            result = _run_shell(command, cwd=frontend_dir)
        except subprocess.TimeoutExpired:
            return TestSuiteResult(
                suite="frontend", ran=False, passed=0, failed=0, total=0,
                failures=[],
                run_failure_message=f"`{' '.join(command)}` timed out after {_TEST_TIMEOUT_SECONDS}s.",
            )

        if not json_path.exists():
            tail = (result.stdout or "")[-3000:] + (result.stderr or "")[-1000:]
            return TestSuiteResult(
                suite="frontend", ran=False, passed=0, failed=0, total=0,
                failures=[],
                run_failure_message=(
                    f"Frontend test suite ({runner}) failed to produce a JSON report — likely "
                    f"a build/syntax error, not a test failure. Tail of output:\n\n{tail}"
                ),
            )

        return _parse_jest_json(json_path)


def _jest_collection_failures(data: dict) -> list[str]:
    """
    Finds test files that failed to *collect* (a broken import, a syntax
    error, a type error — anything that prevents Jest/Vitest from even
    starting to run the file's tests), as opposed to a file that collected
    fine and had one or more tests assert falsely.

    Confirmed live against both runners (a real broken-import fixture, since
    Jest/Vitest don't document this shape anywhere): a collection-failed file
    appears in testResults[] with status == "failed" and an EMPTY
    assertionResults[] (there were no individual tests to report on — the
    file itself never loaded) plus a top-level "message" string containing
    the actual error. A file with real per-test assertion failures instead
    has a non-empty assertionResults[], each entry individually marked
    failed — that shape is already handled by the loop above and is not
    treated as a collection failure here.

    This is the root cause behind the "0 passed / 0 failed / 0 total" blind
    spot: numFailedTests only counts individual failed assertionResults
    entries, so a file that fails to collect contributes nothing to that
    count on either side, regardless of whether numTotalTests happens to be
    exactly 0 (every file failed to collect) or nonzero (some other file in
    the same run collected fine and had real, counted tests) — both cases
    are covered by scanning every testResults[] entry directly.
    """
    messages: list[str] = []
    for test_file in data.get("testResults", []):
        if test_file.get("status") != "failed":
            continue
        if test_file.get("assertionResults"):
            continue  # a real per-test failure, not a collection failure
        name = test_file.get("name", "unknown file")
        message = (test_file.get("message") or "(no message provided)").strip()
        messages.append(f"{name}:\n{message}")
    return messages


def _parse_jest_json(json_path: Path) -> TestSuiteResult:
    data = json.loads(json_path.read_text(encoding="utf-8"))

    collection_failures = _jest_collection_failures(data)
    if collection_failures:
        combined = "\n\n---\n\n".join(collection_failures)
        return TestSuiteResult(
            suite="frontend", ran=False, passed=0, failed=0, total=0,
            failures=[],
            run_failure_message=(
                f"{len(collection_failures)} frontend test file(s) failed to collect "
                "(broken import, syntax error, or type error — the file never started "
                f"running its tests):\n\n{combined[:3000]}"
            ),
        )

    failures: list[TestFailure] = []
    for test_file in data.get("testResults", []):
        for assertion in test_file.get("assertionResults", []):
            if assertion.get("status") != "failed":
                continue
            failure_messages = assertion.get("failureMessages", [])
            combined = "\n---\n".join(failure_messages)
            failures.append(
                TestFailure(
                    suite="frontend",
                    test_name=assertion.get("fullName") or assertion.get("title", "unknown"),
                    message=combined[:2000],
                    stack_trace=combined,
                )
            )

    passed = data.get("numPassedTests", 0)
    failed = data.get("numFailedTests", 0)
    total = data.get("numTotalTests", passed + failed)
    return TestSuiteResult(
        suite="frontend", ran=True, passed=passed, failed=failed, total=total,
        failures=failures,
    )


def _classify_failure_severity(failure: TestFailure) -> str:
    """Fixed, deterministic mapping — not an LLM judgment call (Document 3)."""
    haystack = (failure.message + " " + failure.stack_trace).lower()
    if any(marker in haystack for marker in _ASSERTION_MARKERS):
        return _SEVERITY_MEDIUM
    return _SEVERITY_HIGH


def _resolve_parent_story_id(request_id: str) -> int | None:
    """
    Best-effort lookup of a real ADO User Story ID to link Bugs against.

    KNOWN GAP: Phase 4's ADO item-creation step (4.3) hasn't been built/run for
    any request yet, so docs/<request-id>/ado-work-items.json currently only
    holds the Requirements Agent's *draft* payload (no real numeric IDs).
    This function expects that once Phase 4 exists, it will write back a real
    ID under a "primary_user_story_id" key at the top level of that same file.
    Until then, this will reliably return None — that's expected, not a bug.
    """
    try:
        content = get_file_contents(f"docs/{request_id}/ado-work-items.json", branch="pipeline-state")
    except Exception:
        logger.warning(
            "No ado-work-items.json found for %s — Bugs will be filed with no "
            "parent User Story link (expected until Phase 4 ADO creation exists).",
            request_id,
        )
        return None

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("ado-work-items.json for %s is not valid JSON — skipping parent link.", request_id)
        return None

    story_id = payload.get("primary_user_story_id")
    if not isinstance(story_id, int):
        logger.warning(
            "ado-work-items.json for %s has no resolved 'primary_user_story_id' yet "
            "(still a pre-Phase-4 draft payload) — Bugs will be filed with no parent link.",
            request_id,
        )
        return None
    return story_id


def _count_prior_qa_attempts(pr_number: int, request_id: str) -> int:
    """
    Derive the current attempt number statelessly (ADR-0002): 1 + however many
    of this agent's own marked comments already exist on this PR.
    """
    marker = f"<!-- forge:agent-comment stage=qa request_id={request_id}"
    comments = get_pr_comments(pr_number)
    prior = sum(1 for c in comments if marker in c.get("body", ""))
    return prior + 1


def _build_bug_title(failure: TestFailure) -> str:
    title = f"QA: [{failure.suite}] {failure.test_name} failed"
    return title[:250]  # ADO title length safety margin


def _build_bug_description(failure: TestFailure, pr_url: str) -> str:
    return (
        f"**Suite:** {failure.suite}\n\n"
        f"**Test:** `{failure.test_name}`\n\n"
        f"**Failure message:**\n\n```\n{failure.message[:1500]}\n```\n\n"
        f"**GitHub PR:** {pr_url}\n\n"
        "_Filed automatically by the FORGE QA Agent from parsed test output._"
    )


def _build_bug_repro_steps(failure: TestFailure, suite_command: str, suite_dir: str) -> str:
    return (
        f"1. Check out the feature branch.\n"
        f"2. Run `{suite_command}` in `{suite_dir}`.\n"
        f"3. Observe `{failure.test_name}` fail with:\n\n```\n{failure.stack_trace[:1500]}\n```"
    )


_SYSTEM_PROMPT = """You are the FORGE QA Agent for Legal Aid Alberta's software delivery \
pipeline, writing the human-facing test report comment for a feature PR.

You will be given already-computed, deterministic test results: pass/fail counts per \
suite (backend/frontend), whether a suite is "not_applicable" (never in scope for this \
service — no test project/script found, distinct from a suite that ran and failed), \
the list of failing tests with their (already-decided, fixed-mapping) severities, \
whether any ADO Bug tickets were filed for them, the current QA retry attempt number, \
and the retry outcome (approved / looped back / retry limit reached).

Do NOT re-judge pass/fail status, severity, or applicability — these are already \
decided by deterministic code and must be reported exactly as given, not reinterpreted.

Your job is only to write a clear, well-organized Markdown test report comment for a \
human reviewer (the QA Reviewer, per Document 6 Gate 4). Include:
- A one-line overall verdict (pass / fail / retry limit reached).
- Pass/fail/total counts per suite. For any suite marked not_applicable, state plainly \
that it is "Not applicable — no test suite in scope for this service" rather than \
reporting it as passed, failed, or skipped-without-explanation — this must read as a \
deliberate scope decision, not a silently skipped check. Do not count a not_applicable \
suite toward the overall pass/fail verdict.
- If there are failures: a short table or list of failed tests with severity and a \
link/reference to the filed ADO Bug (if one was filed).
- If the retry limit was reached, a clear note telling the Orchestration Manager to \
triage manually per Document 6's failure-handling guidance — do not imply the loop \
will continue.
- If all tests passed, a brief positive summary and a note that `qa-approved` was \
applied.

Output format — this is strict:
Respond with ONLY a single JSON object, no markdown code fences, no prose before or \
after it. It must have exactly this shape:

{
  "pr_comment_markdown": "<string - the full Markdown comment body>"
}"""


def run_qa_agent(
    issue_number: int,
    request_id: str,
    repo_path: str,
    pr_number: int | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Core entry point. Returns a dict summarizing the run (suite results, bugs
    filed, label applied, PR comment text).
    """
    if not dry_run and not pr_number:
        raise ValueError(
            "--pr-number is required for a real (non-dry-run) run — it determines "
            "where the test report comment is posted and how retry attempts are "
            "counted. Refusing to proceed without it."
        )

    # Retry-ceiling enforcement (must happen before any test execution or
    # labeling, per the acceptance criteria this guards against): previously
    # _MAX_RETRIES only picked which label to apply -- a passing run always
    # got qa-approved regardless of attempt number, and nothing stopped a
    # fourth, fifth, etc. automatic QA run once the ceiling was already
    # reached. Read-only (get_issue), so it's safe to run under --dry-run too
    # -- only the comment-posting below is skipped in that mode, matching the
    # rest of this function's dry-run discipline.
    issue = get_issue(issue_number)
    existing_labels = {label["name"] for label in issue.get("labels", [])}
    if "qc-retry-limit-reached" in existing_labels:
        skip_message = (
            "⏭️ **FORGE QA Agent skipped — retry ceiling already reached.**\n\n"
            f"This tracking issue already has `qc-retry-limit-reached` applied from a "
            f"prior QA run (retry budget: {_MAX_RETRIES} attempts). No test suites were "
            "run for this dispatch, and no ADO Bugs were filed.\n\n"
            "An Orchestration Manager needs to triage the underlying failure manually "
            "per Document 6's failure-handling guidance. To allow another automatic QA "
            "attempt once the issue is fixed, remove the `qc-retry-limit-reached` label "
            "from this tracking issue — the next PR push (or a manually replayed "
            "dispatch event) will then run QA normally, starting a fresh attempt count."
        )
        if dry_run:
            print("=" * 20, "would be skipped -- retry ceiling already reached", "=" * 20)
            print(skip_message)
        else:
            post_comment(issue_number, skip_message)
        logger.info(
            "QA Agent skipped for request %s — qc-retry-limit-reached already present "
            "on issue #%s; refusing to consume another attempt.",
            request_id, issue_number,
        )
        return {"skipped": True, "reason": "qc-retry-limit-reached"}

    service_root = Path(repo_path) / "services" / request_id
    backend_dir, backend_dir_warning = _resolve_backend_test_dir(service_root)
    if backend_dir_warning:
        logger.warning(backend_dir_warning)
    frontend_dir = str(service_root / "frontend")

    try:
        if backend_dir is None:
            backend_result = TestSuiteResult(
                suite="backend", ran=False, passed=0, failed=0, total=0,
                failures=[], not_applicable=True,
            )
        else:
            backend_result = _run_backend_tests(backend_dir)

        if _frontend_test_script_exists(frontend_dir):
            frontend_result = _run_frontend_tests(frontend_dir)
        else:
            frontend_result = TestSuiteResult(
                suite="frontend", ran=False, passed=0, failed=0, total=0,
                failures=[], not_applicable=True,
            )

        all_failures = list(backend_result.failures) + list(frontend_result.failures)
        # not_applicable suites are a real third outcome (Phase 5 pre-flight
        # Fix 3) -- they must never make suite_run_failed true, or an
        # out-of-scope suite gets treated identically to a genuinely broken one.
        suite_run_failed = (
            (not backend_result.ran and not backend_result.not_applicable)
            or (not frontend_result.ran and not frontend_result.not_applicable)
        )
        tests_pass = (
            not suite_run_failed
            and backend_result.failed == 0
            and frontend_result.failed == 0
        )

        attempt_number = 1
        if not dry_run:
            attempt_number = _count_prior_qa_attempts(pr_number, request_id)

        if tests_pass:
            label_to_apply = "qa-approved"
        elif attempt_number <= _MAX_RETRIES:
            label_to_apply = "qa-loop-back"
        else:
            label_to_apply = "qc-retry-limit-reached"

        owner = os.environ.get("FORGE_GITHUB_OWNER", "")
        target_repo = os.environ.get("FORGE_TARGET_REPO", "forge-demo-apps")
        pr_url = (
            f"https://github.com/{owner}/{target_repo}/pull/{pr_number}"
            if owner and pr_number else "(PR URL unavailable — dry run)"
        )

        parent_story_id = _resolve_parent_story_id(request_id) if not dry_run else None

        filed_bugs: list[dict] = []
        for failure in all_failures:
            severity = _classify_failure_severity(failure)
            suite_dir = backend_dir if failure.suite == "backend" else frontend_dir
            suite_command = "dotnet test" if failure.suite == "backend" else "npm test"
            title = _build_bug_title(failure)
            description = _build_bug_description(failure, pr_url)
            repro_steps = _build_bug_repro_steps(failure, suite_command, suite_dir)

            if dry_run:
                filed_bugs.append({
                    "would_create": True,
                    "title": title,
                    "severity": severity,
                    "parent_story_id": parent_story_id,
                })
                continue

            bug = ado_helper.create_bug(
                title=title,
                repro_steps=repro_steps,
                severity=severity,
                parent_story_id=parent_story_id,
            )
            filed_bugs.append({
                "ado_id": bug["id"],
                "title": title,
                "severity": severity,
                "parent_story_id": parent_story_id,
            })

        # Also file a single synthetic Bug per suite that failed to even run
        # (build/compile error) — distinct from a per-test failure.
        for suite_result in (backend_result, frontend_result):
            if suite_result.ran or suite_result.not_applicable or suite_result.run_failure_message is None:
                continue
            title = f"QA: [{suite_result.suite}] test suite failed to run (build/compile error)"[:250]
            description = (
                f"**Suite:** {suite_result.suite}\n\n"
                f"**Failure:**\n\n```\n{suite_result.run_failure_message[:1500]}\n```\n\n"
                f"**GitHub PR:** {pr_url}"
            )
            if dry_run:
                filed_bugs.append({
                    "would_create": True, "title": title,
                    "severity": _SEVERITY_HIGH, "parent_story_id": parent_story_id,
                })
                continue
            bug = ado_helper.create_bug(
                title=title,
                repro_steps=description,
                severity=_SEVERITY_HIGH,
                parent_story_id=parent_story_id,
            )
            filed_bugs.append({
                "ado_id": bug["id"], "title": title,
                "severity": _SEVERITY_HIGH, "parent_story_id": parent_story_id,
            })

        summary_for_model = {
            "backend": {
                "ran": backend_result.ran,
                "not_applicable": backend_result.not_applicable,
                "passed": backend_result.passed,
                "failed": backend_result.failed,
                "total": backend_result.total,
                "run_failure_message": backend_result.run_failure_message,
            },
            "frontend": {
                "ran": frontend_result.ran,
                "not_applicable": frontend_result.not_applicable,
                "passed": frontend_result.passed,
                "failed": frontend_result.failed,
                "total": frontend_result.total,
                "run_failure_message": frontend_result.run_failure_message,
            },
            "failures": [
                {"suite": f.suite, "test_name": f.test_name, "message": f.message[:500]}
                for f in all_failures
            ],
            "bugs_filed": filed_bugs,
            "attempt_number": attempt_number,
            "max_retries": _MAX_RETRIES,
            "label_applied": label_to_apply,
            "tests_pass": tests_pass,
        }
        user_prompt = (
            "## Deterministic QA Results (already computed — report exactly as given)\n\n"
            f"```json\n{json.dumps(summary_for_model, indent=2)}\n```\n"
            "---\nProduce your JSON response now."
        )

        result = invoke_agent(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=_MAX_TOKENS,
            stage_name=_STAGE_NAME,
            request_id=request_id,
        )
        if result.stop_reason == "max_tokens":
            raise ValueError(
                f"Model response was truncated at max_tokens={_MAX_TOKENS} — "
                "increase _MAX_TOKENS in qa_agent.py and retry."
            )
        text = result.output_text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed_output = json.loads(text)
        pr_comment_markdown = parsed_output["pr_comment_markdown"]

    except Exception as exc:
        logger.exception("QA Agent failed for request %s", request_id)
        if not dry_run:
            failure_body = (
                "⚠️ **FORGE QA Agent failed to complete.**\n\n"
                f"Error: `{exc}`\n\n"
                "An Orchestration Manager needs to investigate before this request "
                "can proceed. Do not apply `qa-approved` yet."
            )
            try:
                post_comment(issue_number, failure_body)
            except Exception:
                logger.exception("Also failed to post failure comment to issue #%s", issue_number)
        raise

    marker = f"<!-- forge:agent-comment stage=qa request_id={request_id} attempt={attempt_number} -->"
    comment_body = f"{marker}\n{pr_comment_markdown}"

    run_summary = {
        "backend_result": backend_result,
        "frontend_result": frontend_result,
        "filed_bugs": filed_bugs,
        "attempt_number": attempt_number,
        "label_applied": label_to_apply,
        "tests_pass": tests_pass,
        "pr_comment_markdown": pr_comment_markdown,
    }

    if dry_run:
        print("=" * 20, "test summary", "=" * 20)
        print(json.dumps(summary_for_model, indent=2))
        print("=" * 20, "PR comment (not posted)", "=" * 20)
        print(comment_body)
        print("=" * 20, "label (not applied)", "=" * 20)
        print(label_to_apply)
        logger.info(
            "Dry run complete for request %s — nothing filed, nothing posted, "
            "nothing labeled.",
            request_id,
        )
        return run_summary

    post_pr_comment(pr_number, comment_body)
    add_label(issue_number, label_to_apply)

    logger.info(
        "QA Agent complete for request %s — attempt %d, label '%s', %d bug(s) filed, "
        "PR #%s comment posted.",
        request_id,
        attempt_number,
        label_to_apply,
        len(filed_bugs),
        pr_number,
    )
    return run_summary


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE QA Agent")
    parser.add_argument("--issue-number", required=True, type=int, help="FORGE tracking issue number in forge-template")
    parser.add_argument("--request-id", required=True, help="FORGE request ID")
    parser.add_argument("--pr-number", default=None, type=int, help="Feature PR number in forge-demo-apps (required for a real run)")
    parser.add_argument("--repo-path", required=True, help="Local path to an existing checkout of forge-demo-apps at the feature branch")
    parser.add_argument("--dry-run", action="store_true", help="Run tests and compute results but don't file bugs, post, or label")
    args = parser.parse_args()

    try:
        run_qa_agent(
            issue_number=args.issue_number,
            request_id=args.request_id,
            repo_path=args.repo_path,
            pr_number=args.pr_number,
            dry_run=args.dry_run,
        )
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
