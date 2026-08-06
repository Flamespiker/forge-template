"""
FORGE ADO Item Creation — Phase 4 step 4.3, part of the Stage 2 (Design) workflow.

Reads the draft ADO hierarchy the Requirements Agent committed to
docs/<request-id>/ado-work-items.json (main branch, forge-demo-apps), creates
the real Epic -> Features -> User Stories in Azure DevOps via ado_helper.py,
and writes the resulting numeric IDs back into that same file (main branch) --
including a top-level "primary_user_story_id" key, which qa_agent.py's
_resolve_parent_story_id() already looks for and silently no-ops on when it's
absent.

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

from core.agents.utils import ado_helper
from core.agents.utils.github_helper import get_file_contents, commit_files, post_comment

logger = logging.getLogger(__name__)


def _ado_items_path(request_id: str) -> str:
    return f"docs/{request_id}/ado-work-items.json"


def run_create_ado_items(
    issue_number: int,
    request_id: str,
    dry_run: bool = False,
) -> dict:
    """
    Core entry point. Returns the updated ado-work-items.json payload (with
    real ADO IDs merged in).
    """
    path = _ado_items_path(request_id)
    content = get_file_contents(path, branch="main")
    payload = json.loads(content)

    if "epic" not in payload or "features" not in payload:
        raise ValueError(
            f"{path} is missing required 'epic' or 'features' keys -- refusing "
            "to create ADO items against a malformed payload."
        )

    created_summary: list[str] = []
    primary_user_story_id: int | None = None

    try:
        epic = ado_helper.create_epic(
            title=payload["epic"]["title"],
            description=payload["epic"].get("description", ""),
        )
        payload["epic"]["ado_id"] = epic["id"]
        created_summary.append(f"Epic #{epic['id']}: {payload['epic']['title']}")

        for feature in payload["features"]:
            created_feature = ado_helper.create_feature(
                title=feature["title"],
                description=feature.get("description", ""),
                parent_epic_id=epic["id"],
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
        branch_name="main",
        files={path: json.dumps(payload, indent=2)},
        commit_message=f"FORGE: create ADO work items for {request_id}",
    )
    logger.info(
        "ADO item creation complete for request %s -- %d item(s) created, "
        "primary_user_story_id=%s, %s updated on main.",
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
    args = parser.parse_args()

    try:
        run_create_ado_items(
            issue_number=args.issue_number,
            request_id=args.request_id,
            dry_run=args.dry_run,
        )
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
