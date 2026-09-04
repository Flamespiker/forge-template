"""
FORGE ADO Item Creation — Phase 4 step 4.3, part of the Stage 2 (Design) workflow.

Reads the draft ADO hierarchy the Requirements Agent committed to
docs/<request-id>/ado-work-items.json (`pipeline-state` branch, forge-demo-apps
-- moved off `main` in the Phase 4 step 4.8 retrofit once branch protection
required a PR review for every push to `main` and no bypass was available;
see CLAUDE.md's "Phase 4 -- Pipeline Wiring" section), creates the real
Epic -> Features -> User Stories in Azure DevOps via ado_helper.py, and
writes the resulting numeric IDs back into that same file on that same
branch -- including a top-level "primary_user_story_id" key, which
qa_agent.py's _resolve_parent_story_id() already looks for and silently
no-ops on when it's absent.

`pipeline-state` is a persistent, shared branch (unlike `design/<request-id>`/
`feature/<request-id>`, which are created fresh per request) -- it already
exists in forge-demo-apps as of this retrofit, so this script does not call
create_branch() itself; doing so unconditionally would fail with "Reference
already exists" on every run after the first.

This is orchestration glue, not an agent: no Claude call happens here. Per
Document 6, ADO items are created only once, only on requirements-approved --
this script has no re-run guard beyond that (it is only ever invoked by
02-design.yml immediately before the Design Agent, once per approval).

"primary_user_story_id" is chosen as the FIRST User Story created, in
document order (first Feature's first User Story). Nothing in Document 3 or
the ado-work-items.json schema names a "primary" story explicitly -- this is
a deliberate, documented default so QA has *something* concrete to link Bugs
against, not a claim that it's the most relevant story for every Bug.

Usage:
    python -m core.agents.create_ado_items --issue-number 42 --request-id REQ-2026-01
    python -m core.agents.create_ado_items --issue-number 42 --request-id REQ-2026-01 --dry-run

Design requirement (Phase 4 brief): if ANY ADO item creation call fails, this
script must fail loudly (non-zero exit) and must NOT leave the caller free to
proceed to the Design Agent against a partial traceability chain. Items
already created before the failure are NOT rolled back (ADO has no atomic
multi-item transaction) -- the failure comment names exactly which item
failed so a human can inspect/clean up the partial hierarchy in ADO directly.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

import requests

from core.agents.utils import ado_helper
from core.agents.utils.github_helper import get_file_contents, commit_files, post_comment

logger = logging.getLogger(__name__)


def _ado_items_path(request_id: str) -> str:
    return f"docs/{request_id}/ado-work-items.json"


def _resolve_existing_epic_id(existing_service: str) -> int:
    """
    Item #32: for an Enhancement request, look up the existing service's own
    real Epic ID instead of creating a brand-new, disconnected one.

    Fetches docs/<existing_service>/ado-work-items.json from pipeline-state and
    returns its epic.ado_id. Raises ValueError (caught by the same
    failure-comment path run_create_ado_items() already has) if the file is
    missing, malformed, or epic.ado_id isn't a populated int -- an Enhancement
    whose existing service has no discoverable Epic ID is a real problem worth
    surfacing loudly, not a case to silently fall back from. The three failure
    shapes (file not found / not valid JSON / epic.ado_id not populated) get
    distinct messages, since a human diagnosing this will want to know which.
    """
    path = _ado_items_path(existing_service)
    try:
        content = get_file_contents(path, branch="pipeline-state")
    except requests.HTTPError as exc:
        raise ValueError(
            f"Could not find {path} on pipeline-state for existing service "
            f"'{existing_service}' -- has that service's own ADO items ever "
            f"been created? ({exc})"
        ) from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    epic_id = payload.get("epic", {}).get("ado_id")
    if not isinstance(epic_id, int):
        raise ValueError(
            f"{path} was found but its epic.ado_id is not a populated int "
            f"(got {epic_id!r}) -- the existing service's own Epic may never "
            "have been created, or this file predates ADO item creation."
        )
    return epic_id


def run_create_ado_items(
    issue_number: int,
    request_id: str,
    dry_run: bool = False,
    existing_service: str = "",
) -> dict:
    """
    Core entry point. Returns the updated ado-work-items.json payload (with
    real ADO IDs merged in).

    Item #32: when existing_service is set (an Enhancement request whose
    existing service resolved to a real value -- same "" convention
    enhancement_target.py's resolve_service_root() already documents), the
    Features/User Stories below are created as children of that existing
    service's own real Epic (looked up via _resolve_existing_epic_id())
    instead of a brand-new, disconnected one. Greenfield (existing_service
    falsy): zero behavior change from before this fix.
    """
    path = _ado_items_path(request_id)
    content = get_file_contents(path, branch="pipeline-state")
    payload = json.loads(content)

    if "epic" not in payload or "features" not in payload:
        raise ValueError(
            f"{path} is missing required 'epic' or 'features' keys -- refusing "
            "to create ADO items against a malformed payload."
        )

    created_summary: list[str] = []
    primary_user_story_id: int | None = None

    try:
        if existing_service:
            epic_id = _resolve_existing_epic_id(existing_service)
            payload["epic"]["ado_id"] = epic_id
            payload["epic"]["reused_existing"] = True
            created_summary.append(
                f"Reused existing Epic #{epic_id} (not created this run) -- "
                f"existing service '{existing_service}'"
            )
        else:
            epic = ado_helper.create_epic(
                title=payload["epic"]["title"],
                description=payload["epic"].get("description", ""),
            )
            epic_id = epic["id"]
            payload["epic"]["ado_id"] = epic_id
            created_summary.append(f"Epic #{epic_id}: {payload['epic']['title']}")

        for feature in payload["features"]:
            created_feature = ado_helper.create_feature(
                title=feature["title"],
                description=feature.get("description", ""),
                parent_epic_id=epic_id,
            )
            feature["ado_id"] = created_feature["id"]
            created_summary.append(f"  Feature #{created_feature['id']}: {feature['title']}")

            for story in feature.get("user_stories", []):
                created_story = ado_helper.create_user_story(
                    title=story["title"],
                    description=story.get("description", ""),
                    acceptance_criteria=story.get("acceptance_criteria", ""),
                    parent_feature_id=created_feature["id"],
                )
                story["ado_id"] = created_story["id"]
                created_summary.append(
                    f"    User Story #{created_story['id']}: {story['title']}"
                )
                if primary_user_story_id is None:
                    primary_user_story_id = created_story["id"]

    except Exception as exc:
        logger.exception(
            "ADO item creation failed for request %s partway through -- items "
            "already created above are NOT rolled back.",
            request_id,
        )
        if not dry_run:
            progress_text = "\n".join(created_summary) if created_summary else "(none created yet)"
            failure_body = (
                "⚠️ **FORGE ADO item creation failed -- Design stage blocked.**\n\n"
                f"Error: `{exc}`\n\n"
                "**Items successfully created before the failure (NOT rolled back -- "
                "review/clean up directly in ADO if needed):**\n\n"
                f"```\n{progress_text}\n```\n\n"
                "The Design Agent will NOT run against a partial traceability chain. "
                "An Orchestration Manager needs to investigate, then either fix and "
                "re-apply `requirements-approved`, or complete the remaining ADO items "
                "manually and re-trigger Design directly."
            )
            try:
                post_comment(issue_number, failure_body)
            except Exception:
                logger.exception("Also failed to post failure comment to issue #%s", issue_number)
        raise

    payload["primary_user_story_id"] = primary_user_story_id

    if dry_run:
        print("=" * 20, "ado-work-items.json (with real IDs)", "=" * 20)
        print(json.dumps(payload, indent=2))
        logger.info(
            "Dry run complete for request %s -- %d ADO item(s) created for real "
            "(ADO has no dry-run mode of its own), nothing committed back to the repo.",
            request_id, len(created_summary),
        )
        return payload

    commit_files(
        branch_name="pipeline-state",
        files={path: json.dumps(payload, indent=2)},
        commit_message=f"FORGE: create ADO work items for {request_id}",
    )
    logger.info(
        "ADO item creation complete for request %s -- %d item(s) created, "
        "primary_user_story_id=%s, %s updated on pipeline-state.",
        request_id, len(created_summary), primary_user_story_id, path,
    )
    return payload


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE ADO Item Creation (Stage 2 prerequisite)")
    parser.add_argument("--issue-number", required=True, type=int, help="FORGE tracking issue number in forge-template")
    parser.add_argument("--request-id", required=True, help="FORGE request ID")
    parser.add_argument("--dry-run", action="store_true", help="Create real ADO items but don't commit the updated json back")
    parser.add_argument(
        "--existing-service", default="",
        help="Item #32: for an Enhancement request, the existing service whose real "
             "Epic these Features/User Stories should be created under. Empty string "
             "(default) means Greenfield or unresolved -- creates a brand-new Epic.",
    )
    args = parser.parse_args()

    try:
        run_create_ado_items(
            issue_number=args.issue_number,
            request_id=args.request_id,
            dry_run=args.dry_run,
            existing_service=args.existing_service,
        )
    except Exception:
        logger.exception("ADO item creation failed for request %s", args.request_id)
        sys.exit(1)


if __name__ == "__main__":
    main()
