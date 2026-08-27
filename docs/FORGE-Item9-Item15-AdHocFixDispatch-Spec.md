# FORGE — Ad Hoc Fix-PR Real Security Dispatch (Item #9 + Item #15), Enabling Item #10: Spec for Claude Code

**Prepared:** 2026-08-26 (Claude.ai)
**For:** Claude Code CLI session against `forge-template` (workflow/glue-code fixes) and, for verification only, a throwaway ad hoc fix PR against `forge-demo-apps`
**Context:** Two coupled Open Items, both previously logged in CLAUDE.md, decided together by Mike this session:

- **Item #9** — ad hoc `fix/*`-branch PRs hit the permanently-unsatisfiable `security-check` gate (only `feature/*`/`design/*` branches get dispatched a real or no-op check) and have needed `--admin` merge 4 times (PRs #7, #8, #11, #16), plus twice more recently for unrelated reasons (PRs #28, #29, per Item #23's own note — same admin-merge precedent, same underlying gap).
- **Item #15** — even a correctly-named `feature/fix-*` branch fails outright at `resolve_tracking_issue()` if the PR body is missing the `Related FORGE tracking issue: owner/repo#N` line, since ad hoc PRs (human- or Claude-opened) don't get that line written automatically the way `design_agent.py`/`implementation_coordinator.py` PRs do.

**Decision (Mike, this session):** fix both properly rather than accept `--admin` merge as standing procedure (**Path 2** from the two options presented — real scan via the already-decided `feature/fix-*` naming convention, not a no-op bypass). Once both are fixed and live-verified, **Item #10** (`enforce_admins` currently `false` on `forge-demo-apps`' `main`) can be flipped back to `true` as a separate, low-risk follow-up step — do not flip it as part of this same commit; flip only after this spec's fixes are confirmed working end-to-end on a real PR.

**Standing conventions to follow (per CLAUDE.md / context doc):**
- Verify against the live file, not this spec — `grep -n` the actual current `notify-forge.yml`, `workflow_glue.py`, `04-qa.yml`, `05-security.yml` before editing anything. Line numbers/function names below are from CLAUDE.md's own notes and may have drifted.
- Windows environment: `shutil.which()` for subprocess calls, `encoding="utf-8"` on subprocess readers, no bash heredocs.
- Commit each of the two fixes **separately** (Item #9's dispatch fix and Item #15's tracking-issue-line fix are different root causes in different files) — verified against actual `git diff HEAD`.
- Report any design fork back to Mike rather than resolving silently.
- Do **not** update the context doc from this Claude Code session — that's Claude.ai's job at session close. Do update `CLAUDE.md` with what this session actually did/observed, including marking Items #9 and #15 resolved (or partially resolved, if something doesn't land cleanly) and adding the Item #10 flip as a new, explicit next step rather than doing it inline.
- Do **not** flip `enforce_admins` to `true` as part of this session unless explicitly re-confirmed by Mike after live verification — this spec's job is to make the flip *safe*, not to perform it.

---

## Fix 1 (Item #9): Real `security-check` dispatch for ad hoc fix PRs

**Files:** `forge-demo-apps/.github/workflows/notify-forge.yml`, possibly `forge-template`'s `04-qa.yml`/`05-security.yml` guard clauses.

**Problem, confirmed live:** `notify-forge.yml` currently forwards `pull_request` (`opened`, `synchronize`) events to `forge-template` as `feature-pr-opened` only for branches matching the formal `feature/<request_id>` pattern used by `implementation_coordinator.py`-opened PRs. The already-decided branch-naming convention (`feature/fix-<short-description>`, decided 2026-08-13, documented in CLAUDE.md) was meant to route ad hoc fixes through this same dispatch — confirm live whether `notify-forge.yml`'s branch-matching logic (`grep`/read its actual `if:`/`branches:` filter) already covers `feature/fix-*` as a subset of `feature/*`, or whether it has a narrower pattern (e.g. requiring `feature/REQ-\d+` specifically) that would silently exclude it. **Item #23's PRs #28/#29 still hit admin-merge on 2026-08-26 for this exact reason — do not assume the 2026-08-13 naming decision alone already fixed this; verify the actual filter live before writing any fix**, since the evidence suggests it did not.

**Fix design:**
1. Read `notify-forge.yml`'s live trigger/filter logic. If it's pattern-matching something narrower than `feature/*` as a whole (e.g. hardcoded to `feature/REQ-*`), broaden it to match any `feature/*` branch, including `feature/fix-*` — this should be a minimal, additive filter change, not a rewrite.
2. Confirm `04-qa.yml`/`05-security.yml`'s own guard clauses (which re-check trigger state at run time, per the project's established "guard clause on every workflow" pattern) don't have a *separate*, narrower assumption baked in — e.g. an implicit expectation that `request_id` always resolves to something with an open Implementation-stage tracking issue in a specific label state. Ad hoc fix PRs are, by definition, out-of-band from the six-gate label lifecycle (Document 07: locked stage sequence) — confirm both workflows can run cleanly against a PR that has no `design-approved`/`qa-approved` label history at all, since they were never dispatched through Stage 3.
3. Do **not** add a new no-op check workflow (that was the rejected Path 1) — the goal here is that ad hoc fix PRs get a **real** Dependabot-backed `security-check` run and pass or fail on their actual merit, same as any `feature/<request_id>` PR.

**Acceptance criteria:**
- Confirm live (read, don't assume) that `notify-forge.yml` now dispatches `feature-pr-opened` for a `feature/fix-*` branch, not just `feature/<REQ-id>`.
- Open a real throwaway ad hoc fix PR on `forge-demo-apps` (small, additive, low-risk diff — e.g. a comment or README tweak, same pattern as the throwaway PR used to verify Item #17) on a `feature/fix-<description>` branch, **with** the tracking-issue body line present (to isolate this fix from Fix 2 below — test them independently first, then together).
- Confirm via `gh run view` that both `04-qa.yml` and `05-security.yml` actually ran (not skipped) and that `security-check` posted a real `success` status (not a no-op label, an actual Dependabot-backed scan conclusion).
- Confirm the PR is mergeable via the normal required-check path — no `--admin` flag needed — while `enforce_admins` is still `false` (don't flip Item #10 yet; this step is proving Fix 1 works under current settings first).
- Close the throwaway PR and delete the branch immediately after, same cleanup discipline as prior throwaway-PR verifications (Item #17).

---

## Fix 2 (Item #15): Auto-populate the tracking-issue body line for ad hoc PRs, or make resolution tolerant of its absence

**Files:** `core/agents/utils/workflow_glue.py` (`resolve_tracking_issue()`), and/or whatever tooling a human/Claude uses to open an ad hoc fix PR.

**Problem, confirmed live:** `resolve_tracking_issue()` (used by `04-qa.yml`/`05-security.yml`) requires the `Related FORGE tracking issue: owner/repo#N` line in the PR body. `design_agent.py`/`implementation_coordinator.py` always write it; a human- or Claude-opened ad hoc fix PR does not, by default — confirmed live on PR #21, where both QA and Security failed outright on `resolve-tracking-issue` until the body was manually edited and the `repository_dispatch` event manually replayed.

**Design fork — surface to Mike, don't guess:** two real options, meaningfully different:
- **Option A — process fix:** document/enforce that any ad hoc fix PR must include the tracking-issue line in its body at open time (a PR template, or a documented step in whatever procedure Mike/Claude Code follows when opening one). No code change; relies on the human/Claude-in-the-loop remembering every time. Cheapest, but doesn't remove the "bites on a correctly-named branch anyway" gap this item was raised to close — it just relocates the discipline requirement.
- **Option B — code fix:** make `resolve_tracking_issue()` tolerant of a missing line by falling back to something derivable without it — e.g. `workflow_glue.py`'s existing `resolve_feature_pr()` fallback pattern (Item #17: try direct match, then fall back to scanning open PRs) suggests a precedent — but note an ad hoc fix PR has no natural tracking issue to resolve to at all if one was never opened for it. Confirm with Mike whether ad hoc fixes should require *some* tracking issue to exist (even a lightweight one opened just to carry the fix), or whether QA/Security should be able to run and post their `security-check`/`qa-approved`-equivalent status **without** a tracking issue at all for this PR shape specifically — that's a real behavior change to what a tracking issue means in this pipeline, not a small fix, and shouldn't be picked without Mike's explicit sign-off.

**Recommended default if Mike doesn't want to spend more decision cycles right now:** Option A (process fix) is safer and smaller — it doesn't touch `resolve_tracking_issue()`'s contract, which other stages rely on meaning something real. Flag this recommendation to Mike at spec-execution time and get an explicit yes/no rather than silently implementing it.

**Acceptance criteria (once Option A or B is confirmed):**
- Re-run the same throwaway-PR test as Fix 1, this time **without** manually adding the tracking-issue line up front, and confirm `resolve_tracking_issue()` now resolves correctly (Option A: because the line was included per the new documented step; Option B: because the fallback logic kicked in).
- Confirm no regression to `design_agent.py`/`implementation_coordinator.py`-opened PRs, which already write the line correctly today — this fix must not change behavior for the common case.

---

## After both fixes are done

1. Run one **combined** live test: a real throwaway ad hoc fix PR, `feature/fix-*` branch, tracking-issue handling per whichever option was chosen in Fix 2, zero manual intervention (no manual `repository_dispatch` replay, no manual body edit) — confirm it goes from PR-open to a real `security-check` pass end-to-end, then merges normally without `--admin`.
2. Report this result back to Mike explicitly. **Only after Mike confirms this live test is good** should `enforce_admins` (Item #10) be flipped to `true` on `forge-demo-apps`' `main` branch protection — this is a separate, explicit action (a `gh api` or Portal change, not a code commit), not something to bundle into this same session's commits.
3. Update `CLAUDE.md`: mark Item #9 resolved (with the live-verification evidence), mark Item #15 resolved per whichever option was chosen (with rationale, since the design fork was real), and add a new explicit Open Item (or a note in Item #10's own entry) capturing "safe to flip now, pending Mike's go-ahead" — don't just silently flip it and don't let the flip get lost as an implicit side effect of this spec.
4. Do **not** touch the `pipeline-state` branch or any of Items #1/#7/#12 — out of scope here.

---

## Next chat after this one (Claude.ai)

Once Claude Code reports back with live-verification evidence and Mike has confirmed the `enforce_admins` flip, fold the outcome into a fresh context doc (v69), close Items #9/#10/#15 in the backlog, and resume the previously-flagged next spec target — **Item #23** (Stage 3 never extended for Enhancement requests), which is still open and still blocking tracking issue #10's Stage 3 re-run.
