# FORGE — Session Context v87

**Session date:** 2026-09-03 (Claude.ai + Claude Code CLI)
**Carries forward from:** v86, unchanged except where noted below.

---

## What changed this session

### Item #43 — Configurable Pipeline Depth ("Phase Checkpoint") — spec'd, built, live-verified

Mike asked for a spec letting a requester choose "up to what agent" a
pipeline run should reach — a contiguous prefix selector, not an arbitrary
stage picker. This had been sitting un-numbered in prior sessions'
"Configurable Pipeline Depth" note (v84-v86); assigned **Item #43** this
session (confirmed against live `CLAUDE.md`/`Backlog v9` — #42 was the
highest in use, and v9 already listed this as a known-but-unnumbered
upcoming item).

**Spec authorship (Claude.ai), three revisions before build:**
- **v1** — initial shape: five depth tiers, capture field in Intake
  Template Section B, enforcement via a guard-clause addition ahead of each
  stage's existing precondition check, config persisted to
  `pipeline-config.json` on `pipeline-state`.
- **v2** — after Claude Code CLI's investigation-only pass: confirmed the
  `ado-work-items.json` write site (`requirements_agent.py`,
  `commit_files()` call, lines 342-349) and `get_file_contents()` reuse
  were both real, minimal insertions. Corrected a wrong assumption — v1
  claimed Pipeline Depth parsing should "mirror the Intake Agent's Request
  Type parsing"; investigation found no such function exists in
  `intake_agent.py` at all — Request Type normalization actually lives in
  an inline Python block inside `00-intake.yml`. Also surfaced the exact
  guard-clause insertion points (file:line for all six stages) and one real
  wrinkle: `04-qa.yml`/`05-security.yml` don't resolve `request_id` until
  after their existing guard clause, so the depth check needs a different
  insertion point there.
- **v3** — after Mike's design-fork decisions: collapsed from five tiers to
  **four** (`Just Requirements` / `Up to Design` / `Up to Implementation` /
  `Up to Deployment`), merging what had been separate Implementation and
  QA/Security tiers into one. This wasn't just a naming preference — QA and
  Security trigger automatically off "Implementation PR opened or updated"
  (Document 02 §4.6-4.7), not off a human-applied label, so a standalone
  "Implementation-only, stop before QA/Security" tier would have required
  building an entirely new gate that doesn't exist today. All six design
  forks resolved (bundled QA+Security; manual-edit override; depth
  captured at intake, persisted as soon as Requirements Agent runs;
  Cost Estimator note: yes; parsing mirrors the existing inline-YAML
  pattern rather than a new shared helper; Document 07 classification:
  Locked shape, fixed tier list).

**Build (Claude Code CLI), one correction found mid-build:** v3's
guard-clause table said the depth check inserts "immediately after" each
stage's label guard clause, but `request_id` actually isn't resolved until
a later step for **Design and Implementation too**, not only QA/Security as
v3 had flagged — CLI corrected all four affected insertion points (only
Deploy's was already right). Files changed: `Intake Template.xlsx` (new
Section B field, v1.1), `requirements_agent.py` (`_normalize_pipeline_
depth()`, writes `pipeline-config.json`), `workflow_glue.py`
(`check_pipeline_depth()`), `implementation_coordinator.py` (depth note in
the pre-flight cost-estimate comment), five workflow YAMLs (depth-check
step ANDed into every real-agent-invoking step), `06_Orchestration_v7.md`
and `07_Customization_Ref_v4.md` (new Locked row, with the QA/Security
auto-trigger reasoning documented inline so it doesn't need re-deriving
later). Committed as 6 separate commits by logical unit, each verified
against the live remote tip (`gh api .../commits/<sha>`, final
`heads/main` ref confirmed `df557fc` as genuine tip).

**Live verification — all three §10 test cases passed:**

| Test | Issue | Result | Real cost |
|---|---|---|---|
| 1 — Greenfield, Up to Design | `forge-template#14` (closed) | PASS | $0 (blocked before Stage 3) |
| 2 — Enhancement, Up to Implementation | `forge-template#15` (closed) | PASS | $0.66 real Stage 3 spend (vs. $7-12 estimated) |
| 3 — blank depth, regression | `forge-template#16` (closed) | PASS | $0 |

Test 1 and Test 2 were each deliberately re-run to isolate the new depth
check from the pre-existing two-label gates (applying `design-approved`
alone vs. also `cost-approved`; confirming Deploy stayed blocked even after
a real confirmed PR merge with both `qa-approved`/`security-approved`
present) — this rules out "the ordinary gate happened to also block it" as
a false-positive explanation. Test 2's Deploy-block was independently
confirmed via `az containerapp list` showing zero resources ever created.
All cleanup (issues closed, branches deleted, zero orphaned PRs) verified
via fresh API reads, not local state.

**Item #43 is now fully built and live-verified. Closed.**

### Two findings surfaced during verification — logged, not fixed this session

1. **New Item #44 (open):** `run_cost_estimate()` reads `tasks.md` from
   `main`, which only exists once the design PR is merged. Applying
   `design-approved` before merging causes a real 404 job failure. Found
   during Test 1's first attempt (label applied before merge, to isolate
   the event) — pre-existing, unrelated to Item #43's own code, and never
   hit in normal use because the documented Gate 2 flow always merges
   first. Worth a fix (defensive check or clearer failure message) but not
   urgent since the documented order avoids it.
2. **Not a backlog item:** a transient `anthropic.OverloadedError: 529` hit
   the Design Agent once during Test 3. Existing ADR-0011 failure-comment
   path and retry handled it correctly — noted here only as a "the existing
   resilience machinery works" data point, no action needed.

### Real ADO items left in place (as usual)

Tests 1, 2, and 3's retry each created real Epic/Feature/User Story items
under `spike99/FORGE-Build` as a Stage 2 side effect. Left in place per
existing precedent (manual cleanup whenever convenient, not auto-deleted).
Flagging for Mike's own tracking, not a to-do for either tool.

---

## Open items — updated status

- **Item #43 — CLOSED** (was: "Configurable Pipeline Depth," un-numbered).
  Built and live-verified this session, see above.
- **Item #44 (new, open)** — `run_cost_estimate()` 404s if `design-approved`
  is applied before the design PR is merged. Low urgency; documented flow
  avoids it.
- **Item #41 (open, design decision)** — unchanged from v86: `forge-
  template`'s `is_template: true` conflates Mike's live instance with the
  public template source. Still deferred, still worth deciding before
  external template users show up in volume.
- **Item #38, #39** — unchanged, still open design calls.
- **Item #40, #42** — unchanged, low-priority/clubbable bookkeeping.
- **Item #7, #11** — unchanged, deliberately left as-is / accepted ongoing
  risk.
- **Two stale-content review candidates** (from v84-v86):
  `01_FORGE_ProductSpec_v2.md`, `FORGE-phase-summary-and-training-
  reference-v2.md` — still flagged, still not scheduled.

## Azure infrastructure

Nothing Azure-related touched or spun up this session. Test 2 reached Stage
3 (real Managed Agents spend, $0.66) but never reached Deploy — confirmed
via `az containerapp list` that zero Container App resources were created
by any of the three tests. No shutdown prompt needed; no Azure infra was
started.

---

## On the horizon

- **Item #44** — fix or at least document the merge-before-label ordering
  requirement more defensively.
- **Item #41** — decide the template/live-instance dual-role question.
- **#38, #39** — still open design calls, no urgency.
- **#40, #42** — clubbable, low-priority, do whenever convenient.
- **Two stale-content review candidates** — flagged, not scheduled.
- **MDP platform swap** — still in progress per the runbook, unaffected by
  this session's work (Item #43 touched `forge-template`/`forge-demo-apps`
  only, not the MDP resources).
- **ADO cleanup** — real Epic/Feature/User Story items from three test
  runs sitting under `spike99/FORGE-Build`, whenever Mike wants to clear
  them.
