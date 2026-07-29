"""
FORGE GitHub helper — cross-repo operations for FORGE workflows.

Two auth contexts, two repo targets:

  GitHub App installation token (PyJWT + raw requests):
    Used for cross-repo operations into the application monorepo (forge-demo-apps):
    create_branch, open_pr, commit_files. The App is installed only on the monorepo,
    so these calls must use the App token. JWTs are short-lived (10 min) and
    installation tokens are scoped to that repo.

  GITHUB_TOKEN (workflow's own token):
    Used for same-repo operations on forge-template (the orchestration repo):
    post_comment, add_label, remove_label. The tracking issue lives in forge-template.
    In Actions, GITHUB_TOKEN is automatically available. For local smoke tests, set it
    to a PAT with repo scope on forge-template.

Required environment variables (see .env.example):
    FORGE_APP_ID          — numeric GitHub App ID
    FORGE_APP_PRIVATE_KEY — full PEM private key content
    FORGE_GITHUB_OWNER    — owner of both repos (user or org)
    FORGE_TARGET_REPO     — name of the application monorepo (e.g. forge-demo-apps)
    FORGE_SOURCE_REPO     — name of the orchestration repo (default: forge-template)
    GITHUB_TOKEN          — workflow token or PAT for same-repo ops on forge-template
"""

from __future__ import annotations

import os
import time
import logging

import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_JWT_EXPIRY_SECONDS = 600  # GitHub's max is 10 minutes


def _build_app_jwt() -> str:
    """Generate a signed JWT authenticating as the GitHub App (not an installation)."""
    app_id = os.environ["FORGE_APP_ID"]
    private_key = os.environ["FORGE_APP_PRIVATE_KEY"]

    now = int(time.time())
    payload = {
        "iat": now - 60,  # issued-at skewed back 60 s to account for clock drift
        "exp": now + _JWT_EXPIRY_SECONDS,
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def _get_installation_id(app_jwt: str) -> int:
    """Look up the installation ID for the target repo."""
    owner = os.environ["FORGE_GITHUB_OWNER"]
    repo = os.environ["FORGE_TARGET_REPO"]
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/installation"
    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["id"]


def get_installation_token() -> str:
    """
    Generate a short-lived GitHub App installation token scoped to the target repo.

    This token grants the permissions configured on the App installation
    (Contents R/W, Pull requests R/W, Issues R/W, Checks R/W, Metadata R).

    Returns:
        The installation access token string.
    """
    app_jwt = _build_app_jwt()
    installation_id = _get_installation_id(app_jwt)
    url = f"{_GITHUB_API}/app/installations/{installation_id}/access_tokens"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
        timeout=15,
    )
    response.raise_for_status()
    token: str = response.json()["token"]
    logger.debug("GitHub App installation token generated for installation %s", installation_id)
    return token


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _repo_url() -> str:
    """Monorepo (forge-demo-apps) — App installation token required."""
    owner = os.environ["FORGE_GITHUB_OWNER"]
    repo = os.environ["FORGE_TARGET_REPO"]
    return f"{_GITHUB_API}/repos/{owner}/{repo}"


def _source_repo_url() -> str:
    """Orchestration repo (forge-template) — GITHUB_TOKEN required."""
    owner = os.environ["FORGE_GITHUB_OWNER"]
    repo = os.environ.get("FORGE_SOURCE_REPO", "forge-template")
    return f"{_GITHUB_API}/repos/{owner}/{repo}"


def _github_token_headers() -> dict[str, str]:
    """
    Auth headers using GITHUB_TOKEN for same-repo ops on forge-template.

    IN PRODUCTION (GitHub Actions): GITHUB_TOKEN is automatically injected by the
    Actions runtime for every workflow run — it is ephemeral, scoped to that run, and
    requires no secret configuration whatsoever. Do NOT add GITHUB_TOKEN as a GitHub
    Actions secret in Phase 4; doing so would be redundant and could shadow the
    automatic token with a stale or overly-broad one.

    LOCAL DEV ONLY: set GITHUB_TOKEN in .env to a fine-grained PAT scoped to
    forge-template with Issues: Read and write. This is the only context where a
    stored value is needed.
    """
    token = os.environ["GITHUB_TOKEN"]
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def post_comment(issue_or_pr_number: int, body: str) -> dict:
    """
    Post a comment on a tracking issue or PR in forge-template (the orchestration repo).

    Uses GITHUB_TOKEN — same-repo operation; the GitHub App is not installed on
    forge-template so the App token cannot be used here.

    Args:
        issue_or_pr_number: The issue or PR number in forge-template.
        body: Markdown comment body.

    Returns:
        The created comment object from the GitHub API.
    """
    url = f"{_source_repo_url()}/issues/{issue_or_pr_number}/comments"
    response = requests.post(
        url,
        headers=_github_token_headers(),
        json={"body": body},
        timeout=15,
    )
    response.raise_for_status()
    logger.info("Posted comment on forge-template #%s", issue_or_pr_number)
    return response.json()


def add_label(issue_or_pr_number: int, label: str) -> dict:
    """
    Add a label to a tracking issue or PR in forge-template (the orchestration repo).

    Uses GITHUB_TOKEN — same-repo operation on forge-template.

    Args:
        issue_or_pr_number: The issue or PR number in forge-template.
        label: Label name to add (must already exist in the repo).

    Returns:
        The API response body.
    """
    url = f"{_source_repo_url()}/issues/{issue_or_pr_number}/labels"
    response = requests.post(
        url,
        headers=_github_token_headers(),
        json={"labels": [label]},
        timeout=15,
    )
    response.raise_for_status()
    logger.info("Added label '%s' to forge-template #%s", label, issue_or_pr_number)
    return response.json()


def remove_label(issue_or_pr_number: int, label: str) -> None:
    """
    Remove a label from a tracking issue or PR in forge-template (the orchestration repo).

    Uses GITHUB_TOKEN — same-repo operation on forge-template.

    Args:
        issue_or_pr_number: The issue or PR number in forge-template.
        label: Label name to remove.
    """
    url = f"{_source_repo_url()}/issues/{issue_or_pr_number}/labels/{label}"
    response = requests.delete(url, headers=_github_token_headers(), timeout=15)
    # 404 means the label wasn't applied — treat as a no-op, not an error
    if response.status_code != 404:
        response.raise_for_status()
    logger.info("Removed label '%s' from forge-template #%s", label, issue_or_pr_number)


def create_branch(branch_name: str, from_branch: str) -> dict:
    """
    Create a new branch in the target repo from an existing branch.

    Args:
        branch_name: Name for the new branch (e.g. "feature/req-0042").
        from_branch: The branch to branch from (e.g. "main").

    Returns:
        The created ref object from the GitHub API.
    """
    token = get_installation_token()
    base_url = _repo_url()

    # Resolve the SHA of the source branch tip
    ref_response = requests.get(
        f"{base_url}/git/ref/heads/{from_branch}",
        headers=_auth_headers(token),
        timeout=15,
    )
    ref_response.raise_for_status()
    sha = ref_response.json()["object"]["sha"]

    # Create the new ref
    create_response = requests.post(
        f"{base_url}/git/refs",
        headers=_auth_headers(token),
        json={"ref": f"refs/heads/{branch_name}", "sha": sha},
        timeout=15,
    )
    create_response.raise_for_status()
    logger.info("Created branch '%s' from '%s' (SHA %s)", branch_name, from_branch, sha[:8])
    return create_response.json()


def open_pr(
    title: str,
    body: str,
    head_branch: str,
    base_branch: str,
    draft: bool = True,
) -> dict:
    """
    Open a pull request in the target repo.

    Per ADR-0009: agents open PRs; humans approve and merge. No agent ever merges its own PR.

    Args:
        title: PR title.
        body: PR description (Markdown). Include the FORGE tracking issue cross-link here.
        head_branch: The branch containing the changes.
        base_branch: The branch to merge into (typically "main").
        draft: Whether to open as a draft PR (default True — all agent-opened PRs start as draft).

    Returns:
        The created pull request object from the GitHub API.
    """
    token = get_installation_token()
    url = f"{_repo_url()}/pulls"
    response = requests.post(
        url,
        headers=_auth_headers(token),
        json={
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
            "draft": draft,
        },
        timeout=15,
    )
    response.raise_for_status()
    pr = response.json()
    logger.info("Opened %s PR #%s: %s", "draft" if draft else "ready", pr["number"], title)
    return pr


def commit_files(
    branch_name: str,
    files: dict[str, str],
    commit_message: str,
) -> dict:
    """
    Write one or more files to a branch in the monorepo via the Git Data API and
    create a signed commit. Used by Stage 3 subagents to persist generated code.

    The branch must already exist (call create_branch() first if needed).
    Files are written atomically as a single commit — all blobs are created, a new
    tree is assembled on top of the branch's current tree, and the branch ref is
    fast-forwarded to the new commit.

    Uses the GitHub App installation token (cross-repo write into forge-demo-apps).

    Args:
        branch_name:    Target branch (must already exist in the monorepo).
        files:          Dict mapping repo-relative file path → UTF-8 file content.
                        Example: {"services/auth/src/main.py": "# generated code"}
        commit_message: Commit message string.

    Returns:
        The created commit object from the GitHub API (includes sha, html_url, etc.).
    """
    token = get_installation_token()
    headers = _auth_headers(token)
    base_url = _repo_url()

    # 1. Resolve the current HEAD SHA for the branch.
    ref_resp = requests.get(
        f"{base_url}/git/ref/heads/{branch_name}",
        headers=headers,
        timeout=15,
    )
    ref_resp.raise_for_status()
    head_sha = ref_resp.json()["object"]["sha"]

    # 2. Get the base tree SHA from the current commit.
    commit_resp = requests.get(
        f"{base_url}/git/commits/{head_sha}",
        headers=headers,
        timeout=15,
    )
    commit_resp.raise_for_status()
    base_tree_sha = commit_resp.json()["tree"]["sha"]

    # 3. Create a blob for each file.
    tree_items = []
    for path, content in files.items():
        blob_resp = requests.post(
            f"{base_url}/git/blobs",
            headers=headers,
            json={"content": content, "encoding": "utf-8"},
            timeout=15,
        )
        blob_resp.raise_for_status()
        tree_items.append({
            "path": path,
            "mode": "100644",  # regular file
            "type": "blob",
            "sha": blob_resp.json()["sha"],
        })

    # 4. Create a new tree on top of the existing tree.
    tree_resp = requests.post(
        f"{base_url}/git/trees",
        headers=headers,
        json={"base_tree": base_tree_sha, "tree": tree_items},
        timeout=15,
    )
    tree_resp.raise_for_status()
    new_tree_sha = tree_resp.json()["sha"]

    # 5. Create the commit.
    new_commit_resp = requests.post(
        f"{base_url}/git/commits",
        headers=headers,
        json={
            "message": commit_message,
            "tree": new_tree_sha,
            "parents": [head_sha],
        },
        timeout=15,
    )
    new_commit_resp.raise_for_status()
    new_commit = new_commit_resp.json()
    new_commit_sha = new_commit["sha"]

    # 6. Fast-forward the branch ref to the new commit.
    update_resp = requests.patch(
        f"{base_url}/git/refs/heads/{branch_name}",
        headers=headers,
        json={"sha": new_commit_sha},
        timeout=15,
    )
    update_resp.raise_for_status()

    logger.info(
        "Committed %d file(s) to '%s' (SHA %s): %s",
        len(files),
        branch_name,
        new_commit_sha[:8],
        commit_message,
    )
    return new_commit
