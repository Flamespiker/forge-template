# FORGE — Deploy Agent: `resolve_feature_pr()` Ad Hoc Fix-PR Resolution: Spec for Claude Code

**Prepared:** 2026-08-20 (Claude.ai)
**For:** Claude Code CLI session against `forge-template` (no `forge-demo-apps` app-code changes required — this is a `workflow_glue.py` bug, not an application bug)
**Context:** Open Item #17. `06-deploy.yml` calls `workflow_glue.py`'s `resolve_feature_pr()`, which looks for an open PR on branch `feature/<request_id>` literally. Confirmed twice failing on ad hoc fix PRs (manual verification in v62, live automated failure on PR #22's merge: `ValueError: No open PR found on branch 'feature/REQ-2026-03'...`) even once both `qa-approved`/`security-approved` are genuinely present. Design direction (Option A below) decided this session — generalize resolution to the tracking-issue reference, mirroring `resolve_tracking_issue()`'s existing approach.

**Standing conventions to follow (per `CLAUDE.md` / context doc):**
- Verify against the live file, not this spec — `grep -n "resolve_feature_pr\|resolve_tracking_issue\|list_open_prs_by_head" core/agents/workflow_glue.py core/agents/github_helper.py` before editing anything. Function names/signatures below are from CLAUDE.md's own notes and may have drifted.
- Windows environment: `shutil.which()` for subprocess calls, `encoding="utf-8"` on subprocess readers, no bash heredocs.
- Commit separately from any unrelated change, verified against actual `git diff HEAD`.
- Report any further design fork back to Mike rather than resolving silently.
- Do **not** update the context doc (`FORGE-context_v63.md`) from this Claude Code session — that's Claude.ai's job at session close. Do update `CLAUDE.md` with what this session actually did/observed.

---

## The fix: generalize `resolve_feature_pr()` to match by tracking-issue reference, not branch name

**File:** `core/agents/workflow_glue.py` — `resolve_feature_pr()` (used by `06-deploy.yml`'s guard clause).

**Current behavior (confirmed, per CLAUDE.md):** asks GitHub directly for the currently-open PR on branch `feature/<request_id>` via `github_helper.list_open_prs_by_head()`. Correct for the original per-request implementation branch. Raises `ValueError` on zero or more than one open match — that strictness is good and should be preserved.

**Problem:** an ad hoc fix PR (e.g. `feature/fix-shift-already-claimed` for PR #22) doesn't match `feature/<request_id>` literally, so the guard clause raises even when QA/Security are both genuinely green.

**Root cause:** the function resolves "the PR for this request" via branch-name equality, which only holds for the original implementation branch. It has no path for a PR whose branch is named differently but which still legitimately belongs to the same tracking issue.

**Fix design:**

1. Read `resolve_tracking_issue()` in full first (per CLAUDE.md: it finds the tracking issue number from a `forge-demo-apps` PR body's `Related FORGE tracking issue: owner/repo#N` line — the same line Item #15 already requires on every ad hoc PR). Confirm its exact signature and what it returns (issue number? owner/repo/issue tuple?) before reusing any of its logic.

2. Rewrite `resolve_feature_pr()`'s resolution order as:
   - **Step 1 (unchanged, tried first):** look for an open PR on branch `feature/<request_id>` via the existing `list_open_prs_by_head()` call. If found, use it — this preserves the original implementation-branch path exactly as-is, with zero behavior change for the common case.
   - **Step 2 (new, fallback only if Step 1 finds nothing):** list all currently-open PRs on `forge-demo-apps` (a new or existing `github_helper.py` call — check whether one already exists, e.g. something like `list_open_prs()`, before adding a duplicate), and for each, parse its body for the `Related FORGE tracking issue: owner/repo#N` line (reuse `resolve_tracking_issue()`'s own parsing logic directly — don't reimplement the regex/parsing a second time; refactor the body-line parsing into a shared helper both functions call if it isn't already factored out). Match against the issue number implied by `request_id`. **Add this as a shared body-parsing helper, not just a mirrored regex, so this line's parsing rule only lives in one place.**
   - If Step 2 finds exactly one match, use it.
   - If Step 2 finds zero matches, raise the same `ValueError` shape as today (no open PR found for this request), now with wording that reflects both paths were checked (e.g. name both the branch pattern and the tracking-issue line as things that were searched, so a future failure is diagnosable without reading source).
   - If Step 2 finds more than one match (two simultaneously-open fix PRs both referencing the same tracking issue), raise `ValueError` — do not silently pick one. This mirrors the existing strictness for the Step-1 path and is a real scenario worth failing loudly on rather than guessing.

3. **Do not change `resolve_tracking_issue()` itself** — this fix only adds a new fallback path inside `resolve_feature_pr()`, refactoring shared parsing logic out if needed. `04-qa.yml`/`05-security.yml`'s existing behavior must be unaffected.

4. Confirm whether Item #15's known gap — an ad hoc PR opened by a human (not a FORGE stage agent) missing the tracking-issue body line entirely — is in scope here. It is **not**: if the line is missing, Step 2 correctly finds nothing and the existing manual remediation (editing the PR body, per Item #15's documented fix) still applies. Don't try to solve "PR body missing the line" in this fix; that's Item #15's territory and already has a working (if manual) answer.

**Acceptance criteria:**

- Re-run against the original implementation-branch case (a real or simulated `feature/<request_id>` PR) — confirm Step 1 still resolves it with **zero code path change** to today's working behavior (no regression for the common case).
- Re-run against PR #22's actual shape (an ad hoc `feature/fix-*` branch, tracking-issue body line present, `qa-approved`/`security-approved` both present) — confirm `resolve_feature_pr()` now returns PR #22 via the Step 2 fallback instead of raising, without needing the manual `deploy_agent.py --commit-sha/--pr-number` workaround from this session.
- Simulate the zero-match case (no PR on the expected branch, no PR body referencing the tracking issue) — confirm the `ValueError` message clearly states both paths were checked.
- Simulate the multiple-match case (two open PRs both referencing the same tracking issue, neither on `feature/<request_id>`) — confirm `ValueError` is raised rather than either PR being silently selected.
- Confirm `resolve-request-id`/`resolve-tracking-issue` subcommands used by `04-qa.yml`/`05-security.yml` are unaffected — re-run (or confirm via code review) that their call paths are untouched by this change.
- If a shared body-line-parsing helper was extracted, confirm both `resolve_tracking_issue()` and the new Step 2 path call the same helper (not two independently-maintained regexes for the same line format).

---

## After the fix is done

- Commit as its own single commit (this is one coherent fix, not several — no need to split further).
- Since `06-deploy.yml` only triggers on a `labeled` webhook event (a known, separate quirk noted in Open Item #17 — not being fixed here), verifying this live will require either a fresh ad hoc fix PR cycle or a manual label re-add/remove/re-add to re-fire the workflow. Note in `CLAUDE.md` which method was actually used.
- Update `CLAUDE.md` with what this session did/observed, including confirmation of live (not just unit-level) verification if a real PR cycle was exercised. Do **not** update the context doc from this session — that's Claude.ai's job at close.
- Next chat after this one (Claude.ai): fold this session's findings into the context doc, close Item #17, and move to the next open item (Dependabot triage or next-phase discussion, per Mike's priority).
