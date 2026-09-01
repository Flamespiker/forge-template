# ADR-0006: Azure Container Apps Environment Configuration

**Status:** Accepted
**Date:** 2026-07-23
**RFC:** _(seed ADR — predates RFC process)_

## Context

FORGE's Deploy Agent (Stage 6) needs a concrete, opinionated default for
how staging and production Container Apps environments are shaped —
replica counts, resource allocation, and revision strategy — so a new team
cloning FORGE gets a working, reasonably-costed deployment target without
needing to make every infrastructure decision themselves before their
first run. At the same time, some of these values genuinely vary by
team/app and shouldn't be hardcoded at the core layer.

## Decision

FORGE mandates a **two-environment model**: `forge-staging` and
`forge-production`, always separate, no single-environment deployments.
Within that model:

**Locked (core layer, not team-configurable):**
- Two-environment model itself (staging/production, no third tier)
- Staging auto-deploys with no human gate; production requires a
  GitHub Environment approval with a required reviewer — this is the
  final, irreversible gate and cannot be bypassed
- Single active revision per environment — no blue/green or canary
  deployment at the FORGE platform level
- Rollback mechanism: redeploy the prior image tag; the previous revision
  is retained for 48 hours post-deploy; no other rollback mechanism exists
- Image tagging convention: `<request-id>-<commit-sha>`, used for rollback
  identification

**Flexible (team-configurable within core-defined floor/ceiling values in
`core/container-apps.schema.yaml`, set in `team/config.yaml`):**
- Staging replica count (platform default: min 0, max 2)
- Production replica count (platform default: min 1 — always on — max 5)
- Container resource allocation (platform default: staging 0.25 vCPU /
  0.5 Gi; production 0.5 vCPU / 1.0 Gi)

Changes to these flexible values apply to new pipeline runs; they do not
retroactively change already-running containers.

## Consequences

**Positive:**
- Every team gets a working, sanely-costed staging/production split
  without needing to design their own Container Apps topology first.
- The floor/ceiling schema prevents a team from accidentally configuring
  something pathological (e.g. zero max replicas, or an oversized default
  that burns budget) while still leaving real room for team judgment.
- Production's required-reviewer gate and the 48-hour rollback window give
  every team the same minimum safety net regardless of how much Azure
  experience their Orchestration Manager has.

**Negative / tradeoffs accepted:**
- Teams needing blue/green or canary deployment, a third environment tier,
  or per-service replica/resource overrides beyond the schema's ceiling
  cannot get them without a core-layer RFC.
- Worker-style Container Apps with no ingress and `rules: null` do not
  actually scale to zero despite `min_replicas: 0` in config — only apps
  with real HTTP ingress or an actual KEDA scale rule idle to zero in
  practice. This is a real operational gap between the documented default
  and observed Azure behavior, not a documented exception at design time.
- A byte-identical redeployment (no actual code change) does not provision
  a new Container Apps revision, so teams should not expect a restart or
  availability blip from every Deploy Agent run — this can be surprising
  if a team expects "deploy ran" to always mean "container restarted."
