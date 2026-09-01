"""
FORGE Implementation Coordinator — Stage 3 (Implementation, ADR-0010).

Runs a Managed Agents coordinator session that delegates to Backend, Frontend, and
Test Writer specialist subagents on a shared sandbox filesystem. Reads design.md,
openapi.yaml, and tasks.md (committed to the monorepo by the Design Agent), waits
for the subagents to finish, retrieves the resulting implementation as a single
archive via the Files API, extracts it, and commits the result to
feature/<request-id> in the monorepo before opening a draft PR.

Packaging convention (see coordinator system prompt below): the coordinator
packages the ENTIRE services/<request-id>/ directory tree into exactly one file --
/mnt/session/outputs/implementation.tar.gz -- before finishing. This sidesteps an
open question in Anthropic's own docs about whether nested directory structure
survives the Files API's flat "filename" field: a single well-known archive name
avoids the question entirely, and lets Python's tarfile module (not the model)
be the thing that guarantees exact path fidelity when reconstructing the file
dict commit_files() expects.

Usage:
    python -m core.agents.implementation_coordinator --issue-number 2 --request-id REQ-2026-01
    python -m core.agents.implementation_coordinator --issue-number 2 --request-id REQ-2026-01 --dry-run

CLI arguments:
    --issue-number   FORGE tracking issue number in forge-template, used to post
                      the summary/failure comment (required).
    --request-id      FORGE request ID. Required for a real run (determines the
                      services/<request-id> target directory and the
                      feature/<request-id> branch); optional for --dry-run.
    --dry-run         Runs the REAL Managed Agents session (this is the expensive,
                      meaningful part -- there's no cheap way to simulate a
                      multi-agent coordinator run) but skips commit/PR/comment.
                      Prints the session ID, Console link, and the files that
                      would have been committed.

Per ADR-0011 / Document 6's hard-requirement pattern (extended here to Stage 3's
Managed Agents call, not just the Messages API calls it was originally written
for): run_implementation_stage() is wrapped in try/except at the call site. On
failure, a failure comment is posted to the tracking issue (best-effort, real run
only) before the exception is re-raised.
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import re
import sys
import tarfile

from core.agents.subagents import (
    EXISTING_SERVICE_MOUNT_DIR,
    SHARED_DOCS_DIR,
    backend_agent,
    frontend_agent,
    test_writer_agent,
)
from core.agents.utils.existing_service_files import (
    select_existing_service_files,
    select_seed_blobs,
)
from core.agents.utils.github_helper import (
    get_file_contents,
    get_issue_comments,
    get_repo_tree,
    post_comment,
    create_branch,
    commit_files,
    open_pr,
)
from core.agents.utils.managed_agents_wrapper import (
    run_implementation_stage,
    list_session_output_files,
    download_file_content,
    upload_input_file,
    get_session_resource_ids,
    get_thread_statuses,
    archive_session,
    SessionStillRunningError,
)

logger = logging.getLogger(__name__)

_STAGE_NAME = "implementation"

# Item #34 (docs/Specs/FORGE-Item34-CostEstimator-Spec.md §2.1): coarse,
# shape-bucketed pre-flight cost heuristic for Stage 3 -- NOT a trained
# model, NOT a hard limit (no threshold is stored anywhere, per Mike's
# explicit 2026-08-31 decision -- this is purely informative). Bucketed by
# (unit_count, is_enhancement). Confirmed live 2026-08-31: every logged
# Stage 3 actual to date is 2-unit (REQ-2026-01/02/03/04 all have both
# "## Backend" and "## Frontend" in tasks.md) -- zero real precedent exists
# for either 1-unit bucket. Those two use a fixed 0.5x scale-down of their
# same-enhancement-status 2-unit sibling (Mike's explicit call), not a real
# historical average -- flagged as low-confidence wherever surfaced.
# Revisit ALL FOUR constants once more real runs land, especially
# (2, True)'s single-data-point mean.
_COST_BASELINES_USD: dict[tuple[int, bool], float] = {
    (2, False): 8.96,   # mean of REQ-2026-01 ($12.31), REQ-2026-02 ($6.63), REQ-2026-03 recovered ($7.95)
    (2, True): 4.57,    # REQ-2026-04/PR#32 only real data point (session sesn_01GBkGBfEYEBLJLcc9Ftyqhv)
    (1, False): 8.96 * 0.5,
    (1, True): 4.57 * 0.5,
}

# The confirmed real seed file count from the corrected REQ-2026-04/PR#32
# run (verified via live tool-use events, same count as the earlier
# interrupted attempt since the mount-path bug only affected file
# resolution, not the selection list). A single data point -- the same
# low-confidence caveat as the (2, True) baseline above applies here too.
_ENHANCEMENT_REFERENCE_SEED_SIZE = 87

_ARCHIVE_FILENAME = "implementation.tar.gz"
_ARCHIVE_SANDBOX_PATH = f"/mnt/session/outputs/{_ARCHIVE_FILENAME}"
_CONSOLE_SESSION_URL_PREFIX = "https://platform.claude.com/sessions/"


_COORDINATOR_SYSTEM_PROMPT = f"""You are the FORGE Implementation Coordinator for \
Legal Aid Alberta's software delivery pipeline (Stage 3). You manage three \
specialist subagents -- Backend, Frontend, and Test Writer -- who share your \
sandbox filesystem and work on the same request.

You will be given design.md, openapi.yaml, and tasks.md for this request, plus the \
target directory (a path under services/ in the monorepo) all three subagents will \
write into.

Your job:
0. Before delegating anything, write the design.md, openapi.yaml, and tasks.md \
content you were given to these exact paths on your sandbox filesystem: \
{SHARED_DOCS_DIR}/design.md, {SHARED_DOCS_DIR}/openapi.yaml, {SHARED_DOCS_DIR}/tasks.md. \
Tell Backend and Frontend to read these files directly rather than relying on your \
own summary of them in the delegation message -- this is deliberate: a paraphrased \
relay of a structured contract like openapi.yaml risks a dropped or renamed field \
neither subagent could catch without the literal source to check against.
1. Check whether {EXISTING_SERVICE_MOUNT_DIR} exists and has files on your sandbox \
filesystem. If it does, this is an Enhancement to an existing service -- those \
files are the real, current implementation, mounted READ-ONLY for reference (you \
cannot edit them in place). Before delegating anything, copy the relevant existing \
files from {EXISTING_SERVICE_MOUNT_DIR} into your actual target directory (the one \
you were given below) so Backend/Frontend/Test Writer have a real, writable \
starting point to edit rather than an empty directory or a read-only mount they \
can't write through. Tell Backend and Frontend this has been done, and that \
{EXISTING_SERVICE_MOUNT_DIR} remains available afterward as a read-only reference \
if they need to double-check something against the original. If \
{EXISTING_SERVICE_MOUNT_DIR} does not exist or is empty, this is a Greenfield \
request -- start from the empty target directory as usual, there is nothing to copy.
2. Delegate the Backend, Frontend, and Test Writer sections of tasks.md to the \
matching subagent. Let Backend and Frontend work in parallel; Test Writer should \
start once there's real code for it to test against.
3. Check in on all three as they work. When a subagent reports its portion done, \
verify it actually did what tasks.md asked -- spot-check the files it wrote.
4. Perform integration checking yourself: confirm the frontend's API calls actually \
match the endpoints Backend implemented and the contract in openapi.yaml; resolve \
any mismatch by asking the relevant subagent to fix it, or fixing it directly if \
it's a small inconsistency (e.g. a route casing or field-name mismatch).
5. Once all three are done and consistent, package the ENTIRE target directory \
(everything under the path you were given) into a single gzip-compressed tar \
archive at exactly this path: {_ARCHIVE_SANDBOX_PATH}

   Critical packaging rules:
   - Paths inside the archive MUST be relative and MUST start with the target \
directory itself (e.g. "services/REQ-2026-01/backend/Controllers/..."). Do NOT \
strip the leading path or use absolute paths.
   - Do NOT include build output or installed dependencies in the archive: no \
bin/, obj/, node_modules/, .next/, dist/, or similar directories. Only source and \
config files that should actually be committed to the repository.
   - Every file in the archive must be UTF-8 text -- this implementation targets \
source code and config, not binary assets.
   - A command like this works well: `tar --exclude=node_modules --exclude=bin \
--exclude=obj --exclude=.next --exclude=dist -czf {_ARCHIVE_SANDBOX_PATH} \
<parent-of-target>/<target-directory-name>` -- adjust excludes for what you \
actually produced, and verify with `tar -tzf {_ARCHIVE_SANDBOX_PATH}` that the \
paths inside look correct (relative, prefixed with the target directory) before \
finishing.
6. Confirm the archive was created successfully (nonzero size, contents look \
right) before ending your turn. State "IMPLEMENTATION COMPLETE" once you've \
verified this.

Do not invent requirements not present in tasks.md/design.md. If something is \
ambiguous, make a reasonable, clearly-stated assumption rather than blocking -- a \
human reviews the resulting PR regardless."""


def _build_initial_message(
    design_md: str,
    openapi_yaml_text: str,
    tasks_md: str,
    service_root: str,
    existing_service: str | None = None,
) -> str:
    enhancement_note = (
        (
            f"This is an Enhancement to the existing service `services/{existing_service}`. "
            f"Its current files have been mounted read-only at {EXISTING_SERVICE_MOUNT_DIR} "
            "-- per your step 1, copy what's relevant into your target directory before "
            "delegating.\n\n"
        )
        if existing_service
        else ""
    )
    return (
        f"Your target directory for this request is: {service_root}\n\n"
        f"{enhancement_note}"
        "## design.md\n\n"
        f"{design_md}\n\n"
        "## openapi.yaml\n\n"
        f"{openapi_yaml_text}\n\n"
        "## tasks.md\n\n"
        f"{tasks_md}\n\n"
        "---\n"
        "Begin. Delegate to Backend and Frontend now; bring in Test Writer once "
        "there's real code for it to test."
    )


def _count_tasks_md_units(tasks_md: str) -> int:
    """
    Reuses the exact same case-insensitive "backend"/"frontend" substring
    check as _sanity_check_extracted_files() (tasks.md's own section headers
    per _COORDINATOR_SYSTEM_PROMPT's delegation) to derive unit_count for
    Item #34's cost estimate: 1 if only one of backend/frontend appears, 2 if
    both. Test Writer is not counted separately -- it never runs without at
    least one of the other two.

    Clamped to [1, 2] defensively: every real request logged so far mentions
    at least one of the two, but _COST_BASELINES_USD has no (0, *) bucket, so
    a tasks.md that somehow mentions neither must not KeyError here.
    """
    lowered = tasks_md.lower()
    raw_count = sum(1 for unit in ("backend", "frontend") if unit in lowered)
    return max(1, min(2, raw_count))


def _round_to_nearest_half(amount: float) -> float:
    return round(amount * 2) / 2


def _estimate_implementation_cost(
    tasks_md: str,
    is_enhancement: bool,
    enhancement_seed_file_count: int = 0,
) -> dict:
    """
    Item #34 §2.1: combines two pre-flight-knowable signals that correlate
    with cache-read/cache-creation token volume (the dominant real Stage 3
    cost driver, per docs/FORGE-pipeline-cost-log.md) with a hardcoded
    historical baseline for the closest-matching shape -- how many of
    backend/frontend tasks.md calls for, and (for Enhancement requests) how
    many existing-service files must be seeded into the sandbox. See
    _COST_BASELINES_USD above for the real data behind each bucket, and
    docs/Specs/FORGE-Item34-CostEstimator-Spec.md §2.1 for the full narrative.

    This is deliberately a coarse, shape-bucketed heuristic, not a trained
    model -- it will get better as more real runs land (especially any
    single-unit or additional Enhancement data), not by adding more inputs to
    this formula. A live check during this feature's own build (correlating
    combined design.md+openapi.yaml+tasks.md character count against the 4
    real logged actuals) found NO usable correlation there either -- the
    four requests cluster within a ~28% size range while cost varies by
    2.7x -- so this intentionally does not chase a fancier per-character
    formula that would just be overfitting 4 noisy points into false
    precision.

    Returns a dict with "unit_count", "is_enhancement",
    "enhancement_seed_file_count", "bucket", "baseline", "low", "high"
    (rounded to nearest $0.50, presented as baseline +/- 25%), and
    "low_confidence" (True for a 1-unit bucket, since neither has any real
    precedent -- see _COST_BASELINES_USD).
    """
    unit_count = _count_tasks_md_units(tasks_md)
    bucket = (unit_count, is_enhancement)
    baseline = _COST_BASELINES_USD[bucket]

    if is_enhancement:
        baseline *= 1 + (enhancement_seed_file_count / _ENHANCEMENT_REFERENCE_SEED_SIZE)

    return {
        "unit_count": unit_count,
        "is_enhancement": is_enhancement,
        "enhancement_seed_file_count": enhancement_seed_file_count,
        "bucket": bucket,
        "baseline": baseline,
        "low": _round_to_nearest_half(baseline * 0.75),
        "high": _round_to_nearest_half(baseline * 1.25),
        "low_confidence": unit_count == 1,
    }


def _build_cost_estimate_comment(request_id: str, estimate: dict) -> str:
    """
    Item #34 §2.2.A.4/§2.4: the tracking-issue comment posted when
    design-approved lands, before the real coordinator session is created.
    This is the human's basis for the yes/no `cost-approved` call -- says so
    explicitly (no stored threshold anywhere, per Mike's 2026-08-31
    decision).

    Carries a hidden marker (same `<!-- forge:agent-comment ... -->`
    convention every other agent comment uses) encoding the estimate's low/
    high/bucket values as key=value pairs on the marker line itself, so
    _fetch_cost_estimate() can re-parse them later without needing a new
    CLI arg/env var threaded across two separate workflow steps that don't
    share state today (see that function's docstring for why this is the
    first place in the codebase parsing structured data out of a marker,
    not just checking presence/counting occurrences).
    """
    bucket_label = (
        f"{estimate['unit_count']}-unit "
        f"{'Enhancement' if estimate['is_enhancement'] else 'Greenfield'}"
    )
    enhancement_note = (
        f"\n\nThis is an Enhancement — **{estimate['enhancement_seed_file_count']}** "
        "existing-service file(s) will be seeded read-only into the sandbox, which "
        "increases the baseline (more real code for the coordinator/subagents to "
        "read before editing)."
        if estimate["is_enhancement"] else ""
    )
    low_confidence_note = (
        "\n\n⚠️ **No real cost history exists yet for a single-unit build.** This "
        "range is a rough 0.5x scale-down of the two-unit baseline, not a real "
        "historical average — treat it with extra skepticism."
        if estimate["low_confidence"] else ""
    )
    marker = (
        f"<!-- forge:agent-comment stage=implementation-estimate request_id={request_id} "
        f"low={estimate['low']} high={estimate['high']} "
        f"bucket_unit_count={estimate['unit_count']} "
        f"bucket_is_enhancement={estimate['is_enhancement']} -->"
    )
    return (
        f"{marker}\n"
        "## 💰 FORGE Implementation Cost Estimate\n\n"
        f"Estimated Stage 3 (Implementation) cost for `{request_id}`: "
        f"**${estimate['low']:.2f}–${estimate['high']:.2f}** (bucket: {bucket_label})."
        f"{enhancement_note}"
        f"{low_confidence_note}\n\n"
        "This is a coarse, shape-bucketed estimate based on historical Stage 3 "
        "runs — not a hard limit and not a precise prediction. Review and apply "
        "`cost-approved` to proceed, or investigate further if this looks high "
        "for the scope."
    )


def _get_enhancement_service_blobs(existing_service: str) -> list[dict]:
    """
    Item #23's Layer 2 "strict rejection over silent auto-remap" backstop
    (shared by _resolve_enhancement_target() and Item #34's
    _count_enhancement_seed_files()): an empty tree under
    services/<existing_service>/ is a real, human-actionable mismatch (a
    wrong/mistyped "Existing Service Name" on the intake spreadsheet), not a
    benign no-op -- raises rather than silently falling back to the request
    ID or to Greenfield bucketing. Callers' own ADR-0011 try/except wraps this
    and posts a failure comment before re-raising.
    """
    service_prefix = f"services/{existing_service}/"
    blobs = get_repo_tree(service_prefix)
    if not blobs:
        raise ValueError(
            f"No files found under '{service_prefix}' in the target monorepo -- "
            f"the 'If Enhancement -- Existing Service Name' value "
            f"('{existing_service}') does not match any real services/ folder. "
            "Refusing to guess or silently fall back to the request ID."
        )
    return blobs


def _count_enhancement_seed_files(existing_service: str) -> int:
    """
    Item #34 §2.2.A.2: cost-estimate-only counterpart to
    _resolve_enhancement_target() -- resolves the same blob list via
    get_repo_tree()/select_seed_blobs() but never fetches file content or
    calls upload_input_file(), since the estimate step only needs a count and
    must not do real work that's wasted if the estimate leads to a "no".
    """
    blobs = _get_enhancement_service_blobs(existing_service)
    return len(select_seed_blobs(blobs))


def _resolve_enhancement_target(existing_service: str) -> tuple[str, list[dict]]:
    """
    Item #23 (§2.1/§2.2): resolves the real service_root for an Enhancement
    request and builds the session `resources[]` list that seeds the existing
    service's files read-only at EXISTING_SERVICE_MOUNT_DIR.

    Returns:
        Tuple of (service_root, resources) -- service_root is the real
        existing services/<existing_service> path (no trailing slash, same
        shape as the Greenfield f"services/{request_id}"); resources is the
        session resources[] list ready to pass to run_implementation_stage().
    """
    service_prefix = f"services/{existing_service}/"
    blobs = _get_enhancement_service_blobs(existing_service)
    files_to_seed = select_existing_service_files(blobs)
    resources: list[dict] = []
    for repo_path, content in files_to_seed.items():
        rel_path = repo_path[len(service_prefix):]
        file_id = upload_input_file(content, filename=os.path.basename(repo_path))
        resources.append({
            "type": "file",
            "file_id": file_id,
            "mount_path": f"{EXISTING_SERVICE_MOUNT_DIR}/{rel_path}",
        })
    logger.info(
        "Enhancement target resolved: services/%s -- seeded %d file(s) read-only at %s",
        existing_service, len(resources), EXISTING_SERVICE_MOUNT_DIR,
    )
    return f"services/{existing_service}", resources


def _extract_archive_to_file_dict(archive_bytes: bytes, expected_prefix: str) -> dict[str, str]:
    """
    Extract the coordinator's implementation.tar.gz into a {path: content} dict
    ready for github_helper.commit_files().

    Args:
        archive_bytes: Raw gzip-tar bytes downloaded via download_file_content().
        expected_prefix: The services/<request-id> path every archive member's
            path must start with -- guards against the coordinator having tarred
            the wrong working directory.

    Returns:
        Dict mapping monorepo-relative path -> UTF-8 file content.

    Raises:
        ValueError: If a member is outside expected_prefix in a way that leaves
            nothing usable, or if a member is not valid UTF-8.
        RuntimeError: If extraction yields no files at all.

    Note: REQ-2026-02 (2026-08-11) hit a case where the coordinator tarred the
    archive rooted at just "<request-id>/..." instead of the full
    "services/<request-id>/..." its own system prompt asked for. A remap
    fallback was added and then deliberately REVERTED (same day) -- n=1, no
    reproducibility test, and a standing auto-remap would quietly weaken this
    guard for every future run based on one unproven hypothesis about why it
    happened. Strict rejection stays the behavior. If this recurs, that's real
    evidence -- fix it then, with data, not a guess now. See CLAUDE.md.

    Item #8: a second, narrower rejection rule follows the same strict-
    rejection-no-auto-remap philosophy as the expected_prefix guard above --
    any member with a literal ".github" path segment (not a substring match:
    a legitimately named path like ".../mygithubutil/foo.cs" must NOT be
    caught) is skipped with a warning. Two confirmed live incidents
    (REQ-2026-01 commit 3397617, REQ-2026-02 commit 47b3fef) had a subagent
    write a nested .github/workflows/*.yml file that's legal per every rule
    in force but useless as CI (GitHub only recognizes .github/workflows/ at
    the real repo root). This is a backstop for Design Agent's tasks.md
    scope-boundary prompt fix (Item #8 Layer 1) -- catches it even if that
    prompt guidance is imperfect. Never auto-promoted to the real repo-root
    .github/workflows/ location -- that's a meaningfully higher-stakes action
    than this fix's scope and should only ever happen as a deliberate human
    decision.
    """
    files: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            path = member.name.lstrip("./")
            if not (path == expected_prefix or path.startswith(expected_prefix + "/")):
                logger.warning(
                    "Archive member '%s' is outside expected prefix '%s' -- skipping "
                    "(coordinator may have tarred the wrong working directory).",
                    path, expected_prefix,
                )
                continue
            if ".github" in path.split("/"):
                logger.warning(
                    "Archive member '%s' is a nested .github/ path -- skipping "
                    "(CI/workflow files are owned by forge-template, not "
                    "generated per-request).",
                    path,
                )
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            content_bytes = extracted.read()
            try:
                files[path] = content_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(
                    f"Archive member '{path}' is not valid UTF-8 -- commit_files() "
                    "only supports UTF-8 text content. Binary assets should not be "
                    "part of the generated implementation."
                ) from exc

    if not files:
        raise RuntimeError(
            f"Extracted archive contained no files under expected prefix "
            f"'{expected_prefix}' -- nothing to commit."
        )
    return files


# Deliberately conservative -- comfortably below every real run logged in
# docs/FORGE-pipeline-cost-log.md (smallest so far: DRYRUN-2026-01's 24 files /
# 15,072-byte archive) while still catching a genuinely degenerate archive
# (e.g. a single stub file from a session that errored out mid-packaging).
_MIN_ARCHIVE_FILES = 3
_MIN_ARCHIVE_BYTES = 500


def _sanity_check_extracted_files(
    files_to_commit: dict[str, str], service_root: str, tasks_md: str
) -> None:
    """
    Guard against committing a partial/truncated archive silently.

    Two checks, deliberately NOT hardcoding "every request must have both a
    backend and a frontend unit" -- some requests are legitimately backend-only
    (e.g. DRYRUN-2026-01), and that's not a failure:

    1. Minimum total file count / byte size -- catches an archive that's
       trivially too small to be a real implementation at all.
    2. For each unit tasks.md actually calls for (detected by a simple
       case-insensitive substring check -- tasks.md's own section headers are
       "Backend" / "Frontend" per the coordinator's delegation, see
       _COORDINATOR_SYSTEM_PROMPT), require at least 2 files under
       services/<request-id>/<unit>/ in the archive. A unit tasks.md doesn't
       mention isn't checked at all -- its absence is expected, not a defect.

    Raises:
        RuntimeError: If either check fails. Treat as a failed recovery/run --
            do not commit the extracted files.
    """
    total_files = len(files_to_commit)
    total_bytes = sum(len(content) for content in files_to_commit.values())
    if total_files < _MIN_ARCHIVE_FILES or total_bytes < _MIN_ARCHIVE_BYTES:
        raise RuntimeError(
            f"Extracted archive looks too small to be a real implementation: "
            f"{total_files} file(s), {total_bytes} byte(s) total (minimums: "
            f"{_MIN_ARCHIVE_FILES} files / {_MIN_ARCHIVE_BYTES} bytes). "
            "Treating this as a failed/truncated result -- refusing to commit."
        )

    for unit in ("backend", "frontend"):
        if unit not in tasks_md.lower():
            continue
        prefix = f"{service_root}/{unit}/"
        present = [p for p in files_to_commit if p.startswith(prefix)]
        if len(present) < 2:
            raise RuntimeError(
                f"tasks.md calls for a {unit} unit, but the extracted archive "
                f"has only {len(present)} file(s) under {prefix} -- looks like "
                "a truncated/partial archive. Refusing to commit."
            )


def _detect_missing_secrets_declaration(design_md: str) -> bool:
    """
    Deterministic, flag-only completeness check (Item #1 Option 1): does this
    request's design.md declare a "## Required Secrets" section at all.

    This is NOT a secrets-accuracy or code-correctness check -- a present
    section is never verified against what the generated code actually reads,
    and a missing section never blocks implementation. It only confirms
    whether the author wrote the section down, so a gap like
    req-2026-01-email-worker's undeclared Service Bus connection string
    surfaces here (before merge) instead of being discovered later as a live
    crash loop. design_agent.py (Item #1 §2.1) writes this section
    unconditionally, including a literal "None identified" when nothing
    applies -- so "missing" is unambiguous: the author never declared,
    not "declared none."

    Callers are responsible for keeping a design.md *fetch failure* entirely
    separate from this function's result -- this function must only ever be
    called with content that was actually fetched. See
    _build_secrets_declaration_flag() for how the two cases get distinct
    wording.
    """
    return "## Required Secrets" not in design_md


def _build_secrets_declaration_flag(
    missing_secrets_declaration: bool,
    secrets_check_fetch_error: str | None,
) -> str | None:
    """
    Renders the (optional) secrets-declaration flag paragraph appended to the
    tracking-issue comment -- mirrors deploy_agent.py's _detect_design_gaps()
    conditional-append shape, but for two genuinely distinct problems that
    must not collapse into the same wording (a missing section is a real,
    confirmed finding; a fetch failure means the check simply couldn't run):

    - secrets_check_fetch_error set: design.md could not be read at all for
      this check -- say so explicitly rather than silently treating it as
      "missing" (which would be a false positive) or silently dropping it
      (which would hide a real fetch problem).
    - missing_secrets_declaration True (and no fetch error): design.md was
      read successfully but has no "## Required Secrets" section.
    - Neither: no paragraph at all.
    """
    if secrets_check_fetch_error:
        return (
            "⚠️ **Could not check for a `## Required Secrets` declaration** -- "
            f"fetching design.md failed (`{secrets_check_fetch_error}`). This is "
            "a fetch problem, not a confirmed missing declaration -- an "
            "Orchestration Manager should check design.md manually."
        )
    if missing_secrets_declaration:
        return (
            "⚠️ **design.md has no `## Required Secrets` section.** This is a "
            "completeness check only -- it confirms the section was never "
            "declared, not that any secrets are missing or misconfigured in the "
            "generated code. An Orchestration Manager should confirm whether "
            "this service needs secrets and, if so, add the section to "
            "design.md before this ships further."
        )
    return None


def _commit_and_open_pr(
    request_id: str,
    service_root: str,
    session_id: str,
    issue_number: int,
    files_to_commit: dict[str, str],
    recovered: bool = False,
    existing_service: str | None = None,
    missing_secrets_declaration: bool = False,
    secrets_check_fetch_error: str | None = None,
    cost_estimate: dict | None = None,
    actual_cost_usd: float | None = None,
) -> dict:
    """
    Shared tail end for both the normal happy path and a manual session
    recovery: commit files_to_commit to feature/<request_id>, open the draft
    PR, and post the tracking-issue comment. Deliberately factored out so
    recover_implementation_session() doesn't duplicate this logic.

    Args:
        existing_service: Item #23 §2.3 -- when set (an Enhancement run), adds
            a "Related service: services/<existing_service>/" traceability
            line to both the PR body and the tracking-issue comment. Omitted
            entirely (no empty/placeholder line) on a Greenfield run.
        missing_secrets_declaration: Item #1 Option 1 §2.2 -- True when
            design_md was fetched successfully but has no "## Required
            Secrets" section. Flag-only, never blocks. See
            _detect_missing_secrets_declaration().
        secrets_check_fetch_error: Item #1 Option 1 §2.2 -- set instead of
            missing_secrets_declaration when design.md itself couldn't be
            fetched for this check, so that case gets its own distinct
            wording rather than being conflated with a confirmed-missing
            section. See _build_secrets_declaration_flag().
        cost_estimate: Item #34 §2.3 -- the dict returned by
            _fetch_cost_estimate(), or None if no prior estimate comment was
            found for this request. Only used together with
            actual_cost_usd -- see below.
        actual_cost_usd: Item #34 §2.3 -- this session's real cost from
            _extract_actual_cost_usd(), or None if the session's usage data
            didn't carry a cost figure. The "estimate vs. actual" section is
            only appended when BOTH this and cost_estimate are present --
            not called at all from recover_implementation_session(), which
            doesn't fetch either, so that path's comment is unaffected.

    Returns:
        Dict with "pr_number" and "pr_url".
    """
    branch_name = f"feature/{request_id}"
    create_branch(branch_name, from_branch="main")
    commit_files(
        branch_name=branch_name,
        files=files_to_commit,
        commit_message=f"FORGE Implementation Coordinator: implement {request_id}",
    )

    owner = os.environ.get("FORGE_GITHUB_OWNER", "")
    source_repo = os.environ.get("FORGE_SOURCE_REPO", "forge-template")
    # NOTE: must stay qualified (owner/repo#N), not bare #N -- workflow_glue.py's
    # resolve_tracking_issue() greps the PR body for "<source_repo>#N" to find
    # the tracking issue from 04-qa.yml/05-security.yml's repository_dispatch
    # payload, which only carries a PR number/SHA, never the tracking issue.
    # A bare "#N" broke this on the DRYRUN-2026-01 recovery.
    tracking_issue_ref = f"{owner}/{source_repo}#{issue_number}" if owner else f"#{issue_number}"

    recovery_note = (
        "\n\n_Recovered manually from a session that outlived the automated "
        "job's completion-wait ceiling -- the session itself finished "
        "normally on its own; no implementation work was lost or duplicated._"
        if recovered else ""
    )
    related_service_line = (
        f"Related service: services/{existing_service}/\n\n" if existing_service else ""
    )

    pr = open_pr(
        title=f"FORGE Implementation: {request_id}",
        body=(
            f"Implementation for {request_id} ({service_root}), generated "
            "by the FORGE Implementation Coordinator (Backend + Frontend + Test "
            "Writer subagents via Anthropic Managed Agents -- ADR-0010).\n\n"
            f"Related FORGE tracking issue: {tracking_issue_ref}\n\n"
            f"{related_service_line}"
            f"Managed Agents session: `{session_id}` -- per-subagent audit trail in "
            f"the Claude Console: {_CONSOLE_SESSION_URL_PREFIX}{session_id}\n\n"
            "Merge to approve (Document 6 Gate 3)."
            f"{recovery_note}"
        ),
        head_branch=branch_name,
        base_branch="main",
        draft=True,
    )

    recovered_note_comment = (
        "**Note:** this PR was recovered manually from a session that "
        "outlived the automated job's completion-wait ceiling -- the session "
        "finished normally on its own; nothing was lost or duplicated.\n\n"
        if recovered else ""
    )
    secrets_flag_message = _build_secrets_declaration_flag(
        missing_secrets_declaration, secrets_check_fetch_error
    )
    secrets_flag_section = f"{secrets_flag_message}\n\n" if secrets_flag_message else ""
    cost_section = ""
    if cost_estimate is not None and actual_cost_usd is not None:
        cost_bucket_label = (
            f"{cost_estimate['unit_count']}-unit "
            f"{'Enhancement' if cost_estimate['is_enhancement'] else 'Greenfield'}"
        )
        cost_section = (
            "### 💰 Cost estimate vs. actual\n"
            f"Estimated: ${cost_estimate['low']:.2f}–${cost_estimate['high']:.2f} "
            f"(bucket: {cost_bucket_label})\n"
            f"Actual: ${actual_cost_usd:.2f} (from this session's usage)\n\n"
        )
    comment_body = (
        f"<!-- forge:agent-comment stage=implementation request_id={request_id} -->\n"
        f"## 🛠️ FORGE Implementation — Draft Ready for Review"
        f"{' (recovered)' if recovered else ''}\n\n"
        f"The Implementation Coordinator ran Backend, Frontend, and Test Writer as "
        f"subagents (Managed Agents session `{session_id}`), committed the result "
        f"to `{service_root}/` on branch `{branch_name}`, and opened a draft PR: "
        f"{pr['html_url']}\n\n"
        f"{related_service_line}"
        f"Per-subagent audit trail: {_CONSOLE_SESSION_URL_PREFIX}{session_id}\n\n"
        "---\n"
        f"{recovered_note_comment}"
        f"{secrets_flag_section}"
        f"{cost_section}"
        "QA and Security are already running in parallel -- both trigger "
        "automatically now that this PR is open, and will post their own results "
        "directly on it. Review the diff; mark it ready for review and merge when "
        "you're satisfied and QA/Security are clear."
    )
    post_comment(issue_number, comment_body)
    logger.info(
        "Implementation %s for request %s -- PR #%s opened, summary posted to issue #%s.",
        "recovery complete" if recovered else "Coordinator complete",
        request_id, pr["number"], issue_number,
    )
    return {"pr_number": pr["number"], "pr_url": pr["html_url"]}


def recover_implementation_session(
    session_id: str,
    issue_number: int,
    request_id: str,
    dry_run: bool = False,
    existing_service: str | None = None,
) -> dict:
    """
    Recover a session left alive by a SessionStillRunningError (or one that
    outlived a killed local process, per the REQ-2026-01/DRYRUN-2026-01
    incidents) -- WITHOUT re-invoking the coordinator, which would create a
    duplicate, separately-billed session on top of one that may still be
    working or may have already finished on its own.

    Derives coordinator_id/environment_id/subagent_ids straight from the
    session_id via get_session_resource_ids() -- no need to dig the
    managed_agents_session_start log line out of a GitHub Actions run.

    Checks live thread status directly. If any thread is still busy, reports
    status and returns without touching the monorepo or GitHub at all --
    "not ready yet" is a normal, expected outcome here, not an error.

    If every thread is idle, sanity-checks the output archive
    (_sanity_check_extracted_files()) before committing anything, then runs
    the same commit/PR/comment sequence the happy path uses, and finally
    archives the session (left alive specifically so this recovery could
    reach it).

    Args:
        existing_service: Item #23 -- pass the SAME "Existing Service Name"
            value the original (still-running) session was started with, if
            it was an Enhancement request. Only used to resolve the correct
            service_root string for archive-prefix matching and the PR's
            "Related service" line -- recovery never re-seeds sandbox
            resources (the session already has them; re-fetching/re-uploading
            here would be pointless and could raise on a tree that's since
            changed). Getting this wrong on an Enhancement recovery fails
            loudly (an expected_prefix mismatch in
            _extract_archive_to_file_dict()), not silently.

    Returns:
        Dict with "outcome": "still_running" (+ "thread_statuses") or
        "recovered" (+ "pr_number", "pr_url").
    """
    ids = get_session_resource_ids(session_id)
    coordinator_id = ids["coordinator_id"]
    environment_id = ids["environment_id"]
    subagent_ids = ids["subagent_ids"]

    threads = get_thread_statuses(session_id)
    statuses = {t["agent_name"]: t["status"] for t in threads}
    busy = {name: s for name, s in statuses.items() if s in ("running", "rescheduling")}
    if busy:
        logger.info(
            "Session %s is not yet fully idle -- %d thread(s) still busy: %s. "
            "Not touching the monorepo or GitHub. Check back later.",
            session_id, len(busy), busy,
        )
        return {"outcome": "still_running", "thread_statuses": statuses}

    logger.info("Session %s: all threads idle (%s). Proceeding with recovery.", session_id, statuses)

    service_root = f"services/{existing_service}" if existing_service else f"services/{request_id}"
    tasks_md = get_file_contents(f"docs/{request_id}/tasks.md", branch="main")

    output_files = list_session_output_files(session_id)
    archive_meta = next((f for f in output_files if f.get("filename") == _ARCHIVE_FILENAME), None)
    if archive_meta is None:
        raise RuntimeError(
            f"Session {session_id} is idle but produced no '{_ARCHIVE_FILENAME}' in "
            f"/mnt/session/outputs/. Files present: {[f.get('filename') for f in output_files]}. "
            "This session genuinely failed -- not recoverable by this tool."
        )
    logger.info("Found archive: %s", archive_meta)
    archive_bytes = download_file_content(archive_meta["id"])
    files_to_commit = _extract_archive_to_file_dict(archive_bytes, expected_prefix=service_root)
    _sanity_check_extracted_files(files_to_commit, service_root, tasks_md)
    logger.info(
        "Archive sanity check passed: %d file(s), %d byte(s) total.",
        len(files_to_commit), sum(len(c) for c in files_to_commit.values()),
    )

    if dry_run:
        print("=" * 20, "Recovery dry run -- would commit", "=" * 20)
        for path in sorted(files_to_commit):
            print(f"  {path} ({len(files_to_commit[path])} chars)")
        return {"outcome": "recovered", "pr_number": None, "pr_url": None}

    # Item #1 Option 1 §2.2 -- unlike the happy path, this function never
    # fetches design.md for any other purpose, so this check gets its own
    # fetch. A failure here must not abort a recovery that's otherwise ready
    # to commit real, already-finished work -- it's caught and turned into
    # its own distinctly-worded flag (see _build_secrets_declaration_flag())
    # rather than either crashing the recovery or being silently treated as
    # "section confirmed missing."
    missing_secrets_declaration = False
    secrets_check_fetch_error: str | None = None
    try:
        design_md_for_secrets_check = get_file_contents(f"docs/{request_id}/design.md", branch="main")
        missing_secrets_declaration = _detect_missing_secrets_declaration(design_md_for_secrets_check)
    except Exception as exc:
        logger.warning(
            "Could not fetch design.md to check for a Required Secrets "
            "declaration (request %s) during recovery: %s -- flagging this "
            "distinctly rather than assuming the section is missing.",
            request_id, exc,
        )
        secrets_check_fetch_error = str(exc)

    pr_result = _commit_and_open_pr(
        request_id, service_root, session_id, issue_number, files_to_commit,
        recovered=True, existing_service=existing_service,
        missing_secrets_declaration=missing_secrets_declaration,
        secrets_check_fetch_error=secrets_check_fetch_error,
    )

    archive_session(coordinator_id, environment_id, session_id, subagent_ids)
    logger.info("Session %s and all associated resources archived.", session_id)

    return {"outcome": "recovered", **pr_result}


_COST_ESTIMATE_MARKER_STAGE = "implementation-estimate"
_COST_ESTIMATE_MARKER_RE = re.compile(
    r"<!-- forge:agent-comment stage=implementation-estimate request_id=(?P<request_id>\S+) "
    r"low=(?P<low>[\d.]+) high=(?P<high>[\d.]+) "
    r"bucket_unit_count=(?P<unit_count>\d+) "
    r"bucket_is_enhancement=(?P<is_enhancement>True|False) -->"
)


def run_cost_estimate(
    issue_number: int,
    request_id: str,
    existing_service: str | None = None,
) -> dict:
    """
    Item #34 §2.2.A: posts a pre-flight cost-estimate comment to the tracking
    issue when design-approved lands, before the real coordinator session is
    created. Never uploads files or creates a Managed Agents session -- only
    reads tasks.md and (for Enhancement) the existing service's file tree,
    the same read-only, side-effect-free operations the real run performs
    before session creation, minus the actual upload_input_file() calls
    (uploading costs nothing but is wasted work if the estimate leads to a
    "no" -- see _count_enhancement_seed_files()).

    Follows the same ADR-0011 comment-then-reraise contract as every other
    agent entry point: on failure, posts a best-effort failure comment before
    re-raising. In particular, a wrong/mistyped existing-service name
    surfaces here too (via _count_enhancement_seed_files()'s Layer 2 backstop)
    rather than silently falling back to Greenfield bucketing (§3).

    Returns the estimate dict from _estimate_implementation_cost() (for
    dry-run/testing convenience) -- the real output that matters is the
    posted comment.
    """
    try:
        tasks_md = get_file_contents(f"docs/{request_id}/tasks.md", branch="main")
        enhancement_seed_file_count = 0
        if existing_service:
            enhancement_seed_file_count = _count_enhancement_seed_files(existing_service)
        estimate = _estimate_implementation_cost(
            tasks_md,
            is_enhancement=bool(existing_service),
            enhancement_seed_file_count=enhancement_seed_file_count,
        )
    except Exception as exc:
        logger.exception(
            "Failed to compute cost estimate for request %s (existing_service=%s)",
            request_id, existing_service,
        )
        failure_body = (
            "⚠️ **FORGE could not compute a pre-flight cost estimate for "
            "Implementation.**\n\n"
            f"Error: `{exc}`\n\n"
            "No cost-estimate comment was posted. This is most likely a wrong/"
            "mistyped 'Existing Service Name' on the intake spreadsheet, or a "
            "problem fetching tasks.md. An Orchestration Manager needs to "
            "investigate before applying `cost-approved`."
        )
        try:
            post_comment(issue_number, failure_body)
        except Exception:
            logger.exception(
                "Also failed to post cost-estimate failure comment to issue #%s", issue_number
            )
        raise

    comment_body = _build_cost_estimate_comment(request_id, estimate)
    post_comment(issue_number, comment_body)
    logger.info(
        "Cost estimate posted for request %s: $%.2f-$%.2f (bucket=%s)",
        request_id, estimate["low"], estimate["high"], estimate["bucket"],
    )
    return estimate


def _fetch_cost_estimate(issue_number: int, request_id: str) -> dict | None:
    """
    Item #34 §2.3: re-fetch-and-parse the hidden marker from the
    cost-estimate comment run_cost_estimate() posted (if any) before the real
    coordinator run, so the post-run comment can show estimate vs. actual.

    This is the first place in the codebase that parses structured key=value
    data out of a forge:agent-comment marker, rather than just checking
    presence or counting occurrences (see _is_agent_comment() in
    requirements_agent.py, qa_agent.py's attempt counter) -- flagged per
    Item #34 spec §4 investigation item #4.

    Returns None if no matching comment is found (e.g. a manual invocation
    that skipped the estimate step, or a request predating this feature) --
    this must never block or fail the real run.
    """
    try:
        comments = get_issue_comments(issue_number)
    except Exception:
        logger.warning(
            "Could not fetch issue comments to look for a prior cost estimate "
            "(issue #%s) -- proceeding without estimate-vs-actual reporting.",
            issue_number, exc_info=True,
        )
        return None

    prefix = (
        f"<!-- forge:agent-comment stage={_COST_ESTIMATE_MARKER_STAGE} "
        f"request_id={request_id} "
    )
    for comment in reversed(comments):  # most recent matching estimate wins
        body = comment.get("body", "")
        if not body.startswith(prefix):
            continue
        match = _COST_ESTIMATE_MARKER_RE.match(body.splitlines()[0])
        if not match:
            logger.warning(
                "Found a cost-estimate comment for request %s but its marker "
                "line didn't match the expected pattern -- skipping. Body "
                "prefix: %r",
                request_id, body.splitlines()[0],
            )
            continue
        return {
            "low": float(match["low"]),
            "high": float(match["high"]),
            "unit_count": int(match["unit_count"]),
            "is_enhancement": match["is_enhancement"] == "True",
        }
    return None


def _extract_actual_cost_usd(final_status: dict) -> float | None:
    """
    Item #34 §2.3: GET /sessions/{id}'s usage.list_cost.amount is in CENTS,
    not dollars (confirmed live, docs/FORGE-pipeline-cost-log.md §3), AND is
    returned as a STRING (e.g. "51"), not a number -- confirmed live during
    this feature's own end-to-end test (TEST-ITEM34-GF, session
    sesn_01L5BAj9c2sD6pnEiV35WuYB): an un-cast `amount / 100` raised
    `TypeError: unsupported operand type(s) for /: 'str' and 'int'` AFTER the
    session had already been archived, silently killing the entire
    commit/PR/comment step with no traceback logged (main()'s outer bare
    `except Exception: sys.exit(1)` swallows it) -- a real, live-caught bug,
    not a hypothetical. Returns None if the session's status dict has no
    usage/list_cost data at all, or if amount is present but not parseable as
    a number -- this must never crash the post-run comment over a missing or
    malformed cost figure.
    """
    usage = final_status.get("usage") or {}
    list_cost = usage.get("list_cost") or {}
    amount = list_cost.get("amount")
    if amount is None:
        return None
    try:
        return float(amount) / 100
    except (TypeError, ValueError):
        logger.warning(
            "usage.list_cost.amount was present but not parseable as a number: %r",
            amount,
        )
        return None


def run_implementation_coordinator(
    issue_number: int,
    request_id: str | None = None,
    dry_run: bool = False,
    existing_service: str | None = None,
) -> dict:
    """
    Core entry point. Returns a summary dict (session_id, files, and pr_number
    on a real run).

    Args:
        existing_service: Item #23 §2.1 -- the "If Enhancement -- Existing
            Service Name" value from the intake spreadsheet, when this is an
            Enhancement request. When set, service_root resolves to the real
            existing services/<existing_service>/ folder (not
            services/<request_id>/) and the sandbox is pre-seeded read-only
            with that service's current files (§2.2). None/empty for a
            Greenfield request -- current behavior, unchanged.
    """
    if not dry_run and not request_id:
        raise ValueError(
            "--request-id is required for a real (non-dry-run) run -- it "
            "determines the services/<request-id> target directory and the "
            "feature/<request-id> branch in the monorepo. Refusing to proceed "
            "without it."
        )
    resolved_request_id = request_id or "unknown"

    resources: list[dict] = []
    if existing_service:
        try:
            service_root, resources = _resolve_enhancement_target(existing_service)
        except Exception as exc:
            # Same ADR-0011 comment-then-raise contract every other agent
            # follows -- this call sits BEFORE the try/except below that
            # covers run_implementation_stage(), so a Layer 2 raise here
            # (existing service not found) needs its own explicit handling
            # or it would propagate to main()'s bare except with no comment
            # ever posted, unlike Ingestion Agent's own Layer 2 backstop.
            logger.exception(
                "Failed to resolve Enhancement target for request %s "
                "(existing_service=%s)",
                resolved_request_id, existing_service,
            )
            if not dry_run:
                failure_body = (
                    "⚠️ **FORGE Implementation Coordinator failed to resolve the "
                    "Enhancement target.**\n\n"
                    f"Error: `{exc}`\n\n"
                    "No Managed Agents session was created -- nothing to recover or "
                    "clean up. This is most likely a wrong/mistyped 'Existing Service "
                    "Name' on the intake spreadsheet. An Orchestration Manager needs "
                    "to investigate before re-applying `design-approved`."
                )
                try:
                    post_comment(issue_number, failure_body)
                except Exception:
                    logger.exception(
                        "Also failed to post failure comment to issue #%s", issue_number
                    )
            raise
    else:
        service_root = f"services/{resolved_request_id}"

    design_md = get_file_contents(f"docs/{resolved_request_id}/design.md", branch="main")
    openapi_yaml_text = get_file_contents(f"docs/{resolved_request_id}/openapi.yaml", branch="main")
    tasks_md = get_file_contents(f"docs/{resolved_request_id}/tasks.md", branch="main")

    initial_message = _build_initial_message(
        design_md, openapi_yaml_text, tasks_md, service_root, existing_service=existing_service
    )
    subagent_configs = [
        backend_agent.get_config(service_root),
        frontend_agent.get_config(service_root),
        test_writer_agent.get_config(service_root),
    ]

    session_id: str | None = None
    files_to_commit: dict[str, str] = {}
    try:
        result = run_implementation_stage(
            coordinator_system_prompt=_COORDINATOR_SYSTEM_PROMPT,
            subagent_configs=subagent_configs,
            initial_message=initial_message,
            expected_output_filename=_ARCHIVE_FILENAME,
            resources=resources,
        )
        session_id = result["session_id"]

        # run_implementation_stage() already guarantees (via
        # expected_output_filename) that this file exists and the session was
        # NOT archived otherwise -- see Item #6 Bug 6b. output_files is reused
        # from its return value rather than re-fetched here.
        archive_meta = next(
            f for f in result["output_files"] if f.get("filename") == _ARCHIVE_FILENAME
        )
        archive_bytes = download_file_content(archive_meta["id"])
        files_to_commit = _extract_archive_to_file_dict(archive_bytes, expected_prefix=service_root)
        _sanity_check_extracted_files(files_to_commit, service_root, tasks_md)

    except SessionStillRunningError as exc:
        # NOT a failure -- the coordinator's own turn ended, but real completion
        # (every subagent thread idle) hasn't happened within the wait ceiling.
        # Real Stage 3 runs have taken 37-55 minutes (docs/FORGE-pipeline-cost-log.md);
        # this is expected to fire occasionally on a slow-but-healthy run, not just
        # a stuck one. The session was left alive by wait_for_all_threads_idle() --
        # do not archive it here, do not treat this as requiring investigation.
        logger.warning(
            "Implementation Coordinator session %s for request %s is still "
            "running past the completion-wait ceiling -- not a failure, "
            "leaving the session alive. Thread statuses: %s",
            exc.session_id, resolved_request_id, exc.thread_statuses,
        )
        if not dry_run:
            still_running_body = (
                "⏳ **FORGE Implementation Coordinator is still running.** This is "
                "expected for a real two-service build — recent runs have taken "
                "37-55 minutes — and is **not a failure**.\n\n"
                f"Managed Agents session: `{exc.session_id}` -- see the Claude "
                f"Console ({_CONSOLE_SESSION_URL_PREFIX}{exc.session_id}) for the "
                "live per-subagent trace.\n\n"
                f"Current per-thread status: `{exc.thread_statuses}`\n\n"
                "No action is needed yet. The session was left alive (not "
                "archived) — check back shortly. If it's still running well "
                "past an hour, an Orchestration Manager should use the "
                "recovery tool against this session ID rather than re-applying "
                "`design-approved` (which would create a duplicate, "
                "separately-billed session on top of this one)."
            )
            try:
                post_comment(issue_number, still_running_body)
            except Exception:
                logger.exception(
                    "Also failed to post 'still running' comment to issue #%s", issue_number
                )
        raise

    except Exception as exc:
        logger.exception(
            "Implementation Coordinator failed for request %s (session: %s)",
            resolved_request_id, session_id,
        )
        if not dry_run:
            session_note = (
                f"Managed Agents session: `{session_id}` -- see the Claude Console "
                f"({_CONSOLE_SESSION_URL_PREFIX}{session_id}) for the full "
                "per-subagent trace.\n\n"
                if session_id else
                "The session may not have been created -- check the GitHub Actions "
                "log for `managed_agents_session_start`.\n\n"
            )
            failure_body = (
                "⚠️ **FORGE Implementation Coordinator failed to produce an "
                "implementation.**\n\n"
                f"Error: `{exc}`\n\n"
                f"{session_note}"
                "An Orchestration Manager needs to investigate before this request "
                "can proceed. Do not merge any partial PR from this run."
            )
            try:
                post_comment(issue_number, failure_body)
            except Exception:
                logger.exception("Also failed to post failure comment to issue #%s", issue_number)
        raise

    if dry_run:
        print("=" * 20, "Session summary", "=" * 20)
        print(f"session_id: {session_id}")
        print(f"Console: {_CONSOLE_SESSION_URL_PREFIX}{session_id}")
        print(f"Files that would be committed to {service_root}:")
        for path in sorted(files_to_commit):
            print(f"  {path} ({len(files_to_commit[path])} chars)")
        logger.info(
            "Dry run complete for request %s -- nothing committed, nothing posted.",
            resolved_request_id,
        )
        return {"session_id": session_id, "files": list(files_to_commit)}

    # Item #1 Option 1 §2.2 -- design_md was already fetched (uncaught) above,
    # before this function's try/except even begins, so by construction its
    # fetch has already succeeded by this point; no secrets_check_fetch_error
    # case applies on this path (see recover_implementation_session() for the
    # one path where the fetch is new and can fail independently).
    missing_secrets_declaration = _detect_missing_secrets_declaration(design_md)

    # Item #34 §2.3 -- best-effort only: neither call must ever block a real,
    # already-successful implementation from being committed and PR'd. A
    # missing/unparseable estimate comment or a session usage object with no
    # cost figure both just mean the "estimate vs. actual" section is omitted
    # (see _commit_and_open_pr()'s cost_estimate/actual_cost_usd handling).
    cost_estimate = _fetch_cost_estimate(issue_number, resolved_request_id)
    actual_cost_usd = _extract_actual_cost_usd(result["final_status"])

    pr_result = _commit_and_open_pr(
        resolved_request_id, service_root, session_id, issue_number, files_to_commit,
        existing_service=existing_service,
        missing_secrets_declaration=missing_secrets_declaration,
        cost_estimate=cost_estimate,
        actual_cost_usd=actual_cost_usd,
    )
    return {"session_id": session_id, "pr_number": pr_result["pr_number"], "files": list(files_to_commit)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE Implementation Coordinator")
    parser.add_argument("--issue-number", required=True, type=int, help="FORGE tracking issue number in forge-template")
    parser.add_argument("--request-id", default=None, help="FORGE request ID (required for a real run)")
    parser.add_argument("--dry-run", action="store_true", help="Run the real session but skip committing/posting")
    parser.add_argument(
        "--existing-service",
        default=None,
        help=(
            "Item #23: the 'If Enhancement -- Existing Service Name' value from "
            "the intake spreadsheet. When set, service_root resolves to the real "
            "existing services/<existing-service>/ folder and the sandbox is "
            "pre-seeded read-only with that service's current files. Omit for a "
            "Greenfield request (current behavior, unchanged). With "
            "--recover-session, pass the SAME value the original session was "
            "started with, if any."
        ),
    )
    parser.add_argument(
        "--recover-session",
        default=None,
        metavar="SESSION_ID",
        help=(
            "Recover an existing session left alive by a SessionStillRunningError "
            "(or a killed local process) instead of starting a new coordinator run. "
            "Requires --request-id. Never re-invokes the coordinator."
        ),
    )
    parser.add_argument(
        "--estimate-only",
        action="store_true",
        help=(
            "Item #34: post a pre-flight cost estimate comment to the tracking "
            "issue and exit -- does not create a Managed Agents session, upload "
            "any files, commit, or open a PR. Requires --request-id."
        ),
    )
    args = parser.parse_args()

    if args.estimate_only:
        if not args.request_id:
            parser.error("--request-id is required with --estimate-only")
        try:
            run_cost_estimate(
                issue_number=args.issue_number,
                request_id=args.request_id,
                existing_service=args.existing_service,
            )
        except Exception:
            logger.exception("Cost estimate failed for request %s", args.request_id)
            sys.exit(1)
        return

    if args.recover_session:
        if not args.request_id:
            parser.error("--request-id is required with --recover-session")
        try:
            result = recover_implementation_session(
                session_id=args.recover_session,
                issue_number=args.issue_number,
                request_id=args.request_id,
                dry_run=args.dry_run,
                existing_service=args.existing_service,
            )
        except Exception:
            logger.exception("Recovery failed for session %s", args.recover_session)
            sys.exit(1)
        print(f"Recovery outcome: {result['outcome']}")
        if result["outcome"] == "still_running":
            sys.exit(0)  # a successful check reporting "not ready yet" is not a failure
        return

    try:
        run_implementation_coordinator(
            issue_number=args.issue_number,
            request_id=args.request_id,
            dry_run=args.dry_run,
            existing_service=args.existing_service,
        )
    except SessionStillRunningError:
        # Distinguishable from a real failure (sys.exit(1) below) -- exit code
        # 75 is an arbitrary but documented convention (nothing in POSIX/GitHub
        # Actions assigns it a reserved meaning) so anything grepping Actions
        # job exit codes can tell "still working, check back" apart from
        # "genuinely failed". The tracking-issue comment posted above is the
        # real human-facing signal; this exit code is for tooling.
        sys.exit(75)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
