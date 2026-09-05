# FORGE — Session Context v89

**Session date:** 2026-09-05 (Claude.ai + Claude Code CLI)
**Carries forward from:** v88, unchanged except where noted below.

---

## Scoping decision this session — read this first

**Going forward, this project's context docs track FORGE's own engine-level history —
architecture decisions, agent behavior, items affecting every future app — not any single
app's product narrative.** Fiddy5 surfaced this session's real engine-level work (Items #59,
#60, the Enhancement-detection fix, the multi-platform spec) purely because it's been the only
real dogfooding case so far. Once Fiddy5's replatform is fully verified end-to-end, it gets its
own Claude.ai project, and its own ongoing tracking (backlog, product decisions, deploy
specifics) moves there — not carried forward here in the detail v87/v88 used. This doc
deliberately keeps Fiddy5 detail lighter than prior versions for that reason.

**The same split applies to every future app FORGE builds**, not just Fiddy5: build each app's
Greenfield request (Intake through Deploy) inside this project, since that's genuinely
engine-level work; once an app reaches a stable first Deploy and moves into ongoing life, it
gets its own project. This is now written up properly in `docs/06_Orchestration_v11.md`, not
just a working assumption.

---

## What changed this session

### Deploy Agent Multi-Platform Spec — authored, v2 shipped

Real deliverable of this session: `Deploy-Agent-Multi-Platform-Spec-v2.md`. Generalizes Deploy
from its current Azure-Container-Apps-only path into a `DeployPlatform` adapter abstraction,
classified by **shape** (container / serverless-function / BaaS) rather than by vendor —
Azure Container Apps and Google Cloud Run are peer container-shaped adapters; AWS spans both a
container shape (ECS/Fargate) and, notably, a serverless shape with genuine .NET support
(AWS Lambda, confirmed supporting .NET 10 as of Jan 2026 — the one platform among the four
surveyed that doesn't force a backend rewrite for an existing .NET app going serverless);
Vercel+Supabase is BaaS-shaped, Node/TS + Deno-only.

Key design decisions: platform choice happens at **Intake**, not Deploy (Deploy is too late —
by then Design has already committed a stack); Design Agent validates the chosen stack against
the platform's declared shape, flagging incompatibility back to the OM rather than silently
building anyway (same "strict rejection over silent fallback" principle as
`EnhancementServiceNotFoundError`); Enhancement requests inherit their platform, never choose
one. Five-phase rollout: Google Cloud Run first (lowest-risk, same container contract as
Azure) → Vercel+Supabase (once Fiddy5's real build exists as reference) → AWS (two
sub-adapters) → Intake field + Design-gate validation → full Azure retrofit into the adapter
interface. This is core-layer per `04_Governance-v2.md`; should go through the RFC process
before merging to `core/`, even though Mike is both requester and Core Platform Owner.

**A real gap this surfaced, not solved:** Security Agent's SAST/dependency/secrets model
assumes app code is the entire security surface. A BaaS-shaped adapter moves real authorization
logic into database-level policies (Row Level Security) that nothing currently reviews.
Flagged as a follow-on item — likely starting as a manual gate, same pattern as Google Cloud
Console OAuth setup being manual today.

### Instance Scope principle — added to Governance

New subsection in `04_Governance-v2.md`'s Team Layer discussion, "Instance Scope: One FORGE
Clone, One Context" — codifies that each FORGE clone (one repo, one `team/config.yaml`) is
scoped to exactly one identity (one GitHub account/org, one set of cloud accounts), so a
personal-use instance and a future work-use instance are two separate clones, not two
configurations of one instance. This resolves cleanly out of the existing platform-swap
precedent (`FORGE_GITHUB_OWNER`/`FORGE_TARGET_REPO` already tie an instance to one identity) —
nothing new needed in the adapter design itself; account context is resolved once, at the
instance level, never per-app or per-adapter.

### Fiddy5 → Vercel + Supabase replatform — built, merged, not yet live-verified end-to-end

Full replatform spec'd, built, and merged (PR #3, commit `e922260` on `mike-digital-platform`
main). Backend architecture: Supabase Postgres (all 14 real EF Core entities, not the spec's
original 5-entity illustrative sketch) + Row Level Security (including a since-restored
admin-can-view-household-investments policy, matching the real EF Core app's actual behavior
rather than the spec's incorrect "strictly private" assumption) + two Edge Functions
(household creation, holding-price refresh) + Supabase Auth replacing NextAuth entirely.
Frontend: Next.js on Vercel, `apiClient.ts` swapped for direct `supabase-js` calls.

**Real gaps the build's own investigation caught that the spec missed:** four business-logic
pieces (retirement projection, `.ics` generation, dashboard aggregation, recurring-occurrence
generation) the spec never accounted for — three ported to client-side TS, one to a Postgres
function/trigger/`pg_cron` job; a second background service (`PriceFetchService.cs`, Yahoo
Finance price refresh) with zero spec mention; `accept-invitation` turned out not to exist as
a user action at all (real behavior is auto-accept-by-email-match, built as a trigger instead
of the spec's proposed dead-code Edge Function); and the original `apiClient.ts` had no path to
create a household at all — the exact bug Item #56 was blocked on, which would have silently
reproduced in the new stack if not caught.

**Real build issues found and fixed, not glossed over:** a Windows-local `next build` crash
initially attributed to a Node-version mismatch turned out to be a red herring — the real cause
was `@supabase/ssr`'s `createBrowserClient()` throwing synchronously on `undefined` env vars at
module-load time during prerendering, only exposed once QA ran with real content (not the
empty-spreadsheet Greenfield path). Fixed with placeholder env vars — but this landed in
`04-qa.yml` itself (core, shared), not scoped to Fiddy5, meaning the shared QA workflow now has
Supabase-specific variable names hardcoded into it. Logged as **Item #59**, not fixed: QA needs
an app-declared manifest of required build-time env vars, same shape as the multi-platform
spec's adapter-declares-requirements pattern, rather than accumulating one app's variable names
after another as new apps are built.

**Deploy Agent bypassed for this merge, deliberately, not silently:** Deploy Agent has no
adapter for Vercel+Supabase yet (exactly the gap Phase 2 of the multi-platform spec names).
Rather than let `06-deploy.yml` fire its only path (Azure) against a merge that has nothing to
do with Azure, Deploy Agent was temporarily disabled, the PR merged, then re-enabled — with the
traceability gap this creates written up explicitly as a comment on `forge-template#18` rather
than left as a silent hole in the usual tracking-issue → merge → deployment-record chain.

**Not yet done — genuinely blocking, not deferred by choice:** Google OAuth wiring into
Supabase Auth's provider settings (Mike's action item), and the real end-to-end sign-in →
household creation → dashboard smoke test. **Azure Container Apps
(`req-2026-01-frontend`/`-backend`) remain live, deliberately, pending that test** — the
decommission step from the original spec is explicitly gated on real verification, not on the
merge landing.

### Enhancement-detection bug found and fixed across all 5 pipeline stages

Real, generalizable bug, unrelated to Fiddy5's platform specifically: `download_issue_attachment()`
unconditionally re-downloaded the tracking issue's intake spreadsheet, hard-failing on any
issue that never went through `00-intake.yml` — like the ad hoc `forge-template#18`. Fixed with
an `--optional` flag, applied correctly across `02-design.yml`/`03-implementation.yml`/
`04-qa.yml`/`05-security.yml`/`06-deploy.yml`, still hard-failing (correctly) on
`00-intake.yml`/`01-requirements.yml` where a missing spreadsheet is a real bug. Live-verified
for QA, Security, and Implementation. **02-design.yml and 06-deploy.yml's versions are
syntax/diff-validated against the proven pattern but deliberately not live-fired** — 02-design.yml
because `create_ado_items.py` has no idempotency protection (Item #51's exact duplicate-ADO-
hierarchy problem would recur) and would trigger a real costed Design Agent run for an
already-built app; 06-deploy.yml because dispatching it post-merge risks a real Azure deploy
attempt against a repo with nothing left for Deploy Agent to correctly deploy. Both logged as
deferred live-verification, same shape as Item #55's Test 2 — left open deliberately, not
solved artificially.

Confirmed exhaustively (32 failed runs across all 5 workflows checked, not sampled) that no
other issue or PR was ever affected by this bug, and nothing in the existing backlog already
tracked it under a different number — genuinely new. Logged as **Item #61** (no CLAUDE.md
entry existed prior — the fix had only lived in commit messages until this session's wrap-up):
covers the full fix family, live-verified for 03-implementation.yml/04-qa.yml/05-security.yml,
with 02-design.yml's version explicitly noted as deferred-live-verification, same cost/risk
shape as Item #55's Test 2.

### Branch protection gap found — Item #60

`mike-digital-platform`'s `main` has zero branch protection at all (confirmed via a 404 during
today's merge, not assumed) — no required status checks, no required reviewers. Not
consequential while Deploy Agent had no real wiring to this repo; now that it does, this is a
real gap. Logged, not fixed — a literal "required status check" rule needs a small wiring
change first, since `qa-approved`/`security-approved` are tracking-issue labels today, not
GitHub PR status checks.

---

## Open items — updated status

- **Items #55/#56/#57/#58 (the original Azure-specific bugs)** — superseded by the Vercel/
  Supabase replatform, per the CLAUDE.md pointer entry. Not resolved via fix; moot once the
  .NET backend is retired. Full Fiddy5-specific narrative now lives in `mike-digital-platform`'s
  own archive files, not carried here in detail.
- **Item #59 (new)** — `04-qa.yml` has Supabase-specific env vars hardcoded into a shared, core
  file. Open. Real fix needs an app-declared build-env-var manifest.
- **Item #60 (new)** — no branch protection on `mike-digital-platform` main. Open, newly
  consequential now that Deploy Agent has live wiring there.
- **Item #61 (new)** — Enhancement-detection fix. Closed/live-verified for
  03-implementation.yml/04-qa.yml/05-security.yml. 02-design.yml applied but deliberately
  unverified live (deferred, same shape as Item #55's Test 2). 06-deploy.yml applied,
  syntax/diff-validated only, not tracked under #61 — see the Fiddy5-replatform entry instead,
  since it's specifically tied to the Deploy Agent bypass this session.
- **Item #44, #41, #38, #39, #40, #42, #7, #11** — unchanged from v88, no movement this session.
- **Documentation audit (stale docs, missing Tooling doc, orphan cleanup)** — unchanged from
  v88, still pending.

---

## Azure infrastructure

No new resources touched this session. `req-2026-01-frontend`/`req-2026-01-backend` remain
live, untouched, gated on the real sign-in smoke test — this is deliberate, not an oversight
(the spec's own decommission step is explicitly sequenced after verification, not after the
merge). A fresh end-of-session idle-check was requested of CLI as this doc was being written;
carry forward whatever that confirms rather than assuming continuity from v88's last check.

Platform-level resources (`mdp-rg`, `mdp-con-stage`/`mdp-con-prod`, `mdpacr`, `mdp-kv`) — no
change, remain provisioned for future Azure-targeted apps regardless of Fiddy5's platform.

---

## On the horizon

- **Google OAuth wiring into Supabase Auth** (Mike action item) → real end-to-end sign-in smoke
  test → **only then** the Azure Container Apps decommission.
- **Backlog consolidation, v9 → v10** — the gate v88 set (holding until #57 resolved) is now
  satisfied; real v9 content requested from CLI to write this properly rather than from a
  secondhand summary. Should cover #43 through #60, the Enhancement-detection fix, and the
  deferred-live-verification caveat.
- **Fiddy5's own Claude.ai project** — stood up once the replatform is fully verified
  end-to-end, not before. Seed it with a proper context doc (product spec, chosen adapter,
  current open items) rather than starting cold.
- **Deploy-Agent-Multi-Platform-Spec Phase 1** — Google Cloud Run adapter, next real build
  candidate once picked up.
- **RLS policy review gap** (§7 of the multi-platform spec) — no automation exists yet for
  reviewing database-level authorization logic; likely starts as a manual gate.
- **Item #60** — branch protection rule for `mike-digital-platform` main, needs the
  labels-to-status-checks wiring question resolved first.
- **Documentation audit remediation** — unchanged from v88, still batched for a future
  documentation-focused session.
