"""
FORGE Requirements Agent — Stage 1 (Requirements).

Reads the BA's completed intake spreadsheet plus their clarification answers from
the tracking issue thread, and produces:
  - requirements.md — a structured, traceable requirements document
  - a draft ADO work-item payload (Epic -> Features -> User Stories)

Both are committed directly to the monorepo (docs/<request-id>/) on the dedicated
`pipeline-state` branch (Phase 4 step 4.8 retrofit — this used to be `main`, moved off
it once branch protection on forge-demo-apps required a PR review for every push to
`main` and no bypass was available; see CLAUDE.md's "Phase 4 — Pipeline Wiring"
section). This stage has no PR of its own either way (see Document 6 Gate 1: approval
happens via the `requirements-approved` label on the tracking issue, reading these
files as posted in the summary comment below, not via a git diff on `main`). A
human-readable summary of the draft ADO hierarchy is posted as a comment on the
tracking issue for review. ADO work items are NOT created here — only after a human
applies `requirements-approved` (Phase 4 wiring, not this script).

Usage:
    python -m core.agents.requirements_agent --spreadsheet path/to/file.xlsx --issue-number 42 --request-id REQ-2026-01
    python -m core.agents.requirements_agent --spreadsheet path/to/file.xlsx --issue-number 42 --request-id REQ-2026-01 --dry-run

CLI arguments:
    --spreadsheet   Path to the completed Intake Template .xlsx file (required)
    --issue-number  FORGE tracking issue number in forge-template, used to read the
                     BA's clarification answers and (unless --dry-run) post the
                     draft summary comment (required)
    --request-id    FORGE request ID. Required for a real run (used in the monorepo
                     file path docs/<request-id>/); optional for --dry-run.
    --dry-run       Parse the spreadsheet, fetch issue comments, and call Claude, but
                     print requirements.md and the ADO payload to stdout instead of
                     committing to the monorepo or posting to GitHub.

Per ADR-0011 / Document 6: the invoke_agent() call is wrapped in try/except at the
call site. On failure (or malformed/truncated JSON from the model), a failure
comment is posted to the tracking issue (best-effort, real run only) before the
exception is re-raised.

Enhancement requests (Phase 7 step 7.1): if the spreadsheet's Request Type is
Enhancement, this agent also attempts to fetch existing-architecture-summary.md
(committed by the Codebase Ingestion Agent, Stage 0a, to the same pipeline-state
branch) and folds it into the prompt. A 404 (Ingestion hasn't finished yet, or
failed) is tolerated -- logged as a warning, proceeds without it -- since a missing
summary shouldn't hard-block Requirements from drafting off the spreadsheet +
clarification answers alone, same as every request took before Stage 0a existed.
Any OTHER fetch error (not a 404) is treated as a real failure, same as any other
exception here -- it propagates into the existing try/except below and produces
the standard failure comment, rather than being silently swallowed.

Pipeline Depth (Item #43): this is the earliest point with a durable, downstream-
readable location (pipeline-state), so this agent also normalizes the intake
spreadsheet's Pipeline Depth field (_normalize_pipeline_depth()) and writes it to
docs/<request-id>/pipeline-config.json alongside requirements.md/ado-work-items.json.
Every later stage's guard clause reads this file (via get_file_contents()) to decide
whether it's still within the configured depth before invoking its real agent.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

import requests

from core.agents.utils import file_io
from core.agents.utils.claude_agent_wrapper import invoke_agent
from core.agents.utils.github_helper import get_file_contents, get_issue_comments, post_comment, commit_files

logger = logging.getLogger(__name__)

_STAGE_NAME = "requirements"
_MAX_TOKENS = 8000
_AGENT_COMMENT_PREFIX = "<!-- forge:agent-comment"

_SYSTEM_PROMPT = """You are the FORGE Requirements Agent for Legal Aid Alberta's \
software delivery pipeline.

You will be given: (1) a Business Analyst's completed intake spreadsheet (Overview \
section and Requirements rows), and (2) the BA's answers to a prior round of \
clarifying questions from the Intake Agent, taken verbatim from the GitHub issue \
thread.

Your job is to produce two things, combining the spreadsheet with the clarification \
answers so the final output reflects the fuller picture, not just the original \
spreadsheet in isolation:

1. A complete, traceable requirements.md document (as Markdown text).
2. A draft Azure DevOps work-item hierarchy: one Epic, containing one or more \
Features, each containing one or more User Stories.

Rules for requirements.md:
- Open with the request's title, type (Greenfield/Enhancement), and a one-paragraph \
summary of the problem and purpose, informed by both the spreadsheet and the \
clarification answers.
- Include the success criteria and explicit out-of-scope items.
- Include a "Clarifications" section summarizing what the BA's answers added or \
changed versus the original spreadsheet.
- List every requirement from the spreadsheet under a "Requirements" section, each \
with its original Req # for traceability, a clear user story, and acceptance \
criteria sharpened by the clarification answers where relevant. Do not drop any \
requirement row, and do not invent new ones that aren't grounded in the spreadsheet \
or the clarification answers.
- Write for a Technical Approver who needs to decide whether to approve this for \
ADO work item creation — clear, complete, plain English.
- If an Existing Architecture Summary is provided (Enhancement requests only), note \
where each new requirement fits into what already exists, and explicitly flag any \
requirement that appears to conflict with the existing observed behavior described \
in that summary.

Rules for the ADO work-item hierarchy:
- Exactly one Epic, titled after the request itself.
- Group related requirements into logical Features. If no natural grouping exists, \
one Feature per requirement is acceptable.
- Every requirement row must map to exactly one User Story somewhere in the tree — \
never dropped, merged away, or invented.
- Each User Story's description is the full "As a ... I want ... so that ..." story \
text (sharpened by clarification answers where relevant), and acceptance_criteria \
is the full acceptance criteria text.
- Include source_req_number on every User Story (e.g. "R-001") so it can be traced \
back to the original spreadsheet row.

Submit both artifacts via the submit_structured_output tool — do not respond with \
plain text."""

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "requirements_markdown": {
            "type": "string",
            "description": "The full contents of requirements.md.",
        },
        "ado_payload": {
            "type": "object",
            "properties": {
                "epic": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["title", "description"],
                    "additionalProperties": False,
                },
                "features": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "user_stories": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "description": {"type": "string"},
                                        "acceptance_criteria": {"type": "string"},
                                        "source_req_number": {
                                            "type": "string",
                                            "description": "e.g. 'R-001', traces back to the original spreadsheet row.",
                                        },
                                    },
                                    "required": [
                                        "title",
                                        "description",
                                        "acceptance_criteria",
                                        "source_req_number",
                                    ],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": ["title", "description", "user_stories"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["epic", "features"],
            "additionalProperties": False,
        },
    },
    "required": ["requirements_markdown", "ado_payload"],
    "additionalProperties": False,
}


def _is_agent_comment(body: str) -> bool:
    return body.lstrip().startswith(_AGENT_COMMENT_PREFIX)


def _format_clarification_answers(comments: list[dict]) -> str:
    """
    Comments not authored by a FORGE agent (identified by the invisible
    forge:agent-comment marker, not by GitHub account) are treated as the BA's
    clarification answers, concatenated in chronological order.
    """
    human_comments = [c for c in comments if not _is_agent_comment(c.get("body", ""))]
    if not human_comments:
        return "_(no clarification answers found on the tracking issue yet)_"
    lines: list[str] = []
    for c in human_comments:
        author = c.get("user", {}).get("login", "unknown")
        lines.append(f"**{author} wrote:**")
        lines.append(c.get("body", ""))
        lines.append("")
    return "\n".join(lines)


def _is_enhancement(parsed: dict) -> bool:
    request_type_section = parsed["overview"].get("request_type") or {}
    return (request_type_section.get("Request Type") or "").strip().lower() == "enhancement"


# Maps the Intake Template's Pipeline Depth field (Section B, Item #43) to the
# canonical tier value every stage's depth-check guard clause compares against.
# Blank, missing, or unrecognized values default to "full" -- same graceful-
# degradation posture as every other optional intake field (see file_io.py's
# bracket-placeholder stripping) -- so a request submitted before this field
# existed, or with the field left blank, behaves exactly as before.
_PIPELINE_DEPTH_VALUE_MAP = {
    "just requirements": "requirements",
    "up to design": "design",
    "up to implementation": "implementation",
    "up to deployment": "full",
}


def _normalize_pipeline_depth(parsed: dict) -> str:
    request_type_section = parsed["overview"].get("request_type") or {}
    raw_value = (request_type_section.get("Pipeline Depth") or "").strip().lower()
    return _PIPELINE_DEPTH_VALUE_MAP.get(raw_value, "full")


def _fetch_existing_architecture_summary(parsed: dict, request_id: str) -> str | None:
    """
    For an Enhancement request, fetch existing-architecture-summary.md (committed
    by the Codebase Ingestion Agent, Stage 0a, to pipeline-state). Returns None for
    a Greenfield request (nothing to fetch) or a 404 (Ingestion hasn't finished, or
    failed -- logged as a warning, not a hard failure). Any other error propagates
    to the caller.
    """
    if not _is_enhancement(parsed):
        return None
    try:
        return get_file_contents(
            f"docs/{request_id}/existing-architecture-summary.md", branch="pipeline-state"
        )
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            logger.warning(
                "No existing-architecture-summary.md found for enhancement request %s "
                "(Codebase Ingestion may not have finished yet, or may have failed) -- "
                "proceeding without existing-architecture grounding.",
                request_id,
            )
            return None
        raise


def _build_user_prompt(
    parsed: dict,
    clarification_answers: str,
    existing_architecture_summary: str | None = None,
) -> str:
    overview_text = file_io.format_overview_markdown(parsed["overview"])
    requirements_text = file_io.format_requirements_markdown(parsed["requirements"])
    existing_architecture_section = (
        f"## Existing Architecture Summary (Codebase Ingestion Agent)\n\n{existing_architecture_summary}\n"
        if existing_architecture_summary
        else ""
    )
    return (
        "## Request Overview\n\n"
        f"{overview_text}\n"
        f"## Requirements ({len(parsed['requirements'])} submitted)\n\n"
        f"{requirements_text}\n"
        f"{existing_architecture_section}"
        "## BA's Clarification Answers (from the tracking issue thread)\n\n"
        f"{clarification_answers}\n"
        "---\n"
        "Produce your structured output now."
    )


def _render_ado_summary(ado_payload: dict) -> str:
    """Human-readable indented rendering of the draft ADO hierarchy for the issue comment."""
    lines: list[str] = []
    epic = ado_payload.get("epic", {})
    lines.append(f"**Epic:** {epic.get('title', '(untitled)')}")
    for feature in ado_payload.get("features", []):
        lines.append(f"  - **Feature:** {feature.get('title', '(untitled)')}")
        for story in feature.get("user_stories", []):
            req_ref = story.get("source_req_number", "?")
            lines.append(f"    - **User Story** ({req_ref}): {story.get('title', '(untitled)')}")
    return "\n".join(lines)


def run_requirements_agent(
    spreadsheet_path: str,
    issue_number: int,
    request_id: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Core entry point. Returns the parsed model output dict
    ({"requirements_markdown": ..., "ado_payload": ...}).
    """
    if not dry_run and not request_id:
        raise ValueError(
            "--request-id is required for a real (non-dry-run) run — it determines "
            "the docs/<request-id>/ path in the monorepo. Refusing to write to "
            "docs/unknown/ by accident."
        )
    resolved_request_id = request_id or "unknown"

    parsed = file_io.read_xlsx(spreadsheet_path)
    pipeline_depth = _normalize_pipeline_depth(parsed)
    comments = get_issue_comments(issue_number)
    clarification_answers = _format_clarification_answers(comments)

    try:
        existing_architecture_summary = _fetch_existing_architecture_summary(parsed, resolved_request_id)
        user_prompt = _build_user_prompt(parsed, clarification_answers, existing_architecture_summary)
        result = invoke_agent(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=_MAX_TOKENS,
            stage_name=_STAGE_NAME,
            request_id=resolved_request_id,
            output_schema=_OUTPUT_SCHEMA,
        )
        if result.stop_reason == "max_tokens":
            raise ValueError(
                f"Model response was truncated at max_tokens={_MAX_TOKENS} — "
                "increase _MAX_TOKENS in requirements_agent.py and retry."
            )
        parsed_output = result.structured_output
        requirements_md = parsed_output["requirements_markdown"]
        ado_payload = parsed_output["ado_payload"]
    except Exception as exc:
        logger.exception("Requirements Agent failed for request %s", resolved_request_id)
        if not dry_run:
            failure_body = (
                "⚠️ **FORGE Requirements Agent failed to produce a draft.**\n\n"
                f"Error: `{exc}`\n\n"
                "An Orchestration Manager needs to investigate before this request "
                "can proceed. Do not apply `requirements-approved` yet."
            )
            try:
                post_comment(issue_number, failure_body)
            except Exception:
                logger.exception("Also failed to post failure comment to issue #%s", issue_number)
        raise

    if dry_run:
        print("=" * 20, "requirements.md", "=" * 20)
        print(requirements_md)
        print("=" * 20, "ado-work-items.json", "=" * 20)
        print(json.dumps(ado_payload, indent=2))
        print("=" * 20, "pipeline-config.json", "=" * 20)
        print(json.dumps({"pipeline_depth": pipeline_depth}, indent=2))
        logger.info(
            "Dry run complete for request %s — nothing committed, nothing posted.",
            resolved_request_id,
        )
        return parsed_output

    commit_files(
        branch_name="pipeline-state",
        files={
            f"docs/{resolved_request_id}/requirements.md": requirements_md,
            f"docs/{resolved_request_id}/ado-work-items.json": json.dumps(ado_payload, indent=2),
            f"docs/{resolved_request_id}/pipeline-config.json": json.dumps(
                {"pipeline_depth": pipeline_depth}, indent=2
            ),
        },
        commit_message=f"FORGE Requirements Agent: draft requirements for {resolved_request_id}",
    )

    depth_note = (
        f"\n**Pipeline Depth:** `{pipeline_depth}` — this request will stop after the "
        "corresponding stage regardless of which gate labels are applied later "
        "(Item #43).\n"
        if pipeline_depth != "full"
        else ""
    )
    comment_body = (
        f"<!-- forge:agent-comment stage=requirements request_id={resolved_request_id} -->\n"
        "## 📋 FORGE Requirements — Draft Ready for Review\n\n"
        f"`requirements.md` and the draft ADO work-item hierarchy have been committed "
        f"to `docs/{resolved_request_id}/` in the monorepo.\n"
        f"{depth_note}\n"
        "**Draft ADO hierarchy:**\n\n"
        f"{_render_ado_summary(ado_payload)}\n\n"
        "---\n"
        "Review `requirements.md` and the hierarchy above. If it looks correct, apply "
        "the `requirements-approved` label to this issue — ADO work items are created "
        "only after that label is applied."
    )
    post_comment(issue_number, comment_body)
    logger.info(
        "Requirements Agent complete for request %s — files committed, draft posted "
        "to issue #%s.",
        resolved_request_id,
        issue_number,
    )
    return parsed_output


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE Requirements Agent")
    parser.add_argument("--spreadsheet", required=True, help="Path to the completed Intake Template .xlsx")
    parser.add_argument("--issue-number", required=True, type=int, help="FORGE tracking issue number in forge-template")
    parser.add_argument("--request-id", default=None, help="FORGE request ID (required for a real run)")
    parser.add_argument("--dry-run", action="store_true", help="Print output instead of committing/posting")
    args = parser.parse_args()

    try:
        run_requirements_agent(
            spreadsheet_path=args.spreadsheet,
            issue_number=args.issue_number,
            request_id=args.request_id,
            dry_run=args.dry_run,
        )
    except Exception:
        logger.exception("Requirements Agent failed for request %s", args.request_id)
        sys.exit(1)


if __name__ == "__main__":
    main()
