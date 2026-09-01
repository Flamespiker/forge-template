# FORGE — Session Context v84

**Session date:** 2026-09-01 (Claude.ai + Claude Code CLI)
**Carries forward from:** v83, unchanged except where noted below.

---

## What changed this session

### Phase 8 opened — 8.1, 8.2, 8.3 complete (Handoff Readiness)

Picked up from v83's "on the horizon" — Phase 8 is next on the Build Plan
after Item #34 fully closed out the backlog. Investigation pass (Claude.ai)
against the live repo found the real scope was bigger than "final review"
implied for one of the three steps:

**8.1 — Document 6 (Orchestration Manager Guide), v6 → v7.** Investigation
found the doc had zero coverage of the Enhancement workflow (no Stage 0a,
no `existing_service` targeting, no ADO Epic linkage), no mention of the
Cost Estimator (`cost-approved`, Item #34), an inaccurate Gate 6 (didn't
reflect the Item #26 confirmed-merge requirement), no mention of the
post-deploy crash-loop health check (Item #1), and two stale "Claude Agent
SDK" references left over from before ADR-0011 moved six of seven stages
to the base `anthropic` client. All fixed: new "Enhancement vs. Greenfield
Requests" section, new Gate 2.5 (cost approval), corrected Gate 6, Label/
File Reference table updates, corrected Failure Handling.

**8.2 — Document 7 (Customization Reference), v3 → v4.** Same SDK
correction (two references); new Locked rows for the cost-approval gate,
Enhancement-target resolution, the post-deploy health check, and the
confirmed-merge Deploy requirement.

**8.3 — ADRs in `core/decisions/`.** Investigation found only 2 of 11 were
real (ADR-0008, ADR-0011) — the other nine (0001–0007, 0009, 0010) were
still literal `_(To be written)_` stubs, despite being cited elsewhere in
the doc set as if complete. Wrote real Context/Decision/Consequences
content for all nine, sourced from the architecture doc, Governance doc,
and CLAUDE.md rather than invented — each reflects what was actually
decided and why, including later amendments (e.g. ADR-0004's 2026-08-19
Dependabot swap, ADR-0002's ADR-0010 clarification).

**Execution (Claude Code CLI):** verified all drafts against live
CLAUDE.md state before landing (no drift found); confirmed the nine ADRs
were still genuine stubs before overwriting; confirmed `forge-template`'s
`main` is unprotected (direct commits, no PR needed for these doc-only
changes). Five commits: `566ab53` (Mike's docs/ reorg — ADRs/Archives/
Specs/Templates subfolders, confirmed byte-identical pure moves),
`61f52c0` (nine ADRs), `c98fe38` (Doc 6 v7), `b27eb1f` (Doc 7 v4), `3c9f58d`
(CLAUDE.md Phase 8 checklist entry). Pushed to `origin/main` on Mike's
confirmation.

**One real fork surfaced and resolved:** the reorg had briefly staged
copies of the nine new ADRs in `docs/ADRs/` alongside the pre-existing
`docs/ADRs/ADR-0011.md`, raising the question of whether `docs/ADRs/`
should become a second permanent human-readable ADR home. Resolved (Mike,
agreeing with Claude Code CLI's own reasoning): no — `core/decisions/`
remains the one real ADR home per Document 7's own "ADR storage location"
row, and a second permanent copy would recreate the doc-duplication/
staleness problem CLAUDE.md already warns about. The staging copies in
`docs/ADRs/` were deleted after copying into `core/decisions/`.

**Not touched, flagged for a future session:** `01_FORGE_ProductSpec_v2.md`
— Mike flagged it as "maybe needs review" mid-session, but it's outside
Phase 8's defined scope (8.1/8.2 name only Documents 6 and 7). Left as a
candidate, not pulled into this session.

---

## Open items — updated status

- **Phase 8, 8.1–8.3:** **complete.** No new open items surfaced beyond
  the ADR-location question above, which is resolved, not outstanding.
- **Phase 8, 8.4 (setup verification on a fresh clone) and 8.5 (tag
  `v1.0.0`):** unchanged — next up, deliberately a separate session per
  Mike's sequencing call at the top of this session.
- **`01_FORGE_ProductSpec_v2.md` review:** new candidate, not numbered or
  scheduled. Mike's own words: "maybe it needs review."
- **Item #7, #11:** unchanged — deliberately left as-is / accepted ongoing
  risk.
- Everything else carried from v83 unchanged.

## Azure infrastructure

Nothing Azure-related touched this session — doc/ADR authorship and a git
reorg only. No shutdown prompt needed.

---

## On the horizon

- **Phase 8, 8.4** — run the setup verification workflow (Build Plan
  2.8–2.9) on a fresh clone. Separate session, per Mike's call.
- **Phase 8, 8.5** — tag `v1.0.0`, only after 8.4 passes clean.
- **`01_FORGE_ProductSpec_v2.md` review** — flagged, not scheduled.
- **Configurable Pipeline Depth** — still unblocked from v83, still not
  numbered or investigated, no urgency.
- Documentation Ownership discipline continues to hold — this session's
  own reorg (`docs/adr/`, `docs/archive/`, `docs/templates/`,
  `docs/specs/`) is new structure worth carrying forward in mind when
  referencing file paths in future prompts to Claude Code CLI, since
  several documents in this project's own knowledge base may now be
  stale relative to the new layout until Mike re-syncs it.
