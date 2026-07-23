# FORGE Governance Model

**Full-SDLC Orchestration with Review Gates for Engineers**

---

## Purpose

FORGE is a two-layer platform. The core layer is shared infrastructure — changes there affect every team running a FORGE instance. The team layer is each team's own — changes there are that team's business. Good governance means being clear about which layer something belongs to, and having a lightweight, consistent process for changing the one that matters to everyone.

This document defines:

- How core-layer changes are proposed, reviewed, and decided
- The format for recording those decisions
- Who has authority at each step
- How the team layer is governed differently, and why

---

## The Two Layers, Revisited

### Core Layer

The core layer contains everything FORGE mandates across all teams:

- Security gates (SAST, secrets detection, dependency scanning) and their blocking behaviour
- Azure DevOps work item structure — Epics → Features → User Stories — and the fields FORGE writes
- Naming conventions for branches, Docker images, work item tags, and tracking issues
- Branching strategy in the monorepo (`main` ← `feature/<request-id>` ← `design/<request-id>`)
- Deployment standards — what constitutes staging and production, and how rollback works
- The Excel intake spreadsheet template — field names, the overview/context tab, required vs. optional columns
- The GitHub App permission set (`forge-pipeline`)
- The list of approved tools and services teams may use in the team layer

Core-layer files live in `core/` in the FORGE template repo. They are not modified by teams. A team that finds a legitimate reason to change something in `core/` proposes it through the RFC process below — they do not fork and patch.

### Team Layer

The team layer contains what each team adapts for their own context:

- Tech stack specifics, within the approved list (CSS framework, component libraries, ORM, state management)
- Agent personas and tone
- Notification channels and escalation contacts
- Linting rulesets (the requirement that linting runs is core; which rules applies is team layer)
- Azure Container Apps defaults (vCPU, memory, replica counts — within defined floor/ceiling values)
- ADO configuration (area path defaults, iteration path, story point conventions)

Team-layer files live in `team/` in each team's cloned FORGE repo instance. The Orchestration Manager owns and maintains them. No RFC is required to change them.

---

## Decision Authority

Three roles participate in governance decisions:

**Orchestration Managers** are the practitioners. They run FORGE instances day-to-day, encounter real friction, and identify what should change. Any Orchestration Manager may open an RFC.

**The Core Platform Owner** is the person (currently Mike Faulkner) responsible for the core layer's long-term integrity. They have final approval authority on all core-layer changes. This role may be shared or transferred as the team grows, but there is always exactly one person in the seat at a time.

**Technical Reviewers** are Orchestration Managers or senior developers who have agreed to participate in RFC review. They are not a standing committee — they are named on individual RFCs based on who has relevant context. The Core Platform Owner assigns at least one Technical Reviewer to each RFC.

For decisions that affect only the team layer, the Orchestration Manager for that team has full authority. No RFC needed, no external sign-off.

---

## When an RFC Is Required

An RFC is required for any proposed change to:

- The contents of `core/` in the FORGE template repo
- The list of approved tools and services in the team layer
- This governance document itself
- The Excel intake spreadsheet template
- The GitHub App (`forge-pipeline`) permission set

An RFC is **not** required for:

- Changes to `team/` within a team's own instance
- Bug fixes to core-layer code that restore documented behaviour without changing it (these go directly as PRs; the Core Platform Owner reviews)
- Documentation corrections that don't change policy

When in doubt, open an RFC. The cost of an unnecessary RFC is low. The cost of a undocumented core-layer change is high.

---

## The RFC Process

### Step 1 — Open a GitHub Discussion

The proposer opens a GitHub Discussion in the FORGE template repo under the **RFC** category. The Discussion title format is:

```
RFC: <short imperative description of the change>
```

The Discussion body uses the RFC template (see below). No pull request yet — the Discussion is for reaching agreement on whether and how to make the change, not for reviewing code.

### Step 2 — Assign a Reviewer

The Core Platform Owner reads the Discussion within **3 business days** and either:

- Assigns a Technical Reviewer and sets a review-by date (no longer than **10 business days** from opening), or
- Closes the RFC with a brief explanation if the proposal is out of scope or clearly duplicates an existing decision

### Step 3 — Review Period

The assigned Technical Reviewer(s) and any other interested parties comment on the Discussion. The proposer responds to questions and updates the RFC body in place (clearly marked as edits, not new top-level comments).

The goal of the review period is to surface: whether the proposal solves the stated problem, what risks or side effects it introduces, and whether there are simpler alternatives. It is not a vote.

### Step 4 — Decision

At the end of the review period, the Core Platform Owner makes one of three calls:

- **Accepted** — the proposal moves to implementation
- **Accepted with modifications** — the proposal is approved in a revised form; the final scope is recorded in the Discussion
- **Declined** — the proposal is not adopted; the reason is recorded in the Discussion so it can be referenced if the question comes up again

The Core Platform Owner posts the decision as a comment, closes the Discussion, and applies the `rfc-accepted`, `rfc-accepted-modified`, or `rfc-declined` label.

Accepted RFCs do not expire. If an accepted RFC is not implemented within **30 business days**, the Core Platform Owner either confirms it is still on the roadmap or reopens the Discussion to revisit the decision.

### Step 5 — Implementation and ADR

The proposer (or another contributor, agreed in the Discussion) opens a pull request in the FORGE template repo against `main`. The PR:

- Cites the RFC Discussion number in the PR description
- Includes an ADR (see format below) in `core/decisions/`
- Passes all CI checks

The Core Platform Owner reviews and merges. No other approver is required, though the Core Platform Owner may request a second review from a Technical Reviewer for high-risk changes.

---

## RFC Template

```markdown
## Problem

<!-- What is broken, missing, or creating friction? Be specific. -->

## Proposed Change

<!-- What exactly would change in the core layer, and where does it live? -->

## Motivation

<!-- Why is this the right change? Why now? -->

## Alternatives Considered

<!-- What else could solve this problem? Why is this approach preferred? -->

## Impact

<!-- Which teams and pipeline stages are affected?
     What would existing FORGE instances need to do after this change is merged? -->

## Open Questions

<!-- What is not yet resolved, and who needs to answer it? -->
```

A useful RFC is specific. "Make security gates more flexible" is not an RFC — "Allow teams to configure Semgrep rulesets in the team layer while keeping the gate itself in the core layer" is.

---

## Architecture Decision Records (ADRs)

Every accepted RFC that results in a merged change produces one ADR. ADRs are stored in `core/decisions/` in the FORGE template repo, named by sequence number and a short slug:

```
core/decisions/0001-security-tooling-defaults.md
core/decisions/0002-ado-field-mapping.md
```

The ADR format is:

```markdown
# ADR-NNNN: <Title>

**Status:** Accepted  
**Date:** YYYY-MM-DD  
**RFC:** <GitHub Discussion link>

## Context

<!-- What situation or constraint made this decision necessary? -->

## Decision

<!-- What was decided, stated plainly. -->

## Consequences

<!-- What becomes easier, harder, or different as a result?
     Include known trade-offs and accepted limitations. -->
```

ADRs are **append-only**. If a later decision supersedes an earlier one, the later ADR notes the supersession — the earlier one is not edited or removed. This preserves the history of why things were done the way they were.

ADRs are written for the Orchestration Manager who will inherit this codebase two years from now and needs to understand why the rules are the way they are — not for the person who already knows.

---

## Core Layer Updates to Existing Instances

When the core layer changes in the FORGE template repo, existing team instances need to pull in the update. The update process is:

1. The merged change is tagged with a semantic version bump on the FORGE template repo (`v1.1.0`, `v1.2.0`, etc.)
2. The release notes list every changed file in `core/` and describe what teams need to do — usually a `git pull upstream main` and a review of any conflicts with team-layer config
3. Orchestration Managers are responsible for applying the update to their instance within the timeframe stated in the release notes (typically **30 days** for non-security changes, **10 days** for security gate changes)

The Core Platform Owner does not merge changes on behalf of teams. Teams own their instances.

Breaking changes to the core layer — changes that require teams to take manual action beyond a clean merge — go through the RFC process with `breaking-change` noted explicitly, and the release notes include a migration checklist.

---

## Team-Layer Governance

The team layer has no formal process. The Orchestration Manager makes decisions, may consult their team, and records significant choices in `team/decisions/` in their own instance if they want a record. No required format, no external review.

The one constraint: team-layer changes cannot exceed the boundaries the core layer sets. A team cannot remove a security gate. A team cannot add a tool that isn't on the approved list. A team cannot change ADO work item structure. If a team needs those boundaries to move, they open an RFC.

---

## Where Governance Discussions Live

| Type | Location |
|------|----------|
| RFC proposals and review | GitHub Discussions (FORGE template repo), category: RFC |
| ADRs | `core/decisions/` in the FORGE template repo |
| Team-layer decisions (optional) | `team/decisions/` in the team's instance |
| Open questions for future RFCs | This context document (updated each session) |

Governance does not happen in Slack, email threads, or meeting notes that can't be found later. If a decision was made but not recorded in one of the locations above, it didn't happen — open an RFC or write an ADR to make it real.

---

## Seeded ADRs

The decisions made during FORGE's design phase (Documents 1–3 and this document) are recorded retroactively as ADRs before the first team instance is cloned. The seed ADR list, to be written into `core/decisions/` at initial repo setup:

| ADR | Decision |
|-----|----------|
| ADR-0001 | Event-driven orchestration via GitHub Actions (no separate orchestrator service) |
| ADR-0002 | Stateless per-stage agent invocation; context passes forward as committed files |
| ADR-0003 | Two-repo model — FORGE repo separate from target monorepo; cross-repo auth via GitHub App |
| ADR-0004 | Security tooling defaults — Semgrep Community, Gitleaks, OWASP Dependency-Check |
| ADR-0005 | ADO field mapping — FORGE writes traceability/accuracy fields; team owns planning fields |
| ADR-0006 | Azure Container Apps environment specifics — scale-to-zero staging, min-1 production |
| ADR-0007 | GitHub App permission scoping — forge-pipeline, monorepo-only install, short-lived tokens |
| ADR-0008 | TypeScript mandated for all frontend code; Jest for frontend tests; xUnit for .NET |
| ADR-0009 | Agents open PRs; humans approve — no agent merges its own PR |
| ADR-0010 | Anthropic Managed Agents adopted for Stage 3 (Implementation) coordination — a coordinator agent runs Backend, Frontend, and Test Writer subagents in parallel on a shared sandbox filesystem, replacing the original three-parallel-GitHub-Actions-jobs design; clarifies that ADR-0002's "stateless per stage" principle permits bounded within-stage coordinator state |

Each of these will be written as a full ADR in `core/decisions/` during the initial repo setup phase. ADR-0010 was added after the initial nine were drafted, following the Managed Agents architectural review (2026-07-22) — see Document 2 §11 for the full decision record and consequences.

---

## A Note on Lightweight Intent

This governance model is designed to be proportionate. FORGE is a platform for one organization's development teams, not an open-source project with hundreds of contributors. The RFC process is meant to create a record and invite feedback — not to introduce bureaucracy for its own sake. A well-written RFC with one thoughtful reviewer and a clear decision is better than a committee meeting with no written outcome.

The model should be revisited (via an RFC) if it proves too slow for the pace of change, or too light for the complexity of decisions being made.
