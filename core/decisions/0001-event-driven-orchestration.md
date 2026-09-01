# ADR-0001: Event-Driven Orchestration via GitHub Actions

**Status:** Accepted
**Date:** 2026-07-23
**RFC:** _(seed ADR — predates RFC process)_

## Context

FORGE needed an orchestration layer to carry a request through seven
pipeline stages (Intake, Requirements, Design, Implementation, QA, Security,
Deploy — later joined by Stage 0a, Codebase Ingestion, for enhancements)
with a human approval gate between each one. Two shapes were available:
build a separate, long-running orchestrator service that tracks pipeline
state and decides when to invoke each agent, or drive the whole pipeline
from the event primitives GitHub already provides (label changes, PR
events, issue events, GitHub Environment approvals).

A standalone orchestrator would need its own state store, its own
scheduling/retry logic, and its own audit trail for who approved what and
when — all things GitHub already does natively for a project already living
in GitHub. It would also be a new system FORGE would need to build, secure,
and maintain, on top of everything else the platform already depends on
GitHub for (repo hosting, PR review, branch protection).

## Decision

GitHub Actions workflows, triggered by label changes, PR events, and issue
events, **are** FORGE's orchestration layer. There is no separate
long-running orchestrator process or service. Each pipeline stage is one
(or a small number of) GitHub Actions workflow(s) that:

1. Triggers on a specific, narrow event (e.g. the `requirements-approved`
   label being applied)
2. Runs a guard clause checking the precondition label(s) are actually
   present, to prevent a stray event from re-triggering a stage out of order
3. Invokes the stage's agent as a bounded job — a single-turn `anthropic`
   Messages API call for six of the seven stages (ADR-0011), or the Stage 3
   Managed Agents coordinator session (ADR-0010) — given exactly the
   artifacts it needs
4. Commits the stage's output artifacts and/or posts a summary comment
5. Exits — nothing persists between invocations except what was committed

Pipeline state itself lives entirely in native GitHub primitives: labels
encode gate status, PR review state encodes approval, and GitHub
Environment approvals gate production deployment. No bespoke state
database or external state service exists anywhere in FORGE.

## Consequences

**Positive:**
- The "deterministic orchestration" property FORGE promises is enforced by
  GitHub itself, not by a custom system FORGE would need to build and trust
  separately.
- Every stage transition is visible and auditable in the same place
  (the tracking issue, PR, and Actions log) without a separate dashboard.
- No orchestrator process to keep running, patch, or scale — GitHub Actions
  runners are provisioned on demand per job.

**Negative / tradeoffs accepted:**
- Pipeline logic is expressed as a set of guard clauses spread across
  `.github/workflows/*.yml` rather than centralized in one orchestrator
  codebase — understanding the full pipeline state machine means reading
  several workflow files together, not one place.
- FORGE is tied to GitHub Actions' event model and its constraints (e.g.
  job timeouts, label-event semantics). A future move to a different CI/CD
  or orchestration platform would require rebuilding this layer, not just
  porting agent code.
- Guard-clause correctness is critical and has been a recurring source of
  real bugs when a stage needed new state (e.g. Enhancement-target
  awareness, the Deploy Agent's `pr-merged` trigger requirement) that the
  original guard clause didn't anticipate.
