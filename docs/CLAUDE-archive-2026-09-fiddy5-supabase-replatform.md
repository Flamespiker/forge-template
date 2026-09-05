# Fiddy5 — Vercel + Supabase replatform (2026-09-05)

Full narrative for the CLAUDE.md pointer under "Fiddy5 replatform (Vercel +
Supabase) — supersedes Items #55/#56/#57/#58" — kept here per this doc series'
"short pointer + dated archive entry" convention (see CLAUDE.md's
Documentation Ownership section). Fiddy5's own ongoing tracking moves to its
own Claude project once stood up; this entry is the handoff snapshot, not a
living doc.

## Addendum, same day — QA's frontend build failure (Item #59)

PR #3 (`feature/google-oauth-setup` → `main` on `mike-digital-platform`,
still open as a draft) triggered a real `04-qa.yml` run against
`forge-template#18`, which genuinely failed — the frontend production build
crashed on 9 routes (everything importing `lib/apiClient.ts`) with `Cannot
read properties of null (reading 'useContext')` during Next's static
prerendering.

First hypothesis, tried and disproven live: `@supabase/supabase-js@2.115.0`
declares `engines.node: >=22.0.0`, and `04-qa.yml`/`05-security.yml` both
pinned Node 20 — bumped both to 22 (commits `76b53bf`, `ffc74bf`), re-ran QA
for real, **still failed identically**. Not the cause.

Real root cause, found by reproducing the exact call directly (`node -e`
against the installed `@supabase/ssr` package): `createBrowserClient()`
throws synchronously — `"Your project's URL and API key are required..."` —
when called with `undefined` args. `lib/apiClient.ts` calls it at module top
level (`const supabase = createClient();`), which executes during Next's
static prerendering for every route that imports it — exactly the 9 routes
that failed. Confirmed via plain `grep`, not inference, that neither
`04-qa.yml`'s job env nor `qa_agent.py`'s `_run_shell()` (no `env=` override,
inherits the job's environment as-is) ever set
`NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` anywhere. Fixed
(commit `1c79686`) by adding both as literal placeholder strings
(`https://placeholder.supabase.co` / `placeholder`) to `04-qa.yml`'s job-level
`env:` block — invented values, not read from any credentials file or other
source (no real Supabase credentials existed anywhere in this session at any
point) — matching the pattern `verify-frontend-build.yml` already used
successfully. Re-verified live: real `qa-approved` label applied, backend
91/91, frontend build clean (run
`https://github.com/Flamespiker/forge-template/actions/runs/33983338153`).

This is a real, narrow gap in the *shared* QA pipeline, not a Fiddy5-local
fix — see Item #59 in CLAUDE.md's Open Items for the forward-looking note
(an app-declared build-time-env-vars manifest, same shape as the
multi-platform Deploy Agent spec's adapter-declares-requirements pattern, is
the likely eventual fix — not built here).

## Source

`docs/Fiddy5-Vercel-Supabase-Deploy-Spec-v1.md` (Claude.ai, 2026-09-05),
implemented in full by Claude Code CLI the same day against the local
`mike-digital-platform` clone at `C:\Users\mikef\projects\mike-digital-platform`,
branch `feature/google-oauth-setup`.

## Why

Fiddy5 had no working deployment on Azure (Item #57: frontend 404s on every
API call; Item #58: backend never started, no database ever provisioned).
Rather than fix both on Container Apps, Mike chose Vercel + Supabase — the
Postgres/RLS/Edge Functions model directly resolves #58 without FORGE's Deploy
Agent needing to provision anything itself (see the sibling
`docs/Specs/Deploy-Agent-Multi-Platform-Spec-v2.md` for that engine-level
gap — not duplicated here). Vercel Functions have no .NET runtime, so this is
a genuine backend architecture change, not a lift-and-shift.

## Investigation corrections against the spec (per instruction #1 — investigate before building)

The spec's own §3 header called its table list "a first pass... CLI should
verify against the real EF Core model" — it undersold the real scope
considerably:

1. **14 real entities, not 5.** The real `AppDbContext.cs` has Users,
   Households, HouseholdMembers, HouseholdInvitations, BudgetCategories,
   Transactions, RecurringTemplates, InvestmentAccounts, Holdings, Assets,
   AssetGrants, ServiceEntries, MaintenanceReminders, and
   UserRetirementPreferences — not just the 5 illustrative tables in spec §3.
   All 14 are represented in `001_initial_schema.sql`.
2. **Real business logic beyond "plain RLS-scoped table access" existed in
   four places spec §4 didn't mention at all**, each with a different correct
   home in the new architecture:
   - `RetirementProjectionService.cs` (compound-growth math, pure arithmetic,
     no external calls) → ported to client-side TS
     (`lib/retirementProjection.ts`) — no Edge Function needed.
   - `IcsGeneratorService.cs` (RFC 5545 .ics generation) → ported to
     client-side TS (`lib/icsGenerator.ts`) — the browser already has every
     field via RLS, so this needs no network round-trip at all (the original
     was a backend file-download endpoint).
   - `DashboardController.cs`'s aggregation (budget/investment/retirement/
     reminders in one round-trip, plus its own recurrence-date computation)
     → ported to client-side TS (`lib/dashboardAggregation.ts`), run as
     parallel RLS-scoped reads.
   - `OccurrenceGeneratorService.cs` (a real nightly `BackgroundService`
     generating recurring-transaction occurrences) → ported to a Postgres
     function + trigger (immediate generation on template create/update) +
     `pg_cron` nightly job (`002_functions_triggers_cron.sql`) — pure
     set-based SQL, no Deno needed.
3. **A second real `BackgroundService` with zero spec mention at all:**
   `PriceFetchService.cs` (4-hourly Yahoo Finance price refresh for
   auto-fetch holdings). This one genuinely needs outbound HTTP + JSON
   parsing, so it's the one real Edge Function added beyond spec's two:
   `fetch-holding-prices` (cron-only, no frontend caller,
   `--no-verify-jwt` deploy).
4. **`accept-invitation` doesn't exist as a user-invoked action in the real
   app at all.** `UserSyncMiddleware.cs`'s `AcceptPendingInvitationAsync`
   auto-accepts a pending invitation by email match on first sign-in — there
   is no explicit "accept" button anywhere in `apiClient.ts` or any page.
   Building an unused Edge Function just to satisfy the letter of "build the
   two Edge Functions" would have been dead code contradicting the real
   app's own behavior — replaced with the `handle_new_user()` Postgres
   trigger on `auth.users` insert/update, which reproduces the exact
   auto-accept behavior (`002_functions_triggers_cron.sql`).
5. **`create-household` was built as a genuine Deno Edge Function** (matching
   the literal instruction) but is a thin wrapper — the actual atomic
   multi-table write lives in a `create_household()` plpgsql function (one
   transaction by construction), called via `supabase.rpc()` with the
   caller's own JWT forwarded so `auth.uid()` resolves correctly. Simpler
   and more robust than trying to fake atomicity across two sequential
   Edge-Function REST calls.
6. **The original apiClient.ts had NO `createHousehold()` call and no UI path
   to `POST /api/household` at all** — confirmed by grepping `apiClient.ts`
   and every `hooks/*.ts` file. This matches CLAUDE.md Item #56's own "Not
   yet done" list ("a frontend onboarding step so a new user without a
   household is routed to create one... today's login page still only has a
   single 'Continue with Google' button"). Without fixing this, the new
   Supabase version would have reproduced the exact same "first user can
   never get in" bug Item #56 exists to fix. Added: `createHousehold()` in
   `apiClient.ts`, a new `app/onboarding/page.tsx`, and a middleware check
   (`lib/supabase/middleware.ts`) that redirects any signed-in user with no
   household membership to `/onboarding` instead of letting every other page
   fail against empty RLS results.
7. **A real, live behavior discrepancy flagged, not silently resolved either
   way:** the real EF Core `InvestmentAccount` global query filter includes
   `_currentUser.IsAdmin` as a bypass — a household admin can currently see
   every member's investment accounts, not just their own. This contradicts
   the private-investment design intent stated explicitly in spec §3
   ("RLS must scope these to the owning user_id only, not the whole
   household"). The new RLS policies implement strictly-private (no admin
   bypass), per the spec's explicit instruction — flagged here as a real
   behavior change from the currently-live Azure app, in case Mike was
   relying on that bypass.
8. **A real inconsistency in the source app preserved, not fixed:**
   `MaintenanceReminderController`'s access check has no accessLevel
   distinction (a view-only grantee can create/edit/delete reminders), while
   `ServiceHistoryController` does gate on accessLevel (view-only can't add
   entries). Both behaviors are matched exactly in the new RLS policies
   rather than "fixed" to be consistent — not this session's call to make.

## What was built

- `services/REQ-2026-01/supabase/migrations/001_initial_schema.sql` — all 14
  tables, indexes, RLS policies, and helper functions (`is_household_member`,
  `is_household_admin`, `caller_household_id`, `can_access_asset`,
  `asset_access_level`).
- `services/REQ-2026-01/supabase/migrations/002_functions_triggers_cron.sql`
  — `handle_new_user()` (profile upsert + auto-accept invitation),
  `create_household()` RPC, invitation/grant validation triggers
  (ALREADY_MEMBER / NOT_IN_HOUSEHOLD / NO_HOUSEHOLD), recurring-occurrence
  generation (trigger + nightly `pg_cron`). The `fetch-holding-prices` cron
  schedule is committed **commented out** — it needs the real project ref and
  service role key, which don't exist until Supabase is provisioned; see
  `supabase/README.md` step 4.
- `services/REQ-2026-01/supabase/functions/create-household/index.ts` and
  `.../fetch-holding-prices/index.ts`.
- `services/REQ-2026-01/supabase/README.md` — the full manual setup sequence
  (provision → migrate → deploy functions → wire cron → Google OAuth →
  Vercel env vars → smoke test).
- Frontend: `@supabase/ssr` + `@supabase/supabase-js` replace `next-auth`
  entirely (`lib/supabase/{client,server,middleware}.ts`, root
  `middleware.ts`, `app/auth/callback/route.ts`, `app/onboarding/page.tsx`,
  and updates to `login/page.tsx`, `app/page.tsx`, `navbar.tsx`,
  `providers.tsx`, `types/index.ts`, `package.json`). `lib/auth.ts` and
  `app/api/auth/[...nextauth]/route.ts` deleted.
- `lib/apiClient.ts` fully rewritten on `supabase-js` — **every exported
  function name, parameter shape, and return shape preserved exactly**, so
  every hook in `hooks/*.ts` and every page needed zero changes; only this
  file's internals changed. New `lib/retirementProjection.ts`,
  `lib/icsGenerator.ts`, `lib/dashboardAggregation.ts` hold the ported
  business logic described above.

## Verification done vs. not done

- `npx tsc --noEmit` — **100% clean** across the entire rewritten frontend,
  after fixing two implicit-`any` findings in the Supabase SSR boilerplate
  (`lib/supabase/{server,middleware}.ts`).
- `next build` — **could not get a clean local build on this Windows
  machine.** Every route, including Next's own auto-generated `/_error` and
  `/_not-found` (zero custom code), fails prerendering with `TypeError:
  Cannot read properties of null (reading 'useContext')`. Confirmed this
  isn't caused by the Supabase rewrite specifically — the failure is generic
  across every route, including ones this session never touched. Strong
  circumstantial evidence it's a Next.js 14.2.35 / Node v24.11.1 / React
  18.3.1 compatibility issue on this machine (Next 14.2 predates Node 24 by
  a long way), not a real code defect — same "Windows-only false alarm,
  builds clean on Linux" pattern this file's own Item #20 already documented
  for a `next build` failure on this exact app family. **Not independently
  re-confirmed on Linux this session** — flagged as an open verification gap
  rather than silently assumed fine.
- No live Supabase project exists, so none of the SQL/RLS/Edge Function code
  has been run against a real database — only reviewed against the real EF
  Core model and controllers for logical equivalence.
- No real Google OAuth sign-in was attempted (explicitly Mike's action item,
  step 5 of `supabase/README.md`) and no browser tooling was available this
  session — the spec's own end-to-end smoke test (§8.7) was not run.

## What's still open (all Mike's action items, per `supabase/README.md`)

1. Provision the `fiddy5` Supabase project.
2. Apply both migrations.
3. Deploy both Edge Functions; wire the `fetch-holding-prices` cron schedule
   with the real project ref/service role key.
4. New Google Cloud Console OAuth client, redirect URI pointed at Supabase's
   own Auth callback.
5. Connect the Vercel project to the repo (frontend directory), set the two
   public env vars.
6. Real end-to-end smoke test (Google sign-in → household creation →
   dashboard load).
7. **Only after that smoke test passes:** decommission
   `req-2026-01-frontend` / `req-2026-01-backend` on Azure. Not done this
   session — the user's own instructions gated decommissioning on a
   successful live verification this session could not perform (no OAuth
   setup, no browser tooling). The two Azure Container Apps are still live.

## Items superseded

Items #55, #56, #57, #58 (and the Azure-Container-Apps deploy path described
in `docs/Specs/Deploy-Agent-Multi-Platform-Spec-v1.md` /
`docs/Specs/Deploy-Agent-Multi-Platform-Spec-v2.md` where it names Fiddy5
specifically) are superseded by this replatform — moot, not resolved-via-fix,
since the .NET backend they were about is being retired. Item #58's general
insight (Deploy Agent never provisions app-level databases) remains live as
a FORGE-engine-level gap in `Deploy-Agent-Multi-Platform-Spec-v2.md` — not
re-litigated here.
