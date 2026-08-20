# FORGE Context — v62
**Session date:** 2026-08-19
**Carries forward from:** v61

---

## Purpose & context (unchanged)

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment, with human approval gates at defined stages.

Two-repo model: `forge-template` (public, orchestration/agents) and `forge-demo-apps` (private, target monorepo). Two-tool convention firm: Claude.ai owns strategy/spec authorship/context docs; Claude Code CLI owns live execution/git/CLAUDE.md. Mike shuttles between tools and holds all unilateral decisions.

---

## Current state

**Phase 6 (Repeatability) remains CLOSED** (per v60). This whole session (v61 + v62) was housekeeping cleanup plus one ad hoc fix PR — no new build phase started. All housekeeping items identified at session start are now resolved except the live smoke test. Next phase is still undefined.

### Resolved this session (continuing from v61)

1. **`forge-demo-apps-clone` deleted.** Confirmed clean first (`main`, no tracked changes, only untracked build artifacts, sitting at `7596ff7` — one commit behind current `main` since it hadn't fetched since REQ-2026-03's original PR #20/#21 work). Folder removed. Mike now works exclusively in `forge-demo-apps`.

2. **PR #22 merged, branch deleted.** The `SHIFT_ALREADY_CLAIMED` wording fix (backend + frontend, per v61) is now on `main`. `feature/fix-shift-claim-message-wording` deleted post-merge.

3. **Tracking issue `forge-template#6` (REQ-2026-03's parent tracking issue) closed manually.**
   - PR #22's merge triggered `06-deploy.yml`'s auto-trigger (off `security-approved`/merge), which failed before `deploy_agent.py` could even run — this is **Open Item #17 manifesting in the wild**, not a new bug: `resolve_feature_pr()` couldn't find PR #22 (branch `feature/fix-shift-claim-message-wording`, not the original `feature/REQ-2026-03`) and threw the same `ValueError` seen during this session's manual invocation. Confirmed as already-understood, already-logged — no new investigation needed.
   - Since the real deploy had already happened via the manual `deploy_agent.py` invocation earlier this session (confirmed live at commit `d53bebd` via `az containerapp show`), the failed automated workflow run doesn't reflect an actual deployment failure — just the automation's inability to locate the PR. GitHub does not auto-close on a failed workflow run, so the issue was closed manually by Mike through the GitHub UI, since the tracking issue's actual purpose (build + deploy REQ-2026-03, including this fix) is genuinely satisfied.
   - This is now the **second real-world confirmation** of Open Item #17 in a single session (once during the manual verification, once via the automated workflow's own failure) — reinforces it as a priority for the next spec session rather than a theoretical edge case.

### Still open / next session's starting point

**All housekeeping from today is now closed except:**

- **Live HTTP smoke test for the `SHIFT_ALREADY_CLAIMED` fix** — self-claim-retry vs. other-user-claim, both cases, with real bearer tokens. Still not run. PR #22 is merged and deployed live, but this fix should not be treated as fully verified until this test is actually performed. Highest-priority loose end carried into next session.
- **Open Item #17 (Deploy pipeline gap)** — `resolve_feature_pr()` in `workflow_glue.py` only recognizes the original `feature/<request-id>` branch as a tracking issue's PR; cannot resolve ad hoc fix PRs. Confirmed twice this session (manual verification + live automated workflow failure). Needs its own spec (design question: issue linkage? branch-name pattern? PR body parsing?) before Claude Code implements anything — every future ad hoc fix PR will hit this same wall otherwise. Good candidate for next session's main focus.
- **102 Dependabot alerts repo-wide, 74 outside REQ-2026-03** — still not triaged. Carried forward across v58–v61. Needs a dedicated pass (severity + individual NVD-source verification for CPE fuzzy-match hits, per existing root-cause discipline).
- **Cloud-portability / multi-cloud deploy-target abstraction** — raised and discussed this session (v61), explicitly deferred by Mike. Not urgent, no spec drafted. Assessment on record: orchestration core (Stages 0–5) is cloud-agnostic; Deploy Agent's direct `az containerapp` calls are the one deep Azure coupling point.
- **Next phase still undefined.** With Phase 6 closed and this session being pure housekeeping, the "what comes after repeatability" decision remains open — worth a dedicated conversation whenever Mike is ready to have it, separate from the smaller cleanup/spec items above.

---

## Key learnings & principles (new this session)

**A workflow failure isn't automatically a new bug — check against already-logged gaps first.** The `06-deploy.yml` failure on PR #22's merge looked alarming at first glance ("forge deploy workflow failed") but was immediately traceable to the already-identified Open Item #17, confirmed by matching the exact `ValueError` and branch-name mismatch. Worth checking new-looking failures against the current open-items list before treating them as fresh investigation work.

**GitHub's auto-close-on-merge only fires on a successful linked action or explicit closing keyword — not on a failed workflow run.** When automation fails partway through, don't assume the tracking issue will resolve itself; a manual close is sometimes the correct and honest way to reflect "the underlying work is genuinely done" even though the automated path choked.

**Open Item #17 has now surfaced twice in one session** (manual invocation needed to work around it, then the same gap causing the automated workflow to fail outright on merge) — a good example of why a newly-found structural gap should be logged clearly even when the immediate task isn't blocked, since it will keep recurring until actually fixed.

---

## Approach & patterns (reconfirmed, unchanged)

- Two-tool convention firm; Claude Code CLI prompts/specs drafted in full in Claude.ai chat, copy-pasted.
- Verification honesty maintained end-to-end this session: the live smoke test gap was tracked explicitly through v61 and v62 rather than being quietly dropped once PR #22 merged.
- Design forks and structural gaps (frontend scope extension, Deploy pipeline gap, cloud-portability question) all surfaced explicitly to Mike for a real decision rather than resolved silently — reconfirmed multiple times this session.

---

## Tools & resources (updates this session)

- **Local checkouts:** `forge-demo-apps` only — `forge-demo-apps-clone` deleted this session.
- **`forge-demo-apps` main:** now includes PR #22 (`SHIFT_ALREADY_CLAIMED` wording fix), branch `feature/fix-shift-claim-message-wording` deleted post-merge.
- **`forge-template#6`:** REQ-2026-03's tracking issue, now closed manually.
- **Live staging state unchanged from v61:** both Container Apps serving commit `d53bebd`.
