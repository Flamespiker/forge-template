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
import sys
import tarfile

from core.agents.subagents import (
    EXISTING_SERVICE_MOUNT_DIR,
    SHARED_DOCS_DIR,
    backend_agent,
    frontend_agent,
    test_writer_agent,
)
from core.agents.utils.existing_service_files import select_existing_service_files
from core.agents.utils.github_helper import (
    get_file_contents,
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


def _resolve_enhancement_target(existing_service: str) -> tuple[str, list[dict]]:
    """
    Item #23 (§2.1/§2.2): resolves the real service_root for an Enhancement
    request and builds the session `resources[]` list that seeds the existing
    service's files read-only at EXISTING_SERVICE_MOUNT_DIR.

    Reuses the Layer 2 "strict rejection over silent auto-remap" precedent
    from Ingestion Agent / Open Item #8: an empty tree under
    services/<existing_service>/ is a real, human-actionable mismatch (a
    wrong/mistyped "Existing Service Name" on the intake spreadsheet), not a
    benign no-op -- raises rather than silently falling back to the request
    ID. The caller's existing ADR-0011 try/except wraps this call and posts a
    failure comment before re-raising -- the same generic contract every
    other agent follows, so no separate mismatch-specific comment (unlike
    Ingestion Agent's own dedicated one) is needed here.

    Returns:
        Tuple of (service_root, resources) -- service_root is the real
        existing services/<existing_service> path (no trailing slash, same
        shape as the Greenfield f"services/{request_id}"); resources is the
        session resources[] list ready to pass to run_implementation_stage().
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


def _commit_and_open_pr(
    request_id: str,
    service_root: str,
    session_id: str,
    issue_number: int,
    files_to_commit: dict[str, str],
    recovered: bool = False,
    existing_service: str | None = None,
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

    pr_result = _commit_and_open_pr(
        request_id, service_root, session_id, issue_number, files_to_commit,
        recovered=True, existing_service=existing_service,
    )

    archive_session(coordinator_id, environment_id, session_id, subagent_ids)
    logger.info("Session %s and all associated resources archived.", session_id)

    return {"outcome": "recovered", **pr_result}


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

    pr_result = _commit_and_open_pr(
        resolved_request_id, service_root, session_id, issue_number, files_to_commit,
        existing_service=existing_service,
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
    args = parser.parse_args()

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
