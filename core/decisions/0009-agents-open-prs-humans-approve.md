# ADR-0009: Agents Open PRs; Humans Approve and Merge

**Status:** Accepted
**Date:** 2026-07-23
**RFC:** _(seed ADR — predates RFC process)_

## Context

FORGE's Design Agent and Implementation Coordinator both produce real,
committable output (design docs plus API contract; a complete feature
implementation) that needs to land in the monorepo. The question is where
the human review gate sits relative to that landing: should an agent be
allowed to merge its own work once it judges the work complete, or must a
human always be the one who clicks merge, no matter how confident the
agent's own self-assessment is?

Given that FORGE's entire premise is "human approval gates at defined
checkpoints" (Document 0's core pattern) rather than autonomous
deployment, allowing an agent to merge its own PR would undermine the one
property every other design decision in FORGE depends on: that nothing
reaches the next stage, or production, without a human having actually
looked at it.

## Decision

Every agent that produces committable output opens its work as a **draft**
pull request — never merges it, never marks it ready for review on a
human's behalf. Specifically:

- The Design Agent opens a draft PR against `design/<request-id>`
  containing `design.md`, `openapi.yaml`, and `tasks.md`.
- The Implementation Coordinator opens a draft PR against
  `feature/<request-id>` containing the complete implementation.

In both cases, a human (the Technical Approver) must click **Ready for
review** — draft PRs cannot be merged directly in GitHub regardless of
approval state — and then approve and merge the PR themselves. No agent
identity is permitted to merge these PRs under any circumstance, including
a case where the agent's own output looks complete and correct. This is
enforced structurally by branch protection (required reviewers), not left
to agent self-restraint or prompt instruction alone.

## Consequences

**Positive:**
- The no-self-merge property is guaranteed by GitHub's branch protection
  mechanism, not by trusting that an agent will always follow its
  instructions — a prompt-injection or a bug in agent logic cannot cause
  autonomous merging.
- Every piece of code or design that reaches `main` was reviewed and
  explicitly approved by a person, with a full GitHub PR review trail as
  the audit record.
- The draft-PR pattern gives the Technical Approver a natural moment to
  request changes or edit the output directly before it's mergeable at
  all, rather than only being able to approve-or-reject a fait accompli.

**Negative / tradeoffs accepted:**
- Every PR requires an explicit "Ready for review" click before it can
  even be approved — a real extra step in the gate sequence that a fully
  autonomous pipeline would skip. This has occasionally added friction
  when a Technical Approver forgets this step exists, expecting label
  application alone to be sufficient (it is not — merging the PR, not just
  applying a label, is what's required at Gate 2 before `design-approved`
  can be meaningfully applied).
- Branch protection requiring reviewers created a genuine deadlock for
  self-authored ad hoc PRs (a human opening a PR under their own account
  cannot review-approve their own PR either, under standard branch
  protection) — resolved as an accepted manual workaround procedure, not a
  change to this ADR's core rule.
