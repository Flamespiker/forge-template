# FORGE — Session Context v86

**Session date:** 2026-09-01 (Claude.ai + Claude Code CLI, continued same
day as v84/v85)
**Carries forward from:** v85, unchanged except where noted below.

---

## What changed this session

### Backlog v9 discovered ahead of CLAUDE.md/Build Plan — reconciled

At session open, Mike pointed to `docs/FORGE-Open-Items-Backlog-v9.md` on
GitHub, which turned out to be substantially ahead of both CLAUDE.md and
`FORGE_Build_Plan_v12.md` (both still showed 8.4/8.5 unchecked, no Item
#35-#42 entries). Investigated and confirmed real (not hallucinated):
Backlog v9 reflected work done in a session after v85 closed — 8.4 had
actually run, hit a real bug, gotten fixed, and passed on retest.

Verified via live GitHub API/pages before trusting anything in the
backlog text: commit SHAs `53b3fd5`, `baddc8c`, `d40b761`, `5b8ace6`,
`71424df` all confirmed as real ancestors of `main` (`behind_by: 0`
each).

Dispatched Claude Code CLI to reconcile CLAUDE.md and Build Plan v12
against Backlog v9. CLI caught a discrepancy in the reconciliation
prompt itself before writing anything: the run URL cited for the
fresh-clone verification (`.../forge-template/actions/runs/33547029934`)
actually belonged to the scratch repo `forge-8-4b-scratch` (since
deleted), not `forge-template` — a 404 when queried against the real
repo. CLI used the correct URLs throughout rather than propagating the
error. This is the two-tool split and investigation-first discipline
working as intended.

**Reconciliation commits (all direct to `main`, unprotected, verified
via API):**
- `64ded5c` — Build Plan: checked off 8.4, fixed stale "8.4 and 8.5
  remain unchecked" top-of-file note
- `adde747` — CLAUDE.md: Phase 8 status line updated to "8.1-8.4
  complete; 8.5 pending," full narrative of Items #35/#36/#37 and the
  two-pass verification (real 404 → fixed → fresh-clone retest against
  a genuinely different target proving real `${{ vars.* }}` indirection,
  not coincidence)
- `97aa752` — CLAUDE.md: Open Items #35-#42 added per Backlog v9 (#35,
  #36 resolved; #37 investigated/not-a-bug; #38-#42 open, matching
  existing resolved/open-item formatting conventions)

### 8.5 — `v1.0.0` tagged

Immediately following reconciliation, ran 8.5. Pre-checks: confirmed
`main` HEAD via API matched local checkout exactly (no stale-copy risk),
confirmed the three reconciliation commits were ancestors, confirmed no
`v1.0.0` tag already existed.

**Tag created:** annotated tag `v1.0.0` on commit `97aa752` (tag object
`a355aac`), message "FORGE v1.0.0 — first stable release, Phase 8
(Handoff Readiness) complete." Pushed to `origin`, verified via three
separate API reads (`GET .../tags`, `GET .../git/ref/tags/v1.0.0`
confirming `"type":"tag"` — genuine annotated object, not lightweight —
and `GET .../git/tags/{sha}` confirming the tag's own message and target
commit).

**Follow-up commits:**
- `bf29a96` — Build Plan: 8.5 checked off with tag/SHA/verification
  detail
- `d3338a4` — CLAUDE.md: Current Build Phase now states Phase 8 fully
  complete (8.1-8.5), notes `v1.0.0` SHA

**Phase 8 (Handoff Readiness) is now fully complete.** FORGE has its
first stable tagged release.

---

## Open items — updated status

- **Item #41 (open, design decision)** — `forge-template`'s `is_template:
  true` conflates Mike's live instance with the public template source;
  `team/config.yaml`'s real `spike99`/`FORGE-Build` `ado:` block values
  get copied verbatim into every new "Use this template" instantiation.
  No urgency, but explicitly deferred this session in favor of tagging
  `v1.0.0` first. Worth deciding before external template users show up
  in volume, since it's now a first-stable-release-adjacent question,
  not purely hypothetical.
- **Item #38, #39** — unchanged, still open design calls.
- **Item #40, #42** — unchanged, low-priority/clubbable bookkeeping.
- **Item #7, #11** — unchanged, deliberately left as-is / accepted
  ongoing risk.
- **Two stale-content review candidates** (from v84/v85):
  `01_FORGE_ProductSpec_v2.md`, `FORGE-phase-summary-and-training-
  reference-v2.md` — still flagged, still not scheduled.
- **Configurable Pipeline Depth** — still unblocked, still un-numbered,
  no urgency.

## Azure infrastructure

Nothing Azure-related touched this session — reconciliation and tagging
were docs/git only. No shutdown prompt needed.

---

## On the horizon

- **Item #41** — decide the template/live-instance dual-role question.
  Now more relevant given `v1.0.0` is tagged and the repo may see wider
  use.
- **#38, #39** — still open design calls, no urgency.
- **#40, #42** — clubbable, low-priority, do whenever convenient.
- **Two stale-content review candidates** — flagged, not scheduled.
- **Configurable Pipeline Depth** — still unblocked, still un-numbered.
- **Post-v1.0.0 housekeeping question (new, not yet raised with Mike):**
  now that Backlog reached v9 mid-session and outran the trackers once,
  worth considering whether Backlog should be checked against
  CLAUDE.md/Build Plan explicitly at the *start* of future sessions
  (not just assumed synced) — this session's opening move (reading v85
  first, then finding v9 ahead of it) is what caught the gap, so the
  existing "read context doc + CLAUDE.md at session start" convention
  held up, but it's worth flagging that a live-repo Backlog check could
  usefully join that same opening routine going forward.
