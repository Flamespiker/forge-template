# FORGE Deploy Agent — Multi-Platform Support Technical Spec v1

**Status:** Spec only — not yet built. Hand-off to Claude Code CLI for implementation.
**Author:** Claude.ai
**Date:** 2026-09-05
**Layer:** Core (per `04_Governance-v2.md` — "deployment standards... what constitutes staging
and production" is explicitly core-layer). Formally this should go through the RFC process
before merging to `core/`, even though Mike is both requester and Core Platform Owner — noted so
CLAUDE.md's changelog can reference an RFC if he wants the paper trail.
**Informed by:** today's Fiddy5 → Vercel + Supabase spec (companion document), used here as the
first real second data point rather than designing this abstraction from Azure alone.

---

## 1. Problem statement

Today, "deployment target" is not a decision anywhere in FORGE — it's a hardcoded assumption.
`02-forge-architecture-document-v4.md` §8 names Azure Container Apps as *the* target; the Deploy
Agent has exactly one code path. This worked because Azure Container Apps is stack-agnostic (any
Dockerized language runs there), so Design never had to think about where the app would end up.

Fiddy5's replatform broke that assumption in a way worth generalizing from: Vercel + Supabase is
not just "a different container host" — it's a different *shape* of platform (function/BaaS,
not container), with its own constraints on what stack is even viable (see the companion spec's
§1 for the concrete Vercel-runtime-support finding). Any future platform choice that isn't
"arbitrary container" runs into the same problem: **stack and platform stop being independent
decisions.**

## 2. Core design decision: Deploy Platform Adapters

Introduce a `DeployPlatform` adapter abstraction. Each adapter declares:

- **Supported stack shapes** — e.g. `azure-container-apps` accepts any Dockerized language;
  `vercel-supabase` accepts a Node/TS (or static) frontend plus Postgres, with custom logic
  limited to Deno/TS Edge Functions.
- **What it provisions** — compute, database, secrets/env-var wiring — and how. Azure:
  Container App revision + (per Item #58's fix, see §4) a Postgres Flexible Server if declared
  and missing. Vercel+Supabase: a Vercel project + a Supabase project (schema applied via
  migration files, RLS policies applied, Auth provider configured).
- **How Greenfield vs. Enhancement differ** for that platform (see §5).

Two adapters to start: `azure-container-apps` (the existing path, refactored into this shape
rather than left as the implicit default) and `vercel-supabase` (new, built from today's Fiddy5
spec as the reference implementation — deliberately not over-abstracted from a single example
before a second one exists to check the interface against).

## 3. Where platform gets chosen

**Decision: at Intake, not at Deploy.** Deploy is too late — by the time Deploy runs, Design has
already committed the app to a stack, and if that stack doesn't fit the chosen platform, you get
exactly the situation Fiddy5 was in (a stack built without the target platform in mind).

Proposed: a new `Target Platform` field on the Intake spreadsheet template (`Intake_Template.xlsx`),
alongside the other overview-tab fields, for **Greenfield requests only**. Design Agent reads it
and must confirm the requirements-driven stack choice is compatible with that platform's declared
supported shapes — a mismatch is flagged back to the OM at the Design gate, not silently built
anyway (same "strict rejection over silent fallback" principle already established elsewhere in
FORGE, e.g. `EnhancementServiceNotFoundError`).

**Enhancement requests do not get a platform choice.** The existing service's platform is fixed —
inherited from whatever it already runs on. An enhancement to an existing Azure Container
Apps .NET service is not an invitation to redirect it to Vercel; that would be a replatform
project (see the companion spec's §9 — FORGE has no formal workflow for that today, and this spec
doesn't invent one either).

## 4. Deploy Agent's responsibility, generalized

Deploy Agent's job becomes: given `request.platform` (resolved at Intake/Design, not decided at
Deploy time), dispatch to the matching adapter. Item #58's fix — "provision an app-level database
if declared and missing" — belongs in the adapter *contract*, not as an Azure-specific patch:
every adapter must implement its own version of "make sure the declared database exists before
the app tries to start," not just Azure's.

## 5. Greenfield vs. Enhancement, per adapter

| | Greenfield | Enhancement |
|---|---|---|
| **Platform selection** | Chosen at Intake, validated at Design gate | Inherited from the existing service — not selectable |
| **Provisioning** | Adapter provisions everything from scratch (compute, DB, secrets) | Adapter updates the existing live resource in place — no new parallel infrastructure (matches the existing "Enhancement updates in place" behavior in `06_Orchestration_v10.md`) |
| **Stack compatibility check** | Design Agent validates against the adapter's supported shapes | Not applicable — stack is already whatever the existing service runs |
| **Failure mode if incompatible** | Flagged back to OM at Design gate, request does not proceed to Implementation | N/A |

## 6. A gap this surfaces, not solved here

The Security Agent's current model (SAST via Semgrep, dependency scanning via Dependabot,
secrets scanning via Gitleaks) assumes application code is the entire security surface. A
BaaS-shaped adapter like `vercel-supabase` moves a real chunk of authorization logic into Row
Level Security policies — SQL, not application code — which none of the current Security Agent's
tooling reviews at all. This is a genuine gap, not addressed in this spec: flagged as a follow-on
item (an "RLS policy review" check class), likely starting as a manual Mike-reviews-it gate
before any automation, same pattern as Google Cloud Console OAuth setup being a manual step today.

## 7. Rollout plan

1. **Phase 1 (this cycle):** build the `vercel-supabase` adapter using today's Fiddy5 spec as the
   concrete reference — dogfooding before formalizing the interface.
2. **Phase 2:** add the `Target Platform` Intake field + Design-gate validation logic.
3. **Phase 3:** retrofit `azure-container-apps` into the same adapter interface, so it's a true
   peer rather than "the real path plus one bolt-on" — today it's implicit and everywhere;
   this phase makes it explicit and swappable.

## 8. Open questions for Mike (not decided in this spec)

- Module layout: `core/agents/deploy_platforms/{azure_container_apps,vercel_supabase}.py`, or a
  different structure? No strong reason to prefer one yet — CLI's call during Phase 1 unless
  Mike wants to weigh in.
- Does `Intake_Template.xlsx` get the new `Target Platform` column now (Phase 2 work) or wait
  until Phase 1's adapter is proven out? Recommend waiting — no sense adding an intake field
  before there's a second adapter for it to meaningfully choose between.
- Should RLS review start as a manual gate (§6) immediately when `vercel-supabase` ships, or is
  that a later hardening pass? Recommend manual-from-day-one, same as every other new security
  surface FORGE has added incrementally.
