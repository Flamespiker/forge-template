# FORGE — Pipeline Cost & Stage Log

**Purpose:** A running ledger of where cost is actually incurred in the FORGE pipeline, and what each real invocation of each stage has actually cost. This is separate from Document 3 (which estimates cost for planning/procurement purposes) and separate from `FORGE-context_vN.md` (which is chat-continuity, not a data record). This file is the one place actuals accumulate over time; Document 3 should eventually cite it rather than re-derive estimates once enough runs exist.

**Maintenance:** Append a new row to the relevant stage's table after every real (non-dry-run) invocation. Dry runs are worth recording too if they're the only data point for a stage, but mark them clearly as dry runs — they don't include commit/PR/comment steps and can run cheaper or more expensive depending on the stage. This file lives in `forge-template` at `docs/FORGE-pipeline-cost-log.md` and is committed like any other doc — not gitignored, not local-only.

---

## 1. Pipeline Stage → Cost Mechanism Reference

| Stage | Agent | Invocation Mechanism | Cost Model | Auto-Logged? |
|---|---|---|---|---|
| Intake | `intake_agent.py` | `anthropic` Messages API (single-turn, ADR-0011) | Per-token (input/output) | ✅ `forge_event: agent_invocation` JSON line, `claude_agent_wrapper.py` |
| Ingestion (Stage 0a, Enhancement only) | `ingestion_agent.py` | Messages API (single-turn) — conditional step inside `00-intake.yml`, only fires for Enhancement-flagged requests | Per-token | ✅ same |
| Requirements | `requirements_agent.py` | Messages API (single-turn) | Per-token | ✅ same |
| Design (Spec & Design) | `design_agent.py` | Messages API (single-turn) | Per-token | ✅ same |
| **Implementation** | `implementation_coordinator.py` + Backend/Frontend/Test Writer subagents | **Anthropic Managed Agents** (ADR-0010), separate mechanism from the Messages API | Per-token (input/output/cache read/cache write) **+ $0.08/session-hour active runtime** | ❌ **No equivalent to `agent_invocation` exists yet** — cost data currently requires a manual pull from the Claude Console session detail page (`usage` object) or `GET /v1/sessions/{id}` (not yet confirmed to return it — open item from chat 28). This is a real automation gap; every row below for Stage 3 was hand-copied from the Console. **Update 2026-08-11: `GET /sessions/{id}`'s own `usage` object DOES carry this — confirmed live pulling REQ-2026-02's numbers directly from the API with no Console visit, closing this open question.** Still no `agent_invocation`-equivalent auto-logged line — a manual pull is still required, just no longer a Console-only one. |
| QA | `qa_agent.py` | Messages API (single-turn) | Per-token | ✅ same |
| Security | `security_agent.py` | Messages API (single-turn) — invokes Semgrep/Gitleaks/OWASP Dependency-Check directly as local CLI subprocesses, not GitHub Actions marketplace steps (real architecture deviation from Document 3's original description, flagged chat 32 — not corrected here, separate Document 3 pass needed) | Per-token | ✅ same |
| Deploy | `deploy_agent.py` | **No Claude/Messages API call.** Unit detection, Dockerfile generation, and PR commenting are fully deterministic (string/template logic) — same "keep structural output out of the model's hands" pattern as QA's severity classifier and Security's severity tables, taken one step further. | **$0 Anthropic API cost, always** | N/A — nothing to log |

**GitHub Actions minutes are $0 for every stage, always (confirmed 2026-08-31):** `forge-template` is a **public** GitHub repo (`gh repo view Flamespiker/forge-template --json visibility` → `PUBLIC`), and public repos get unlimited, unbilled Actions minutes. Confirmed directly against the REQ-2026-04/Items #24–#28/#30 fix-cycle runs below via `GET /repos/{owner}/{repo}/actions/runs/{id}/timing` — every single run (including a 27.6-minute real `03-implementation.yml` job) returned `"billable":{"UBUNTU":{"total_ms":0}}`. This is a real, structural $0, not an unmeasured gap — no further Actions-minutes tracking is needed in this log as long as the repo stays public. Wall-clock job duration is still worth recording (via `run_duration_ms`) purely as a timing reference, same role the existing "Duration" column already plays for Messages-API stages.

**Model tier split (ADR-0010):** Stage 3's coordinator runs on the Opus tier; Backend/Frontend/Test Writer subagents run on the Sonnet tier (`FORGE_COORDINATOR_MODEL` / `FORGE_SUBAGENT_MODEL`). All other stages currently default to Sonnet 4.6 (see `_MODEL_RATES` in `claude_agent_wrapper.py`).

**Known caching asymmetry:** Stage 3 caches automatically at the Managed Agents session level with no `cache_control` set anywhere in `managed_agents_wrapper.py` — cache reads have dominated the token bill by four orders of magnitude over fresh input in both runs recorded below. The six Messages-API stages currently cache **zero** tokens on every call (no `cache_control` set in `claude_agent_wrapper.py` either) — a queued, not-yet-actioned follow-up from chat 28/29 is adding it there, which should show up as a visible drop in per-run cost for those stages once done. Worth watching this log for that change when it lands.

---

## 2. Per-Run Actuals

### Intake — `intake_agent.py`

| Date | Request ID | Run Type | Input Tok | Output Tok | Cost (USD) | Duration | Notes |
|---|---|---|---|---|---|---|---|
| 2026-07-29 | REQ-2026-01 | Real | 1,045 | 472 | $0.010215 | 13.3 s | Verified end-to-end on issue #2 (6 targeted clarifying questions, correct label applied). Figure sourced from `CLAUDE.md`'s intake_agent.py build notes — was previously marked "cost not captured" in this log, corrected 2026-08-13. |
| 2026-08-27 | REQ-2026-04 | Real (job failed) | 1,978 | 465 | $0.012909 | 13.231 s | `00-intake.yml` run `33033572766`. Intake Agent itself completed normally (real cost incurred) — the job failed afterward (exit 1) at a later step because the spreadsheet's Request ID cell still held the BA-template's provisional placeholder text (`"REQ-2026-04  (provisional — confirm actual ID with Orchestration Manager before submission)"`), not a code bug. |
| 2026-08-27 | REQ-2026-04 | Real (job failed) | 1,978 | 477 | $0.013089 | 12.9 s | `00-intake.yml` run `33033907843`. Same provisional-Request-ID cause as the row above; retried after the spreadsheet was corrected. |
| 2026-08-27 | REQ-2026-04 | **Real** | 1,949 | 450 | $0.012597 | 12.625 s | `00-intake.yml` run `33034072729` — clean Request ID, job succeeded. This is the run whose conditional Stage 0a step also triggered the first real (non-scratch-test) production Ingestion Agent invocation — see the new Ingestion table immediately below. First step of the Items #24–#28/#30 Enhancement fix cycle (existing service: REQ-2026-03) — see the Implementation/QA/Security/Deploy tables below for the rest of that cycle. |

### Ingestion (Stage 0a, Enhancement only) — `ingestion_agent.py`

| Date | Request ID | Run Type | Input Tok | Output Tok | Cost (USD) | Duration | Notes |
|---|---|---|---|---|---|---|---|
| 2026-08-27 | REQ-2026-04 (existing service: REQ-2026-03) | **Real** | 21,723 | 5,313 | $0.144864 | 95.116 s | `00-intake.yml` run `33034072729`, same job as the successful Intake Agent row above. First real production use of Ingestion Agent (the three 2026-08-27 Phase 7 verification runs on issues #7/#8/#9 were explicitly scratch tests, not counted here). Committed `docs/REQ-2026-04/existing-architecture-summary.md` to `pipeline-state`, seeded from `services/REQ-2026-03/`. |

### Requirements — `requirements_agent.py`

| Date | Request ID | Run Type | Input Tok | Output Tok | Cost (USD) | Duration | Notes |
|---|---|---|---|---|---|---|---|
| 2026-07-29 | REQ-2026-01 | Real | 2,281 | 3,876 | $0.064983 | 62.5 s | `requirements.md` + `ado-work-items.json` committed to `main` (predates the Phase 4 step 4.8 `pipeline-state` branch retrofit). Figure sourced from `CLAUDE.md`'s requirements_agent.py build notes — was previously marked "cost not captured," corrected 2026-08-13. |
| 2026-08-10 | DRYRUN-2026-01 | Real | 2,154 | 3,158 | $0.053832 | 51.04 s | Succeeded on retry after a real GitHub Actions platform incident (15:22–15:53 UTC). Confirmed `requirements.md`/`ado-work-items.json` correctly landed on `pipeline-state`, validating the chat 38 branch-routing fix against a fresh request for the first time. |
| — | REQ-2026-02 | — | — | — | **Not captured** | — | `FORGE-Phase5-Closeout.md` cites $0.053832 for this run, but that figure is byte-identical to DRYRUN-2026-01's row above (same tokens, same duration) — almost certainly a copy/attribution error in the closeout doc, not a real REQ-2026-02 data point. Logged as a gap rather than transcribing a number that doesn't check out. Replace this row if the real figure surfaces. |
| 2026-08-14 | REQ-2026-03 | **Real** | 3,354 | 6,353 | $0.105357 | 104.0 s | Single attempt, `end_turn`, no retries. Source: `agent_invocation` log line, `01-requirements.yml` run `31816043997`. |
| 2026-08-27 | REQ-2026-04 | **Real** | 7,482 | 5,263 | $0.101391 | 91.712 s | `01-requirements.yml` run `33034753773`. Enhancement request (existing service REQ-2026-03); produced `docs/REQ-2026-04/requirements.md`. Part of the Items #24–#28/#30 fix cycle. |

### Design (Spec & Design) — `design_agent.py`

| Date | Request ID | Run Type | Input Tok | Output Tok | Cost (USD) | Duration | Notes |
|---|---|---|---|---|---|---|---|
| 2026-07-29 | REQ-2026-01 | Dry run | 2,929 | 12,745 | $0.1999 | 207 s | `end_turn`, no truncation. All 3 artifacts valid. |
| 2026-07-30 | REQ-2026-01 | **Real** | 2,929 | 12,738 | $0.199857 | 222 s | Committed to `design/REQ-2026-01`; PR #4 opened. |
| 2026-08-27 | REQ-2026-04 | **Real** | 9,360 | 11,986 | $0.20787 | 210.016 s | `02-design.yml` run `33035007781`. **Not explicitly requested under Item #12** (Design/"Stage 2" wasn't named in scope) — included here for completeness since it's a real cost incurred inside the same fix-cycle pipeline being backfilled. Produced `docs/REQ-2026-04/design.md`/`openapi.yaml`/`tasks.md`, later read verbatim by Stage 3 (Implementation) below. |

### Implementation — `implementation_coordinator.py` (coordinator + Backend/Frontend/Test Writer, Managed Agents)

| Date | Request ID | Run Type | Cache Read Tok | Cache Creation (5m) | Output Tok | Input Tok (fresh) | Cost (USD) | Active Duration | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-07-30 | REQ-2026-01 | Dry run | 11,868,067 | 358,148 | 125,693 | 253 | **$7.65** | 2,309 s (~38.5 min) | Pre-shared-docs-patch. 96 files, 156,728-byte archive. |
| 2026-07-30 | REQ-2026-01 | **Real** | 17,512,129 | 604,497 | 235,190 | 239 | **$12.31** | 3,310.6 s (~55.2 min) | Post-shared-docs-patch (Backend/Frontend read `design.md`/`openapi.yaml`/`tasks.md` directly instead of via coordinator relay). PR #5 opened, 101 files → 98 after stripping 3 unrequested files (CI workflow, compliance checklist, verify script). **+61% cost / +43% duration vs. dry run — attributed to the extra real file reads the patch introduced, not a regression.** |
| 2026-08-11 | REQ-2026-02 | **Real** | 6,684,549 | 420,976 | 138,996 | 155 | **~$6.63** (`usage.list_cost.amount` from `GET /sessions/{id}`, units as returned by the API — not cross-checked against the Console) | 2,218.4 s active (~37.0 min, from `usage.active_seconds`); 2,199 s (~36m39s) wall-clock from session creation to `implementation.tar.gz` appearing | Pulled directly from `GET /sessions/{id}`'s own `usage` object post-hoc — confirms that endpoint DOES carry cost/token data (open question flagged in §3 below), closing that gap for future rows without a Console visit. **First real two-service (.NET backend + Next.js frontend) build since the 03-implementation.yml GitHub Actions job's own fixed archive-wait budget was ~246s (Phase 5 pre-flight Fix 1: 120s thread pre-check + ~126s archive retry-backoff) — the job failed outright at that ceiling while the session kept working legitimately in the background, confirmed via a live read-only thread-status poll (`test_writer_agent` still `running` well past the job's own failure). Recovered manually after the fact; see CLAUDE.md for the incident and the resulting fix to `archive_session()`.** Notably, this ~37-minute duration is consistent with — not an outlier against — the REQ-2026-01 dry-run (38.5 min) and real (55.2 min) durations already recorded above; the 246s budget was never going to be enough for a real Stage 3 run and that should have been visible from this table alone before Fix 1 shipped. |
| 2026-08-14 | REQ-2026-03 | Real (failed) | 15,445,573 | 376,760 | 140,774 | 241 | **$9.12** | 2,464.9 s active (~41.1 min) | Session completed but never produced `implementation.tar.gz` (`RuntimeError: ... Files present: []`) — the `03-implementation.yml` run (`31833478314`) still failed and fully archived this session despite zero usable output, a real billed wasted attempt. This is the live incident behind Open Item #6 (idle-vs-fatal-error blindness) and its separate "archives unconditionally, before checking output" gap — see CLAUDE.md/Item #6 diagnosis. Figures pulled live from `GET /v1/sessions/sesn_0135RbeieLaZVoamUVymowtT`. |
| 2026-08-15 | REQ-2026-03 | Real (recovered) | 10,297,075 | 435,212 | 135,497 | 197 | **$7.95** | 2,263.2 s active (~37.7 min) | Recovered via `--recover-session` after the failed session above sat idle ~11h wall-clock before manual recovery (`duration_seconds` 39,575 reflects that wait, not compute — `active_seconds` is the real figure). Produced `implementation.tar.gz`, committed to `feature/REQ-2026-03`, PR #20 opened. Figures from `GET /v1/sessions/sesn_01BJBnYKAc6ontnMnUxDFmy8`. |
| 2026-08-27 | REQ-2026-04 (existing service: REQ-2026-03) | Real (stale code) | 4,615,763 | 341,011 | 89,163 | 120 | **$4.92** | 1,599.92 s active (~26.7 min) | Session `sesn_01NASDWFqwqg1X1EigAP8LnW`, `03-implementation.yml` run `33127879913`. **Ran against un-pushed local commits** (pre-Item-#24-fix code) — built a brand-new `services/REQ-2026-04/` from scratch instead of editing the real REQ-2026-03, reproducing the original Enhancement-targeting bug for real. PR `forge-demo-apps#31` opened and briefly deployed live (see Deploy notes below) before being caught and decommissioned. |
| 2026-08-28 | REQ-2026-04 (existing service: REQ-2026-03) | Real (failed — manually interrupted) | 2,674,208 | 209,776 | 54,525 | 89 | **$3.04** | 1,085.529 s active (~18.1 min) | Session `sesn_01MwLQkRnUCb54aguyJLknvX`, `03-implementation.yml` run `33136955162`. Hit the mount-path-rewrite bug (all 87 seeded existing-service files resolved to `/mnt/session/uploads/existing-service/...`, not the plain path every prompt referenced); manually interrupted via the documented kill procedure once found. The `user.interrupt` drove every thread to `idle`, which the job's own polling loop read as genuine completion — it then correctly raised `RuntimeError: ... produced no 'implementation.tar.gz'` rather than falsely succeeding (Bug 6b's Item #6 fix holding up as designed). Session was left alive per that fix's design, then manually archived. **Note:** CLAUDE.md's separate "Manually killing a runaway Managed Agents session" walkthrough previously cited a different, incorrect session ID (`sesn_01AbaBvHhDkLpkRPHRFdrFLF`) for this same kill event — that ID never appeared in this run's actual log. Corrected in CLAUDE.md 2026-08-31 to the real, GitHub-Actions-linked ID used here (`sesn_01MwLQkRnUCb54aguyJLknvX`, confirmed 15 times in the run log). |
| 2026-08-28 | REQ-2026-04 (existing service: REQ-2026-03) | **Real** | 4,065,007 | 330,220 | 66,728 | 105 | **$4.57** | 1,353.203 s active (~22.6 min) | Session `sesn_01GBkGBfEYEBLJLcc9Ftyqhv`, `03-implementation.yml` run `33139090631`. Real Item #24 fix in place; correctly edited the existing `services/REQ-2026-03/` files (19 changed, 0 new under `services/REQ-2026-04/`). PR `forge-demo-apps#32` opened — the PR used throughout the rest of the Items #24–#28/#30 fix cycle. |

**Items #24–#28/#30 fix-cycle Implementation subtotal: $12.53** (3 sessions, 4,038.65 s / ~67.3 min active compute combined).

### QA — `qa_agent.py`

| Date | Request ID | Run Type | Input Tok | Output Tok | Cost (USD) | Duration | Notes |
|---|---|---|---|---|---|---|---|
| 2026-08-04 | REQ-2026-01 | **Real** | 3,361 | 947 | $0.024288 | 15.58 s | First fully real end-to-end QA run, against genuinely clean post-infra-fix checkout. 8 real ADO Bugs filed (#96–103), PR #5 comment posted, `qa-loop-back` applied (attempt 1). |
| 2026-08-10 | DRYRUN-2026-01 | Real | — | — | **Not captured** | — | Backend-only service; `qa-approved` on attempt 1, frontend correctly reported `not_applicable`. No cost figure was recorded in any session note for this run. |
| — | REQ-2026-02 | Real (3 attempts) | — | — | **$0.013425 — partial, unattributed** | — | 3 real automated attempts (2 failed on genuine backend/frontend bugs, one retry consumed by an unrelated CI-file-cleanup `synchronize` trigger firing QA unnecessarily; 3rd attempt passed clean, 54/54 backend + 44/44 frontend). `FORGE-Phase5-Closeout.md`'s $0.013425 figure is not attributed to a specific attempt and may not represent the full 3-attempt total — flagged as incomplete rather than treated as final. Not included in §3 cumulative totals until resolved. |
| 2026-08-15 → 2026-08-25 | REQ-2026-03 | Real (14 invocations across PRs #20/#21/#22/#23/#26) | — | — | **$0.095145** (sum of all 14, each pulled from its own `agent_invocation` log line) | — | Spans the full fix-cycle history: initial post-recovery QA on PR #20 (7 costed runs, 2026-08-15→17, converging on `qa-approved`); the Azure AD/NextAuth fix cycle on PR #21 (4 costed runs + 1 zero-cost failure — the Item #15 ad hoc-PR tracking-issue-line gap); the `SHIFT_ALREADY_CLAIMED` wording fix on PR #22 (1 run); the throwaway `resolve_feature_pr()` verification PR #23 (1 run); the Pipeline-Hardening verification cycle on PR #26 (1 zero-cost run — the real `401 API key is invalid` infra incident — then 1 costed run after the key fix, genuinely passed). The 2 zero-cost dispatches are genuinely $0 (failed before the Claude call ran), not omissions. |
| 2026-08-28 | REQ-2026-04 (PR `forge-demo-apps#31`) | **Real** | 702 | 255 | $0.005931 | 4.905 s | `04-qa.yml` run `33129458694`. Attempt 1, `qa-approved`, 0 bugs — a genuine pass against the stray/stale-code build's own real (if accidental) `services/REQ-2026-04/` code. |
| 2026-08-28 | REQ-2026-04 (PR `forge-demo-apps#32`) | Real (false pass — stale code) | 702 | 277 | $0.006261 | 5.234 s | `04-qa.yml` run `33140302933`. Attempt 1 on PR #32, but still running un-pushed pre-Item-#25-fix code — both suites silently reported `not_applicable` against a nonexistent `services/REQ-2026-04/`, applying `qa-approved` with zero real test coverage (the exact original Item #25 bug). |
| 2026-08-28 | REQ-2026-04 (PR #32) | Real (false pass — stale code, 2nd occurrence) | 702 | 303 | $0.006651 | 6.331 s | `04-qa.yml` run `33216902141`. Attempt 2 — a **second** repeat of the same stale-code false-pass above (fix still not live yet at this point); CLAUDE.md's own narrative describes only one such re-dispatch before the fix landed, but the logs show it happened twice. |
| 2026-08-28 | REQ-2026-04 (PR #32) | **Real** | 846 | 515 | $0.010263 | 9.777 s | `04-qa.yml` run `33218424276`. Attempt 3, real Item #25 fix live — `dotnet test` genuinely ran against `services/REQ-2026-03/backend/OnCallRosterTracker.Api.Tests`, found 1 real bug, applied `qa-loop-back`. |
| 2026-08-28 | REQ-2026-04 (PR #32) | **Real** | 702 | 270 | $0.006156 | 6.489 s | `04-qa.yml` run `33220299036`. Attempt 4 — genuine clean pass (0 bugs), `qa-approved`, after the frontend `npm install` Enhancement-target follow-up fix (`b08ad31`) also landed. |

**Items #24–#28/#30 fix-cycle QA subtotal: $0.035262** (5 invocations).

### Security — `security_agent.py`

| Date | Request ID | Run Type | Input Tok | Output Tok | Cost (USD) | Duration | Notes |
|---|---|---|---|---|---|---|---|
| 2026-08-05 | REQ-2026-01 | Dry run | — | — | $0.00654 | 8.83 s | Pre-Gitleaks-allowlist-fix dry run. |
| 2026-08-05 | REQ-2026-01 | Dry run | — | — | $0.005637 | 5.76 s | Post-Gitleaks-allowlist-fix dry run. |
| 2026-08-05 | REQ-2026-01 | **Real** | 599 | 269 | $0.005832 | 5.37 s | All three scanners clean (0 findings). `security-check` check run created on PR #5 head commit `0f5f1c57`, conclusion `success`. `security-approved` applied. |
| — | REQ-2026-02 | Real | — | — | **Not captured** | — | Found and fixed one genuine High-severity Semgrep finding (`backend/Dockerfile` missing `USER` directive). No dollar figure was recorded anywhere in session notes for this run — genuine gap, not a zero. |
| 2026-08-15 → 2026-08-25 | REQ-2026-03 | Real (13 invocations across PRs #20/#21/#22/#23/#26) | — | — | **$0.123297** (sum of all 13) | — | Same PR/date span as the QA row above. 3 real dispatches produced $0: PR #20's one run hit a GitHub-infra `503` downloading `actions/setup-java` before ever reaching PR resolution or the agent; PR #21 and PR #26 hit the same two incidents noted in the QA row (tracking-issue-line gap; API-key incident). All costed runs found scanners clean or only already-accepted findings (see Item #11/#19's no-14.x-backport CVE population) — no Critical finding blocked this request on any of these runs. |
| 2026-08-28 | REQ-2026-04 (PR `forge-demo-apps#31`) | **Real** | 800 | 292 | $0.00678 | 5.399 s | `05-security.yml` run `33129458742`. Real scan, clean, `security-approved` — against the stray/stale-code build's own real code. |
| 2026-08-28 | REQ-2026-04 (PR `forge-demo-apps#32`) | Real (crash, $0) | — | — | $0 | — | `05-security.yml` run `33140302917`. Un-pushed pre-Item-#25-fix code — raw, uncaught `FileNotFoundError: ... services/REQ-2026-04` (the original Item #25 bug in its crashing form, not yet the fail-loud fix), correctly caught by the existing ADR-0011 comment-then-reraise wrapper. |
| 2026-08-28 | REQ-2026-04 (PR #32) | Real (crash, $0, 2nd occurrence) | — | — | $0 | — | `05-security.yml` run `33216902143`. Same raw `FileNotFoundError` as the row above — a **second** repeat of the pre-fix crash, confirming (alongside the matching QA duplicate above) that this stale-code incident happened twice, not once. |
| 2026-08-28 | REQ-2026-04 (PR #32) | **Real** | 800 | 381 | $0.008115 | 7.915 s | `05-security.yml` run `33218424135`. Real Item #25 fix live — genuine scan against `services/REQ-2026-03/`, 22 findings (0 Critical), `security-approved`. |
| 2026-08-28 | REQ-2026-04 (PR #32) | **Real** | 800 | 374 | $0.00801 | 7.788 s | `05-security.yml` run `33220299090`. Final re-scan after the frontend npm-install follow-up fix, same clean 22-finding (0 Critical) result, `security-approved`. |

**Items #24–#28/#30 fix-cycle Security subtotal: $0.022905** (5 dispatches, 2 genuinely $0).

### Deploy — `deploy_agent.py`

No table — **this stage never calls Claude or the Messages API** (see §1). Unit detection, Dockerfile generation, and PR comments are fully deterministic. Anthropic API cost is $0 for every run, by design. If Azure/infrastructure cost tracking is ever wanted for this stage, it belongs in a separate ledger — out of scope for this Anthropic-API-focused log.

**REQ-2026-03 real-run history (2026-08-15 → 2026-08-25), $0 API cost throughout as always:** 6 automated `06-deploy.yml` triggers on issue #6 — 2 were gate-skips (only one of the two required labels present at that moment, not real attempts), 3 were real attempts that failed before reaching a live Azure operation (the pre-Item-#17 `resolve_feature_pr()` gap twice, then the Item #18 `az login`-ordering bug once — all since fixed), and 1 was a real, successful deploy (2026-08-25, both `req-2026-03-on-call-rost-5bb949` and `req-2026-03-frontend` updated to PR #26's head commit `ba994a85...`). Per CLAUDE.md's prose, at least two further manual local `deploy_agent.py` invocations also happened outside `06-deploy.yml` (the 2026-08-18 unit-naming-fix verification; the PR #22 `SHIFT_ALREADY_CLAIMED` fix's manual deploy) — these left no GitHub Actions log to pull from and aren't independently re-verified here beyond what CLAUDE.md already states.

**REQ-2026-04 (existing service: REQ-2026-03) Items #24–#28/#30 fix-cycle real-run history (2026-08-27 → 2026-08-29), $0 API cost throughout as always — but see the note on real Azure cost below:** 11 `06-deploy.yml` triggers on issue #10, all pulled directly from the run logs, not inferred from CLAUDE.md prose:
- **6 guard-clause no-ops, zero work** (`33129500805`, `33136955164`, `33139090697`, `33140333691`, `33218533933`, `33219539160`) — some report at the workflow level as `skipped`, others as `success` with an internal `proceed=false` early exit before any real step ran; same zero-work outcome either way (the required label pair was never simultaneously present at that instant).
- `33129585341` (2026-08-28 00:23) — **real, partial deploy** against the stray/stale-code PR `forge-demo-apps#31`: `req-2026-04-on-call-rost-ef23ba` (backend) deployed successfully to a brand-new, live Container App; `req-2026-04-frontend` failed its `docker build` (`npm error`). Job conclusion `failure` (1 of 2 units). **This is the real, briefly-live, billable Azure resource CLAUDE.md's Item #24 narrative describes as later found and decommissioned via `az containerapp delete`** — Azure infrastructure cost for the time it was live is out of scope for this Anthropic-API-focused log (see §1's Deploy row), but is flagged here since it's a genuine cost this fix cycle incurred beyond Anthropic API spend.
- `33218470957` (2026-08-28 22:53) and `33220424754` (2026-08-28 23:26) — both real deploy attempts against the real PR `forge-demo-apps#32`, both **safe-failed** with `ValueError: No deployable units detected under services/REQ-2026-04/` (Deploy Agent's own Item #28 fix hadn't landed yet) — zero Azure resource touched either time, confirming Item #25/#28's "raise loud, touch nothing" design held under real repeated firing.
- `33263474117` (2026-08-29 16:37) — **real, successful deploy**, post-Item-#28-fix: 2 of 2 units updated in place (`req-2026-03-on-call-rost-5bb949`, `req-2026-03-frontend`), `naming_id=REQ-2026-03` confirmed in the log. This is Item #28's own live-verification run.
- `33269070840` (2026-08-29 18:44, `pr-merged` event) — **real, successful deploy**, triggered automatically 13 seconds after Mike's real merge of PR #32 — Item #26 §5's live end-to-end verification run.

---

## 3. Cumulative Totals (Anthropic API cost, tracked stages only)

| Stage | Runs Recorded | Total Cost (USD) |
|---|---|---|
| Intake | 4 (incl. REQ-2026-04's 2 job-failed-after-agent-success runs) | $0.04881 |
| Ingestion (Stage 0a) | 1 | $0.144864 |
| Requirements | 4 (+1 gap: REQ-2026-02 not captured, see note above) | $0.325563 |
| Design | 3 | $0.607627 |
| Implementation | 8 (incl. REQ-2026-03's 1 failed + 1 recovered session, and REQ-2026-04's 3 fix-cycle sessions) | $56.19 |
| QA | 20 (+2 gaps: DRYRUN-2026-01 not captured, REQ-2026-02 partial/unattributed — both still excluded from this total; REQ-2026-03's 2 zero-cost failed dispatches and REQ-2026-04's 3 fully-costed false-pass/real runs ARE included) | $0.154695 |
| Security | 21 (+1 gap: REQ-2026-02 not captured; REQ-2026-04's 2 zero-cost crash dispatches ARE included, at their genuine $0) | $0.164211 |
| Deploy | N/A — $0 by design, not a gap (REQ-2026-04's briefly-live stray Container App is a real Azure cost, not an Anthropic API cost — see the Deploy section's note) | $0 |
| **Total (costed runs only)** | | **$57.64** |

This excludes Managed Agents' separate $0.08/session-hour billing component, which is already folded into the $12.31/$7.65 figures above per the Console's `list_cost` — worth confirming that assumption the first time `GET /v1/sessions/{id}`'s own cost field (if one exists) is checked against the Console total, since right now both Stage 3 rows are taken as a single all-in number rather than split token-cost vs. session-hour-cost. **Confirmed 2026-08-31 for the three REQ-2026-04 fix-cycle sessions:** `GET /sessions/{id}`'s `usage.list_cost.amount` field is returned in **cents**, not dollars (e.g. `"492"` → $4.92) — reverse-derived by reconstructing each session's cost from its raw token counts against `_MODEL_RATES` and getting a match within a few percent (the exact split isn't recoverable since the aggregate `usage` object doesn't separate the Opus-tier coordinator's tokens from the Sonnet-tier subagents'). **Spot-checked the same reconstruction against all three existing REQ-2026-02/REQ-2026-03 Stage 3 rows above** (`$6.63`/`$9.12`/`$7.95`) using their already-recorded token counts — all three land within ~5% of their recorded dollar figures under the identical cents convention, so those figures are consistent with this unit and do not need correcting.

---

## 4. How to Add a Row

1. **Messages-API stages (Intake, Ingestion, Requirements, Design, QA, Security, Deploy):** grep the GitHub Actions job log for `"forge_event": "agent_invocation"` — the JSON line already has `input_tokens`, `output_tokens`, `total_cost_usd`, `latency_seconds`. Copy directly into the relevant table; no manual math needed. Ingestion (Stage 0a) added as its own table 2026-08-31 — it only fires for Enhancement-flagged requests, so most requests will never have a row here.
2. **Implementation (Stage 3):** no automatic equivalent yet. Open the Claude Console session detail page for the `session_id` printed by `implementation_coordinator.py`'s dry-run output or PR comment, and copy the `usage` object's fields as shown above. (Flagged in §1 as an open automation gap — closing it would mean adding an `agent_invocation`-equivalent log line to `managed_agents_wrapper.py`, queued but not yet built.)
3. Update the cumulative totals table in §3 after adding any costed row.
4. If a stage's cost mechanism or model tier changes (e.g. cache_control lands on the Messages-API stages), note the change inline in §1 rather than silently starting a new pattern with no explanation.
