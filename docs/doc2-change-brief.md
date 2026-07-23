# Document 2 — Architecture Document Change Brief
# For: Managed Agents ADR-0010 Update
# Use this in the dedicated Document 2 update chat

---

## What This Brief Is

This is not a replacement for Document 2. It is a precise specification of every change
required in Document 2 as a result of ADR-0010 (Managed Agents for Stage 3). The next
chat should open Document 2, apply these changes section by section, and produce the
updated file. No other changes should be made in that chat.

---

## Section 2.2 — Stage → Workflow Mapping

**Current text (excerpt):**
> each stage is one (or a small number of) GitHub Actions workflow(s), triggered by a
> specific event, that:
> 3. Invokes the relevant Claude Agent SDK call as a bounded job.

**Change:**
Add a note after step 3:
> *Exception — Stage 3 (Implementation): Step 3 invokes a Managed Agents coordinator
> agent session rather than a direct Claude Agent SDK call. The coordinator manages
> Backend, Frontend, and Test Writer subagents in parallel via the Anthropic Managed
> Agents API (`managed-agents-2026-04-01` beta header). The GitHub Actions workflow
> starts the agent session and waits for its completion; all parallel subagent
> orchestration happens within the Managed Agents runtime, not within GitHub Actions.*

Also add a new note at the end of Section 2.2:
> **Managed Agents billing note:** The Stage 3 Managed Agents coordinator session
> incurs $0.08/session-hour of active runtime in addition to standard token costs.
> Track actuals during App 1 and update Document 3 cost summary.

---

## Section 2.3 — Stateless Agent Invocation (ADR-0002 clarification)

**Current text:**
> Each stage's agent invocation is stateless. Every stage spins up a fresh Claude Agent
> SDK call scoped to that stage, given exactly the artifacts it needs as input, and
> producing exactly the artifacts the next stage (or the human gate) needs as output.
> No agent process persists across stages or holds cross-stage memory.

**Change:**
Add a clarifying paragraph after this block:

> *ADR-0002 clarification (per ADR-0010):* "Stateless" means no cross-stage memory.
> Within Stage 3, the Managed Agents coordinator session maintains coordinator-to-subagent
> state during execution — this is bounded inside the stage window. The stage still starts
> from committed files (design.md, openapi.yaml, tasks.md) and ends by committing files
> (the feature branch implementation). No state from Stage 3's agent session is available
> to any subsequent stage. The stateless-per-stage principle is not violated; it is
> clarified to account for within-stage coordination.

---

## Section 3 — Agent Topology Table

**Current Implementation row:**
| **Backend Agent** | `design-approved` label applied | `design.md`, `openapi.yaml`, `tasks.md` (monorepo) | Backend implementation (.NET) on `feature/<request-id>` branch |
| **Frontend Agent** | `design-approved` label applied (parallel with Backend) | ... | Frontend implementation on same feature branch |
| **Test Writer Agent** | `design-approved` label applied (parallel with above) | ... | Unit/integration tests on same feature branch |

**Replace these three rows with four rows:**

| Agent | Invoked by | Inputs | Outputs |
|---|---|---|---|
| **Implementation Coordinator** | `design-approved` label applied — GitHub Actions workflow starts a Managed Agents coordinator agent session | `design.md`, `openapi.yaml`, `tasks.md` (monorepo); Managed Agents sandbox filesystem | Complete feature branch implementation committed to `feature/<request-id>`; draft PR opened in monorepo |
| **Backend Agent** *(subagent)* | Implementation Coordinator (Managed Agents delegation) | `design.md`, `openapi.yaml`, `tasks.md` on shared sandbox filesystem | .NET backend implementation written to sandbox filesystem |
| **Frontend Agent** *(subagent)* | Implementation Coordinator (parallel with Backend) | `design.md`, `openapi.yaml`, `tasks.md` on shared sandbox filesystem | React/Next.js + TypeScript frontend written to sandbox filesystem |
| **Test Writer Agent** *(subagent)* | Implementation Coordinator (parallel with above) | `design.md`, `tasks.md`, and backend/frontend code on shared sandbox filesystem | Jest and xUnit tests written to sandbox filesystem |

**Also update the note block below the table:**

Remove the current note about "Backend, Frontend, and Test Writer agents run as three parallel jobs in the same workflow, all committing to the same feature branch in the monorepo — this is the 'implements the backend, frontend, and tests in parallel' behavior from Document 0. A short integration-check job runs after all three complete..."

Replace with:

> Backend, Frontend, and Test Writer agents run as three parallel Managed Agents subagents
> within a single coordinator agent session, all writing to the same shared sandbox
> filesystem. The coordinator synthesizes their outputs, performs integration checking
> natively (no separate job required), then commits the complete implementation to the
> `feature/<request-id>` branch in the monorepo and opens the draft PR. The GitHub
> Actions workflow that triggered the coordinator session waits for the session to
> complete before marking the PR ready for review. (ADR-0010)

---

## Section 4.5 — Stage 3: Implementation

**Current text:**
> **Trigger:** `design-approved`.
> **Mechanics:** Backend, Frontend, Test Writer agents run in parallel on
> `feature/<request-id>`, open a draft PR, agents post pre-flagged known issues as PR
> review comments before marking the PR ready for review.
> **Gate:** Technical Approver reviews the diff and approves.

**Replace Mechanics paragraph with:**

> **Mechanics:** The Stage 3 GitHub Actions workflow starts a Managed Agents coordinator
> agent session. The coordinator declares Backend, Frontend, and Test Writer as specialist
> subagents. The three subagents run in parallel on the coordinator's shared sandbox
> filesystem — each with its own scoped system prompt and tools, but sharing the same
> file system and vault credentials. The coordinator synthesizes their outputs, performs
> integration checking natively, flags any known issues as pre-annotated PR review
> comments, commits the complete implementation to `feature/<request-id>` in the monorepo,
> and opens a draft PR. The coordinator then closes the agent session. The GitHub Actions
> workflow monitors the session event stream and marks the run complete when the session
> terminates. Claude Console provides a per-subagent audit trail for the Stage 3 run in
> addition to GitHub's workflow run log.
>
> **Billing:** $0.08/session-hour of active Managed Agents runtime in addition to standard
> token costs. Track actuals during App 1.

**Gate line is unchanged:** Technical Approver reviews the diff and approves.

---

## Section 9 — Traceability Chain

No change to the traceability chain itself. Add a parenthetical to the
`feature/<request-id> branch + PR` line:

> → feature/<request-id> branch + PR *(produced by Managed Agents coordinator session; see ADR-0010)* [monorepo]

---

## Section 10 — Open Items

Add one new item:
> - **Managed Agents beta stability:** Monitor for breaking changes to the
>   `managed-agents-2026-04-01` header behaviour during the build phase. If the API
>   changes materially, evaluate impact on Stage 3 and raise as an RFC if the core
>   layer changes are required.

---

## New Section to Add — Section 11: ADR-0010 Reference

Add a new section at the end of the document (before the current §11 "Where This Fits"):

```
## 11. ADR-0010 — Managed Agents for Stage 3

Full text in `core/decisions/0010-managed-agents-implementation-coordinator.md`.

Summary: Stage 3 uses an Anthropic Managed Agents coordinator agent session with three
specialist subagents (Backend, Frontend, Test Writer) running in parallel on a shared
sandbox filesystem, rather than three independent GitHub Actions parallel jobs. All other
stages use stateless Claude Agent SDK calls. ADR-0002 (stateless per stage) remains valid —
"stateless" means no cross-stage memory; within-stage coordination is permitted and bounded
by the stage window.

Consequences to note during build phase:
- Managed Agents is beta — test stability before committing to production
- Track $0.08/session-hour cost actuals during App 1 and App 2
- Managed Agents failure modes require specific handling (see Orchestration Manager Guide)
```

Renumber the existing "Where This Fits" section to §12.

---

## Instructions for the Document 2 Update Chat

1. Open this brief and the current Document 2 (02-forge-architecture-document.md)
2. Apply each change above section by section
3. Do not change anything not listed in this brief
4. Produce the updated full document as 02-forge-architecture-document-v2.md
5. Append a session note to the context document confirming Document 2 is updated
