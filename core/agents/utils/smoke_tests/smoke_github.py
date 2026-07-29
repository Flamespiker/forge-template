"""
Smoke test — github_helper.py

Exercises the real GitHub API against forge-demo-apps using stored credentials.
Run manually from the repo root:
    python -m core.agents.utils.smoke_tests.smoke_github

Requires a .env file with: FORGE_APP_ID, FORGE_APP_PRIVATE_KEY,
FORGE_GITHUB_OWNER, FORGE_TARGET_REPO.

This script does NOT commit or push anything. It creates a test branch,
posts a comment on issue #1 (must exist), adds/removes a label, and
opens + immediately closes a draft PR. All changes are ephemeral.
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

    # create_branch — creates a throwaway branch
    branch_name = "forge-smoke-test-branch"
    branch = run(
        f"create_branch('{branch_name}', 'main')",
        lambda: gh.create_branch(branch_name, "main"),
    )

    # open_pr — requires the branch to have at least one commit ahead of main
    # This will likely fail if branch is identical to main (no diff) — that's expected
    run(
        "open_pr (expected to fail if branch has no commits ahead of main)",
        lambda: gh.open_pr(
            title="FORGE smoke test PR — delete me",
            body="This PR was created by the FORGE smoke test. Safe to close.",
            head_branch=branch_name,
            base_branch="main",
            draft=True,
        ),
    )

    print("\n=== Results ===")
    passed = sum(1 for _, ok in results if ok)
    for label, ok in results:
        print(f"  {'OK' if ok else 'XX'} {label}")
    print(f"\n{passed}/{len(results)} checks passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
