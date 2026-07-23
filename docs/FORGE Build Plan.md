# FORGE — Build Phase Project Plan

**Purpose:** Step-by-step checklist for building FORGE from scratch. Work through one item at a time. Each step is a discrete unit — complete it, confirm it, move on.

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
- [ ] 1.8 Write the 9 seed ADRs into `core/decisions/` (stubs with title, status, context, decision, consequences — full content to follow)
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

---

## Phase 3 — Agent Implementation

> Goal: Each agent is a working Python script, callable from the command line, producing the correct output artifact. Wired into GitHub Actions in Phase 4.

> **Order matters:** Implement in pipeline order so each agent's output can be used as the next agent's test input.

- [ ] 3.1 **Shared agent utilities** (`core/agents/utils/`)
  - GitHub API helper (post comment, add label, create branch, open PR)
  - ADO API helper (create Epic, Feature, User Story, Bug)
  - File I/O helpers (read XLSX, read/write Markdown, read/write YAML)
  - Claude Agent SDK wrapper (standard invocation pattern, logging)
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
- [ ] 3.5 **Backend Agent** (`core/agents/backend_agent.py`)
  - Reads `design.md`, `openapi.yaml`, `tasks.md`
  - Produces .NET API implementation (controllers, services, models, xUnit tests)
  - Commits to `feature/<request-id>` branch under `services/<name>/backend/`
- [ ] 3.6 **Frontend Agent** (`core/agents/frontend_agent.py`)
  - Reads `design.md`, `openapi.yaml`, `tasks.md`
  - Produces React/Next.js + TypeScript UI
  - Commits to `feature/<request-id>` branch under `services/<name>/frontend/`
- [ ] 3.7 **Test Writer Agent** (`core/agents/test_writer_agent.py`)
  - Reads `design.md`, `tasks.md`, and the backend/frontend code committed by the above agents
  - Produces Jest integration tests and fills any gaps in xUnit coverage
  - Commits to `feature/<request-id>` branch under `services/<name>/tests/`
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
- [ ] 4.4 Wire `03-implementation.yml` — trigger on `design-approved` label, run Backend + Frontend + Test Writer agents in parallel jobs, run integration-check job after all three complete, open feature PR as draft
- [ ] 4.5 Wire `04-qa.yml` — trigger on feature PR opened, invoke QA Agent, loop-back or apply `qa-approved`
- [ ] 4.6 Wire `05-security.yml` — trigger on feature PR opened (parallel with QA), invoke Security Agent, apply label or fail check
- [ ] 4.7 Wire `06-deploy.yml` — trigger on both `qa-approved` and `security-approved` labels present, invoke Deploy Agent (staging), pause for production Environment approval
- [ ] 4.8 Set branch protection rules on monorepo `main`:
  - Require PR reviews (1 approver)
  - Require status checks: integration-check, security-check
  - No direct pushes (agents use PRs; humans approve)
- [ ] 4.9 Verify reciprocal traceability links are written:
  - FORGE tracking issue → monorepo PR URL (written by implementation workflow)
  - Monorepo PR body → FORGE tracking issue URL (written by implementation workflow)
- [ ] 4.10 Full dry-run: trigger a pipeline with a dummy spreadsheet, walk every stage manually confirming labels, comments, and artifacts appear correctly (no deployment)

---

## Phase 5 — App 1: Greenfield Pipeline Validation

> Goal: Run the complete pipeline end-to-end on a real (small) app. Fix everything that breaks. This is the "proof it works" run.

- [ ] 5.1 Write a simple BA intake spreadsheet for App 1 (suggest: a basic internal tool — something with a small API surface and a simple UI)
- [ ] 5.2 Stage 0b — upload spreadsheet to tracking issue, apply `intake-ready`, review Intake Agent questions
- [ ] 5.3 Answer clarifying questions, apply `clarification-complete`
- [ ] 5.4 Stage 1 — review Requirements Agent draft, approve ADO items, apply `requirements-approved`
- [ ] 5.5 Stage 2 — review Design Agent output (design.md, openapi.yaml, tasks.md), approve design PR, apply `design-approved`
- [ ] 5.6 Stage 3 — review implementation PR (backend + frontend + tests), confirm parallel jobs ran, approve PR
- [ ] 5.7 Stage 4 — review QA report, confirm bugs filed (or clean run), apply `qa-approved`
- [ ] 5.8 Stage 5 — review Security Agent findings, confirm no Critical blockers, apply `security-approved`
- [ ] 5.9 Stage 6 — confirm staging deployment, click production approval gate, confirm production deployment
- [ ] 5.10 Record actuals: GitHub Actions minutes consumed, Anthropic API cost for the run — update Document 3 cost summary
- [ ] 5.11 Document all fixes made during App 1 run — anything patched mid-run becomes a follow-up task

---

## Phase 6 — App 2: Repeatability

> Goal: Run the pipeline again on a second small app with no fixes mid-run. If it completes cleanly, the pipeline is proven repeatable.

- [ ] 6.1 Write a second BA intake spreadsheet for App 2 (different domain from App 1)
- [ ] 6.2 Run all pipeline stages gate-by-gate (same sequence as Phase 5)
- [ ] 6.3 Confirm no mid-run patches required
- [ ] 6.4 Record actuals — compare to App 1 metrics
- [ ] 6.5 Note any Orchestration Manager Guide gaps discovered during App 2 — update Document 6

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
- [ ] 8.3 Confirm the nine seed ADRs in `core/decisions/` are fully written (not stubs)
- [ ] 8.4 Run the setup verification workflow (Phase 2.8) on a fresh clone — confirms a new Orchestration Manager can get from clone to verified config without hand-holding
- [ ] 8.5 Tag the repo `v1.0.0` — first stable release of the FORGE template

---

## Notes

- **One step at a time.** Don't start a step until the previous one is confirmed working.
- **Record mid-run fixes.** Anything patched during App 1/2 runs should be logged — it's either a doc gap or a real bug to fix before v1.0.0.
- **ADO PAT:** Acceptable for all build phases. Evaluate service principal before handing off to production teams.
- **Docker Desktop:** Verify LAA non-profit eligibility or standardize on Rancher Desktop before production rollout.
