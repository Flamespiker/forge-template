# FORGE — Phase-by-Phase Summary & Training Reference

**Project:** FORGE — Full-SDLC Orchestration with Review Gates for Engineers
**As of:** 2026-08-05, context doc v37 (Step 3.10 / Deploy Agent complete)
**Purpose:** A single reference walking through each build phase — what it's for, what's actually been built and decided, real gotchas hit along the way, and training materials worth reading at that point. Companion to the living context doc, not a replacement for it — this is the "orient a new person" document; the context doc is the source of truth for decisions.

---

## Phase 1 — Repo Foundation

**Goal:** A real GitHub template repository exists with the right structure, configs, and workflow stubs. Nothing runs yet, but everything has a home.

**What's built:** `forge-template` repo (template flag on), the full folder structure (`core/agents/`, `core/schemas/`, `core/decisions/`, `team/personas/`, `tracking/`), `team/config.yaml` and `team/stack-preferences.yaml`, the FORGE tracking issue template, ten seed ADR stubs in `core/decisions/`, and guard-clause workflow stubs for all seven pipeline stages.

**Worth knowing:** this phase is intentionally inert — no agent logic, just scaffolding. The two-layer model (locked `core/` vs. customizable `team/`) is set up here and governs everything that follows: any file under `core/agents/` is the same "don't casually edit" governance tier for the rest of the project.

**Training / references:**
- [GitHub Docs — Creating a template repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository) — the template-repo mechanic teams will actually use to stand up their own instance
- [GitHub Docs — Actions workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions) — needed to read the Phase 1 workflow stubs before Phase 4 fills them in
- Anthropic's own [Architectural Decision Records](https://docs.anthropic.com) practice, or any standard ADR template (e.g. Michael Nygard's original format) — worth skimming before writing the seed ADRs, since Document 4 defines FORGE's specific ADR/RFC process on top of the generic pattern

---

## Phase 2 — Infrastructure Setup

**Goal:** Every external dependency is provisioned, credentialed, and verified before any agent code is written.

**What's built:** GitHub App `forge-pipeline` (repo-scoped, Contents/PRs/Issues/Checks R/W), Azure Container Registry, `forge-staging` and `forge-production` Container Apps environments (both later discovered to share one resource group, `forge-build-rg`), GitHub Environments (`staging` auto-deploy, `production` gated on Mike as reviewer), ADO PAT connection, Anthropic API key, and an end-to-end connectivity workflow confirming GitHub App token generation + ADO + Anthropic API all green. Managed Agents beta access confirmed separately (2.9).

**Real gotchas hit here** (worth flagging to anyone repeating this phase):
- `actions/create-github-app-token` needed the `@v3` bump (Node 24-native; `@v1` is deprecated and renames `app-id` → `client-id`) — a secret naming trap if you copy an older tutorial.
- The default `aka.ms/installazurecliwindows` link installs the **32-bit** Azure CLI, which fails installing the `containerapp` extension (`cryptography` has no prebuilt wheel for 32-bit Python) — use `aka.ms/installazurecliwindowsx64` instead.
- `az login`'s default Windows auth broker flow doesn't reliably surface an MFA prompt — `az login --use-device-code` does.
- Azure Portal only creates a Container Apps environment as a byproduct of creating a Container App — no standalone option there; the `az containerapp env create` CLI command doesn't have that restriction.
- **Verbally-confirmed-done ≠ actually done** for secrets — several secrets assumed stored earlier turned out not to be, and had to be added properly on a second pass.
- A **real credential-exposure incident** (an SP's `clientSecret` pasted into chat accidentally) was caught and handled correctly: treated as compromised immediately, rotated via `az ad sp credential reset` before use, and all subsequent credential handling moved to "type it directly into your own editor, never into chat."

**Training / references:**
- [Azure Container Apps — Overview & quickstart](https://learn.microsoft.com/en-us/azure/container-apps/overview) — core service this phase provisions
- [Azure CLI install guide (Windows)](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows) — check the 64-bit-specific link explicitly, not just the top default one
- [GitHub Apps — Creating a GitHub App](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps) and [`actions/create-github-app-token`](https://github.com/actions/create-github-app-token) — the exact action FORGE uses for cross-repo auth
- [Azure DevOps REST API — Work Items](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/) — what the ADO PAT is actually authorizing
- [Managed Agents Quickstart](https://platform.claude.com/docs/en/managed-agents/quickstart) — needed before 2.9's beta-access check makes sense

---

## Phase 3 — Agent Implementation

**Goal:** Each agent is a working Python script, callable from the command line, producing the correct output artifact. Wired into GitHub Actions in Phase 4. Built in pipeline order so each agent's output becomes the next one's real test input.

This is the largest phase and the one with the most decisions attached — worth its own sub-breakdown.

### 3.1–3.3 — Shared utilities, Intake Agent, Requirements Agent
Built and verified against real services. `claude_agent_wrapper.py` calls the base `anthropic` Python client's Messages API directly per **ADR-0011**, which superseded an earlier plan to use the Claude Agent SDK — every non-Stage-3 agent script must wrap its `invoke_agent()` call in try/except at the call site, since the wrapper never sets `is_error=True` itself.

### 3.4 — Design Agent
Produces `design.md`, `openapi.yaml`, `tasks.md`. Real run verified: branch created, files committed, draft PR opened.

### 3.4a–3.7 — Implementation Coordinator + Backend/Frontend/Test Writer subagents
The one stage that uses Anthropic's **Managed Agents API** (**ADR-0010**) instead of the plain Messages client — a coordinator running three specialist subagents in parallel on a shared sandbox filesystem. Real run against `REQ-2026-01` produced a full .NET + Next.js implementation; merged as PR #5 after stripping three unrequested scope-creep files (`COMPLIANCE_CHECKLIST.md`, a mispathed `ci.yml`, a stray verify script).

### 3.8 — QA Agent
Runs `dotnet test`/`npm test`, classifies failures via a fixed deterministic string-marker mapping (not an LLM judgment call), files ADO bugs. First live run surfaced several real defects — an unpushed-commit gap and cross-platform bugs in the agent itself, plus five build/test-infrastructure defects in the merged application code that had nothing to do with QA logic.

### 3.9 — Security Agent
Runs Semgrep, Gitleaks, and OWASP Dependency-Check via shell against a local checkout, maps findings to severity.

### 3.10 — Deploy Agent
Deterministically detects deployable units (walks for `.csproj` files, classifies `web`/`worker`, treats a frontend `package.json` as its own unit), generates missing Dockerfiles from stack templates, builds/pushes to ACR, deploys to Container Apps via a scoped service-principal login, posts one PR comment with staging URLs. Real run deployed two of three units successfully; surfaced two genuine new gaps (no secrets-wiring mechanism for Container Apps yet; a frontend dependency-duplication bug) now tracked as open items.

**Cross-cutting lessons from all of Phase 3:**
- **Verify against the live repo, not documentation summaries** — this caught real drift more than once (unpushed commits reported as pushed; a "design.md gap" that turned out to be a misread, confirmed only by `git blame`).
- **Real executed evidence required before "done"** — diffs, actual test output, real API responses, not summaries of changes.
- **Scope creep is a real, recurring risk** in agent-produced output — tighten prompts, don't just catch it after the fact.
- **Prompt/architecture patches have real cost implications** — worth logging in the cost ledger, not just accepting silently.

**Training / references:**
- [Managed Agents — Multi-agent docs](https://platform.claude.com/docs/en/managed-agents/multi-agent) — the coordinator/subagent pattern Stage 3 (3.4a–3.7) is built on directly
- [Claude Cookbooks — managed_agents folder](https://github.com/anthropics/claude-cookbooks/tree/main/managed_agents) — a near-exact worked example of the parallel-specialist pattern
- [Anthropic — Messages API reference](https://docs.anthropic.com/en/api/messages) — what `claude_agent_wrapper.py` calls directly per ADR-0011
- [Tool Use overview](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview) — every agent uses tools; read before writing any stage script
- [xUnit documentation](https://xunit.net/docs/getting-started/netcore/cmdline) and [Jest documentation](https://jestjs.io/docs/getting-started) — the two test frameworks QA's parsing logic depends on
- [Semgrep docs](https://semgrep.dev/docs/), [Gitleaks](https://github.com/gitleaks/gitleaks), [OWASP Dependency-Check](https://owasp.org/www-project-dependency-check/) — the three Security Agent scanners
- [Docker — Dockerfile reference](https://docs.docker.com/reference/dockerfile/) and [Azure Container Apps — `az containerapp` CLI reference](https://learn.microsoft.com/en-us/cli/azure/containerapp) — core to Deploy Agent's build/push/deploy flow
- [ASP.NET Core web APIs overview](https://learn.microsoft.com/en-us/aspnet/core/web-api/) and [Next.js documentation](https://nextjs.org/docs) — the two stacks Backend/Frontend actually produce, useful context for reading their output

---

## Phase 4 — Pipeline Wiring *(complete)*

**Goal:** Wire the built-and-verified agent scripts into the actual GitHub Actions workflow stubs from Phase 1, so the pipeline runs end-to-end without manual invocation.

**Known design notes already carried forward for this phase:** step 4.3 (ADO item creation) should fail the whole workflow run if any item fails, so Design never starts against a partial traceability chain; the checkout wiring this phase introduces (step 4.5, per the Build Plan) is what several Phase 3 stages have so far substituted with a manual local clone.

**Training / references:**
- [GitHub Actions — Contexts and expressions](https://docs.github.com/en/actions/learn-github-actions/contexts) — needed once workflows start passing state between jobs via labels/outputs rather than a human running scripts by hand
- [GitHub Actions — Environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment) — the actual mechanism behind the `staging`/`production` approval gates set up in Phase 2.5

---

## Phase 5 — App 1: Greenfield Pipeline Validation *(substantially complete — see `FORGE-Phase5-Closeout.md`)*

**Goal:** Run a full, real greenfield request through the wired pipeline end-to-end, human gates and all, to validate the whole thing works together — not just stage-by-stage.

**Outcome:** Ran for real against "Inactive User & License Auditor" (`REQ-2026-02`), a D365 Dataverse admin tool. Reached staging (confirmed working in a real browser); production deliberately not attempted. Needed real manual intervention along the way (recovery from a Stage 3 completion-detection bug, admin-merges, hand-wired D365 secret, one-off Deploy Agent patches) — read as a genuine validation run finding real gaps, not a clean pass. The app's Azure/D365 resources have since been decommissioned; the close-out doc is the authoritative record of what shipped, what was descoped, and what's carried forward into Phase 6.

**Training / references:** Document 6 (Orchestration Manager Guide) was the operational reference used throughout, as expected.

---

## Phase 6 — App 2: Repeatability *(not yet started)*

**Goal:** Run a second, different request through the same pipeline to confirm FORGE generalizes rather than having been implicitly tuned to App 1's specifics.

---

## Phase 7 — Enhancement Workflow *(not yet started)*

**Goal:** Build and validate the enhancement (brownfield) path — the Codebase Ingestion Agent (3.11) reading an existing repo to produce an architecture summary feeds into Requirements, rather than starting from a blank slate.

---

## Phase 8 — Handoff Readiness *(not yet started)*

**Goal:** Confirm a fresh team could actually pick up `forge-template`, clone it, and run it — documentation complete, ADR set complete (including organically-added ones like ADR-0011), a verified fresh-clone walkthrough.

**Known open item already tracked for this phase:** the Build Plan currently has no step that actually creates the nine GitHub labels the pipeline depends on — they were created manually as a one-off during the build; Phase 8.4's fresh-clone verification would otherwise hit this gap.

**Training / references:**
- [CCA-F certification](https://anthropic.skilljar.com) — flagged in the context doc as "better understood after real agent work," i.e. save this for after Phase 3/4 rather than before

---

## How to use this document

This is a snapshot as of context doc v37 — it'll drift as Phases 4–8 start producing their own real decisions and gotchas the same way Phases 1–3 did. Treat it as an orientation document for a new person joining mid-project, or a refresher before picking up a phase that's been dormant for a while. For anything more current or more detailed than what's here, the living context doc (`FORGE-context_vN.md`) is authoritative.
