"""
Smoke test — github_helper.py

Exercises the real GitHub API using stored credentials.
Run manually from the repo root:
    python -m core.agents.utils.smoke_tests.smoke_github

Requires a .env file with:
    FORGE_APP_ID, FORGE_APP_PRIVATE_KEY, FORGE_GITHUB_OWNER,
    FORGE_TARGET_REPO, FORGE_SOURCE_REPO, GITHUB_TOKEN

Two repos are exercised:
  forge-template  — post_comment, add_label, remove_label (GITHUB_TOKEN)
                    Requires issue #1 and label "forge-smoke-test" to exist there.
  forge-demo-apps — create_branch, commit_files, open_pr (App installation token)

The test branch and PR are cleaned up after the run.
"""

from __future__ import annotations

import sys
import traceback

from dotenv import load_dotenv

load_dotenv()

from core.agents.utils import github_helper as gh  # noqa: E402

PASS = "[PASS]"
FAIL = "[FAIL]"
results: list[tuple[str, bool]] = []


def run(label: str, fn):
    try:
        result = fn()
        print(f"{PASS} {label}")
        if result:
            print(f"       -> {result}")
        results.append((label, True))
        return result
    except Exception as exc:
        print(f"{FAIL} {label}: {exc}")
        traceback.print_exc()
        results.append((label, False))
        return None


def main():
    print("=== GitHub Helper Smoke Test ===\n")

    token = run("get_installation_token()", gh.get_installation_token)
    if not token:
        print("\nCannot proceed — token generation failed.")
        sys.exit(1)

    # post_comment — requires issue #1 to exist in forge-demo-apps
    run(
        "post_comment(1, 'FORGE smoke test — ignore')",
        lambda: gh.post_comment(1, "FORGE smoke test — ignore this comment."),
    )

    # add_label — requires a label named "forge-smoke-test" to exist in the repo
    # Create it manually once via the GitHub UI or API if it doesn't exist
    run(
        "add_label(1, 'forge-smoke-test')",
        lambda: gh.add_label(1, "forge-smoke-test"),
    )

    run(
        "remove_label(1, 'forge-smoke-test')",
        lambda: gh.remove_label(1, "forge-smoke-test"),
    )

    # create_branch — creates a throwaway branch in forge-demo-apps
    branch_name = "forge-smoke-test-branch"
    branch = run(
        f"create_branch('{branch_name}', 'main')",
        lambda: gh.create_branch(branch_name, "main"),
    )

    # commit_files — write a real file so the branch is ahead of main (required for open_pr)
    pr = None
    if branch:
        run(
            f"commit_files('{branch_name}', {{smoke file}}, ...)",
            lambda: gh.commit_files(
                branch_name=branch_name,
                files={"forge-smoke-test.txt": "FORGE smoke test — safe to delete.\n"},
                commit_message="chore: FORGE smoke test commit — safe to delete",
            ),
        )

        # get_file_contents — read back the file we just committed, verify round-trip
        run(
            f"get_file_contents('forge-smoke-test.txt', '{branch_name}')",
            lambda: gh.get_file_contents("forge-smoke-test.txt", branch=branch_name),
        )

        # open_pr — branch now has a real commit ahead of main
        pr = run(
            "open_pr (draft PR on non-empty branch)",
            lambda: gh.open_pr(
                title="FORGE smoke test PR — delete me",
                body="This PR was created by the FORGE smoke test. Safe to close.",
                head_branch=branch_name,
                base_branch="main",
                draft=True,
            ),
        )

    # Cleanup — close the PR and delete the branch
    token = gh.get_installation_token()
    import requests as _requests
    owner = gh._repo_url().split("/repos/")[1].split("/")[0]
    repo = gh._repo_url().split("/repos/")[1].split("/")[1]
    if pr:
        pr_num = pr.get("number")
        _requests.patch(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}",
            headers=gh._auth_headers(token),
            json={"state": "closed"},
            timeout=15,
        )
        print(f"       Closed PR #{pr_num}")
    _requests.delete(
        f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{branch_name}",
        headers=gh._auth_headers(token),
        timeout=15,
    )
    print(f"       Deleted branch '{branch_name}'")

    print("\n=== Results ===")
    passed = sum(1 for _, ok in results if ok)
    for label, ok in results:
        print(f"  {'OK' if ok else 'XX'} {label}")
    print(f"\n{passed}/{len(results)} checks passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
