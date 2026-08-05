"""
FORGE Security Agent — Stage 5 (Security).

Runs three security scanners (via shell) against a checked-out copy of the
feature branch — Semgrep (SAST), Gitleaks (secrets detection), and OWASP
Dependency-Check (dependency vulnerability scanning) — parses their output,
maps every finding to FORGE's locked Critical/High/Medium/Low schema
(Document 7) using a fixed, deterministic table per tool (never an LLM
judgment call), and:

  - Posts every finding as a severity-tagged inline PR review comment on the
    feature PR in the monorepo (forge-demo-apps) — Document 2 §4.7. Comment
    bodies are built deterministically; Claude is not asked to interpret or
    reword individual findings.
  - Creates a completed GitHub check run named "security-check" on the PR's
    head commit: conclusion "failure" if any Critical finding exists (this is
    what actually blocks merge, via the required-status-check branch
    protection rule — Build Plan 4.8), "success" otherwise. The check run
    exists independent of any label — Document 2 §3 notes branch protection
    waits on this named check resolving, not on a label being applied.
  - If there are no Critical findings: applies `security-approved` to the
    FORGE tracking issue directly (following the same agent-applies-the-label
    precedent as qa_agent.py's qa-approved; Document 6's Label Reference table
    says "Applied by: Security Reviewer" for this label, same pre-existing
    table/reality mismatch already flagged for qa-approved in the QA Agent's
    own session notes — not re-litigated here).
  - Claude is used only once per run, to write a short human-facing overview
    comment given the already-computed deterministic finding counts/severities
    — it does not re-judge severity and does not write the individual inline
    comment bodies.

Unlike QA, there is no retry-loop/attempt-counting here: Document 6 has no
`security-loop-back` or retry-limit label for this stage. Security re-scans
on every PR update; the failing check run is what blocks merge until findings
are resolved, not a retry budget.

KNOWN LIMITATION (flagged, not fixed here): re-running this agent after a fix
re-posts the full current finding set as new inline comments rather than
diffing against a prior run's comments — no de-duplication against previously
posted findings exists yet. Flagged as an open item for whoever wires Phase 4,
same pattern as other gaps already tracked in FORGE-context.

Severity mapping (fixed, per tool — Document 7: "Locked... used consistently
across SAST, secrets, and dependency scanning outputs"):
  - Gitleaks: every finding -> Critical. Gitleaks has no lesser-severity
    output category of its own; a hardcoded secret is always treated as
    Critical under this fixed table. Test/fixture project paths are excluded
    from scanning entirely via team/gitleaks-allowlist.toml (team-configurable
    per Document 7's Flexible/Locked model for the secrets detection tool) --
    a hardcoded fake key in a WebApplicationFactory or __tests__ mock never
    reaches this classifier in the first place.
  - OWASP Dependency-Check: CVSS score thresholds — >=9.0 Critical,
    >=7.0 High, >=4.0 Medium, else Low. Prefers cvssv3.baseScore, falls back
    to cvssv2.score if v3 is absent. If neither is present (rare), defaults
    to Medium (logged) rather than silently under-reporting as Low.
  - Semgrep: ERROR -> High, WARNING -> Medium, INFO -> Low. NOTE: under this
    fixed table, Semgrep findings can never be classified Critical — same
    kind of documented best-effort limitation as QA's assertion-vs-crash
    heuristic (Semgrep community rules don't expose a clean CVSS-equivalent
    score to threshold against).

Like qa_agent.py, this script needs the actual repository contents on disk —
it assumes a local checkout of the monorepo at the feature branch already
exists (passed via --repo-path), populated by the invoking GitHub Actions
job's own actions/checkout step (Phase 4, step 4.6, not yet wired). This
script does not clone anything itself.

PREREQUISITE (not yet confirmed installed as of this build — flagged,
not assumed): semgrep, gitleaks, and the OWASP dependency-check CLI must all
be on PATH wherever this script runs. Unlike QA's dotnet/npm (already
required for local app development), these three are new tooling
dependencies specific to the Security stage. See CLAUDE.md for install notes
once confirmed.

Additionally, an NVD API key is strongly recommended for
_run_dependency_check(): without one, NVD database updates are rate-limited
and can be extremely slow on every run, not just the first. If the
NVD_API_KEY environment variable is set, it's passed to dependency-check via
--nvdApiKey; if unset, the scan still runs, just slower, and a warning is
logged. The key is read from an environment variable rather than hardcoded
or passed as a bare CLI literal from this script's own arguments, consistent
with this project's "credential storage needs explicit verification"
principle -- never commit a real key to a file dependency-check reads from
disk.

Usage:
    python -m core.agents.security_agent --issue-number 2 --request-id REQ-2026-01 \\
        --pr-number 5 --repo-path /path/to/forge-demo-apps-checkout
    python -m core.agents.security_agent --issue-number 2 --request-id REQ-2026-01 \\
        --pr-number 5 --repo-path /path/to/forge-demo-apps-checkout --dry-run

CLI arguments:
    --issue-number   FORGE tracking issue number in forge-template, used to
                     post a failure comment (best-effort) and apply
                     `security-approved` when clean (required).
    --request-id     FORGE request ID. Used to locate services/<request-id>/
                     within --repo-path (required).
    --pr-number      The feature PR number in forge-demo-apps, used to resolve
                     the head SHA, post inline review comments, and create the
                     check run. Required for a real run; optional for
                     --dry-run.
    --repo-path      Local path to an existing checkout of forge-demo-apps at
                     the feature branch (required — see module docstring;
                     this script does not clone anything itself).
    --dry-run        Run all three scans, parse results, compute severities,
                     and call Claude for the overview write-up, but print
                     everything to stdout instead of posting review comments,
                     creating a check run, or applying the label.

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
from dataclasses import dataclass
from pathlib import Path

from core.agents.utils.claude_agent_wrapper import invoke_agent
from core.agents.utils.github_helper import (
    add_label,
    create_check_run,
    create_review_with_comments,
    create_single_review_comment,
    get_pr,
    post_comment,
)

logger = logging.getLogger(__name__)

_STAGE_NAME = "security"
_MAX_TOKENS = 2000
_TOOL_TIMEOUT_SECONDS = 1800  # 30 min ceiling per scanner invocation
_CHECK_RUN_NAME = "security-check"  # must match Build Plan 4.8's branch-protection required check

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GITLEAKS_ALLOWLIST_CONFIG = _REPO_ROOT / "team" / "gitleaks-allowlist.toml"

_SEV_CRITICAL = "Critical"
_SEV_HIGH = "High"
_SEV_MEDIUM = "Medium"
_SEV_LOW = "Low"


@dataclass
class Finding:
    tool: str            # "semgrep" | "gitleaks" | "dependency-check"
    severity: str         # Critical | High | Medium | Low
    path: str | None      # repo-relative file path, if applicable
    line: int | None      # 1-indexed line, if applicable
    rule_id: str
    message: str


@dataclass
class ScanResult:
    tool: str
    ran: bool
    findings: list[Finding]
    run_failure_message: str | None = None  # set when ran=False


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
        timeout=_TOOL_TIMEOUT_SECONDS,
    )


def _dependency_check_executable() -> str:
    """
    OWASP Dependency-Check ships as dependency-check.sh (Unix) or
    dependency-check.bat (Windows) — unlike semgrep/gitleaks, which are a
    single bare command name that shutil.which() already resolves correctly
    across platforms (same PATHEXT-aware resolution qa_agent.py's _run_shell
    relies on for bare "npm"). Pick the right candidate name up front so
    _run_shell's shutil.which() call has something resolvable to find.
    """
    return "dependency-check.bat" if os.name == "nt" else "dependency-check.sh"


# ---------------------------------------------------------------------------
# Semgrep (SAST)
# ---------------------------------------------------------------------------

def _run_semgrep(service_dir: str) -> ScanResult:
    with tempfile.TemporaryDirectory() as results_dir:
        json_path = Path(results_dir) / "semgrep-results.json"
        try:
            result = _run_shell(
                ["semgrep", "--config=auto", "--json", f"--output={json_path}", "."],
                cwd=service_dir,
            )
        except subprocess.TimeoutExpired:
            return ScanResult(tool="semgrep", ran=False, findings=[],
                               run_failure_message=f"semgrep timed out after {_TOOL_TIMEOUT_SECONDS}s.")

        if not json_path.exists():
            tail = (result.stdout or "")[-3000:] + (result.stderr or "")[-1000:]
            return ScanResult(
                tool="semgrep", ran=False, findings=[],
                run_failure_message=f"semgrep failed to produce a JSON report. Tail of output:\n\n{tail}",
            )
        return _parse_semgrep(json_path)


def _classify_semgrep_severity(raw_severity: str) -> str:
    """Fixed mapping (module docstring) — Semgrep can never map to Critical here."""
    mapping = {"ERROR": _SEV_HIGH, "WARNING": _SEV_MEDIUM, "INFO": _SEV_LOW}
    return mapping.get((raw_severity or "").upper(), _SEV_MEDIUM)


def _parse_semgrep(json_path: Path) -> ScanResult:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    findings: list[Finding] = []
    for r in data.get("results", []):
        extra = r.get("extra", {})
        findings.append(Finding(
            tool="semgrep",
            severity=_classify_semgrep_severity(extra.get("severity", "")),
            path=r.get("path"),
            line=(r.get("start") or {}).get("line"),
            rule_id=r.get("check_id", "unknown-rule"),
            message=(extra.get("message") or "")[:1000],
        ))
    return ScanResult(tool="semgrep", ran=True, findings=findings)


# ---------------------------------------------------------------------------
# Gitleaks (secrets detection)
# ---------------------------------------------------------------------------

def _run_gitleaks(service_dir: str) -> ScanResult:
    """
    --no-git: treat service_dir as a plain filesystem tree, not a git
    repository, so this is a directory-scoped scan of current file contents
    (what we want here), not a full commit-history scan of the whole monorepo.
    --exit-code 0: don't let gitleaks' nonzero-on-findings exit code matter —
    we determine "ran" from report-file presence, same principle as QA's
    TRX/Jest presence check, not from process exit code.
    """
    with tempfile.TemporaryDirectory() as results_dir:
        json_path = Path(results_dir) / "gitleaks-results.json"
        command = ["gitleaks", "detect", "--source", ".", "--no-git",
                   "--report-format", "json", "--report-path", str(json_path),
                   "--exit-code", "0"]
        if _GITLEAKS_ALLOWLIST_CONFIG.exists():
            command.extend(["--config", str(_GITLEAKS_ALLOWLIST_CONFIG)])
        else:
            logger.warning(
                "Gitleaks allowlist config not found at %s -- running with "
                "Gitleaks' default ruleset only (no test-path exclusions). "
                "Team-configurable per Document 7; see team/gitleaks-allowlist.toml.",
                _GITLEAKS_ALLOWLIST_CONFIG,
            )
        try:
            result = _run_shell(command, cwd=service_dir)
        except subprocess.TimeoutExpired:
            return ScanResult(tool="gitleaks", ran=False, findings=[],
                               run_failure_message=f"gitleaks timed out after {_TOOL_TIMEOUT_SECONDS}s.")

        if not json_path.exists():
            # Gitleaks omits the report file entirely when there are zero
            # findings in some versions — treat that as "ran, clean", not a
            # run failure, distinguishing it from a genuine execution error
            # via the process's own exit code (nonzero + no file = real error).
            if result.returncode == 0:
                return ScanResult(tool="gitleaks", ran=True, findings=[])
            tail = (result.stdout or "")[-3000:] + (result.stderr or "")[-1000:]
            return ScanResult(
                tool="gitleaks", ran=False, findings=[],
                run_failure_message=f"gitleaks failed to produce a report. Tail of output:\n\n{tail}",
            )
        return _parse_gitleaks(json_path)


def _parse_gitleaks(json_path: Path) -> ScanResult:
    raw = json_path.read_text(encoding="utf-8").strip()
    data = json.loads(raw) if raw else []
    findings: list[Finding] = []
    for entry in data:
        findings.append(Finding(
            tool="gitleaks",
            severity=_SEV_CRITICAL,  # fixed mapping — every gitleaks finding is Critical
            path=entry.get("File"),
            line=entry.get("StartLine"),
            rule_id=entry.get("RuleID", "unknown-rule"),
            message=(entry.get("Description") or "Potential secret detected")[:1000],
        ))
    return ScanResult(tool="gitleaks", ran=True, findings=findings)


# ---------------------------------------------------------------------------
# OWASP Dependency-Check
# ---------------------------------------------------------------------------

def _run_dependency_check(service_dir: str, request_id: str) -> ScanResult:
    with tempfile.TemporaryDirectory() as results_dir:
        command = [_dependency_check_executable(),
                   "--project", request_id,
                   "--scan", ".",
                   "--format", "JSON",
                   "--out", results_dir]

        nvd_api_key = os.environ.get("NVD_API_KEY")
        if nvd_api_key:
            command.extend(["--nvdApiKey", nvd_api_key])
        else:
            logger.warning(
                "NVD_API_KEY is not set -- dependency-check's NVD database "
                "update will be rate-limited and may be extremely slow. "
                "Set NVD_API_KEY (see https://nvd.nist.gov/developers/request-an-api-key) "
                "to avoid this on every run, not just the first."
            )

        try:
            _run_shell(command, cwd=service_dir)
        except subprocess.TimeoutExpired:
            return ScanResult(tool="dependency-check", ran=False, findings=[],
                               run_failure_message=f"dependency-check timed out after {_TOOL_TIMEOUT_SECONDS}s.")

        json_path = Path(results_dir) / "dependency-check-report.json"
        if not json_path.exists():
            return ScanResult(
                tool="dependency-check", ran=False, findings=[],
                run_failure_message="dependency-check failed to produce dependency-check-report.json.",
            )
        return _parse_dependency_check(json_path)


def _classify_dependency_check_severity(vuln: dict) -> str:
    """Fixed CVSS-threshold mapping (module docstring)."""
    score = None
    cvssv3 = vuln.get("cvssv3")
    if isinstance(cvssv3, dict) and "baseScore" in cvssv3:
        score = cvssv3["baseScore"]
    elif isinstance(vuln.get("cvssv2"), dict) and "score" in vuln["cvssv2"]:
        score = vuln["cvssv2"]["score"]

    if score is None:
        logger.warning(
            "dependency-check finding %s has no CVSS score — defaulting to Medium.",
            vuln.get("name", "unknown"),
        )
        return _SEV_MEDIUM
    if score >= 9.0:
        return _SEV_CRITICAL
    if score >= 7.0:
        return _SEV_HIGH
    if score >= 4.0:
        return _SEV_MEDIUM
    return _SEV_LOW


def _parse_dependency_check(json_path: Path) -> ScanResult:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    findings: list[Finding] = []
    for dep in data.get("dependencies", []):
        vulns = dep.get("vulnerabilities") or []
        for vuln in vulns:
            findings.append(Finding(
                tool="dependency-check",
                severity=_classify_dependency_check_severity(vuln),
                path=dep.get("filePath") or dep.get("fileName"),
                line=None,  # dependency findings are manifest-level, not line-anchored
                rule_id=vuln.get("name", "unknown-cve"),
                message=(vuln.get("description") or "")[:1000],
            ))
    return ScanResult(tool="dependency-check", ran=True, findings=findings)


# ---------------------------------------------------------------------------
# Shared: comment building, posting, orchestration
# ---------------------------------------------------------------------------

def _build_finding_comment(finding: Finding) -> str:
    return (
        f"**[{finding.severity}] {finding.tool}** — `{finding.rule_id}`\n\n"
        f"{finding.message}"
    )


def post_findings(pr_number: int, commit_sha: str, findings: list[Finding]) -> dict:
    """
    Post every line-anchored finding as one batched inline review. Findings
    with no path/line (dependency-check) or that the batch review rejects as
    outside the diff fall back to per-finding attempts, then to a single
    aggregated plain PR comment for whatever still couldn't be attached.
    """
    line_anchored = [f for f in findings if f.path and f.line]
    unanchored = [f for f in findings if not (f.path and f.line)]

    posted = 0
    fallback_failures: list[Finding] = []

    if line_anchored:
        comments = [
            {"path": f.path, "line": f.line, "body": _build_finding_comment(f)}
            for f in line_anchored
        ]
        try:
            create_review_with_comments(pr_number, commit_sha, comments)
            posted = len(comments)
        except Exception:
            logger.warning(
                "Batch review failed (likely a line outside the diff) — "
                "retrying %d finding(s) individually.",
                len(line_anchored),
            )
            for f in line_anchored:
                try:
                    create_single_review_comment(
                        pr_number, commit_sha, f.path, f.line, _build_finding_comment(f)
                    )
                    posted += 1
                except Exception:
                    fallback_failures.append(f)

    to_summarize = unanchored + fallback_failures
    if to_summarize:
        body = "**Additional security findings (couldn't attach inline — see details below):**\n\n" + "\n\n---\n\n".join(
            f"`{f.path or 'N/A'}` — {_build_finding_comment(f)}" for f in to_summarize
        )
        from core.agents.utils.github_helper import post_pr_comment
        post_pr_comment(pr_number, body)

    return {"posted_inline": posted, "posted_as_summary": len(to_summarize)}


_SYSTEM_PROMPT = """You are the FORGE Security Agent for Legal Aid Alberta's software delivery \
pipeline, writing a short human-facing overview comment for a feature PR's security check.

You will be given already-computed, deterministic scan results: which of the three tools \
(Semgrep, Gitleaks, OWASP Dependency-Check) ran successfully, finding counts by severity \
(Critical/High/Medium/Low — already decided by fixed, non-AI-judgment mapping tables), \
whether any Critical finding exists, and the check run conclusion.

Do NOT re-judge severity or re-interpret individual findings — these are already decided \
by deterministic code and must be reported exactly as given. Do not write the individual \
finding descriptions; those are posted separately as inline PR comments.

Your job is only to write a brief, clear Markdown overview comment for a human reviewer \
(the Security Reviewer, per Document 6 Gate 5). Include:
- A one-line overall verdict (blocked / clear).
- Finding counts by severity, and by tool.
- If Critical findings exist: a clear note that the security-check is failing and blocking \
merge until they're resolved — do not imply anything else will unblock it.
- If there are no Critical findings: a brief note that the security-check passed and, if \
applicable, that `security-approved` was applied to the tracking issue — but that a Security \
Reviewer's PR approval is still required regardless of finding severity (Document 6 Gate 5: \
even an all-clear scan needs an explicit human approval).

Output format — this is strict:
Respond with ONLY a single JSON object, no markdown code fences, no prose before or after it. \
It must have exactly this shape:

{
  "overview_markdown": "<string - the full Markdown overview comment body>"
}"""


def run_security_agent(
    issue_number: int,
    request_id: str,
    repo_path: str,
    pr_number: int | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Core entry point. Returns a dict summarizing the run (findings by tool,
    check run conclusion, label applied, overview text).
    """
    if not dry_run and not pr_number:
        raise ValueError(
            "--pr-number is required for a real (non-dry-run) run — it determines "
            "where inline comments and the check run are posted. Refusing to "
            "proceed without it."
        )

    service_dir = str(Path(repo_path) / "services" / request_id)

    try:
        semgrep_result = _run_semgrep(service_dir)
        gitleaks_result = _run_gitleaks(service_dir)
        depcheck_result = _run_dependency_check(service_dir, request_id)

        all_results = [semgrep_result, gitleaks_result, depcheck_result]
        all_findings = [f for r in all_results for f in r.findings]

        counts_by_severity = {sev: 0 for sev in (_SEV_CRITICAL, _SEV_HIGH, _SEV_MEDIUM, _SEV_LOW)}
        for f in all_findings:
            counts_by_severity[f.severity] += 1
        has_critical = counts_by_severity[_SEV_CRITICAL] > 0

        check_conclusion = "failure" if has_critical else "success"
        label_to_apply = None if has_critical else "security-approved"

        commit_sha = None
        if not dry_run:
            pr = get_pr(pr_number)
            commit_sha = pr["head"]["sha"]

        summary_for_model = {
            "tools_ran": {r.tool: r.ran for r in all_results},
            "tool_run_failures": {r.tool: r.run_failure_message for r in all_results if not r.ran},
            "counts_by_severity": counts_by_severity,
            "counts_by_tool": {
                r.tool: len(r.findings) for r in all_results
            },
            "has_critical": has_critical,
            "check_conclusion": check_conclusion,
            "label_to_apply": label_to_apply,
        }
        user_prompt = (
            "## Deterministic Security Scan Results (already computed — report exactly as given)\n\n"
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
                "increase _MAX_TOKENS in security_agent.py and retry."
            )
        text = result.output_text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed_output = json.loads(text)
        overview_markdown = parsed_output["overview_markdown"]

    except Exception as exc:
        logger.exception("Security Agent failed for request %s", request_id)
        if not dry_run:
            failure_body = (
                "⚠️ **FORGE Security Agent failed to complete.**\n\n"
                f"Error: `{exc}`\n\n"
                "An Orchestration Manager needs to investigate before this request "
                "can proceed. Do not apply `security-approved` yet."
            )
            try:
                post_comment(issue_number, failure_body)
            except Exception:
                logger.exception("Also failed to post failure comment to issue #%s", issue_number)
        raise

    run_summary = {
        "counts_by_severity": counts_by_severity,
        "counts_by_tool": {r.tool: len(r.findings) for r in all_results},
        "check_conclusion": check_conclusion,
        "label_to_apply": label_to_apply,
        "overview_markdown": overview_markdown,
    }

    if dry_run:
        print("=" * 20, "scan summary", "=" * 20)
        print(json.dumps(summary_for_model, indent=2))
        print("=" * 20, "overview comment (not posted)", "=" * 20)
        print(overview_markdown)
        print("=" * 20, "check run (not created)", "=" * 20)
        print(f"name={_CHECK_RUN_NAME} conclusion={check_conclusion}")
        print("=" * 20, "label (not applied)", "=" * 20)
        print(label_to_apply or "(none — Critical findings present)")
        logger.info(
            "Dry run complete for request %s -- nothing posted, nothing labeled.",
            request_id,
        )
        return run_summary

    post_findings(pr_number, commit_sha, all_findings)

    from core.agents.utils.github_helper import post_pr_comment
    post_pr_comment(pr_number, overview_markdown)

    create_check_run(
        head_sha=commit_sha,
        name=_CHECK_RUN_NAME,
        conclusion=check_conclusion,
        title="Security scan: blocked" if has_critical else "Security scan: passed",
        summary=overview_markdown,
    )

    if label_to_apply:
        add_label(issue_number, label_to_apply)

    logger.info(
        "Security Agent complete for request %s -- check_conclusion=%s, %d finding(s) "
        "(%d Critical), label=%s.",
        request_id, check_conclusion, len(all_findings),
        counts_by_severity[_SEV_CRITICAL], label_to_apply,
    )
    return run_summary


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE Security Agent")
    parser.add_argument("--issue-number", required=True, type=int, help="FORGE tracking issue number in forge-template")
    parser.add_argument("--request-id", required=True, help="FORGE request ID")
    parser.add_argument("--pr-number", default=None, type=int, help="Feature PR number in forge-demo-apps (required for a real run)")
    parser.add_argument("--repo-path", required=True, help="Local path to an existing checkout of forge-demo-apps at the feature branch")
    parser.add_argument("--dry-run", action="store_true", help="Run scans and compute results but don't post, check, or label")
    args = parser.parse_args()

    try:
        run_security_agent(
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
