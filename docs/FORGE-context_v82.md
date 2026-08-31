# FORGE — Session Context v82

**Session date:** 2026-08-31 (Claude.ai)
**Carries forward from:** v81, unchanged except where noted below.

---

## What changed this session

### 1. New backlog idea — Configurable Pipeline Depth (per-request stage limit)

Mike proposed a new FORGE capability: let a request specify how many stages to
run (e.g. "through Requirements only," "Requirements + Cost Estimate," "through
Design"), rather than always running the full stack to Deploy. Scoped via
quick decisions:
- Setting lives as a new field on the intake spreadsheet (not a global config)
- Applies to **both** greenfield and enhancement workflows
- **Blocked** — held until the Cost Estimator spec/build exists, since one of
  the stop points ("Requirements + Cost Estimate") needs a real stage to point
  at

Not investigated or spec'd this session — logged as a future item, not yet
numbered against the Backlog (it should get a number once picked up for real
investigation).

### 2. Phase 7 (Enhancement Workflow) — discovered already substantially complete

Session started as "carry on with Phase 7" (confirm the proposed coverage-history-view
enhancement target). Mike's question — "didn't we finish the view for that
already?" — triggered a reconciliation pass that found Build Plan steps 7.2–7.8
had **already happened**, via **REQ-2026-04** (tracking issue `forge-template#10`,
feature PR `forge-demo-apps#32`, existing service REQ-2026-03), during the
Item #24/#25/#26/#28 fix cycle, which used it as the real live test target. No
standalone "yes, build this" decision was ever recorded — it happened implicitly.

**Verified via Claude Code CLI (live GitHub + ADO API calls):**
- 7.2/7.3: real intake spreadsheet (`docs/FORGE-Intake-REQ-2026-04-CoverageHistoryView.xlsx`),
  Request Type = Enhancement, Existing Service = REQ-2026-03, requirements match
  the coverage-history view word for word
- 7.4: Stage 0a genuinely fired (`existing-architecture-summary.md` committed
  to `pipeline-state`, real non-dry-run commit)
- 7.5: Requirements → Design → Implementation → QA → Security → Deploy all ran
  for real
- 7.6: confirmed lands on `services/REQ-2026-03/`, deployed in place, zero new
  `req-2026-04-*` resources
- 7.7: **attempted but did not land as intended** — surfaced Backlog Item #32
  (see below)
- 7.8: actuals present in the cost log (part of Item #12's backfill)

**Docs updated:** `FORGE_Build_Plan_v9.md` → **v10** (7.2–7.6/7.8 checked off
with evidence, 7.7 left unchecked with the Item #32 pointer). Phase 7 status:
substantially complete.

### 3. Backlog reconciliation — v2 → v3 → v4 → v5, several real discoveries along the way

First pass (v3, built from a stale project-knowledge snapshot of v2) had to be
corrected twice by Claude Code CLI against the live file — not just wording
drift, genuine regressions:
- **Item #1 (secrets discovery)** was already **fully resolved 2026-08-31**
  (both Option 3 and Option 1 built and live-verified) — my draft had reverted
  it to "still open." This was news to me too; not reflected in v81 or memory
  going into this session.
- **The PR self-approval/branch-protection deadlock** — genuinely unresolved,
  and hit for real this same day while merging Item #1's own `design.md`
  backfill PR (`forge-demo-apps#35`) — was dropped entirely from my draft.
  Restored, then **decided by Mike this session**: keep the manual
  disable/restore workaround (confirm state → drop required-review count to 0
  → merge → confirm → restore to 1 → independently re-verify) rather than
  weaken branch protection permanently or build App-identity PR routing. Will
  recur on the next ad hoc PR under Mike's own account — by deliberate choice,
  not an oversight. Standing 6-step procedure now documented in the Backlog.
- Item #31's live entry was more complete than my reconstruction (6 commits,
  not 5) — kept as-is.

**New items found and resolved same session:**
- **Item #32** — `create_ado_items.py` had zero Enhancement awareness (the
  same "no existing_service" pattern as #24/#25/#28, a fourth occurrence).
  REQ-2026-04's ADO items landed as a brand-new parallel Epic (#169), never
  linked to REQ-2026-03's real Epic (#134). **Mike's call: build the real fix.**
  Investigated live, spec'd (`docs/Specs/FORGE-Item32-ADOEpicLinkage-Spec.md`),
  built and live-verified same session via throwaway ADO items (Epic
  #179/Feature #180/Story #181 for the reuse path, Epic #182/Feature
  #183/Story #184 for the confirmed-unregressed Greenfield path) — commits
  `bbbe3d0`, `759cc58`, `c4b3d0c`. **Resolved.** Six throwaway ADO items
  (#179–184) and a throwaway tracking issue (`forge-template#11`, already
  closed) are left for Mike to delete via the ADO UI whenever convenient — not
  urgent, not tracked as a numbered item.
- **Item #33** — `forge-template#10` was still open despite REQ-2026-04's
  pipeline having completed and deployed. Closed this session with a summary
  comment.

**Net result:** Backlog is now at **v5**, with genuinely nothing open in
Design/Policy Decisions or Bookkeeping — only Items #7 and #11 remain
(deliberate accepted-risk/leave-as-is, unchanged) plus the self-approval
deadlock's standing accepted procedure. The six throwaway ADO items and the
throwaway tracking issue from Item #32's live verification have since been
deleted by Mike — nothing left to clean up.

**CLAUDE.md updated** (commit `27c2576`): new Item #32 entry in Open Items /
Known Gaps, plus a one-line forward-reference added to each of Items
#24/#25/#28 naming #32 as the fourth occurrence of the same pattern.

**Process note for next session:** twice this session, Claude Code CLI found
that content I'd handed it as "new" (the v3 draft, a spec file path) had
already been committed directly by Mike before the task started. Not a
problem — CLI caught and reconciled both times — but worth knowing collab is
happening on both ends of the two-tool split sometimes.

---

## Open items — updated status

- **Configurable Pipeline Depth (new backlog idea):** blocked on Cost Estimator,
  not yet numbered or investigated.
- **Item #1:** now known to be **fully resolved** (was incorrectly tracked as
  open in v81 — v81 itself was stale on this point going into this session).
- **PR self-approval/branch-protection deadlock:** **decided** — manual
  workaround, standing procedure documented in Backlog v5.
- **Item #32:** **resolved** this session (built, live-verified).
- **Item #33:** **resolved** this session (issue closed).
- **Item #7, #11:** unchanged — deliberately left as-is / accepted ongoing risk.
- **Cost Estimator spec:** unchanged, not yet started. Now blocks two things
  (its own Stage 3 slot, and the new Configurable Pipeline Depth idea) —
  worth bumping up in priority.
- **Phase 7:** now **substantially complete** (see above) — not "on the
  horizon" anymore.

## Azure infrastructure

Nothing started this session — all work was doc commits, GitHub API calls
(including real issue/PR/branch-protection operations), and real ADO API calls
(creating/reading throwaway work items for Item #32's live verification, no
cost). No Azure resources touched. No shutdown prompt needed. Postgres
(`forge-req2026-03-pg`) was not touched.

---

## On the horizon (unchanged from v81 unless noted)

- **Cost Estimator spec** — five open design forks, not yet started. Now
  higher priority than before (blocks the new Configurable Pipeline Depth
  idea too).
- **Configurable Pipeline Depth** — new this session, blocked on Cost
  Estimator.
- Phase 8 (Handoff Readiness) — next up on the Build Plan now that Phase 7 is
  substantially complete; not yet started, not discussed this session beyond
  noting it's next.
- Ongoing Documentation Ownership discipline continues to hold — no drift
  detected this session beyond the pre-existing staleness this session itself
  found and fixed.
