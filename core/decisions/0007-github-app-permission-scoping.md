# ADR-0007: GitHub App Permission Scoping

**Status:** Accepted
**Date:** 2026-07-23
**RFC:** _(seed ADR — predates RFC process)_

## Context

FORGE's workflows, running in the FORGE repo, need to read and write into
a separate target monorepo (per ADR-0003's two-repo model) — creating
issues, opening PRs, committing files, applying labels. That cross-repo
access needs an authentication mechanism, and that mechanism's blast radius
needs to be as small as possible: FORGE should never have more access to a
team's systems than the minimum its actual pipeline stages require, and a
compromised or misbehaving FORGE workflow should not be able to touch
anything outside the one monorepo it's meant to operate on.

## Decision

FORGE authenticates into the target monorepo via a dedicated GitHub App,
named `forge-pipeline` by convention (the name itself is cosmetic and
team-renameable; the permission set is what matters and is locked):

- **Installation scope:** installed only on the target monorepo, never
  organization-wide. A compromised or buggy workflow cannot reach any
  other repository in the organization through this App's credentials.
- **Permission set (minimum required, no more):**
  - Contents: Read and write
  - Pull requests: Read and write
  - Issues: Read and write
  - Checks: Read and write
  - Metadata: Read (required by GitHub for any App)
- **No inbound webhook.** FORGE's workflows call the GitHub and Anthropic
  APIs directly using a generated token; nothing needs to call back into
  FORGE, so the App's webhook is left inactive.
- **Token lifetime:** every job generates a fresh, short-lived installation
  token (via `actions/create-github-app-token`, currently pinned to `@v3`
  or later, which uses the App's Client ID rather than the older App ID
  input). Tokens expire after one hour and are never stored — no long-lived
  credential exists anywhere in the pipeline for monorepo access.

Any additional permission beyond this list requires an RFC — this is not a
team-layer decision, since expanding the App's permissions changes FORGE's
actual security posture for every team running an instance.

## Consequences

**Positive:**
- The App's blast radius is structurally bounded to one repository and a
  minimum permission set — not just documented as a convention, but
  enforced by GitHub's own App installation model.
- Short-lived, per-job tokens mean there is no long-lived credential to
  leak, rotate on a schedule, or accidentally commit — the only long-lived
  secret is the App's own private key, held once at the FORGE-repo level.
- The permission set maps directly and only to what FORGE's stages
  actually do (open PRs, apply labels, comment, commit files) — no
  speculative permissions "in case a future stage needs them."

**Negative / tradeoffs accepted:**
- A future stage that needs a permission not in this list (e.g. something
  requiring Actions: write, or org-level access) cannot get it without an
  RFC — by design, but it does mean permission expansion isn't a fast path.
- Credential misconfiguration between the two required-secret and
  one-required-variable storage locations (`FORGE_APP_ID`/
  `FORGE_APP_PRIVATE_KEY` as repo secrets, `FORGE_APP_CLIENT_ID` as a repo
  variable) fails silently rather than erroring clearly if a value is
  saved in the wrong place — a real, observed setup pitfall documented in
  the Orchestration Manager Guide's troubleshooting section, not something
  GitHub surfaces on its own.
