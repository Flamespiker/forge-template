# ADR-0002: Stateless Per-Stage Agent Invocation

**Status:** Accepted
**Date:** 2026-07-23
**RFC:** _(seed ADR — predates RFC process)_

## Context

Each FORGE pipeline stage needs to invoke Claude to do real work
(interpreting an intake spreadsheet, writing requirements, designing an
API, generating code, reviewing test results, and so on). Two models were
available: a long-running agent process that persists across the entire
request and accumulates conversational memory stage-to-stage, or a fresh,
bounded agent invocation per stage that receives exactly the artifacts it
needs and produces exactly the artifacts the next stage needs.

A persistent cross-stage agent would make every run harder to reproduce
(the agent's behavior at Stage 5 would depend on everything that happened
in Stages 1–4 within that same session, not just on the committed
artifacts), harder to reason about in isolation, and harder to retry a
single stage without restarting the whole request. It also doesn't match
how GitHub Actions jobs work — each job already starts from a clean runner
with no memory of prior jobs.

## Decision

Every pipeline stage's agent invocation is stateless. A stage spins up a
fresh, bounded agent call scoped to that stage only, given exactly the
committed artifacts it needs as input (e.g. `requirements.md` for Design),
and produces exactly the artifacts the next stage or human gate needs as
output. No agent process persists across stages, and no agent holds
memory of a prior stage's conversation. Context passes forward **only** as
committed files — markdown, YAML, and code committed to the repo — never
as retained agent state.

This keeps every run reproducible (a stage's output depends only on its
committed inputs, not on session history), keeps each agent's scope bounded
per Document 0's core design pattern, and lets any single stage be
re-invoked independently without needing to replay the whole request.

**Clarified by ADR-0010:** Stage 3 (Implementation) uses a Managed Agents
coordinator session that maintains coordinator-to-subagent state
*within* that one stage's execution window, so the Backend, Frontend, and
Test Writer subagents can coordinate with each other during synthesis.
This does not violate the stateless-per-stage principle — "stateless"
means no memory carries *across* stages. The stage still starts from
committed files (`design.md`, `openapi.yaml`, `tasks.md`) and ends by
committing files (the feature branch implementation); no state from
Stage 3's agent session is available to Stage 4 (QA) or any later stage.

## Consequences

**Positive:**
- Every stage's output is fully explained by its committed inputs — no
  hidden conversational state to account for when debugging unexpected
  agent behavior.
- Any stage can be re-invoked in isolation (starting fresh from its
  committed inputs) without needing to reconstruct or replay prior stages.
- Matches GitHub Actions' own execution model — no special handling needed
  to keep an agent process alive across separate job runs.

**Negative / tradeoffs accepted:**
- An agent has no memory of *why* an earlier stage made a particular
  choice beyond what that stage wrote into its committed artifacts — if a
  human wants Design to account for reasoning the BA gave verbally during
  Requirements clarification, that reasoning must be captured in
  `requirements.md`, not assumed to carry forward implicitly.
- Re-running a stage always starts from the beginning of that stage; there
  is no partial-resume within a stage (this is explicit guidance in the
  Orchestration Manager Guide's failure-handling section).
