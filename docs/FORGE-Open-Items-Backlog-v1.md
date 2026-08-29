# FORGE — Open Items Backlog: Planning for Next Session(s)

**Prepared:** 2026-08-24 (Claude.ai)
**Purpose:** A working breakdown of all 10 items still open as of context doc v64, sorted by what kind of work each actually needs, so the next session (Claude.ai spec + Claude Code implementation, or a Mike decision alone) can move efficiently instead of re-deriving this each time.

**Reconciled against CLAUDE.md live state as of 2026-08-29; prior version (2026-08-24) was significantly stale on item status.** A future session should treat CLAUDE.md as the source of truth for current item status and not trust this doc's statuses without checking — that's exactly what went wrong the first time.

**This is not itself a set of implementation specs** — items in the "Design/Policy Decisions" section need Mike's judgment before any spec makes sense; items in "Real Bugs" need their own dedicated spec (one at a time, same pattern as the pipeline-hardening spec) once picked; items in "Bookkeeping" are low-effort enough to just do directly without a formal spec cycle.

---

## Design / Policy Decisions — need Mike's call, not a spec

These shouldn't get a Claude Code spec written until Mike has actually decided the direction — writing a spec first would mean guessing at a decision that isn't Claude's to make.

### Item #1 — Deploy Agent has no way to learn an app needs a given secret
The wiring *primitive* (`_wire_keyvault_secret()`) exists and works — the missing piece is how Deploy Agent would ever know, on its own, that a given app needs a given secret in the first place. Every wiring so far has been a manual, one-off CLI invocation. Real options worth Mike weighing:
- A machine-readable declaration convention (e.g. a `secrets.yaml` per service, or a section in `design.md` with a fixed schema Deploy Agent parses)
- Accept this as permanently manual — the primitive exists, tribal knowledge handles the "which secret" question, and that's fine given how infrequently new secrets get introduced
- Something in between (a lightweight convention checked by `_detect_design_gaps()`-style flagging, never blocking)

**Question for Mike:** is this worth solving generally, or is manual-per-secret an acceptable permanent state given how rarely it comes up?

### ~~Item #9 — Ad hoc `fix/*` branches need `--admin` merge (4 occurrences)~~ — RESOLVED 2026-08-27
**Not a real bug — no code fix landed.** Confirmed live via real PR history (per `docs/FORGE-Item9-Item15-AdHocFixDispatch-Spec.md`) that `notify-forge.yml`'s `feature/` prefix match already works correctly for `feature/fix-*`: PR #27 (`feature/fix-appinsights-core-js-dedupe`) dispatched successfully and `security-check` ran for real, returning `SUCCESS`. The 4 original admin-merge cases (PRs #7, #8, #11, #16) all used bare `fix/*`, which *predates* the 2026-08-13 `feature/fix-*` naming convention — they were correctly excluded by design, not a dispatch bug. The remaining risk is purely a human/Claude process one (remembering the naming convention), not something a code fix can close.

### ~~Item #10 — `enforce_admins` on `forge-demo-apps` main is `false`~~ — RESOLVED 2026-08-27
Flipped `false` → `true` via the dedicated `enforce_admins` endpoint (not a full protection PATCH, so nothing else could be touched by construction), on Mike's explicit go-ahead. Confirmed via a `GET` on branch protection immediately before and after: `enforce_admins.enabled` was the only field that changed. Safe to flip now that #9 confirmed the admin-merge pattern wasn't masking a real gap that needed the escape hatch.

---

## Real Bugs — well-scoped, good spec-and-fix candidates

These are genuine, understood problems that just haven't been picked up yet. Any one of these is a reasonable next spec cycle, same pattern as the pipeline-hardening work.

### ~~Item #6 — `wait_for_all_threads_idle()` can't distinguish "finished" from "every thread hit a fatal session error"~~ — RESOLVED 2026-08-26
Per `docs/FORGE-Item6-Item8-Fix-Spec.md`. Two separately-fixable bugs: **6a** (budget exhaustion invisible to idle detection) — added `SessionBudgetExhaustedError`, raised directly off the coordinator's own `status_idle` event via one `get_subagent_audit_trail()` call made only at the point of declaring success, not on every poll iteration; **6b** (archived before validating real output existed) — `run_implementation_stage()` gained an optional `expected_output_filename` check via `list_session_output_files()`, run before `archive_session()`. Commits: `e300ddc` (6a), `24ceb85` (6b). Verified via a 10-case mocked harness covering both bugs plus regression checks on every untouched path. **Deliberately deferred, not performed:** a live, real Stage 3 dry-run end-to-end, on cost/time grounds (Mike's explicit call) — deferred to the first real Stage 3-6 cycle of the next enhancement phase, not skipped permanently.

### ~~Item #8 — Implementation Coordinator sometimes generates unrequested `.github/workflows/*.yml` scope creep~~ — RESOLVED 2026-08-26
Per `docs/FORGE-Item6-Item8-Fix-Spec.md`. Root cause confirmed: `design_agent.py`'s `tasks.md` prompt section put no restriction on what a task item could describe, so nothing told the model CI/CD infrastructure was out of scope. Fixed as a prevention + backstop pair: **Layer 1** (prompt-only) — `tasks.md`'s prompt section now states task items must describe only files under `services/<request-id>/`. **Layer 2** (extraction-time guard) — `_extract_archive_to_file_dict()` skips any archive member with a literal `.github` path segment (exact segment match, not substring, so `mygithubutil/foo.cs` isn't false-flagged). Commits: `78a2f3f` (Layer 1), `5ef29de` (Layer 2). Layer 2 verified via an adversarial local harness with real in-memory tar.gz fixtures; Layer 1 verified via a live single Messages API call against adversarial synthetic requirements text explicitly asking for CI/CD.

### ~~Item #20 — REQ-2026-01's `lib/app-insights.ts:70` Application Insights type conflict~~ — RESOLVED 2026-08-26
Root cause confirmed via `npm ls`: `applicationinsights-react-js@3.4.3` hoists a top-level `core-js@2.8.18` while `applicationinsights-web`'s own tree needs `3.4.3`, resolved as a separate nested copy — a genuine 2.x/3.x type-shape mismatch (`Tags`, `ITelemetryPlugin.setNextPlugin`). Confirmed `applicationinsights-react-js` never actually `require()`s `core-js` at runtime (duck-typed injection instead), so pinning is a type-only change with no runtime risk. Fixed via a `package.json` `overrides` entry pinning `applicationinsights-react-js`'s own `applicationinsights-common`/`core-js` to `3.4.3` — the scoped type-cast fallback wasn't needed. Landed via `forge-demo-apps#27`, merged (`71890f7e239947619cd0d951ee4ebe6b90d7d9a7`). Deploy Stage 6 never fired automatically for this merge (`qa-approved` was never satisfied — 6 pre-existing, unrelated Jest failures blocked it); deliberately deployed manually (same precedent as PR #22), bypassing the `qa-approved` gate on the strength of independent verification (Linux-container `next build` pass, PR #27's own real QA run showing `npm run build` succeeding, `security-approved` reached cleanly). First deploy attempt hit the frontend build's 1800s timeout ceiling; retried once at 3600s (see the now-permanent fix below) and succeeded with zero app changes. Verified live via `az containerapp show` on all 3 units — every image tag matches the fix commit exactly.

### ~~Item #23 — Stage 3 (Implementation) never extended for Enhancement requests~~ — RESOLVED 2026-08-27
Per `docs/FORGE-Item23-Stage3-Enhancement-Spec.md`. `implementation_coordinator.py` previously always resolved `service_root` from the **new** `request_id`, so an Enhancement would have built a brand-new `services/<request_id>/` folder instead of editing the real existing service. Fixed: an `--existing-service` flag resolves the real `services/<existing_service>/` directory when set, raising (Layer 2 precedent from Ingestion Agent) if that folder doesn't exist. Existing-service files seed into the sandbox read-only, then get copied into the real (writable) `service_root` before delegation. Live-verified against `forge-demo-apps#32` (REQ-2026-04 targeting the real REQ-2026-03 service): 19 files changed, all under `services/REQ-2026-03/`, zero files under `services/REQ-2026-04/`.

**Numbering collision, flagged for future cross-reference:** this backlog independently numbered this fix **#23**. CLAUDE.md's own Open Items list separately renumbered the *same fix* **#24** — to avoid colliding with CLAUDE.md's own *different*, unrelated, already-resolved Item #23 ("no on-demand way to verify a service's language build or Docker build," resolved 2026-08-26 via `forge-demo-apps`' `verify-build.yml`). Same fix, two different numbers depending which list you're reading. When cross-referencing between this doc and CLAUDE.md, check the spec filename (`FORGE-Item23-Stage3-Enhancement-Spec.md`) or the commit — not the bare item number.

### ~~Item #27 — `04-qa.yml`'s stale-label-clearing step checked current label presence, not this run's own outcome~~ — RESOLVED 2026-08-28
Found live during Item #25's verification pass. A stale `qa-approved` left over from an earlier run against un-pushed (pre-fix) code was still present when a later, genuinely-fixed run correctly failed and applied a fresh `qa-loop-back` — the cleanup step's `"qa-approved" in labels` check couldn't distinguish "this run just passed" from "qa-approved is merely still sitting there," and deleted the just-applied `qa-loop-back`, leaving the tracking issue showing an incorrect all-clear state. Fixed: `qa_agent.py`'s `main()` now writes this run's real `label_applied` outcome to `$GITHUB_OUTPUT`; the cleanup step gates on that output instead of re-deriving it from current label state. Commit: `5d07169`. Verified via a scoped local test (real `qa_agent.main()`, mocked `run_qa_agent()`).

### Item #28 — Deploy Agent has zero Enhancement-target awareness
Confirmed live 2026-08-28 during Item #25's verification pass: a real dispatch on `forge-template#10`/`forge-demo-apps#32` reached `deploy_agent.py`, which immediately raised `ValueError: No deployable units detected under services/REQ-2026-04/ ... nothing to deploy` — unlike Stage 3/QA/Security, Deploy Agent (`deploy_agent.py`/`06-deploy.yml`) has no concept of an Enhancement request's real existing-service target at all. The failure is safe (fails loud, no wrong Azure resource touched) but the gap is real, not theoretical. Out of scope for Item #25's spec per Mike's explicit instruction not to touch Deploy Agent in that session. Related to, but distinct from, CLAUDE.md's Item #26 (no human gate exists between a feature PR opening and Deploy firing) — both concern Deploy's behavior on this class of request, but this is specifically about target-directory resolution, not about the missing human gate. **Not yet specced.**

### Item #7 — Archive-prefix mismatch (REQ-2026-02, once)
Deliberately left alone per its own note — root cause unconfirmed, only happened once, and REQ-2026-02's infra is decommissioned anyway so this specific instance can't recur on that app. **Recommend leaving this exactly as-is** unless it happens again on a still-live app — not worth investigating a one-off with no reproduction path.

---

## Bookkeeping — no spec needed, just do directly

### ~~Item #12 — Cost log needs REQ-2026-03 figures backfilled~~ — RESOLVED 2026-08-25
Commit `2fa77c2` ("docs: backfill REQ-2026-03 cost log figures (Stages 1/3/4/5/6)") — one day after this backlog was first written, making this entry stale from birth. `docs/FORGE-pipeline-cost-log.md` now carries real, sourced REQ-2026-03 rows for Stages 1 (Requirements), 3 (Implementation), 4 (QA), 5 (Security), and 6 (Deploy, $0 by design) — session IDs and `agent_invocation` log lines cited per row.

### ~~Item #15 — Ad hoc PRs need the tracking-issue body line added manually if not opened by a stage agent~~ — RESOLVED 2026-08-27
Resolved via Option A (process fix), per Mike's explicit choice over Option B (a `resolve_tracking_issue()` code-level fallback, rejected to keep that function's existing contract intact for every other caller). Documented as a standing convention in CLAUDE.md, alongside the `feature/fix-*` branch-naming rule: any ad hoc fix PR must include a `Related FORGE tracking issue: owner/repo#N` line in its body at open time. Per `docs/FORGE-Item9-Item15-AdHocFixDispatch-Spec.md`. No ad hoc PR has been opened since this landed, so it hasn't had an opportunity to recur one way or the other as of 2026-08-29.

---

## Suggested sequencing

**Superseded by the 2026-08-29 reconciliation above** — the original sequencing below assumed a mostly-open backlog; as of this reconciliation only **#1**, **#7**, and **#28** remain open. Kept for historical reference only; do not follow it as a live plan.

1. ~~**Item #20** first~~ — resolved 2026-08-26.
2. ~~**Items #1, #9, #10** — send back to Mike as a batch of decisions before any of them gets a spec.~~ — #9 and #10 resolved 2026-08-27; #1 still genuinely needs Mike's call, standalone now.
3. ~~**Items #6, #8** — need their own diagnosis-first sessions~~ — both resolved 2026-08-26.
4. ~~**Item #12** — fold into whichever of #6/#8 gets picked up next~~ — resolved 2026-08-25.
5. **Items #7, #15** — #15 resolved 2026-08-27; #7 remains leave-as-is per its own note, revisit only if it recurs.

**Current actual state (2026-08-29):** #1 (Mike's decision, standalone) and #28 (needs diagnosis before a spec, same shape #6/#8 used to be) are the only real open work items. #7 is a deliberate leave-as-is.
