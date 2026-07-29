"""
FORGE Intake Agent — Stage 0b (Intake & Clarification).

Reads a completed BA intake spreadsheet, asks a focused round of clarifying
questions via Claude, and posts them as a comment on the FORGE tracking issue.

Usage:
    python -m core.agents.intake_agent --spreadsheet path/to/file.xlsx --issue-number 42
    python -m core.agents.intake_agent --spreadsheet path/to/file.xlsx --issue-number 42 --dry-run

CLI arguments:
    --spreadsheet   Path to the completed Intake Template .xlsx file (required)
    --issue-number  FORGE tracking issue number in forge-template (required)
    --request-id    FORGE request ID for log correlation. Defaults to the
                     "Request ID" field in the spreadsheet's Overview tab if present,
                     else "unknown".
    --dry-run       Parse the spreadsheet and call Claude, but print the resulting
                     comment to stdout instead of posting it to GitHub, and skip the
                     clarification-pending label. Use this to review agent output
                     locally before wiring into the real pipeline (Phase 4).

Per ADR-0011 / Document 6: the invoke_agent() call is wrapped in try/except at the
call site. On failure, a failure comment is posted to the tracking issue (best-effort)
before the exception is re-raised, so a GitHub Actions run fails loudly rather than
silently.
"""

from __future__ import annotations

import argparse
import logging
import sys

from core.agents.utils import file_io
from core.agents.utils.claude_agent_wrapper import invoke_agent
from core.agents.utils.github_helper import post_comment, add_label

logger = logging.getLogger(__name__)

_STAGE_NAME = "intake"
_MAX_TOKENS = 2048

_SECTION_DISPLAY_NAMES: dict[str, str] = {
    "request_identification": "A — Request Identification",
    "request_type": "B — Request Type",
    "problem_purpose": "C — Problem & Purpose",
    "success_criteria_scope": "D — Success Criteria & Scope",
    "constraints_considerations": "E — Constraints & Considerations",
    "additional_context": "F — Additional Context",
}

_SYSTEM_PROMPT = """You are the FORGE Intake Agent for Legal Aid Alberta's software \
delivery pipeline.

Your job: read a Business Analyst's completed intake spreadsheet (an Overview \
section and a list of Requirements) and produce a focused, numbered list of \
clarifying questions for the BA to answer before the Requirements stage begins.

Rules:
- Ask between 5 and 7 questions. Never more than 7. If the intake is unusually \
complete and fewer than 5 genuine gaps exist, ask only the genuine gaps rather \
than padding with filler questions.
- Every question must target a real ambiguity, missing detail, contradiction, or \
risk you can point to in the supplied data — not a generic question the BA could \
answer straight from the template.
- Prioritize, in order: (1) information needed to write clear, testable acceptance \
criteria, (2) unclear scope boundaries, (3) incomplete or risky technical/compliance \
constraints, (4) anything affecting whether this is genuinely Greenfield vs. \
Enhancement scoping.
- Write in plain, non-technical language a Business Analyst can answer without \
engineering knowledge.
- Do not ask about anything already clearly answered in the Overview or \
Requirements data.
- Number the questions 1 through N, one per line.
- Output ONLY the numbered question list. No preamble, no closing remarks, no \
restating the request, no markdown headers."""


def _format_overview(overview: dict) -> str:
    lines: list[str] = []
    for key, display_name in _SECTION_DISPLAY_NAMES.items():
        fields = overview.get(key) or {}
        lines.append(f"**{display_name}**")
        if not fields:
            lines.append("_(left blank by BA)_")
        else:
            for label, value in fields.items():
                lines.append(f"- {label}: {value if value else '(blank)'}")
        lines.append("")
    return "\n".join(lines)


def _format_requirements(requirements: list[dict]) -> str:
    if not requirements:
        return "_(no requirements rows submitted)_"
    lines: list[str] = []
    for req in requirements:
        lines.append(
            f"**{req.get('req_number') or '(no ID)'}** "
            f"[{req.get('type') or 'Type not set'}, "
            f"{req.get('priority') or 'Priority not set'}]"
        )
        lines.append(f"- User Story: {req.get('user_story')}")
        lines.append(f"- Acceptance Criteria: {req.get('acceptance_criteria') or '(none given)'}")
        if req.get("notes"):
            lines.append(f"- Notes / Constraints: {req['notes']}")
        lines.append("")
    return "\n".join(lines)


def _build_user_prompt(parsed: dict) -> str:
    overview_text = _format_overview(parsed["overview"])
    requirements_text = _format_requirements(parsed["requirements"])
    return (
        "## Request Overview\n\n"
        f"{overview_text}\n"
        f"## Requirements ({len(parsed['requirements'])} submitted)\n\n"
        f"{requirements_text}\n"
        "---\n"
        "Based on the above, produce your clarifying questions now."
    )


def _derive_request_id(parsed: dict, cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    fields = parsed["overview"].get("request_identification") or {}
    return fields.get("Request ID") or "unknown"


def run_intake_agent(
    spreadsheet_path: str,
    issue_number: int,
    request_id: str | None = None,
    dry_run: bool = False,
) -> str:
    """
    Core entry point — parses the spreadsheet, calls Claude, and posts the
    result to the tracking issue (unless dry_run). Returns the comment body
    that was posted (or would have been posted).
    """
    parsed = file_io.read_xlsx(spreadsheet_path)
    resolved_request_id = _derive_request_id(parsed, request_id)
    user_prompt = _build_user_prompt(parsed)

    try:
        result = invoke_agent(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=_MAX_TOKENS,
            stage_name=_STAGE_NAME,
            request_id=resolved_request_id,
        )
    except Exception as exc:
        logger.exception("Intake Agent invocation failed for request %s", resolved_request_id)
        if not dry_run:
            failure_body = (
                "⚠️ **FORGE Intake Agent failed to generate clarifying questions.**\n\n"
                f"Error: `{exc}`\n\n"
                "An Orchestration Manager needs to investigate before this request "
                "can proceed. Do not apply `clarification-complete` yet."
            )
            try:
                post_comment(issue_number, failure_body)
            except Exception:
                logger.exception("Also failed to post failure comment to issue #%s", issue_number)
        raise

    comment_body = (
        "## 🧭 FORGE Intake — Clarifying Questions\n\n"
        f"{result.output_text.strip()}\n\n"
        "---\n"
        "When you've answered every question above, apply the `clarification-complete` "
        "label to this issue to continue the pipeline. If a follow-up round of "
        "questions is needed, remove the label, update your answers, and re-apply it "
        "when you're done."
    )

    if dry_run:
        print(comment_body)
        logger.info(
            "Dry run complete for request %s — comment NOT posted, label NOT applied.",
            resolved_request_id,
        )
        return comment_body

    post_comment(issue_number, comment_body)
    add_label(issue_number, "clarification-pending")
    logger.info(
        "Intake Agent complete for request %s — questions posted to issue #%s, "
        "clarification-pending applied.",
        resolved_request_id,
        issue_number,
    )
    return comment_body


def main() -> None:
    # Force UTF-8 stdout so emoji/unicode in comment bodies never crash on a
    # Windows console using a legacy codepage that can't encode them.
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE Intake Agent")
    parser.add_argument("--spreadsheet", required=True, help="Path to the completed Intake Template .xlsx")
    parser.add_argument("--issue-number", required=True, type=int, help="FORGE tracking issue number in forge-template")
    parser.add_argument("--request-id", default=None, help="FORGE request ID (defaults to the spreadsheet's Request ID field)")
    parser.add_argument("--dry-run", action="store_true", help="Print the comment instead of posting it to GitHub")
    args = parser.parse_args()

    try:
        run_intake_agent(
            spreadsheet_path=args.spreadsheet,
            issue_number=args.issue_number,
            request_id=args.request_id,
            dry_run=args.dry_run,
        )
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
