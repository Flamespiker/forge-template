# FORGE — Project Context & Decision Log

**Project:** FORGE — Full-SDLC Orchestration with Review Gates for Engineers  
**Owner:** Mike Faulkner (mfaulkner@legalaid.ab.ca) — Legal Aid Alberta  
**Last Updated:** 2026-07-29 (Document 9 refined post-Claude-Code review; Document 3 aligned on cost figure — chat 24)  
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
- **Agent runtime:** Anthropic Claude Managed Agents (Stage 3 coordinator/subagent pattern); base `anthropic` Python client / Messages API for all other stages (ADR-0011, chat 21 — supersedes the original Claude Agent SDK decision; Documents 2/3/9 correction still outstanding, see below)
- **Primary model:** Claude (Sonnet tier for non-Stage-3 stages; Opus tier for coordinator in Stage 3 — see ADR-0010)
- **Frontend:** React / Next.js — **TypeScript mandated (core layer)**
- **Backend:** .NET
- **Architecture pattern:** C4 model, microservices (small, manageable domains for mid-sized org)
- **Development methodology:** Spec-driven development
- **Containerization:** Docker, targeting **Azure Container Apps** (migration path from Azure App Service)
- **Current hosting:** Azure App Service (org), personal Azure account (build phase)
- **Anthropic API:** Mike's personal developer API account (build phase), org API account (production)
- **GitHub account (personal, build phase):** `Flamespiker` — owns both `forge-template` and `forge-demo-apps`
- **ADO org (build phase):** `spike99` (`https://dev.azure.com/spike99`) — **note:** this is a different identity than the GitHub account; the two got confused once during Phase 2 build (see chat 20 session note) and are worth keeping straight going forward

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
- Document 4 (Governance) — ADR-0010 added to seed ADR list (10th ADR) — **done** (completed chat "FORGE 04 Governance," 2026-07-23; see drift-correction note under chat 22 below — this was miscarried as "still outstanding" in every session note from chat 13 through chat 21)
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

### Managed Agents API — build-phase notes (confirmed Phase 2.9, 2026-07-25)

These are hands-on findings from the Phase 2.9 access check, worth building correctly into the Phase 3 Managed Agents API wrapper (step 3.1) rather than rediscovering them then:

- Beta header `managed-agents-2026-04-01` confirmed accepted on the personal developer API key used for build phase.
- Full lifecycle verified end-to-end: agent create → environment create → session create → send message via events endpoint → poll to idle → archive (session → agent → environment).
- Test model used: `claude-sonnet-4-6` (confirmed compatible with Managed Agents beta as of this date). This was only a connectivity test model choice — not necessarily the production model for the Stage 3 coordinator (ADR-0010 specifies Opus for the coordinator, Sonnet for subagents — apply that split when Phase 3 builds the real Implementation Coordinator).
- **Events endpoint body shape:** sending a message requires
  ```json
  {
    "events": [
      {"type": "user.message", "content": [{"type": "text", "text": "..."}]}
    ]
  }
  ```
  A flat `content` field at the top level is rejected with a 400 (`unknown field "content"`).
- **Archive race condition observed:** a session can flip briefly back to `running` immediately after reaching `idle` (e.g., trailing extended-thinking wrap-up), causing an archive call to fail with a 400 ("cannot be archived while its status is running") even though the poller had just seen it idle. Build a short retry-with-backoff around session archival in the real wrapper rather than treating this as a hard failure.
- Two throwaway local diagnostic scripts (`managed_agents_check.py`, `archive_retry.py`) were created for this check — gitignored, not committed to `forge-template`, not intended for reuse beyond this one verification.

### Base Anthropic client for non-Stage-3 invocation — ADR-0011

**Decision:** The six non-Stage-3 stages (Codebase Ingestion, Intake, Requirements, Design, QA, Security, Deploy) switch from the Claude Agent SDK to the base `anthropic` Python client, calling the Messages API directly. Stage 3 is unaffected (Managed Agents, ADR-0010, separate mechanism).

**Why:** Phase 3.1 live testing showed every Agent SDK invocation — even a trivial, tool-free text exchange — pays a fixed cost: ~25,700 tokens of Claude Code's bundled system prompt/tool definitions written to cache on a cold call (~$0.10 at $3.75/MTok cache-write rates), plus a subprocess-launch latency floor measured at ~10 seconds regardless of task size. None of the six stages ever use the SDK's autonomous tool-execution capability — FORGE's deterministic Python layer handles all file I/O; Claude only generates text from content already in the prompt. Confirmed empirically: every Phase 3.1 invocation across these stages already passed `allowed_tools=[]`.

**What changes:**
- `claude_agent_wrapper.py` calls the Messages API directly instead of the Agent SDK's `query()`
- `invoke_agent()` drops the `allowed_tools` parameter (no tool-use loop left to scope) and gains an explicit `max_tokens` parameter (the SDK managed this internally; the raw Messages API requires it)
- `total_cost_usd` is now computed via a maintained per-model rate table in the wrapper, rather than read directly from an SDK-provided `ResultMessage` — needs manual updates if Anthropic's pricing changes
- `requirements.txt`: `anthropic` becomes a direct dependency again; `claude-agent-sdk` is removed (Stage 3's Managed Agents wrapper never depended on it — confirmed, uses raw `requests` to the beta REST endpoints)

**What does not change:**
- `invoke_agent()`'s core signature and `AgentResult`'s shape are preserved as closely as possible — the stage-agent scripts calling it need no architectural changes, only the wrapper's internals changed
- Stage 3 / Managed Agents is entirely unaffected

**Status as of this chat's end: decided, code rewrite handed to Claude Code, NOT yet confirmed complete or re-tested.** Do not assume this is live until a real diff and a clean `smoke_claude_agent` re-run have been reviewed.

**ADR-0011 code rewrite — VERIFIED, chat 22.** Real `git diff` reviewed across `claude_agent_wrapper.py`, `requirements.txt`, `smoke_claude_agent.py`, and `CLAUDE.md`. Real smoke test output reviewed verbatim (5/5 passed: output_text, latency, token counts, total_cost_usd all real and positive; `total_cost_usd: 0.00021` on 30 input / 8 output tokens against Sonnet 4.6 — arithmetic confirmed: 30×$3.00 + 8×$15.00 = $0.00021, matches the response exactly). `_MODEL_RATES` table independently checked against Anthropic's live pricing page (2026-07-29) — Sonnet 4.6, Opus 4.6, and Haiku 4.5 rates all match published pricing exactly, nothing fabricated. Error-handling design confirmed honest: `invoke_agent()` has no try/except around `client.messages.create()`; `is_error=False` is a compile-time constant, not a runtime check; API failures propagate as exceptions. This is documented accurately in both the function docstring and CLAUDE.md — not glossed over.

**Affected documents requiring update — gate cleared, ready to action:**
- ~~Document 2 (Architecture) — agent invocation section currently states Claude Agent SDK for all non-Stage-3 stages~~ — **done**, produced `02-forge-architecture-document-v3.md` (see Document List; exact changes not re-summarized here — see the file's own diff from v2)
- ~~Document 3 (Tool Inventory) — §3.3 Claude Agent SDK row and cost summary~~ — **done**, produced `03_FORGE_Tooling_v6.md`, plus the flagged open item (Sonnet 5 introductory pricing as a future cost-optimization candidate) added. **Follow-up, chat 24:** the dollar estimate itself (~$1–5) had been left unrevised despite the invocation-mechanism fix — caught during the Document 9 refinement pass and corrected to ~$0.50–3 in `03_FORGE_Tooling_v7.md` (see chat 24 note below).
- ~~Document 9 (README) — Prerequisites and cost-reference sections reference the Agent SDK~~ — **done, chat 23 (this chat).** Actual review found the flagged assumption didn't hold: Document 9's Prerequisites bullet (`Anthropic API — an API key with Managed Agents beta access...`) never named the Claude Agent SDK, and the Cost reference table was already split by ADR-0010 mechanism (API tokens vs. Managed Agents runtime) rather than by invocation library — so neither section was actually factually wrong, unlike Docs 2 and 3, which did name the SDK explicitly and required real corrections. The one genuine gap: the reader-relevant *consequence* of ADR-0011 (elimination of the ~$0.10 cold-call cost + ~10s launch latency the Agent SDK's bundled CLI added per invocation) wasn't mentioned anywhere. Added a single footnote under the Cost reference table stating this, worded to match Document 3's ADR-0011 note. No other section changed. Also investigated whether the Prerequisites' "Node.js 20+ installed locally" line was Agent-SDK-driven (it would have been a genuine correction if so) — confirmed via Documents 2/3/6 that Node.js only appears in this document set in connection with `actions/create-github-app-token`'s own GitHub-hosted-runner requirement (not a local prerequisite) and with the target application's own TypeScript/Next.js stack — unrelated to the Agent SDK, so left unchanged. Produced `09-forge-readme_v4.md` (project file was already at v3 for reasons not reflected in this context doc's session log — treated v3 as the correct current baseline and incremented from there).
- FORGE Build Plan — step 3.1's SDK-wrapper line; Phase 8.3's "ten seed ADRs" count needs to become eleven, and a step should track ADR-0011's actual commit to `core/decisions/`; this would be v4 — **still outstanding, next in queue**
- ~~Document 6 (Orchestration Manager Guide) — added chat 22, not in the original ADR-0011 list.~~ Needs a new, explicit requirement: every stage-agent script from 3.2 onward MUST wrap `invoke_agent()` in try/except at the call site. — **done**, produced `06_Orchestration_v3.md`

**ADR-0011 full text:** see `ADR-0011.md`, generated chat 21, awaiting commit to `core/decisions/` in `forge-template` (an organic addition beyond the original ten-seed-ADR list from Phase 1 — the governance model supports ADRs being added over time, per Document 4's not-yet-written RFC process).

### Repository model — two repos, not one
- **Existing platform reality:** LAA's custom applications live in a single existing **monorepo** (all microservices, one repo). A separate, existing **Dynamics 365 repo** holds D365 development — out of scope for FORGE v1, flagged as a real future goal.
- **FORGE is a separate repo from the code it acts on.** FORGE's own template repo (workflows, agents, core/team config, the per-request tracking issue) never holds application source. It orchestrates *into* the custom-apps monorepo by opening branches/commits/PRs there.
- **Build/demo phase stand-in:** since there is no existing LAA monorepo available during the personal-account build phase, a new repo **`forge-demo-apps`** (private, under the `Flamespiker` GitHub account) was created in Phase 2 to play this role for App 1, App 2, and the enhancement demo. In a real team rollout, this would be the team's actual existing applications monorepo instead.
- **Cross-repo mechanics:** FORGE workflows authenticate into the monorepo via a **GitHub App installation** (scoped, revocable, attributable to "FORGE" rather than a personal token) with permissions limited to branch/commit/PR/comment/check-run operations. Triggering webhooks come from the monorepo; the tracking issue and orchestration state live in the FORGE repo.
- **Structural repo layout:**
  - FORGE repo: `.github/workflows/`, `core/` (agents, schemas — locked), `team/` (personas, config — customizable), `tracking/`
  - Monorepo: `services/<n>/` per microservice (new folder = greenfield, existing folder = enhancement), `docs/<request-id>/` for requirements.md/design.md/tasks.md
- **Branching (in the monorepo):** `main` (always deployable) ← `feature/<request-id>` ← `design/<request-id>`. FORGE's GitHub App creates/pushes these branches on the agents' behalf.
- **Traceability now crosses a repo boundary** (FORGE repo ↔ monorepo) partway through the chain. Full traceability depends on both sides writing the reciprocal link.

### Agent topology
- Ten agents total. All other than Stage 3 are stateless single-purpose calls invoked within GitHub Actions jobs, none persistent.
- **Stage 3 (Implementation):** One Managed Agents coordinator agent + three specialist subagents (Backend, Frontend, Test Writer). Coordinator runs subagents in parallel on a shared sandbox filesystem. Integration checking is native to the coordinator. (ADR-0010)
- All other stages: Codebase Ingestion, Intake, Requirements, Design, QA, Security, Deploy — stateless single-purpose calls via the base `anthropic` client / Messages API (ADR-0011, chat 21 — originally spec'd as Claude Agent SDK calls; changed after Phase 3.1 testing showed the SDK's CLI-subprocess overhead was unjustified since none of these stages use its autonomous tool-calling).

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
- Per-pipeline cost estimate: ~$0.50–3 USD for token costs (Sonnet tier, revised down from $1–5 per ADR-0011's SDK-overhead removal) + $0.08–0.32 for Managed Agents runtime (estimate 1–4 hours per implementation run). Track actuals during App 1.

### ADO field mapping (resolved)
- **FORGE writes automatically:** Title, Description, Acceptance Criteria (User Stories), Parent links, State (Active), Area Path (from team config default), Tags (`forge-managed`, `<request-id>`), traceability links
- **Left to the team:** Story Points, Priority, Iteration Path, Effort, Business Value, custom org fields

### Azure Container Apps environment specifics (resolved)
- Two separate environments: `forge-staging` and `forge-production`
- Staging: scale to zero, max 2 replicas, 0.25 vCPU / 0.5 Gi
- Production: min 1 replica, max 5, 0.5 vCPU / 1.0 Gi
- Rollback = redeploy prior image tag; previous revision retained 48h
- **Build-phase note:** in the current Azure portal, a Container Apps environment can only be created as a byproduct of creating an actual Container App (not as a standalone resource). Both `forge-staging` and `forge-production` were provisioned in Phase 2 using Azure's built-in "quickstart image" as a disposable placeholder app, then deleting just the placeholder app afterward while keeping the environment.

### GitHub App permission scoping (resolved)
- App named `forge-pipeline` (App ID `4388813`); installed on `forge-demo-apps` only, not org-wide
- Permissions: Contents (R/W), Pull requests (R/W), Issues (R/W), Checks (R/W), Metadata (R)
- Credentials stored as repo-level secrets: `FORGE_APP_ID` and `FORGE_APP_PRIVATE_KEY`; Client ID stored as repo-level **variable** `FORGE_APP_CLIENT_ID` (not a secret — Client ID is publicly visible on the App's settings page)
- Short-lived installation token generated per job via `actions/create-github-app-token@v3` (bumped from the deprecated Node-20-only `@v1` during Phase 2; `@v3` also renamed the `app-id` input to `client-id`)

### Cost summary (updated)
- Build phase incremental cost: Anthropic API tokens (~$0.50–3 USD per full pipeline run for token costs, revised down from $1–5 per ADR-0011's SDK-overhead removal, plus ~$0.08–0.32 for Managed Agents runtime — track actuals) + Azure Container Registry (~$0.17/day)
- No net-new SaaS contracts required with default tool choices
- ACR has no pause/deallocate option — only delete/recreate stops the daily charge. Accepted as a small ongoing build-phase cost rather than torn down between work sessions.

---

## Document List (in production order)

| # | Document | Status | Managed Agents Update Required |
|---|----------|--------|-------------------------------|
| 0 | FORGE Introduction | ✅ Complete | No |
| 1 | FORGE Product Specification | ✅ Complete — **updated (chat 18, `01-forge-product-specification_v2.md`)** | Yes — Section 3.3 Implementation Coordinator correction (originally mis-scoped as "No" — see chat 18) |
| 2 | FORGE Architecture Document | ✅ Complete — **updated (chat 12, `02-forge-architecture-document-v2.md`)** | Done |
| 3 | Tool & Licensing Inventory | ✅ Complete — **updated for ADR-0011 cost-estimate alignment (chat 24, `03_FORGE_Tooling_v7.md`)** | Done (Managed Agents, chat 14); Done (ADR-0011, chat 24) |
| 4 | FORGE Governance Model | ✅ Complete — **needs update** | Yes — ADR-0010 added to seed ADR list |
| 5 | AI Foundations Guide | ✅ Complete — **updated (chat 15, `05_AI_Foundation_v2.md`)** | Done |
| 6 | Orchestration Manager Guide | ✅ Complete — **updated (chat 16, `06_Orchestration_v2.md`)** | Done |
| 7 | Customization Reference | ✅ Complete — **updated (chat 16, `07_Customization_Ref_v2.md`)** | Done |
| 8 | Excel Intake Template | ✅ Complete | No |
| 9 | FORGE README | ✅ Complete — **refined post-Claude-Code review (chat 24, `09-forge-readme_v5.md`)** | Done (ADR-0010, chat 17); Done (ADR-0011, chat 23–24) |
| — | FORGE Build Plan | ✅ Complete — **updated (chat 13, `FORGE_Build_Plan_v2.md`)** | Done |

**Update priority order for new chats:**
1. ~~Document 2 (Architecture) — highest priority, other docs reference it~~ — done, chat 12
2. ~~Document 4 (Governance) — seed ADR list needs ADR-0010~~ — **done** (see chat 22 drift-correction note; incorrectly tracked as outstanding for six sessions)
3. ~~Build Plan — build sequence changes before Phase 3~~ — done, chat 13
4. ~~Document 3 (Tool Inventory) — billing update~~ — done, chat 14
5. ~~Document 5 (AI Foundations) — training materials + orchestration concepts~~ — done, chat 15
6. ~~Document 6 (Orchestration Manager Guide) — failure handling~~ — done, chat 16
7. ~~Document 7 (Customization Reference) — Agent Configuration + Pipeline & Orchestration sections~~ — done, chat 16 (turned out to be more than "minor" — see session note)
8. ~~Document 9 (README) — minor update~~ — done, chat 17 (ADR-0010); done again, chat 23 (ADR-0011)
9. ~~Document 4 (Governance) — ADR-0010 seed ADR list~~ — **done**, not actually outstanding (see chat 22 drift-correction note)

**ADR-0011 update queue (post chat-22 code verification):** ~~Document 2~~ → ~~Document 3 (v6)~~ → ~~Document 9 (v4)~~ → **Build Plan (v4) — next** → ~~Document 6 (try/except requirement)~~

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
- **Managed Agents archive race condition** (see build-phase notes under ADR-0010 above) — build retry-with-backoff into the Phase 3 wrapper (step 3.1) rather than treating a transient archive failure as a hard error

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
| GitHub Actions cross-repo auth with GitHub Apps | Before Phase 2 | `actions/create-github-app-token` pattern — ✅ used in Phase 2, note the `@v3`/`client-id` update above |
| Azure Container Apps quickstart (Microsoft Learn) | Before Phase 2 | Infrastructure provisioning — ✅ done in Phase 2 |
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
- **2026-07-22 (chat 11):** Pre-build architectural review. Two decisions made:
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
- **2026-07-23 (chat 17):** Document 9 (README) reviewed and updated for ADR-0010. Review surfaced three factual corrections, not just the "minor note" flagged in prior session notes. Produced `09-forge-readme_v2.md`, intended to replace `09-forge-readme.md` in the project.
  - **Changes applied:** Pipeline diagram Implementation-stage line rewritten from "backend + frontend + tests run in parallel" to "Implementation Coordinator runs Backend, Frontend, Test Writer subagents in parallel." Prerequisites section's Anthropic API line updated to note Managed Agents beta access (`managed-agents-2026-04-01` header) and the Opus-for-coordinator/Sonnet-elsewhere tier split (previously just said "Sonnet tier recommended"). Cost reference table gained a dedicated Managed Agents runtime row (~$0.08–0.32 USD, session-hour billing) and relabeled the Anthropic API row as token costs specifically. Repository layout's `core/agents/` line updated to note it includes the coordinator + subagent definitions. No other sections changed — Approving-a-gate table and reference documentation links were checked and found still accurate.
  - File is in `/mnt/user-data/outputs/` awaiting upload to the project — the user will upload it and remove the old `09-forge-readme.md`.
  - **Document 4 (Governance) is now the only document remaining from the original ADR-0010 update list** — outstanding since chat 12, deferred in favour of other documents three times.
- **2026-07-23 (chat 18):** User asked whether Documents 0 and 1 needed ADR-0010 updates. Document 0 (Introduction) confirmed accurate as-is — its Implementation-stage line ("implements the backend, frontend, and tests in parallel") stays true at its level of abstraction and doesn't claim the old three-independent-jobs model. **Document 1 (Product Specification) was found to need a correction**, despite being marked "No" in the document list — Section 3.3 omitted the Implementation Coordinator entirely and incorrectly attributed the feature-branch commit and draft-PR-open action to the three subagents rather than the Coordinator. Produced `01-forge-product-specification_v2.md`, intended to replace `01-forge-product-specification.md` in the project.
  - **Change applied:** Section 3.3 rewritten — the Implementation Coordinator now explicitly orchestrates Backend/Frontend/Test Writer in parallel on a shared sandbox, synthesizes their output, and is the one that commits the implementation and opens the draft PR. No other sections changed.
  - File is in `/mnt/user-data/outputs/` awaiting upload to the project — the user will upload it and remove the old `01-forge-product-specification.md`.
  - **Document 4 (Governance) remains the only document from the original ADR-0010 priority list still outstanding** — now deferred four times in favour of other work.
- **2026-07-23 (chat 19):** Phase 1 build complete. `forge-template` GitHub repository created (template flag enabled, public). All 10 Phase 1 steps completed and pushed.
  - **Steps completed:** 1.1 repo created on GitHub; 1.2 full folder structure with `.gitkeep` files; 1.3 `team/config.yaml` with Container Apps values from architecture decisions; 1.4 `team/stack-preferences.yaml` with core-layer mandates vs team-layer placeholders clearly distinguished; 1.5 GitHub issue form template (`forge-request.yml`) with all pipeline stage checkboxes; 1.6 `.gitignore` (Python + Node + .NET + FORGE-specific) and `.gitattributes` (LF line endings enforced); 1.7 README.md populated from Document 9; 1.8 10 seed ADR stubs in `core/decisions/`; 1.9 7 GitHub Actions workflow stubs in `.github/workflows/`; 1.10 repo verified clean on GitHub.
  - **Additional:** `/docs` folder added to the repo containing all FORGE documents (all v2 files). Duplicate of Document 9 removed from `/docs` after being promoted to `README.md`.
  - **Two-machine workflow established:** Code stays in local folders on each machine (not OneDrive). Git push/pull via GitHub is the sync mechanism between machines.
  - **Build session structure agreed:** Roughly one phase per chat thread. Start a new chat at phase boundaries or when context feels stale. Paste the phase and last completed step at the start of each new build chat.
  - **Learning approach:** Just-in-time — concepts introduced immediately before the phase that needs them. Claude Code CLI handles file writing; this chat handles strategy, explanation, and review.
  - **Document 4 (Governance) — ADR-0010** is the only outstanding document update. Handle in a dedicated doc-update chat before or during Phase 2 — not blocking Phase 2 infrastructure work but should be done before Phase 3.
  - Next: Phase 2 — Infrastructure Setup. Start a fresh chat.
- **2026-07-25 (chat 20 — this chat):** Phase 2 (Infrastructure Setup) complete — all nine steps (2.1–2.9) verified working end-to-end.
  - **2.1 GitHub App:** Created `forge-pipeline` (App ID `4388813`), installed on `forge-demo-apps` only (not org-wide). Permissions: Contents R/W, Pull requests R/W, Issues R/W, Checks R/W, Metadata R. Credentials stored as `FORGE_APP_ID`, `FORGE_APP_PRIVATE_KEY` secrets, and `FORGE_APP_CLIENT_ID` as a repo **variable** in `forge-template` (Client ID needed because the current `create-github-app-token@v3` action deprecates the old `app-id` input in favour of `client-id`).
  - **New repo created:** `forge-demo-apps` (private, under personal GitHub account **`Flamespiker`**) — stands in for LAA's real application monorepo during the build/demo phase, since no such repo exists yet in this personal-account context. This is the repo FORGE actually builds into; distinct from `forge-template`, which holds only FORGE's own orchestration machinery.
  - **2.2 Azure Container Registry:** Created (Basic tier), admin-user credentials stored as `ACR_LOGIN_SERVER`, `ACR_USERNAME`, `ACR_PASSWORD` secrets. Confirmed ACR has no pause/deallocate option — only delete/recreate stops the daily charge — accepted as a small ongoing build-phase cost rather than torn down between sessions.
  - **2.3 / 2.4 Container Apps environments:** `forge-staging` and `forge-production` environments created (Consumption plan). Portal note: environments can currently only be created as a byproduct of creating a Container App — used Azure's "quickstart image" placeholder trick to provision each environment, then deleted the placeholder container app afterward, keeping the environment itself.
  - **2.5 GitHub Environments:** `staging` (no required reviewers, auto-deploy) and `production` (required reviewer: Mike) configured in `forge-template`.
  - **2.6 ADO connection:** New ADO project **`FORGE-Build`** created under org **`https://dev.azure.com/spike99`** (Agile process) to act as the one tracking project for all build-phase apps (App 1, App 2, enhancement all show up as separate Epics inside it, mirroring the `services/<n>/` folder split in the monorepo). PAT generated (scoped to `spike99` only, not all orgs), verified via a real test Epic created through the ADO REST API and then deleted, stored as `ADO_PAT` secret.
  - **2.7 Anthropic API key:** Personal developer key confirmed active, stored as `ANTHROPIC_API_KEY` secret.
  - **2.8 End-to-end connectivity check:** Built `.github/workflows/verify-setup.yml` (permanent — reused in Phase 8.4 to verify a fresh clone), verifying GitHub App token generation + repo access, ADO connectivity, and Anthropic API access in one workflow. Notable debugging along the way, worth remembering for Phase 3: `actions/create-github-app-token` needed bumping from the deprecated `@v1` (Node 20, being forced onto Node 24 with warnings) to `@v3` (Node 24-native, and renames `app-id` to `client-id`); several secrets/variables assumed stored earlier in the session (`FORGE_APP_ID`, `FORGE_APP_PRIVATE_KEY`, `FORGE_APP_CLIENT_ID`) turned out not to have actually been saved and had to be added properly on a second pass; and a copy-paste mix-up briefly had a verification step's GitHub API call pointed at the ADO org name (`spike99`) instead of the actual GitHub owner (`Flamespiker`) — two similarly-shaped "org" identifiers that are easy to cross. All resolved; workflow now passes cleanly with three green checks.
  - **2.9 Managed Agents access check:** Verified via two throwaway local scripts (`managed_agents_check.py`, `archive_retry.py` — gitignored, not committed). Full lifecycle confirmed: beta header accepted, agent/environment/session creation, message send, idle state reached, and cleanup archival all worked (with one transient archive-timing hiccup, resolved by retry — see "Managed Agents API — build-phase notes" under ADR-0010 above for the exact schema/behavior details to carry into Phase 3).
  - **Process lesson for future phases:** several credential-storage steps this session were verbally confirmed "done" but had not actually been saved in GitHub's UI, causing repeated debugging loops before the real problem (a missing secret/variable) was found. Worth explicitly confirming (screenshot or listing) that secrets/variables actually appear in GitHub's UI before moving to the next step, rather than treating a verbal "done" as sufficient for credential-storage steps specifically.
  - **Formatting preference established:** anything meant to be handed to Claude Code, and all git commands, should be given in fenced code blocks so the copy button is available — apply this from now on in all future chats, not just this one.
  - **Document 4 (Governance) — ADR-0010 seed ADR list is still the only outstanding document update**, now deferred five times (four document-update chats, plus the entire Phase 2 build) in favour of other work. Per the chat 19 note, this should land before Phase 3 begins.
  - Next: Phase 3 — Agent Implementation. Start a fresh chat.
- **2026-07-29 (chat 21 — this chat):** Phase 3.1 (Shared Agent Utilities) fully complete — all five modules built, reviewed, and **verified against real services with real evidence**, not just code review. User explicitly chose to proceed with Phase 3 this session rather than land Document 4 first — that item is now deferred six times (see below).
  - **`file_io.py`** — 7/7 passed. Three real bugs found and fixed during review, all confirmed against the actual `Intake_Template.xlsx` (not assumed): (1) Requirements-sheet header search was scanning every cell for the substring "req" instead of exact-matching column A — fixed to `row[0].strip().lower() == "req #"`; (2) an `_is_example_row()` heuristic meant to skip the four pre-populated example rows was flagged for removal but initially left in place on the first fix attempt — genuinely removed on the second pass, confirmed by re-running against the real file; (3) Overview-section detection used exact match against bare section names ("Request Identification") when the real cells have letter prefixes ("A — Request Identification") — fixed via substring matching, then further improved to return canonical snake_case dict keys (`request_identification`, etc.) with nested `{field_label: field_value}` dicts per section, rather than the raw spreadsheet text or a flat interleaved list. A separate portability bug (wrong `Path.parents[]` index, overshooting the repo root by one level) was also found and fixed, confirmed genuinely portable (anchored to `__file__` depth, not any absolute path).
  - **`claude_agent_wrapper.py`** — 5/5 passed, then superseded by ADR-0011 (see below). Initial build mistakenly used the base `anthropic` package instead of the real Claude Agent SDK; corrected to the actual `claude-agent-sdk` PyPI package (verified real via direct PyPI fetch — v0.2.128 confirmed current) after Claude Code initially disputed the package's existence. Cost investigation after an anomalous $0.09652-for-3-tokens smoke test result correctly diagnosed the cause as Claude Code CLI system-prompt/tool-definition cache creation (~25,700 tokens on a cold call) rather than a per-invocation minimum charge — this diagnosis directly led to ADR-0011.
  - **`ado_helper.py`** — 4/4 passed. Real bug found via live API testing: Document 3 §5 specified `"Active" on creation` for all four work item types (Epic, Feature, User Story, Bug); the live ADO API only permits creation in `"New"` — `"Active"` is transition-only for all four types, confirmed via `/wit/workitemtypes/{type}/states`. Fixed by dropping `System.State` from all four `_make_patch` calls (defaults to `"New"`). **Document 3 corrected same-session (v5)** — the four State rows changed from `"Active" on creation` to `"New" on creation`, with an explanatory note.
  - **`github_helper.py`** — 7/7 passed. Real architecture bug found: `post_comment`/`add_label`/`remove_label` were targeting `FORGE_TARGET_REPO` (the monorepo, `forge-demo-apps`) when the tracking issue actually lives in `FORGE_SOURCE_REPO` (`forge-template`) — would have silently posted tracking-issue updates to the wrong repo in production. Fixed: those three functions now use a local-dev-only `GITHUB_TOKEN` (explicitly documented in code as a stand-in for the ambient token GitHub Actions injects automatically for same-repo ops — must NOT be added as a real Actions secret in Phase 4) targeting `FORGE_SOURCE_REPO`, while `create_branch`/`commit_files`/`open_pr` correctly stay on the GitHub App's installation token targeting `FORGE_TARGET_REPO`. Also: `commit_files()` was missing entirely from the original build (needed by 3.4 and 3.4a, not just this smoke test) — added, verified via a real signed commit (`forge-pipeline[bot]`, `verified: true`) into `forge-demo-apps`.
  - **`managed_agents_wrapper.py`** — 6/6 passed on the second attempt. **Real, substantial Managed Agents API schema change discovered and confirmed against Anthropic's official docs** (`platform.claude.com/docs/en/managed-agents/*`, `github.com/anthropics/skills`, `claude-cookbooks/managed_agents`): the `"subagents"` field assumed since Phase 2.9 no longer exists (if it ever did — Phase 2.9's own verification was explicitly a zero-subagent test, so this may never have been validated rather than having regressed). Current schema: subagents must be created as independent, standalone agent resources first, then a coordinator agent references them by ID via `multiagent: {"type": "coordinator", "agents": [...]}`; environments and sessions are top-level resources (`POST /v1/environments`, `POST /v1/sessions`); errors surface as `session.error` events in the stream, not as a status value (`terminated` is a rare, unrecoverable orchestration-layer state, not the general error signal); per-subagent audit trail comes from `client.beta.sessions.threads.list(session_id)` (coordinator = primary thread, `parent_thread_id: null`; each subagent = its own thread). First smoke test attempt passed 5/5 but was **coordinator-only** (`subagent_configs=[]`) — did not actually exercise the multi-agent path; re-run with a real declared specialist agent confirmed genuine coordinator→subagent delegation, correct thread structure, per-subagent event retrieval, and full four-resource archive (coordinator + specialist agents + environment + session).
  - **ADR-0011 decided:** the Agent SDK cost/latency investigation above surfaced a broader question — none of the six non-Stage-3 stages use the Agent SDK's autonomous tool-calling, yet every invocation pays its full CLI-subprocess overhead. Decision: switch those six stages to the base `anthropic` client (Messages API), full rationale in the ADR-0011 subsection above. **Code rewrite handed to Claude Code this session but not yet confirmed complete or re-tested** — treat as decided-but-unverified until a real diff and clean smoke test re-run are reviewed in the next chat.
  - **Process pattern that kept paying off:** insisting on real executed output (diffs, actual API responses, re-run smoke tests) rather than accepting summaries caught real problems repeatedly this session — the file_io fixes, the github_helper repo-targeting bug, the ADO state assumption, and the Managed Agents coordinator-only false-pass would all likely have shipped unnoticed under a "trust the summary" approach.
  - **Document 3 updated twice this session** (v4: added §3.7 Context7 dev-tooling note, not part of FORGE's runtime tool inventory; v5: corrected the four State-on-creation rows per the ADO finding above) — v5 is the current authoritative version in the project. A third update (v6) is still needed once ADR-0011's code change is verified (see ADR-0011 subsection above).
  - **New memory edit added:** for FORGE project work, don't use organizational skills (`laa-brand`, `laa-security-review`, `freshservice-kb-article`) unless explicitly asked.
  - **Document 4 (Governance) — ADR-0010 seed ADR list remains the only outstanding *document-list* item**, now deferred six times. **New outstanding item this chat:** Documents 2, 3, and 9 need correction for ADR-0011 once its code is verified — do not action until then.
  - Next: continue Phase 3 at step 3.2 (Intake Agent) — but **first**, confirm ADR-0011's `claude_agent_wrapper.py` rewrite is genuinely complete and re-tested (real diff, real smoke test output), since 3.2 will call `invoke_agent()` and the interface changed (`allowed_tools` removed, `max_tokens` added). Starting 3.2 against an unverified wrapper interface risks building against a signature that isn't final.
  - **[Correction added chat 22 — see below]:** the "Document 4 still outstanding" claim above, and every prior instance of it back through chat 13, was stale. Document 4 was actually completed on 2026-07-23 in a session titled "FORGE 04 Governance," which produced the ADR-0010 addition and bumped that session's context doc to a v13. A **different** same-day session ("Build Plan") branched off the same earlier context version independently and became the lineage that actually continued forward into v14 → v21 — so every context doc from that point on inherited "still outstanding" from the branch that never saw the fix, even though the real, completed `04_Governance-v2.md` was uploaded to the project and has been sitting there correctly the whole time. Content was never wrong; only this document's own session log was. Confirmed by direct inspection of `04_Governance-v2.md` (ADR-0010 is present in the Seeded ADRs table) and by conversation search of the "FORGE 04 Governance" session.
- **2026-07-29 (chat 22 — this chat):** Session opened with the standard "review everything, read context first" request. Reviewed all nine project documents, `CLAUDE.md`, `requirements.txt`, and `ADR-0011.md` before making any changes, per standing process.
  - **Document 4 drift found and corrected** — see note above. No content changes needed to `04_Governance-v2.md` itself; only this context document's session-log claims were corrected (this entry, the Governance bullet under Key Decisions, and both Document List entries).
  - **ADR-0011 code status checked and confirmed still pending** — inspected `requirements.txt` (still pins `claude-agent-sdk`, does not list `anthropic`) and `CLAUDE.md` (still fully describes the pre-ADR-0011 `claude_agent_sdk` / `query()` architecture with no mention of ADR-0011). Neither file shows any trace of the rewrite landing. User confirmed verbally: still pending.
  - **Decision:** since the ADR-0011 code gate is still closed, Documents 2, 3, and 9 remain untouched this chat — updating them now would describe code that doesn't exist in the repo yet. User chose to send the ADR-0011 rewrite back to Claude Code now, rather than draft provisional doc language.
  - **Claude Code brief for the rewrite handed to the user this chat** (not yet run): rewrite `claude_agent_wrapper.py` to call the base `anthropic` Messages API directly per ADR-0011 (drop `allowed_tools`, add `max_tokens`, build a maintained per-model cost-rate table instead of reading `total_cost_usd` from an SDK `ResultMessage`); update `requirements.txt` (`anthropic` back in as a direct dependency, `claude-agent-sdk` removed); update `CLAUDE.md`'s stale Agent SDK section to match; re-run `smoke_claude_agent` for a real pass/fail with real output; produce a real diff. See the chat 22 transcript for the exact brief given.
  - **Build Plan reviewed for accuracy while user ran Claude Code.** Confirmed accurate throughout for ADR-0010 (Phases 3.1, 3.4a, 3.5–3.7, 4.4, 4.8, 4.9/4.10, 5.6, 5.10 all consistent). **Found it was missed from the ADR-0011 affected-documents list** — step 3.1's SDK-wrapper line is stale, and Phase 8.3's "ten seed ADRs" count doesn't account for ADR-0011, which also has no checklist step tracking its commit to `core/decisions/`. Added to the outstanding list above (would become Build Plan v4). Not edited this chat — same code-verification gate applies.
  - **ADR-0011 code verified this chat** — real diff, real smoke test output, independently-checked pricing table, and an honest error-handling design all reviewed and confirmed. See the verification note above. The gate is clear.
  - Next: per standing process (one document per chat thread), the ADR-0011 corrections should each get their own fresh chat, pasting in this context doc. Suggested order, following the existing priority convention (Document 2 first since other docs reference it): **Document 2 → Document 3 (v6) → Document 9 → Build Plan (v4) → Document 6 (new try/except requirement)**. Once those land, Phase 3 can continue at step 3.2 (Intake Agent) against a confirmed-final `invoke_agent()` signature.
- **2026-07-29 (chat 23 — this chat):** Document 9 (README) reviewed and updated for ADR-0011, per queue order. (Documents 2, 3, and 6 were evidently completed in intervening chats not individually logged here — found already at v3, v6, and v3 respectively in the project at the start of this chat; content spot-checked and consistent with the ADR-0011 gate-cleared plan from chat 22, so treated as done rather than re-litigated. This context doc's own session log had fallen a step behind the actual project state — same category of drift as the chat-22 Document-4 correction, just less consequential since no incorrect "still outstanding" claim was actively being repeated.)
  - **Genuine finding:** the chat-22 assumption that Document 9's "Prerequisites and cost-reference sections reference the Agent SDK" did not hold up — neither section actually named the Claude Agent SDK, so there was no factual error to correct there (unlike Documents 2 and 3, which did). Also checked whether the Prerequisites' "Node.js 20+ installed locally" line was Agent-SDK-driven — confirmed it isn't (Node.js appears elsewhere in the doc set only in connection with `create-github-app-token`'s GitHub-hosted-runner requirement and the target app's own TypeScript/Next.js stack) — left unchanged.
  - **Actual change applied:** one footnote added under the Cost reference table noting ADR-0011's consequence for readers — elimination of the ~$0.10 cold-call cost and ~10-second launch latency the Agent SDK's bundled CLI added per invocation on the six non-Stage-3 stages — worded to match Document 3's ADR-0011 note. No other section changed.
  - Produced `09-forge-readme_v4.md` (project file was already at v3, for reasons not reflected in this context doc — incremented from that actual baseline rather than the v2 the session log implied).
  - File is in `/mnt/user-data/outputs/` awaiting upload to the project — the user will upload it and remove the old `09-forge-readme_v3.md`.
  - **ADR-0011 update queue: only the Build Plan (v4) remains** — step 3.1's SDK-wrapper line, Phase 8.3's "ten seed ADRs" → eleven, and a new checklist step tracking ADR-0011's commit to `core/decisions/`.
  - Next: Build Plan (v4) in a fresh chat. Once that lands, Phase 3 can continue at step 3.2 (Intake Agent) against the confirmed-final `invoke_agent()` signature.
- **2026-07-29 (chat 24 — this chat):** User ran the chat-23 draft of Document 9 (`09-forge-readme_v4.md`) past Claude Code, which suggested two further refinements beyond what this chat had caught:
  1. **Prerequisites / Anthropic API bullet rewritten** — the prior wording ("an API key with Managed Agents beta access... for Stage 3") could read as if beta access were a blanket requirement. Reworded to state plainly that a standard key covers Intake, Requirements, Design, QA, Security, and Deploy, and that Managed Agents beta access is an *additional* requirement specific to Stage 3. Accepted without reservation — genuine clarity improvement, no downstream conflict.
  2. **Cost reference token-cost estimate revised from ~$1–5 USD to ~$0.50–3 USD**, reasoning that the lower floor reflects removal of the Agent SDK's ~$0.10 cold-call overhead per invocation across the six non-Stage-3 stages (ADR-0011). Also relabeled the Managed Agents cost row "(Stage 3 only)" for clarity.
  - **Caught before applying:** this second change would have put Document 9 out of sync with Document 3 v6, which still stated ~$1–5 for the same figure (Document 3's own ADR-0011 pass, done in an intervening untracked chat, updated the invocation-mechanism rows but never revisited the dollar estimate). Flagged this to the user rather than applying Document 9's number in isolation.
  - **User decision: align both documents on ~$0.50–3 now.** Updated Document 3 (`03_FORGE_Tooling_v6.md` → `03_FORGE_Tooling_v7.md`): the Cost Summary table row and the §3.3 cost-estimation note both revised to ~$0.50–3 USD, with an inline note explaining the figure was revised down from $1–5 to reflect ADR-0011's overhead removal. Also swept this context document itself for the same stale figure — both instances under "Anthropic API billing" and "Cost summary" (Key Decisions section) updated to match, since this document is meant to be the authoritative living reference and would otherwise itself be a third inconsistent source.
  - **Produced `09-forge-readme_v5.md`** (supersedes the chat-23 `09-forge-readme_v4.md` — that file should NOT be uploaded; use v5) and **`03_FORGE_Tooling_v7.md`**. Both are in `/mnt/user-data/outputs/`.
  - **Note for future sessions:** this is the second time in two chats that a "gate cleared, done" document turned out to need a follow-up pass (Document 3 here; the Document-9-assumption-didn't-hold finding in chat 23). Worth treating "done" status on ADR-0011 documents as provisional until Phase 3 actually exercises `invoke_agent()` against real stage scripts — a live run may well surface further drift the same way Phase 3.1 did originally.
  - **ADR-0011 update queue: only the Build Plan (v4) remains outstanding** (step 3.1's SDK-wrapper line, "ten seed ADRs" → eleven, new checklist step for ADR-0011's commit to `core/decisions/`). Document 3 is now fully current at v7 — no further ADR-0011 work expected there barring new findings.
  - Next: Build Plan (v4) in a fresh chat, pasting in this context doc.

---

## How to Use This Document

- **Starting a new chat:** Tell Claude "Continue the FORGE project — read the context doc first" and point to this file.
- **After each chat:** Ask Claude to append a session note with any new decisions made. Update version number.
- **If a decision changes:** Update the relevant section and note the change date inline.
