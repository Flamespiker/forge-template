# FORGE — Session Context v83

**Session date:** 2026-08-31 (Claude.ai, continued same day as v82)
**Carries forward from:** v82, unchanged except where noted below.

---

## What changed this session

### Item #34 — Stage 3 Cost Estimator: scoped, specced, built, live-verified, cleaned up (full lifecycle, one session)

Picked up from v82's "on the horizon" — the Cost Estimator, bumped to top
priority since it blocked both its own Stage 3 slot and the new Configurable
Pipeline Depth idea. This session covered the entire lifecycle in one
continuous chat rather than splitting across investigation/spec/build
sessions, since the investigation had already been done earlier this same
day (chat 2026-08-29's scoping session supplied the five original forks; this
session's own investigation pass against live code supplied the rest).

**Five original forks (2026-08-29) resolved this session:**
1. **Pre-flight estimate basis:** not tasks.md alone — unit count from
   tasks.md + Enhancement seed file count (already computed by existing
   `_resolve_enhancement_target()` code, just never surfaced) + a
   shape-bucketed historical baseline.
2. **Gate mechanism shape:** new `cost-approved` label, required alongside
   `design-approved` — same two-label AND-gate shape as Item #26's Deploy fix.
3. **Mid-session behavior:** out of scope — no threshold exists (see #4), so
   there's nothing to breach mid-session. Explicitly not built.
4. **Threshold storage:** **no threshold at all** (Mike's call) — purely
   informative, human decides yes/no by applying `cost-approved`. Simpler
   than originally scoped; no `team/config.yaml` addition needed.
5. **Post-run reporting surface:** both — extend the existing tracking-issue
   comment (estimate vs. actual) AND close the standing cost-log automation
   gap (`FORGE-pipeline-cost-log.md` §4.2) with a new `managed_agents_cost`
   structured log line.

**A sixth fork, surfaced by Claude Code CLI's own investigation (not
anticipated by the original spec):** real logged Stage 3 actuals are *all*
2-unit (REQ-2026-01/02/03/04 every one has both Backend and Frontend in
tasks.md) — zero precedent existed for either 1-unit bucket, not just
`(1, True)` as the spec assumed. **Resolved (Mike):** scale the
same-enhancement-status 2-unit baseline by a fixed 0.5x, explicitly labeled
low-confidence in the posted comment, rather than falling back to an overall
mean or refusing to estimate.

**Confirmed baselines used:** `(2, False)` = $8.96 (mean of 3 real runs),
`(2, True)` = $4.57 (1 real run, REQ-2026-04/PR#32, 87 seed files — confirmed
live via tool-use events), `(1, False)` = $4.48 (0.5x scaled, no precedent),
`(1, True)` = $2.285 (0.5x scaled, no precedent).

**Built:** `_estimate_implementation_cost()` + `_COST_BASELINES_USD` in
`implementation_coordinator.py`; a shared `select_seed_blobs()` refactor
avoiding wasted per-file fetches for the estimate step; `run_cost_estimate()`
/ `--estimate-only` CLI mode posting the estimate as a tracking-issue comment
with a hidden marker (first instance of marker-based structured-data
round-trip in this codebase — every prior use only checked
presence/counted occurrences); `_fetch_cost_estimate()` /
`_extract_actual_cost_usd()` reading the marker back and
`usage.list_cost.amount` respectively, both wired into the final
estimate-vs-actual comment; `03-implementation.yml`'s new two-label AND-gate
(mirroring Item #26's Deploy shape) plus the new estimate-only step; a new
`managed_agents_cost` log line in `managed_agents_wrapper.py`.

**Live-verified, both paths, real Managed Agents sessions:**
- **Greenfield** (scratch issue #12): first-ever real `(1, False)` data
  point — $0.51–0.56 actual, against a $3.50–5.50 low-confidence estimate.
- **Enhancement** (scratch issue #13, against real REQ-2026-03): `(2, True)`
  bucket with live seed-file scaling — 94 files (not 87), correctly
  reflecting real drift from the historical reference rather than
  hardcoding a stale number.

**Real P0 found and fixed during live verification:** `usage.list_cost.amount`
is returned by the live API as a **string**, not numeric —
`_extract_actual_cost_usd()`'s original `amount / 100` crashed on every real
completed run. Would have silently broken the comment/PR step on every real
Stage 3 run once merged (session already archived by that point, so no
orphaned billable resources, but no PR/comment either — a confusing silent
failure). A second, related bug — `main()`'s bare
`except Exception: sys.exit(1)` was swallowing the traceback with no
logging — also fixed, since it's what hid the first bug from CLI for a
while. Both fixed, unit-verified, then **confirmed live** with one more
cheap Greenfield re-run (issue #12 again, $0.56 actual) before committing —
worth doing given this would have hit every real production run otherwise.

**Cleanup, fully complete:** both scratch tracking issues (#12/#13) closed;
both Managed Agents sessions cleanly archived (no orphaned billable
resources — the Enhancement one hit the Item #6 interrupt-handling path as
expected and was manually archived per the documented procedure); real draft
PR `forge-demo-apps#39` (Greenfield test) closed unmerged, its branch
deleted; scratch docs (`docs/TEST-ITEM34-GF/`, `docs/TEST-ITEM34-ENH/`)
removed from `main` via PR `forge-demo-apps#41` (merged); all five
`design/TEST-ITEM34-*`/`feature/TEST-ITEM34-GF` branches deleted, each
deletion confirmed via a fresh API 404 read, not just the delete call's own
response. No scratch state remains anywhere in `forge-demo-apps`.

**Commits (forge-template):** `1aee048`, `363067b` (the two P0 bugfixes) plus
the original 5 feature commits from the build phase — full hash list lives
in CLAUDE.md's Item #34 entry, not duplicated here.

**CLAUDE.md updated by Claude Code CLI** — new Item #34 entry, per
Documentation Ownership convention (Claude.ai does not write to CLAUDE.md
directly).

---

## Open items — updated status

- **Item #34 (Cost Estimator):** **fully resolved and closed out** this
  session — scoped, specced, built, live-verified (both paths), one P0
  found and fixed, all scratch state cleaned up. Nothing outstanding.
- **Configurable Pipeline Depth:** **unblocked** — Item #34 was the last
  blocker (needed a real Cost Estimator stage for the "Requirements + Cost
  Estimate" stop point to point at). Still not numbered or investigated;
  ready to pick up as real work whenever prioritized.
- **Phase 8 (Handoff Readiness):** unchanged from v82 — next up on the Build
  Plan, not yet started.
- **Item #7, #11:** unchanged — deliberately left as-is / accepted ongoing
  risk.
- Everything else carried from v82 unchanged (Item #25's narrative
  correction already folded into CLAUDE.md per v82; no other drift found
  this session).

## Azure infrastructure

Nothing Azure-related touched this session. The live tests never reached
Deploy (no PR was merged during verification — both test PRs were closed
without merging, and the real docs-cleanup PR #41 only touched
`forge-demo-apps` doc files, not any service code that would trigger a
redeploy). Postgres (`forge-req2026-03-pg`) was not touched. No shutdown
prompt needed.

---

## On the horizon

- **Configurable Pipeline Depth** — now unblocked (see above). Not yet
  numbered or investigated. Candidate for next session's focus, or whenever
  Mike wants to pick it up.
- **Phase 8 (Handoff Readiness)** — next up on the Build Plan, unchanged
  from v82.
- **Cost baseline recalibration** — flagged during this session, not urgent:
  the real `(1, False)` actual ($0.51–0.56) came in well under the 0.5x-scaled
  estimate ($4.48), and `(2, True)`'s single-data-point baseline drifted
  (87 → 94 seed files on the very next Enhancement run). Worth revisiting
  `_COST_BASELINES_USD`'s constants once a few more real runs accumulate in
  each bucket — not a bug, just an expected consequence of shipping a
  coarse heuristic with thin historical data, exactly as the spec's own
  commentary anticipated.
- Ongoing Documentation Ownership discipline continues to hold — no drift
  detected this session.
