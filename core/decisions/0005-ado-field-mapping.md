# ADR-0005: Azure DevOps Field Mapping

**Status:** Accepted
**Date:** 2026-07-23
**RFC:** _(seed ADR — predates RFC process)_

## Context

FORGE creates Azure DevOps work items (Epic → Feature → User Story, plus
Bug tickets from failed QA runs) to give every generated request a real,
traceable presence in the team's existing ADO board. Some of the fields on
those work items matter for FORGE's own traceability chain (linking a work
item back to the exact request, PR, and pipeline run that produced it, and
back to the exact test failure that produced a Bug ticket) and must always
be written the same way regardless of team. Other fields are pure team
planning fields (Story Points, Priority, Iteration Path) that FORGE has no
basis to fill in — an agent estimating story points or setting sprint
iteration would be making up a number with no real planning input behind
it.

## Decision

FORGE work item creation is split into two field categories:

**Always written by FORGE (locked, cannot be skipped):**
- Title, Description, Acceptance Criteria (agent-generated content)
- State = Active
- Tags: `forge-managed` + `<request-id>`
- Traceability links (work item ↔ tracking issue ↔ PR)
- For Bug tickets specifically: Steps to Reproduce, Severity (from the
  fixed assertion-failure=Medium / crash-or-exception=High mapping),
  Parent User Story link, PR URL

**Left entirely to the team (fully open, FORGE never writes or validates
these):**
- Story Points, Priority, Iteration Path, Effort, Business Value, and any
  custom organization-specific fields

The work item hierarchy itself (Epic → Feature → User Story) is fixed —
FORGE creates exactly this three-level structure and no alternative
hierarchy is supported. Work items are created only once, triggered by the
`requirements-approved` label — never speculatively at an earlier stage,
and never re-created if requirements are later revised within the same
request.

**Enhancement-specific behavior (added post-launch, see Item #32):** for
an Enhancement request, Features and User Stories are created as children
of the *existing* service's real Epic (looked up from that service's own
`ado-work-items.json`), not a new, disconnected Epic — keeping an
Enhancement's ADO traceability chain attached to the application it's
actually enhancing rather than fragmenting into a parallel backlog. The
Greenfield path (new application) is unaffected and always creates a new
Epic.

## Consequences

**Positive:**
- Every FORGE-created work item is traceable back to its originating
  request and pipeline run without a team needing to establish that
  convention themselves.
- Teams retain full control over planning fields FORGE has no legitimate
  basis to estimate, without needing an RFC to "unlock" them — they were
  never locked in the first place.
- The Enhancement/Epic-linkage behavior keeps a team's ADO backlog
  reflecting real application boundaries rather than accumulating a new,
  disconnected Epic per enhancement.

**Negative / tradeoffs accepted:**
- A team cannot ask FORGE to also populate a planning field it considers
  important (e.g. auto-estimating Story Points from task complexity)
  without an RFC to move that field into the locked/always-written set —
  and doing so would require the Requirements or Design Agent to make a
  planning judgment call it currently has no basis for.
- The default Area Path is team-configurable, but the underlying hierarchy
  shape is not — a team wanting a four-level hierarchy, or Features
  without an Epic parent, is not supported without a core-layer RFC.
