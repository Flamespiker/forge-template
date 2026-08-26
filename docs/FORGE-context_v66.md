# FORGE Context — v66

**Session date:** 2026-08-26
**Prior doc:** v65
**Prepared by:** Claude.ai, from this session's work plus Claude Code CLI's live execution and verification

---

## Purpose & context

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment. Phase 6 (Repeatability) is complete. Two apps remain live: REQ-2026-01 and REQ-2026-03. REQ-2026-02's infrastructure was decommissioned in Phase 5 (code retained).

**Two-repo model (unchanged):**
- `forge-template` (public, `Flamespiker/forge-template`) — orchestration/agent code
- `forge-demo-apps` (private) — target monorepo where generated app code lands

**Firm two-tool convention (unchanged):**
- Claude.ai: strategy, spec authorship, context documents
- Claude Code CLI: live execution, git operations, CLAUDE.md updates, README.md updates
- Mike shuttles between tools and holds all unilateral architecture/scope decisions

**This session's shape:** started as an open-item review/planning session, then explicitly batched into a multi-item fix session at Mike's request ("consider this chat session 6 and 8") — the normal one-doc-per-chat convention was deliberately suspended for this thread. This doc closes the thread out; the next chat returns to normal one-doc-per-chat for enhancement-phase work.

---

## Current state — Open Items

**This session closed:** #6, #8, #20, #21, #22, plus new item **#23** (Docker Desktop replacement — resolved same session it was opened).

**Genuinely still open: none requiring action.** All remaining items are explicit accepted-risk/standing-procedure decisions, not unfinished work:

| # | Item | Status |
|---|---|---|
| 1 | Deploy Agent has no secrets-discovery mechanism | Accepted — tribal knowledge, moot unless new apps with new secrets get built |
| 7 | Archive-prefix mismatch (REQ-2026-02, one-off) | Accepted — leave alone unless it recurs |
| 9 | Ad hoc `fix/*` branches need `--admin` merge | Accepted — standing procedure (now used 4+ times this session alone, see below) |
| 10 | `enforce_admins` on `forge-demo-apps` `main` is `false` | Accepted — deliberate, currently load-bearing for #9's workflow |
| 11 | 21 CVEs, no `next` 14.x backport | Accepted risk, not actionable |
| 15 | Ad hoc PRs need tracking-issue line added manually | Accepted — known workaround |
| — | ADO #163–168 Jest baseline (UploadPage/HistoryPage) | Explicitly dropped — app-level (REQ-2026-01's own code), out of forge-mechanism scope per Mike's explicit "I don't care about the apps" instruction this session |

A new working principle emerged this session (see Key learnings): **forge-mechanism correctness vs. app-level concerns** is now the standing filter for what counts as required work. Applied retroactively, this is what re-sorted #8 back into "must fix" after an earlier draft miscategorized it, and what cleanly dropped the Jest baseline and CVE items out of scope.

**Mike's explicit call at session end: clean to start the enhancement phase.** No blocking items remain.

---

## This session's work, in order

### 1. Item #20 close-out — PR #27 merge, partial deploy, retry, full live resolution

PR #27 (the Item #20 App Insights fix, authored and verified in the v65 session) was merged by Mike directly — despite its own PR body saying "Do not merge" pending a real `qa-approved`, which never landed (blocked by the unrelated Jest baseline). Flagged as a process-gap observation; no corrective action taken (Mike's explicit call: "no").

Merge alone did not deploy the fix — `06-deploy.yml` only fires on both `qa-approved` and `security-approved`, and `qa-approved` was never satisfied. Verified live (image tag comparison via `az containerapp show`) that `req-2026-01-document-api` was still serving a 2026-08-04 build three weeks after the fix merged.

**Decision: manually dispatch Deploy, bypassing the unsatisfied `qa-approved` gate.** Justified because the underlying fix was already independently verified (clean Linux build, real QA pass on PR #27's actual content prior to hitting the unrelated Jest baseline, security-approved scan) — waiting on the gate wasn't buying additional confidence, just delay.

First deploy attempt: `document-api` and `email-worker` (backend .NET units, unaffected by the actual fix) succeeded. `frontend` (where the real fix lives) failed — `docker build` timed out at the default 1800s ceiling; the Container App didn't even exist yet (`ResourceNotFound`).

**One retry at 3600s succeeded cleanly, zero app changes needed** — confirmed this was a forge-mechanism gap (the timeout ceiling), not an app-quality issue. This became Item #21.

**Final state, all three `req-2026-01` units live at commit `71890f7e239947619cd0d951ee4ebe6b90d7d9a7`, image tags confirmed via `az containerapp show`.** Item #20 fully resolved.

**Byproduct finding:** `req-2026-01-email-worker` has `minReplicas: 0`, no ingress, `rules: null` — nothing can trigger it back up from zero. Confirmed via live inspection. Decision: **leave the live app's config untouched** (deferred, app-operations concern), but fix Deploy Agent so it stops generating this broken shape for future units. This became Item #22.

### 2. Item #6 — fix implemented and committed

Two bugs, both root-caused in the prior (v65) session, fixed this session against live-verified code (not the diagnosis summary's remembered line numbers — a spec was authored fresh against a live fetch of `managed_agents_wrapper.py`/`implementation_coordinator.py`, correcting one detail: the archive-before-fetch framing was imprecise — the real gap was archiving with no validation gate at all, not a fetch/archive ordering bug).

- **Bug 6a (budget exhaustion invisible to idle check):** `poll_until_idle()` gained a `budget_reached` stop_reason branch; `wait_for_all_threads_idle()` gained a second data source (event-stream check at the point of declaring success, not in the polling loop) to catch per-thread budget exhaustion. New `SessionBudgetExhaustedError` — deliberately its own `RuntimeError` subclass, **not** a subclass of `SessionStillRunningError` (confirmed via CLI's own sanity check), so it correctly routes through the existing archive-on-failure path rather than the "still working, leave it alive" path.
- **Bug 6b (archive with no validation gate):** a genuine design fork was flagged in the spec (where should the "was real output produced" check live) and resolved by Claude Code tracing the actual control flow: the archive call sits **outside** the existing `try/except` block in `run_implementation_stage()`, so a plain `RuntimeError` raised just before the archive call propagates cleanly with zero new exception types and zero caller-side changes needed. Simpler than either option the spec proposed.
- Bonus fix taken during implementation: `run_implementation_stage()`'s return dict now includes `output_files`, avoiding a redundant second `list_session_output_files()` call in the caller.

**Verification: mocked API harness only (10 cases, both bugs, including explicit regression checks), live end-to-end Stage 3 dry-run deliberately deferred** — real cost ($5-15+, 35-55+ min, cleanup overhead) wasn't justified for changes this small and well-isolated. Documented in CLAUDE.md as a deliberate deferral, not an oversight. **The enhancement phase's first real Stage 3 run will serve as the live integration test for this fix**, per Mike's explicit direction this session.

Commits: `e300ddc`, `24ceb85`, `78a2f3f`, `5ef29de`; CLAUDE.md update in `3b7d726`.

### 3. Item #8 — fix implemented, committed, and fully live-verified

Two-layer fix, since either layer alone leaves a gap:

- **Layer 1 (prompt guardrail):** `design_agent.py`'s system prompt now explicitly excludes CI/CD/pipeline-infrastructure deliverables from `tasks.md` task items — those are fixed `forge-template` infrastructure, never per-request generated work.
- **Layer 2 (defensive extraction guard):** `implementation_coordinator.py`'s `_extract_archive_to_file_dict()` now rejects any archive member with a `.github` path segment, using exact segment matching (`split("/")`, not substring matching — confirmed live to avoid false-flagging something like `mygithubutil/`).

**Fully live-verified, not just mocked:** a real Design Agent run against requirements text explicitly demanding "a CI/CD pipeline configuration" correctly produced no CI-related task item (redirected into legitimate backend/frontend test infrastructure instead) — Layer 1 confirmed live. Layer 2 confirmed via a deliberately adversarial fixture (`.github/workflows/fake.yml` nested inside a valid prefix, plus a negative-case path to prove no false-flagging).

### 4. Item #21 — Deploy Agent build timeout

`_SHELL_TIMEOUT_SECONDS` bumped 1800s → 3600s in `deploy_agent.py`. One-line change. **Live proof already existed** from the earlier Item #20 frontend-deploy retry (same session) — no separate live verification run was needed. Commit `ac13529`.

### 5. Item #22 — Deploy Agent replica default for non-ingress/no-scale-rule workers

`_build_containerapp_command()` now defaults `minReplicas: 1` (not `0`) for a generated unit with no ingress and no scale rule — units with either ingress or a real scale rule are unaffected. Rationale documented in-code: a `minReplicas: 0` unit with nothing to trigger it back up is a broken config, not a cost optimization.

**`req-2026-01-email-worker`'s live config deliberately left untouched** — this fix only changes what Deploy Agent generates for future units, per explicit instruction. Verified via scoped mock checks (no-ingress/no-scale-rule → 1; ingress → 0 unchanged). **One documented gap:** the spec's third test case (units with a real scale rule) isn't currently testable — `DeployUnit` has no scale-rule field yet, since nothing generates one today. Revisit if that changes. Commit `9d57398`.

### 6. New Item #23 — Docker Desktop replacement

Mike's local Docker Desktop had become the bottleneck for FORGE-verification work specifically (spinning up a `node:20-bullseye` container to reproduce CI locally before trusting a fix — the same workflow that hung mid-session during the v65 Item #20 diagnosis). This does **not** touch production deploys, which already run in the cloud (`06-deploy.yml` on GitHub-hosted runners) and were never on Mike's local Docker.

**Fix:** new `verify-build.yml` in `forge-demo-apps` (kept in-repo rather than `forge-template`, avoiding cross-repo checkout/auth entirely). `workflow_dispatch`-only, inputs `ref`/`service-path`/`mode` (`language-build` | `docker-build`), runs on `ubuntu-latest` (free, matches `04-qa.yml`'s real CI environment, Node + Docker both preinstalled).

**Real bug caught during its own live verification, then fixed:** `docker-build` mode initially assumed build context == service-path; failed against `services/REQ-2026-01/backend/DocumentApi` because .NET units' Dockerfiles expect the shared `backend/` parent directory as context (matching `deploy_agent.py`'s own `_detect_backend_units()` convention). Fixed and merged as a follow-up PR. Mike's requested spot-check confirmed `language-build` mode's `dotnet build` path was never affected by the same class of bug — MSBuild finds `Directory.Build.props` via its own upward search, unlike Docker's `COPY`-restricted context — confirmed live, not just reasoned.

**Final live-verified state, both modes, both unit types:**
- `language-build`: frontend 56s pass, backend 28s pass
- `docker-build`: frontend correctly fails clean (no Dockerfile committed yet for that service — genuine gap, correct tool behavior, not a bug), backend 51s pass post-fix

Two admin-merges required to land this (initial add, PR #28; the context-fix follow-up, PR #29) — same rationale as Item #9 each time: ad hoc branch naming means `security-check` structurally can't fire either way, files were additive-only/low-risk. **Four admin-merges total this session** (PR #27 itself was a Mike-direct merge, not CLI's; PR #28, PR #29, plus the earlier Deploy dispatch bypass for Item #20) — flagged as a pattern worth a real conversation if it continues into the enhancement phase, not acted on further this session.

### 7. Batch-wide verification approach

Per Mike's explicit direction: no live QA/Security dispatch or test deploys for #6/#21/#22 individually. Each got local/mocked verification against its own acceptance criteria instead. #8 and #23 ended up fully live-verified anyway, as a natural consequence of how their fixes were tested (a real Design Agent run for #8, real `workflow_dispatch` runs for #23) — not because the batch-wide deferral was violated, but because those two didn't require a full expensive Stage 3-6 cycle to verify live. **The enhancement phase's first real pipeline run is the designated integration test** for everything in this batch collectively.

---

## Key learnings & principles (new/updated this session)

- **"Forge mechanism vs. app-level" is now the standing filter for scope decisions**, introduced explicitly this session ("I want all the forge orchestration and agents to work as planned... I don't care about the apps once deployed"). Applied retroactively, it correctly re-classified Item #8 (subagent write-scope violation) back into required work after an earlier draft had miscategorized it as low-priority, and cleanly dropped the CVE/Jest-baseline items as genuinely out of scope rather than just deprioritized.
- **A design fork flagged in a spec doesn't always need a human decision** — sometimes tracing the actual control flow resolves it outright, as Bug 6b's archive-ordering fork did. Worth having the implementer trace first before escalating, but still worth flagging in the spec so the implementer knows to check rather than assume.
- **A resolved bug and a resolved pipeline gate remain distinct** (carried forward from v65, reconfirmed by Item #20's saga this session) — merged-to-main, deployed-and-live, and QA-gate-satisfied are three separate claims. This session's Item #20 close-out needed all three tracked separately before it could honestly be called done.
- **"Live-verified" is worth being precise about at the level of individual sub-checks, not just the item as a whole** — Item #23's clean frontend `docker-build` failure (no committed Dockerfile) is correct tool behavior, not an incomplete verification; worth documenting as such rather than leaving it read as a gap.
- **Self-verification catching its own bugs is the system working, not scope creep** — Item #23's build-context bug, found during its own live dispatch test before being reported as a full pass, is exactly the kind of thing a "verify before trusting" culture is supposed to catch.
- **Repeated ad hoc admin-merges are individually justifiable but collectively worth watching** — four this session (Item #20's deploy dispatch, PR #27 itself, PR #28, PR #29). None was wrong on its own merits; the pattern as a whole is flagged for future attention, not acted on.

---

## On the horizon

- **Enhancement-phase direction** — not yet decided. Carried forward from v64/v65: production promotion (REQ-2026-03 through the Stage 6 *production* gate for the first time), cloud-portability abstraction (deferred since v61), a third greenfield app, or org-facing onboarding groundwork.
- **The enhancement phase's first real pipeline run doubles as live integration verification** for this session's entire batch (#6, #8, #21, #22, #23) — worth choosing a first task that actually exercises Stage 3 (for #6/#8) and Stage 6 (for #21/#22) rather than one that skips either.
- **Ad hoc admin-merge pattern** — four occurrences this session; worth a real conversation if the frequency continues, not urgent now.
- **Item #22's third test case** (scale-rule units) remains untestable until something actually generates a scale rule — revisit only if that changes.
- **Items #1, #7, #9, #10, #11, #15** — all explicit accepted-risk/standing-procedure decisions, not todos. No further action expected unless circumstances change (e.g. #9/#10 would need revisiting together if the ad hoc admin-merge pattern above prompts a real fix).

---

## Tools & resources (unchanged from v65)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **Azure:** Container Apps (`forge-staging`, `forge-production` environments in `forge-build-rg`), Azure Container Registry, Azure Database for PostgreSQL Flexible Server (`forge-req2026-03-pg`, Burstable B1ms, Canada Central — remember to stop after each session), Key Vault (`forge-build-kv`), Azure AD (single-tenant app registration `FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **Live Container Apps as of last known state:** `req-2026-01-document-api` (idle, scale-to-zero via HTTP ingress, working correctly), `req-2026-01-email-worker` (⚠️ still running continuously, `minReplicas: 0` but no ingress/scale-rule to bring it back — deliberately deferred, not fixed), `req-2026-01-frontend` (newly created this session, idle via HTTP ingress), `req-2026-03-frontend`, `req-2026-03-on-call-rost-5bb949`
- **New this session:** `verify-build.yml` in `forge-demo-apps` — manual `workflow_dispatch` build verification, replaces local Docker Desktop for FORGE-verification purposes.
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`, `C:\Users\mikef\Projects\forge-demo-apps`
