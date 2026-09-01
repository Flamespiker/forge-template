# FORGE — Session Context v85

**Session date:** 2026-09-01 (Claude.ai + Claude Code CLI, continued same
day as v84)
**Carries forward from:** v84, unchanged except where noted below.

---

## What changed this session

### Docs folder cleanup and reorg (housekeeping, not a tracked Backlog item)

Following on from the Phase 8 8.1–8.3 work (v84), Mike asked for a review
of everything under `docs/` in the live repo — separate from Phase 8
itself, prompted by noticing genuinely stale/duplicate files sitting
around after the reorg into `docs/ADRs/`, `docs/Archives/`,
`docs/Specs/`, `docs/Templates/`.

**Deletions (superseded/duplicate, verified against live CLAUDE.md
citations before removal):**
- `docs/FORGE_Build_Plan_v10.md`, `docs/FORGE_Build_Plan_v11.md` —
  superseded by v12, zero citations (Build Plan convention: single
  current version, unlike Backlog).
- `docs/FORGE-context_v83.md` — superseded by v84, zero citations (same
  single-current-version convention as Build Plan, confirmed by the fact
  no earlier context versions existed in the repo at all).
- `docs/Specs/FORGE-DeployAgent-ResolveFeaturePR-AdHocFix-Spec.md` (the
  non-`-v2` original) — CLAUDE.md cites only the `-v2` file.
- `docs/ADRs/ADR-0011.md` — a stale duplicate of
  `core/decisions/0011-base-anthropic-client.md` (diffed: same ADR, but
  the `docs/ADRs/` copy still said Documents 2/3/9 "require correction"
  while the `core/decisions/` version correctly says they've already been
  corrected). `docs/ADRs/` is now gone entirely (confirmed — not an empty
  stray directory, not tracked by git).

**Moves (superseded-but-retained content, into the existing Archives
convention rather than sitting loose in `docs/` root):**
- `FORGE-Open-Items-Backlog-v1.md` through `v5.md` → `docs/Archives/`
  (v6 stays in root — it's current). CLAUDE.md's "every Backlog version
  stays" rule was never about *where*; these are exactly the
  superseded-but-retained category Archives already exists for.
- `FORGE-Phase5-Closeout.md` → `docs/Archives/` — same category as the
  `CLAUDE-archive-*.md` files already there.
- CLAUDE.md's Documentation Ownership section corrected to describe the
  new split: current Backlog version at `docs/` root, prior versions in
  `docs/Archives/`.

**Stale-reference cleanup, found and fixed across two follow-up passes:**
- CLAUDE.md:1720 (Item #29 narrative) and `FORGE_Build_Plan_v12.md`
  (three spots: v8 changelog note, two Phase 5 status-prose mentions) —
  path references to `FORGE-Open-Items-Backlog-v2.md` and
  `FORGE-Phase5-Closeout.md` updated to their new `docs/Archives/` paths.
  Committed together as one logical fix (`6aa4d3d`).
- A second, separate stale-reference sweep specifically for the deleted
  `docs/ADRs/ADR-0011.md` found the folder itself fully gone (clean) and
  exactly one dangling reference: `FORGE_Build_Plan_v12.md:122`, a
  "Write the full ADR-0011 text (see ADR-0011.md) into
  core/decisions/0011-base-anthropic-client.md" instruction that became
  self-referential nonsense once the source file no longer existed.
  Judgment call (Claude.ai): reword to drop the dangling parenthetical
  entirely, rather than treat it as historical narrative — this is a
  step in an actionable checklist, not a session diary, so a broken
  pointer there is just broken guidance, not preserved history. A second
  hit, `docs/FORGE-context_v84.md:54`, was deliberately left untouched —
  accurate past-tense narrative in a Claude.ai-owned session diary, not a
  dangling pointer.
- Not touched, by design: `docs/Templates/` (explicit standing
  instruction), `docs/Archives/` contents themselves, every other file
  under `docs/Specs/` (all still cited or the sole version of that spec),
  and the numbered reference docs (`00`–`07`).

**Flagged, not acted on:**
`FORGE-phase-summary-and-training-reference-v2.md` is stale content (frozen
"as of context doc v37," still describes Phases 7–8 as "not yet started"
though both are long done) — not a folder-placement issue, a
content-refresh candidate. Joins `01_FORGE_ProductSpec_v2.md` (flagged in
v84) as a second future-review candidate. Neither scheduled yet.

---

## Open items — updated status

Nothing new opened or closed as a tracked Backlog item — this entire
session was documentation hygiene, not Item-tracked work. Backlog v6
remains accurate as-is; no new version needed.

- **Phase 8, 8.4/8.5:** unchanged from v84 — still next up, still a
  separate session.
- **Two flagged content-review candidates:** `01_FORGE_ProductSpec_v2.md`
  (from v84) and `FORGE-phase-summary-and-training-reference-v2.md` (new
  this session). Neither scheduled.
- **Item #7, #11:** unchanged — deliberately left as-is / accepted ongoing
  risk.

## Azure infrastructure

Nothing Azure-related touched this session — docs/git only. No shutdown
prompt needed.

---

## On the horizon

- **Phase 8, 8.4** — run the setup verification workflow on a fresh
  clone. Separate session, per Mike's earlier sequencing call.
- **Phase 8, 8.5** — tag `v1.0.0`, only after 8.4 passes clean.
- **Two stale-content review candidates** (see above) — flagged, not
  scheduled.
- **Configurable Pipeline Depth** — still unblocked, still not numbered
  or investigated, no urgency.
- **Docs/ layout is now settled**, worth knowing for future prompts to
  Claude Code CLI: `docs/` root holds the numbered reference set (00–07)
  plus the single current version of Backlog, Build Plan, and context
  doc; `docs/Archives/` holds every superseded Backlog version plus
  Phase5-Closeout and the CLAUDE-archive-*.md files; `docs/Specs/` and
  `docs/Templates/` unchanged from the original reorg; `docs/ADRs/` no
  longer exists — `core/decisions/` is the sole ADR home.
