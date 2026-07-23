# FORGE Architecture Document

**Document 2 of 9 — Agent Topology, Pipeline Mechanics, ADO Integration, GitHub Structure, Container Strategy**

---

## 1. Purpose of This Document

This document defines *how* FORGE works, technically. It assumes the reader has read the **FORGE Introduction** (Document 0) and the **Product Specification** (Document 1), and translates the personas, features, and success criteria in those documents into a concrete implementation design: what runs, what triggers it, where state lives, and how the two-layer model is enforced in the repository itself rather than just in policy.

Four foundational decisions anchor everything below:

- **Orchestration is event-driven.** GitHub Actions workflows, triggered by PR events, label changes, and issue events, *are* the deterministic orchestration layer. There is no separate long-running orchestrator service.
- **State lives natively in GitHub** — labels, issue state, and GitHub Environments — not in a bespoke database or state file. GitHub is the source of truth for "what stage is this in, and what gate is it waiting on."
- **Each stage's agent invocation is stateless.** Every stage spins up a fresh Claude Agent SDK call scoped to that stage, given exactly the artifacts it needs as input, and producing exactly the artifacts the next stage (or the human gate) needs as output. No agent process persists across stages or holds cross-stage memory. This keeps every run reproducible, keeps agent scope bounded (per Document 0's core pattern), and matches how GitHub Actions runs work anyway — each job starts from a clean runner.

  *ADR-0002 clarification (per ADR-0010):* "Stateless" means no cross-stage memory. Within Stage 3, the Managed Agents coordinator session maintains coordinator-to-subagent state during execution — this is bounded inside the stage window. The stage still starts from committed files (design.md, openapi.yaml, tasks.md) and ends by committing files (the feature branch implementation). No state from Stage 3's agent session is available to any subsequent stage. The stateless-per-stage principle is not violated; it is clarified to account for within-stage coordination.
- **FORGE is a separate repo from the code it works on.** FORGE does not live inside the application code it builds or modifies. LAA's custom applications live in an existing **monorepo** (all microservices, one repo) — separate from an existing **Dynamics 365 repo**. FORGE's own template repo (workflows, agents, core/team config — Document 0's "GitHub template repository") is distinct from both, and orchestrates *into* them: it opens branches and PRs in the target repo, it doesn't hold application source itself. Dynamics 365 is a future consideration for FORGE, not v1 scope (§6.3) — v1 targets the custom-apps monorepo only.

This is a working assumption for this document, flagged here rather than silently baked in, since it wasn't separately confirmed: cross-stage context that an agent genuinely needs (e.g., the Design Agent needing the approved requirements) is passed forward as **committed files in the target repo**, not as retained agent memory. If a stage needs something that isn't in the repo yet, that's a gap in the artifact chain, not something to patch with persistent agent state.

---

## 2. Orchestration Model

### 2.1 Why GitHub Actions as the orchestrator

GitHub Actions already provides the primitives FORGE's orchestration layer needs:
- Event triggers (`pull_request`, `issues`, `label`, `workflow_dispatch`, `push`)
- A place to run bounded, ephemeral compute (the Claude Agent SDK calls)
- Native state surfaces (labels, issue/PR state, GitHub Environments with required reviewers)
- An audit trail for free (every workflow run is logged, every approval is recorded with who and when — satisfying NFR 4.1, Traceability & Auditability)

Using GitHub Actions as the orchestrator (rather than building a separate service) means the "deterministic orchestration" claim in Document 0 is enforced by GitHub itself, not by a custom system FORGE would need to maintain and trust separately.

### 2.2 The stage → workflow mapping

Each pipeline stage is one (or a small number of) GitHub Actions workflow(s), triggered by a specific event, that:
1. Checks the triggering event is valid for the current state (guard clause — e.g., don't run the Design stage workflow unless the `requirements-approved` label is present).
2. Assembles the inputs that stage's agent needs from the repo.
3. Invokes the relevant Claude Agent SDK call as a bounded job.
4. Commits the agent's output artifacts to the branch, or opens/updates a PR.
5. Applies the label/state transition that signals the stage is complete and a gate is now open, or opens the GitHub Environment approval that *is* the gate.
6. Stops. No workflow advances the pipeline past a gate itself — the next workflow only fires when a human produces the triggering event (an approval, a merged PR, an Environment approval).

*Exception — Stage 3 (Implementation):* Step 3 invokes a Managed Agents coordinator agent session rather than a direct Claude Agent SDK call. The coordinator manages Backend, Frontend, and Test Writer subagents in parallel via the Anthropic Managed Agents API (`managed-agents-2026-04-01` beta header). The GitHub Actions workflow starts the agent session and waits for its completion; all parallel subagent orchestration happens within the Managed Agents runtime, not within GitHub Actions.

**Managed Agents billing note:** The Stage 3 Managed Agents coordinator session incurs $0.08/session-hour of active runtime in addition to standard token costs. Track actuals during App 1 and update Document 3 cost summary.

### 2.4 Cross-repo mechanics

Because FORGE's workflows run in the FORGE repo but must create branches, commits, and PRs in the **custom-apps monorepo**, every workflow that touches application code authenticates to the monorepo as a separate step, not an implicit one:
- A **GitHub App installation** (preferred over a personal access token, since it's scoped, revocable, and attributable to "FORGE" rather than an individual's account) is installed on the monorepo with permissions limited to: create branch, push commit, open/update PR, read/write PR comments and check runs.
- Triggering events (PR opened, label applied, review submitted) are received as **webhooks from the monorepo**, not from the FORGE repo — FORGE repo events (like a design PR being approved *within FORGE's own repo*, if that's ever the case) are not the same thing as monorepo events, and the workflows must be explicit about which repo they're listening to versus acting on.
- The tracking issue (§2.3) lives in the **FORGE repo** (it's orchestration metadata, not application code), while the branches/PRs/commits it references live in the **monorepo** — so every tracking issue comment that links to a branch or PR is a cross-repo link.

This cross-repo relationship is the mechanism that makes FORGE genuinely reusable across teams and repos: the same FORGE instance's workflows can, in principle, be pointed at a different target repo by changing the GitHub App installation and a repo-reference config value, without changing the workflows themselves.

### 2.3 State tracking mechanics

State tracking (NFR "reliability of orchestration," and the cross-cutting "state tracking" feature in Document 1 §3.7) is implemented as:

| Mechanism | Used for |
|---|---|
| **Issue labels** (on the tracking issue created at intake) | Current pipeline stage (`stage:requirements`, `stage:design`, `stage:implementation`, etc.) and gate status (`awaiting-approval:requirements`, `approved:requirements`) |
| **Issue state / comments** | Human-readable log of what happened at each stage, linked artifacts, and agent-flagged issues |
| **PR review state** | The Code gate (Document 1 §3.3) — a required reviewer approval on the implementation PR |
| **GitHub Environments with required reviewers** | The Deploy gate (Document 1 §3.6) — the one-click, irreversible approval, using GitHub's native Environment protection rules rather than a custom approval mechanism |
| **PR status checks** | QA and Security gate completion (Document 1 §3.4–3.5) — the QA Agent and Security Agent post results as check runs; a required-check branch protection rule prevents merge until both pass and both reviewers approve |

A single **tracking issue per business request** is created at intake and carries the request through every stage via labels. This is the one artifact that exists for the whole lifecycle of a request; every other artifact (requirements.md, design.md, the feature branch, the PR) is linked back to it, which is what makes the traceability chain in Document 1 §3.7 concrete rather than aspirational.

### 2.4 Guard clauses and idempotency

Because triggers are events (not sequential steps in one script), every workflow must open with a guard clause confirming its precondition label is present before doing anything. This prevents, for example, a stray label edit from re-triggering the Design stage after implementation has already started. Guard clauses are core-layer — teams do not get to loosen them, since NFR 4.2 (Human Control) depends on state transitions being unambiguous.

---

## 3. Agent Topology

All agents are built on the **Claude Agent SDK**, invoked as a scoped, single-purpose call within a GitHub Actions job. None of them run continuously; each is instantiated, given its stage's inputs, produces its stage's outputs, and exits.

| Agent | Invoked by (workflow trigger) | Inputs | Outputs |
|---|---|---|---|
| **Codebase Ingestion Agent** *(enhancement only)* | `workflow_dispatch` when a request is flagged as an enhancement | Monorepo, read-only checkout of the relevant `services/<name>/` folder | `existing-architecture-summary.md` (committed to `monorepo:docs/<request-id>/`) |
| **Intake Agent** | New intake spreadsheet committed/uploaded to the FORGE repo | Completed intake spreadsheet (FORGE repo) | Answered clarifying-question record (posted as FORGE tracking-issue comments) |
| **Requirements Agent** | Clarification round marked complete | Spreadsheet + Q&A record (+ ingestion summary, if enhancement) | `requirements.md` (committed to `monorepo:docs/<request-id>/`), draft ADO work item payloads (not yet created) |
| **Design Agent** | `requirements-approved` label applied (on the FORGE tracking issue) | `requirements.md` (read from monorepo) | `design.md`, `openapi.yaml`, `tasks.md` — committed to `monorepo:docs/<request-id>/` on a `design/<request-id>` branch, PR opened in the monorepo |
| **Implementation Coordinator** | `design-approved` label applied — GitHub Actions workflow starts a Managed Agents coordinator agent session | `design.md`, `openapi.yaml`, `tasks.md` (monorepo); Managed Agents sandbox filesystem | Complete feature branch implementation committed to `feature/<request-id>`; draft PR opened in monorepo |
| **Backend Agent** *(subagent)* | Implementation Coordinator (Managed Agents delegation) | `design.md`, `openapi.yaml`, `tasks.md` on shared sandbox filesystem | .NET backend implementation written to sandbox filesystem |
| **Frontend Agent** *(subagent)* | Implementation Coordinator (parallel with Backend) | `design.md`, `openapi.yaml`, `tasks.md` on shared sandbox filesystem | React/Next.js + TypeScript frontend written to sandbox filesystem |
| **Test Writer Agent** *(subagent)* | Implementation Coordinator (parallel with above) | `design.md`, `tasks.md`, and backend/frontend code on shared sandbox filesystem | Jest and xUnit tests written to sandbox filesystem |
| **QA Agent** | Implementation PR opened/updated (monorepo) | Feature branch, test suite (monorepo) | Test report (PR check run on monorepo PR), bug tickets (ADO) filed on failure |
| **Security Agent** | Implementation PR opened/updated (parallel with QA, monorepo) | Feature branch (monorepo) | Severity-tagged inline PR comments, PR check run (monorepo) |
| **Deploy Agent** | All gates passed + Environment approval granted | Merged `main` branch, monorepo | Container image, staging → production deployment |

Note the pattern: every agent's **workflow definition** lives in the FORGE repo, but every agent's **artifact output** — requirements, design docs, code, tests — lands in the monorepo. The FORGE repo holds orchestration logic and the tracking issue; it never accumulates application state itself. This is what makes the GitHub App installation in §2.4 load-bearing rather than incidental.

Backend, Frontend, and Test Writer agents run as three parallel Managed Agents subagents within a single coordinator agent session, all writing to the same shared sandbox filesystem. The coordinator synthesizes their outputs, performs integration checking natively (no separate job required), then commits the complete implementation to the `feature/<request-id>` branch in the monorepo and opens the draft PR. The GitHub Actions workflow that triggered the coordinator session waits for the session to complete before marking the PR ready for review. (ADR-0010)

---

## 4. Pipeline Stage Mechanics

For each stage: trigger, what the workflow does, and how the gate is enforced.

### 4.1 Stage 0a — Codebase Ingestion *(enhancement workflow only)*
- **Trigger:** Request flagged as an enhancement at intake (checkbox/field in the intake spreadsheet).
- **Mechanics:** Workflow checks out the target repository read-only, invokes the Codebase Ingestion Agent, commits `existing-architecture-summary.md` to a scratch location referenced by the tracking issue.
- **Gate:** None — feeds directly into Requirements, per Document 1 §3.0a.

### 4.2 Stage 0b — Intake & Clarification
- **Trigger:** BA uploads the completed intake spreadsheet (via a repo path or issue attachment convention — finalized in the Excel Intake Template, Document 8).
- **Mechanics:** Intake Agent reads the spreadsheet, posts 5–7 clarifying questions as issue comments, BA replies in-thread, one follow-up round max.
- **Gate:** None — Requirements Agent proceeds once the Q&A round is marked complete (BA applies a `clarification-complete` label or replies with a defined keyword — exact mechanism is a team-layer notification detail).

### 4.3 Stage 1 — Requirements
- **Trigger:** `clarification-complete` label.
- **Mechanics:** Requirements Agent produces `requirements.md` and draft ADO work item payloads (Epic/Feature/User Story bodies), posted for review — **not created in ADO yet**.
- **Gate:** A named human reviews the draft and applies `requirements-approved`. Only on that label does a workflow call the ADO API to actually create the Epics/Features/User Stories (§5). This is what makes "nothing is created speculatively" (Document 1 §3.1) literal rather than a design intention.

### 4.4 Stage 2 — Spec & Design
- **Trigger:** `requirements-approved` (and successful ADO item creation).
- **Mechanics:** Design Agent produces `design.md`, `openapi.yaml`, `tasks.md` on a `design/<request-id>` branch, opens a design PR.
- **Gate:** Technical Approver reviews and approves the design PR; merge applies `design-approved`.

### 4.5 Stage 3 — Implementation
- **Trigger:** `design-approved`.
- **Mechanics:** The Stage 3 GitHub Actions workflow starts a Managed Agents coordinator agent session. The coordinator declares Backend, Frontend, and Test Writer as specialist subagents. The three subagents run in parallel on the coordinator's shared sandbox filesystem — each with its own scoped system prompt and tools, but sharing the same file system and vault credentials. The coordinator synthesizes their outputs, performs integration checking natively, flags any known issues as pre-annotated PR review comments, commits the complete implementation to `feature/<request-id>` in the monorepo, and opens a draft PR. The coordinator then closes the agent session. The GitHub Actions workflow monitors the session event stream and marks the run complete when the session terminates. Claude Console provides a per-subagent audit trail for the Stage 3 run in addition to GitHub's workflow run log.

  **Billing:** $0.08/session-hour of active Managed Agents runtime in addition to standard token costs. Track actuals during App 1.
- **Gate:** Technical Approver reviews the diff and approves.

### 4.6 Stage 4 — QA
- **Trigger:** Implementation PR opened or updated.
- **Mechanics:** QA Agent runs the test suite, posts a pass/fail/skip report as a PR check run, files ADO bug tickets for failures, linked back to the User Story.
- **Loop-back:** If failures require code changes, the tracking issue returns to `stage:implementation` (label change) without re-running Requirements or Design — this is the one stage transition that can move backward, and it's still label-driven, not agent-decided.
- **Gate:** QA Reviewer sign-off (required PR reviewer approval).

### 4.7 Stage 5 — Security
- **Trigger:** Implementation PR opened or updated (parallel with QA).
- **Mechanics:** Security Agent runs SAST, secrets detection, OWASP checks; posts severity-tagged inline PR comments; any Critical finding sets a failing check run that blocks merge automatically, independent of human action.
- **Gate:** Security Reviewer sign-off (required PR reviewer approval), regardless of finding severity mix — even an all-clear scan needs an explicit human approval, per NFR 4.3.

### 4.8 Stage 6 — Deploy
- **Trigger:** PR merged to `main` with both QA and Security checks passed and both reviewers' approvals recorded.
- **Mechanics:** Deploy Agent containerizes the application, pushes through a `staging` GitHub Environment automatically, then requests deployment to a `production` GitHub Environment.
- **Gate:** One-click approval on the `production` Environment. This is the only irreversible action in the pipeline and the only stage with no review after the fact (Document 1 §3.6) — rollback is a redeploy of the previous image tag, not a pipeline stage in itself.

---

## 5. ADO Integration

- **Work item creation timing:** ADO Epics/Features/User Stories are created by a workflow step that fires only on `requirements-approved` — never speculatively, never before human approval (§4.3).
- **Linking:** Each ADO User Story is linked to the GitHub tracking issue via the ADO item's description/URL field and a corresponding comment on the GitHub issue containing the ADO item ID — a two-way pointer, so traceability holds navigating from either system.
- **Bug tickets (QA loop-back):** Filed as ADO Bugs, linked to the parent User Story, tagged with the failing test name and PR link.
- **Exact field mapping** (which ADO fields FORGE populates automatically vs. leaves to the team to fill in) is an open question, carried forward to the **Tool & Licensing Inventory** (Document 3) and **Customization Reference** (Document 7) — not resolved here, per Document 1 §6.

---

## 6. GitHub Repository Structure

FORGE spans **two repositories**, not one: the FORGE orchestration repo (the template repo each team clones, per Document 0) and the existing **custom-apps monorepo** that already houses LAA's microservices. FORGE never holds application source; the monorepo never holds workflows/agent config.

### 6.1 FORGE repo (per-team instance, cloned from the FORGE template)

```
/
├── .github/
│   ├── workflows/           # one workflow file per stage trigger (core layer)
│   └── ISSUE_TEMPLATE/      # tracking issue template (core layer)
├── core/
│   ├── agents/              # Requirements, Design, QA, Security, Deploy agent prompts/config (core layer)
│   └── schemas/             # requirements.md, design.md, openapi.yaml templates (core layer, format locked)
├── team/
│   ├── agents/              # team-specific agent personas/skills (team layer)
│   └── config.yaml          # notification channels, tool allowlist additions, target-repo reference (team layer)
└── tracking/                # one tracking issue per business request; source of truth for pipeline state (§2.3)
```

### 6.2 Custom-apps monorepo (existing platform, target of FORGE's changes)

```
/
├── services/
│   ├── <microservice-a>/    # existing microservice — enhancement work lands here
│   ├── <microservice-b>/
│   └── <request-id>/        # new microservice — greenfield work creates a new folder here, not a new repo
├── docs/                    # requirements.md, design.md, tasks.md land here per request, under docs/<request-id>/
└── ...                      # existing monorepo scaffold (shared libs, CI config already in place, etc.)
```

This reframes what "greenfield" means structurally: a new application is a **new folder under `services/`** in the existing monorepo, not a new repository. An enhancement modifies a folder that's already there. Both paths use the same branch/PR mechanics (§6.3) — the only difference is whether `services/<request-id>/` is created fresh or already exists, and whether Stage 0a (Codebase Ingestion) runs first.

### 6.3 Dynamics 365 (future consideration, not v1 scope)

LAA also maintains a separate Dynamics 365 repo. FORGE v1 targets the custom-apps monorepo only — the agent roster (.NET/React-oriented), the design/implementation stages, and the QA/Security tooling are all scoped to that stack. Extending FORGE to D365 is a real future goal, not a rejected one, but it isn't designed here: D365's development model (solutions, plugins, Power Platform tooling) doesn't map cleanly onto the Backend/Frontend/Test Writer agent split, and would need its own agent topology pass. Carried forward as an open item (§10).

### Branching strategy (core layer, locked) — applies within the monorepo
- `main` — always deployable; every merge has passed QA + Security + both human gates.
- `design/<request-id>` — design artifacts, merged after design approval.
- `feature/<request-id>` — implementation branch, scoped to `services/<request-id>/` (new) or the relevant existing service folder (enhancement), merged after code + QA + security gates.
- No direct commits to `main`; all changes arrive via PR, satisfying the audit trail requirement even outside the agent-driven stages.
- FORGE's GitHub App installation (§2.4) creates and pushes to these branches in the monorepo on the agents' behalf; the branches never exist in the FORGE repo itself.

### PR conventions (core layer, locked) — PRs are opened in the monorepo
- PR titles: `[<request-id>] <stage>: <short description>` — keeps traceability visible in the GitHub UI without needing to open the linked issue.
- Every PR body includes a generated traceability block: spreadsheet row reference → ADO User Story link → FORGE tracking issue link (cross-repo link back to the FORGE repo, per §2.4).

---

## 7. Two-Layer Model, Enforced Structurally

Document 1 (NFR 4.5) requires the core/team split to be enforced structurally, not just by convention. This is done by:
- **Directory boundary:** `core/` and `.github/workflows/` are the only paths the template repo's update mechanism touches on a pull-from-upstream. `team/` is never touched by a core update.
- **CODEOWNERS on `core/`:** changes to core-layer paths require the Orchestration Manager (or a core maintainer, once a multi-team governance model exists — Document 4) to approve, even if a team's own developer opens the PR — preventing silent drift of "locked" pieces.
- **Config, not code, for team customization:** team-layer differences (agent persona tone, additional tools, notification channel) live in `team/config.yaml` and `team/agents/`, read by the same core workflows — so pulling a core update never requires touching team files, and a team update never requires touching core files.

---

## 8. Container & Deployment Strategy

- **Containerization:** Docker images built per application, per stage (`staging`, `production`), tagged with the request ID and commit SHA for rollback traceability.
- **Target:** Azure Container Apps, per Document 0/context log — a deliberate migration path from the org's current Azure App Service hosting.
- **Environments:** `staging` (auto-deploy on merge to `main`, no human gate — it's a verification step, not a release) → `production` (GitHub Environment with required reviewer, the Deploy gate itself).
- **Rollback:** Redeploying the prior image tag to the `production` Environment; no separate rollback pipeline stage.
- Specific Container Apps environment setup (scaling rules, revision/slot strategy) remains an open question, carried to Document 3 (Tool & Licensing Inventory) — infra-level detail, not architecture-level.

---

## 9. Traceability Chain, End to End

Concretely, per NFR 4.1:

```
Intake spreadsheet row                                            [FORGE repo]
   → GitHub tracking issue (created at intake)                    [FORGE repo]
      → ADO User Story (created on requirements-approved,
        linked to tracking issue)                                 [ADO, cross-linked to FORGE repo]
         → design/<request-id> branch + PR                        [monorepo, cross-linked to FORGE tracking issue]
            → feature/<request-id> branch + PR                    [monorepo, cross-linked to tracking issue + ADO item]
              (produced by Managed Agents coordinator session; see ADR-0010)
               → merge commit SHA                                 [monorepo]
                  → container image tag (request ID + SHA)        [Azure Container Registry]
                     → production deployment record                [Azure Container Apps Environment approval log]
```

Every arrow above is a link stored in a system already keeping its own audit log (GitHub, ADO, Azure) — FORGE does not need its own audit database to satisfy NFR 4.1. The one thing worth being explicit about: the chain now crosses a repo boundary partway through (FORGE repo → monorepo), so "full traceability" depends on every cross-repo link actually being written both directions — the FORGE tracking issue must reference the monorepo PR URL, and the monorepo PR body must reference the FORGE tracking issue URL (per the PR convention in §6). If either side of that link is skipped, the chain breaks at exactly the point where someone would need it — that's a correctness requirement on the workflows, not just a nice-to-have.

---

## 10. Open Items Carried Forward

- Exact ADO field mapping (§5) — Document 3, Document 7.
- Container Apps environment specifics (scaling, revision strategy) — Document 3.
- Intake spreadsheet upload mechanism (repo path vs. issue attachment) — Document 8.
- Whether the "clarification complete" signal is a label or a keyword reply — team-layer notification detail, addressed in Document 6.
- GitHub App installation and permission scoping for FORGE's cross-repo access into the monorepo (§2.4) — Document 3 (provisioning), Document 6 (Orchestration Manager setup steps).
- Future Dynamics 365 support (§6.3) — not designed here; would need its own agent topology and stage design when prioritized.
- **Managed Agents beta stability:** Monitor for breaking changes to the `managed-agents-2026-04-01` header behaviour during the build phase. If the API changes materially, evaluate impact on Stage 3 and raise as an RFC if the core layer changes are required.

---

## 11. ADR-0010 — Managed Agents for Stage 3

Full text in `core/decisions/0010-managed-agents-implementation-coordinator.md`.

Summary: Stage 3 uses an Anthropic Managed Agents coordinator agent session with three specialist subagents (Backend, Frontend, Test Writer) running in parallel on a shared sandbox filesystem, rather than three independent GitHub Actions parallel jobs. All other stages use stateless Claude Agent SDK calls. ADR-0002 (stateless per stage) remains valid — "stateless" means no cross-stage memory; within-stage coordination is permitted and bounded by the stage window.

Consequences to note during build phase:
- Managed Agents is beta — test stability before committing to production
- Track $0.08/session-hour cost actuals during App 1 and App 2
- Managed Agents failure modes require specific handling (see Orchestration Manager Guide)

---

## 12. Where This Fits

This document defines *how*. The next document — the **Tool & Licensing Inventory** — enumerates every tool named here (GitHub, ADO, Azure Container Apps, Claude Agent SDK, etc.), who provisions each, what's required vs. optional, and cost, so the architecture above is fully provisionable rather than just designed.
