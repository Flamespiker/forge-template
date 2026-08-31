# FORGE — Session Context v79

**Session date:** 2026-08-30 (Claude.ai)
**Carries forward from:** v78, unchanged except where noted below.

---

## What changed this session

### 1. Item #12 — cost log fully backfilled (resolved)

REQ-2026-03 actuals (original build + the #24–#28/#30 fix cycle) pulled from
the Managed Agents session cost endpoint and added to
`docs/FORGE-pipeline-cost-log.md`, matching the existing REQ-2026-02 entry
format.

**Total cost, all stages/requests to date: $57.64** (up from $44.55):
- REQ-2026-03 original build (Aug 14–25): ~$17.39
- Items #24–#28/#30 fix cycle (REQ-2026-04, existing service REQ-2026-03,
  Aug 27–29): ~$13.08, of which Implementation (3 Managed Agents sessions)
  is $12.53 — by far the dominant cost, as expected.

**Commits:**
- `103c9274` — cost-log data backfill
- `3ff8af3d` — CLAUDE.md Item #12 + Open Items Backlog v2 closeout

**Surprises surfaced during the pull (all real, all logged):**
1. **Stale-code incident happened twice, not once.** CLAUDE.md's Item #25
   narrative described a single re-dispatch against un-pushed code; logs
   showed the identical pre-fix failure mode (QA false-passing, Security
   crashing with a raw `FileNotFoundError`) on both the 03:55 and 22:27 runs
   on 2026-08-28. Narrative gap flagged, not yet corrected in CLAUDE.md
   itself (see "still open" below).
2. **Session-ID mismatch found and fixed** (see #2 below).
3. **GitHub Actions minutes are structurally $0** for `forge-template` since
   it's a public repo — confirmed directly, not assumed. Worth remembering
   for any future cost analysis: Actions-minutes cost will never appear for
   this repo regardless of run length.
4. **Sessions API's `list_cost.amount` field is in cents, not dollars**
   (e.g. `"492"` → $4.92) — verified by reconstructing cost from raw token
   counts against the rate table, and cross-checked against the three
   already-logged REQ-2026-02/03 sessions to confirm the same convention was
   used there too (it was — no retroactive correction needed).
5. **A real, non-Anthropic cost surfaced**: a stray `req-2026-04-*` Container
   App from the pre-push run was briefly live in Azure before being deleted.
   Noted in the cost log but explicitly out of scope for that
   Anthropic-API-focused ledger — flagging here too in case it's relevant to
   any future Azure cost reconciliation.

### 2. CLAUDE.md session-ID discrepancy — fixed

CLAUDE.md's "Manually killing a runaway Managed Agents session" walkthrough
cited `sesn_01AbaBvHhDkLpkRPHRFdrFLF` for the mount-path-bug kill. The actual
`03-implementation.yml` run that hit that bug used
`sesn_01MwLQkRnUCb54aguyJLknvX` (confirmed 15 times in that run's log).

**Fixed:** commit `4b0438cf` — CLAUDE.md:1476 corrected. A second occurrence
was found in `docs/FORGE-pipeline-cost-log.md:75` (a note flagging the
original discrepancy) — reworded rather than blind-replaced, to avoid a
self-contradictory sentence, while preserving the historical record of what
the wrong ID was. No other occurrences existed anywhere else in the repo.

### 3. CLAUDE.md date discrepancy — fixed

Same runaway-session section incorrectly dated the incident 2026-08-27; real
evidence (GitHub Actions run `33136955162` `created_at: 2026-08-28T02:47:11Z`,
and the session's own `created_at`/`archived_at` timestamps) confirmed
2026-08-28.

**Fixed:** commit `e0342d72` — CLAUDE.md lines 1475, 1513, 1541 corrected.
Repo-wide grep for other references to this specific incident (via session
ID and run number) found none outside CLAUDE.md and the already-correct
cost-log entry. The other 35 unrelated `2026-08-27` hits in the repo (Items
#9/#15/#16, Ingestion Agent verification, REQ-2026-04 rows, backlog docs)
were confirmed correctly-dated and left untouched.

---

## Open items — updated status

- **Item #1:** unchanged from v78 — discovery/prevention gap remains open,
  revisit only if Mike decides it's worth building.
- **Item #12:** **now resolved** (this session). Remove from "open" going
  forward.
- **Cost Estimator spec:** unchanged, not yet started.
- **`req-2026-01-email-worker` crash-loop:** unchanged, still pre-existing
  and unfixed.
- **Phase 7 end-to-end Enhancement Workflow validation run:** unchanged from
  v78 — still worth a dedicated fresh-intake pass if Mike wants the full
  pipeline exercised beyond the v78 replay-based test.
- **NEW — Item #25 narrative gap:** CLAUDE.md's Item #25 write-up describes
  the stale-code re-dispatch incident as happening once; live log evidence
  (surfaced during this session's cost pull) shows it happened twice, on
  both the 03:55 and 22:27 runs on 2026-08-28. Not yet corrected — flagged
  here as a small candidate for a future clubbed session, same pattern as
  this session's two fixes.

## Azure infrastructure

Nothing started this session — all work was doc/log edits and read-only API
calls (GitHub API, Managed Agents session cost endpoint). No shutdown
prompt needed. Postgres (`forge-req2026-03-pg`) was not touched.

---

## On the horizon (unchanged from v78, plus the new item above)

- Cost Estimator spec — five open design forks, not yet started
- A dedicated Phase 7 validation run from a genuinely fresh intake
- Item #25 narrative-gap correction (small, clubbable — new this session)
- Ongoing Open Items Backlog discipline
