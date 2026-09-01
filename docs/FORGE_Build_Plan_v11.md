# FORGE — Build Phase Project Plan

**Purpose:** Step-by-step checklist for building FORGE from scratch. Work through one item at a time. Each step is a discrete unit — complete it, confirm it, move on.

**Current version: v11** (2026-08-31) — see the v11 update note below for what changed.

**Version:** v6 — Step 4.8 (branch protection on `forge-demo-apps` `main`) checked off as complete this session (chat 37), after resolving a real GitHub-plan-tier blocker (classic branch protection on private repos requires GitHub Pro; Mike upgraded). Verified live via `gh api .../branches/main/protection` GET: `required_status_checks.checks` = `security-check` (scoped to `app_id: 4388813`, the `forge-pipeline` App), `required_pull_request_reviews.required_approving_review_count` = 1, `enforce_admins.enabled` = true, `allow_force_pushes`/`allow_deletions` = false. Step 4.10 (full dry-run) remains unchecked — next up, now that its 4.8 dependency is satisfied. No other content/step text changed from v5.

**v7 update:** a follow-on conflict under 4.8 was found and resolved in the next chat, not a reopening of 4.8 itself — `requirements_agent.py` and `create_ado_items.py` both wrote directly to `main` (a pre-existing, documented-as-intentional pattern), which the newly-live required-PR-review rule would reject on their next real run. `bypass_pull_request_allowances` was tried first but is org-only (confirmed via a 422 and GitHub's own docs — not available on a personal-account repo). Resolved instead by moving both files' target branch from `main` to a dedicated, intentionally-unprotected `pipeline-state` branch — see 4.8's note below for details. No checkbox change (4.8 was already correctly checked in v6); this just closes a gap chat 37 hadn't hit yet.

**v8 update (2026-08-13):** Step 4.10 (full dry-run, `DRYRUN-2026-01`) checked off — ran for real, chat 39, Phase 4 fully closed. Phase 5 (App 1 — `REQ-2026-02`, Inactive User & License Auditor) substantially complete: 5.1–5.8 and 5.11 checked off against real evidence in the context doc and `FORGE-Phase5-Closeout.md`. **5.9 checked with a caveat — staging only, production deliberately not attempted** (not appropriate for a Phase 5 validation run per Mike's call; App 1's Azure/D365 resources have since been decommissioned entirely, so a production deploy of this specific app is now moot). **5.10 left unchecked** — some real actuals were captured mid-run (Stage 1 cost, a Stage 3 Managed Agents timing/cost data point) but never fully transcribed into `docs/FORGE-pipeline-cost-log.md`; that pass is still outstanding and should happen before Phase 6, per the close-out doc's go/no-go read. See `FORGE-Phase5-Closeout.md` for full detail on what shipped, what was descoped (R-001), every confirmed-not-fixed structural gap, and the real manual-intervention count.

**v9 update (2026-08-27):** Phase 6 (Repeatability) confirmed complete — App 2 (`REQ-2026-03`, On-Call Roster Tracker) closed clean (`forge-template#6`, closed 2026-08-20). Phase 7 (Enhancement Workflow) opened: **step 3.11 and 7.1 (Codebase Ingestion Agent + Stage 0a wiring) checked off — built, live-verified across three real throwaway test issues (`forge-template` #7/#8/#9: Greenfield no-op, Enhancement happy path, Layer 2 mismatch backstop), per `docs/FORGE-Phase7-Ingestion-Agent-Spec.md` and context doc v67.** New this step: `core/agents/ingestion_agent.py`, `github_helper.get_repo_tree()`, a conditional Stage 0a step inside `00-intake.yml` (no new workflow file/label), and optional `existing-architecture-summary.md` fetches in `requirements_agent.py`/`design_agent.py` with graceful-absence handling. **Step 7.2 remains unchecked — next action.** A candidate enhancement target was proposed but not yet confirmed by Mike: a read-only coverage-history view surfacing REQ-2026-03's already-recorded claim/release event log (per R-010 and the Overview tab's out-of-scope note), additive only, no write-path changes. Needs explicit confirmation before the 7.2/7.3 spec (fresh chat, per one-doc-per-chat convention) is drafted.

**v10 update (2026-08-31) — reconciliation, not new work:** this session discovered Phase 7 steps 7.2–7.8 had **already substantially happened**, just never linked back to this doc. The candidate proposed in v9 (coverage-history view) was in fact chosen, built, and deployed as **REQ-2026-04** (tracking issue `forge-template#10`, feature PR `forge-demo-apps#32`, existing service REQ-2026-03) during the Item #24/#25/#26/#28 fix cycle, which used it as the real live test target. Nobody had explicitly confirmed "yes, run with this candidate" as a standalone decision — it happened implicitly as those items got verified against real requests. Live evidence gathered via Claude Code CLI (GitHub + ADO REST APIs) 2026-08-31: **7.2, 7.3, 7.4, 7.5, 7.6, and 7.8 are now checked off below against that evidence. 7.7 is confirmed *attempted* but did *not* land as originally intended** — see 7.7's note for the real gap this surfaced (logged as Backlog Item #32). `forge-template#10` itself remains **open** (labels `qa-approved`+`security-approved`, PR #32 merged 2026-08-29) — closing it is a small separate bookkeeping call for Mike, not blocked on anything above.

**v11 update (2026-08-31) — Phase 7 closed out fully.** Step 7.7's gap (ADO
Enhancement work landing as a disconnected parallel Epic instead of linking
to the real existing Epic) was resolved same-day as **Backlog Item #32**:
`create_ado_items.py` gained `_resolve_existing_epic_id()`, live-verified
against a throwaway existing-service Epic (commits `bbbe3d0`, `759cc58`,
`c4b3d0c`). Separately, **Backlog Item #33** resolved the
`forge-template#10` bookkeeping gap — that tracking issue is now closed.
Phase 7 is fully complete, all steps checked.

---

## Phase 1 — Repo Foundation

> Goal: A real GitHub template repository exists with the right structure, configs, and workflow stubs. Nothing runs yet, but everything has a home.

- [x] 1.1 Create the `forge-template` GitHub repository (template repo setting enabled)
- [x] 1.2 Create the FORGE repo folder structure:
  - `.github/workflows/` — Actions workflow files
  - `.github/ISSUE_TEMPLATE/` — Tracking issue template
  - `core/agents/` — Agent scripts (locked layer)
  - `core/schemas/` — JSON schemas for stage artifacts
  - `core/decisions/` — ADRs
  - `team/personas/` — Agent persona overrides
  - `tracking/` — Tracking utilities
- [x] 1.3 Create `team/config.yaml` — main team-layer config (ADO org/project, monorepo name, area path, tags, Container Apps defaults)
- [x] 1.4 Create `team/stack-preferences.yaml` — Design Agent input (CSS approach, component library, ORM, state management, logging)
- [x] 1.5 Create the FORGE tracking issue template (`.github/ISSUE_TEMPLATE/forge-request.yml`) — request ID, request type, intake spreadsheet attachment slot, status checklist
- [x] 1.6 Create `.gitignore` appropriate for a Python + Node environment
- [x] 1.7 Create `README.md` — drop in Document 9 (FORGE README)
- [x] 1.8 Write the 10 seed ADRs into `core/decisions/` (stubs with title, status, context, decision, consequences — full content to follow). *(Was 9 — ADR-0010 adds a 10th; confirm Document 4 update has landed before writing stubs, since it defines the full seed ADR list.)*
- [x] 1.9 Create GitHub Actions workflow stubs (`.github/workflows/`) for all 7 stages — guard clause + job skeleton, no agent logic yet:
  - `00-intake.yml`
  - `01-requirements.yml`
  - `02-design.yml`
  - `03-implementation.yml`
  - `04-qa.yml`
  - `05-security.yml`
  - `06-deploy.yml`
- [x] 1.10 Commit and push — verify repo loads cleanly on GitHub, template flag is on

---

## Phase 2 — Infrastructure Setup

> Goal: Every external dependency is provisioned, credentialed, and verified before any agent code is written.

- [x] 2.1 **GitHub App — `forge-pipeline`**
  - Create the GitHub App in your personal/org GitHub account
  - Set permissions: Contents (R/W), Pull requests (R/W), Issues (R/W), Checks (R/W), Metadata (R)
  - Leave Webhook → Active unchecked (not needed — workflows call the GitHub/Anthropic APIs directly using a generated token)
  - Generate and download the private key (.pem)
  - Install the app on the monorepo (not org-wide)
  - Store `FORGE_APP_ID` and `FORGE_APP_PRIVATE_KEY` as repo-level secrets in the FORGE repo
  - Also store the App's **Client ID** (a separate value from the App ID, shown on the same settings page) as a repo-level **variable** named `FORGE_APP_CLIENT_ID` — required because `actions/create-github-app-token@v3` (the current major version as of mid-2026) reads `client-id` rather than the older `app-id` input; older action versions rely on a Node.js runtime GitHub has deprecated and won't be updated
- [x] 2.2 **Azure Container Registry**
  - Create an ACR instance (Basic tier, ~$0.17/day)
  - Note the login server URL
  - Create a service principal or admin credentials for GitHub Actions push access
  - Store credentials as FORGE repo secrets: `ACR_LOGIN_SERVER`, `ACR_USERNAME`, `ACR_PASSWORD`
- [x] 2.3 **Azure Container Apps — staging environment**
  - Create `forge-staging` Container Apps environment
  - Settings: min 0 replicas, max 2, 0.25 vCPU / 0.5 Gi, single active revision
  - Note: the Azure Portal only creates an environment as a byproduct of creating a Container App (no standalone option) — the CLI (`az containerapp env create`) doesn't have this restriction, if scripting this step
- [x] 2.4 **Azure Container Apps — production environment**
  - Create `forge-production` Container Apps environment
  - Settings: min 1 replica, max 5, 0.5 vCPU / 1.0 Gi, single active revision
- [x] 2.5 **GitHub Environments**
  - Create `staging` environment in the FORGE repo (no required reviewers — auto-deploy)
  - Create `production` environment in the FORGE repo (required reviewer: you)
  - Note: these GitHub Environment names (`staging`/`production`) are distinct from the Azure Container Apps environment names above (`forge-staging`/`forge-production`) — don't conflate the two
- [x] 2.6 **ADO connection**
  - Generate a PAT in Azure DevOps (scopes: Work Items R/W, Project R)
  - Store as FORGE repo secret: `ADO_PAT`
  - Store ADO org URL and project name in `team/config.yaml`
  - Verify PAT can create a test work item via the ADO REST API (curl test is fine)
- [x] 2.7 **Anthropic API key**
  - Confirm your personal developer API key is active
  - Store as FORGE repo secret: `ANTHROPIC_API_KEY`
- [x] 2.8 **End-to-end connectivity check**
  - Write a minimal GitHub Actions test workflow that: generates a GitHub App token ✓, pings ADO ✓, pings the Anthropic API (models list) ✓
  - Run it, verify all three green
- [x] 2.9 **Managed Agents access check** *(new — ADR-0010)*
  - Confirm the `ANTHROPIC_API_KEY` has access to the Managed Agents beta (`managed-agents-2026-04-01` header)
  - Create a throwaway single-coordinator, zero-subagent test session via the API to confirm the header, environment, and session lifecycle work end-to-end before Phase 3 agent work begins
  - Note the beta status in the tracking log — this is a candidate for an RFC if the API changes materially during the build phase
  - Note: the session events endpoint expects a nested `{"events": [{"type": "user.message", "content": [...]}]}` body, not a flat `content` field; and a session can transiently report `running` again immediately after appearing `idle` — build a short retry around archive calls rather than treating this as fatal

---

## Phase 3 — Agent Implementation

> Goal: Each agent is a working Python script, callable from the command line, producing the correct output artifact. Wired into GitHub Actions in Phase 4.

> **Order matters:** Implement in pipeline order so each agent's output can be used as the next agent's test input.

- [x] 3.1 **Shared agent utilities** (`core/agents/utils/`)
  - GitHub API helper (post comment, add label, create branch, open PR)
  - ADO API helper (create Epic, Feature, User Story, Bug)
  - File I/O helpers (read XLSX, read/write Markdown, read/write YAML)
  - **Anthropic Messages API wrapper** (`claude_agent_wrapper.py`) *(ADR-0011 — supersedes the originally-planned Claude Agent SDK wrapper)* — calls the base `anthropic` Python client's Messages API directly (system prompt + user prompt, single-turn, no tool-use loop); `invoke_agent()` takes an explicit `max_tokens` parameter and has no `allowed_tools` parameter; `total_cost_usd` is computed from a maintained per-model rate table in the wrapper rather than an SDK-provided value. Used by all stages except Stage 3.
    - **Hard requirement (ADR-0011 / Document 6):** every stage-agent script built in 3.2 onward (except Stage 3) MUST wrap its `invoke_agent()` call in try/except at the call site — the wrapper never sets `is_error=True` itself, so an uncaught API failure aborts the script silently with no `forge_event` log line and no chance to post a failure comment on the tracking issue.
  - **Managed Agents API wrapper** *(ADR-0010)* — standard invocation pattern for starting a coordinator agent session, declaring subagents, polling/streaming the session event stream to completion, and retrieving the per-subagent audit trail. Used only by Stage 3. Build in the correct events-endpoint request shape and archive retry behavior noted in step 2.9 above.
- [x] 3.1a **Commit ADR-0011 to `core/decisions/`** *(new — organic ADR, decided chat 21, verified chat 22)*
  - Write the full ADR-0011 text (see `ADR-0011.md`) into `core/decisions/0011-base-anthropic-client.md`, alongside the ten seed ADR stubs from Phase 1.8
  - Unlike ADR-0010 (folded into the seed list before Phase 1 ran), ADR-0011 was decided mid-build — it's the first ADR added organically after the initial seed set, exercising Document 4's ADR/RFC process as intended for ongoing decisions rather than just the initial ten
- [x] 3.2 **Intake Agent** (`core/agents/intake_agent.py`)
  - Reads the BA's Excel spreadsheet (Overview + Requirements tabs)
  - Produces 5–7 clarifying questions
  - Posts questions as a comment on the tracking issue
  - Applies `clarification-pending` label
- [x] 3.3 **Requirements Agent** (`core/agents/requirements_agent.py`)
  - Reads the spreadsheet + BA's clarification answers from the issue thread
  - Produces `requirements.md` (structured, traceable)
  - Produces draft ADO work item payload (Epics → Features → User Stories)
  - Posts draft as an issue comment for human review (does NOT create ADO items yet)
- [x] 3.4 **Design Agent** (`core/agents/design_agent.py`)
  - Reads `requirements.md` + `team/stack-preferences.yaml`
  - Produces `design.md` (architecture narrative, component breakdown, tech choices)
  - Produces `openapi.yaml` (API contract)
  - Produces `tasks.md` (implementation task list for Backend/Frontend/Test Writer agents)
  - Commits all three to `design/<request-id>` branch, opens PR to `main`
- [x] 3.4a **Implementation Coordinator** (`core/agents/implementation_coordinator.py`) *(new — ADR-0010)*
  - Starts a Managed Agents coordinator agent session scoped to a request ID
  - Declares Backend, Frontend, and Test Writer as specialist subagents, each with its own system prompt and scoped tool access, sharing one sandbox filesystem
  - Passes `design.md`, `openapi.yaml`, and `tasks.md` into the session as coordinator input
  - Runs the three subagents in parallel, waits for all to report complete
  - Synthesizes subagent output, performs integration checking natively (no separate integration-check job)
  - Commits the complete implementation to `feature/<request-id>` in the monorepo and opens a draft PR
  - Closes the agent session; surfaces the Claude Console session URL for the audit trail
- [x] 3.5 **Backend Agent — subagent definition** (`core/agents/subagents/backend_agent.py`) *(reframed — ADR-0010)*
  - Defined as a Managed Agents specialist subagent, not an independently invoked script
  - System prompt + scoped tools for reading `design.md`, `openapi.yaml`, `tasks.md` from the shared sandbox filesystem
  - Produces .NET API implementation (controllers, services, models, xUnit tests) into the sandbox filesystem
  - Does not commit directly — the Implementation Coordinator commits on the subagent's behalf after synthesis
- [x] 3.6 **Frontend Agent — subagent definition** (`core/agents/subagents/frontend_agent.py`) *(reframed — ADR-0010)*
  - Defined as a Managed Agents specialist subagent, running in parallel with Backend
  - System prompt + scoped tools for the same shared sandbox filesystem
  - Produces React/Next.js + TypeScript UI into the sandbox filesystem
  - Does not commit directly — coordinator handles the commit
- [x] 3.7 **Test Writer Agent — subagent definition** (`core/agents/subagents/test_writer_agent.py`) *(reframed — ADR-0010)*
  - Defined as a Managed Agents specialist subagent, running in parallel with the above two
  - Reads `design.md`, `tasks.md`, and the in-progress backend/frontend code from the shared sandbox filesystem
  - Produces Jest integration tests and fills any gaps in xUnit coverage into the sandbox filesystem
  - Does not commit directly — coordinator handles the commit
- [x] 3.8 **QA Agent** (`core/agents/qa_agent.py`)
  - Runs the test suite (via shell) and parses results
  - Files ADO bugs for failures (with steps to reproduce, severity mapping)
  - Posts a test summary comment on the feature PR
  - If failures: applies `qa-loop-back` label; if passing: applies `qa-approved` label
- [x] 3.9 **Security Agent** (`core/agents/security_agent.py`)
  - Runs Semgrep, Gitleaks, OWASP Dependency-Check (via shell)
  - Parses tool output, maps findings to severity
  - Posts severity-tagged inline PR comments
  - If Critical findings: sets a failing check run (blocks merge); otherwise: applies `security-approved` label
- [x] 3.10 **Deploy Agent** (`core/agents/deploy_agent.py`)
  - Builds Docker image, tags with `<request-id>-<commit-sha>`
  - Pushes to ACR
  - Deploys to `forge-staging` Container Apps environment
  - Posts deployment URL as PR comment
- [x] 3.11 **Codebase Ingestion Agent** (`core/agents/ingestion_agent.py`) *(enhancement workflow — completed in Phase 7, not deferred further)*
  - Reads the existing monorepo structure via a new `github_helper.get_repo_tree()` (Git Trees API, `recursive=1`, filtered client-side by path prefix)
  - Two-pass file selection: full filtered tree always included; manifest/config files always read in full; remaining token budget spent on largest/most-central source files by descending size
  - Produces `existing-architecture-summary.md`, committed to `docs/<request-id>/` on `pipeline-state`, fed into the Requirements Agent (and Design Agent) as an optional fetch
  - Layer 2 backstop: if the given "Existing Service Name" doesn't resolve to a real `services/` folder, fails loudly (non-zero exit, posts-then-raises per the ADR-0011 failure contract) rather than guessing — confirmed live via a real mismatch test issue (`forge-template#9`)
  - *(2026-08-27 — done, live-verified across three real throwaway test issues; see `docs/FORGE-Phase7-Ingestion-Agent-Spec.md` and context doc v67 for full detail)*

---

## Phase 4 — Pipeline Wiring

> Goal: The workflow stubs from Phase 1 become fully wired — agents are invoked, state transitions happen, labels flow correctly end-to-end.

- [x] 4.1 Wire `00-intake.yml` — download attachment, invoke Intake Agent, apply label
- [x] 4.2 Wire `01-requirements.yml` — trigger on `clarification-complete` label, invoke Requirements Agent, post draft for review
- [x] 4.3 Wire `02-design.yml` — trigger on `requirements-approved` label, create ADO items, invoke Design Agent, commit artifacts, open design PR
- [x] 4.4 Wire `03-implementation.yml` *(rewritten — ADR-0010)* — trigger on `design-approved` label, invoke the Implementation Coordinator (starts a Managed Agents coordinator agent session with Backend/Frontend/Test Writer as subagents), the workflow job waits on the session event stream rather than running parallel jobs, opens the feature PR as draft once the coordinator commits. No separate integration-check job — integration is native to the coordinator session.
- [x] 4.5 Wire `04-qa.yml` — trigger on feature PR opened, invoke QA Agent, loop-back or apply `qa-approved`
- [x] 4.6 Wire `05-security.yml` — trigger on feature PR opened (parallel with QA), invoke Security Agent, apply label or fail check
- [x] 4.7 Wire `06-deploy.yml` — trigger on both `qa-approved` and `security-approved` labels present, invoke Deploy Agent (staging), pause for production Environment approval
- [x] 4.8 Set branch protection rules on monorepo `main` *(updated — ADR-0010)*:
  - Require PR reviews (1 approver)
  - Require status checks: **security-check** (the standalone integration-check is eliminated — integration is performed natively inside the Managed Agents coordinator session, not as a separate GitHub Actions job)
  - No direct pushes (agents use PRs; humans approve)
  - Applied via `gh api --method PUT repos/Flamespiker/forge-demo-apps/branches/main/protection` from Mike's personal account (the `forge-pipeline` App's permission set has no Administration scope, so it cannot set this itself). `enforce_admins: true` — no bypass, even for Mike. Required GitHub Pro (classic branch protection on private repos is a paid-tier feature); resolved by upgrading rather than making the repo public or migrating to an org.
  - **Follow-on fix (next chat):** once live, this rule correctly blocked `requirements_agent.py`'s and `create_ado_items.py`'s pre-existing direct-to-`main` commits (`docs/<request-id>/requirements.md`, `ado-work-items.json`) — a real gap, not a false positive, since neither file goes through a PR. `bypass_pull_request_allowances` (App-scoped) was the first approach tried; rejected by GitHub with a 422 — that setting is org-only, confirmed both by GitHub's docs and by empirical test against this exact repo, and `forge-demo-apps` is a personal-account repo. Resolved instead by moving both files' target branch to a new, dedicated, deliberately-unprotected `pipeline-state` branch (created once, persistent, not per-request) — the human review for this content already happens via the posted issue comment before `requirements-approved` is applied, so no PR-based rework of the approval gate was needed. Three downstream readers (`create_ado_items.py`, `design_agent.py`, `qa_agent.py`) updated to read from `pipeline-state` explicitly rather than relying on a default that was changing meaning. `design.md`/`openapi.yaml`/`tasks.md` are unaffected — still land on `main` via the real human-reviewed design PR. Branch protection reapplied/reconfirmed clean afterward with no bypass needed.
- [x] 4.9 Verify reciprocal traceability links are written:
  - FORGE tracking issue → monorepo PR URL (written by the Implementation Coordinator)
  - Monorepo PR body → FORGE tracking issue URL (written by the Implementation Coordinator)
- [x] 4.10 Full dry-run: trigger a pipeline with a dummy spreadsheet, walk every stage manually confirming labels, comments, and artifacts appear correctly (no deployment). For Stage 3, also confirm the Claude Console per-subagent audit trail is reachable from the coordinator session. *(Done for real, chat 39, `DRYRUN-2026-01` — a real GitHub Actions platform incident hit mid-run, unrelated to FORGE config; cleared and re-ran clean. Its staging Container Apps were later torn down; confirmed already gone as of the chat 44 teardown.)*

---

## Phase 5 — App 1: Greenfield Pipeline Validation

> Goal: Run the complete pipeline end-to-end on a real (small) app. Fix everything that breaks. This is the "proof it works" run.

**Status: substantially complete.** App 1 = "Inactive User & License Auditor" (`REQ-2026-02`), a read-only D365 Dataverse admin tool. Full detail, including the R-001 descope, every confirmed-not-fixed structural gap, real manual-intervention count, and a go/no-go read for Phase 6, is in `FORGE-Phase5-Closeout.md`. App 1's Azure Container Apps and D365 connection were decommissioned 2026-08-13 (code retained in `forge-demo-apps`); see the context doc's chat 44 entry for the teardown record.

- [x] 5.1 Write a simple BA intake spreadsheet for App 1 (suggest: a basic internal tool — something with a small API surface and a simple UI)
- [x] 5.2 Stage 0b — upload spreadsheet to tracking issue, apply `intake-ready`, review Intake Agent questions
- [x] 5.3 Answer clarifying questions, apply `clarification-complete`
- [x] 5.4 Stage 1 — review Requirements Agent draft, approve ADO items, apply `requirements-approved`
- [x] 5.5 Stage 2 — review Design Agent output (design.md, openapi.yaml, tasks.md), approve design PR, apply `design-approved`
- [x] 5.6 Stage 3 *(updated — ADR-0010)* — review implementation PR (backend + frontend + tests), confirm the coordinator ran Backend/Frontend/Test Writer as subagents in parallel via the Claude Console session audit trail, approve PR *(required a real recovery cycle — Stage 3's completion-detection bug, see `FORGE-Stage3-Completion-Detection-Spec.md` — not a clean first pass)*
- [x] 5.7 Stage 4 — review QA report, confirm bugs filed (or clean run), apply `qa-approved` *(passed on the 3rd of 3 automated attempts against real bugs, not a clean first pass)*
- [x] 5.8 Stage 5 — review Security Agent findings, confirm no Critical blockers, apply `security-approved`
- [x] 5.9 Stage 6 — confirm staging deployment, click production approval gate, confirm production deployment *(staging only — confirmed live and working in a real browser; production deliberately not attempted, not appropriate for a validation run. Moot now: this app's infrastructure has since been decommissioned.)*
- [ ] 5.10 Record actuals *(updated — ADR-0010)*: GitHub Actions minutes consumed, Anthropic API token cost, and Managed Agents session-hours for the Stage 3 run — update Document 3 cost summary *(partial — some real figures captured in the context doc, never fully transcribed into `docs/FORGE-pipeline-cost-log.md`. Outstanding — do before Phase 6.)*
- [x] 5.11 Document all fixes made during App 1 run — anything patched mid-run becomes a follow-up task *(see `FORGE-Phase5-Closeout.md` §4–5 for the full list of confirmed structural gaps and manual interventions, and §7–8 for what's carried forward into Phase 6)*

---

## Phase 6 — App 2: Repeatability

> Goal: Run the pipeline again on a second small app with no fixes mid-run. If it completes cleanly, the pipeline is proven repeatable.

**Status: complete.** App 2 = "On-Call Roster Tracker" (`REQ-2026-03`), a write-heavy, Postgres-backed app with real Azure AD SSO. FORGE tracking issue `forge-template#6` closed 2026-08-20. Code retained in `forge-demo-apps`; staging Container Apps/Postgres left running (no decommission requested, unlike Phase 5's App 1) — Postgres server must be manually stopped after each testing session per standing procedure.

- [x] 6.1 Write a second BA intake spreadsheet for App 2 (different domain from App 1)
- [x] 6.2 Run all pipeline stages gate-by-gate (same sequence as Phase 5)
- [x] 6.3 Confirm no mid-run patches required
- [x] 6.4 Record actuals — compare to App 1 metrics, including Managed Agents session-hour cost trend
- [x] 6.5 Note any Orchestration Manager Guide gaps discovered during App 2 — update Document 6 (including any Managed Agents failure-handling gaps)

---

## Phase 7 — Enhancement Workflow

> Goal: Prove the enhancement path works. Run a targeted enhancement to App 1 or App 2 through the pipeline, including Codebase Ingestion.

**Status: complete** (see v11 update note above). REQ-2026-04 (coverage-history view for REQ-2026-03) proved the full enhancement path end-to-end — Stage 0a through Deploy, live in staging, visually confirmed by Mike. The one gap found during the 2026-08-31 reconciliation (7.7, ADO Epic linkage) was resolved same-day as Item #32. `forge-template#10` is closed (Item #33).

- [x] 7.1 Complete Codebase Ingestion Agent (3.11 above, if deferred) *(2026-08-27 — done, live-verified; see 3.11 above and `docs/FORGE-Phase7-Ingestion-Agent-Spec.md`)*
- [x] 7.2 Choose a small, well-scoped enhancement to App 1 or App 2 *(2026-08-31 reconciliation — confirmed done: REQ-2026-04, a read-only coverage-history view for REQ-2026-03 surfacing the claim/release event log, per R-010. Intake spreadsheet: `docs/FORGE-Intake-REQ-2026-04-CoverageHistoryView.xlsx`. No standalone "go" decision was ever recorded — it happened implicitly during the Item #24/#25/#26/#28 fix cycle, which used this real request as its live test target.)*
- [x] 7.3 Write the BA intake spreadsheet for the enhancement (Request Type = Enhancement) *(2026-08-31 reconciliation — confirmed live: Overview sheet C12=Enhancement, C13=REQ-2026-03; R-001–R-005 describe the coverage-history view word for word)*
- [x] 7.4 Stage 0a — confirm ingestion agent reads the target service folder and produces an architecture summary *(2026-08-31 reconciliation — confirmed: `docs/REQ-2026-04/existing-architecture-summary.md` committed to `pipeline-state`, commit `ffdd65b`, 2026-08-27T02:44:11Z, real non-dry-run run. Two earlier "existing service not found" comments on the tracking issue were from the spreadsheet's existing-service field still holding instructional example text, not an ingestion agent bug.)*
- [x] 7.5 Run all pipeline stages (same sequence, plus ingestion summary fed into Requirements Agent) *(2026-08-31 reconciliation — confirmed all stages ran for real: `docs/REQ-2026-04/requirements.md` committed 2026-08-27T02:56:54Z; design (design.md/openapi.yaml/tasks.md) via `forge-demo-apps#30`, merged 2026-08-27T03:09:05Z; Implementation/QA/Security/Deploy per Items #24/#25/#26/#28)*
- [x] 7.6 Confirm the enhancement lands on the correct existing `services/<n>/` folder, not a new one *(confirmed — 19 files changed, all under `services/REQ-2026-03/`, per Item #24; Deploy updated the existing live Container Apps in place, zero new `req-2026-04-*` resources, per Item #28)*
- [x] 7.7 Confirm ADO bug parent links correctly to the original User Story (or a new one under the existing Epic) *(RESOLVED 2026-08-31 — Item #32: `create_ado_items.py` gained `existing_service`/`--existing-service` and `_resolve_existing_epic_id()`; Enhancement Features/User Stories now parent under the existing service's real Epic instead of a new disconnected one. Live-verified against a throwaway existing-service Epic to avoid polluting real backlog data. Greenfield path confirmed unchanged. Commits: `bbbe3d0`, `759cc58`, `c4b3d0c`. Note: REQ-2026-04's original QA bug #178 remains parented under the old disconnected Epic #169 from before this fix — the mechanism is corrected going forward, not retroactively.)*
- [x] 7.8 Record actuals *(2026-08-31 reconciliation — confirmed present in `docs/FORGE-pipeline-cost-log.md`, filed as part of Item #12's 2026-08-31 backfill: Intake/Ingestion/Requirements/Design costs plus three Stage 3 Managed Agents sessions and QA/Security run costs across the multi-attempt fix cycle, kept distinct from REQ-2026-03's original-build figures)*

---

## Phase 8 — Handoff Readiness

> Goal: FORGE is ready to hand to a second Orchestration Manager to clone and operate without your help.

- [ ] 8.1 Final review of Document 6 (Orchestration Manager Guide) against everything learned in Phases 5–7 — update where reality differed from the doc
- [ ] 8.2 Final review of Document 7 (Customization Reference) — confirm all locked/flexible/open items are accurate
- [ ] 8.3 Confirm all eleven ADRs in `core/decisions/` are fully written (not stubs) — the ten seed ADRs from Phase 1.8, plus ADR-0011 (organically added mid-build per step 3.1a, not part of the original seed set)
- [ ] 8.4 Run the setup verification workflow (Phase 2.8–2.9) on a fresh clone — confirms a new Orchestration Manager can get from clone to verified config (including Managed Agents access) without hand-holding
- [ ] 8.5 Tag the repo `v1.0.0` — first stable release of the FORGE template

---

## Notes

- **One step at a time.** Don't start a step until the previous one is confirmed working.
- **Record mid-run fixes.** Anything patched during App 1/2 runs should be logged — it's either a doc gap or a real bug to fix before v1.0.0.
- **ADO PAT:** Acceptable for all build phases. Evaluate service principal before handing off to production teams.
- **Docker Desktop:** Verify LAA non-profit eligibility or standardize on Rancher Desktop before production rollout.
- **Managed Agents beta:** Monitor for breaking changes to the `managed-agents-2026-04-01` header behaviour throughout the build phase. If the API changes materially, evaluate impact on Stage 3 and raise as an RFC if core-layer changes are required.
