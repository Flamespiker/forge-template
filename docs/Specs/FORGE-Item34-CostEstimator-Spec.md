# FORGE — Item #34: Stage 3 Cost Estimator: Spec for Claude Code

**Prepared:** 2026-08-31 (Claude.ai)
**For:** Claude Code CLI session against `forge-template`
**Context:** Scoped in chat 2026-08-29 (five open forks identified, not resolved
that session — see `docs/FORGE-context_v72.md`). All five forks resolved this
session (2026-08-31) via direct Q&A with Mike, grounded in live code already
read this session (`managed_agents_wrapper.py`, `implementation_coordinator.py`,
`03-implementation.yml`, `04-qa.yml`'s label-gate pattern, `team/config.yaml`,
`docs/FORGE-pipeline-cost-log.md`'s real actuals). This spec authors the design;
Claude Code CLI should still re-verify every cited line against the live repo
before editing, per standing convention — this describes intended behavior, not
a guaranteed current line-by-line diff.

**Standing conventions to follow (per `CLAUDE.md` / context doc):**
- Verify against live reality before editing.
- Report any design fork this spec didn't anticipate back to Mike rather than
  resolving it silently.
- Confirm before any first-time action with Azure consequences — not expected
  to apply here (this is Anthropic API + GitHub only), but flag if it does.
- Smoke-test before committing; commit each logical change separately.
- Both greenfield and enhancement paths must work — see §2.1 and §2.2.

---

## 1. Background — why tasks.md alone isn't the estimate

Real Stage 3 actuals (`docs/FORGE-pipeline-cost-log.md`, 8 sessions) range
**$3.04–$12.31**, 18–55 min active duration, with no clean correlation to any
single number available before the coordinator session starts. The dominant
cost driver is **cache-read/cache-creation token volume**, not turn count.

Two real, pre-flight-knowable signals correlate with that volume:

1. **Unit count from `tasks.md`** — single-unit (backend-only, e.g.
   `DRYRUN-2026-01`) runs cluster cheaper than multi-unit (backend+frontend)
   runs. `implementation_coordinator.py`'s own
   `_sanity_check_extracted_files()` already does a case-insensitive
   `"backend"`/`"frontend"` substring check against `tasks_md` — the same
   detection this spec reuses for the estimate.
2. **Enhancement seed size** — for Enhancement requests,
   `_resolve_enhancement_target()` already computes
   `select_existing_service_files()`'s file list *before* the session is
   created (existing code, `implementation_coordinator.py` lines resolving
   `resources`). This is a real, already-computed number driving
   cache-creation cost for Enhancement runs — currently computed and used to
   build `resources[]`, but never surfaced as a cost signal.

**Resolved (Mike, 2026-08-31): the estimate combines both signals plus a
historical baseline for the closest-matching shape** — not `tasks.md` alone.
See §2.1 for the exact formula.

---

## 2. Scope

### 2.1 Pre-flight estimate: `_estimate_implementation_cost()`

**New function in `implementation_coordinator.py`**, called after `tasks_md` is
fetched and (for Enhancement requests) after `_resolve_enhancement_target()`
resolves `resources`, but before the Managed Agents session is created.

**Inputs:**
- `tasks_md` (already fetched) — reuse the existing `"backend"`/`"frontend"`
  substring check pattern from `_sanity_check_extracted_files()` to derive
  `unit_count` (1 if only one of backend/frontend appears, 2 if both; Test
  Writer is not counted separately since it never runs without at least one
  of the other two).
- `resources` (already computed for Enhancement requests, `[]` for
  Greenfield) — `enhancement_seed_file_count = len(resources)`.
- Historical actuals from `docs/FORGE-pipeline-cost-log.md`'s Implementation
  table — hardcode the shape-bucketed averages as constants for now (see
  below); do not attempt to parse the markdown table at runtime, that's
  needless fragility for a one-time input.

**Formula (simple, explainable, not a black box):**
- Bucket by shape: `(unit_count, is_enhancement)` → one of four buckets:
  `(1, False)`, `(2, False)`, `(1, True)`, `(2, True)`.
- **Confirmed live data (Claude Code CLI investigation, 2026-08-31):** every
  logged Stage 3 actual to date is 2-unit (REQ-2026-01/02/03/04 all have both
  `## Backend` and `## Frontend` in `tasks.md`) — zero real precedent exists
  for either 1-unit bucket, not just `(1, True)` as originally assumed.
  Confirmed baselines:
  - `(2, False)`: mean of REQ-2026-01 ($12.31), REQ-2026-02 ($6.63),
    REQ-2026-03-recovered ($7.95) → **$8.96**
  - `(2, True)`: REQ-2026-04/PR#32 only real data point → **$4.57** (87 seed
    files — confirmed via live tool-use events, session
    `sesn_01GBkGBfEYEBLJLcc9Ftyqhv`)
  - `(1, False)` and `(1, True)`: **no real data. Resolved (Mike,
    2026-08-31): scale the same-enhancement-status 2-unit baseline by a
    fixed 0.5x ratio**, explicitly labeled low-confidence in the posted
    comment (e.g. "no single-unit precedent exists yet — this is a rough
    0.5x scale-down of the 2-unit baseline, not a real historical average.
    Treat with extra skepticism.").
  - `_COST_BASELINES_USD = {(2, False): 8.96, (2, True): 4.57, (1, False):
    8.96 * 0.5, (1, True): 4.57 * 0.5}` — revisit all four constants (not
    just the scaled pair) once more real runs land, especially `(2, True)`'s
    single-data-point mean.
- **Enhancement adjustment:** when `is_enhancement`, scale the baseline by
  `1 + (enhancement_seed_file_count / 87)` — `87` is the confirmed real seed
  file count from the corrected REQ-2026-04/PR#32 run (session
  `sesn_01GBkGBfEYEBLJLcc9Ftyqhv`, verified via live tool-use events, same
  count as the earlier interrupted attempt since the mount-path bug only
  affected file resolution, not the selection list). Note this reference
  seed size is itself a single data point — the same low-confidence caveat
  that applies to the `(2, True)` baseline above applies here.
- Round to nearest $0.50 and present as a range (baseline ± 25%), not a false-
  precision single number — the whole point of this estimate is to inform a
  yes/no call, not to be exact.

**This is a real design decision the code should make explicit in a comment:**
this is a coarse, shape-bucketed heuristic, not a trained model — it will get
better as `_MODEL_RATES`-adjacent historical data accumulates (see §2.4), and
should be revisited once more Enhancement runs exist to calibrate against.

### 2.2 Gate: new `cost-approved` label

Mirrors `design-approved`'s existing role exactly, but as a **second required
label alongside `design-approved`** for the real coordinator run — not a
replacement. Two moving pieces:

**A. New estimate-only step, triggered by `design-approved` landing (before
`cost-approved` exists):**
- `03-implementation.yml` needs a new job (or a new early step in the existing
  job, gated by a check of whether `cost-approved` is already present) that:
  1. Resolves `request_id` and `existing_service`/Enhancement status exactly
     as the existing "Resolve request ID" / "Determine Enhancement status"
     steps already do (reuse, don't duplicate).
  2. Fetches `tasks.md` and (for Enhancement) computes `resources` the same
     way `_resolve_enhancement_target()` does — **this means the estimate
     step calls `_resolve_enhancement_target()`'s file-listing logic without
     actually uploading files via `upload_input_file()`** (uploading costs
     nothing but is wasted work if the estimate leads to a "no"). Consider
     factoring `select_existing_service_files(get_repo_tree(...))`'s call out
     of `_resolve_enhancement_target()` into a small helper both the estimate
     step and the real resolve step can share, so this isn't a forked
     duplicate implementation as the real one changes over time — a real
     design decision to flag if it turns out messier than expected; if
     factoring it out cleanly isn't feasible, duplicating the read-only
     tree/file-list call is acceptable since it's cheap and side-effect-free.
  3. Calls `_estimate_implementation_cost()`.
  4. Posts the estimate as a tracking-issue comment (new function,
     `_build_cost_estimate_comment()`, same posting mechanism as every other
     agent comment) — this comment is the human's basis for the yes/no call.
     Do **not** apply any label from this step; the human applies
     `cost-approved` manually, same action model as `design-approved` itself.

**B. Real coordinator dispatch, now requires BOTH labels:**
- `03-implementation.yml`'s trigger stays `issues: types: [labeled]`, but the
  guard clause step must now check **both** `design-approved` AND
  `cost-approved` are present before proceeding — same AND-gate shape as
  Item #26's Deploy fix (`qa-approved` + `security-approved`), not a new
  pattern. If `cost-approved` lands first (shouldn't normally happen since
  the estimate step is what a human bases the label on, but the workflow
  can't prevent it), the guard should still just check both labels are
  present at that instant, same as the existing single-label check does
  today — order of arrival doesn't matter, only current state.
- On successful dispatch, clear **both** `design-approved` and
  `cost-approved` (mirrors the existing single-label clear today, extended to
  both).

**No stored threshold anywhere** (Mike, 2026-08-31) — this is purely
informative. The estimate comment should say so explicitly (e.g. "This is an
estimate only, not a hard limit — review and apply `cost-approved` to
proceed, or investigate further if this looks high for the scope.").

### 2.3 Post-run reporting: extend the existing comment, don't add a new one

**`_commit_and_open_pr()`'s existing comment_body** (in
`implementation_coordinator.py`) gains a new section, appended the same way
`secrets_flag_section` already is conditionally appended — when a pre-flight
estimate was made for this request, show estimate vs. actual:

```
### 💰 Cost estimate vs. actual
Estimated: $X.XX–$Y.YY (bucket: <shape>)
Actual: $Z.ZZ (from this session's usage)
```

This requires threading the estimate value from the `03-implementation.yml`
estimate step through to `implementation_coordinator.py`'s real run — simplest
approach: post it as a hidden marker in the estimate comment (matching the
existing `<!-- forge:agent-comment ... -->` convention every other agent
comment already uses) and have `implementation_coordinator.py` re-fetch and
parse that one comment by its marker before building the final comment,
rather than piping it through as a new CLI arg/env var across two separate
workflow steps that don't share state today. Flag to Mike if this parsing
approach turns out fragile in practice — the CLI-arg/env-var alternative is
available if so.

Actual cost: `usage.list_cost.amount` from `GET /sessions/{id}` (already
confirmed live, per the cost log's units note — cents, not dollars, divide by
100), fetched via `get_session_resource_ids()` (already returns `usage`) after
`run_implementation_stage()` completes, same place `final_status` is already
fetched in `run_implementation_coordinator()`.

### 2.4 Post-run reporting: close the cost-log automation gap

**New structured log line**, same pattern as every Messages-API stage's
existing `"forge_event": "agent_invocation"` line
(`claude_agent_wrapper.py`) — add an equivalent for Stage 3 in
`managed_agents_wrapper.py`'s `run_implementation_stage()`, right after
`final_status` is fetched:

```python
log_entry_cost = {
    "forge_event": "managed_agents_cost",
    "stage": "implementation",
    "session_id": session_id,
    "usage": final_status.get("usage"),
}
print(json.dumps(log_entry_cost), flush=True)
```

This closes the gap `FORGE-pipeline-cost-log.md` §4.2 already flags ("no
automatic equivalent yet... queued but not yet built") — future cost-log
updates can grep this line the same way Messages-API stages' rows are already
transcribed, instead of a manual Console visit. Does not itself update the
cost log file — that's still a separate, periodic bookkeeping pass (per
existing Item #12-style backfill convention), just no longer blocked on
manually finding the number.

---

## 3. Both workflows — explicit greenfield/enhancement coverage

- **Greenfield:** `unit_count` from `tasks.md` only; `enhancement_seed_file_count
  = 0`; bucket is `(unit_count, False)`; no seed-size adjustment applied.
  Confirm the estimate step's Enhancement-detection reuses the exact same
  `workflow_glue`/`file_io` parsing `03-implementation.yml`'s existing
  "Determine Enhancement status" step already uses, so a Greenfield request
  never accidentally takes the Enhancement branch.
- **Enhancement:** `unit_count` from `tasks.md`; `enhancement_seed_file_count`
  from the real (or estimate-step-duplicated, per §2.2.A.2) seed file list;
  bucket is `(unit_count, True)`; seed-size adjustment applied. Confirm the
  estimate step's `existing_service` resolution matches
  `_resolve_enhancement_target()`'s own strict-rejection behavior (raise if
  the named service doesn't exist) rather than silently falling back to
  Greenfield bucketing on a resolution failure — a wrong/mistyped existing
  service name should surface as its own failure here too, same philosophy
  as Item #23/§2.1's existing guard.

---

## 4. Investigation checklist before writing code

1. **Confirm `GET /sessions/{id}`'s `usage` field shape** while a session is
   NOT yet idle — not required for this spec (post-run reporting only reads
   it after completion), but worth a quick live check in case a future
   mid-session cost check is ever wanted; do not build mid-session checking
   now, it's out of scope (see §5).
2. **Verify the real REQ-2026-04 Enhancement seed file count** (§2.1's
   `<reference_seed_size>`) against live `select_existing_service_files()`
   output for the corrected (post-mount-path-fix) PR #32 run, not the
   earlier failed/interrupted attempts — confirm via the Managed Agents
   session's actual resources list or the `upload_input_file()` call count
   in that run's log, not assumption.
3. **Confirm current `03-implementation.yml` guard-clause structure** can
   cleanly extend to a two-label check without restructuring the whole
   workflow — likely a small diff (see Item #26's own two-label precedent in
   `06-deploy.yml` for the exact shape to mirror).
4. **Confirm the hidden-comment-marker parsing approach (§2.3)** is workable
   given `post_comment()`/`get_issue()`'s existing helpers in
   `github_helper.py` — check whether a marker-based re-fetch-and-parse
   pattern already exists elsewhere in the codebase to reuse, or if this
   would be the first instance.

Report back before proceeding if any of these surface a genuine blocker, per
standing convention.

---

## 5. Out of scope

- **Mid-session cost breach checking/killing** — not requested (no threshold
  exists at all, per Mike's decision). Do not build any accumulating-cost
  check during a live session.
- **`team/config.yaml` changes** — no threshold means no configurable value
  to store. Do not add a cost-estimator section to team config.
- **Automating the cost-log file update itself** — §2.4 only adds the log
  line; actually transcribing it into `FORGE-pipeline-cost-log.md` stays a
  manual/periodic bookkeeping pass, same as today.
- **Retroactively estimating past runs** — the four historical actuals are
  used only to seed `_COST_BASELINES_USD`'s constants, not re-estimated
  themselves.
- **Extending this pattern to any other stage** — Messages-API stages already
  have predictable, already-logged costs; this is Stage 3-only, per the
  original 2026-08-29 scoping decision.

---

## 6. Sequencing

1. Verify §4's investigation items live, especially #2 (the reference seed
   size) and #3 (guard-clause extension shape) — both are load-bearing for
   the rest of this spec.
2. `_estimate_implementation_cost()` + `_COST_BASELINES_USD` constants in
   `implementation_coordinator.py` — build and unit-test against the shape
   buckets independent of any workflow wiring.
3. `03-implementation.yml`'s new estimate step + two-label guard-clause
   extension — smallest, most mechanical piece once the estimate function
   works standalone.
4. `_build_cost_estimate_comment()` + hidden-marker posting.
5. `implementation_coordinator.py`'s comment-parsing to surface estimate vs.
   actual in the existing post-run comment (§2.3).
6. `managed_agents_wrapper.py`'s new `managed_agents_cost` log line (§2.4) —
   independent of everything else, can be done in any order relative to 2-5.
7. Full-chain live test: one real or throwaway Greenfield request AND one
   real or throwaway Enhancement request, confirming both bucket correctly,
   both labels gate correctly, and the post-run comment shows estimate vs.
   actual for both.
8. `CLAUDE.md` close-out — new Item #34 entry, cross-reference from the
   Backlog.
