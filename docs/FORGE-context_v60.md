# FORGE Context — v60
**Session date:** 2026-08-19
**Carries forward from:** v59

---

## Purpose & context (unchanged)

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment, with human approval gates at defined stages.

Two-repo model: `forge-template` (public, orchestration/agents) and `forge-demo-apps` (private, target monorepo). Two-tool convention firm: Claude.ai owns strategy/spec authorship/context docs; Claude Code CLI owns live execution/git/CLAUDE.md. Mike shuttles between tools and holds all unilateral decisions.

---

## Current state

**Phase 6 (Repeatability) is CLOSED as of this session.** Mike's decision: the repeatability proof is considered complete with two apps — App 1 (REQ-2026-02, read-heavy, D365-backed) and App 2 (REQ-2026-03, write-heavy, Postgres-backed, real Azure AD SSO). No third app planned. This resolves the last open question carried forward from v59.

**Active build:** Phase 6, App 2 — REQ-2026-03 (On-Call Roster Tracker) — fully deployed and functionally verified end-to-end (frontend, backend, Azure AD SSO, real Postgres backing store all live; write-path claim/release proven with real HTTP calls plus direct DB verification, per v59). No further build work on App 2 this session; this session was closeout and documentation only.

### Resolved this session

1. **Phase 6 closeout decision.** Mike confirmed the two-app repeatability proof (App 1 + App 2) satisfies Phase 6's goal. Remaining App 2 cleanup items (test-user flag, firewall rules, registration rename) are tracked below as post-closeout housekeeping, not blockers to calling the phase done.
2. **Three pending doc updates from v58 applied** (Dependabot swap, drafted v58, applied this session):
   - `03_FORGE_Tooling_v7.md` → **v8**: §3.5 default dependency scanner swapped from OWASP Dependency-Check to GitHub Dependabot alerts (native, API-based, no Actions job); Dependency-Check retained as a documented alternative. Cost Summary (§8) and Provisioning Checklist (§4 item 8) updated to match. Root cause and the 30-min-timeout→18-second live result carried into a new §3.5 note.
   - `07_Customization_Ref_v2.md` → **v3**: Security Tooling table's dependency scanner row updated to Dependabot alerts as default, Dependency-Check moved to the substitution option.
   - `09-forge-readme_v6.md` → **v7**: Cost reference table's security tooling row updated to name Dependabot alerts instead of Dependency-Check.
   - All three are one-doc-per-chat convention exceptions — done together in this session at Mike's explicit request to close out the batch.

### Resolved in v59 (prior session, carried forward for record)

1. **Azure AD wiring — Steps 1 & 2, RESOLVED.**
   - Frontend (`req-2026-03-frontend`): `AZURE_AD_CLIENT_ID`/`AZURE_AD_TENANT_ID` wired as plain env vars; `AZURE_AD_CLIENT_SECRET` generated fresh in the Portal and wired via the existing `_wire_keyvault_secret()` primitive (`app_secret_key='azuread-secret'`, new KV secret `req-2026-03-azuread-secret`). Verified live: `/api/auth/providers` returns a fully-formed `azure-ad` entry with real signin/callback URLs.
   - Backend (`req-2026-03-on-call-rost-5bb949`): confirmed via `Program.cs` (`.AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"))`, no custom `TokenValidationParameters`, no custom config provider) that the standard ASP.NET Core double-underscore convention applies safely. Wired `AzureAd__TenantId`/`AzureAd__ClientId`/`AzureAd__Audience` as plain env vars via the normal deploy loop (not secrets).
   - `AzureAd__Audience` confirmed as exactly `api://b59886c1-12ac-42c1-895f-5fafa8e57318` via the Portal's "Expose an API" blade (the Azure default, non-custom URI) — checked for real rather than assumed, since the staging SP has no Graph read access to verify this itself (`az ad app show` fails by design under a Contributor-scoped SP). Matches `lib/auth.ts`'s existing `access_as_user` scope request — no frontend scope-request change needed.
   - Live verification: both units restart clean, zero `__AZURE_TENANT_ID__`/`__AZURE_CLIENT_ID__` placeholder errors.

2. **Azure Database for PostgreSQL Flexible Server — provisioned, real staging DB now live.**
   Root gap: no app before REQ-2026-03 had ever needed a real Postgres instance (App 1/REQ-2026-02 was D365-backed) — `DATABASE_URL` had never had a real target. Decided and built:
   - Provisioned `forge-req2026-03-pg` (Burstable B1MS, 32GB storage — Azure's storage floor, cannot go smaller; storage can only increase later, never decrease), Canada Central, under Mike's own elevated `az` session (staging SP can't register resource providers or create this resource type — same bootstrap pattern as Key Vault).
   - **Real Canada Central pricing** (Azure Retail Prices API, not the commonly-cited US East figure): compute $0.0185/hr (~$13.51/mo continuous), storage $0.1265/GB/mo (~$4.05/mo, billed regardless of stop/start state), backup free at this size. **~$17.56/mo running continuously; ~$4.05/mo floor when stopped.**
   - `az postgres flexible-server stop` pauses compute billing immediately but not storage billing; server auto-restarts after 7 days if never manually started again — acceptable given active weekly-plus testing cadence. **Server confirmed stopped at end of session.**
   - Connection string format confirmed via `.csproj` (`Npgsql.EntityFrameworkCore.PostgreSQL 8.0.11`) and `Program.cs`'s own fallback default: ADO.NET key=value format, not a `postgres://` URI. Stored as KV secret `req-2026-03-database-url`, wired to the backend via `_wire_keyvault_secret()` (`app_secret_key='database-url'`).
   - Firewall: tested the narrow option first (Container Apps environment's documented static IP) — failed live (`TimeoutException`), confirming that IP isn't actually used for this environment's egress in a no-VNet WorkloadProfiles config. Fell back to the broad `AllowAzureServices` rule (tested working), a known and explicitly-accepted tradeoff, not a silent default.
   - Two real gaps found and fixed mid-session, not anticipated by the original plan: (a) `--public-access None` was mistakenly included on server-create, which blocks firewall-rule operations entirely — caught and reverted; (b) `req-2026-03-on-call-rost-5bb949` had no managed identity at all (`type: "None"`) — Key Vault wiring requires one, so system-assigned identity was enabled and granted `Key Vault Secrets User` on `forge-build-kv` before proceeding, mirroring the frontend's existing grant.
   - Live migration verified: `20260815025731_InitialCreate` applied clean, `Users`/`Shifts`/`AuditEntries` tables created, prior `[::1]:5432` connection error fully gone.

3. **Write-path (claim/release) verification — RESOLVED. This was the actual point of choosing this app for Phase 6, and it's now proven.**
   En route, found and fixed a real root cause: the frontend's "too many redirects" error wasn't a new bug — the deployed image predated PR #21's already-merged NextAuth fix (a stale-image-after-merge gap, same shape as the earlier missing-`frontend/public/` recurrence). Rebuilt from current `main` and redeployed; confirmed single 307→200 redirect via curl.

   Full results, each with real HTTP response + direct DB verification (not API-response trust):

   | # | Action | HTTP | DB state |
   |---|---|---|---|
   | 1 | `POST /api/v1/shifts` (create test shift; bootstrapped `IsCoordinator=true` via direct SQL — no self-service path exists) | 201, `status:"Open"` | Row created, `AssignedUserId` null |
   | 2 | `POST /api/v1/shifts/{id}/claim` | 200, `status:"Claimed"` | `AssignedUserId` = real test-user ID ✓ |
   | 3 | `DELETE /api/v1/shifts/{id}/claim` (release) | 200, `status:"Open"` | `AssignedUserId` = NULL ✓ |
   | 4 | Invalid: release an already-unclaimed shift | 409 `SHIFT_NOT_CLAIMED` — correctly rejected | no DB change, no audit entry |
   | 5 | Invalid: claim an already-claimed shift | 409 `SHIFT_ALREADY_CLAIMED` — correctly rejected | no DB change, no audit entry |
   | 6 | AuditEntries for this shift | — | Exactly 3 rows (Claimed → Released → Claimed), correct actor + timestamp order; zero spurious entries from the two rejected attempts — confirms audit-write only runs on the success path |

   Auth chain fully validated end-to-end: the first authenticated `GET /api/v1/shifts` returning 200 was itself live proof the `AzureAd__Audience`/`ClientId`/`TenantId` wiring validates a real bearer token, no separate check needed.

   Minor, non-blocking bug found: `SHIFT_ALREADY_CLAIMED`'s error message ("claimed by someone else") is imprecise for the self-claim-retry case tested — status code and rejection logic are both correct, wording only.

4. **CLAUDE.md updated (additive, per its new convention — see below).**
   Claude Code applied the diff directly: resolved/struck-through the old Azure AD placeholder Open Item, added a new "Azure AD wiring + Postgres provisioning" reference subsection, added the stale-image-after-merge pattern note, and logged one new open cleanup item (below). Reviewed and confirmed clean — no restructuring, additive only.

### Still open / next session's starting point

**Phase 6 is closed. These are post-closeout housekeeping items, not blockers — pick up whenever convenient, no active build required to address any of them:**

- **Cleanup debt (not urgent):** test user "Mike App Test" (`AzureAdOid=3100bd61-03a4-4ebc-9327-4d2731f172f5`) still has `IsCoordinator=true` in the DB — a bootstrap artifact, needed to create a test shift via the real API since no self-service coordinator path exists. Flip back before treating App 2 as fully closed out.
- **Firewall rule cleanup (not urgent):** `forge-req2026-03-pg` still has two now-irrelevant rules — `AllowAdminVerificationIp` (added in v59 for direct `psql` verification) and the earlier stale, never-functional `AllowContainerAppsEnvOutboundIp`. Both harmless, worth clearing when convenient.
- **Registration rename** — still recommended (`FORGE-REQ-2026-03-OnCallRoster` → something like `FORGE-DemoApps-SSO`), still not done. Cosmetic only, carried forward from v58.
- **102 Dependabot alerts repo-wide, 74 outside REQ-2026-03** — future triage pass needed, not urgent. Carried forward from v58/v59.
- **`SHIFT_ALREADY_CLAIMED` error message wording** — minor bug, self-claim-retry case gets a misleading "claimed by someone else" message. Worth a ticket, not urgent.

**Doc updates:** all three drafted from v58 (`03_FORGE_Tooling` §3.5, `07_Customization_Ref` Security Tooling table, `09-forge-readme` cost table) are now applied — see "Resolved this session" above. No further doc updates outstanding.

**Next phase:** not yet defined. With Phase 6 closed, next session's starting point is whatever Mike decides comes after repeatability — a new phase kickoff, or FORGE considered feature-complete for now pending the housekeeping items above.

---

## Key learnings & principles (new this session)

**One-doc-per-chat is suspendable by explicit request, not a hard rule.** Mike explicitly asked to batch four document updates (context doc + three Dependabot-swap doc updates) into a single session rather than four separate chats, given they were small, mechanically similar edits reflecting an already-decided, already-drafted change. Treated as a one-time exception for this batch, not a standing change to the convention.



**Stale-image-after-merge is a recurring failure shape, not a one-off.** This is at least the second time a merged fix PR didn't match the actually-running container (earlier: missing `frontend/public/` directory recurrence; this session: the NextAuth redirect-loop fix). Confirming a fix is present in the *redeployed image's build SHA* — not just "PR shows merged on GitHub" — is now a documented CLAUDE.md pattern.

**Azure's Postgres storage floor (32GB) removes a cost lever some plans assume exists.** Before assuming a smaller-storage option can trim cost, confirm the platform's actual minimum — it can't be reduced later either, only increased, so getting size wrong compounds rather than one-time-costs.

**Test narrow-scope infrastructure options before falling back to broad ones, but accept the broad option explicitly once the narrow one is proven not to work** — the Container Apps static-IP firewall attempt was tested and failed live rather than assumed to work or skipped in favor of the broad rule by default. The broad `AllowAzureServices` fallback was adopted as a known, stated tradeoff, not a silent default.

**Azure Portal/Graph-level facts (App ID URIs, resource states) sometimes require a human with the right session, not the pipeline SP** — confirmed again this session (`az ad app show` failing under the Contributor-scoped staging SP was expected, not a bug) alongside the `az login --use-device-code` MFA workaround first identified in an earlier session, now confirmed working a second time.

**Real end-to-end write-path verification (real HTTP + direct DB query, including checking the audit trail and confirming invalid operations are actually rejected) surfaces things API-response trust alone would miss** — the audit-entry check specifically confirmed a negative (zero spurious entries from rejected 409s), which required deliberately looking rather than just accepting a 200/409 status code at face value.

---

## Approach & patterns (reconfirmed, unchanged)

- Two-tool convention firm; Claude Code CLI prompts/specs drafted in full in Claude.ai chat, copy-pasted.
- Credentials (client secrets, bearer tokens) are always entered directly into the Claude Code terminal session, never pasted into Claude.ai chat — reconfirmed twice this session (Azure AD client secret, and the live bearer token used to drive write-path testing).
- Design forks with cost or architectural implications surfaced explicitly to Mike before proceeding — reconfirmed this session with the Postgres provisioning choice (managed Flexible Server vs. containerized Postgres) and the 32GB storage-floor confirmation.
- Verify before trusting: live git evidence, real re-scans, real HTTP + DB checks against deployed units — reconfirmed repeatedly (Postgres firewall rule tested live rather than assumed, migration output checked directly rather than trusting absence-of-error).
- **`CLAUDE.md`'s role has changed:** per Mike, it is no longer a running daily account — closed/resolved items get archived out, and only open or newly-relevant items persist going forward. Session prompts to Claude Code for `CLAUDE.md` updates should be framed as durable facts/patterns/open-items only, not session narrative, going forward.

---

## Tools & resources (additions this session)

- **Azure Database for PostgreSQL Flexible Server:** `forge-req2026-03-pg` in `forge-build-rg`, Canada Central, Burstable B1MS / 32GB. Database `oncallroster`. Admin user `forgeadmin`. Connection string stored as KV secret `req-2026-03-database-url`.
- **New KV secret:** `req-2026-03-azuread-secret` (Azure AD client secret for the frontend OAuth client).
- **Firewall rules on `forge-req2026-03-pg`:** `AllowAzureServices` (broad, functional), `AllowAdminVerificationIp` (narrow, verification-only — cleanup candidate), a stale non-functional `AllowContainerAppsEnvOutboundIp` (cleanup candidate).
- **`req-2026-03-on-call-rost-5bb949`'s managed identity:** now system-assigned (was previously `type: "None"`), granted `Key Vault Secrets User` on `forge-build-kv`.
