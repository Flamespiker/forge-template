"""
FORGE Codebase Ingestion Agent — Stage 0a (Codebase Ingestion).

Only ever invoked for Enhancement-flagged requests, never Greenfield (Document 07:
Stage 0a's trigger is Locked to the Enhancement case). Walks the existing service's
folder in the target monorepo (forge-demo-apps) and produces:
  - existing-architecture-summary.md — tech stack, folder/module structure, data
    model, API surface, testing conventions actually observed in the existing code,
    plus an explicit "what this summary could NOT determine" section.

Committed to docs/<request-id>/existing-architecture-summary.md on the dedicated
`pipeline-state` branch — same rationale as requirements.md/ado-work-items.json
(Phase 4 step 4.8 retrofit: `main` requires a PR review for every push, and this
content was never meant to go through one). See
docs/FORGE-Phase7-Ingestion-Agent-Spec.md §2 Fork B.

Despite the "0a before 0b" naming, this agent runs AFTER the intake spreadsheet has
been parsed once (Stage 0b/Intake Agent's job) — the Enhancement flag and existing
service name only become known at that point. In practice it's wired as a
conditional step inside 00-intake.yml itself, running in parallel with the BA's
clarification round rather than as a separate sequential stage. See
docs/FORGE-Phase7-Ingestion-Agent-Spec.md §2 Fork A. This stage is NOT human-gated
(Document 01 §3.0a) — there is nothing for a human to approve, so this agent posts
no "ready for review" comment on success. It DOES post a comment on failure (per
ADR-0011) and on the Layer 2 existing-service mismatch case below.

IMPORTANT — any comment this agent ever posts must carry the standard
`<!-- forge:agent-comment stage=ingestion request_id=... -->` marker. Requirements
Agent's clarification-answer parsing (_is_agent_comment() in requirements_agent.py)
treats every UNMARKED comment on the tracking issue as a BA answer — an unmarked
comment from this agent would silently corrupt that parsing.

Usage:
    python -m core.agents.ingestion_agent --request-id REQ-2026-03 --existing-service REQ-2026-03 --issue-number 42
    python -m core.agents.ingestion_agent --existing-service REQ-2026-03 --dry-run

CLI arguments:
    --existing-service  The "If Enhancement — Existing Service Name" value from the
                         intake spreadsheet — must match a real services/<name>/
                         folder in the monorepo exactly (required).
    --request-id        FORGE request ID. Required for a real run (used for the
                         monorepo file path docs/<request-id>/); optional for
                         --dry-run.
    --issue-number       FORGE tracking issue number in forge-template, used only
                         to post a failure/mismatch comment if something goes
                         wrong (this agent never reads issue comments — Ingestion
                         doesn't depend on the BA's clarification answers at all).
                         Required for a real run; optional for --dry-run.
    --dry-run            Walk the tree and call Claude, but print
                         existing-architecture-summary.md to stdout instead of
                         committing to the monorepo or posting to GitHub. The
                         Layer 2 mismatch comment (below) is also just printed,
                         never posted, under --dry-run — same contract as every
                         other agent's dry-run mode.

Layer 2 backstop (existing-service mismatch) — per
docs/FORGE-Phase7-Ingestion-Agent-Spec.md §3.3: if get_repo_tree() finds zero blobs
under services/<existing_service>/, this is treated as a real, human-actionable
problem (a wrong/mistyped service name on an Enhancement-flagged request), not a
benign no-op. It does NOT silently fall back to guessing request_id or any other
value — same "strict rejection over silent auto-remap" philosophy already used by
implementation_coordinator.py's .github/ path-segment guard (Open Item #8). This
agent logs a warning, posts a best-effort comment naming the mismatch, and raises
EnhancementServiceNotFoundError — a real (non-zero-exit) failure, not a quiet skip,
distinct from 00-intake.yml's own clean Greenfield no-op.

Per ADR-0011 / Document 6: the invoke_agent() call is wrapped in try/except at the
call site. On failure (or malformed/truncated JSON from the model), a failure
comment is posted to the tracking issue (best-effort, real run only) before the
exception is re-raised.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from core.agents.utils.claude_agent_wrapper import invoke_agent
from core.agents.utils.github_helper import get_file_contents, get_repo_tree, post_comment, commit_files

logger = logging.getLogger(__name__)

_STAGE_NAME = "ingestion"
_MAX_TOKENS = 12000

# Directory segments that are pure build/dependency noise if they ever appear
# under a services/<existing-service>/ prefix (normally gitignored and never
# committed at all, but excluded defensively rather than assumed absent).
_NOISE_DIR_SEGMENTS = {"node_modules", "bin", "obj", ".next", "dist", "coverage", ".git"}

# Exact filenames that are low-signal/high-size and never worth reading in full.
# tsconfig.tsbuildinfo confirmed live (2026-08-26) against services/REQ-2026-03/
# frontend/ — a 100KB+ incremental-build cache file not in the spec's original
# guessed list; added after seeing the real tree, per the spec's own instruction
# to extend this list from live data rather than guess a complete list upfront.
_NOISE_FILENAMES = {"package-lock.json", "yarn.lock", "tsconfig.tsbuildinfo"}
_NOISE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".ico", ".svg", ".woff", ".woff2"}

# Manifest/config files — always fetched in full regardless of the content
# budget below, since they're cheap and high-signal (tech stack, dependencies,
# API contract already committed, entry points).
_MANIFEST_EXACT_BASENAMES = {
    "package.json", "tsconfig.json", "openapi.yaml", "Program.cs", "Startup.cs",
}

# Approximate character budget for full-content source files beyond the
# manifests above (byte size used as a proxy for character count — source code
# is overwhelmingly ASCII, so this is a close enough approximation). Per spec
# §3.2: "start around 60k characters... adjust after a live test shows real
# sizes."
_CONTENT_BUDGET_CHARS = 60_000

_SYSTEM_PROMPT = """You are the FORGE Codebase Ingestion Agent for Legal Aid \
Alberta's software delivery pipeline.

You will be given: (1) the full list of file paths found under an existing \
service's folder in the monorepo (so you can see the whole folder/module shape \
even for files you don't get full content for), and (2) the full contents of a \
subset of those files — always including manifest/config files (csproj, \
package.json, tsconfig.json, openapi.yaml, entry points, appsettings), plus as \
many of the largest remaining source files as fit in the budget.

Your job is to produce a single existing-architecture-summary.md document (as \
Markdown text) that a Requirements Agent and a Design Agent will read before \
drafting a new enhancement to this existing service. Cover, at minimum:

- Actual tech stack observed (frameworks, languages, major libraries) — call out \
explicitly anywhere this appears to differ from what a greenfield FORGE app would \
default to, since that's exactly the kind of thing Requirements/Design need to \
know before assuming a greenfield-style default.
- Folder/module structure and naming conventions actually in use.
- Existing data model / schema, as far as it's inferable from the files you were \
given (entities, migrations, DTOs).
- Existing API surface (endpoints, contracts) for a backend service; existing \
page/route structure for a frontend.
- Testing conventions observed (frameworks, file naming, coverage patterns).
- A final "What this summary could NOT determine" section — name anything you \
couldn't confidently infer from the files you were given as an explicit gap, so \
the Requirements Agent's clarifying-question round can potentially pick it up. Do \
not silently omit a gap, and do not guess or invent detail you don't have grounds \
for.

Ground every claim in the files you were actually given — the full path list shows \
you the folder shape, but only cite specifics (endpoint names, entity fields, etc.) \
from files whose content you actually received. Never hallucinate an endpoint, \
field, or convention that isn't visible in what you were given.

Output format — this is strict:
Respond with ONLY a single JSON object, no markdown code fences, no prose before or \
after it. It must have exactly this shape:

{
  "summary_markdown": "<string - the full contents of existing-architecture-summary.md>"
}"""


class EnhancementServiceNotFoundError(RuntimeError):
    """
    Raised when --existing-service doesn't resolve to any real
    services/<existing_service>/ folder in the target monorepo (get_repo_tree()
    returned zero blobs). A real, human-actionable problem — never silently
    papered over by falling back to request_id or any other guessed value.
    """


def _filter_noise(blobs: list[dict]) -> list[dict]:
    filtered = []
    for blob in blobs:
        path = blob["path"]
        segments = path.split("/")
        if any(seg in _NOISE_DIR_SEGMENTS for seg in segments):
            continue
        basename = segments[-1]
        if basename in _NOISE_FILENAMES:
            continue
        if any(basename.endswith(ext) for ext in _NOISE_EXTENSIONS):
            continue
        filtered.append(blob)
    return filtered


def _is_manifest(path: str) -> bool:
    basename = path.rsplit("/", 1)[-1]
    if path.endswith(".csproj"):
        return True
    if basename in _MANIFEST_EXACT_BASENAMES:
        return True
    if basename.startswith("appsettings") and basename.endswith(".json"):
        return True
    return False


def _select_content_files(filtered_blobs: list[dict]) -> list[dict]:
    """
    Two-pass budget: always include every manifest/config file, then fill the
    remaining character budget with the largest non-manifest source files
    (descending size) until the budget is spent.
    """
    manifests = [b for b in filtered_blobs if _is_manifest(b["path"])]
    others = sorted(
        (b for b in filtered_blobs if not _is_manifest(b["path"])),
        key=lambda b: b["size"],
        reverse=True,
    )

    selected = list(manifests)
    used_chars = sum(b["size"] for b in manifests)
    for blob in others:
        if used_chars >= _CONTENT_BUDGET_CHARS:
            break
        selected.append(blob)
        used_chars += blob["size"]
    return selected


def _build_user_prompt(existing_service: str, all_paths: list[str], content_files: dict[str, str]) -> str:
    path_list_text = "\n".join(f"- {p}" for p in all_paths) or "_(no files found)_"
    content_sections = []
    for path, content in content_files.items():
        content_sections.append(f"### `{path}`\n\n```\n{content}\n```\n")
    content_text = "\n".join(content_sections) or "_(no file contents fetched)_"
    return (
        f"## Existing service: `services/{existing_service}/`\n\n"
        f"## Full file list ({len(all_paths)} files, after noise filtering)\n\n"
        f"{path_list_text}\n\n"
        f"## File contents ({len(content_files)} of {len(all_paths)} files)\n\n"
        f"{content_text}\n"
        "---\n"
        "Produce your JSON response now."
    )


def _parse_model_json(output_text: str) -> dict:
    text = output_text.strip()
    if text.startswith("```"):
        # Defensive: strip a wrapping ```json ... ``` fence if the model added one
        # despite instructions not to.
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def run_ingestion_agent(
    existing_service: str,
    request_id: str | None = None,
    issue_number: int | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Core entry point. Returns the parsed model output dict
    ({"summary_markdown": ...}).
    """
    if not dry_run and not request_id:
        raise ValueError(
            "--request-id is required for a real (non-dry-run) run — it determines "
            "the docs/<request-id>/ path in the monorepo. Refusing to proceed without it."
        )
    if not dry_run and not issue_number:
        raise ValueError(
            "--issue-number is required for a real (non-dry-run) run — needed to "
            "post a failure/mismatch comment to the tracking issue if something "
            "goes wrong. Refusing to proceed without it."
        )
    resolved_request_id = request_id or "unknown"

    service_prefix = f"services/{existing_service}/"
    blobs = get_repo_tree(service_prefix)

    if not blobs:
        # Layer 2 backstop (spec §3.3) — a real, human-actionable mismatch, not
        # a benign no-op. Never silently fall back to guessing request_id or
        # any other value.
        warning = (
            f"No files found under `{service_prefix}` in the target monorepo — "
            f"the 'If Enhancement — Existing Service Name' value ('{existing_service}') "
            "does not match any real services/ folder."
        )
        logger.warning(warning)
        mismatch_body = (
            f"<!-- forge:agent-comment stage=ingestion request_id={resolved_request_id} -->\n"
            "## ⚠️ FORGE Codebase Ingestion Agent — existing service not found\n\n"
            f"{warning}\n\n"
            "This is an Enhancement-flagged request, so Codebase Ingestion tried to read "
            "the existing service's code before Requirements/Design run. An Orchestration "
            "Manager needs to confirm the real folder name under `services/` in "
            "`forge-demo-apps` and correct the intake spreadsheet's 'Existing Service Name' "
            "field before this can proceed. Requirements/Design will still run without this "
            "summary, but without any existing-codebase grounding."
        )
        if dry_run:
            print("=" * 20, "would-be mismatch comment (NOT posted -- dry-run)", "=" * 20)
            print(mismatch_body)
        else:
            try:
                post_comment(issue_number, mismatch_body)
            except Exception:
                logger.exception("Also failed to post mismatch comment to issue #%s", issue_number)
        raise EnhancementServiceNotFoundError(warning)

    filtered_blobs = _filter_noise(blobs)
    content_blobs = _select_content_files(filtered_blobs)
    content_files = {
        blob["path"]: get_file_contents(blob["path"], branch="main") for blob in content_blobs
    }
    all_paths = [blob["path"] for blob in filtered_blobs]
    user_prompt = _build_user_prompt(existing_service, all_paths, content_files)

    try:
        result = invoke_agent(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=_MAX_TOKENS,
            stage_name=_STAGE_NAME,
            request_id=resolved_request_id,
        )
        if result.stop_reason == "max_tokens":
            raise ValueError(
                f"Model response was truncated at max_tokens={_MAX_TOKENS} — "
                "increase _MAX_TOKENS in ingestion_agent.py and retry."
            )
        parsed_output = _parse_model_json(result.output_text)
        summary_md = parsed_output["summary_markdown"]
    except Exception as exc:
        logger.exception("Ingestion Agent failed for request %s", resolved_request_id)
        if not dry_run:
            failure_body = (
                f"<!-- forge:agent-comment stage=ingestion request_id={resolved_request_id} -->\n"
                "⚠️ **FORGE Codebase Ingestion Agent failed to produce a summary.**\n\n"
                f"Error: `{exc}`\n\n"
                "Requirements/Design will still run without this summary (best-effort "
                "graceful absence), but without any existing-codebase grounding. An "
                "Orchestration Manager should investigate."
            )
            try:
                post_comment(issue_number, failure_body)
            except Exception:
                logger.exception("Also failed to post failure comment to issue #%s", issue_number)
        raise

    if dry_run:
        print("=" * 20, "existing-architecture-summary.md", "=" * 20)
        print(summary_md)
        logger.info(
            "Dry run complete for request %s — nothing committed, nothing posted.",
            resolved_request_id,
        )
        return parsed_output

    commit_files(
        branch_name="pipeline-state",
        files={f"docs/{resolved_request_id}/existing-architecture-summary.md": summary_md},
        commit_message=f"FORGE Ingestion Agent: existing-architecture summary for {resolved_request_id}",
    )
    logger.info(
        "Ingestion Agent complete for request %s — existing-architecture-summary.md committed "
        "to pipeline-state. Not human-gated -- no comment posted on success.",
        resolved_request_id,
    )
    return parsed_output


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE Codebase Ingestion Agent")
    parser.add_argument("--existing-service", required=True, help="Existing services/<name>/ folder in the monorepo")
    parser.add_argument("--request-id", default=None, help="FORGE request ID (required for a real run)")
    parser.add_argument("--issue-number", default=None, type=int, help="FORGE tracking issue number in forge-template (required for a real run)")
    parser.add_argument("--dry-run", action="store_true", help="Print output instead of committing/posting")
    args = parser.parse_args()

    try:
        run_ingestion_agent(
            existing_service=args.existing_service,
            request_id=args.request_id,
            issue_number=args.issue_number,
            dry_run=args.dry_run,
        )
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
