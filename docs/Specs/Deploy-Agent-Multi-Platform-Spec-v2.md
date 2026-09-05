# FORGE Deploy Agent — Multi-Platform Support Technical Spec v2

**Status:** Spec only — not yet built. Hand-off to Claude Code CLI for implementation.
**Author:** Claude.ai
**Date:** 2026-09-05
**Supersedes:** v1 (same day) — broadened from a two-platform (Azure / Vercel+Supabase) spec
informed by a single build, to a genuinely platform-agnostic design covering Azure, AWS, Google
Cloud, and Vercel+Supabase, so Design can choose based on user input across the real field of
options rather than the two platforms one app happened to need.
**Layer:** Core (per `04_Governance-v2.md` — deployment standards are explicitly core-layer).
Should go through the RFC process before merging to `core/`, same note as v1.
**Scope note:** this spec is FORGE-engine-level and belongs in this project going forward.
Fiddy5's own deployment specifics (its data model, its Vercel+Supabase build) live in Fiddy5's
own project once that's stood up post-migration — not duplicated here.

---

## 1. Problem statement

"Deployment target" is not a decision anywhere in FORGE today — it's a hardcoded assumption.
`02-forge-architecture-document-v4.md` §8 names Azure Container Apps as *the* target; Deploy
Agent has exactly one code path. This worked as long as the target platform could run any
Dockerized language, so Design never had to think about where the app would end up.

That assumption breaks the moment platform choice becomes real, because not every platform is
container-shaped, and the ones that aren't have real constraints on what stack is even viable.
**Stack and platform stop being independent decisions** once more than one platform shape is on
the table.

## 2. Platform shapes, not vendors

The thing that actually determines stack compatibility is *shape*, not which company runs it.
Four target platforms, classified by shape:

| Platform | Shape | Stack constraint |
|---|---|---|
| **Azure Container Apps** (existing) | Container | Any Dockerized language |
| **Google Cloud Run** | Container | Any Dockerized language — same contract as Azure Container Apps, different provisioning API |
| **AWS — ECS/Fargate** | Container | Any Dockerized language |
| **AWS — Lambda** | Serverless function | Node.js, Python, Go, Java, Ruby, and — notably, as of .NET 10 (Jan 2026) — **.NET**, both as a managed runtime and a container base image |
| **Vercel** (frontend) + **Supabase** (backend) | BaaS / serverless | Node.js, Python, Go, Ruby, PHP, Rust, Deno, Bash (Vercel); custom logic on Supabase limited to Deno/TS Edge Functions |

**Key asymmetry worth designing around:** AWS is the only platform here that spans both a
container shape and a serverless shape *with real .NET support in both* — meaning an AWS adapter
could let an existing .NET app go serverless without the kind of backend rewrite Fiddy5's
Vercel+Supabase move required. This matters for Design-gate validation (§4): "the requested
stack doesn't fit the platform" is a real per-platform-per-shape check, not a single yes/no.

## 3. Core design decision: Deploy Platform Adapters

Introduce a `DeployPlatform` adapter abstraction. Each adapter declares:

- **Shape** (container / serverless-function / BaaS) and supported stacks within it.
- **What it provisions** — compute, database, secrets/env-var wiring, and how.
- **How Greenfield vs. Enhancement differ** for that platform (§5).

Four adapters to build toward: `azure-container-apps` (existing, refactored into this shape
rather than left as the implicit default), `google-cloud-run` (closest architectural peer to
Azure — same contract, lowest-risk second adapter to build), `aws` (spans both shapes — likely
two sub-adapters, `aws-ecs-fargate` and `aws-lambda`, rather than one, given the shape split),
and `vercel-supabase` (BaaS, built from the Fiddy5 reference implementation once that project
exists).

## 4. Where platform gets chosen

**At Intake, not at Deploy** — Deploy is too late; by then Design has already committed the app
to a stack. Proposed: a `Target Platform` field on the Intake spreadsheet template
(`Intake_Template.xlsx`), **Greenfield requests only**. Design Agent reads it and must confirm
the requirements-driven stack choice fits that platform's declared shape and stack list — a
mismatch is flagged back to the OM at the Design gate, not silently built anyway (same
"strict rejection over silent fallback" principle as `EnhancementServiceNotFoundError`).

**Enhancement requests do not get a platform choice** — inherited from whatever the existing
service already runs on. Redirecting an existing service to a different platform is a replatform
project, out of scope for a normal enhancement request (FORGE has no formal replatform workflow
today — noted, not solved, here).

## 5. Greenfield vs. Enhancement, per adapter

| | Greenfield | Enhancement |
|---|---|---|
| **Platform selection** | Chosen at Intake, validated at Design gate against the platform's shape/stack list | Inherited from the existing service — not selectable |
| **Provisioning** | Adapter provisions everything from scratch (compute, DB, secrets) | Adapter updates the existing live resource in place — no new parallel infrastructure (matches existing Enhancement behavior in `06_Orchestration_v10.md`) |
| **Stack compatibility check** | Design Agent validates against the adapter's declared shape | N/A — stack is already whatever the existing service runs |
| **Failure mode if incompatible** | Flagged to OM at Design gate; request does not proceed to Implementation | N/A |

## 6. Deploy Agent's generalized responsibility

Given `request.platform` (resolved at Intake/Design), dispatch to the matching adapter. Database
provisioning ("make sure the declared database exists before the app tries to start" — the real
gap behind Item #58) belongs in the adapter *contract*, not as a platform-specific patch: every
adapter implements its own version of it — Azure: Postgres Flexible Server; Google Cloud Run:
Cloud SQL; AWS: RDS (container shape) or DynamoDB/Aurora Serverless (Lambda shape, depending on
access pattern); Vercel+Supabase: the Supabase project's own Postgres instance.

## 7. A gap this surfaces, not solved here

Security Agent's current model (SAST, dependency scanning, secrets scanning) assumes application
code is the entire security surface. A BaaS-shaped adapter moves real authorization logic into
database-level policies (e.g. Supabase Row Level Security) that none of the current tooling
reviews. Flagged as a follow-on item — likely a manual gate before any automation — not addressed
in this spec.

## 8. Rollout plan

1. **Phase 1:** `google-cloud-run` — lowest-risk second adapter, same container contract as
   Azure, proves the adapter interface without also having to solve a shape change.
2. **Phase 2:** `vercel-supabase` — first BaaS-shaped adapter, built from Fiddy5's real
   implementation once that migration lands in its own project.
3. **Phase 3:** `aws-ecs-fargate` / `aws-lambda` — two sub-adapters given AWS spans both shapes;
   `aws-lambda` is the one to point future .NET-serverless requests at, per §2's asymmetry.
4. **Phase 4:** `Target Platform` Intake field + Design-gate validation, once at least two
   genuinely different-shaped adapters exist to meaningfully choose between.
5. **Phase 5:** retrofit `azure-container-apps` fully into the adapter interface as a true peer.

## 9. Open questions for Mike

- Module layout (`core/agents/deploy_platforms/`) — no strong reason to prefer a structure yet.
- Whether `aws` really wants two sub-adapters or one adapter with an internal shape switch —
  recommend two, since their provisioning code and DB story don't overlap much.
- Timing of the Intake field (§8 Phase 4) — recommend waiting until Phase 3 lands, so the field
  is choosing between a real field of options rather than two.
