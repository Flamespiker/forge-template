# FORGE Context — v65

**Session date:** 2026-08-25
**Prior doc:** v64
**Prepared by:** Claude.ai, from this session's work plus Claude Code CLI's live execution and verification

---

## Purpose & context

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment. Phase 6 (Repeatability) is complete; the project remains in a maintenance/hardening posture. Two apps remain live: REQ-2026-01 and REQ-2026-03. REQ-2026-02's infrastructure was decommissioned in Phase 5 (code retained).

**Two-repo model (unchanged):**
- `forge-template` (public, `Flamespiker/forge-template`) — orchestration/agent code
- `forge-demo-apps` (private) — target monorepo where generated app code lands

**Firm two-tool convention (unchanged):**
- Claude.ai: strategy, spec authorship, context documents
- Claude Code CLI: live execution, git operations, CLAUDE.md updates, README.md updates
- Mike shuttles between tools and holds all unilateral architecture/scope decisions

This was a straightforward **open-item session**: one document (this one) plus prompts handed to Claude Code CLI, no separate spec docs authored. Normal one-doc-per-chat convention applied without exception this time.

---

## Current state — Open Items

**11 resolved/closed as of end of this session:** #2, #3, #4, #5, #13, #14, #16, #17, #18, #19, **#20 (new this session)**

**9 genuinely still open:**

| # | Item | Nature |
|---|---|---|
| 1 | Deploy Agent has no way to learn an app needs a given secret (wiring mechanism exists; nothing declares which secrets are needed) | Design gap, tribal knowledge |
| 6 | `wait_for_all_threads_idle()` can't distinguish "finished" from "every thread hit a fatal session error" | **Diagnosed this session — root cause confirmed, fix not yet written. See below.** |
| 7 | Archive-prefix mismatch (REQ-2026-02, once, root cause unconfirmed) | Deliberately left alone unless it recurs |
| 8 | Implementation Coordinator sometimes generates unrequested `.github/workflows/*.yml` scope creep | **Diagnosed this session — root cause confirmed, fix not yet written. See below.** |
| 9 | Ad hoc `fix/*` branches hit `security-check` and need `--admin` merge (4 occurrences) | Undecided: fix the branch convention or accept as standing procedure |
| 10 | `enforce_admins` on `forge-demo-apps` `main` is `false`, should arguably be `true` again | Mike's call, not yet made |
| 11 | 21 CVEs (not just 8) have no `next` 14.x backport | Accepted risk, not actionable — a decision, not a todo |
| 15 | Ad hoc PRs need the tracking-issue body line added manually if not opened by a stage agent | Known gap, manual workaround exists |
| — | 6 pre-existing frontend Jest failures (UploadPage/HistoryPage accessibility/DOM-query issues), surfaced blocking PR #27's `qa-approved` | **New, tracked via ADO Bugs #163–168 only — deliberately not added as a numbered CLAUDE.md Open Item per Mike's explicit call this session.** |

Item #12 (cost log backfill) closed this session — see below.

Of the remaining open items: **#1, #9, #10 are genuine design/policy decisions waiting on Mike**, not something to unilaterally spec and fix. **#6, #8 now have confirmed root causes and are ready for fix specs** — #6 first, per Mike's sequencing call this session. **#7, #15 are deliberately left alone.** **#11 is an accepted-risk decision, not a todo.**

A companion planning doc, `FORGE-Open-Items-Backlog-v1.md`, still holds the fuller original breakdown — now stale on #6/#8/#12/#20's status (all resolved/diagnosed since it was written) but accurate on #1/#7/#9/#10/#11/#15.

---

## This session's work, in order

### 1. Item #20 — REQ-2026-01 Application Insights type conflict — **RESOLVED**

Root cause confirmed precisely (refined from the earlier "duplicate copy" framing): `applicationinsights-react-js@3.4.3` pins `applicationinsights-common@^2.8.14`, which resolves `@microsoft/applicationinsights-core-js@2.8.18` — a physically separate copy from the `3.4.3` used throughout `applicationinsights-web`'s own tree (nested under `applicationinsights-analytics-js`). Genuine 2.x-vs-3.x type-shape mismatch (`Tags`, `ITelemetryPlugin.setNextPlugin`), not a cosmetic duplicate.

**Fix:** a `package.json` `overrides` entry forcing `applicationinsights-react-js`'s own `applicationinsights-common`/`core-js` dependencies to `3.4.3`. Confirmed live that `applicationinsights-react-js`'s runtime bundle never `require()`s `core-js` directly — it's a duck-typed plugin that receives its `core` instance at runtime from `ApplicationInsights` itself — so this is a type-only change with no runtime risk. No type-cast fallback was needed.

**Verification:**
- `npm ls @microsoft/applicationinsights-core-js` before/after: two physical copies (`2.8.18` + `3.4.3`, plus a private nested copy) → single deduped `3.4.3` resolution, nested private copy gone entirely.
- Real `next build` inside `node:20-bullseye` (matching `04-qa.yml`'s `ubuntu-latest` runner): compiles, type-checks, generates all 6 static pages cleanly.
- **Live pipeline verification:** real PR (`forge-demo-apps#27`, branch `feature/fix-appinsights-core-js-dedupe`) dispatched through `notify-forge.yml` → real QA/Security run in `forge-template`. QA's real CI log confirms `npm run build` completed with no failure — Fix 3's build-validation step stayed silent, confirming the build genuinely passes in production CI.

**Not fully closed out yet:** PR #27 got **security-approved** (clean scan) but landed **`qa-loop-back`**, not `qa-approved` — due to 6 pre-existing frontend Jest failures (UploadPage/HistoryPage accessibility/DOM-query issues), byte-identical to an already-documented baseline and unrelated to app-insights. QA auto-filed ADO Bugs #163–168 for them. Deploy never triggered (needs both approvals). **PR #27 remains open, unmerged, awaiting Mike's review** — the app-insights fix itself is done and verified; only the unrelated Jest baseline blocks the formal `qa-approved` gate.

CLAUDE.md's Item #20 entry rewritten with the full corrected narrative (commit `26335ae`): root cause, why the overrides fix is runtime-safe, before/after `npm ls`, Linux + live QA verification, and the PR #27 caveat.

**Documentation cleanup, same thread:** CLAUDE.md's Item #11 CVE count ("8 HIGH-severity") corrected to match the already-correct body text ("21... 8 High + 11 Medium + 2 Low"), committed standalone per Mike's explicit request (separate commit from the app-insights work).

### 2. Item #6 — `wait_for_all_threads_idle()` diagnosis — root cause confirmed, no fix yet

Two distinct bugs, confirmed against real Anthropic Managed Agents API docs and live code (not guessed):

- **Wrong data source:** `wait_for_all_threads_idle()` (`managed_agents_wrapper.py:596-671`) only reads the bare `status` field from `GET /sessions/{id}/threads` and returns success the moment no thread is running/rescheduling — it never touches the event stream. A session that hits its budget cap also goes idle, but carries `stop_reason: budget_reached` on `session.thread_status_idle` events — a signal that exists but lives in the event stream, not the `/threads` resource this function polls. `poll_until_idle()`, which does scan events, only checks for `stop_reason == "requires_action"` and would also miss a budget-exhaustion stop.
- **Archive-before-validation ordering bug (separate and arguably worse):** `run_implementation_stage()` archives the session at line 855 **before** the caller ever checks for real output — the inverse of `recover_implementation_session()`'s already-correct order (sanity-check output, then archive last). This is actively destroying evidence of failures, not just misreporting them.

**Live corroboration, found incidentally:** the Item #12 cost-log backfill surfaced a real instance of exactly this failure mode — a failed Stage 3 session ($9.12, no `implementation.tar.gz` produced) that was archived anyway.

**Proposed fix shape for next session (not implemented):** a `budget_reached` check in `poll_until_idle()`; a second data source (events, not just `/threads`) in `wait_for_all_threads_idle()`; a new `SessionBudgetExhaustedError`; reordering the archive call in `run_implementation_stage()` to run after output validation, matching `recover_implementation_session()`'s pattern. Exact file/line targets are in Claude Code's full diagnosis output (not yet captured in a standalone spec doc).

**Mike's call this session: #6 gets the next fix spec, ahead of #8.**

### 3. Item #8 — CI-workflow scope creep diagnosis — root cause confirmed, no fix yet

Confirmed as a real structural contradiction, not model flakiness:

- Both historical incidents traced to real commits: REQ-2026-01 (`3397617`, cleaned up in `0f5f1c5`) and REQ-2026-02 (`47b3fef`, cleaned up in `ba3b3a7`).
- Design Agent's own `tasks.md` asked for these files using bare, root-implied paths (e.g. `.github/workflows/backend-ci.yml`) with no indication of "relative to repo root" vs. "relative to your confined directory."
- Every Stage 3 subagent prompt carries an absolute rule: write only under `<target>/backend/...` — never outside it. Nothing carves out an exception for "this task item describes a repo-root artifact — skip or escalate it." A subagent given one instruction demanding a repo-root artifact and another forbidding it from leaving its subdirectory can only satisfy both by nesting the file — which is exactly what happened, twice.
- **Gap spans two stages:** Design Agent proposes legitimate DevOps deliverables without path-scoping them; Stage 3 has no logic to recognize and reject a task item that targets outside its writable area.

No fix implemented yet — next spec after #6's.

### 4. Item #12 — cost log backfill — **CLOSED**

Committed as `2fa77c2`. REQ-2026-03 figures backfilled across Stages 1/3/4/5/6, cumulative total $27.16 → $44.55:
- Stage 1 (Requirements): $0.105357, one clean run.
- Stage 3 (Implementation): two sessions — a failed one ($9.12, no output, archived anyway — the live Item #6 incident) and the recovered one ($7.95, produced PR #20). Combined $17.07.
- Stage 4 (QA): $0.095145 across 14 real invocations (PRs #20/#21/#22/#23/#26); 2 genuinely-$0 dispatches (Item #15 tracking-issue gap once, a 401 API-key incident once).
- Stage 5 (Security): $0.123297 across 13 invocations, same PR span; 3 genuinely-$0 dispatches (one GitHub-infra 503, plus the same two incidents as Stage 4).
- Stage 6 (Deploy): $0 by design; real run history noted (1 successful deploy, 3 failed automated attempts pre-Item-#17/#18 fixes, 2 gate-skips).

### 5. Process note from CLI

Docker Desktop hung unresponsive mid-session (its CLI hanging on basic commands) during the Linux-container verification work for Item #20; killed and restarted, healthy afterward. No lasting impact, noted here in case it recurs.

---

## Key learnings & principles (new/updated this session)

- **A "duplicate dependency" diagnosis is worth refining past "two copies exist" to "why do two *incompatible* copies exist"** — Item #20's real root cause was a specific upstream package (`applicationinsights-react-js`) pinning an older sub-dependency range, not a generic resolution accident. The more precise diagnosis is what made the runtime-safety confirmation (duck-typed plugin, no direct `require()`) possible.
- **A resolved bug and a resolved pipeline gate are different things** — Item #20's underlying code fix is done and verified, but the PR is still blocked at `qa-loop-back` by an unrelated pre-existing test baseline. Don't conflate "the fix works" with "the PR is mergeable."
- **When a diagnosis session surfaces a live instance of the very bug being diagnosed, that's corroboration, not scope creep** — the Item #6 diagnosis and the Item #12 cost-log pull happened to touch the same failed Stage 3 session from different angles, and it strengthened the #6 diagnosis rather than needing separate investigation.
- **A "two rules that can't both be satisfied" root cause (Item #8) is a distinct failure class from a diagnosed logic bug (Item #6)** — the fix shapes will look different: #8 likely needs a validation/rejection step at task-list-generation or subagent-dispatch time, not a data-source fix like #6.
- **Diagnosis-first sessions are worth protecting as their own step** — both #6 and #8 came out with confirmed, evidence-backed root causes specifically because Claude Code was told not to write fix code this round. Worth continuing this pattern for future undiagnosed items.

---

## On the horizon

- **Item #6 fix spec — next up**, per Mike's explicit sequencing call. Root cause and proposed fix shape are documented above; needs a formal spec authored (Claude.ai) before Claude Code implements.
- **Item #8 fix spec — after #6.** Root cause documented above.
- **PR #27 (Item #20's fix)** — needs Mike's review/merge decision; blocked only by the unrelated Jest baseline (ADO #163–168), not by anything in the fix itself.
- **The 6 pre-existing Jest failures (ADO #163–168)** — not yet scoped as a FORGE open item by design (Mike's call), but will need attention eventually since they're now actively blocking a real PR's `qa-approved` gate, not just sitting latent.
- **Items #1, #9, #10** — design/policy decisions still waiting on Mike.
- **Items #7, #15** — deliberately left alone; revisit only if either recurs or becomes actively annoying.
- **Item #11** — accepted risk, no action needed unless the risk posture changes.
- **Bigger direction question, still open (carried from v64):** production promotion (pushing REQ-2026-03 through the Stage 6 *production* gate for the first time), cloud-portability abstraction (deferred since v61), a third greenfield app, or org-facing onboarding groundwork. Not decided this session.

---

## Tools & resources (unchanged from v64)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **Azure:** Container Apps (`forge-staging`, `forge-production` environments in `forge-build-rg`), Azure Container Registry, Azure Database for PostgreSQL Flexible Server (`forge-req2026-03-pg`, Burstable B1ms, Canada Central — **remember to `az postgres flexible-server stop` after each testing session**), Key Vault (`forge-build-kv`), Azure AD (single-tenant app registration `FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **Live Container Apps as of last known state:** `req-2026-01-document-api`, `req-2026-01-email-worker` (⚠️ running continuously, does not auto-scale to zero), `req-2026-03-frontend`, `req-2026-03-on-call-rost-5bb949`
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build` — new bugs this session: **#163–168** (pre-existing Jest failures, UploadPage/HistoryPage)
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`, `C:\Users\mikef\Projects\forge-demo-apps`
- **Security scanning:** GitHub Dependabot (default); Semgrep; Gitleaks
- **Anthropic Managed Agents:** Stage 3 only; all other stages use base `anthropic` Python client (Messages API)
- **New commits this session:** `26335ae` (CLAUDE.md Item #20 full rewrite), CLAUDE.md Item #11 count fix (standalone), `2fa77c2` (cost log backfill), plus PR #27 (`forge-demo-apps`, unmerged) for the app-insights dedupe fix itself

---

## Other instructions (unchanged)

- For FORGE project work, do not use organizational skills (`laa-brand`, `laa-security-review`, `freshservice-kb-article`) unless Mike explicitly requests one.
- One context doc per chat is the default.
