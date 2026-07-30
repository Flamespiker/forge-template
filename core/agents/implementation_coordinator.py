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

from core.agents.subagents import backend_agent, frontend_agent, test_writer_agent
from core.agents.utils.github_helper import (
    get_file_contents,
    post_comment,
    create_branch,
    commit_files,
    open_pr,
)
from core.agents.utils.managed_agents_wrapper import (
    run_implementation_stage,
    list_session_output_files,
    download_file_content,
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
1. Delegate the Backend, Frontend, and Test Writer sections of tasks.md to the \
matching subagent. Let Backend and Frontend work in parallel; Test Writer should \
start once there's real code for it to test against.
2. Check in on all three as they work. When a subagent reports its portion done, \
verify it actually did what tasks.md asked -- spot-check the files it wrote.
3. Perform integration checking yourself: confirm the frontend's API calls actually \
match the endpoints Backend implemented and the contract in openapi.yaml; resolve \
any mismatch by asking the relevant subagent to fix it, or fixing it directly if \
it's a small inconsistency (e.g. a route casing or field-name mismatch).
4. Once all three are done and consistent, package the ENTIRE target directory \
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
5. Confirm the archive was created successfully (nonzero size, contents look \
right) before ending your turn. State "IMPLEMENTATION COMPLETE" once you've \
verified this.

Do not invent requirements not present in tasks.md/design.md. If something is \
ambiguous, make a reasonable, clearly-stated assumption rather than blocking -- a \
human reviews the resulting PR regardless."""


def _build_initial_message(
    design_md: str, openapi_yaml_text: str, tasks_md: str, service_root: str
) -> str:
    return (
        f"Your target directory for this request is: {service_root}\n\n"
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


def run_implementation_coordinator(
    issue_number: int,
    request_id: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Core entry point. Returns a summary dict (session_id, files, and pr_number
    on a real run).
    """
    if not dry_run and not request_id:
        raise ValueError(
            "--request-id is required for a real (non-dry-run) run -- it "
            "determines the services/<request-id> target directory and the "
            "feature/<request-id> branch in the monorepo. Refusing to proceed "
            "without it."
        )
    resolved_request_id = request_id or "unknown"
    service_root = f"services/{resolved_request_id}"

    design_md = get_file_contents(f"docs/{resolved_request_id}/design.md", branch="main")
    openapi_yaml_text = get_file_contents(f"docs/{resolved_request_id}/openapi.yaml", branch="main")
    tasks_md = get_file_contents(f"docs/{resolved_request_id}/tasks.md", branch="main")

    initial_message = _build_initial_message(design_md, openapi_yaml_text, tasks_md, service_root)
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
        )
        session_id = result["session_id"]

        output_files = list_session_output_files(session_id)
        archive_meta = next(
            (f for f in output_files if f.get("filename") == _ARCHIVE_FILENAME), None
        )
        if archive_meta is None:
            raise RuntimeError(
                f"Coordinator session {session_id} completed but did not produce "
                f"'{_ARCHIVE_FILENAME}' in /mnt/session/outputs/. Files present: "
                f"{[f.get('filename') for f in output_files]}"
            )
        archive_bytes = download_file_content(archive_meta["id"])
        files_to_commit = _extract_archive_to_file_dict(archive_bytes, expected_prefix=service_root)

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

    branch_name = f"feature/{resolved_request_id}"
    create_branch(branch_name, from_branch="main")
    commit_files(
        branch_name=branch_name,
        files=files_to_commit,
        commit_message=f"FORGE Implementation Coordinator: implement {resolved_request_id}",
    )

    owner = os.environ.get("FORGE_GITHUB_OWNER", "")
    source_repo = os.environ.get("FORGE_SOURCE_REPO", "forge-template")
    tracking_issue_ref = f"{owner}/{source_repo}#{issue_number}" if owner else f"#{issue_number}"

    pr = open_pr(
        title=f"FORGE Implementation: {resolved_request_id}",
        body=(
            f"Implementation for {resolved_request_id} ({service_root}), generated "
            "by the FORGE Implementation Coordinator (Backend + Frontend + Test "
            "Writer subagents via Anthropic Managed Agents -- ADR-0010).\n\n"
            f"Related FORGE tracking issue: {tracking_issue_ref}\n\n"
            f"Managed Agents session: `{session_id}` -- per-subagent audit trail in "
            f"the Claude Console: {_CONSOLE_SESSION_URL_PREFIX}{session_id}\n\n"
            "Merge to approve (Document 6 Gate 3)."
        ),
        head_branch=branch_name,
        base_branch="main",
        draft=True,
    )

    comment_body = (
        f"<!-- forge:agent-comment stage=implementation request_id={resolved_request_id} -->\n"
        "## 🛠️ FORGE Implementation — Draft Ready for Review\n\n"
        f"The Implementation Coordinator ran Backend, Frontend, and Test Writer as "
        f"subagents (Managed Agents session `{session_id}`), committed the result "
        f"to `{service_root}/` on branch `{branch_name}`, and opened a draft PR: "
        f"{pr['html_url']}\n\n"
        f"Per-subagent audit trail: {_CONSOLE_SESSION_URL_PREFIX}{session_id}\n\n"
        "---\n"
        "QA and Security are already running in parallel -- both trigger "
        "automatically now that this PR is open, and will post their own results "
        "directly on it. Review the diff; mark it ready for review and merge when "
        "you're satisfied and QA/Security are clear."
    )
    post_comment(issue_number, comment_body)
    logger.info(
        "Implementation Coordinator complete for request %s -- PR #%s opened, "
        "summary posted to issue #%s.",
        resolved_request_id, pr["number"], issue_number,
    )
    return {"session_id": session_id, "pr_number": pr["number"], "files": list(files_to_commit)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE Implementation Coordinator")
    parser.add_argument("--issue-number", required=True, type=int, help="FORGE tracking issue number in forge-template")
    parser.add_argument("--request-id", default=None, help="FORGE request ID (required for a real run)")
    parser.add_argument("--dry-run", action="store_true", help="Run the real session but skip committing/posting")
    args = parser.parse_args()

    try:
        run_implementation_coordinator(
            issue_number=args.issue_number,
            request_id=args.request_id,
            dry_run=args.dry_run,
        )
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
