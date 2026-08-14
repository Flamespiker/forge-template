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
    post_comment, get_issue, get_issue_comments, remove_label. The tracking issue
    lives in forge-template. In Actions, GITHUB_TOKEN is automatically available.
    For local smoke tests, set it to a PAT with repo scope on forge-template.

    add_label() is the one exception, on the App installation token instead (see
    its own docstring) -- GITHUB_TOKEN-authored actions never trigger a new
    Actions workflow run (GitHub's anti-recursion rule), which silently broke
    06-deploy.yml's label-driven trigger for every agent-applied qa-approved/
    security-approved. The App is installed on forge-template too (Phase 4 step
    4.8), under the same installation as forge-demo-apps, so no other change was
    needed to make this work.

Required environment variables (see .env.example):
    FORGE_APP_ID          — numeric GitHub App ID
    FORGE_APP_PRIVATE_KEY — full PEM private key content
    FORGE_GITHUB_OWNER    — owner of both repos (user or org)
    FORGE_TARGET_REPO     — name of the application monorepo (e.g. forge-demo-apps)
    FORGE_SOURCE_REPO     — name of the orchestration repo (default: forge-template)
    GITHUB_TOKEN          — workflow token or PAT for same-repo ops on forge-template
"""

from __future__ import annotations

import base64
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

    Uses GITHUB_TOKEN — same-repo operation on forge-template. (Note: the App IS
    now also installed on forge-template as of the Phase 4 step 4.8 retrofit --
    this docstring's original claim that it wasn't is stale. Left on GITHUB_TOKEN
    anyway since posting a comment triggers no downstream label-driven workflow,
    unlike add_label(), which was switched to the App token for exactly that
    reason -- see add_label()'s docstring.)

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


def get_issue(issue_number: int) -> dict:
    """
    Retrieve a tracking issue's own object (title, body, labels, state) from
    forge-template (the orchestration repo).

    Uses GITHUB_TOKEN — same-repo operation on forge-template. Needed starting
    with Phase 4 workflow wiring: guard clauses re-check that a triggering
    label is still actually present at job-run time (the "labeled" event can
    race with a near-simultaneous label removal), and the label-driven stages
    resolve the request ID from a prior agent comment rather than a new piece
    of persisted state — but before either of those, the workflow needs the
    issue's current label set at all, which no existing function returns.

    Args:
        issue_number: The issue number in forge-template.

    Returns:
        The issue object from the GitHub API. Includes "labels" (list of
        {"name": ...} dicts among other fields), "body", "title", "state".
    """
    url = f"{_source_repo_url()}/issues/{issue_number}"
    response = requests.get(url, headers=_github_token_headers(), timeout=15)
    response.raise_for_status()
    issue = response.json()
    logger.info("Retrieved forge-template issue #%s (state=%s)", issue_number, issue.get("state"))
    return issue


def get_issue_comments(issue_or_pr_number: int) -> list[dict]:
    """
    Retrieve all comments on a tracking issue or PR in forge-template (the
    orchestration repo), oldest first (GitHub's default ordering for this endpoint).

    Uses GITHUB_TOKEN — same-repo operation on forge-template.

    Args:
        issue_or_pr_number: The issue or PR number in forge-template.

    Returns:
        List of comment objects from the GitHub API. Each dict includes at least
        "id", "user" (with "login"), "body", and "created_at".
    """
    url = f"{_source_repo_url()}/issues/{issue_or_pr_number}/comments"
    response = requests.get(url, headers=_github_token_headers(), timeout=15)
    response.raise_for_status()
    comments = response.json()
    logger.info("Retrieved %d comment(s) from forge-template #%s", len(comments), issue_or_pr_number)
    return comments


def add_label(issue_or_pr_number: int, label: str) -> dict:
    """
    Add a label to a tracking issue or PR in forge-template (the orchestration repo).

    Uses the GitHub App installation token, NOT GITHUB_TOKEN (switched 2026-08-11).

    Why: GitHub Actions has a documented anti-recursion rule -- actions performed
    with the default GITHUB_TOKEN never trigger a NEW workflow run (with the
    exception of workflow_dispatch/repository_dispatch). qa_agent.py and
    security_agent.py both call this to apply qa-approved/security-approved,
    which 06-deploy.yml's `issues: types: [labeled]` trigger is supposed to react
    to -- but since those calls used GITHUB_TOKEN, that event never actually
    reached Actions. Confirmed via real run history on REQ-2026-02: the only
    successful 06-deploy.yml run ever was triggered by a label a HUMAN applied
    (Flamespiker, via a personal token) -- every agent-applied label, before and
    after, produced zero deploy runs. This was a silent, fully general bug
    affecting every future request that passes QA/Security without a manual
    label touch in between, not something specific to one run.

    The App installation token works here: the App is installed on
    forge-template too (Phase 4 step 4.8 retrofit), under the SAME installation
    as forge-demo-apps (confirmed empirically: GET .../forge-template/installation
    and GET .../forge-demo-apps/installation both resolve to installation id
    148876680) -- so get_installation_token() already returns a token valid for
    this repo with no changes needed there. App tokens are not subject to the
    GITHUB_TOKEN anti-recursion restriction, so this label add will correctly
    fire a real `issues.labeled` event.

    post_comment()/get_issue()/get_issue_comments()/remove_label() below are
    UNCHANGED and still use GITHUB_TOKEN -- none of them need to trigger a
    downstream label-driven workflow (posting a comment or removing a label
    triggers nothing; 06-deploy.yml is the only stage-trigger workflow gated on
    an agent-applied label rather than a human-applied one or a
    repository_dispatch), so there was no equivalent bug to fix in those, and no
    reason to touch their auth to keep this change minimal and isolated.

    Args:
        issue_or_pr_number: The issue or PR number in forge-template.
        label: Label name to add (must already exist in the repo).

    Returns:
        The API response body.
    """
    token = get_installation_token()
    url = f"{_source_repo_url()}/issues/{issue_or_pr_number}/labels"
    response = requests.post(
        url,
        headers=_auth_headers(token),
        json={"labels": [label]},
        timeout=15,
    )
    response.raise_for_status()
    logger.info("Added label '%s' to forge-template #%s (App token)", label, issue_or_pr_number)
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


def get_file_contents(path: str, branch: str = "main") -> str:
    """
    Read a file's content from the target monorepo (forge-demo-apps) at a given
    branch or ref, via the GitHub Contents API.

    Uses the GitHub App installation token — same cross-repo auth context as
    create_branch/commit_files/open_pr. Needed starting with the Design Agent
    (Stage 2), which reads requirements.md — an artifact the Requirements Agent
    committed to the monorepo, not something available in a local checkout of
    forge-template.

    Args:
        path:   Repo-relative file path in the monorepo, e.g.
                "docs/REQ-2026-01/requirements.md".
        branch: Branch or ref to read from (default "main").

    Returns:
        Decoded UTF-8 file content as a string.

    Raises:
        requests.HTTPError: If the file does not exist at that path/ref (404) or
                             the API call otherwise fails.
    """
    token = get_installation_token()
    url = f"{_repo_url()}/contents/{path}"
    response = requests.get(
        url,
        headers=_auth_headers(token),
        params={"ref": branch},
        timeout=15,
    )
    response.raise_for_status()
    content_b64 = response.json()["content"]
    content = base64.b64decode(content_b64).decode("utf-8")
    logger.info("Read file '%s' (ref=%s, %d chars) from monorepo", path, branch, len(content))
    return content


def post_pr_comment(pr_number: int, body: str) -> dict:
    """
    Post a comment on a pull request in the target monorepo (forge-demo-apps).

    Uses the GitHub App installation token — same cross-repo auth context as
    create_branch/commit_files/open_pr/get_file_contents. Needed starting with the
    QA Agent (Stage 4), which posts its test report on the feature PR in the
    monorepo, not on the FORGE tracking issue in forge-template (post_comment is
    same-repo-only, via GITHUB_TOKEN, and cannot reach forge-demo-apps).

    GitHub's REST API treats PRs as issues for the comments endpoint, so this is
    the same "/issues/{number}/comments" shape as post_comment() — just a
    different repo and a different token.

    Args:
        pr_number: The pull request number in forge-demo-apps.
        body: Markdown comment body.

    Returns:
        The created comment object from the GitHub API.
    """
    token = get_installation_token()
    url = f"{_repo_url()}/issues/{pr_number}/comments"
    response = requests.post(
        url,
        headers=_auth_headers(token),
        json={"body": body},
        timeout=15,
    )
    response.raise_for_status()
    logger.info("Posted comment on monorepo PR #%s", pr_number)
    return response.json()


def get_pr_comments(pr_number: int) -> list[dict]:
    """
    Retrieve all comments on a pull request in the target monorepo (forge-demo-apps),
    oldest first (GitHub's default ordering for this endpoint).

    Uses the GitHub App installation token — same cross-repo auth context as
    post_pr_comment(). Needed by the QA Agent to count its own prior comments on
    this PR (each marked with the `<!-- forge:agent-comment stage=qa ... -->`
    marker) as a stateless way to derive the current retry attempt number —
    ADR-0002 means no other persistent counter exists between runs.

    Args:
        pr_number: The pull request number in forge-demo-apps.

    Returns:
        List of comment objects from the GitHub API. Each dict includes at least
        "id", "user" (with "login"), "body", and "created_at".
    """
    token = get_installation_token()
    url = f"{_repo_url()}/issues/{pr_number}/comments"
    response = requests.get(url, headers=_auth_headers(token), timeout=15)
    response.raise_for_status()
    comments = response.json()
    logger.info("Retrieved %d comment(s) from monorepo PR #%s", len(comments), pr_number)
    return comments


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


def delete_files(
    branch_name: str,
    paths: list[str],
    commit_message: str,
) -> dict:
    """
    Delete one or more files from a branch in the monorepo via the Git Data API.

    Mirrors commit_files()'s tree/commit/ref-update sequence exactly, except
    each tree entry has sha=None -- the Git Trees API's documented way to
    remove a path from a tree relative to base_tree, rather than add/update it.

    Added for the REQ-2026-01/REQ-2026-02 dead-weight-CI-file cleanup pattern
    (Implementation Coordinator subagents generating unrequested, non-
    functional nested .github/workflows/*.yml files that GitHub never
    discovers outside the true repo root) -- no prior FORGE stage needed to
    delete a file from the monorepo before this.

    Args:
        branch_name:    Target branch (must already exist in the monorepo).
        paths:          Repo-relative file paths to remove.
        commit_message: Commit message string.

    Returns:
        The created commit object from the GitHub API (includes sha, html_url, etc.).
    """
    token = get_installation_token()
    headers = _auth_headers(token)
    base_url = _repo_url()

    ref_resp = requests.get(f"{base_url}/git/ref/heads/{branch_name}", headers=headers, timeout=15)
    ref_resp.raise_for_status()
    head_sha = ref_resp.json()["object"]["sha"]

    commit_resp = requests.get(f"{base_url}/git/commits/{head_sha}", headers=headers, timeout=15)
    commit_resp.raise_for_status()
    base_tree_sha = commit_resp.json()["tree"]["sha"]

    tree_items = [{"path": path, "mode": "100644", "type": "blob", "sha": None} for path in paths]

    tree_resp = requests.post(
        f"{base_url}/git/trees",
        headers=headers,
        json={"base_tree": base_tree_sha, "tree": tree_items},
        timeout=15,
    )
    tree_resp.raise_for_status()
    new_tree_sha = tree_resp.json()["sha"]

    new_commit_resp = requests.post(
        f"{base_url}/git/commits",
        headers=headers,
        json={"message": commit_message, "tree": new_tree_sha, "parents": [head_sha]},
        timeout=15,
    )
    new_commit_resp.raise_for_status()
    new_commit = new_commit_resp.json()
    new_commit_sha = new_commit["sha"]

    update_resp = requests.patch(
        f"{base_url}/git/refs/heads/{branch_name}",
        headers=headers,
        json={"sha": new_commit_sha},
        timeout=15,
    )
    update_resp.raise_for_status()

    logger.info(
        "Deleted %d file(s) from '%s' (SHA %s): %s",
        len(paths), branch_name, new_commit_sha[:8], commit_message,
    )
    return new_commit


def get_pr(pr_number: int) -> dict:
    """
    Retrieve a pull request object from the target monorepo (forge-demo-apps).

    Uses the GitHub App installation token — same cross-repo auth context as
    post_pr_comment()/get_pr_comments(). Needed by the Security Agent to resolve
    the PR's head commit SHA before creating inline review comments or a check
    run — both APIs require a commit SHA, and QA never needed one since it only
    posts a plain issue-style comment.

    Args:
        pr_number: The pull request number in forge-demo-apps.

    Returns:
        The pull request object from the GitHub API. Includes "head" (with
        "sha" and "ref") among other fields.
    """
    token = get_installation_token()
    url = f"{_repo_url()}/pulls/{pr_number}"
    response = requests.get(url, headers=_auth_headers(token), timeout=15)
    response.raise_for_status()
    pr = response.json()
    logger.info("Retrieved monorepo PR #%s (head SHA %s)", pr_number, pr["head"]["sha"][:8])
    return pr


def list_open_prs_by_head(branch_name: str) -> list[dict]:
    """
    List open PRs in the target monorepo (forge-demo-apps) whose head branch
    matches branch_name exactly. Uses the GitHub App installation token --
    same cross-repo auth context as get_pr(). Needed by resolve_feature_pr()
    to find the *currently* open feature PR, rather than trusting a
    potentially-stale comment reference.
    """
    owner = os.environ["FORGE_GITHUB_OWNER"]
    token = get_installation_token()
    url = f"{_repo_url()}/pulls"
    params = {"state": "open", "head": f"{owner}:{branch_name}"}
    response = requests.get(url, headers=_auth_headers(token), params=params, timeout=15)
    response.raise_for_status()
    prs: list[dict] = response.json()
    logger.info("Found %d open PR(s) with head '%s'", len(prs), branch_name)
    return prs


def create_check_run(
    head_sha: str,
    name: str,
    conclusion: str,
    title: str,
    summary: str,
) -> dict:
    """
    Create a completed check run on a commit in the target monorepo (forge-demo-apps).

    Uses the GitHub App installation token with the App's Checks: Read & Write
    permission (step 2.1). Needed by the Security Agent (Document 2 §4.7): a
    Critical finding sets a failing check run that blocks merge via the
    branch-protection required-status-check rule ("security-check", Build Plan
    4.8), independent of any human action or label. A clean scan still creates
    a passing check run — the branch protection rule waits on this specific
    check name resolving, not just the label.

    Args:
        head_sha:   The commit SHA to attach the check run to (the PR's head SHA).
        name:       Check run name (must match the required-status-check name
                    in branch protection — "security-check").
        conclusion: One of "success", "failure", "neutral". FORGE only ever
                    uses these three — no in_progress/queued states, since this
                    is always called after the scan has already completed.
        title:      Short check run title.
        summary:    Markdown summary body (shown in the PR checks tab).

    Returns:
        The created check run object from the GitHub API.
    """
    if conclusion not in ("success", "failure", "neutral"):
        raise ValueError(f"Unsupported check run conclusion: {conclusion!r}")
    token = get_installation_token()
    url = f"{_repo_url()}/check-runs"
    response = requests.post(
        url,
        headers=_auth_headers(token),
        json={
            "name": name,
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {"title": title, "summary": summary},
        },
        timeout=15,
    )
    response.raise_for_status()
    check_run = response.json()
    logger.info("Created check run '%s' (conclusion=%s) on commit %s", name, conclusion, head_sha[:8])
    return check_run


def create_review_with_comments(
    pr_number: int,
    commit_id: str,
    comments: list[dict],
    body: str = "",
) -> dict:
    """
    Post a single PR review carrying one or more inline (file+line) comments,
    in one API call, on the target monorepo (forge-demo-apps).

    Uses the GitHub App installation token. Needed by the Security Agent
    (Document 2 §4.7 / Document 7: "severity-tagged inline PR comments").

    GitHub's Reviews API is atomic: if ANY comment's path/line isn't part of
    the PR's diff, the ENTIRE review call fails with a 422 and no comments are
    posted. security_agent.py's post_findings() retries individually via
    create_single_review_comment() when this happens, so one bad line
    reference doesn't silently drop every other legitimate finding.

    Args:
        pr_number: The pull request number in forge-demo-apps.
        commit_id: The commit SHA the comments are anchored to (PR's head SHA).
        comments:  List of {"path": str, "line": int, "body": str} dicts.
                   Always anchored to the "RIGHT" (new) side of the diff —
                   security findings are always about code as it exists on
                   the feature branch, never the base branch.
        body:      Optional overall review summary body.

    Returns:
        The created review object from the GitHub API.

    Raises:
        requests.HTTPError: On any API failure, including the 422 diff-mismatch
                             case described above — the caller handles fallback.
    """
    token = get_installation_token()
    url = f"{_repo_url()}/pulls/{pr_number}/reviews"
    payload_comments = [
        {"path": c["path"], "line": c["line"], "side": "RIGHT", "body": c["body"]}
        for c in comments
    ]
    response = requests.post(
        url,
        headers=_auth_headers(token),
        json={"commit_id": commit_id, "body": body, "event": "COMMENT", "comments": payload_comments},
        timeout=30,
    )
    response.raise_for_status()
    review = response.json()
    logger.info("Posted review with %d inline comment(s) on monorepo PR #%s", len(comments), pr_number)
    return review


def create_single_review_comment(
    pr_number: int,
    commit_id: str,
    path: str,
    line: int,
    body: str,
) -> dict:
    """
    Post one inline PR review comment. Fallback path when a batch review via
    create_review_with_comments() fails atomically because one comment in the
    batch had a path/line outside the diff.

    Uses the GitHub App installation token.

    Args:
        pr_number: The pull request number in forge-demo-apps.
        commit_id: The commit SHA the comment is anchored to.
        path:      File path (repo-relative).
        line:      Line number on the RIGHT (new) side of the diff.
        body:      Comment Markdown body.

    Returns:
        The created review comment object from the GitHub API.

    Raises:
        requests.HTTPError: If this specific path/line still isn't part of the
                             diff (422) — the caller catches this per-comment
                             and falls back further to a plain PR comment.
    """
    token = get_installation_token()
    url = f"{_repo_url()}/pulls/{pr_number}/comments"
    response = requests.post(
        url,
        headers=_auth_headers(token),
        json={"commit_id": commit_id, "path": path, "line": line, "side": "RIGHT", "body": body},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()
