"""
FORGE Stage 3 helper (Item #23, §2.2): selects and fetches the existing service's
files for an Enhancement request, to be seeded read-only into the Implementation
Coordinator's sandbox via Managed Agents session `resources[]`.

Deliberately NOT importing from ingestion_agent.py -- Item #23's spec explicitly
scopes "re-litigating Ingestion Agent (Stage 0a) itself" as out of scope, so the
noise-filtering constants below are a duplicated, adapted copy of that module's
own `_NOISE_DIR_SEGMENTS`/`_NOISE_FILENAMES`/`_NOISE_EXTENSIONS`/
`_MANIFEST_EXACT_BASENAMES`, not a shared import.

Budget shape is a deliberate DEVIATION from Ingestion Agent's own two-pass
selection, not a copy of it -- flagged explicitly here and in the Item #23
report-back, not silently decided. Ingestion Agent's ~60k-character budget
exists because its file contents go straight into an LLM prompt (real token
cost per character). Here, selected files are uploaded to the Files API and
mounted onto the sandbox filesystem for the coordinator/subagents to read
selectively with their own tools -- mounting itself carries no token cost, so
truncating an app to an arbitrary character budget risks handing subagents an
incomplete, unbuildable copy of a real production service for no real savings.
The actual hard constraint is the Managed Agents API's 999-file-resource cap
per session (see shared/managed-agents-environments.md -- Resources). Real
current services (REQ-2026-01: 99 tracked files, REQ-2026-02: 70, REQ-2026-03:
89, confirmed live via `git ls-tree`) are nowhere near that cap, so the
two-pass budget below is count-based, not character-based, and only truncates
when a service's filtered file count would actually approach the resource
ceiling.
"""

from __future__ import annotations

import logging

from core.agents.utils.github_helper import get_file_contents

logger = logging.getLogger(__name__)

# Same noise categories as ingestion_agent.py's own constants (duplicated
# deliberately -- see module docstring).
_NOISE_DIR_SEGMENTS = {"node_modules", "bin", "obj", ".next", "dist", "coverage", ".git"}
_NOISE_FILENAMES = {"package-lock.json", "yarn.lock", "tsconfig.tsbuildinfo"}
_NOISE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".ico", ".svg", ".woff", ".woff2"}
_MANIFEST_EXACT_BASENAMES = {
    "package.json", "tsconfig.json", "openapi.yaml", "Program.cs", "Startup.cs",
}

# Leaves comfortable headroom under the Managed Agents API's hard 999-file-
# resource-per-session ceiling. Not expected to bind for any current service
# (largest today is 99 files) -- exists as a real guard for a future large one,
# not a routine truncation path.
_MAX_SEED_FILES = 900


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


def _select_blobs(filtered_blobs: list[dict]) -> list[dict]:
    """
    Two-pass, count-based budget: if everything fits under _MAX_SEED_FILES,
    seed the whole filtered tree (the common case for every real service
    today). Otherwise fall back to manifests-in-full plus the largest
    remaining files by size, up to the cap -- the same "budget-conscious"
    shape Ingestion Agent established, adapted to a file-count ceiling
    instead of a character budget (see module docstring for why).
    """
    if len(filtered_blobs) <= _MAX_SEED_FILES:
        return filtered_blobs

    logger.warning(
        "Existing service has %d files after noise filtering -- exceeds the "
        "%d-file seed cap (headroom under the API's 999-resource-per-session "
        "limit). Falling back to manifests + largest remaining files by size.",
        len(filtered_blobs), _MAX_SEED_FILES,
    )
    manifests = [b for b in filtered_blobs if _is_manifest(b["path"])]
    others = sorted(
        (b for b in filtered_blobs if not _is_manifest(b["path"])),
        key=lambda b: b["size"],
        reverse=True,
    )
    selected = list(manifests)
    remaining_budget = _MAX_SEED_FILES - len(selected)
    selected.extend(others[: max(remaining_budget, 0)])
    return selected


def select_existing_service_files(blobs: list[dict]) -> dict[str, str]:
    """
    Given the full blob list for a services/<existing-service>/ prefix (from
    github_helper.get_repo_tree()), filter noise, apply the count-based
    budget, and fetch each selected file's content.

    Args:
        blobs: Non-empty list of {"path": str, "size": int} dicts, as returned
            by get_repo_tree(). Callers are responsible for the "empty tree ->
            existing service not found" check (Item #23 §2.1's Layer 2
            backstop) -- this function assumes a real, non-empty tree.

    Returns:
        Dict mapping the full monorepo-relative path (e.g.
        "services/REQ-2026-03/backend/Controllers/ShiftsController.cs") to its
        UTF-8 text content, for every selected file.
    """
    filtered = _filter_noise(blobs)
    selected = _select_blobs(filtered)
    logger.info(
        "Selected %d of %d file(s) (after noise filtering) to seed into the "
        "sandbox.", len(selected), len(filtered),
    )
    return {blob["path"]: get_file_contents(blob["path"], branch="main") for blob in selected}
