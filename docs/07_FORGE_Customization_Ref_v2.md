# FORGE Customization Reference

**Document:** 07 — Customization Reference  
**Project:** FORGE — Full-SDLC Orchestration with Review Gates for Engineers  
**Audience:** Orchestration Managers  
**Purpose:** Single-source-of-truth table showing every FORGE configuration item and whether it is locked, team-configurable within constraints, or fully open to team discretion.

---

## How to Read This Document

| Category | Meaning | Who Decides | Where It Lives |
|----------|---------|-------------|----------------|
| **Locked** | Fixed by the core platform. Changing this requires an RFC and Core Platform Owner approval. | Core Platform Owner | `core/` (read-only to Orchestration Managers) |
| **Flexible** | Team-configurable, but within defined boundaries. The *what* is fixed; the *value* is yours. | Orchestration Manager | `team/config.yaml` or `team/stack-preferences.yaml` |
| **Fully Open** | No constraints. Team decides without any platform guidance or approval. | Orchestration Manager / Team | Wherever the team documents it |

If a row has a note, read it — the note defines the boundary exactly.

---

## Pipeline & Orchestration

| Item | Category | Notes |
|------|----------|-------|
| Orchestration engine (GitHub Actions) | **Locked** | No alternative orchestrators permitted. |
| State storage mechanism (native GitHub: labels, PR review state, Environments) | **Locked** | No bespoke state database or external state service. |
| Agent invocation model (stateless per-stage Claude Agent SDK calls) | **Locked** | Agents do not persist memory across stages. Context passes forward as committed files only. Exception: Stage 3 uses a Managed Agents coordinator session (see ADR-0010) — the coordinator maintains state across its subagents *within* the stage window, which clarifies rather than violates this rule. All other stages are unaffected. |
| Pipeline stage sequence and names | **Locked** | Stages 0a–6 execute in order. No stages may be reordered, skipped (except Stage 0a, which is only triggered for enhancements), or merged. |
| Human gate at every stage | **Locked** | Every stage transition requires a human approval action. Gates cannot be bypassed or automated away. |
| No-self-merge rule (agents open PRs; humans merge) | **Locked** | An agent may never merge its own PR. Enforced by branch protection. |
| Guard clause on every workflow (precondition label check) | **Locked** | Prevents stray events from re-triggering a stage out of order. |
| Codebase Ingestion stage trigger (enhancement-only) | **Locked** | Triggered automatically when the request is flagged as an enhancement. Cannot be manually triggered for greenfield requests. |
| "Clarification complete" signal mechanism (label `clarification-complete`) | **Locked** | The BA applies this label — not a keyword reply. Label-event triggers the Requirements stage. BA removes and re-applies for a second clarification round. |
| Intake upload mechanism (issue attachment vs. repo path) | **Flexible** | Team choice, documented in the Orchestration Manager Guide and team config. Issue attachment is the recommended default for the build phase. |
| Number of clarification rounds (maximum 2) | **Locked** | One initial round plus one follow-up if needed. The agent does not loop beyond this. |
| Clarifying questions per round (5–7 maximum) | **Locked** | The Intake Agent's prompt is scoped to this limit at the core layer. |

---

## Repository Structure

| Item | Category | Notes |
|------|----------|-------|
| Two-repo model (FORGE repo separate from target monorepo) | **Locked** | FORGE never holds application source. It orchestrates into the target monorepo. |
| FORGE repo layout (`core/`, `team/`, `tracking/`, `.github/workflows/`) | **Locked** | Top-level directory structure is fixed. `core/` is read-only to Orchestration Managers. |
| Target monorepo layout (`services/<name>/`, `docs/<request-id>/`) | **Locked** | Agents write to these paths. Changing the path convention breaks agent assumptions. |
| Branching strategy in the monorepo (`main` ← `feature/<request-id>` ← `design/<request-id>`) | **Locked** | Branch naming and hierarchy are fixed. |
| ADR storage location (`core/decisions/`) | **Locked** | All ADRs committed here. Path is referenced by the governance process. |
| Team configuration files location (`team/config.yaml`, `team/stack-preferences.yaml`) | **Locked** (path) / **Flexible** (contents) | Files must exist at these paths. Contents are team-configurable within the schema. |
| Cross-repo traceability links (FORGE tracking issue ↔ monorepo PR) | **Locked** | Both sides must write reciprocal links. Agents write these automatically; Orchestration Managers must not remove them. |

---

## GitHub App & Authentication

| Item | Category | Notes |
|------|----------|-------|
| GitHub App name (`forge-pipeline`) | **Flexible** | Can be renamed per team install. The name is cosmetic; the permission set is what matters. |
| GitHub App installation scope (monorepo only, not org-wide) | **Locked** | App is never installed org-wide. Scoped to the target monorepo. |
| GitHub App permissions (Contents R/W, Pull requests R/W, Issues R/W, Checks R/W, Metadata R) | **Locked** | Minimum required set. No additional permissions granted without an RFC. |
| Credential storage (`FORGE_APP_ID`, `FORGE_APP_PRIVATE_KEY` as repo-level secrets in FORGE repo) | **Locked** | Secret names are referenced by core workflows. Renaming them breaks the pipeline. |
| Token generation mechanism (`actions/create-github-app-token`, short-lived per job) | **Locked** | No long-lived tokens. Token expires after 1 hour. |

---

## Azure DevOps Integration

| Item | Category | Notes |
|------|----------|-------|
| ADO work item hierarchy (Epic → Feature → User Story) | **Locked** | FORGE creates exactly this three-level structure. No alternative hierarchies. |
| When ADO items are created (on `requirements-approved` only) | **Locked** | No speculative ADO item creation at any earlier stage. |
| Fields FORGE writes automatically (Title, Description, Acceptance Criteria, State=Active, Tags `forge-managed`+`<request-id>`, traceability links) | **Locked** | These fields are always written. Agents cannot be configured to skip them. The specific content of Description and Acceptance Criteria is agent-generated per request. |
| Fields left to the team (Story Points, Priority, Iteration Path, Effort, Business Value, custom org fields) | **Fully Open** | FORGE does not write or validate these. Team manages them in ADO directly. |
| Default Area Path | **Flexible** | Set in `team/config.yaml`. FORGE uses this value when creating ADO items. |
| Bug severity mapping (assertion failure = Medium, crash/exception = High) | **Locked** | Fixed mapping in the QA Agent prompt. Changing severity categories requires an RFC. |
| Bug fields FORGE writes (Title, Description, Steps to Reproduce, Severity, Parent User Story link, PR URL, tags) | **Locked** | Same rule as User Story fields above — always written, cannot be skipped. |
| ADO authentication method (PAT acceptable for build phase; service principal recommended for production) | **Flexible** | Orchestration Manager chooses. PAT credentials stored as secrets in the FORGE repo. |

---

## Security Tooling

| Item | Category | Notes |
|------|----------|-------|
| Security gate presence (a security stage exists and must be passed) | **Locked** | The Security stage cannot be removed from the pipeline. |
| Critical finding blocks merge | **Locked** | A Critical severity finding from any security tool sets a failing check run, blocking merge automatically. Enforced by branch protection, not agent judgment. |
| Default SAST tool (Semgrep Community) | **Flexible** | Default is Semgrep Community. Teams may substitute GitHub Advanced Security (CodeQL) or another SAST tool, documented in `team/config.yaml`. The tool must run in GitHub Actions and produce results consumable by the Security Agent. |
| Default secrets detection tool (Gitleaks) | **Flexible** | Default is Gitleaks. May be substituted with GitHub Advanced Security Secret Scanning. Same consumption requirement applies. |
| Default dependency vulnerability scanner (OWASP Dependency-Check) | **Flexible** | Default is OWASP Dependency-Check. May be substituted with Snyk or similar. Same consumption requirement applies. |
| Severity categorization schema (Critical / High / Medium / Low) | **Locked** | Used consistently across SAST, secrets, and dependency scanning outputs. The Security Agent's inline PR comments use this schema. |

---

## Containerization & Deployment

| Item | Category | Notes |
|------|----------|-------|
| Containerization technology (Docker) | **Locked** | All services are containerized with Docker. No alternative container runtimes at the core layer. |
| Image tagging convention (`<request-id>-<commit-sha>`) | **Locked** | Used for rollback identification. Agents tag images this way; do not override. |
| Target hosting platform (Azure Container Apps) | **Locked** | The Deploy Agent targets Azure Container Apps. Migration to other platforms is out of scope for FORGE v1. |
| Two-environment model (`forge-staging` → `forge-production`) | **Locked** | Staging and production are separate environments. No single-environment deployments. |
| Staging auto-deploy (no gate) | **Locked** | Staging deploys automatically. Humans do not approve staging deployments. |
| Production gate (GitHub Environment with required-reviewer approval) | **Locked** | One-click production approval is the final irreversible action. This gate cannot be bypassed. |
| Rollback mechanism (redeploy prior image tag) | **Locked** | No other rollback mechanism is defined. Previous revision retained 48 hours post-deploy. |
| Staging replica count (min 0, max 2) | **Flexible** | Defaults set in `team/config.yaml`. Configurable per service within the environment. |
| Production replica count (min 1, max 5) | **Flexible** | Defaults set in `team/config.yaml`. Min 1 (always on) is the default; teams may raise the minimum. |
| Container resource allocation (staging: 0.25 vCPU / 0.5 Gi; production: 0.5 vCPU / 1.0 Gi) | **Flexible** | Defaults set in `team/config.yaml`. Configurable per service. |
| Revision strategy (single active revision per environment) | **Locked** | No blue/green or canary at the FORGE platform level. |

---

## Technology Stack (Application Code)

| Item | Category | Notes |
|------|----------|-------|
| Frontend language (TypeScript) | **Locked** | Mandated for all React/Next.js frontend code. Baked into Frontend Agent and Test Writer Agent prompts. Plain JavaScript is not accepted. |
| Frontend framework (React / Next.js) | **Locked** | The Frontend Agent generates React/Next.js code. Changing frameworks would require a complete Frontend Agent redesign — this is an RFC-level decision. |
| Backend framework (.NET) | **Locked** | The Backend Agent generates .NET code. Same rationale as above. |
| Frontend test framework (Jest) | **Locked** | The Test Writer Agent writes Jest tests. Mandated at core layer. |
| Backend test framework (xUnit) | **Locked** | Mandated for all .NET backend tests. |
| Linting enforcement (linting runs as a CI check) | **Locked** | Linting cannot be disabled. This is a core CI gate. |
| Linting ruleset | **Flexible** | The specific ESLint/Prettier/StyleCop ruleset is team-configurable. Defined in `team/stack-preferences.yaml` and referenced by the linting CI job. |
| CSS approach (Tailwind, CSS modules, styled-components, etc.) | **Fully Open** | Decided by the team at design time. Captured in `design.md` and approved at the design gate. |
| Component library (shadcn, MUI, etc.) | **Fully Open** | Same as CSS approach. |
| .NET ORM (EF Core, Dapper, etc.) | **Fully Open** | Same as CSS approach. |
| State management library (Redux, Zustand, Context, etc.) | **Fully Open** | Same as CSS approach. |
| Logging library | **Fully Open** | Same as CSS approach. |
| Any other stylistic or architectural preference that does not affect CI or agent code generation | **Fully Open** | If the agent doesn't need it to produce runnable code, it's design-time. |

---

## Agent Configuration

| Item | Category | Notes |
|------|----------|-------|
| Agent roster (eleven agents, defined roles) | **Locked** | The eleven agents (Codebase Ingestion, Intake, Requirements, Design, Implementation Coordinator, Backend, Frontend, Test Writer, QA, Security, Deploy) are fixed. Adding or removing agents requires an RFC. |
| Agent execution model (stateless Claude Agent SDK calls in GitHub Actions jobs) | **Locked** | No persistent agent memory across stages. No alternative SDK — except Stage 3, which uses Anthropic Managed Agents (see ADR-0010). This is a core-layer exception, not a team choice. |
| Parallel execution of Backend / Frontend / Test Writer subagents | **Locked** | These three always run in parallel on a shared sandbox filesystem, orchestrated by the Implementation Coordinator (a Managed Agents session — see ADR-0010). Sequential execution is not supported. |
| Integration handling in Stage 3 | **Locked** | There is no separate integration-check job — this was eliminated under ADR-0010. Integration is handled natively by the Managed Agents coordinator session as it synthesizes subagent output before committing. This mechanism cannot be bypassed or replaced with a standalone check. |
| Agent model tier (Claude model tiers — Opus for the Implementation Coordinator, Sonnet for all other agents) | **Locked** | Set at the core layer per ADR-0010. Changing any agent's model tier requires an RFC (cost and capability implications). |
| Agent personas (tone, name, communication style) | **Flexible** | Defined in `team/` persona files. Teams can adjust how agents communicate — not what they produce. |
| Agent skills / additional tools | **Flexible** | Teams may add tools within the approved tool list. No unapproved external services. The approved list is maintained in `core/`. |
| Core agent prompts (what the agent is instructed to produce) | **Locked** | Core prompt content is fixed. Team personas layer on top of — not in place of — core prompts. |

---

## Governance

| Item | Category | Notes |
|------|----------|-------|
| RFC process (required for core layer changes) | **Locked** | All core layer changes go through RFC via GitHub Discussions. No exceptions. |
| RFC timeline (3 days to assign reviewer, 10 days review, 30 days to implement) | **Locked** | Defined in the Governance Model. |
| ADR format and storage | **Locked** | ADRs follow the defined template, stored in `core/decisions/`. |
| Core layer versioning (semantic versioning) | **Locked** | Core layer is versioned. Teams know exactly what version they are running. |
| Update cadence (non-security: 30 days; security gate changes: 10 days) | **Locked** | Teams must apply updates within these windows. |
| Team-layer changes (no RFC required) | **Fully Open** | Orchestration Manager has full authority within core-layer boundaries. No approval needed for team-layer changes. |
| Notification channels (Slack, Teams, email, etc.) | **Fully Open** | Team decides. Not prescribed by the core platform. |
| Notification content | **Fully Open** | Team decides what gate notifications say and to whom. |

---

## Excel Intake Template

| Item | Category | Notes |
|------|----------|-------|
| Template format and column structure | **Locked** | The Intake Agent reads a specific schema. BAs use the official template. Custom columns outside the schema are ignored. |
| Overview/context tab questions | **Locked** | The BA-facing questions on the context tab are fixed at the core layer. |
| Template branding / visual styling | **Flexible** | Teams may adjust visual formatting (fonts, colours, logo) without changing the data schema. |

---

## Quick-Reference Summary

| Category | Count | Key Examples |
|----------|-------|-------------|
| **Locked** | ~40 items | Pipeline stages, human gates, agent roster, TypeScript mandate, GitHub App permissions, security gate, production approval gate, no-self-merge rule |
| **Flexible** | ~15 items | Intake upload mechanism, default area path, security tool choices, container resource sizing, linting ruleset, agent personas |
| **Fully Open** | ~10 items | CSS approach, component library, ORM, state management, logging library, notification channels, team-layer governance |

---

*For questions about whether a specific change requires an RFC, see the FORGE Governance Model (Document 4). For step-by-step instructions on making team-layer changes, see the Orchestration Manager Guide (Document 6).*
