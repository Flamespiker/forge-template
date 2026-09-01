# ADR-0010: Anthropic Managed Agents for Stage 3 (Implementation)

**Status:** Accepted
**Date:** 2026-07-22 (added after the initial nine seed ADRs were drafted,
following the Managed Agents architectural review)

## Context

Stage 3 (Implementation) is structurally different from every other FORGE
stage: it needs three specialists — Backend, Frontend, and Test Writer —
producing an integrated, working implementation together, not one agent
producing one artifact in isolation. The original design ran these three
as independent parallel GitHub Actions jobs, each generating its portion of
the code separately, with a **separate integration-check job** afterward
to catch contract mismatches between what Backend and Frontend each
produced independently (e.g. a shared type or endpoint contract drifting
between the two, since neither agent could see the other's in-progress
work).

This design meant integration problems were only ever caught *after* both
sides had already finished — the correction loop was: generate separately,
integration-check afterward, loop back if mismatched. Anthropic's Managed
Agents API (public beta, `managed-agents-2026-04-01` header) offered an
alternative: a single coordinator agent session that runs specialist
subagents in parallel *on a shared sandbox filesystem*, so subagents can
see and react to each other's output as they go, and the coordinator
itself can perform integration synthesis natively as part of finishing the
session, rather than as a separate downstream job.

## Decision

Stage 3 uses an Anthropic Managed Agents coordinator agent session, not
three independent GitHub Actions parallel jobs. The coordinator declares
Backend, Frontend, and Test Writer as specialist subagents, which run in
parallel on the coordinator's shared sandbox filesystem — each with its own
scoped system prompt and tools, sharing the same filesystem and vault
credentials. The coordinator:

1. Synthesizes the three subagents' output as they work
2. Performs integration checking **natively**, as part of synthesis — the
   standalone integration-check job from the original design is eliminated
   entirely; this cannot be bypassed or replaced with a separate check
3. Flags any known issues as pre-annotated PR review comments
4. Commits the complete implementation to `feature/<request-id>` in the
   monorepo
5. Opens a draft PR (per ADR-0009 — the coordinator never merges it)
6. Closes the agent session

The GitHub Actions workflow for Stage 3 starts the session and waits for it
to complete, rather than running the actual parallel work itself — all
subagent orchestration happens inside the Managed Agents runtime, not
inside GitHub Actions. Model tier is set at the core layer: Opus for the
Implementation Coordinator, Sonnet for every other agent in the pipeline —
changing any agent's model tier requires an RFC given the cost and
capability implications.

**Clarifies ADR-0002:** the coordinator's within-session state across its
subagents is bounded to the Stage 3 execution window and does not
constitute cross-stage memory — see ADR-0002's own "Clarified by ADR-0010"
note.

## Consequences

**Positive:**
- Integration problems between Backend and Frontend are caught natively
  during synthesis, not discovered after the fact by a separate downstream
  job — eliminating a whole class of "generate separately, fail
  integration, loop back" cycles the original design was prone to.
- A per-subagent audit trail is available in the Claude Console alongside
  the GitHub Actions log, giving much richer visibility into which
  subagent did what than a single combined job log would.
- Removes an entire job (the standalone integration-check step) from the
  pipeline's critical path.

**Negative / tradeoffs accepted:**
- Managed Agents is a public beta as of this writing — the
  `managed-agents-2026-04-01` beta header may change between beta
  versions, and Stage 3 failures appearing across multiple unrelated
  requests are a signal to check for a platform-level beta change first,
  not assume a one-off bug (tracked as a standing open item, not fully
  resolved by this ADR).
- Stage 3's cost and duration are genuinely less predictable than any
  other stage — a real, unpredictable-duration Managed Agents session
  rather than a bounded single-turn call, which motivated building a
  dedicated pre-flight cost estimate and cost-approval gate later (see
  Item #34) rather than treating Stage 3 like every other stage's flat,
  predictable cost.
- A Stage 3 job can report failure via its own GitHub Actions
  completion-detection window while the underlying Managed Agents session
  is still alive and legitimately working — re-running the coordinator in
  this state risks starting a second, fully duplicate billed session on
  top of one that may finish on its own. This required building dedicated
  session-recovery tooling (`--recover-session`) rather than a simple
  retry-on-failure pattern.
