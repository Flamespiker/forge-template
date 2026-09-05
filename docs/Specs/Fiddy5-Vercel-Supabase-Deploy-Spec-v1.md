# Fiddy5 — Vercel + Supabase Deployment Spec v1

**Status:** Spec only — not yet built. Hand-off to Claude Code CLI for implementation.
**Author:** Claude.ai
**Date:** 2026-09-05
**Supersedes (for Fiddy5 specifically):** the Azure-Container-Apps deployment path described
in Items #56/#57/#58 and CLAUDE.md's Item 55/56 entries. Those Azure resources
(`req-2026-01-frontend`, `req-2026-01-backend`) are decommissioned by this spec, not fixed.
Platform-level `mike-digital-platform` Azure resources (`mdp-rg`, `mdp-con-stage`/`mdp-con-prod`,
`mdpacr`, `mdp-kv`) are **not** touched — they remain available for any future app that chooses
Azure as its target.

---

## 1. Why this exists

Fiddy5 currently has no real deployment: the frontend 404s on every API call (Item #57), and
the backend has never successfully started because no database was ever provisioned (Item #58).
Rather than fix both bugs on Azure Container Apps, Mike wants Fiddy5 hosted on Vercel + Supabase
instead — genuinely free at this scale, and Supabase's Postgres directly satisfies #58 without
Deploy Agent needing to provision anything itself yet (that generalization is Spec v1's sibling
document, the Deploy Agent multi-platform spec).

**Important constraint discovered during scoping:** Vercel Functions only support Node.js,
Python, Go, Ruby, PHP, Rust, Deno, and Bash runtimes — there is no .NET/CLR runtime, and neither
Vercel nor Supabase does arbitrary container hosting. Fiddy5's backend is ASP.NET Core (C#), so
this is not a lift-and-shift — the backend's *shape* changes, not just its address. Decided
(Mike, this session): lean into Supabase's own backend model (Postgres + Row Level Security +
Edge Functions) rather than porting the C# backend to Node/TS. This is a genuine architecture
change, not a deployment detail — flagged as such rather than resolved silently.

**No data migration required.** Item #58 confirmed no Postgres server has ever existed for
Fiddy5 on any platform — this is a clean-slate build, not a migration.

---

## 2. Target architecture

```
┌─────────────────┐        ┌──────────────────────────────┐
│  Vercel          │        │  Supabase                    │
│  Next.js frontend│───────▶│  Postgres (RLS-scoped)       │
│  (App Router)    │  REST/ │  Auth (Google provider)      │
│                  │  RPC   │  Edge Functions (Deno/TS)     │
└─────────────────┘        └──────────────────────────────┘
```

- **Frontend:** existing Next.js app, largely unchanged in UI/component terms. `apiClient.ts`'s
  custom REST calls are replaced with direct `supabase-js` queries (for simple CRUD, authorized
  by RLS) and calls to a small number of Edge Functions (for the few operations that need an
  atomic multi-table transaction).
- **Auth:** NextAuth + the custom `UserSyncMiddleware.cs` auto-provisioning pattern is retired
  entirely. Supabase Auth's built-in Google OAuth provider replaces both — Supabase already
  maintains its own `auth.users` table and handles the OAuth handshake; no custom sync code is
  needed because every app table just foreign-keys to `auth.users.id`.
- **Database:** Supabase-managed Postgres. Schema authored as SQL migration files (see §3).
- **Business logic:** split between RLS policies (authorization-shaped logic — "can this user
  see/edit this row") and Edge Functions (genuinely atomic operations that RLS can't express
  safely as two separate client-side writes).

---

## 3. Data model & RLS (first pass — CLI should verify against the real EF Core model before building)

Tables (mirroring the existing EF Core model's shape, not reinventing it):

- `households` (`id`, `admin_user_id → auth.users.id`, `created_at`)
- `household_members` (`household_id → households.id`, `user_id → auth.users.id`, `is_admin`,
  `joined_at`)
- `household_invitations` (`household_id`, `invited_email`, `created_at`, `accepted_at`)
- `budget_entries` — household-shared (RESP/TFSA/RRSP contributions, shared budget lines):
  RLS scoped to `household_members` of the same household.
- `investment_entries` — RRSP/TFSA/mutual funds/ETFs/stocks: per user's memory, the data model
  is shared-budget/**private-investment** — RLS must scope these to the owning `user_id` only,
  not the whole household, even though `budget_entries` is household-visible. This split needs
  its own explicit RLS policy per table, not a single blanket "household member" policy.

**RLS policy shape (illustrative, not final SQL):**
- `households`: SELECT/UPDATE allowed where `auth.uid()` is in that household's `household_members`.
- `household_members`: SELECT allowed to any member of the same household; INSERT/DELETE
  restricted to rows where the caller `is_admin`.
- `budget_entries`: SELECT/INSERT/UPDATE/DELETE allowed where `auth.uid()` is a member of the
  owning household.
- `investment_entries`: SELECT/INSERT/UPDATE/DELETE allowed only where `user_id = auth.uid()`.

---

## 4. Edge Functions (atomic operations only)

Only two identified so far — everything else should be plain RLS-scoped table access from the
frontend, to keep custom code minimal:

1. **`create-household`** — mirrors the `POST /api/household` logic already built in
   `HouseholdController.cs`: insert a household row, insert the caller as its admin member, in
   one transaction. Reject with `ALREADY_HAS_HOUSEHOLD` if the caller already belongs to one
   (same rule as the existing C# implementation — port the check, not just the shape).
2. **`accept-invitation`** — insert a `household_members` row and mark the invitation accepted,
   atomically, so a half-completed accept never leaves an orphaned invitation or a member row
   without its invitation being closed out.

If any other operation later turns out to need multi-table atomicity, add it here rather than
reaching for a third custom backend layer.

---

## 5. Auth setup (Mike action item, same shape as before)

- New Google Cloud Console OAuth client (the existing one's redirect URI points at the now-being-
  decommissioned Azure Container App URL — a new client, or at minimum a new redirect URI, is
  needed either way).
- Redirect URI: Supabase's own Auth callback (`https://<project-ref>.supabase.co/auth/v1/callback`),
  **not** a Vercel URL — Supabase Auth owns the OAuth handshake.
- Client ID/secret entered into Supabase's Auth provider settings (dashboard), not into any
  Vercel env var — this is the one credential Vercel never needs to see.

---

## 6. Vercel environment variables

- `NEXT_PUBLIC_SUPABASE_URL` — public, safe client-side.
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — public, safe client-side (RLS is what actually protects data,
  not secrecy of this key — this is Supabase's standard model, not a shortcut).
- Service-role key: **not** set in Vercel at all. It's only needed inside Edge Functions
  (Supabase's own execution environment), which have it available automatically — never ship it
  to the frontend bundle.

---

## 7. Free-tier considerations (verified this session, not assumed)

- **Vercel Hobby:** free, but personal/non-commercial use only — fine for Fiddy5 as Mike's own
  household tool. 100GB bandwidth/month, 1M function invocations/month, 4 hrs Active CPU/month —
  all comfortably above what a single-household finance tracker needs.
- **Supabase Free:** 500MB database, 50,000 MAU, 500K Edge Function invocations/month, 2 active
  projects per org. **Free projects auto-pause after 7 days of inactivity** (restorable from the
  dashboard, but unreachable until restored) — worth knowing if Fiddy5 goes quiet for a week; not
  a blocker for active use, but the opposite failure mode from Azure's "idle to zero cost" — here
  idle means "temporarily down," not "temporarily free."

---

## 8. Migration / build steps (ordered)

1. Provision Supabase project (`fiddy5`, personal org).
2. Author Postgres schema + RLS policies as SQL migration files, committed to the repo (not
   hand-run once and forgotten — same "everything as committed code" discipline as the rest of
   FORGE).
3. Mike sets up the new Google Cloud Console OAuth client (action item, redirect URI above);
   wires client ID/secret into Supabase Auth provider settings.
4. Build the two Edge Functions (`create-household`, `accept-invitation`).
5. Update the Next.js frontend: swap NextAuth for `@supabase/ssr`, swap `apiClient.ts`'s REST
   calls for `supabase-js` queries + the two Edge Function calls.
6. Connect the Vercel project to the GitHub repo (frontend directory only), set the two public
   env vars.
7. Smoke test: real Google sign-in → household creation → dashboard load — the exact end-to-end
   test Item #56 has been blocked on all along.
8. Decommission `req-2026-01-frontend` and `req-2026-01-backend` (`az containerapp delete`) —
   platform-level `mdp-rg`/`mdp-con-stage`/`mdpacr`/`mdp-kv` stay provisioned for future apps.
9. CLAUDE.md pointer entries for Items #55/#56/#57/#58: mark as **superseded by replatform**,
   not resolved-via-fix — the underlying bugs are moot once the .NET backend is retired, but the
   entries should say so explicitly rather than silently disappear.

---

## 9. Open questions (not blocking, but not decided)

- Calendar reminders (`.ics` vs. Google Calendar API) and the investment-price web-scraping
  source — both already deferred per the context doc — are unaffected by this platform change
  and remain open items to pick up separately.
- Should Supabase's Row Level Security policies get any kind of automated review analogous to
  the Security Agent's SAST/dependency/secrets scans? Flagged here; addressed as an open question
  in the companion Deploy Agent multi-platform spec, not solved in this document.
- FORGE has no formal "replatform an already-deployed app" workflow — this session's Fiddy5 work
  is being handled as an ad hoc spec + CLI build, same as any other ad hoc fix, but it's worth
  noting that FORGE's lifecycle model (Greenfield → Enhancement) doesn't currently have a third
  category for "same app, new target platform." Not solved here — noted for later.
