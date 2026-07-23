# FORGE — Project Context & Decision Log

**Project:** FORGE — Full-SDLC Orchestration with Review Gates for Engineers  
**Owner:** Mike Faulkner (mfaulkner@legalaid.ab.ca) — Legal Aid Alberta  
**Last Updated:** 2026-07-23 (Document 1 — FORGE Product Specification — corrected for ADR-0010 — chat 18)  
**Purpose:** Living reference document. Read this at the start of every new chat to restore full project context without re-explanation.

---

## Terminology Note

Two meanings of "session" now exist in the FORGE world. To avoid confusion:

| Term | Meaning |
|------|---------|
| **Chat** or **chat thread** | One Claude.ai conversation — one per document being written (project management) |
| **Agent session** | A running Managed Agents API instance (`/v1/sessions/:id`) — used in Stage 3 |

Documents that discuss Managed Agents always say "agent session" for the API concept. "Chat" or "chat thread" is used for the project management concept throughout this document.

---

## What is FORGE?

FORGE is an AI-orchestrated SDLC platform that takes business requirements from a BA-produced Excel spreadsheet, moves them through a fully staged software development lifecycle, and deploys a working application — with humans only reviewing and approving at defined gates. It is built as a GitHub template repository that developer teams at Legal Aid Alberta clone and manage as their own "orchestration manager" instance.

The core pattern: **deterministic orchestration** (Git operations, state transitions, PR creation) paired with **bounded agent execution** (Claude-powered agents producing artifacts at each stage). Agents do the work. Humans approve the outcomes.

---

## Key Decisions Made

### Intake & Requirements
- Business requirements are gathered **manually by a BA** using a standard Excel spreadsheet template
- The spreadsheet has a dedicated **overview/context tab** (a template the BA fills out: audience, purpose, problem being solved, etc.)
- The Requirements Agent reads the completed spreadsheet, asks a focused set of clarifying questions (5–7 max, one follow-up round if needed), then produces structured requirements
- Requirements are **confirmed by a human before ADO work items are created** — agent produces a draft first
- The ADO integration creates **Epics → Features → User Stories** from the approved requirements
- Full traceability chain: spreadsheet row → ADO User Story → GitHub branch → PR → deployment
- **Intake upload mechanism:** Two options — issue attachment (recommended for build phase; simpler for BAs who are not comfortable with Git) or repository path (`intake/<request-id>.xlsx` via PR). Team-layer choice — Orchestration Manager documents which one the team uses.
- **"Clarification complete" signal:** The BA applies the label `clarification-complete` to the tracking issue when finished answering the agent's questions. Not a keyword reply. If a second clarification round is needed, the BA removes the label, answers, and re-applies it.
- **Excel Intake Template structure:** Three tabs — Instructions (how-to guide, colour legend), Overview (six sections: Request Identification, Request Type, Problem & Purpose, Success Criteria & Scope, Constraints & Considerations, Additional Context), Requirements (one row per requirement with columns: Req #, Type, Priority, User Story / Requirement, Acceptance Criteria, Notes / Constraints). Yellow cells = BA input. Four example rows pre-populated and clearly labelled as examples to replace/delete before submitting.

### Technology Stack
- **Source control & CI/CD:** GitHub (repos + GitHub Actions pipelines)
- **Work item tracking:** Azure DevOps (ADO) Boards — Epics, Features, User Stories
- **Agent runtime:** Anthropic Claude Managed Agents (Stage 3 coordinator/subagent pattern); Claude Agent SDK (all other stages)
- **Primary model:** Claude (Sonnet tier for agentic loops; Opus tier for coordinator in Stage 3 — see ADR-0010)
- **Frontend:** React / Next.js — **TypeScript mandated (core layer)**
- **Backend:** .NET
- **Architecture pattern:** C4 model, microservices (small, manageable domains for mid-sized org)
- **Development methodology:** Spec-driven development
- **Containerization:** Docker, targeting **Azure Container Apps** (migration path from Azure App Service)
- **Current hosting:** Azure App Service (org), personal Azure account (build phase)
- **Anthropic API:** Mike's personal developer API account (build phase), org API account (production)

### Platform Model
- FORGE is a **two-layer platform:**
  - **Core layer (locked):** Security gates, ADO work item structure, naming conventions, branching strategy, deployment standards, Excel intake template format. Standardized across all teams. Not customizable.
  - **Team layer (customizable):** Tech stack specifics, agent personas, additional tools within approved list, notification channels, team-specific skills.
- Delivered as a **GitHub template repository** — teams clone it and own their instance
- Teams can pull core platform updates via the template repo pattern
- The person who owns and maintains a team's FORGE instance is called the **Orchestration Manager** — a developer or tech lead role

### Governance
- Core platform changes require a lightweight **RFC (Request for Comments)** process using GitHub Discussions in the FORGE template repo
- Decisions are recorded as **ADRs (Architecture Decision Records)** in `core/decisions/`
- Decision authority: Core Platform Owner (final approval) + Technical Reviewers (named per RFC) + Orchestration Managers (proposers)
- RFC timeline: 3 business days to assign reviewer, 10 business days review period, 30 days to implement accepted RFCs
- Breaking changes go through RFC with `breaking-change` label; non-breaking bug fixes go direct as PRs
- Team-layer changes need no RFC — Orchestration Manager has full authority within core-layer boundaries
- Nine seed ADRs will be written into `core/decisions/` at initial repo setup (see Document 4)
- **ADR-0010 added** — Managed Agents for Stage 3 implementation coordinator (see Architecture Decisions below)
- Core layer updates are versioned (semantic versioning); teams apply within 30 days (non-security) or 10 days (security gate changes)

### Human Confirmation Gates
Every stage has a human gate before the next stage begins:
1. Requirements — review draft ADO work items, approve before creation
2. Design — review architecture doc and API contracts, approve PR
3. Code — review implementation diff, agents have pre-flagged issues
4. QA sign-off — review test report and bug list
5. Security sign-off — review severity-tagged inline PR comments
6. Deploy approval — one-click GitHub Environment approval

PRs are always **opened by the agent, confirmed/approved by a human** — never the reverse, and no agent merges its own PR.

### Enhancement Workflow
- FORGE handles both **greenfield apps** and **enhancements to existing codebases**
- Enhancements require a **Stage 0 "codebase ingestion"** step — the agent reads the existing repo, understands architecture and conventions, identifies where the change fits — before the Requirements Agent begins
- With the repo model below, "greenfield" means a **new folder under `services/`** in the existing monorepo, not a new repository; "enhancement" means modifying a folder that's already there. Both use the same requirements/design templates — enhancement just adds the ingestion summary as an upstream input.

### Scope & Demo Plan
1. **App 1:** Small greenfield app — validates the full pipeline end-to-end
2. **App 2:** Second greenfield app — proves repeatability
3. **Enhancement:** A targeted enhancement to App 1 or App 2 — proves the enhancement workflow

### Security Approach
- Practical, not regulatory-heavy (LAA is not under heavy AI governance obligations)
- Security gates embedded in the workflow (SAST, secrets detection, OWASP checks)
- Data handling basics and responsible AI principles covered in training
- Client data sensitivity noted as a callout in the AI Foundations Guide

### Training Philosophy
- Two tracks:
  - **Track 1 — AI Foundations:** What LLMs are, how agents work, agentic orchestration concepts, prompt engineering basics, context window awareness, responsible AI, practical AI governance
  - **Track 2 — Orchestration Manager:** Setup, customization boundaries, agent skill management, failure handling, governance process participation
- Includes recommendations for external product training and AI certifications developers should complete
- **Document 5 (AI Foundations) requires updating** to add Claude Cookbooks, Managed Agents quickstart, and multi-agent docs — see "Documents Requiring Updates" below

---

## Architecture Decisions (Document 2)

### Orchestration model
- **Event-driven via GitHub Actions** — no separate long-running orchestrator service. GitHub Actions workflows, triggered by PR/label/issue events, *are* the deterministic orchestration layer.
- **State lives natively in GitHub** — issue labels, PR review state, GitHub Environments with required reviewers. No bespoke state database.
- **Agent invocation is stateless per stage** — each stage (except Stage 3) spins up a fresh Claude Agent SDK call scoped to that stage's inputs/outputs. No persistent cross-stage agent memory; context passes forward as committed files in the target repo. (ADR-0002 — see clarification note below.)
- **ADR-0002 clarification (from ADR-0010):** "Stateless per stage" means no cross-stage memory. Within Stage 3, the Managed Agents coordinator session maintains coordinator-to-subagent state during execution, bounded inside the stage window. The stage still starts from committed files and ends by committing files. The principle is not violated — it is clarified.
- Every workflow opens with a **guard clause** confirming its precondition label is present, to prevent stray events from re-triggering a stage out of order.

### Managed Agents adoption for Stage 3 — ADR-0010

**Decision:** Stage 3 (Implementation) uses an Anthropic Managed Agents coordinator agent with three specialist subagents (Backend, Frontend, Test Writer) rather than three independent GitHub Actions parallel jobs.

**Why:** The parallel-jobs approach required an explicit integration-check job to catch branch commit conflicts between three agents writing to the same feature branch concurrently. The Managed Agents coordinator pattern eliminates this — the coordinator runs the three subagents in parallel on a shared sandbox filesystem, synthesizes their outputs, handles integration naturally, then commits the complete implementation as a single coherent unit and opens the draft PR.

**What changes:**
- The Stage 3 GitHub Actions workflow now invokes one Managed Agents coordinator agent session instead of three parallel jobs
- The integration-check job is eliminated — coordination is native to the Managed Agents session
- Claude Console provides a per-subagent audit trail for Stage 3 in addition to GitHub's audit trail
- Billing: Standard token rates **plus $0.08 per agent session-hour** of active runtime

**What does not change:**
- All other stages remain as standalone stateless Claude Agent SDK calls invoked within GitHub Actions jobs
- GitHub Actions is still the deterministic orchestration layer for all state transitions and gates
- The human gate at Stage 3 (Technical Approver reviewing the draft PR) is unchanged
- The no-self-merge rule applies — the coordinator opens the PR; a human approves and merges it

**Affected documents requiring update:**
- Document 2 (Architecture) — Sections 2.2, 3, 4.5; ADR-0002 clarification note — ✅ done, chat 12
- Document 3 (Tool Inventory) — Managed Agents billing row in Anthropic section — ✅ done, chat 14
- Document 4 (Governance) — ADR-0010 added to seed ADR list (10th ADR) — still outstanding
- Document 5 (AI Foundations) — Section 9 training resources; Section 3 orchestration concepts — ✅ done, chat 15
- Document 6 (Orchestration Manager Guide) — Part 4 failure handling (Managed Agents failures) — ✅ done, chat 16
- Document 7 (Customization Reference) — Agent Configuration section note — ✅ done, chat 16 (scope was larger than "note" — see session note)
- Build Plan — Phase 3 steps 3.5–3.7 become subagent definitions; new step 3.4a coordinator — ✅ done, chat 13
- Document 9 (README) — Minor note on Stage 3 — ✅ done, chat 17 (turned out to be three factual corrections, not just a note — see session note)
- Document 1 (Product Specification) — originally scoped as "No — stage mechanics don't change"; review in chat 18 found Section 3.3 omitted the Implementation Coordinator and misattributed the branch-commit/PR-open action to the subagents — ✅ done, chat 18

**ADR-0010 full text:**

```
# ADR-0010: Anthropic Managed Agents for Implementation Stage Coordination

Status: Accepted
Date: 2026-07-22

Context:
FORGE's implementation stage (Stage 3) requires Backend, Frontend, and
Test Writer agents to run in parallel on the same feature branch. The
original design used three independent GitHub Actions jobs writing
concurrently to the branch, with a separate integration-check job to
catch merge conflicts. Anthropic shipped Managed Agents multi-agent
orchestration (public beta, May 2026) — a native coordinator/subagent
pattern on a shared sandbox filesystem.

Decision:
Stage 3 uses a Managed Agents agent session: one coordinator agent
declares Backend, Frontend, and Test Writer as specialist subagents.
The coordinator runs them in parallel on a shared sandbox filesystem,
synthesizes their results, handles integration checking natively, then
commits the complete implementation to the feature branch and opens the
draft PR. All other stages remain as standalone stateless Claude Agent
SDK calls invoked within GitHub Actions jobs.

ADR-0002 (stateless per stage) remains valid. Stateless means no
cross-stage memory. Within Stage 3, the Managed Agents agent session
maintains coordinator state during execution, bounded by the stage
window. The stage starts from committed files (design.md, openapi.yaml,
tasks.md) and ends by committing files (feature branch). The principle
is not violated — it is clarified.

Consequences:
+ Eliminates branch commit race conditions between parallel agents
+ Integration check is native to the coordinator, not a separate job
+ Claude Console provides per-subagent audit trail for Stage 3
+ Cleaner failure isolation — one agent session failure vs. three job failures
+ Coordinator can check in on subagents mid-workflow
- Managed Agents is beta (managed-agents-2026-04-01 header required)
- Billing: $0.08/agent session-hour active runtime in addition to token costs
  — track actuals during App 1; update Document 3 cost summary
- Managed Agents failure modes differ from standalone job failures —
  Orchestration Manager Guide needs a specific section for this
- Managed Agents multi-agent orchestration is public beta — monitor for
  breaking changes during build phase
```

### Repository model — two repos, not one
- **Existing platform reality:** LAA's custom applications live in a single existing **monorepo** (all microservices, one repo). A separate, existing **Dynamics 365 repo** holds D365 development — out of scope for FORGE v1, flagged as a real future goal.
- **FORGE is a separate repo from the code it acts on.** FORGE's own template repo (workflows, agents, core/team config, the per-request tracking issue) never holds application source. It orchestrates *into* the custom-apps monorepo by opening branches/commits/PRs there.
- **Cross-repo mechanics:** FORGE workflows authenticate into the monorepo via a **GitHub App installation** (scoped, revocable, attributable to "FORGE" rather than a personal token) with permissions limited to branch/commit/PR/comment/check-run operations. Triggering webhooks come from the monorepo; the tracking issue and orchestration state live in the FORGE repo.
- **Structural repo layout:**
  - FORGE repo: `.github/workflows/`, `core/` (agents, schemas — locked), `team/` (personas, config — customizable), `tracking/`
  - Monorepo: `services/<name>/` per microservice (new folder = greenfield, existing folder = enhancement), `docs/<request-id>/` for requirements.md/design.md/tasks.md
- **Branching (in the monorepo):** `main` (always deployable) ← `feature/<request-id>` ← `design/<request-id>`. FORGE's GitHub App creates/pushes these branches on the agents' behalf.
- **Traceability now crosses a repo boundary** (FORGE repo ↔ monorepo) partway through the chain. Full traceability depends on both sides writing the reciprocal link.

### Agent topology
- Ten agents total. All other than Stage 3 are Claude Agent SDK calls invoked within GitHub Actions jobs, none persistent.
- **Stage 3 (Implementation):** One Managed Agents coordinator agent + three specialist subagents (Backend, Frontend, Test Writer). Coordinator runs subagents in parallel on a shared sandbox filesystem. Integration checking is native to the coordinator. (ADR-0010)
- All other stages: Codebase Ingestion, Intake, Requirements, Design, QA, Security, Deploy — stateless single-purpose Claude Agent SDK calls.

### ADO integration
- ADO Epics/Features/User Stories are created only on `requirements-approved` — never speculatively.
- Two-way link maintained between ADO items and the FORGE tracking issue.
- Exact field mapping resolved in Document 3.

### Container & deployment
- Docker images tagged by request ID + commit SHA. Azure Container Apps: `staging` (auto-deploy, no gate) → `production` (GitHub Environment, required-reviewer gate — the one irreversible action, no post-hoc review). Rollback = redeploy prior image tag.

---

## Code-Level Stack Decisions

### What FORGE mandates (core layer — agents need this to produce runnable code)
- **TypeScript** — mandated for all React/Next.js frontend code; baked into Frontend Agent and Test Writer Agent prompts
- **Jest** — mandated test framework for frontend; Test Writer Agent writes Jest tests
- **xUnit** — mandated test framework for .NET backend
- Linting runs as a CI check (core — teams cannot disable); specific ruleset is team-layer configurable

### What is decided at design time by humans (not FORGE's concern)
- CSS approach, component libraries, .NET ORM, state management, logging libraries
- Any stylistic or architectural preference that doesn't affect CI or agent code generation
- These decisions are captured in `design.md` per project and approved by the Technical Approver at the design gate

---

## Tool Decisions (Document 3)

### Security tooling (defaults set)
- **SAST:** Semgrep Community (open source, free)
- **Secrets detection:** Gitleaks (open source, MIT)
- **Dependency vulnerability scanning:** OWASP Dependency-Check (open source, Apache 2.0)
- A Critical finding from any tool sets a failing check run, blocking merge automatically

### Anthropic API billing (updated for Managed Agents)
- **Standard API (all stages except Stage 3):** Per-token, Sonnet tier
- **Managed Agents (Stage 3 coordinator + subagents):** Standard token rates **plus $0.08 per agent session-hour** of active runtime
- Per-pipeline cost estimate: ~$1–5 USD for token costs (Sonnet tier) + $0.08–0.32 for Managed Agents runtime (estimate 1–4 hours per implementation run). Track actuals during App 1.

### ADO field mapping (resolved)
- **FORGE writes automatically:** Title, Description, Acceptance Criteria (User Stories), Parent links, State (Active), Area Path (from team config default), Tags (`forge-managed`, `<request-id>`), traceability links
- **Left to the team:** Story Points, Priority, Iteration Path, Effort, Business Value, custom org fields

### Azure Container Apps environment specifics (resolved)
- Two separate environments: `forge-staging` and `forge-production`
- Staging: scale to zero, max 2 replicas, 0.25 vCPU / 0.5 Gi
- Production: min 1 replica, max 5, 0.5 vCPU / 1.0 Gi
- Rollback = redeploy prior image tag; previous revision retained 48h

### GitHub App permission scoping (resolved)
- App named `forge-pipeline`; installed on the monorepo only
- Permissions: Contents (R/W), Pull requests (R/W), Issues (R/W), Checks (R/W), Metadata (R)
- Credentials stored as repo-level secrets: `FORGE_APP_ID` and `FORGE_APP_PRIVATE_KEY`
- Short-lived installation token generated per job via `actions/create-github-app-token`

### Cost summary (updated)
- Build phase incremental cost: Anthropic API tokens (~$1–5 USD per full pipeline run for token costs, plus ~$0.08–0.32 for Managed Agents runtime — track actuals) + Azure Container Registry (~$0.17/day)
- No net-new SaaS contracts required with default tool choices

---

## Document List (in production order)

| # | Document | Status | Managed Agents Update Required |
|---|----------|--------|-------------------------------|
| 0 | FORGE Introduction | ✅ Complete | No |
| 1 | FORGE Product Specification | ✅ Complete — **updated (chat 18, `01-forge-product-specification_v2.md`)** | Yes — Section 3.3 Implementation Coordinator correction (originally mis-scoped as "No" — see chat 18) |
| 2 | FORGE Architecture Document | ✅ Complete — **needs update** | Yes — Sections 2.2, 3, 4.5; ADR-0002 clarification note |
| 3 | Tool & Licensing Inventory | ✅ Complete — **updated (chat 14, `03_Tooling_v2.md`)** | Done |
| 4 | FORGE Governance Model | ✅ Complete — **needs update** | Yes — ADR-0010 added to seed ADR list |
| 5 | AI Foundations Guide | ✅ Complete — **updated (chat 15, `05_AI_Foundation_v2.md`)** | Done |
| 6 | Orchestration Manager Guide | ✅ Complete — **updated (chat 16, `06_Orchestration_v2.md`)** | Done |
| 7 | Customization Reference | ✅ Complete — **updated (chat 16, `07_Customization_Ref_v2.md`)** | Done |
| 8 | Excel Intake Template | ✅ Complete | No |
| 9 | FORGE README | ✅ Complete — **updated (chat 17, `09-forge-readme_v2.md`)** | Done |
| — | FORGE Build Plan | ✅ Complete — **needs update** | Yes — Phase 3 steps 3.4a, 3.5–3.7; Phase 4 step 4.4 |

**Update priority order for new chats:**
1. ~~Document 2 (Architecture) — highest priority, other docs reference it~~ — done, chat 12
2. **Document 4 (Governance) — seed ADR list needs ADR-0010 — still outstanding, only original priority-list item remaining**
3. ~~Build Plan — build sequence changes before Phase 3~~ — done, chat 13
4. ~~Document 3 (Tool Inventory) — billing update~~ — done, chat 14
5. ~~Document 5 (AI Foundations) — training materials + orchestration concepts~~ — done, chat 15
6. ~~Document 6 (Orchestration Manager Guide) — failure handling~~ — done, chat 16
7. ~~Document 7 (Customization Reference) — Agent Configuration + Pipeline & Orchestration sections~~ — done, chat 16 (turned out to be more than "minor" — see session note)
8. ~~Document 9 (README) — minor update~~ — done, chat 17
9. **Document 4 (Governance) — ADR-0010 seed ADR list — still outstanding; now the only document remaining from the original priority list, deferred three times in favour of other documents**

---

## Pipeline Stages (summary)

| Stage | Name | Trigger | Output | Human Gate | Agent Type |
|-------|------|---------|--------|------------|------------|
| 0a | Codebase Ingestion *(enhancement only)* | Enhancement flagged | Existing architecture summary (monorepo, `docs/<request-id>/`) | No | SDK call |
| 0b | Intake & Clarification | BA uploads spreadsheet | Answered context questions (FORGE tracking issue) | No | SDK call |
| 1 | Requirements | Clarification complete | Draft ADO work items + requirements.md (monorepo) | ✅ Approve ADO items | SDK call |
| 2 | Spec & Design | Requirements approved | design.md, openapi.yaml, tasks.md (monorepo, `design/<request-id>` branch/PR) | ✅ Approve design | SDK call |
| 3 | Implementation | Design approved | Feature branch (backend + frontend + tests, via Managed Agents coordinator, monorepo) | ✅ Review draft PR | **Managed Agents coordinator + 3 subagents** |
| 4 | QA | Implementation PR opened | Test report, bug tickets, loop-back if failures | ✅ QA sign-off | SDK call |
| 5 | Security | Implementation PR opened (parallel with QA) | Severity-tagged PR comments, blocks on Critical | ✅ Security sign-off | SDK call |
| 6 | Deploy | All gates pass | Deployed to Azure Container Apps (staging → prod) | ✅ One-click approval | SDK call |

---

## Agent Roster

- **Intake Agent** — reads BA spreadsheet, asks clarifying questions (SDK call)
- **Requirements Agent** — produces requirements.md and draft ADO work items (SDK call)
- **Design Agent** — produces design.md, openapi.yaml, tasks.md (SDK call)
- **Implementation Coordinator** — Managed Agents coordinator; orchestrates Backend, Frontend, Test Writer subagents in parallel on shared sandbox filesystem; commits complete implementation, opens draft PR (Managed Agents)
- **Backend Agent** — implements .NET API per spec (Managed Agents subagent, parallel)
- **Frontend Agent** — implements React/Next.js UI (Managed Agents subagent, parallel)
- **Test Writer Agent** — writes unit and integration tests (Managed Agents subagent, parallel)
- **QA Agent** — runs tests, files bugs, loop-back to implementation (SDK call)
- **Security Agent** — SAST, OWASP, secrets detection, parallel with QA (SDK call)
- **Deploy Agent** — containerizes, pushes to Azure Container Apps (SDK call)
- **Codebase Ingestion Agent** — reads existing repo for enhancement workflow (SDK call)

---

## Open Questions / To Be Decided

- Whether orchestration managers get a shared skills library to contribute to
- Whether to enforce reciprocal traceability links (FORGE tracking issue ↔ monorepo PR) with a hard workflow failure, or handle it as guidance in the Orchestration Manager Guide
- Future Dynamics 365 support for FORGE — not designed yet, would need its own agent topology
- GitHub Actions minutes actual consumption per pipeline run — measure during App 1 build phase
- **Anthropic API per-run cost actuals (token + Managed Agents session-hour)** — measure during App 1 and App 2 runs; update Document 3 cost summary
- Docker Desktop licensing for local developer use — verify LAA non-profit eligibility or standardize on Rancher Desktop
- ADO service principal vs. PAT — PAT acceptable for build phase; evaluate service principal before production cutover
- **Managed Agents beta stability** — monitor for breaking changes to `managed-agents-2026-04-01` header behaviour during build phase; flag any disruptions as candidates for RFC

---

## Recommended Pre-Build Reading

Before Phase 3 (Agent Implementation), every developer working on the agent layer should read or complete:

| Resource | Priority | Why |
|----------|----------|-----|
| [Anthropic Academy](https://anthropic.skilljar.com) | **Before Phase 3** | Claude API, Agent SDK, MCP — 4–6 hours on the relevant modules |
| [Managed Agents Quickstart](https://platform.claude.com/docs/en/managed-agents/quickstart) | **Before Phase 3** | How to define agents, environments, and agent sessions — directly used in Stage 3 |
| [Managed Agents Multi-agent docs](https://platform.claude.com/docs/en/managed-agents/multi-agent) | **Before Phase 3** | The coordinator/subagent pattern FORGE's Stage 3 is built on |
| [Claude Cookbooks — managed_agents folder](https://github.com/anthropics/claude-cookbooks/tree/main/managed_agents) | **Before Phase 3** | Coordinator running three specialists in parallel — near-exact pattern of Backend/Frontend/Test Writer |
| [Claude Agent SDK docs](https://docs.anthropic.com/en/docs/claude-code/sdk) | **Before Phase 3** | All stages except Stage 3 use this directly |
| [Tool Use overview](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview) | Before Phase 3 | How tool calling works — every agent uses tools |
| GitHub Actions cross-repo auth with GitHub Apps | Before Phase 2 | `actions/create-github-app-token` pattern |
| Azure Container Apps quickstart (Microsoft Learn) | Before Phase 2 | Infrastructure provisioning |
| CCA-F certification | After App 1 | Better understood after real agent work |

---

## Session Notes

- **2026-07-21:** Initial planning session. Full pipeline, tech stack, document list, and platform model established.
- **2026-07-21 (chat 2):** Document 0 — FORGE Introduction — drafted and completed.
- **2026-07-21 (chat 3):** Document 1 — FORGE Product Specification — drafted and completed.
- **2026-07-21 (chat 4):** Document 2 — FORGE Architecture Document — drafted and completed. Major structural correction mid-session: two-repo model established (FORGE repo + existing custom-apps monorepo).
- **2026-07-21 (chat 5, addendum):** Code-level stack decisions finalized. TypeScript/Jest/xUnit mandated at core layer.
- **2026-07-21 (chat 5):** Document 3 — Tool & Licensing Inventory — drafted and completed.
- **2026-07-21 (chat 6):** Document 4 — FORGE Governance Model — drafted and completed. RFC process, ADR format, nine seed ADRs identified.
- **2026-07-21 (chat 7):** Document 5 — AI Foundations Guide — drafted and completed. Nine sections including client data sensitivity callout and external training list.
- **2026-07-21 (chat 8):** Document 6 — Orchestration Manager Guide — drafted and completed. Five parts: setup, running, customization, failure handling, production checklist.
- **2026-07-21 (chat 9):** Document 7 — Customization Reference — drafted and completed. ~65 items explicitly categorized Locked/Flexible/Fully Open.
- **2026-07-21 (chat 10):** Document 8 — Excel Intake Template — created as formatted .xlsx workbook.
- **2026-07-22 (chat 11 — this chat):** Pre-build architectural review. Two decisions made:
  1. **Rejected CrewAI** as the multi-agent framework — conflicts with GitHub Actions as orchestrator, stateless-per-stage design, and human gate architecture. No third-party agent framework adopted.
  2. **Adopted Anthropic Managed Agents for Stage 3** (ADR-0010) — Implementation Coordinator agent runs Backend, Frontend, Test Writer subagents in parallel on a shared sandbox filesystem via Managed Agents multi-agent orchestration. All other stages remain standalone Claude Agent SDK calls. Billing: $0.08/agent session-hour active runtime in addition to token costs.
  - **Terminology note established:** "chat/chat thread" = project writing sessions; "agent session" = Managed Agents API runtime instance.
  - **Training materials:** Claude Cookbooks (managed_agents folder) and Managed Agents docs added to pre-build reading list; Document 5 needs update.
  - **Nine documents identified** as needing Managed Agents updates before build begins. Update priority order documented in Document List section above.
  - Next: Update Document 2 (Architecture) in a new chat, then proceed in priority order before starting Phase 1 of the Build Plan.
- **2026-07-23 (chat 12):** Document 2 (Architecture) updated per the doc2-change-brief — produced `02-forge-architecture-document-v2.md`. Changes applied: Section 2.2 (Managed Agents exception + billing note), ADR-0002 clarification paragraph (in Section 1, where the stateless-invocation text actually lives), Section 3 agent topology table (Implementation Coordinator + 3 subagent rows replacing the old 3-parallel-job rows, plus updated note paragraph), Section 4.5 mechanics rewrite + billing line, Section 9 traceability chain parenthetical, Section 10 new open item (Managed Agents beta stability), new Section 11 (ADR-0010 Reference), "Where This Fits" renumbered to Section 12. No other content changed. File is in `/mnt/user-data/outputs/` awaiting upload to the project to replace `02-forge-architecture-document.md`.
  - Next: Document 4 (Governance) — add ADR-0010 to the seed ADR list — per document list priority order.
- **2026-07-23 (chat 13):** Build Plan updated for ADR-0010 out of priority order (Document 4 still pending — user chose to do the Build Plan next; revisit Document 4 next). Produced `FORGE_Build_Plan_v2.md`, intended to replace `FORGE_Build_Plan.md` in the project. Changes applied: Phase 2 new step 2.9 (Managed Agents access check — beta header, throwaway test session); Phase 3 step 3.1 adds a Managed Agents API wrapper alongside the existing SDK wrapper; new step 3.4a (Implementation Coordinator agent); steps 3.5–3.7 (Backend/Frontend/Test Writer) reframed as Managed Agents subagent definitions rather than independently invoked/committing scripts; Phase 4 step 4.4 rewritten (coordinator session invocation replaces three parallel jobs, no separate integration-check job); step 4.8 branch protection updated (integration-check removed from required status checks); step 4.9/4.10 language updated for coordinator-authored links and Console audit trail. Phase 5 step 5.6 and 5.10 updated for coordinator review language and Managed Agents session-hour cost tracking. Phase 6/7/8 minor references updated (seed ADR count 9→10, Phase 8.4 includes Managed Agents access verification). No other phases changed.
  - File is in `/mnt/user-data/outputs/` awaiting upload to the project — the user will upload it and remove the old `FORGE_Build_Plan.md`.
  - Next: Document 4 (Governance) — add ADR-0010 to the seed ADR list — per document list priority order (still outstanding).
- **2026-07-23 (chat 14):** Document 3 (Tool & Licensing Inventory) updated for ADR-0010 out of priority order (Document 4 still pending — user chose Document 3 next; revisit Document 4 next). Produced `03_Tooling_v2.md`, intended to replace `03_Tooling.md` in the project. Changes applied: §3.3 split the Anthropic API row into Anthropic API (account/billing umbrella), Claude Agent SDK (rescoped to "all stages except Stage 3"), new Managed Agents row (coordinator/subagent runtime, beta header, $0.08/session-hour billing), and renamed model row to "Claude model tiers" (Opus for coordinator, Sonnet elsewhere); cost estimation note updated with the $0.08–0.32/run Managed Agents estimate; §8 Cost Summary table gained a dedicated Managed Agents runtime row and reworded totals; §9 Open Items merged the Anthropic cost-actuals item to cover both token and session-hour costs and added a new Managed Agents beta stability monitoring item. No other sections changed.
  - File is in `/mnt/user-data/outputs/` awaiting upload to the project — the user will upload it and remove the old `03_Tooling.md`.
  - Next: Document 4 (Governance) — add ADR-0010 to the seed ADR list — per document list priority order (still outstanding, now the last document remaining from the original priority list before moving to Documents 5–7 and 9).
- **2026-07-23 (chat 15):** Document 5 (AI Foundations Guide) updated for ADR-0010 out of priority order (Document 4 still pending — user chose Document 5 next; revisit Document 4 next). Produced `05_AI_Foundation_v2.md`, intended to replace `05_AI_Foundation.md` in the project. Changes applied: new Terminology Note section (chat/chat thread vs. agent session, mirroring this context doc); Section 3 new "Managed Agents exception (Stage 3)" callout explaining the coordinator/subagent pattern and why it doesn't violate stateless-per-stage, plus two new reference links; Section 9 gained three new entries after Anthropic Academy and before CCA-F — Managed Agents Quickstart, Managed Agents Multi-agent Patterns, Claude Cookbooks (managed_agents folder). Version 1.0 → 1.1, date updated. No other sections changed.
  - File is in `/mnt/user-data/outputs/` awaiting upload to the project — the user will upload it and remove the old `05_AI_Foundation.md`.
  - Next: Document 4 (Governance) — add ADR-0010 to the seed ADR list — per document list priority order (still outstanding — now the only document remaining from the original priority list before Documents 6, 7, and 9).
- **2026-07-23 (chat 16):** Documents 6 (Orchestration Manager Guide) and 7 (Customization Reference) reviewed against ADR-0010 and updated in the same chat (user opted out of the usual one-chat-per-document rule for this session). Produced `06_Orchestration_v2.md` and `07_Customization_Ref_v2.md`, intended to replace `06_Orchestration.md` and `07_Customization_Ref.md` in the project.
  - **Document 6 changes:** Part 2, Gate 3 description rewritten — now describes the Implementation Coordinator running Backend/Frontend/Test Writer subagents on a shared sandbox filesystem rather than three independent jobs. Part 4 Agent Failures gained a new entry ("The Implementation Coordinator session failed (Stage 3)") plus a clarifying note that the existing silent-failure entry applies to non-Stage-3 stages only. Part 4 Infrastructure Failures gained a new entry for Managed Agents beta-header/access issues. Reference → File Reference table updated to attribute `services/<service-name>/` to Backend/Frontend subagents via the coordinator. No other sections changed.
  - **Document 7 changes:** review surfaced more drift than the "minor clarification" flagged in the prior session note — several rows stated things that ADR-0010 had actually made incorrect, not just outdated. Pipeline & Orchestration section: agent invocation model row gained the ADR-0002/Stage-3 exception note. Agent Configuration section: agent roster row corrected from ten to eleven agents (added Implementation Coordinator); agent execution model row gained the Managed Agents exception for Stage 3; parallel execution row reworded around subagents/coordinator; **the "Integration check job... cannot be removed or bypassed" row was factually wrong post-ADR-0010 and was replaced** with an "Integration handling in Stage 3" row describing the coordinator's native integration handling; agent model tier row corrected from "Sonnet (all agents)" to the Opus-for-coordinator/Sonnet-elsewhere split. Quick-Reference Summary counts checked and left unchanged — no row moved between Locked/Flexible/Fully Open categories, so the approximate counts still hold.
  - Next: Document 4 (Governance) — add ADR-0010 to the seed ADR list — still the only document remaining from the original ADR-0010 priority list. Document 9 (README) also still outstanding (minor note on Stage 3).
- **2026-07-23 (chat 17 — this chat):** Document 9 (README) reviewed and updated for ADR-0010. Review surfaced three factual corrections, not just the "minor note" flagged in prior session notes. Produced `09-forge-readme_v2.md`, intended to replace `09-forge-readme.md` in the project.
  - **Changes applied:** Pipeline diagram Implementation-stage line rewritten from "backend + frontend + tests run in parallel" to "Implementation Coordinator runs Backend, Frontend, Test Writer subagents in parallel." Prerequisites section's Anthropic API line updated to note Managed Agents beta access (`managed-agents-2026-04-01` header) and the Opus-for-coordinator/Sonnet-elsewhere tier split (previously just said "Sonnet tier recommended"). Cost reference table gained a dedicated Managed Agents runtime row (~$0.08–0.32 USD, session-hour billing) and relabeled the Anthropic API row as token costs specifically. Repository layout's `core/agents/` line updated to note it includes the coordinator + subagent definitions. No other sections changed — Approving-a-gate table and reference documentation links were checked and found still accurate.
  - File is in `/mnt/user-data/outputs/` awaiting upload to the project — the user will upload it and remove the old `09-forge-readme.md`.
  - **Document 4 (Governance) is now the only document remaining from the original ADR-0010 update list** — outstanding since chat 12, deferred in favour of other documents three times.
- **2026-07-23 (chat 18 — this chat):** User asked whether Documents 0 and 1 needed ADR-0010 updates. Document 0 (Introduction) confirmed accurate as-is — its Implementation-stage line ("implements the backend, frontend, and tests in parallel") stays true at its level of abstraction and doesn't claim the old three-independent-jobs model. **Document 1 (Product Specification) was found to need a correction**, despite being marked "No" in the document list — Section 3.3 omitted the Implementation Coordinator entirely and incorrectly attributed the feature-branch commit and draft-PR-open action to the three subagents rather than the Coordinator. Produced `01-forge-product-specification_v2.md`, intended to replace `01-forge-product-specification.md` in the project.
  - **Change applied:** Section 3.3 rewritten — the Implementation Coordinator now explicitly orchestrates Backend/Frontend/Test Writer in parallel on a shared sandbox, synthesizes their output, and is the one that commits the implementation and opens the draft PR. No other sections changed.
  - File is in `/mnt/user-data/outputs/` awaiting upload to the project — the user will upload it and remove the old `01-forge-product-specification.md`.
  - **Document 4 (Governance) remains the only document from the original ADR-0010 priority list still outstanding** — now deferred four times in favour of other work.

---

## How to Use This Document

- **Starting a new chat:** Tell Claude "Continue the FORGE project — read the context doc first" and point to this file.
- **After each chat:** Ask Claude to append a session note with any new decisions made. Update version number.
- **If a decision changes:** Update the relevant section and note the change date inline.
