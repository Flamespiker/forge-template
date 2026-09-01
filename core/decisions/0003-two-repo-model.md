# ADR-0003: Two-Repo Model

**Status:** Accepted
**Date:** 2026-07-23
**RFC:** _(seed ADR — predates RFC process)_

## Context

FORGE needs somewhere to keep its own orchestration machinery (agent
prompts, workflow definitions, core/team configuration) and somewhere to
put the actual application code it generates. Those two things could live
in the same repository, or in two separate repositories with FORGE
operating on the second one across a repo boundary.

Keeping them together would mean every team's application codebase carries
FORGE's own orchestration internals alongside real product code, makes it
harder to update FORGE's core layer independently of any one team's app
history, and blurs the line between "platform code" (versioned, owned by
the Core Platform Owner, updated via RFC) and "application code" (owned by
the team, evolving on its own schedule).

## Decision

FORGE uses a two-repo model:

- **The FORGE repo** (`forge-template` upstream; each team clones their own
  copy, e.g. `forge-<team-name>`) holds orchestration machinery only:
  agent prompts (`core/agents/`), workflow definitions
  (`.github/workflows/`), ADRs (`core/decisions/`), and team-layer
  configuration (`team/`). It never holds application source code.
- **The target monorepo** (the team's actual application codebase — for
  the FORGE build/demo phase, `forge-demo-apps`) is where FORGE writes
  generated requirements, design docs, and application code
  (`docs/<request-id>/`, `services/<service-name>/`). FORGE operates on
  this repo as an external actor, not as a repo it owns outright.

Cross-repo access from the FORGE repo's workflows into the target monorepo
is authenticated via a dedicated GitHub App (`forge-pipeline`, see
ADR-0007) installed on the monorepo only, generating short-lived
installation tokens per job — not a personal access token or a repo owned
directly by FORGE's own identity.

## Consequences

**Positive:**
- FORGE's own platform code and any one team's application code evolve on
  independent timelines and independent version histories — a core-layer
  update doesn't touch application git history, and vice versa.
- The Core Platform Owner can update `forge-template` and have teams pull
  updates into their own FORGE repo clone without that update touching the
  monorepo at all.
- The cross-repo boundary makes the "FORGE never holds application source"
  and "FORGE never has more access than it needs" properties structurally
  true, not just a documented convention — enforced by which repo the App
  is installed on.

**Negative / tradeoffs accepted:**
- Every pipeline stage that needs to read or write monorepo content
  (requirements, design docs, code, ADO traceability links) must do so
  across an authenticated cross-repo boundary rather than a same-repo file
  operation — adding the GitHub App token-generation step to every job
  that touches the monorepo.
- Orchestration state that needs to live with the monorepo's own history
  (e.g. `requirements.md`) but isn't real application code needed its own
  home — the `pipeline-state` branch — since `main`'s branch protection is
  scoped to gate application-code merges, not orchestration-state commits.
- Two repositories means two places to check when debugging a request:
  the tracking issue lives in the FORGE repo, but the actual PRs and
  committed artifacts live in the monorepo.
