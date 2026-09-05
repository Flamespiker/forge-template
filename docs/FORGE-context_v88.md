# FORGE — Session Context v88

**Session date:** 2026-09-05 (Claude.ai + Claude Code CLI)
**Carries forward from:** v87, unchanged except where noted below.

---

## What changed this session

### Item #55 — Frontend lockfile commit gap — spec'd, built, mostly live-verified

Fiddy5's frontend reached Deploy with `package.json` committed but no
`package-lock.json`, so `npm ci` in the generated Next.js Dockerfile failed.
Root cause traced to `security_agent.py`'s Item #54 fix, which generates a
lockfile via `npm install --package-lock-only` only to run `npm audit`
against — never commits it. Real gap sat upstream at Implementation, which
never produced/committed a lockfile for a genuinely new (Greenfield)
frontend in the first place.

**Two-part fix, both built:**
- **Part A — Deploy Agent self-heal-and-commit:** if `package-lock.json` is
  missing at Deploy time, generate one (`npm install --package-lock-only`,
  reusing #54's pattern), then commit it back — unlike #54's ephemeral-only
  approach. Guarded by a fresh branch-tip API read before committing; if the
  ref doesn't match expectations, skip the commit and proceed with the local
  lockfile rather than blocking the build.
- **Part B — Implementation-stage source fix, two layers** (confirmed by
  CLI investigation, not assumed): subagents never commit directly — the
  coordinator does, after tar-packaging. Layer 1: `frontend_agent.py`'s
  `SYSTEM_PROMPT` clarified that `package-lock.json` isn't excluded build
  output like `node_modules/`. Layer 2: `implementation_coordinator.py`'s
  packaging-rules step got a pre-archive backstop check/generate.

**Commits (all on `main`, API-confirmed at tip `fa51af7`):** `0586bd5`
(`get_branch_head_sha()` helper), `1454ad3` (Part A), `57ddbe2` (Part B
layer 1), `0aa8482` (Part B layer 2), `fa51af7` (CLAUDE.md Item #55 entry).

**Test results:** 1 (missing lockfile, ref matches) — PASS. 3 (lockfile
already present) — PASS, zero npm/API calls. 4 (ref mismatch) — PASS,
commit correctly skipped, build proceeds off local lockfile. **Test 2**
(Part B actually prevents the gap in a real Stage 3 run) was deliberately
deferred — needs a real, costed Managed Agents session with no cheap local
proxy for LLM prompt-following.

**Item #55 is built and mostly verified. Test 2 is now folded into next
session's Item #57 fix PR** (see below) rather than run standalone, since
that PR's Deploy will exercise the same real Docker-build path for free.

### Fiddy5 — first real Deploy succeeded

Frontend (`req-2026-01-frontend`) and backend (`req-2026-01-backend`) both
confirmed `Provisioned`/`Healthy` via fresh `az containerapp show` reads.
This is the first real Deploy completion on the swapped `mike-digital-platform`
target.

### Item #56 — Google Sign-In / household-creation gap — partially complete

**Done this session:**
- `POST /api/household` built in `HouseholdController.cs`, compiles, and
  passed an 18/18 local sanity check — a throwaway EF Core in-memory-provider
  console harness (not part of the real repo), deliberately **not** using
  Docker, per the new no-Docker-Desktop convention (see below). Committed
  `e90ed8d`.
- `.gitignore` added to `mike-digital-platform` (`a24fb92`) — confirmed
  covers `.env`.
- Google Cloud Console OAuth client set up (Mike's action item, outside the
  pipeline).
- Env vars wired on the frontend Container App: `GOOGLE_CLIENT_ID` as a
  plain var; `GOOGLE_CLIENT_SECRET`/`NEXTAUTH_SECRET` via Key Vault
  reference through the frontend's managed identity (confirmed via fresh
  `az containerapp show` — both show `secretRef`, no plaintext). New
  revision `req-2026-01-frontend--0000003` confirmed `Provisioned`/`Healthy`.
- CLAUDE.md updated with the Item #56 entry and the new Docker Desktop
  convention (below), pushed and API-confirmed at `cb71679`.
- Tracking issue `forge-template#18` open, wired for `resolve_request_id()`.
- Local clone of `mike-digital-platform` established for the first time
  (previously didn't exist locally) — branch `feature/google-oauth-setup`,
  **not yet pushed**.

**New convention, formalized in CLAUDE.md this session:** no Docker Desktop.
For CI/build verification, use a `workflow_dispatch` GitHub Actions job on
`ubuntu-latest` (matching `forge-demo-apps`' old `verify-build.yml`,
Item #23) — `mike-digital-platform` doesn't have an equivalent yet. For
local backend-logic sanity checks, use EF Core's in-memory provider (or
stack equivalent) instead of a throwaway Docker/Postgres container.

**Still open, found live this session — new Item #57:**

### Item #57 (new) — `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_API_BASE_URL` name
mismatch — every frontend API call silently 404s

First real sign-in attempt surfaced this rather than a household-creation
gap: `deploy_agent.py` bakes the backend's URL into the frontend build as
`NEXT_PUBLIC_API_BASE_URL`, but `apiClient.ts` (line 41) reads
`NEXT_PUBLIC_API_URL` — a different name, and the only reference to this var
anywhere in the frontend. The two never matched, so `BASE_URL` always fell
back to `/api` — relative to the frontend's own origin, which has no such
route (only `/api/auth/[...nextauth]` exists there). Every API call
(dashboard, budget, assets, household) has been silently hitting a 404 on
the frontend's own domain instead of the real backend. Never caught before
because no prior session had gotten past sign-in far enough to make a real
API call.

**Fix identified, one line** (`apiClient.ts` line 41, rename to match
`deploy_agent.py`'s real output — confirm the exact name fresh from
`deploy_agent.py` before committing, don't rely on this doc). **Not yet
applied.** Since `NEXT_PUBLIC_*` vars are baked in at Next.js build time,
this needs a real image rebuild, not a Container App env var change.

**Decision (this session, not yet executed):** go through the normal
pipeline — `feature/fix-api-url-env-var-mismatch` branch, real ad hoc fix
PR, let QA/Security auto-trigger and Deploy run for real. Rejected a local
Docker rebuild (even via WSL2 without the Desktop GUI — same "local machine
is a deploy bottleneck" problem the earlier convention was meant to avoid)
and a bespoke `workflow_dispatch` bypass (skips QA/Security on a real code
change, adding to an already-flagged admin-merge pattern). **This PR's real
Deploy run will also serve as Item #55's deferred Test 2** — first genuine
confirmation that the lockfile self-heal works in an actual Stage 3/Deploy
build, at no extra cost. **Deferred to next session**, not started tonight.

So Item #56 remains open until #57 is fixed and a real sign-in → household
creation → dashboard flow can be tested end-to-end. Household-creation UI
(frontend onboarding step, login-page button) is also still unbuilt.

### Security note — `AZURE_STAGING_CREDENTIALS` found in local `.env`

CLI authenticated to Azure using the staging Service Principal during this
session's OAuth env-var work. Investigation confirmed the secret was in
`mike-digital-platform`'s local `.env` (confirmed gitignored, untracked).
Source of how it got there was not fully nailed down before moving on.
**Rotation was agreed but not yet executed** — `az ad sp credential reset`
plus updating the GitHub secret is still outstanding. This should happen
soon, coordinated so it doesn't land mid-deploy. CLI was redirected to use
Mike's own interactive `az login` for the actual env-var push, not the SP.

### Documentation audit — forge-template docs reviewed against live GitHub

Full pass comparing every project-knowledge doc against the live repo
(not just filenames — actual content diffs). Findings, not yet acted on:

**Stale (real content drift):**
- `06_Orchestration_v7.md` — live is now **v10**, three versions behind.
- `FORGE_Build_Plan_v12.md` — same filename, but live has Phase 8 fully
  closed (8.4/8.5 done, `v1.0.0` tag created 2026-09-01); project copy
  still shows those unchecked.
- `01-forge-product-specification_v2.md` — missing the Item #43 feature
  bullet.
- `02-forge-architecture-document-v4.md` / `07_Customization_Ref_v4.md` —
  **same version number as live, but live has "post-review addition" text
  for Item #43 added with no version bump.** Flagged as a systemic risk:
  matching filename/version number alone isn't a safe staleness check.
- `FORGE-Open-Items-Backlog-v6.md` — live is v9; even v9 predates Items
  #43–#57. The v9→v10 delta drafted earlier (in project knowledge) was
  never applied to GitHub at all (confirmed: no v10 file exists anywhere
  in the repo). **Decided:** supersede the delta entirely — next version
  jumps straight from v9 to a single consolidated version covering #43
  through #57 (once #57 lands), not a v10-then-v11 sequence. Also decided:
  "Real Bugs" section placement (after Design/Policy Decisions, before
  Bookkeeping), fresh renumbering of Suggested Sequencing (don't preserve
  old numbers around removed lines). **Not yet written — held pending
  #57's resolution next session.**
- `FORGE-context_v87.md` — this doc (v88) supersedes it.

**Missing from project knowledge entirely:** `03_FORGE_Tooling_v8.md`
("Tool & Licensing Inventory") — a real, current, canonical doc per
README's own reference table, never uploaded.

**Orphaned — zero live references anywhere (README, CLAUDE.md, Build
Plan):** `FORGE-commercial-alternatives-and-justification.md`,
`doc2-change-brief.md` (superseded once Document 2 reached v4). `ADR-0011.md`
(the standalone project-knowledge copy) — same substance survives but the
canonical home is now `core/decisions/0011-base-anthropic-client.md`,
reformatted with one added clarifying line; this copy is a stale duplicate
of a doc that's moved.

**Hygiene, still unaddressed:** `docs/FORGE-Open-Items-Backlog-v6/v7/v8.md`
are all still sitting at `docs/` root even though v9 supersedes them —
CLAUDE.md's own convention says superseded versions move to
`docs/Archives/`. Hasn't happened since v6.

**Not yet done:** re-uploading the stale docs to project knowledge, pulling
in the missing Tooling doc, removing the orphaned ones. Holding until the
next documentation pass alongside the Backlog rewrite.

---

## Open items — updated status

- **Item #55 — mostly CLOSED.** Parts A and B built and committed; Tests
  1/3/4 passed live. Test 2 folded into Item #57's upcoming fix PR rather
  than run standalone.
- **Item #56 (open)** — Google OAuth Cloud Console + env vars done; blocked
  on Item #57's fix before a real end-to-end sign-in test is possible;
  household-creation UI still unbuilt.
- **Item #57 (new, open)** — `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_API_BASE_URL`
  mismatch, one-line fix identified, not yet applied. Next session: real
  fix PR through the normal pipeline.
- **Item #44 (open, unchanged)** — `run_cost_estimate()` 404s if
  `design-approved` applied before design PR merge. Low urgency.
- **Item #41 (open, design decision, unchanged)** — `forge-template`'s
  `is_template: true` dual-role question. Still deferred.
- **Items #38, #39, #40, #42** — unchanged, low-urgency/clubbable.
- **Items #7, #11** — unchanged, accepted ongoing risk.
- **Security hygiene (new, open):** `AZURE_STAGING_CREDENTIALS` rotation
  still outstanding after being found in local `.env`.
- **Documentation reconciliation (new, open):** see audit findings above —
  Backlog rewrite, six stale docs, one missing doc, orphan cleanup, v6-v8
  archive-move all pending, batched for the next documentation session.

## Azure infrastructure

`mdp-con-stage` now has real, healthy, running Fiddy5 workloads for the
first time this session (`req-2026-01-frontend`, `req-2026-01-backend`).
**End-of-session shutdown check completed, nothing to do:** both apps
confirmed at zero active replicas (`minReplicas: 0`, `maxReplicas: 2`,
`cooldownPeriod: 300s`) — genuinely idling on their own. `mdpacr` (Basic
SKU) has no scheduled/active/recent tasks — flat storage only, nothing
billing beyond that. No manual shutdown needed tonight.

### Item #58 (new) — No Postgres database provisioned for Fiddy5 on this
platform at all — systemic Greenfield gap, not Fiddy5-specific

Investigating the shutdown check surfaced this: `az postgres
flexible-server list` (subscription-wide) returns **empty** — no Postgres
server exists anywhere. `req-2026-01-backend`'s only env var is
`FRONTEND_ORIGIN`; no `DATABASE_CONNECTION_STRING`/
`ConnectionStrings:DefaultConnection` is set, and `Program.cs` throws
`InvalidOperationException` at startup without one. **The backend has
almost certainly never successfully started on `mike-digital-platform`.**

This means fixing Item #57 alone would trade a silent frontend 404 for a
real backend crash-loop — the frontend would finally reach the backend,
which would then fail to start. **Root cause is systemic:** nothing in
Design→Implementation→Deploy currently provisions app-level infrastructure
(a database) for a Greenfield build — only app code and the Container Apps
themselves. Any future Greenfield app needing a real database hits this
same wall. Comparable in shape to Item #55 (a gap that's invisible on
Enhancement, since an existing service already has its DB, but bites every
Greenfield app's first real run).

**Real design questions, not decided yet:**
- Does Deploy Agent provision the Postgres Flexible Server itself
  (connection string via Key Vault reference through the backend's managed
  identity — same pattern as tonight's OAuth secrets), or does this stay a
  manual Mike-does-it-in-Azure step, same as Google Cloud Console OAuth
  registration?
- SKU/tier, firewall/VNET rules, backup policy — real provisioning
  decisions requiring their own pass, not defaults to rush.
- **Decided:** #58 does **not** block Item #57's fix PR — #57 is a real,
  correct fix worth shipping on its own even though the backend will still
  crash-loop afterward until #58 is resolved. That's an accurate
  intermediate state, not a reason to hold up a correct fix.

**Not yet spec'd or built.** Next session: proper design pass on #58,
likely after #57's fix PR lands.

---

## On the horizon

- **Item #57** — real fix PR next session (`feature/fix-api-url-env-var-mismatch`),
  doubling as Item #55's deferred Test 2. Does not block on #58.
- **Item #58 (new)** — proper design pass on Postgres provisioning for
  Greenfield apps; likely sequenced after #57's fix PR lands.
- **Per-app README (new candidate, unnumbered)** — raised this session:
  `mike-digital-platform` needs its own top-level README (distinct from
  `forge-template`'s, which documents the orchestration engine, not the
  apps it produces), and each app/service likely needs its own scaffolded
  README documenting its actual architecture, backend, and — notably —
  the real injected env var names (would have directly caught Item #57).
  Open design questions not yet resolved: who generates it (Design vs.
  Implementation subagents vs. Deploy Agent finalization — Deploy is the
  only stage that knows the true injected var names), how Enhancement
  apps' existing READMEs get updated vs. overwritten, and whether Fiddy5
  gets one by hand now or this waits to become a proper pipeline feature.
  Not spec'd — pick up next session.
- **Item #56** — household-creation UI, login-page button, real end-to-end
  sign-in test once #57 (and likely #58) land.
- **`AZURE_STAGING_CREDENTIALS` rotation** — still outstanding.
- **Documentation consolidation pass** — Backlog rewrite (v9 → next
  consolidated version through #57), six stale-doc re-uploads, missing
  Tooling doc, orphan cleanup, v6-v8 archive-move.
- **Item #44, #41, #38, #39, #40, #42** — unchanged, no urgency.

