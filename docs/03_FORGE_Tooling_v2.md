# FORGE Tool & Licensing Inventory

**Document 3 of 9 — Every Tool, License Type, Who Provisions, Cost**

---

## 1. Purpose of This Document

This document enumerates every tool FORGE depends on or recommends: what it does in the FORGE context, whether it's required or optional, who provisions it, what license type applies, and what it costs. It also resolves three open items carried forward from the Architecture Document (Document 2): ADO field mapping, Azure Container Apps environment specifics, and GitHub App permission scoping.

The audience for this document is the person standing up a FORGE instance — the Orchestration Manager — and anyone doing cost or procurement review before committing to the platform. It is a reference, not a narrative: read the rows for the tools that matter to you, refer back to the Architecture Document for context on how each fits into the pipeline.

---

## 2. How to Read This Inventory

Each tool entry records:

- **Role in FORGE** — what FORGE uses this tool for, specifically
- **Required / Optional** — Required tools are load-bearing; FORGE does not function without them. Optional tools are recommendations; a team can substitute or skip them.
- **Who provisions** — who sets up the account, credential, or service. "Org admin" means an existing LAA administrator role; "Orchestration Manager" means the person owning the FORGE instance.
- **License type** — SaaS subscription, consumption-based billing, open source (free), or already-owned (LAA already has this, no new procurement needed)
- **Build-phase cost** — cost while FORGE is being built and validated on Mike's personal accounts
- **Production cost** — cost once the org's accounts are in use

Where two tools serve the same role (e.g., two SAST options), both are listed. FORGE's recommended default is noted; alternatives are marked as such.

---

## 3. Tool Inventory

### 3.1 Source Control & CI/CD — GitHub

| Tool | Role in FORGE | Required | Who Provisions | License Type | Build-Phase Cost | Production Cost |
|---|---|---|---|---|---|---|
| **GitHub repository (FORGE repo)** | Hosts workflows, agent config, tracking issues — the orchestration layer | Required | Orchestration Manager | GitHub Teams or Enterprise (org) | Free (personal account) | Included in org GitHub plan |
| **GitHub repository (custom-apps monorepo)** | Target of all FORGE output: branches, PRs, application code | Required | Org admin (already exists) | Already owned | — | Already paid |
| **GitHub Actions** | Runs all workflow stages; the orchestration engine (Document 2 §2.1) | Required | Included with repo | Included with GitHub plan (usage limits apply) | Free tier: 2,000 min/month (personal); minutes consumed per pipeline run | GitHub Teams: 3,000 min/month included; ~$0.008/min (Linux) beyond that |
| **GitHub Environments** | Enforces the Deploy gate (production Environment with required reviewers) | Required | Orchestration Manager | Included with GitHub Teams and above | Free | Included |
| **CODEOWNERS** | Enforces core-layer protection — core/ paths require Orchestration Manager approval | Required | Orchestration Manager | Included with GitHub | Free | Included |
| **GitHub App installation** | Cross-repo authentication: FORGE repo workflows → monorepo operations (branches, commits, PRs, check runs) — see §6 | Required | Orchestration Manager + org admin | Included with GitHub | Free | Free |
| **Branch protection rules** | Prevents direct commits to `main`; enforces required-reviewer approvals and required-check passes before merge | Required | Orchestration Manager (FORGE repo) + org admin (monorepo) | Included with GitHub | Free | Included |

**GitHub plan note:** GitHub Actions minutes and Environments with required reviewers are available on the GitHub Teams plan ($4 USD/user/month for private repos as of this writing). If LAA is already on GitHub Enterprise, all of the above is included. Verify the current org plan before provisioning — the Orchestration Manager may not need to do anything for GitHub itself beyond creating the FORGE repo.

---

### 3.2 Work Item Tracking — Azure DevOps

| Tool | Role in FORGE | Required | Who Provisions | License Type | Build-Phase Cost | Production Cost |
|---|---|---|---|---|---|---|
| **ADO Boards** | Epics, Features, User Stories, Bug tickets — created by FORGE workflows via the ADO API on `requirements-approved` | Required | Org admin (LAA already has ADO) | Already owned | — | Already paid |
| **ADO REST API** | FORGE workflows call the ADO API to create and link work items; authentication via PAT or Azure Service Principal | Required | Orchestration Manager (creates a PAT or service principal; stores credential as a GitHub Actions secret in the FORGE repo) | Included with ADO | Free | Free |

**ADO field mapping** is resolved in §5 of this document.

---

### 3.3 AI / Agent Platform — Anthropic

| Tool | Role in FORGE | Required | Who Provisions | License Type | Build-Phase Cost | Production Cost |
|---|---|---|---|---|---|---|
| **Anthropic API** | Powers all ten agents. Nine agents (Codebase Ingestion, Intake, Requirements, Design, QA, Security, Deploy — plus the Stage 3 Implementation Coordinator and its Backend/Frontend/Test Writer subagents at the account level) run through the same Anthropic API account; billing splits by invocation type — see the Claude Agent SDK and Managed Agents rows below | Required | Mike (build phase: personal developer account); org IT or a designated API owner (production) | Consumption-based (pay-per-token, plus Managed Agents session-hour billing for Stage 3 — see below) | Mike's personal API account — token costs incurred per pipeline run | Org API account; monthly cost depends on run volume and average token consumption per stage |
| **Claude Agent SDK** | The code library FORGE uses to construct and invoke agents for all stages except Stage 3 — installed in GitHub Actions runner environments via pip/npm | Required | No separate account; bundled with Anthropic API access | Open source (Apache 2.0) | Free | Free |
| **Anthropic Managed Agents** | Runs the Stage 3 Implementation Coordinator agent, which orchestrates the Backend, Frontend, and Test Writer subagents in parallel on a shared sandbox filesystem (ADR-0010, Document 2 §11). Requires the `managed-agents-2026-04-01` beta header on API calls. Billed at standard token rates **plus $0.08 USD per agent session-hour** of active runtime, in addition to the token costs already covered by the Anthropic API row above | Required (for Stage 3 only) | Same Anthropic API account as above; no separate provisioning beyond enabling the beta header in the Implementation Coordinator's API wrapper | Consumption-based (public beta as of May 2026) | Token costs (see above) + ~$0.08–0.32 USD per pipeline run (estimate: 1–4 hours active runtime) — track actuals during App 1 | Same billing model; monthly cost scales with run volume |
| **Claude model tiers** | Sonnet tier is the default for all standalone agents and the Stage 3 subagents (Backend, Frontend, Test Writer); Opus tier is used for the Stage 3 Implementation Coordinator (Document 2 §2.2, §11) | Required (as default) | Configured in `core/config.yaml`; model string set per-agent | Billed through Anthropic API | Per-token | Per-token |

**Cost estimation note:** Exact token costs per pipeline run depend on codebase size, requirements complexity, and agent prompt lengths — these can only be measured during the build-phase runs. After App 1 and App 2 runs are complete, a per-pipeline cost estimate should be recorded here. As a rough planning figure: Sonnet-tier models at typical requirements-to-deployment run volumes (10–50k tokens per stage, 10 stages) are likely to run in the $1–5 USD range per complete pipeline execution for token costs alone, plus an estimated $0.08–0.32 USD per run for Managed Agents session-hour billing on Stage 3 (1–4 hours active runtime), though both figures will vary significantly. Track actuals.

---

### 3.4 Cloud Infrastructure — Azure

| Tool | Role in FORGE | Required | Who Provisions | License Type | Build-Phase Cost | Production Cost |
|---|---|---|---|---|---|---|
| **Azure Container Registry (ACR)** | Stores Docker images tagged by request ID + commit SHA; the source for Container Apps deployments | Required | Mike (build: personal Azure subscription); org Azure admin (production) | Consumption-based | ACR Basic tier: ~$0.17 USD/day + storage (~$0.003/GB/day) | Same tier; org Azure subscription |
| **Azure Container Apps** | Runs deployed applications; staging (auto-deploy) and production (gated) environments — see §6 for environment specifics | Required | Mike (build); org Azure admin (production) | Consumption-based (Consumption plan) | Per-vCPU-second and per-GiB-second; $0 when idle (scale to zero) | Same; billed to org Azure subscription |
| **Azure Container Apps Environment** | Shared networking/logging boundary for Container Apps instances; one environment per deployment target (staging, production) | Required | Provisioned once by Mike / org Azure admin | Included with Container Apps | Included | Included |
| **Azure subscription** | The billing and resource boundary for all Azure services above | Required | Mike (build: personal); org IT (production) | Pay-as-you-go or Enterprise Agreement | Personal PAYG | Org EA or PAYG |

**Azure Container Apps environment specifics** are resolved in §6 of this document.

---

### 3.5 Security Tooling

FORGE's Security Agent (Document 2 §3, §4.7) runs three categories of checks: SAST (static analysis), secrets detection, and OWASP/dependency vulnerability scanning. Each runs in a GitHub Actions job and posts results as PR check runs and inline comments. All recommended tools below are open source and run within GitHub Actions — no separate SaaS account is required for the defaults.

| Tool | Category | Role in FORGE | Required | Who Provisions | License Type | Build-Phase Cost | Production Cost |
|---|---|---|---|---|---|---|---|
| **Semgrep Community** | SAST | Static analysis of .NET and React/Next.js code — rule sets for common vulnerability classes (injection, XSS, insecure deserialization, etc.) | Required (one SAST tool must be chosen) | Orchestration Manager installs via GitHub Actions step (`returntocorp/semgrep-action`) | Open source (LGPL-2.1); Community rules free | Free | Free |
| **Gitleaks** | Secrets detection | Scans commit history and staged changes for API keys, tokens, connection strings, and credential patterns | Required (one secrets tool must be chosen) | Orchestration Manager adds `gitleaks/gitleaks-action` to the Security workflow | Open source (MIT) | Free | Free |
| **OWASP Dependency-Check** | Dependency vulnerability scanning | Scans .NET NuGet and Node npm dependencies against the NVD CVE database; flags known vulnerabilities by severity | Required (one dependency scanner must be chosen) | Orchestration Manager adds `dependency-check/Dependency-Check_Action` to the Security workflow | Open source (Apache 2.0) | Free | Free |
| **GitHub Advanced Security (CodeQL + Secret Scanning)** | SAST + secrets (alternative) | GitHub's native SAST and secret scanning — tighter GitHub integration, automatic PR annotations, broader language coverage | Optional (upgrade path) | Org admin enables on the monorepo; requires GitHub Advanced Security add-on | GitHub Advanced Security add-on (~$49 USD/active committer/month) | Not needed in build phase | If adopted: significant per-user cost; evaluate against open-source alternatives |
| **Snyk** | Dependency vulnerability scanning (alternative) | Freemium SaaS alternative to OWASP Dependency-Check; richer advisory database, auto-fix PR suggestions | Optional | Orchestration Manager creates Snyk account; integrates via `snyk/actions` | Freemium (free tier: limited scans/month; paid plans from ~$25/month) | Free tier sufficient for build phase | Evaluate based on scan volume |

**Default recommendation:** Semgrep Community + Gitleaks + OWASP Dependency-Check. All three run in GitHub Actions, cost nothing, and satisfy the Security Agent's three check categories without a SaaS dependency. GitHub Advanced Security and Snyk are the upgrade path if LAA decides to consolidate security tooling or if the free tools prove insufficient in production.

A Critical finding from any of the three tools sets a failing check run on the implementation PR (Document 2 §4.7), which blocks merge without manual override — this is enforced by the branch protection rule requiring the Security check to pass, not by the agent making a judgment call.

---

### 3.6 Development Stack

These are the languages, frameworks, and runtimes the FORGE-built applications use. They are not "FORGE tools" per se — FORGE doesn't install or manage them as infrastructure — but they are recorded here because they appear in the agent configuration (the Backend and Frontend agents are tuned for these stacks) and because their licenses matter for the applications FORGE produces.

| Tool | Role | License Type | Cost |
|---|---|---|---|
| **.NET (latest LTS)** | Backend API implementation — used by the Backend Agent | MIT (open source, Microsoft) | Free |
| **xUnit** | .NET unit testing framework — used by the Test Writer Agent | Apache 2.0 (open source) | Free |
| **React / Next.js** | Frontend implementation — used by the Frontend Agent | MIT (open source) | Free |
| **Jest** | JavaScript/TypeScript unit testing — used by the Test Writer Agent | MIT (open source) | Free |
| **Docker** | Containerization — used by the Deploy Agent to build images | Docker Desktop requires a paid subscription for organizations above 250 employees or $10M annual revenue (check LAA's eligibility); Docker CLI and BuildKit in CI are free | Docker CLI in GitHub Actions: free. Docker Desktop for local dev: check org eligibility |

**Docker Desktop note:** Docker Desktop's licensing applies to GUI desktop use. GitHub Actions runners run Docker CLI directly, which is free regardless of organization size. If LAA developers want Docker Desktop locally, verify whether the org qualifies for the free tier (non-profits may qualify — confirm with Docker's terms). Alternatively, Rancher Desktop (open source, MIT) is a free substitute for local container development.

---

## 4. Provisioning Checklist

The order matters — some credentials can't be created until the preceding service exists.

1. **Confirm org GitHub plan** — verify GitHub Teams or Enterprise is active; confirm Actions minutes allocation and Environments availability.
2. **Create FORGE template repo** — Orchestration Manager creates the repo from the FORGE template; sets up `CODEOWNERS` on `core/` and `.github/workflows/`.
3. **Create GitHub App** (§6) — Orchestration Manager creates the App, installs it on the monorepo, stores the App ID and private key as GitHub Actions secrets in the FORGE repo.
4. **Confirm ADO access** — org admin confirms ADO Boards is available; Orchestration Manager creates a PAT (or service principal) with work item read/write scope; stores as a GitHub Actions secret.
5. **Set up Anthropic API** — Mike configures the API key as a GitHub Actions secret; org admin sets up the org API account before production cutover.
6. **Provision Azure Container Registry** — Mike creates ACR in the personal Azure subscription (build phase); creates a service principal with `acrpush` role; stores credentials as GitHub Actions secrets.
7. **Provision Azure Container Apps** (§6) — Mike creates staging and production Container Apps Environments; stores environment names and resource group references in `team/config.yaml`.
8. **Configure security tools** — Orchestration Manager adds Semgrep, Gitleaks, and OWASP Dependency-Check GitHub Actions steps to the Security workflow; no external accounts required for the defaults.
9. **Configure branch protection** on the monorepo — org admin applies: require PR, require status checks (QA + Security), require reviews (Technical Approver, QA Reviewer, Security Reviewer), no direct push to `main`.
10. **Run App 1** — validates the full provisioning end to end; record actual Anthropic API token costs per run.

---

## 5. ADO Field Mapping (Open Item from Document 2)

This resolves the open item from Document 2 §5 and §10. The table below specifies which ADO fields FORGE populates automatically via API, which are left to the Orchestration Manager or team to configure, and which are deliberately not touched.

### Epics

| Field | Source | Who/What Sets It |
|---|---|---|
| Title | Requirements Agent: high-level capability name from `requirements.md` | FORGE (automatic) |
| Description | Summary paragraph from the relevant section of `requirements.md` | FORGE (automatic) |
| State | "Active" on creation | FORGE (automatic) |
| Area Path | Default area path for the team | Team config (`team/config.yaml`) — Orchestration Manager sets the default; not overridden by FORGE |
| Iteration Path | Left blank on creation | Team fills in after creation — FORGE does not assign sprints |
| Priority | Not set | Left to team |

### Features

| Field | Source | Who/What Sets It |
|---|---|---|
| Title | Requirements Agent: feature-level capability from `requirements.md` | FORGE (automatic) |
| Description | Feature description from `requirements.md` | FORGE (automatic) |
| Parent | Linked to the corresponding Epic | FORGE (automatic) |
| State | "Active" on creation | FORGE (automatic) |
| Area Path | Inherited from Epic / team default | FORGE (automatic, mirrors Epic) |
| Iteration Path | Left blank | Team fills in |

### User Stories

| Field | Source | Who/What Sets It |
|---|---|---|
| Title | Requirements Agent: "As a [persona], I want [capability]" form | FORGE (automatic) |
| Description | Narrative from `requirements.md` | FORGE (automatic) |
| Acceptance Criteria | Acceptance criteria section from `requirements.md` | FORGE (automatic) |
| Parent | Linked to the corresponding Feature | FORGE (automatic) |
| State | "Active" on creation | FORGE (automatic) |
| Story Points | Not set | Team estimates after creation |
| Priority | Not set | Team sets after creation |
| Area Path | Inherited from Feature | FORGE (automatic, mirrors Feature) |
| Iteration Path | Left blank | Team fills in |
| Tags | `forge-managed`, `<request-id>` | FORGE (automatic — allows filtering all FORGE-generated items) |
| GitHub tracking issue URL | Link to FORGE repo tracking issue (custom field or description footer) | FORGE (automatic — the two-way traceability link from Document 2 §5) |

### Bugs (QA loop-back)

| Field | Source | Who/What Sets It |
|---|---|---|
| Title | QA Agent: failing test name + short description | FORGE (automatic) |
| Description | Test failure output, stack trace excerpt | FORGE (automatic) |
| Steps to Reproduce | Test case steps from the test suite | FORGE (automatic) |
| Severity | Mapped from test failure type (assertion failure = Medium; exception/crash = High) | FORGE (automatic, using a fixed mapping — not AI judgment) |
| Parent | Linked to the relevant User Story | FORGE (automatic) |
| State | "Active" on creation | FORGE (automatic) |
| Tags | `forge-managed`, `<request-id>`, `qa-loop-back` | FORGE (automatic) |
| GitHub PR URL | Link to the implementation PR in the monorepo | FORGE (automatic) |

**Fields FORGE never touches:** Effort, Business Value, Risk, custom org fields, any field not listed above. FORGE writes a minimal, accurate record; teams layer in their own planning data after creation. This is the dividing line between what FORGE is responsible for (traceability and accuracy) and what belongs to the team's planning process (prioritization and scheduling).

**Customization boundary:** The exact field values FORGE writes (e.g., the tagging convention, the area path default) are configurable in `team/config.yaml` — team layer. The *fields FORGE writes at all* (e.g., whether FORGE sets priority) are fixed in `core/` — teams cannot add new fields to the core write set without an RFC (Document 4).

---

## 6. Azure Container Apps — Environment Specifics (Open Item from Document 2)

This resolves the open item from Document 2 §8 and §10.

### Environment layout

Two Container Apps Environments: `forge-staging` and `forge-production`. Both live in the same Azure resource group and region per application. Separate environments (rather than separate revisions in one environment) enforce the physical separation between staging and production traffic — there is no path by which a staging deployment can accidentally affect production.

### Revision strategy

- **Staging:** Single active revision, replaced on each deploy. No traffic-splitting; staging is for validation, not canary testing.
- **Production:** Single active revision, replaced only on GitHub Environment approval. The previous revision is retained for 48 hours post-deploy to enable rollback (redeploy prior image tag via the FORGE tracking issue comment UI or a `workflow_dispatch` trigger — see Orchestration Manager Guide, Document 6).

### Scaling

| Environment | Min replicas | Max replicas | Scale trigger |
|---|---|---|---|
| Staging | 0 (scale to zero) | 2 | HTTP concurrency ≥ 10 |
| Production | 1 (always on) | 5 | HTTP concurrency ≥ 20 |

Staging scales to zero when idle — this is the primary cost-control lever and acceptable for an environment where no one is actively testing. Production keeps one replica running to avoid cold-start latency for internal users.

These values are defaults in `team/config.yaml` and are team-layer configurable. Applications with unusual load patterns (batch jobs, event-driven microservices) should override them per-service.

### Resource sizing (default, per container)

| Environment | CPU | Memory |
|---|---|---|
| Staging | 0.25 vCPU | 0.5 Gi |
| Production | 0.5 vCPU | 1.0 Gi |

Starting values for internal line-of-business applications with moderate load. Resize after observing actual usage in staging; do not upsize speculatively.

### Ingress

Both environments: HTTPS only, external ingress enabled (internal LAA network or authenticated access depending on application). HTTP → HTTPS redirect enforced at the Container Apps level.

### Cost implication

On Azure's Consumption plan, cost is zero when staging is idle and proportional to actual request volume and replica count in production. For internal LAA tools at typical usage patterns, monthly production costs per application are expected to be in the low tens of dollars (USD) — confirm actuals after App 1 runs in production.

---

## 7. GitHub App — Permission Scoping (Open Item from Document 2)

This resolves the open item from Document 2 §2.4 and §10.

### Why a GitHub App, not a PAT

A GitHub App installation is preferred over a personal access token because: it's scoped to specific repositories (FORGE can only access the monorepo, not everything in the org), it's attributable to "FORGE" in audit logs rather than to an individual's account (Git commits and PR actions appear as `forge-bot` or similar, not `mfaulkner`), and it's revocable without affecting any person's account.

### Creating the GitHub App

1. Go to the org's GitHub settings → Developer settings → GitHub Apps → New GitHub App.
2. Name: `forge-pipeline` (or similar — this name appears in commit attribution and PR author fields).
3. Homepage URL: the FORGE template repo URL.
4. Disable "Expire user authorization tokens" — FORGE uses installation tokens, not user tokens.
5. Disable webhook — FORGE does not need the App to receive webhooks (workflows listen to repo events directly).

### Permissions required

| Permission | Scope | Level | Reason |
|---|---|---|---|
| Contents | Monorepo | Read & Write | Create branches, push commits |
| Pull requests | Monorepo | Read & Write | Open PRs, post PR body, update PR description |
| Issues | FORGE repo | Read & Write | Update tracking issue comments and labels |
| Checks | Monorepo | Read & Write | Post QA and Security check runs to implementation PR |
| Metadata | Both | Read | Required by GitHub for any App installation |

No other permissions. FORGE does not need access to Actions, Secrets, Environments, or any org-level scope — all of those are managed by the workflow itself running with its own `GITHUB_TOKEN` in the FORGE repo context.

### Installation

After creating the App: install it on the **monorepo only** (not org-wide). Select "Only select repositories" → choose the custom-apps monorepo. This is the permission boundary that makes FORGE cross-repo access auditable and narrowly scoped.

### Credential storage

After installation, generate a private key for the App (PEM file). Store two values as **repository-level secrets** in the FORGE repo (not org-level secrets):
- `FORGE_APP_ID` — the App's numeric ID (visible on the App settings page)
- `FORGE_APP_PRIVATE_KEY` — the PEM file contents

Workflows use these two values with the `actions/create-github-app-token` Action to generate a short-lived installation token at the start of any job that touches the monorepo. The token expires after one hour — appropriate for a single job run.

### Operational note for the Orchestration Manager

If the GitHub App's private key needs to be rotated (security event, key expiry policy), generate a new key in GitHub App settings, update the `FORGE_APP_PRIVATE_KEY` secret in the FORGE repo, and delete the old key from the App settings. No workflow changes required — the token generation step reads the secret at runtime.

---

## 8. Cost Summary

| Category | Build Phase (Mike's personal accounts) | Production (org accounts) |
|---|---|---|
| GitHub | Free (personal account) | Included in org GitHub plan |
| GitHub Actions minutes | Free tier (2,000 min/month) — monitor usage during App 1 and 2 runs | ~$0.008/min beyond Teams plan included minutes; track actuals |
| Azure DevOps Boards | — | Already paid (org) |
| Anthropic API (token costs) | Personal API account; ~$1–5 USD per full pipeline run (estimate — track actuals) | Org API account; same per-run cost, multiplied by run volume |
| Managed Agents runtime (Stage 3 coordinator + subagents) | ~$0.08–0.32 USD per pipeline run (estimate: 1–4 hours active runtime — track actuals during App 1) | Same billing model; org API account, multiplied by run volume |
| Azure Container Registry | ~$0.17/day + minimal storage | Same; charged to org Azure subscription |
| Azure Container Apps | ~$0 at rest (scale to zero in staging); low single-digit USD/month in production per app | Same; org subscription |
| Security tools (Semgrep, Gitleaks, OWASP Dependency-Check) | Free | Free |
| Development stack (.NET, React, Jest, xUnit) | Free | Free |
| Docker (CI usage) | Free | Free |

**Total incremental cost during build phase:** Anthropic API token cost (likely under $20 USD across the three demo runs) plus Managed Agents session-hour billing (likely under $2 USD across the three demo runs, at the estimated $0.08–0.32/run) plus ACR storage (negligible). Everything else is free or already paid.

**Total incremental cost in production:** Anthropic API token costs + Managed Agents session-hour billing (both dominant variables; track from build-phase actuals) + Azure Container Apps compute (low, scale-to-zero) + any GitHub Actions minutes overage. No net-new SaaS contracts required to go to production with the default tool choices.

---

## 9. Open Items

The following remain unresolved after this document and are carried forward:

- **GitHub Actions minutes estimation** — actual per-pipeline-run minute consumption can only be measured during App 1 build-phase runs. Record actuals and update the cost summary above.
- **Anthropic API per-run cost actuals (token + Managed Agents session-hour)** — same; both estimates above are planning figures only. Record after App 1 and App 2 complete.
- **Managed Agents beta stability** — `managed-agents-2026-04-01` is a public beta header; monitor for breaking changes during the build phase and flag any disruptions as RFC candidates (see Document 2 §10, §11).
- **Docker Desktop licensing for local developer use** — verify whether LAA qualifies for Docker's free tier for non-profits, or whether Rancher Desktop should be the standard recommendation for local development. Not blocking for build phase (CI uses Docker CLI).
- **ADO service principal vs. PAT** — a service principal (Azure AD app registration with ADO permissions) is more robust than a PAT for production use (no expiry tied to an individual). Evaluate before production cutover; interim: PAT is acceptable for build phase.
- **RFC process details** (Document 4) — how core platform changes are proposed and approved, including what tooling hosts RFC discussion (GitHub Discussions, ADO Wiki, etc.).
- **External training / certification recommendations** — Track 1 AI Foundations external resources and certifications (Document 5).

---

## 10. Where This Fits

This document makes the architecture in Document 2 provisionable: every service is named, every credential is scoped, and every cost is estimated. The next document — the **FORGE Governance Model** (Document 4) — defines how core-layer changes get proposed, reviewed, and decided once multiple teams are running FORGE instances: the RFC process, ADR format, and decision authority boundaries.
