"""
Smoke test — ado_helper.py

Exercises the real ADO REST API against the FORGE-Build project (spike99 org).
Run manually from the repo root:
    python -m core.agents.utils.smoke_tests.smoke_ado

Requires a .env file with: ADO_PAT.
Config (org URL, project) is read automatically from team/config.yaml.

Creates a real test Epic → Feature → User Story → Bug hierarchy, verifies
the parent links, then deletes all created items to leave ADO clean.
"""

from __future__ import annotations

import os
import sys
import traceback

import requests
from dotenv import load_dotenv

load_dotenv()

from core.agents.utils import ado_helper as ado  # noqa: E402

PASS = "[PASS]"
FAIL = "[FAIL]"
results: list[tuple[str, bool]] = []
created_ids: list[int] = []


def run(label: str, fn):
    try:
        result = fn()
        print(f"{PASS} {label}")
        results.append((label, True))
        return result
    except Exception as exc:
        print(f"{FAIL} {label}: {exc}")
        traceback.print_exc()
        results.append((label, False))
        return None


def delete_work_item(item_id: int) -> None:
    """Permanently delete a work item (cleanup after smoke test)."""
    url = (
        f"{ado._ORG_URL}/{ado._PROJECT}/_apis/wit/workitems/{item_id}"
        f"?api-version={ado._ADO_API_VERSION}&destroy=true"
    )
    requests.delete(url, auth=ado._auth(), timeout=15).raise_for_status()
    print(f"       Deleted work item #{item_id}")


def main():
    print("=== ADO Helper Smoke Test ===\n")
    print(f"  Org:     {ado._ORG_URL}")
    print(f"  Project: {ado._PROJECT}\n")

    epic = run(
        "create_epic('FORGE Smoke Test Epic', ...)",
        lambda: ado.create_epic(
            "FORGE Smoke Test Epic",
            "Created by FORGE smoke test — safe to delete.",
        ),
    )
    if epic:
        created_ids.append(epic["id"])

    feature = None
    if epic:
        feature = run(
            "create_feature('FORGE Smoke Test Feature', ..., parent=epic)",
            lambda: ado.create_feature(
                "FORGE Smoke Test Feature",
                "Created by FORGE smoke test.",
                epic["id"],
            ),
        )
        if feature:
            created_ids.append(feature["id"])

    story = None
    if feature:
        story = run(
            "create_user_story('As a smoke test ...', ..., parent=feature)",
            lambda: ado.create_user_story(
                "As a smoke test, I want ADO connectivity verified",
                "Created by FORGE smoke test.",
                "All smoke test work items are cleaned up after the run.",
                feature["id"],
            ),
        )
        if story:
            created_ids.append(story["id"])

    if story:
        bug = run(
            "create_bug('Smoke test bug', ..., parent=story)",
            lambda: ado.create_bug(
                "FORGE Smoke Test Bug",
                "1. Run smoke test\n2. Observe this bug entry\n3. Verify cleanup",
                "4 - Low",
                story["id"],
            ),
        )
        if bug:
            created_ids.append(bug["id"])

    # Cleanup
    print(f"\nCleaning up {len(created_ids)} work item(s)...")
    for item_id in reversed(created_ids):  # children before parents
        try:
            delete_work_item(item_id)
        except Exception as exc:
            print(f"  Warning: could not delete #{item_id}: {exc}")

    print("\n=== Results ===")
    passed = sum(1 for _, ok in results if ok)
    for label, ok in results:
        print(f"  {'OK' if ok else 'XX'} {label}")
    print(f"\n{passed}/{len(results)} checks passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
