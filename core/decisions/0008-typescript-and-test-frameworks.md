[//]: # (Seed ADR stub — full content to be written before v1.0.0 release.)

# ADR-0008: TypeScript Mandated; Jest for Frontend; xUnit for .NET

**Status:** Accepted
**Date:** 2026-07-23
**RFC:** _(seed ADR — predates RFC process)_

## Context

FORGE's Backend, Frontend, and Test Writer agents generate application code and tests autonomously, with QA validation running downstream in `qa_agent.py`. This requires deterministic, unambiguous conventions at the core layer for three reasons specific to an agent-orchestrated pipeline (not just general best practice):

1. **Agent prompts need a single, unambiguous target.** Leaving frontend language (TypeScript vs. plain JavaScript) or test framework (Jest vs. Vitest vs. Mocha; xUnit vs. NUnit vs. MSTest) as a team-layer choice would mean every agent invocation needs to read team config and adapt — increasing prompt complexity and the chance of agent drift or inconsistent output across requests.
2. **QA Agent parsing is format-specific, not AI-judged.** `qa_agent.py` parses xUnit's TRX report format and Jest's JSON test-result format directly, with a fixed deterministic severity-classification mapping (not an LLM judgment call, per Document 3's explicit "not AI judgment" language for this field). Supporting multiple test frameworks would mean building and maintaining multiple parsers for a decision that has no meaningful team-specific tradeoff.
3. **Type safety reduces a real, observed failure class.** Plain JavaScript frontend code removes a category of errors (prop-type mismatches, contract drift between Backend/Frontend agents) that TypeScript catches at build time — directly relevant given Backend and Frontend are separate subagents in Stage 3, coordinating only via the coordinator's integration check, not a shared type system unless TypeScript is used.

React/Next.js (frontend) and .NET (backend) were already locked as core-layer framework choices (see Document 7, Technology Stack table) — this ADR extends that same locked status to the language and test framework layer sitting directly on top of those frameworks.

## Decision

The following are mandated at the **core layer** (not team-configurable, per Document 7's Locked/Flexible/Fully Open categorization):

- **TypeScript is mandated for all React/Next.js frontend code.** Plain JavaScript is not accepted. Baked into the Frontend Agent and Test Writer Agent system prompts.
- **Jest is mandated as the frontend test framework.** The Test Writer Agent writes Jest tests exclusively. Other frameworks (e.g., Vitest) are not permitted substitutions, even if functionally similar — this was tested in practice during `REQ-2026-02`'s Stage 3 run, where a Test Writer subagent's unrequested Vitest deviation was caught and corrected by QA before merge.
- **xUnit is mandated as the backend test framework** for all .NET code. No other .NET test framework (NUnit, MSTest) is accepted.

These three mandates are enforced at two points in the pipeline: (1) directly in the relevant agent system prompts (Frontend Agent, Backend Agent, Test Writer Agent), and (2) indirectly via `qa_agent.py`'s hardcoded TRX/Jest parsing, which cannot process any other format — a non-compliant test suite will fail QA by producing no valid report, not by a soft warning.

Linting is a separate, related but distinct decision: linting itself is locked as a CI gate (cannot be disabled), but the specific ruleset (ESLint/Prettier config, StyleCop rules) remains team-configurable via `team/stack-preferences.yaml`, per Document 7.

## Consequences

**Positive:**
- Agent prompts and QA parsing logic stay simple, deterministic, and don't need to branch on team configuration for language/framework/test-runner choice.
- Type-level contract mismatches between independently-generated Backend and Frontend code are caught at build/compile time rather than surfacing only at integration or runtime — Document 2's cross-service wiring gaps (found chats 34/39) were data/config issues, not type issues, but the type-safety net has already caught real bugs in practice (e.g. the `Navigation.tsx` `aria-hidden` typing mismatch, chat 34).
- QA Agent's fixed TRX/Jest parsing and deterministic severity classification (Document 3's "not AI judgment" requirement) remain tractable to build and maintain, since only one format per language needs support.

**Negative / tradeoffs accepted:**
- Teams with existing JavaScript-only codebases, or a strong existing preference for Vitest, NUnit, or MSTest, cannot use those choices within FORGE without an RFC to change a core-layer mandate (Document 4's governance process) — this is a real constraint on team flexibility, accepted deliberately in exchange for pipeline simplicity and agent-prompt determinism.
- A future change to any of these three mandates (e.g. adopting Vitest project-wide) requires updating Frontend/Backend/Test Writer Agent prompts *and* rewriting `qa_agent.py`'s parsing logic simultaneously — these are now coupled decisions, not independently reversible.
- This mandate does not extend to E2E testing frameworks (e.g. Playwright), which remain outside `qa_agent.py`'s scope (confirmed chat 27 — Playwright specs found in a real checkout were legitimate, traceable output, not scope creep, but are not executed by the current QA Agent).

---
