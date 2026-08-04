"""
FORGE ADO helper — creates and links work items in Azure DevOps Boards.

Auth: PAT-based. The ADO REST API uses HTTP Basic auth with a blank username and the
PAT as the password. Base64 encoding is handled by the requests library.

Org URL and project are read from team/config.yaml (ado.org_url and ado.project keys).
This module loads the config at import time so all functions share one parsed config.

Required environment variables (see .env.example):
    ADO_PAT — Azure DevOps Personal Access Token with Work Items (R/W) and Project (R) scopes.

Config keys read from team/config.yaml:
    ado.org_url  — e.g. https://dev.azure.com/spike99
    ado.project  — e.g. FORGE-Build
    ado.area_path — default area path for work items
    ado.default_tags — list of tags applied to every item (must include "forge-managed")
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any

import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_ADO_API_VERSION = "7.1"

# ── Config loading ─────────────────────────────────────────────────────────────

def _load_config() -> dict:
    config_path = Path(__file__).parents[3] / "team" / "config.yaml"
    with config_path.open() as f:
        return yaml.safe_load(f)


_CONFIG = _load_config()
_ADO_CFG = _CONFIG.get("ado", {})
_ORG_URL: str = _ADO_CFG.get("org_url", "").rstrip("/")
_PROJECT: str = _ADO_CFG.get("project", "")
_AREA_PATH: str = _ADO_CFG.get("area_path", _PROJECT)
_DEFAULT_TAGS: list[str] = _ADO_CFG.get("default_tags", ["forge-managed"])


def _auth() -> tuple[str, str]:
    pat = os.environ["ADO_PAT"]
    return ("", pat)  # blank username, PAT as password — standard ADO Basic auth


def _wit_url(path: str = "") -> str:
    """Build a Work Item Tracking REST URL."""
    return f"{_ORG_URL}/{_PROJECT}/_apis/wit/{path}?api-version={_ADO_API_VERSION}"


def _patch_headers() -> dict[str, str]:
    return {"Content-Type": "application/json-patch+json"}


def _tag_string() -> str:
    return "; ".join(_DEFAULT_TAGS)


def _make_patch(fields: dict[str, Any]) -> list[dict]:
    """Convert a flat {field_ref: value} dict into a JSON Patch document for ADO."""
    return [{"op": "add", "path": f"/fields/{key}", "value": val} for key, val in fields.items()]


def _create_work_item(item_type: str, patch: list[dict]) -> dict:
    url = f"{_ORG_URL}/{_PROJECT}/_apis/wit/workitems/${item_type}?api-version={_ADO_API_VERSION}"
    response = requests.post(
        url,
        auth=_auth(),
        headers=_patch_headers(),
        json=patch,
        timeout=20,
    )
    response.raise_for_status()
    item = response.json()
    logger.info("Created %s #%s: %s", item_type, item["id"], item["fields"].get("System.Title"))
    return item


# ── Public functions ───────────────────────────────────────────────────────────

def create_epic(title: str, description: str) -> dict:
    """
    Create an Epic work item in ADO.

    Args:
        title: Epic title.
        description: HTML or plain-text description.

    Returns:
        The created work item object from the ADO REST API.
    """
    patch = _make_patch({
        "System.Title": title,
        "System.Description": description,
        "System.AreaPath": _AREA_PATH,
        "System.Tags": _tag_string(),
    })
    return _create_work_item("Epic", patch)


def create_feature(title: str, description: str, parent_epic_id: int) -> dict:
    """
    Create a Feature work item in ADO, linked to a parent Epic.

    Args:
        title: Feature title.
        description: HTML or plain-text description.
        parent_epic_id: ADO work item ID of the parent Epic.

    Returns:
        The created work item object from the ADO REST API.
    """
    patch = _make_patch({
        "System.Title": title,
        "System.Description": description,
        "System.AreaPath": _AREA_PATH,
        "System.Tags": _tag_string(),
    })
    feature = _create_work_item("Feature", patch)
    link_items(parent_epic_id, feature["id"])
    return feature


def create_user_story(
    title: str,
    description: str,
    acceptance_criteria: str,
    parent_feature_id: int,
) -> dict:
    """
    Create a User Story work item in ADO, linked to a parent Feature.

    Args:
        title: User Story title.
        description: HTML or plain-text description (the "As a … I want … so that …" text).
        acceptance_criteria: HTML or plain-text acceptance criteria.
        parent_feature_id: ADO work item ID of the parent Feature.

    Returns:
        The created work item object from the ADO REST API.
    """
    patch = _make_patch({
        "System.Title": title,
        "System.Description": description,
        "Microsoft.VSTS.Common.AcceptanceCriteria": acceptance_criteria,
        "System.AreaPath": _AREA_PATH,
        "System.Tags": _tag_string(),
    })
    story = _create_work_item("User Story", patch)
    link_items(parent_feature_id, story["id"])
    return story


def create_bug(
    title: str,
    repro_steps: str,
    severity: str,
    parent_story_id: int | None = None,
) -> dict:
    """
    Create a Bug work item in ADO, optionally linked to a parent User Story.

    Args:
        title: Bug title.
        repro_steps: HTML or plain-text reproduction steps.
        severity: Severity string — one of "1 - Critical", "2 - High", "3 - Medium", "4 - Low".
        parent_story_id: ADO work item ID of the parent User Story. Optional
            (default None) because as of Step 3.8 (QA Agent), Phase 4's ADO
            item-creation wiring (step 4.3) has not yet run for any request —
            no real User Story IDs exist yet to link against. When None, the
            Bug is created without a parent link and the caller is responsible
            for logging that the link was skipped. Once Phase 4 exists and a
            real request-id -> User Story ID mapping is available, callers
            should always pass a real ID here — this parameter should not stay
            optional in practice once that mapping exists.

    Returns:
        The created work item object from the ADO REST API.
    """
    patch = _make_patch({
        "System.Title": title,
        "Microsoft.VSTS.TCM.ReproSteps": repro_steps,
        "Microsoft.VSTS.Common.Severity": severity,
        "System.AreaPath": _AREA_PATH,
        "System.Tags": _tag_string(),
    })
    bug = _create_work_item("Bug", patch)
    if parent_story_id is not None:
        link_items(parent_story_id, bug["id"])
    else:
        logger.warning(
            "Bug #%s created with no parent User Story link — no real ADO "
            "User Story ID was available (Phase 4 ADO item creation not yet run "
            "for this request).",
            bug["id"],
        )
    return bug


def link_items(parent_id: int, child_id: int) -> None:
    """
    Create a parent-child link between two ADO work items.

    Args:
        parent_id: Work item ID of the parent.
        child_id: Work item ID of the child.
    """
    url = f"{_ORG_URL}/{_PROJECT}/_apis/wit/workitems/{child_id}?api-version={_ADO_API_VERSION}"
    patch = [
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": f"{_ORG_URL}/_apis/wit/workitems/{parent_id}",
            },
        }
    ]
    response = requests.patch(
        url,
        auth=_auth(),
        headers=_patch_headers(),
        json=patch,
        timeout=20,
    )
    response.raise_for_status()
    logger.info("Linked work item #%s as child of #%s", child_id, parent_id)
