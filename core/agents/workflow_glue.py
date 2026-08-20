"""
FORGE Workflow Glue — Phase 4 orchestration-only helpers with no equivalent in
any stage agent, because no stage agent needed them: they exist purely to let
a GitHub Actions workflow step resolve a value it needs before it can invoke
the next stage script, and all write their result to $GITHUB_OUTPUT so the
calling workflow step can read `steps.<id>.outputs.<name>`.

Four subcommands:

  download-issue-attachment --issue-number N --output PATH [--extension .xlsx]
      Finds the first attachment link matching --extension in a tracking
      issue's body (checked first) or comments (checked in order if the body
      has none), downloads it, writes it to --output. Handles both GitHub
      attachment URL shapes: the classic "github.com/<owner>/<repo>/files/.."
      and the newer "github.com/user-attachments/files/..". Needed by
      00-intake.yml (the BA's original upload) and 01-requirements.yml (same
      spreadsheet, re-read for the Requirements Agent).

  resolve-request-id --issue-number N
      Scans every comment on the tracking issue for the
      "<!-- forge:agent-comment stage=... request_id=<id> ... -->" marker
      every stage agent already writes (see intake_agent.py through
      deploy_agent.py), and returns the first one found. One tracking issue
      maps to exactly one request for the life of that issue, so any prior
      stage's marker carries the same value. Needed by every stage from
      01-requirements.yml onward -- only 00-intake.yml derives request_id
      itself (from the spreadsheet's own Request ID field).

  resolve-feature-pr --issue-number N
      Resolves request_id via resolve-request-id, then asks the GitHub API
      directly for the currently open PR on feature/<request_id> in
      forge-demo-apps (implementation_coordinator.py's own branch-naming
      convention). Returns that PR's number and head commit SHA. Needed by
      06-deploy.yml: the qa-approved/security-approved labels live on the
      tracking issue, but deploy_agent.py needs the *feature PR's* number and
      head commit SHA in forge-demo-apps, neither of which the label event
      carries. Deliberately does NOT anchor to the original Implementation
      Coordinator comment -- that went stale the moment a follow-up feature
      PR was opened on the same tracking issue (e.g. a post-implementation
      fix/descope), since the comment always points at the *first* PR ever
      opened, not the currently open one. If no PR is found on that branch
      (an ad hoc fix PR, e.g. feature/fix-<description>, per CLAUDE.md's
      standing branch-naming convention), falls back to scanning every open
      PR's body for a "Related FORGE tracking issue: owner/repo#N" line
      matching this issue -- confirmed necessary live on PR #22.

  resolve-tracking-issue --pr-number N
      The reverse of resolve-feature-pr: given a forge-demo-apps PR number
      (from notify-forge.yml's repository_dispatch payload), finds the
      forge-template tracking issue number by reading the PR body's own
      "Related FORGE tracking issue: <owner>/<repo>#N" line. Needed by
      04-qa.yml/05-security.yml, which only ever learn about a PR number/SHA/
      branch from the dispatch payload -- never the tracking issue number.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys

import requests

from core.agents.utils.github_helper import (
    _github_token_headers,
    get_issue,
    get_issue_comments,
    get_pr,
    list_open_prs,
    list_open_prs_by_head,
)

logger = logging.getLogger(__name__)

_ATTACHMENT_URL_RE = re.compile(
    r"https://github\.com/(?:[^/\s]+/[^/\s]+/files|user-attachments/files)/\d+/[^\s)\]]+"
)
_REQUEST_ID_MARKER_RE = re.compile(r"forge:agent-comment\b[^>]*\brequest_id=(\S+?)(?=\s|-->)")


def _write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    print(f"{name}={value}")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def download_issue_attachment(issue_number: int, output_path: str, extension: str) -> str:
    issue = get_issue(issue_number)
    candidates = [issue.get("body") or ""]
    candidates.extend(c["body"] for c in get_issue_comments(issue_number))

    url: str | None = None
    for text in candidates:
        for match in _ATTACHMENT_URL_RE.findall(text):
            if match.lower().endswith(extension.lower()):
                url = match
                break
        if url:
            break

    if url is None:
        raise ValueError(
            f"No attachment matching '{extension}' found in issue #{issue_number}'s "
            "body or comments. The BA must attach the intake spreadsheet directly "
            "to the tracking issue (drag-and-drop, not a link to an external file)."
        )

    response = requests.get(
        url, headers=_github_token_headers(), timeout=30, allow_redirects=True
    )
    response.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(response.content)
    logger.info("Downloaded attachment from issue #%s to %s (%d bytes)", issue_number, output_path, len(response.content))
    return output_path


def resolve_request_id(issue_number: int) -> str:
    for comment in get_issue_comments(issue_number):
        match = _REQUEST_ID_MARKER_RE.search(comment["body"])
        if match:
            return match.group(1)
    raise ValueError(
        f"No forge:agent-comment marker with a request_id found on issue "
        f"#{issue_number} -- has any stage agent run on this issue yet?"
    )


def _parse_tracking_issue_number(pr_body: str | None) -> int | None:
    """
    Extracts the FORGE tracking issue number from a forge-demo-apps PR body's
    "Related FORGE tracking issue: <owner>/<repo>#N" line (written identically
    by design_agent.py and implementation_coordinator.py, and required on ad
    hoc PRs per Open Item #15). Shared by resolve_tracking_issue() and
    resolve_feature_pr()'s tracking-issue-body fallback so this line's parsing
    rule lives in exactly one place, not two independently-maintained regexes.

    Returns None if no match -- either the PR wasn't opened by a FORGE stage
    agent, or (for an ad hoc PR) the required line is simply missing (Item #15).
    """
    source_repo = os.environ.get("FORGE_SOURCE_REPO", "forge-template")
    pattern = re.compile(re.escape(source_repo) + r"#(\d+)")
    match = pattern.search(pr_body or "")
    return int(match.group(1)) if match else None


def resolve_tracking_issue(pr_number: int) -> int:
    """
    Returns the forge-template tracking issue number for a forge-demo-apps PR,
    by reading the PR body's "Related FORGE tracking issue: <owner>/<repo>#N"
    line (written identically by design_agent.py and implementation_
    coordinator.py). Needed by 04-qa.yml/05-security.yml: the
    repository_dispatch payload from notify-forge.yml only carries the PR
    number/SHA/branch from forge-demo-apps -- the tracking issue lives in a
    different repo the dispatch payload never mentions.
    """
    pr = get_pr(pr_number)
    issue_number = _parse_tracking_issue_number(pr.get("body"))
    if issue_number is None:
        source_repo = os.environ.get("FORGE_SOURCE_REPO", "forge-template")
        raise ValueError(
            f"No 'Related FORGE tracking issue: .../{source_repo}#N' reference found "
            f"in PR #{pr_number}'s body -- was it opened by a FORGE stage agent?"
        )
    return issue_number


def resolve_feature_pr(issue_number: int) -> tuple[int, str]:
    """
    Returns (pr_number, head_sha) for the *currently open* feature PR tied
    to this tracking issue. Resolves request_id via the same marker-based
    resolve_request_id() every other stage trusts (stable for the life of
    the issue).

    Resolution order:
      1. Look for an open PR on branch feature/<request_id> -- the original
         Implementation Coordinator's own branch-naming convention -- via
         list_open_prs_by_head(). Tried first, zero behavior change from
         before this fallback existed: this is still the common case.
      2. If Step 1 finds nothing, fall back to scanning every open PR in the
         monorepo for one whose body references this tracking issue (the same
         "Related FORGE tracking issue: owner/repo#N" line resolve_tracking_
         issue() reads). Needed for ad hoc fix PRs (e.g. feature/fix-<desc>,
         per CLAUDE.md's standing branch-naming convention) whose branch name
         doesn't match feature/<request_id> literally -- confirmed live: PR
         #22 (the SHIFT_ALREADY_CLAIMED wording fix) hit exactly this gap.

    Raises ValueError on zero or more than one match at whichever step
    resolves it -- never silently guesses which PR to deploy. Item #15's
    separate gap (an ad hoc PR missing the tracking-issue body line entirely)
    is not handled here: Step 2 correctly finds nothing in that case, and the
    existing manual remediation (editing the PR body) still applies.
    """
    request_id = resolve_request_id(issue_number)
    branch_name = f"feature/{request_id}"
    prs = list_open_prs_by_head(branch_name)

    if len(prs) == 1:
        pr = prs[0]
        return pr["number"], pr["head"]["sha"]
    if len(prs) > 1:
        raise ValueError(
            f"Found {len(prs)} open PRs on branch '{branch_name}' for issue "
            f"#{issue_number} -- expected exactly one. Refusing to guess which "
            "one to deploy."
        )

    # Step 1 found nothing -- fall back to the tracking-issue-body match.
    candidates = [
        pr for pr in list_open_prs()
        if _parse_tracking_issue_number(pr.get("body")) == issue_number
    ]

    if len(candidates) == 1:
        pr = candidates[0]
        return pr["number"], pr["head"]["sha"]
    if len(candidates) > 1:
        raise ValueError(
            f"Found {len(candidates)} open PRs referencing tracking issue "
            f"#{issue_number} in their body (none on branch '{branch_name}') -- "
            "expected exactly one. Refusing to guess which one to deploy."
        )
    raise ValueError(
        f"No open PR found on branch '{branch_name}' for issue #{issue_number}, "
        "and no open PR's body references this tracking issue either -- has "
        "Stage 3 run yet, has the feature PR already been merged/closed without "
        "a new one being opened, or (for an ad hoc fix PR) is the 'Related FORGE "
        "tracking issue: owner/repo#N' line missing from the PR body (Open Item #15)?"
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE Phase 4 workflow glue")
    subparsers = parser.add_subparsers(dest="action", required=True)

    p_attach = subparsers.add_parser("download-issue-attachment")
    p_attach.add_argument("--issue-number", required=True, type=int)
    p_attach.add_argument("--output", required=True)
    p_attach.add_argument("--extension", default=".xlsx")

    p_reqid = subparsers.add_parser("resolve-request-id")
    p_reqid.add_argument("--issue-number", required=True, type=int)

    p_pr = subparsers.add_parser("resolve-feature-pr")
    p_pr.add_argument("--issue-number", required=True, type=int)

    p_issue = subparsers.add_parser("resolve-tracking-issue")
    p_issue.add_argument("--pr-number", required=True, type=int)

    args = parser.parse_args()

    try:
        if args.action == "download-issue-attachment":
            download_issue_attachment(args.issue_number, args.output, args.extension)
        elif args.action == "resolve-request-id":
            _write_output("request_id", resolve_request_id(args.issue_number))
        elif args.action == "resolve-feature-pr":
            pr_number, head_sha = resolve_feature_pr(args.issue_number)
            _write_output("pr_number", str(pr_number))
            _write_output("head_sha", head_sha)
        elif args.action == "resolve-tracking-issue":
            _write_output("issue_number", str(resolve_tracking_issue(args.pr_number)))
    except Exception:
        logger.exception("workflow_glue action '%s' failed", args.action)
        sys.exit(1)


if __name__ == "__main__":
    main()
