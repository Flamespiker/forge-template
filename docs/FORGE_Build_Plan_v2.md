# FORGE — Build Phase Project Plan

**Purpose:** Step-by-step checklist for building FORGE from scratch. Work through one item at a time. Each step is a discrete unit — complete it, confirm it, move on.

**Version:** v2 — updated for ADR-0010 (Managed Agents adoption for Stage 3). Replaces the original Build Plan. Changes are confined to Phase 2 (one new step), Phase 3 (steps 3.1, 3.4a new, 3.5–3.7 reframed as subagent definitions), Phase 4 (step 4.4 rewritten, step 4.8 updated), and the Stage 3 review language in Phases 5–7. All other phases are unchanged from v1.

---

## Phase 1 — Repo Foundation

> Goal: A real GitHub template repository exists with the right structure, configs, and workflow stubs. Nothing runs yet, but everything has a home.

- [ ] 1.1 Create the `forge-template` GitHub repository (template repo setting enabled)
- [ ] 1.2 Create the FORGE repo folder structure:
  - `.github/workflows/` — Actions workflow files
  - `.github/ISSUE_TEMPLATE/` — Tracking issue template
  - `core/agents/` — Agent scripts (locked layer)
  - `core/schemas/` — JSON schemas for stage artifacts
  - `core/decisions/` — ADRs
  - `team/personas/` — Agent persona overrides
  - `tracking/` — Tracking utilities
- [ ] 1.3 Create `team/config.yaml` — main team-layer config (ADO org/project, monorepo name, area path, tags, Container Apps defaults)
- [ ] 1.4 Create `team/stack-preferences.yaml` — Design Agent input (CSS approach, component library, ORM, state management, logging)
- [ ] 1.5 Create the FORGE tracking issue template (`.github/ISSUE_TEMPLATE/forge-request.yml`) — request ID, request type, intake spreadsheet attachment slot, status checklist
- [ ] 1.6 Create `.gitignore` appropriate for a Python + Node environment
- [ ] 1.7 Create `README.md` — drop in Document 9 (FORGE README)
- [ ] 1.8 Write the 10 seed ADRs into `core/decisions/` (stubs with title, status, context, decision, consequences — full content to follow). *(Was 9 — ADR-0010 adds a 10th; confirm Document 4 update has landed before writing stubs, since it defines the full seed ADR list.)*
- [ ] 1.9 Create GitHub Actions workflow stubs (`.github/workflows/`) for all 7 stages — guard clause + job skeleton, no agent logic yet:
  - `00-intake.yml`
  - `01-requirements.yml`
  - `02-design.yml`
  - `03-implementation.yml`
  - `04-qa.yml`
  - `05-security.yml`
  - `06-deploy.yml`
- [ ] 1.10 Commit and push — verify repo loads cleanly on GitHub, template flag is on

---

## Phase 2 — Infrastructure Setup

> Goal: Every external dependency is provisioned, credentialed, and verified before any agent code is written.

- [ ] 2.1 **GitHub App — `forge-pipeline`**
  - Create the GitHub App in your personal/org GitHub account
  - Set permissions: Contents (R/W), Pull requests (R/W), Issues (R/W), Checks (R/W), Metadata (R)
  - Generate and download the private key (.pem)
  - Install the app on the monorepo (not org-wide)
  - Store `FORGE_APP_ID` and `FORGE_APP_PRIVATE_KEY` as repo-level secrets in the FORGE repo
- [ ] 2.2 **Azure Container Registry**
  - Create an ACR instance (Basic tier, ~$0.17/day)
  - Note the login server URL
  - Create a service principal or admin credentials for GitHub Actions push access
  - Store credentials as FORGE repo secrets: `ACR_LOGIN_SERVER`, `ACR_USERNAME`, `ACR_PASSWORD`
- [ ] 2.3 **Azure Container Apps — staging environment**
  - Create `forge-staging` Container Apps environment
  - Settings: min 0 replicas, max 2, 0.25 vCPU / 0.5 Gi, single active revision
- [ ] 2.4 **Azure Container Apps — production environment**
  - Create `forge-production` Container Apps environment
  - Settings: min 1 replica, max 5, 0.5 vCPU / 1.0 Gi, single active revision
- [ ] 2.5 **GitHub Environments**
  - Create `staging` environment in the FORGE repo (no required reviewers — auto-deploy)
  - Create `production` environment in the FORGE repo (required reviewer: you)
- [ ] 2.6 **ADO connection**
  - Generate a PAT in Azure DevOps (scopes: Work Items R/W, Project R)
  - Store as FORGE repo secret: `ADO_PAT`
  - Store ADO org URL and project name in `team/config.yaml`
  - Verify PAT can create a test work item via the ADO REST API (curl test is fine)
- [ ] 2.7 **Anthropic API key**
  - Confirm your personal developer API key is active
  - Store as FORGE repo secret: `ANTHROPIC_API_KEY`
- [ ] 2.8 **End-to-end connectivity check**
  - Write a minimal GitHub Actions test workflow that: generates a GitHub App token ✓, pings ADO ✓, pings the Anthropic API (models list) ✓
  - Run it, verify all three green
- [ ] 2.9 **Managed Agents access check** *(new — ADR-0010)*
  - Confirm the `ANTHROPIC_API_KEY` has access to the Managed Agents beta (`managed-agents-2026-04-01` header)
  - Create a throwaway single-coordinator, zero-subagent test session via the API to confirm the header, environment, and session lifecycle work end-to-end before Phase 3 agent work begins
  - Note the beta status in the tracking log — this is a candidate for an RFC if the API changes materially during the build phase

---

## Phase 3 — Agent Implementation

> Goal: Each agent is a working Python script, callable from the command line, producing the correct output artifact. Wired into GitHub Actions in Phase 4.

> **Order matters:** Implement in pipeline order so each agent's output can be used as the next agent's test input.

- [ ] 3.1 **Shared agent utilities** (`core/agents/utils/`)
  - GitHub API helper (post comment, add label, create branch, open PR)
  - ADO API helper (create Epic, Feature, User Story, Bug)
  - File I/O helpers (read XLSX, read/write Markdown, read/write YAML)
  - Claude Agent SDK wrapper (standard invocation pattern, logging) — used by all stages except Stage 3
  - **Managed Agents API wrapper** *(new — ADR-0010)* — standard invocation pattern for starting a coordinator agent session, declaring subagents, polling/streaming the session event stream to completion, and retrieving the per-subagent audit trail. Used only by Stage 3.
- [ ] 3.2 **Intake Agent** (`core/agents/intake_agent.py`)
  - Reads the BA's Excel spreadsheet (Overview + Requirements tabs)
  - Produces 5–7 clarifying questions
  - Posts questions as a comment on the tracking issue
  - Applies `clarification-pending` label
- [ ] 3.3 **Requirements Agent** (`core/agents/requirements_agent.py`)
  - Reads the spreadsheet + BA's clarification answers from the issue thread
  - Produces `requirements.md` (structured, traceable)
  - Produces draft ADO work item payload (Epics → Features → User Stories)
  - Posts draft as an issue comment for human review (does NOT create ADO items yet)
- [ ] 3.4 **Design Agent** (`core/agents/design_agent.py`)
  - Reads `requirements.md` + `team/stack-preferences.yaml`
  - Produces `design.md` (architecture narrative, component breakdown, tech choices)
  - Produces `openapi.yaml` (API contract)
  - Produces `tasks.md` (implementation task list for Backend/Frontend/Test Writer agents)
  - Commits all three to `design/<request-id>` branch, opens PR to `main`
- [ ] 3.4a **Implementation Coordinator** (`core/agents/implementation_coordinator.py`) *(new — ADR-0010)*
  - Starts a Managed Agents coordinator agent session scoped to a request ID
  - Declares Backend, Frontend, and Test Writer as specialist subagents, each with its own system prompt and scoped tool access, sharing one sandbox filesystem
  - Passes `design.md`, `openapi.yaml`, and `tasks.md` into the session as coordinator input
  - Runs the three subagents in parallel, waits for all to report complete
  - Synthesizes subagent output, performs integration checking natively (no separate integration-check job)
  - Commits the complete implementation to `feature/<request-id>` in the monorepo and opens a draft PR
  - Closes the agent session; surfaces the Claude Console session URL for the audit trail
- [ ] 3.5 **Backend Agent — subagent definition** (`core/agents/subagents/backend_agent.py`) *(reframed — ADR-0010)*
  - Defined as a Managed Agents specialist subagent, not an independently invoked script
  - System prompt + scoped tools for reading `design.md`, `openapi.yaml`, `tasks.md` from the shared sandbox filesystem
  - Produces .NET API implementation (controllers, services, models, xUnit tests) into the sandbox filesystem
  - Does not commit directly — the Implementation Coordinator commits on the subagent's behalf after synthesis
- [ ] 3.6 **Frontend Agent — subagent definition** (`core/agents/subagents/frontend_agent.py`) *(reframed — ADR-0010)*
  - Defined as a Managed Agents specialist subagent, running in parallel with Backend
  - System prompt + scoped tools for the same shared sandbox filesystem
  - Produces React/Next.js + TypeScript UI into the sandbox filesystem
  - Does not commit directly — coordinator handles the commit
- [ ] 3.7 **Test Writer Agent — subagent definition** (`core/agents/subagents/test_writer_agent.py`) *(reframed — ADR-0010)*
  - Defined as a Managed Agents specialist subagent, running in parallel with the above two
  - Reads `design.md`, `tasks.md`, and the in-progress backend/frontend code from the shared sandbox filesystem
  - Produces Jest integration tests and fills any gaps in xUnit coverage into the sandbox filesystem
  - Does not commit directly — coordinator handles the commit
- [ ] 3.8 **QA Agent** (`core/agents/qa_agent.py`)
  - Runs the test suite (via shell) and parses results
  - Files ADO bugs for failures (with steps to reproduce, severity mapping)
  - Posts a test summary comment on the feature PR
  - If failures: applies `qa-loop-back` label; if passing: applies `qa-approved` label
- [ ] 3.9 **Security Agent** (`core/agents/security_agent.py`)
  - Runs Semgrep, Gitleaks, OWASP Dependency-Check (via shell)
  - Parses tool output, maps findings to severity
  - Posts severity-tagged inline PR comments
  - If Critical findings: sets a failing check run (blocks merge); otherwise: applies `security-approved` label
- [ ] 3.10 **Deploy Agent** (`core/agents/deploy_agent.py`)
  - Builds Docker image, tags with `<request-id>-<commit-sha>`
  - Pushes to ACR
  - Deploys to `forge-staging` Container Apps environment
  - Posts deployment URL as PR comment
- [ ] 3.11 **Codebase Ingestion Agent** (`core/agents/ingestion_agent.py`) *(enhancement workflow only — can defer to Phase 7)*
  - Reads the existing monorepo structure
  - Produces an architecture summary fed into the Requirements Agent

---

## Phase 4 — Pipeline Wiring

> Goal: The workflow stubs from Phase 1 become fully wired — agents are invoked, state transitions happen, labels flow correctly end-to-end.

- [ ] 4.1 Wire `00-intake.yml` — download attachment, invoke Intake Agent, apply label
- [ ] 4.2 Wire `01-requirements.yml` — trigger on `clarification-complete` label, invoke Requirements Agent, post draft for review
- [ ] 4.3 Wire `02-design.yml` — trigger on `requirements-approved` label, create ADO items, invoke Design Agent, commit artifacts, open design PR
- [ ] 4.4 Wire `03-implementation.yml` *(rewritten — ADR-0010)* — trigger on `design-approved` label, invoke the Implementation Coordinator (starts a Managed Agents coordinator agent session with Backend/Frontend/Test Writer as subagents), the workflow job waits on the session event stream rather than running parallel jobs, opens the feature PR as draft once the coordinator commits. No separate integration-check job — integration is native to the coordinator session.
- [ ] 4.5 Wire `04-qa.yml` — trigger on feature PR opened, invoke QA Agent, loop-back or apply `qa-approved`
- [ ] 4.6 Wire `05-security.yml` — trigger on feature PR opened (parallel with QA), invoke Security Agent, apply label or fail check
- [ ] 4.7 Wire `06-deploy.yml` — trigger on both `qa-approved` and `security-approved` labels present, invoke Deploy Agent (staging), pause for production Environment approval
- [ ] 4.8 Set branch protection rules on monorepo `main` *(updated — ADR-0010)*:
  - Require PR reviews (1 approver)
  - Require status checks: **security-check** (the standalone integration-check is eliminated — integration is performed natively inside the Managed Agents coordinator session, not as a separate GitHub Actions job)
  - No direct pushes (agents use PRs; humans approve)
- [ ] 4.9 Verify reciprocal traceability links are written:
  - FORGE tracking issue → monorepo PR URL (written by the Implementation Coordinator)
  - Monorepo PR body → FORGE tracking issue URL (written by the Implementation Coordinator)
- [ ] 4.10 Full dry-run: trigger a pipeline with a dummy spreadsheet, walk every stage manually confirming labels, comments, and artifacts appear correctly (no deployment). For Stage 3, also confirm the Claude Console per-subagent audit trail is reachable from the coordinator session.

---

## Phase 5 — App 1: Greenfield Pipeline Validation

> Goal: Run the complete pipeline end-to-end on a real (small) app. Fix everything that breaks. This is the "proof it works" run.

- [ ] 5.1 Write a simple BA intake spreadsheet for App 1 (suggest: a basic internal tool — something with a small API surface and a simple UI)
- [ ] 5.2 Stage 0b — upload spreadsheet to tracking issue, apply `intake-ready`, review Intake Agent questions
- [ ] 5.3 Answer clarifying questions, apply `clarification-complete`
- [ ] 5.4 Stage 1 — review Requirements Agent draft, approve ADO items, apply `requirements-approved`
- [ ] 5.5 Stage 2 — review Design Agent output (design.md, openapi.yaml, tasks.md), approve design PR, apply `design-approved`
- [ ] 5.6 Stage 3 *(updated — ADR-0010)* — review implementation PR (backend + frontend + tests), confirm the coordinator ran Backend/Frontend/Test Writer as subagents in parallel via the Claude Console session audit trail, approve PR
- [ ] 5.7 Stage 4 — review QA report, confirm bugs filed (or clean run), apply `qa-approved`
- [ ] 5.8 Stage 5 — review Security Agent findings, confirm no Critical blockers, apply `security-approved`
- [ ] 5.9 Stage 6 — confirm staging deployment, click production approval gate, confirm production deployment
- [ ] 5.10 Record actuals *(updated — ADR-0010)*: GitHub Actions minutes consumed, Anthropic API token cost, and Managed Agents session-hours for the Stage 3 run — update Document 3 cost summary
- [ ] 5.11 Document all fixes made during App 1 run — anything patched mid-run becomes a follow-up task

---

## Phase 6 — App 2: Repeatability

> Goal: Run the pipeline again on a second small app with no fixes mid-run. If it completes cleanly, the pipeline is proven repeatable.

- [ ] 6.1 Write a second BA intake spreadsheet for App 2 (different domain from App 1)
- [ ] 6.2 Run all pipeline stages gate-by-gate (same sequence as Phase 5)
- [ ] 6.3 Confirm no mid-run patches required
- [ ] 6.4 Record actuals — compare to App 1 metrics, including Managed Agents session-hour cost trend
- [ ] 6.5 Note any Orchestration Manager Guide gaps discovered during App 2 — update Document 6 (including any Managed Agents failure-handling gaps)

---

## Phase 7 — Enhancement Workflow

> Goal: Prove the enhancement path works. Run a targeted enhancement to App 1 or App 2 through the pipeline, including Codebase Ingestion.

- [ ] 7.1 Complete Codebase Ingestion Agent (3.11 above, if deferred)
- [ ] 7.2 Choose a small, well-scoped enhancement to App 1 or App 2
- [ ] 7.3 Write the BA intake spreadsheet for the enhancement (Request Type = Enhancement)
- [ ] 7.4 Stage 0a — confirm ingestion agent reads the target service folder and produces an architecture summary
- [ ] 7.5 Run all pipeline stages (same sequence, plus ingestion summary fed into Requirements Agent)
- [ ] 7.6 Confirm the enhancement lands on the correct existing `services/<name>/` folder, not a new one
- [ ] 7.7 Confirm ADO bug parent links correctly to the original User Story (or a new one under the existing Epic)
- [ ] 7.8 Record actuals

---

## Phase 8 — Handoff Readiness

> Goal: FORGE is ready to hand to a second Orchestration Manager to clone and operate without your help.

- [ ] 8.1 Final review of Document 6 (Orchestration Manager Guide) against everything learned in Phases 5–7 — update where reality differed from the doc
- [ ] 8.2 Final review of Document 7 (Customization Reference) — confirm all locked/flexible/open items are accurate
- [ ] 8.3 Confirm the ten seed ADRs in `core/decisions/` are fully written (not stubs)
- [ ] 8.4 Run the setup verification workflow (Phase 2.8–2.9) on a fresh clone — confirms a new Orchestration Manager can get from clone to verified config (including Managed Agents access) without hand-holding
- [ ] 8.5 Tag the repo `v1.0.0` — first stable release of the FORGE template

---

## Notes

- **One step at a time.** Don't start a step until the previous one is confirmed working.
- **Record mid-run fixes.** Anything patched during App 1/2 runs should be logged — it's either a doc gap or a real bug to fix before v1.0.0.
- **ADO PAT:** Acceptable for all build phases. Evaluate service principal before handing off to production teams.
- **Docker Desktop:** Verify LAA non-profit eligibility or standardize on Rancher Desktop before production rollout.
- **Managed Agents beta:** Monitor for breaking changes to the `managed-agents-2026-04-01` header behaviour throughout the build phase. If the API changes materially, evaluate impact on Stage 3 and raise as an RFC if core-layer changes are required.
