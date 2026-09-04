"""
FORGE Design Agent — Stage 2 (Design).

Reads the approved requirements.md (committed to the monorepo by the Requirements
Agent, on the `pipeline-state` branch -- see below) and the team's
stack-preferences.yaml, and produces:
  - design.md    — architecture narrative, component breakdown, tech choices
  - openapi.yaml — API contract (OpenAPI 3.0)
  - tasks.md     — implementation task breakdown for the Stage 3 subagents
                    (Backend, Frontend, Test Writer)

Unlike the Requirements Agent (which commits straight to `pipeline-state`, a
dedicated, intentionally-unprotected bookkeeping branch -- Phase 4 step 4.8
retrofit, see CLAUDE.md's "Phase 4 -- Pipeline Wiring" section), the Design
Agent is the first stage to use the full create_branch() -> commit_files() ->
open_pr() chain: it commits all three artifacts to a design/<request-id>
branch in the monorepo and opens a real PR against `main` (Document 6 Gate 2)
-- design.md/openapi.yaml/tasks.md DO land on `main` for real, once a human
merges that PR, unlike requirements.md/ado-work-items.json. A summary comment
linking to the PR is posted on the FORGE tracking issue for the Technical
Approver.

Usage:
    python -m core.agents.design_agent --issue-number 2 --request-id REQ-2026-01
    python -m core.agents.design_agent --issue-number 2 --request-id REQ-2026-01 --dry-run

CLI arguments:
    --issue-number       FORGE tracking issue number in forge-template, used to
                          post the summary comment (unless --dry-run) (required)
    --request-id          FORGE request ID. Required for a real run (used for the
                          monorepo path docs/<request-id>/ and the design/<request-id>
                          branch); optional for --dry-run.
    --stack-preferences   Local path to team/stack-preferences.yaml (default:
                          "team/stack-preferences.yaml" — lives in forge-template,
                          so a local checkout has it directly; no GitHub API call
                          needed to read it).
    --dry-run             Fetch requirements.md and stack preferences and call
                          Claude, but print design.md / openapi.yaml / tasks.md to
                          stdout instead of committing or posting to GitHub.

Per ADR-0011 / Document 6: the invoke_agent() call is wrapped in try/except at the
call site. On failure (or malformed/truncated JSON, or an invalid openapi.yaml), a
failure comment is posted to the tracking issue (best-effort, real run only)
before the exception is re-raised.

Enhancement requests (Phase 7 step 7.1): also attempts to fetch
existing-architecture-summary.md (committed by the Codebase Ingestion Agent,
Stage 0a, to the same pipeline-state branch) and folds it into the prompt.
Unlike requirements_agent.py, this agent never reads the original intake
spreadsheet -- it has no direct signal for Greenfield vs. Enhancement -- so the
fetch is attempted unconditionally rather than gated on a parsed Request Type
field. A 404 is tolerated exactly the same way either way: expected and silent
for a Greenfield request (nothing was ever committed), or "Ingestion hasn't
finished/failed yet" for an Enhancement request -- both degrade identically to
proceeding without it, so no extra signal is lost by not distinguishing them here.
Any OTHER fetch error propagates into the existing try/except below and produces
the standard failure comment.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import requests
import yaml

from core.agents.utils import file_io
from core.agents.utils.claude_agent_wrapper import invoke_agent
from core.agents.utils.github_helper import (
    get_file_contents,
    post_comment,
    create_branch,
    commit_files,
    open_pr,
)

logger = logging.getLogger(__name__)

_STAGE_NAME = "design"
_MAX_TOKENS = 20000
_DEFAULT_STACK_PREFS_PATH = "team/stack-preferences.yaml"

_SYSTEM_PROMPT = """You are the FORGE Design Agent for Legal Aid Alberta's software \
delivery pipeline.

You will be given: (1) the approved requirements.md for this request, and (2) the \
team's stack-preferences.yaml, describing the technology choices FORGE mandates at \
the core layer and the choices the team has made (or not yet made) at the team \
layer.

Your job is to produce three artifacts:

1. design.md — an architecture narrative for a Technical Approver, using the C4 \
model's vocabulary (context, containers, components) at whatever level of detail \
this request warrants. Include:
   - A short architecture overview: what this system is, and where it fits.
   - A component breakdown: name each component/service, its responsibility, and \
which requirement(s) it satisfies (cite requirement IDs from requirements.md, \
e.g. "R-001", so every component traces back to a real requirement).
   - A tech choices section: state the core-layer mandates as fixed (TypeScript, \
Next.js, .NET, Docker, Azure Container Apps, GitHub Actions), and state the \
team-layer choices from stack-preferences.yaml. For any team-layer field marked \
as not yet set, propose a sensible, well-justified default and flag it clearly as \
a Design Agent recommendation for the Technical Approver to confirm or override \
at this gate — never present an unset field as if it were an existing team \
standard.
   - A **Required Secrets** section, heading exactly `## Required Secrets`: a \
markdown table listing every secret, API key, connection string, or credential \
this service's code will need at runtime. Columns: Secret Name (the actual \
environment variable or configuration key the app will read -- not a vague \
description), Purpose, and Source (e.g. "Azure Key Vault", "external service \
credential", or "framework-internal -- consumed by <library> directly, never \
referenced in application code" for a case like NextAuth's own \
NEXTAUTH_SECRET/NEXTAUTH_URL). Reason about this actively rather than only \
restating secrets already named elsewhere in the document -- consider any \
authentication library or pattern this design chooses (NextAuth, MSAL/Azure AD, \
or similar), any named external service integration (message queues, email \
providers, third-party APIs, D365/Dataverse-style systems), and any database \
connection string. If, after this reasoning, no secrets are required, the \
section must still be written, with the literal text "None identified" -- never \
omit this section entirely, even when the answer is none. This section is a \
**declaration of what secrets are required**, not a promise that they are \
correctly wired -- do not include placeholder or real secret values here.
   - Do not invent requirements not present in requirements.md; if something is \
ambiguous, state your assumption explicitly rather than silently picking one.

2. openapi.yaml — a valid OpenAPI 3.0 specification (YAML) for the API surface \
implied by requirements.md. Cover the endpoints, request/response schemas, and \
status codes needed to satisfy the requirements. This must be syntactically valid \
YAML — it will be parsed and rejected if it is not.

3. tasks.md — an implementation task breakdown organized under three headings \
("Backend", "Frontend", "Test Writer"), matching the three subagents that will \
read this file in Stage 3. Each task should be concrete and scoped enough that a \
subagent can pick it up and know what to build, and should reference the \
design.md component and requirement ID it serves.

tasks.md scope boundary — this is strict: every task item must describe only \
files that live under services/<request-id>/ (backend, frontend, or tests). Do \
NOT propose a task for a CI/CD workflow, pipeline configuration, or any other \
repository-root infrastructure — those are owned by the FORGE template itself, \
are already fixed for every request, and are never something the Backend, \
Frontend, or Test Writer subagents should build. This does not apply to \
design.md's own architecture narrative, which may still discuss CI/CD (e.g. \
"GitHub Actions") as part of the fixed core-layer tech choices above — the \
boundary is on tasks.md's per-subagent task items specifically.

If an Existing Architecture Summary is provided (Enhancement requests only): \
respect the existing tech stack, naming conventions, folder layout, and API \
surface it describes in both design.md and tasks.md — do not propose a design \
or task breakdown as if the folder were empty. In design.md, note explicitly \
where each new component fits alongside what already exists, and flag anywhere \
a requirement appears to conflict with the existing observed behavior.

Submit your three artifacts via the submit_structured_output tool — do not respond \
with plain text."""

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "design_markdown": {
            "type": "string",
            "description": "The full contents of design.md.",
        },
        "openapi_yaml": {
            "type": "string",
            "description": "The full contents of openapi.yaml, valid YAML.",
        },
        "tasks_markdown": {
            "type": "string",
            "description": "The full contents of tasks.md.",
        },
    },
    "required": ["design_markdown", "openapi_yaml", "tasks_markdown"],
    "additionalProperties": False,
}


def _fetch_existing_architecture_summary(request_id: str) -> str | None:
    """
    Attempt to read existing-architecture-summary.md (committed by the Codebase
    Ingestion Agent, Stage 0a, to pipeline-state). Unlike requirements_agent.py,
    this is attempted unconditionally -- design_agent.py never reads the original
    spreadsheet, so it has no direct Greenfield-vs-Enhancement signal. A 404 is
    tolerated the same way regardless of cause (see module docstring); any other
    error propagates to the caller.
    """
    try:
        return get_file_contents(
            f"docs/{request_id}/existing-architecture-summary.md", branch="pipeline-state"
        )
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            logger.warning(
                "No existing-architecture-summary.md found for request %s -- proceeding "
                "without existing-architecture grounding (expected for a Greenfield "
                "request; for an Enhancement request, confirm the Codebase Ingestion "
                "Agent has finished).",
                request_id,
            )
            return None
        raise


def _build_user_prompt(
    requirements_md: str,
    stack_prefs_text: str,
    existing_architecture_summary: str | None = None,
) -> str:
    existing_architecture_section = (
        f"## Existing Architecture Summary (Codebase Ingestion Agent)\n\n{existing_architecture_summary}\n"
        if existing_architecture_summary
        else ""
    )
    return (
        "## Approved Requirements (requirements.md)\n\n"
        f"{requirements_md}\n"
        "## Team Stack Preferences\n\n"
        f"{stack_prefs_text}\n"
        f"{existing_architecture_section}"
        "---\n"
        "Produce your structured output now."
    )


def run_design_agent(
    issue_number: int,
    request_id: str | None = None,
    stack_preferences_path: str = _DEFAULT_STACK_PREFS_PATH,
    dry_run: bool = False,
) -> dict:
    """
    Core entry point. Returns the parsed model output dict
    ({"design_markdown": ..., "openapi_yaml": ..., "tasks_markdown": ...}).
    """
    if not dry_run and not request_id:
        raise ValueError(
            "--request-id is required for a real (non-dry-run) run — it determines "
            "the docs/<request-id>/ path and design/<request-id> branch in the "
            "monorepo. Refusing to proceed without it."
        )
    resolved_request_id = request_id or "unknown"

    requirements_md = get_file_contents(
        f"docs/{resolved_request_id}/requirements.md", branch="pipeline-state"
    )
    stack_prefs = file_io.read_yaml(stack_preferences_path)
    stack_prefs_text = file_io.format_stack_preferences_markdown(stack_prefs)

    try:
        existing_architecture_summary = _fetch_existing_architecture_summary(resolved_request_id)
        user_prompt = _build_user_prompt(requirements_md, stack_prefs_text, existing_architecture_summary)
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
                "increase _MAX_TOKENS in design_agent.py and retry."
            )
        parsed_output = result.structured_output
        design_md = parsed_output["design_markdown"]
        openapi_yaml_text = parsed_output["openapi_yaml"]
        tasks_md = parsed_output["tasks_markdown"]

        # Validate the openapi.yaml the model produced is actually parseable —
        # catch a malformed spec here rather than committing broken YAML.
        try:
            yaml.safe_load(openapi_yaml_text)
        except yaml.YAMLError as yaml_exc:
            raise ValueError(f"Model's openapi_yaml is not valid YAML: {yaml_exc}") from yaml_exc

    except Exception as exc:
        logger.exception("Design Agent failed for request %s", resolved_request_id)
        if not dry_run:
            failure_body = (
                "⚠️ **FORGE Design Agent failed to produce a draft.**\n\n"
                f"Error: `{exc}`\n\n"
                "An Orchestration Manager needs to investigate before this request "
                "can proceed. Do not apply `design-approved` yet."
            )
            try:
                post_comment(issue_number, failure_body)
            except Exception:
                logger.exception("Also failed to post failure comment to issue #%s", issue_number)
        raise

    if dry_run:
        print("=" * 20, "design.md", "=" * 20)
        print(design_md)
        print("=" * 20, "openapi.yaml", "=" * 20)
        print(openapi_yaml_text)
        print("=" * 20, "tasks.md", "=" * 20)
        print(tasks_md)
        logger.info(
            "Dry run complete for request %s — nothing committed, nothing posted.",
            resolved_request_id,
        )
        return parsed_output

    branch_name = f"design/{resolved_request_id}"
    create_branch(branch_name, from_branch="main")
    commit_files(
        branch_name=branch_name,
        files={
            f"docs/{resolved_request_id}/design.md": design_md,
            f"docs/{resolved_request_id}/openapi.yaml": openapi_yaml_text,
            f"docs/{resolved_request_id}/tasks.md": tasks_md,
        },
        commit_message=f"FORGE Design Agent: draft design for {resolved_request_id}",
    )

    owner = os.environ.get("FORGE_GITHUB_OWNER", "")
    source_repo = os.environ.get("FORGE_SOURCE_REPO", "forge-template")
    tracking_issue_ref = f"{owner}/{source_repo}#{issue_number}" if owner else f"#{issue_number}"

    pr = open_pr(
        title=f"FORGE Design: {resolved_request_id}",
        body=(
            f"Design artifacts for {resolved_request_id}, generated by the FORGE "
            f"Design Agent.\n\nRelated FORGE tracking issue: {tracking_issue_ref}\n\n"
            "Contains `design.md`, `openapi.yaml`, and `tasks.md`. Merge to approve "
            "(Document 6 Gate 2)."
        ),
        head_branch=branch_name,
        base_branch="main",
        draft=True,
    )

    comment_body = (
        f"<!-- forge:agent-comment stage=design request_id={resolved_request_id} -->\n"
        "## 📐 FORGE Design — Draft Ready for Review\n\n"
        f"`design.md`, `openapi.yaml`, and `tasks.md` have been committed to "
        f"`docs/{resolved_request_id}/` on branch `{branch_name}`, and a draft PR "
        f"has been opened: {pr['html_url']}\n\n"
        "---\n"
        "Review the PR. If the architecture and API contract look correct, mark it "
        "ready for review and merge it, then apply the `design-approved` label to "
        "this issue to start Implementation."
    )
    post_comment(issue_number, comment_body)
    logger.info(
        "Design Agent complete for request %s — PR #%s opened, summary posted to issue #%s.",
        resolved_request_id,
        pr["number"],
        issue_number,
    )
    return parsed_output


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE Design Agent")
    parser.add_argument("--issue-number", required=True, type=int, help="FORGE tracking issue number in forge-template")
    parser.add_argument("--request-id", default=None, help="FORGE request ID (required for a real run)")
    parser.add_argument("--stack-preferences", default=_DEFAULT_STACK_PREFS_PATH, help="Local path to team/stack-preferences.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print output instead of committing/posting")
    args = parser.parse_args()

    try:
        run_design_agent(
            issue_number=args.issue_number,
            request_id=args.request_id,
            stack_preferences_path=args.stack_preferences,
            dry_run=args.dry_run,
        )
    except Exception:
        logger.exception("Design Agent failed for request %s", args.request_id)
        sys.exit(1)


if __name__ == "__main__":
    main()
