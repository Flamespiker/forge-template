"""
FORGE GitHub helper — cross-repo operations for FORGE workflows.

Auth approach: GitHub App installation token generated via PyJWT + raw requests.
Rationale: PyGithub is listed as a dependency for convenience in smoke tests, but the
core token-exchange logic uses PyJWT + requests directly so the auth flow is explicit
and easy to audit. GitHub App JWTs are short-lived (10 min) and scoped to the
installation on the target repo.

Required environment variables (see .env.example):
    FORGE_APP_ID          — numeric GitHub App ID
    FORGE_APP_PRIVATE_KEY — full PEM private key content
    FORGE_GITHUB_OWNER    — owner of the target repo (user or org)
    FORGE_TARGET_REPO     — name of the target monorepo (e.g. forge-demo-apps)
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
    owner = os.environ["FORGE_GITHUB_OWNER"]
    repo = os.environ["FORGE_TARGET_REPO"]
    return f"{_GITHUB_API}/repos/{owner}/{repo}"


def post_comment(issue_or_pr_number: int, body: str) -> dict:
    """
    Post a comment on an issue or pull request in the target repo.

    Args:
        issue_or_pr_number: The issue or PR number (GitHub uses the same endpoint for both).
        body: Markdown comment body.

    Returns:
        The created comment object from the GitHub API.
    """
    token = get_installation_token()
    url = f"{_repo_url()}/issues/{issue_or_pr_number}/comments"
    response = requests.post(
        url,
        headers=_auth_headers(token),
        json={"body": body},
        timeout=15,
    )
    response.raise_for_status()
    logger.info("Posted comment on #%s", issue_or_pr_number)
    return response.json()


def add_label(issue_or_pr_number: int, label: str) -> dict:
    """
    Add a label to an issue or pull request.

    Args:
        issue_or_pr_number: The issue or PR number.
        label: Label name to add (must already exist in the repo).

    Returns:
        The API response body.
    """
    token = get_installation_token()
    url = f"{_repo_url()}/issues/{issue_or_pr_number}/labels"
    response = requests.post(
        url,
        headers=_auth_headers(token),
        json={"labels": [label]},
        timeout=15,
    )
    response.raise_for_status()
    logger.info("Added label '%s' to #%s", label, issue_or_pr_number)
    return response.json()


def remove_label(issue_or_pr_number: int, label: str) -> None:
    """
    Remove a label from an issue or pull request.

    Args:
        issue_or_pr_number: The issue or PR number.
        label: Label name to remove.
    """
    token = get_installation_token()
    url = f"{_repo_url()}/issues/{issue_or_pr_number}/labels/{label}"
    response = requests.delete(url, headers=_auth_headers(token), timeout=15)
    # 404 means the label wasn't applied — treat as a no-op, not an error
    if response.status_code != 404:
        response.raise_for_status()
    logger.info("Removed label '%s' from #%s", label, issue_or_pr_number)


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
