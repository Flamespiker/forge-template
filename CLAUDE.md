# FORGE — Claude Reference

This file captures decisions, conventions, and setup notes for the forge-template project.
Read this at the start of every session before making changes.

---

## Project Overview

FORGE is an AI-orchestrated SDLC platform for Legal Aid Alberta. It takes BA-produced Excel
intake spreadsheets through a full pipeline (requirements → design → implementation → QA →
security → deploy) with human approval gates at each stage.

- **FORGE repo:** `forge-template` (GitHub: `Flamespiker`) — orchestration machinery only
- **Target repo:** `mike-digital-platform` (GitHub: `Flamespiker`, private) — stand-in for LAA's
  application monorepo during the build/demo phase. **Swapped from `forge-demo-apps`
  2026-09-04** — see "Platform swap: forge-demo-apps → Mike Digital Platform (mdp)" below.
- **ADO org:** `https://dev.azure.com/spike99` — project `Mike Digital Platform`
- **Full project context:** the newest `docs/FORGE-context_v*.md` — read this for
  architecture decisions, agent roster, pipeline stages, and session history
- **This file's history:** trimmed 2026-08-18 to stay lean (it's loaded into every
  session). Full pre-trim narrative lives in `docs/CLAUDE-archive-2026-08-*.md` — see
  "Further reading" at the end of this file.

**Standing convention — no Docker Desktop for local dev/verification (decided
2026-09-05):** for CI/build verification (matching the real Actions environment),
use a `workflow_dispatch`-triggered GitHub Actions job on `ubuntu-latest`, same
pattern as `forge-demo-apps`' old `verify-build.yml` (Item #23) — confirmed
2026-09-05 that `mike-digital-platform` has no such workflow yet (only the three
cross-repo dispatch workflows from Item #49); create one there before it's needed
rather than reaching for Docker Desktop. For a local backend-logic sanity check
with no real CI/build concern, use EF Core's in-memory provider (or the
equivalent for whatever stack) instead of a throwaway Docker/Postgres container.

---

## Documentation Ownership

**Each tracking doc has exactly one owner, to prevent the staleness/overlap that
happened around 2026-08-31:**

- **`CLAUDE.md`** — owned by Claude Code CLI. The live source of truth, tied to
  actual committed code. Claude.ai never edits this file directly; it may flag
  staleness and hand Claude Code CLI a prompt to fix it.
- **`docs/FORGE-Open-Items-Backlog-v*.md`** (current: `v6`, lives at `docs/` root —
  prior versions live in `docs/Archives/`) — owned by Claude.ai. A forward-planning
  index (one line per item, open or resolved-pointer). Claude Code CLI never edits
  this file directly, even if asked to as part of a larger task — flag back to
  Mike/Claude.ai instead of writing to it. Unlike `docs/FORGE_Build_Plan_v*.md`
  (single current version, old ones removed when superseded), every Backlog
  version is retained — just relocated to `docs/Archives/` once superseded, not
  deleted.
- **`docs/FORGE-context_v*.md`** — owned by Claude.ai. Session-by-session diary.
  Claude Code CLI never touches these.

**Default for any newly-resolved CLAUDE.md item:** a short pointer (3-8 lines) plus
a dated archive-file entry for the full narrative — not full narrative inline. Only
genuinely short resolutions stay inline from the start.

---


## Current Build Phase

**Fiddy5 replatformed to Vercel + Supabase, 2026-09-05 — supersedes Items
#55/#56 below (and #57/#58, tracked in the newest `docs/FORGE-context_v*.md`,
not yet backfilled into this file's numbered Open Items).** Built from
`docs/Fiddy5-Vercel-Supabase-Deploy-Spec-v1.md` (Claude.ai): Postgres schema +
RLS for all 14 real entities, `create-household`/`fetch-holding-prices` Edge
Functions, `@supabase/ssr` auth replacing NextAuth, and `lib/apiClient.ts`
rewritten on `supabase-js` with every exported function signature preserved
(zero changes needed to `hooks/*.ts` or any page). The .NET backend and its
Azure Container Apps are being retired by this change, not fixed — the
REST-API-mismatch (#57) and no-database (#58) bugs are moot once there's no
.NET backend left to have them. **Not yet done: Supabase project
provisioning, Google OAuth re-wiring, and the real end-to-end smoke test —
all Mike's action items — so the two live Azure Container Apps
(`req-2026-01-frontend`/`-backend`) have deliberately NOT been decommissioned
yet**, per the same gate the spec itself sets (verify live, then
decommission). Full narrative, every spec correction made during
investigation, and local build-verification status:
`docs/CLAUDE-archive-2026-09-fiddy5-supabase-replatform.md`. Fiddy5's own
ongoing tracking moves to its own Claude project once stood up — this file
won't carry deeper Fiddy5 narrative going forward.

**Platform swap completed 2026-09-04 — target platform is now `mike-digital-platform`
("mdp"), not `forge-demo-apps`.** Full decommission-and-reprovision cycle following
`docs/FORGE-platform-swap-runbook.md`: old `forge-build-rg` (5 live Container Apps,
Postgres, Key Vault, ACR), the `FORGE-DemoApps-SSO` app registration, `forge-demo-apps`,
and ADO project `FORGE-Build` all confirmed deleted; new `mdp-rg`/`mdp-con-stage`/
`mdp-con-prod`/`mdpacr`/`mdp-kv`/`mike-digital-platform`/ADO project "Mike Digital
Platform" provisioned and wired in (commit `f17d307` to `team/config.yaml`,
`FORGE_TARGET_REPO`/`ACR_*` secrets rotated, GitHub App installation extended, the
`forge-deploy-staging` SP kept and re-scoped rather than recreated). Live-verified via
a real `verify-setup.yml` run (`33829563278`, fully green) against the new target — not
just resource-existence checks. Full step-by-step narrative, every command, and every
live-verification result: `docs/CLAUDE-archive-2026-09-platform-swap-mdp.md`.

**Correction, 2026-09-04 (same day):** that `verify-setup.yml` run did **not** actually
prove the target repo was pipeline-ready — `mike-digital-platform` had been created but
never seeded (0 commits, no `pipeline-state` branch), which `verify-setup.yml`'s
config/connectivity checks don't exercise. This surfaced as a real Stage 1 failure on the
first genuine request run against the new target (`REQ-2026-01`). See Open Item #45 for
the full fix and the runbook update meant to prevent a recurrence.

**Second correction, same day:** the swap also shipped the new target repo with none of
`notify-forge.yml`/`design-pr-security-noop.yml`/`ops-pr-security-noop.yml` — meaning
QA, Security, and (later) Deploy would have silently never fired for any request, a gap
`verify-setup.yml` and Stage 1 alone can never surface. See Open Item #49 for the full
fix, including the discovery that these three files had never lived in `forge-template`
at all until this fix — only ever in the target repo — so a future swap that also
deleted its old target repo with no separate backup would have had no source to recover
them from. Reference copies now live in `core/templates/target-repo-workflows/`.

**Phase 8 (Handoff Readiness) is fully complete (8.1-8.5, 2026-09-01).** Tagged
`v1.0.0` — annotated tag on commit `97aa752` (`main` HEAD at the time), pushed to
origin and verified via the GitHub API (`git/ref/tags/v1.0.0` → `object.type: "tag"`,
confirming a genuine annotated tag; `git/tags/{sha}` → correct message and commit
target). FORGE's first stable release.

**8.4 complete (2026-09-01).** Fresh-clone setup verification — but not a clean pass on
the first try. `verify-setup.yml` (and 8 other stage workflows, two layers deep)
hardcoded `forge-demo-apps`/`spike99`/`Flamespiker` instead of reading config, so a
genuinely new OM's App/target repo hit a real 404 (Item #35). `team/config.yaml` itself
turned out to have three mutually incompatible schemas across README, the OM Guide, and
the real shipped file (Item #36) — neither doc's example keys existed in the real file
at all. Fixed via new repo Variables (`FORGE_TARGET_REPO`, `FORGE_GITHUB_OWNER`,
`FORGE_ADO_ORG_URL`) replacing two layers of hardcoding, plus a config-file trim to its
two actually-read blocks (Item #37 separately confirmed the file's live `spike99`/
`FORGE-Build` values are intentional, not a placeholder bug). Verified twice: a live run
against the real setup went from a real 404 to fully green, then a genuine fresh-clone
retest against a *different* target (a scratch repo, since torn down) confirmed the
connectivity check resolved that scratch target specifically — proving the fix reads
`${{ vars.* }}` for real, not coincidentally matching the old hardcoded values. Full
detail, all commit SHAs, and the newly-surfaced Items #38-#42: `docs/FORGE-Open-Items-Backlog-v9.md`
and this file's own Open Items section below. 8.5 (tag `v1.0.0`) followed in a
same-day follow-up session — see the paragraph above.

**Phase 8 steps 8.1-8.3, historical (2026-08-31).** Landed
Claude.ai's finished drafts after verifying no drift against the live repo:
nine core ADR stubs filled in (`core/decisions/0001-0007, 0009, 0010` — 0008
and 0011 were already real and untouched); `docs/06_Orchestration_v7.md`
(Enhancement vs. Greenfield section, Gate 2.5/`cost-approved`, confirmed-merge
Deploy requirement, post-deploy crash-loop check, stale SDK-reference fixes)
replaces v6; `docs/07_Customization_Ref_v4.md` (same corrections plus two new
Locked-item rows) replaces v3. Old v6/v3 removed per this doc series'
existing single-current-version convention; README links updated to match.
`forge-template`'s `main` confirmed unprotected, so all of this — plus a
separate housekeeping commit for Mike's `docs/ADRs`/`Archives`/`Specs`/
`Templates` reorg — landed as direct commits, not PRs.

**Phase 7 (Enhancement Workflow) is underway — Build Plan step 7.1 (Codebase
Ingestion Agent, Stage 0a) is complete and live-verified (2026-08-27).** New
`core/agents/ingestion_agent.py`, a new `github_helper.get_repo_tree()`, Stage 0a
wiring in `00-intake.yml`, and optional existing-architecture-summary.md fetches in
`requirements_agent.py`/`design_agent.py` — see "ingestion_agent.py — Stage 0a
(Codebase Ingestion)" below for the full writeup. Build Plan step 7.2 (choosing/
writing the actual enhancement request's intake spreadsheet) has not started —
per `docs/FORGE-Phase7-Ingestion-Agent-Spec.md`, that's explicitly a separate,
later session's work.

**Stage 3 (Implementation), QA (Stage 4), Security (Stage 5), and Deploy (Stage 6) all
now correctly resolve an Enhancement request's real existing-service target** — built
and live-verified 2026-08-28/29. Previously each stage assumed a brand-new
`services/<request_id>/` folder, which broke every Enhancement request past Stage 2.
See Item #24 (Stage 3), Item #25 (QA/Security, plus the shared `resolve_service_root()`
helper), and Item #28 (Deploy, plus the `naming_id` concept so an Enhancement updates
the existing Container Apps in place rather than deploying under a new parallel set)
for the full fix narratives. Item #27 (a related stale-label-clearing bug in
`04-qa.yml`) was found and fixed during Item #25's own verification pass.

**Deploy no longer fires until the feature PR is actually merged** — built and fully
live-verified 2026-08-29, including a real Deploy run triggered by a real merge. See
Item #26 for the full fix narrative (the `pr-merged` dispatch trigger, the guard-clause
change requiring both labels and a confirmed merge, and the real end-to-end
merge-to-deploy verification). Landing this fix surfaced a related gap, now also
closed — see Item #30.

**FORGE has completed Phase 6 (Repeatability)** — App 2 (`REQ-2026-03`, On-Call Roster
Tracker) ran through the full pipeline; its FORGE tracking issue (`forge-template#6`)
was closed 2026-08-20. Phases 1-6 are complete:

- **Phase 3 (Agent Implementation)** and **Phase 4 (Pipeline Wiring)** — complete.
  All seven `.github/workflows/*.yml` files are wired with real triggers/guard clauses;
  branch protection is live on `forge-demo-apps`. Full step-by-step history and every
  dated live-run verification: `docs/CLAUDE-archive-2026-08-phase3-5.md`.
- **Phase 5 (App 1, `REQ-2026-02`, Inactive User & License Auditor → descoped to a
  license-status report, R-001)** — complete and closed out. Reached staging in a real
  browser; production deliberately never attempted. Azure Container Apps and the D365
  connection were decommissioned 2026-08-13 (App User disabled, client secret deleted,
  app registration kept for potential reuse; code retained in `forge-demo-apps`). Full
  fix cycle (Stage 3 recovery tooling, the deploy-trigger/label-token bug, cross-service
  wiring, the `request_id`/`resolve_feature_pr()` fixes, the security scanner-failure
  verdict fix): `docs/CLAUDE-archive-2026-08-req2026-02.md`.
- **Phase 6 (App 2, `REQ-2026-03`)** — complete and closed out (tracking issue closed
  2026-08-20; code retained in `forge-demo-apps`, staging Container Apps/Postgres left
  running — no decommission requested, unlike Phase 5's App 1). Stages 0-5 complete
  and approved (PR #20 merged). Stage 6 (Deploy): both frontend and backend live in
  staging — the backend unit's naming blocker was resolved 2026-08-18 by
  `_finalize_unit_name()`'s truncation+hash scheme (see "Unit naming and validation"
  below); real re-run confirmed the backend Container App at
  `req-2026-03-on-call-rost-5bb949.yellowmeadow-894377a9.canadacentral.azurecontainerapps.io`.
  **2026-08-19 fix cycle** (app-secrets wiring + a real frontend auth bug, both closed
  out): `NEXTAUTH_SECRET` and `NEXTAUTH_URL` wired to `req-2026-03-frontend` (see
  `_wire_keyvault_secret()` under deploy_agent.py below); a real `pages.signIn`
  self-redirect-loop bug found in the frontend's own `lib/auth.ts` (PR #21, merged);
  Security Agent's dependency scanner swapped from OWASP Dependency-Check to GitHub
  Dependabot alerts (see security_agent.py below) after Dependency-Check timed out
  twice consecutively in CI. **Resolved same day (later 2026-08-19 session):** Azure AD
  wired to both frontend and backend, a real staging Postgres provisioned, and the
  claim/release write-path verified end-to-end via direct HTTP + DB checks — see "Azure
  AD wiring + Postgres provisioning" below. Former Open Item #14 closed.
  **2026-08-19/20 fix cycle (`SHIFT_ALREADY_CLAIMED` wording, PR #22 in
  `forge-demo-apps`):** the 409's message text always said "claimed by someone else,"
  even on a self-claim retry (a user re-claiming a shift they already hold) — the bug
  identified during the write-path verification above. Fixed both sides: backend's
  `ClaimResult` (`ShiftsRepository.cs`) now carries the actual conflicting
  `AssignedUserId` (re-read fresh from the DB on the `StaleRowVersion` concurrency path,
  since the in-memory entity there reflects the attempted write, not persisted state),
  so `ShiftsController.cs` can branch the message on self vs. other; error code/HTTP
  status unchanged. Also found and fixed a second, previously-undocumented bug while
  verifying: `ShiftRow.tsx` ignored `err.body.message` entirely for this error code and
  rendered a hardcoded string — meaning the backend fix alone would have had zero
  user-visible effect. Now renders the backend's message, since the frontend's own
  `shift` prop is stale at the moment this error fires (only reflects pre-request
  state) and can't reliably distinguish self vs. other itself. 39 backend + 29 frontend
  tests pass (2 new, one per side, for the self-claim case). Live-deployed to staging
  via a **manual** `deploy_agent.py` invocation with explicit `--commit-sha`/
  `--pr-number` — see the new Open Item below on why the normal label-driven path
  couldn't do this automatically; confirmed via `az containerapp show` that both
  running Container Apps' image tags match the fix commit (`d53bebd8610...`). DB
  audit-entry table confirmed internally consistent (4 rows, clean Claimed/Released
  pairs, no spurious entries) via a throwaway `docker run postgres:16-alpine` against
  the existing `req-2026-03-database-url` Key Vault secret (read directly — the
  staging deploy SP already has Key Vault Secrets Officer on `forge-build-kv`, so no
  new credential was needed) — not a fresh live re-test of this specific fix, since the
  live HTTP smoke test (real bearer tokens) was explicitly skipped this cycle. Temp
  firewall rule and Postgres start were both cleaned up (rule removed, server
  re-stopped) immediately after.

  **Live HTTP smoke test completed 2026-08-20 — fix fully verified, this item is now
  closed.** Real Azure AD bearer tokens (device-code sign-in as two existing test
  identities, `MikeTest1` and `Mike Test 2` — captured manually via the live frontend's
  own browser sign-in + devtools Network tab, since the API's app registration doesn't
  authorize the Azure CLI as a client, and neither `az account get-access-token
  --resource api://...` nor an MSAL device-code flow against it will mint a token) hit
  the live backend directly against the single existing Open shift
  (`3999a386-03f2-4a12-a3de-d105f867fffe`), reused sequentially for both cases (no new
  shift creation needed, since neither test identity is a coordinator). Both cases
  deliberately claimed with a stale pre-claim `rowVersion` (not a freshly re-fetched
  one) to exercise the actual fixed code path — the `StaleRowVersion` concurrency
  branch, per the PR #22 fix description above — rather than any other route that might
  reach the same error code.
  - **Self-claim-retry:** `409 SHIFT_ALREADY_CLAIMED`, `"You have already claimed this
    shift."` — self-specific wording confirmed, not the "someone else" variant.
  - **Other-user-claim:** `409 SHIFT_ALREADY_CLAIMED`, `"This shift was just claimed by
    someone else — please refresh and choose another."` — confirmed.
  - **Audit regression check:** `AuditEntries` went from 4 → 8 rows (one clean
    Claimed/Released pair per case); the rejected self-retry and the rejected
    other-user attempt wrote **zero** spurious rows — confirms the audit-write path is
    unaffected by this fix, exactly as expected.
  - `Users` table went 1 → 3 rows (`MikeTest1`/`Mike Test 2` auto-provisioned on first
    authenticated call, both `IsCoordinator=false`) — expected first-login behavior, not
    an anomaly.
  - Shift confirmed back to `Open` after both cases. Token handoff file
    (`~/forge-smoke-test-tokens.txt`, outside both repos, confirmed absent from `git
    status`), the temporary firewall rule, and the Postgres server were all cleaned up
    and independently re-verified (rule list shows only `AllowAzureServices`; server
    `state` confirmed `Stopped`; az CLI confirmed back on the `forge-deploy-staging` SP
    session) immediately after.

  Full narrative: `docs/CLAUDE-archive-2026-08-req2026-03.md` and the newest
  `docs/FORGE-context_v*.md` (maintained by the Claude.ai side of the two-tool
  workflow) — the "still not run" open item there should be marked closed to match.

**Standing convention — ad hoc fix-PR branch naming AND tracking-issue body line
(decided 2026-08-13, re-confirmed and extended 2026-08-27 per Items #9/#15):** any ad
hoc fix PR (human- or Claude-opened, not agent-opened) against `forge-demo-apps` must:
1. Use branch name `feature/fix-<short-description>`, not bare `fix/*` — `notify-forge.yml`'s
   dispatch filter is `startsWith(head.ref, 'feature/')`, so `feature/fix-*` already gets
   forwarded to `04-qa.yml`/`05-security.yml` for a real scan. Bare `fix/*` (or any other
   prefix, e.g. `chore/*`) is never forwarded and hits the permanently-unsatisfiable
   `security-check` branch-protection gate, needing an admin merge every time.
2. Include a `Related FORGE tracking issue: Flamespiker/forge-template#N` line in the PR
   body — `workflow_glue.py`'s `resolve_tracking_issue()` (used by `04-qa.yml`/
   `05-security.yml`) hard-requires this line and has no fallback; a PR missing it fails
   outright at that step even on a correctly-named `feature/fix-*` branch.

**Item #9 re-verified live 2026-08-27, closed — no code fix needed:** the `feature/`
prefix match in `notify-forge.yml` already works correctly for `feature/fix-*`, confirmed
against real PR history rather than assumed:
- **PR #27** (`feature/fix-appinsights-core-js-dedupe`, follows the convention) — `notify`
  dispatch: `SUCCESS`; `security-check` ran for real and returned `SUCCESS`.
- **PRs #7, #8, #11, #16** (the original 4 admin-merge cases) — all used bare `fix/*`,
  which *predates* this convention (PR #16 merged the same day the convention was
  decided). Correctly excluded by design, not a dispatch bug.
- **PRs #28, #29** (cited as recent evidence the gap still existed) — actually used
  `chore/verify-build-workflow` / `chore/verify-build-fix-backend-context`, neither of
  which is `feature/fix-*` at all. Correctly skipped for a different reason: the
  convention simply wasn't used, not a filter bug.
No `notify-forge.yml` change was made. The remaining risk is purely a human/Claude
process one (forgetting the convention), covered by point 1 above.

**Item #15 closed 2026-08-27 — Option A (process fix), per Mike's explicit choice over
Option B (a `resolve_tracking_issue()` code-level fallback):** documented as point 2
above rather than making `resolve_tracking_issue()` tolerant of a missing line — keeps
that function's existing contract (a tracking issue must be identifiable) intact for
every other caller. No live throwaway-PR re-test was run for this closure — the
underlying mechanics (a present tracking-issue line resolving correctly) are already
proven by `design_agent.py`/`implementation_coordinator.py`'s existing behavior and by
PR #27 above; only the process discipline of remembering to include the line on an ad
hoc PR is new. Historical occurrence: PR #21 hit exactly this gap (both QA and Security
failed at `resolve-tracking-issue` until the body was manually edited and the dispatch
manually replayed).

**Files that exist (`forge-template`):**

```
core/agents/utils/
    __init__.py
    github_helper.py
    ado_helper.py
    file_io.py
    claude_agent_wrapper.py
    managed_agents_wrapper.py
    smoke_tests/
        __init__.py
        smoke_github.py
        smoke_ado.py
        smoke_file_io.py
        smoke_claude_agent.py
        smoke_managed_agents.py
core/agents/
    intake_agent.py
    ingestion_agent.py
    requirements_agent.py
    design_agent.py
    implementation_coordinator.py
    qa_agent.py
    security_agent.py
    deploy_agent.py
    create_ado_items.py
    workflow_glue.py
core/agents/subagents/
    __init__.py
    backend_agent.py
    frontend_agent.py
    test_writer_agent.py
core/agents/templates/dockerfiles/
    dotnet-web.Dockerfile.template
    dotnet-worker.Dockerfile.template
    nextjs.Dockerfile.template
core/decisions/
    0011-base-anthropic-client.md
.github/workflows/
    00-intake.yml
    01-requirements.yml
    02-design.yml
    03-implementation.yml
    03b-recover-implementation.yml
    04-qa.yml
    05-security.yml
    06-deploy.yml
requirements.txt
.env.example
```

Also, in `forge-demo-apps` (not this repo): `.github/workflows/notify-forge.yml` and
`.github/workflows/design-pr-security-noop.yml` — see "Pipeline Wiring & Triggers" below.

---

## Python Environment

### Required packages (see requirements.txt)

Install with:
```
pip install -r requirements.txt
```

Individual installs done during this session (all now in requirements.txt):
```
pip install openpyxl
pip install PyYAML
pip install python-dotenv
pip install anthropic
```

### Semgrep — SAST scanner for the Security Agent (added Step 3.9)

`requirements.txt` gained a new dependency block (placed after the `anthropic` entry):
```
semgrep>=1.90.0
```

Semgrep is the only one of the Security Agent's three scanners that's pip-installable.
Gitleaks and OWASP Dependency-Check are **not** — both are standalone binary installs,
still outstanding (see Outstanding section below). Don't add them to `requirements.txt`;
document their install steps here once confirmed.

**Verified 2026-08-04:** `pip install -r requirements.txt` installed cleanly —
`semgrep-1.172.0` — and `semgrep --version` confirms it's on PATH.

Side effect noted during install: pip's resolver also downgraded two packages already
present in this environment that aren't in `requirements.txt` — `pywin32` (312→311) and
`mcp` (1.29.0→1.23.3, pulled in as a semgrep transitive dependency's pin). Not something
FORGE's own dependency list controls; flagged in case anything else on this machine
depends on the newer `mcp`.

---

## Agent Invocation & Infrastructure Reference

### Agent invocation — anthropic Messages API (ADR-0011)

- All non-Stage-3 agents use the **`anthropic`** Python package directly
  (`import anthropic` → `anthropic.Anthropic().messages.create(...)`)
- Each call is a single-turn Messages API request — system prompt + user prompt → text response.
  There is no tool-use loop; FORGE's Python layer handles all file I/O for these stages.
- `invoke_agent()` signature: `system_prompt`, `user_prompt`, `max_tokens` (required),
  `model`, `stage_name`, `request_id`. The `allowed_tools` parameter is gone.
- Stage 3 (Implementation) uses **raw `requests`** for the Managed Agents beta REST endpoints
  (separate mechanism entirely — see managed_agents_wrapper.py and ADR-0010).

**Why not claude-agent-sdk?** ADR-0011: the SDK bundled the Claude Code CLI subprocess,
imposing ~25,700 tokens of fixed overhead (~$0.10 cold-call cost) and a ~10-second launch
latency floor on every call, even though all six stages were already passing `allowed_tools=[]`
— the tool-use capability was provisioned but never exercised. The switch eliminates that
overhead with no loss of capability for these stages.

### AgentResult — token/cost fields (IMPORTANT: read before using for cost tracking)

`invoke_agent()` returns an `AgentResult` dataclass. The JSON log line emits:
- `input_tokens`, `output_tokens`, `cache_creation_tokens`, `cache_read_tokens`
- `total_cost_usd`, `num_turns`, `stop_reason`, `latency_seconds`

Grep for `"forge_event": "agent_invocation"` in Actions logs to find all invocations.

**total_cost_usd is computed from a rate table in the wrapper — not supplied by the API:**

The Messages API returns token counts only. `claude_agent_wrapper.py` maintains `_MODEL_RATES`,
a per-model USD-per-MTok table, and computes `total_cost_usd` from the response usage object.
If the model is not in the table, `total_cost_usd` is `None` and a warning is logged.

Current rates in `_MODEL_RATES` (source: `platform.claude.com/docs/en/about-claude/pricing`, 2026-07-29):

| Model | input | output | cache_write (5-min) | cache_read |
|-------|-------|--------|---------------------|------------|
| claude-sonnet-4-6 | $3.00/MTok | $15.00/MTok | $3.75/MTok | $0.30/MTok |
| claude-opus-4-6   | $5.00/MTok | $25.00/MTok | $6.25/MTok | $0.50/MTok |
| claude-haiku-4-5  | $1.00/MTok |  $5.00/MTok | $1.25/MTok | $0.10/MTok |

**Document 3 cost tables must key off `total_cost_usd`, not raw token counts.**

For plain Messages API calls (no `cache_control`), `cache_creation_tokens` and
`cache_read_tokens` will both be zero; cost = `(input × input_rate + output × output_rate) / 1M`.

### GitHub App token generation

`github_helper.py` uses PyJWT + raw requests for the App JWT exchange (not PyGithub).
`actions/create-github-app-token@v3` is required in CI (not `@v1` — deprecated Node 20).
The action uses `client-id` input, not `app-id`.

Credentials in `forge-template` repo:
- `FORGE_APP_ID` — secret
- `FORGE_APP_PRIVATE_KEY` — secret (multiline PEM; in `.env` wrap in double quotes to preserve real newlines)
- `FORGE_APP_CLIENT_ID` — **variable** (not secret — publicly visible on the App settings page)

**`_build_app_jwt()`'s `exp` claim must be computed from `issued_at`, not `now`** — GitHub
hard-rejects JWTs where `iat`-to-`exp` exceeds 10 minutes; computing `exp` as `now + 600`
on top of an already-skewed-back `iat` (clock-drift padding) silently exceeded that window
project-wide until fixed (found while retrying REQ-2026-03's Design stage).

### github_helper.py — two auth contexts, two repo targets

| Function | Auth | Target repo |
|---|---|---|
| `post_comment`, `remove_label` | `GITHUB_TOKEN` | `forge-template` (tracking issue lives here) |
| `add_label` | App installation token | `forge-template` |
| `create_branch`, `commit_files`, `open_pr`, `get_file_contents`, `post_pr_comment`, `get_pr_comments`, `get_pr`, `create_check_run`, `create_review_with_comments`, `create_single_review_comment`, `delete_files`, `list_open_prs_by_head` | App installation token | `forge-demo-apps` (cross-repo work) |

`add_label` moved off `GITHUB_TOKEN` because GitHub Actions' anti-recursion rule means a
`GITHUB_TOKEN`-authored label change never triggers a new workflow run — this silently
broke `06-deploy.yml`'s label-driven dispatch for every agent-applied
`qa-approved`/`security-approved` until fixed (see "Pipeline Wiring & Triggers" below).

- `FORGE_SOURCE_REPO` env var names the orchestration repo (default: `forge-template`)
- `FORGE_TARGET_REPO` env var names the monorepo (default: `forge-demo-apps`)
- **Do NOT add `GITHUB_TOKEN` as a GitHub Actions secret** — Actions injects it automatically for same-repo workflows. Storing it as a secret would shadow the automatic token. Local dev only: fine-grained PAT scoped to `forge-template`, Issues R/W.

### commit_files() — Git Data API

`commit_files(branch_name, files: dict[str, str], commit_message)` writes files to a branch in `forge-demo-apps` via the Git Data API (blob → tree → commit → ref update). Required by Stage 3 (3.4/3.4a). Commits are attributed to `forge-pipeline[bot]` and verified by GitHub.

### ADO helper

Reads `ado.org_url` and `ado.project` from `team/config.yaml` at import time.
Auth: HTTP Basic with blank username and PAT as password (standard ADO pattern).

### file_io.py — Intake Template parsing

**Requirements sheet:**
- Header row found by searching **column A only** for `"Req #"` (case-insensitive substring)
- Row numbers are NOT assumed — title rows sit above the header in the real template
- A row is included if and only if the **User Story / Requirement cell (column index 3) is non-empty**
- No example-row heuristic — BAs are instructed to replace/delete examples before submitting

**Overview sheet:**
- Section headers detected by **substring match** on column A (case-insensitive)
- Keys in the returned dict are **canonical snake_case**, not raw cell text:

  | Canonical key | Matches substring |
  |---|---|
  | `request_identification` | `"request identification"` |
  | `request_type` | `"request type"` |
  | `problem_purpose` | `"problem"` |
  | `success_criteria_scope` | `"success criteria"` |
  | `constraints_considerations` | `"constraints"` |
  | `additional_context` | `"additional context"` |

- Overview values are **`{field_label: field_value}` dicts** — column B = label, column C = value.
  e.g. `overview["request_identification"]["Request ID"]` → the BA's value directly.
  Empty dict `{}` if the BA left the section blank.

**Bracket-placeholder stripping (added during Step 3.2):**
- Unfilled template cells retain the instructional example text, e.g. `[Example: FORGE-2026-001 ...]`
- Any Overview value that starts with `[` AND ends with `]` is treated as blank (set to `None`)
- This prevents example text from reaching Claude as if it were real BA input, and saved 418 tokens
  on the first live Intake Agent run

**Real parsed output confirmed against `docs/Intake Template.xlsx`:**
- Overview: all six canonical keys present, each a dict of field_label → value pairs
- Requirements: R-001 through R-004 parsed correctly (Functional/Non-Functional, High/Medium/Low)

### intake_agent.py — Stage 0b

Entry point: `python -m core.agents.intake_agent --spreadsheet <path> --issue-number <n>`

- `--dry-run` flag: calls Claude and prints the comment to stdout without posting to GitHub or applying the label. Used for local review before the real pipeline is wired in Phase 4.
- `--request-id`: optional override; defaults to the spreadsheet's `Request ID` field (after bracket-placeholder stripping). Falls back to `"unknown"` if blank.
- `_MAX_TOKENS = 2048` — sufficient for 5–7 questions; adjust if the output regularly hits the ceiling.
- `sys.stdout.reconfigure(encoding="utf-8")` is the first line of `main()` — required on Windows to prevent `UnicodeEncodeError` when printing the 🧭 emoji in the comment header.

**Exception handling pattern (per ADR-0011):**
`invoke_agent()` is wrapped in `try/except` at the call site. On failure the agent posts a
structured failure comment to the tracking issue (best-effort) before re-raising, so the
GitHub Actions job fails loudly with a visible GitHub comment rather than silently. All six
stage agent scripts must follow this pattern.

### ingestion_agent.py — Stage 0a (Codebase Ingestion, Phase 7 step 7.1)

Entry point:
```
python -m core.agents.ingestion_agent --request-id REQ-2026-03 --existing-service REQ-2026-03 --issue-number 42
python -m core.agents.ingestion_agent --existing-service REQ-2026-03 --dry-run
```

Only ever runs for Enhancement-flagged requests (Document 07: Stage 0a's trigger is
Locked to Enhancement, never Greenfield). Despite the "0a before 0b" naming, it
actually runs *after* the intake spreadsheet has been parsed once — the Enhancement
flag and existing service name only become known at that point. Wired as a
conditional step inside `00-intake.yml` itself (see "Pipeline Wiring & Triggers"
below), not a separate workflow — runs in parallel with the BA's clarification
round rather than adding a sequential hop. Not human-gated (Document 01 §3.0a) —
posts no comment on success, only on failure/mismatch.

- `github_helper.get_repo_tree(path_prefix, branch="main")` (new) — lists every
  blob under a path prefix via the Git Trees API (`recursive=1`). Confirmed live:
  a bare branch name resolves directly, no separate branch→SHA lookup needed.
- **File selection (two-pass, budget-conscious):** tree pass filters out noise
  (`node_modules`/`bin`/`obj`/`.next`/`dist`/`coverage`/`.git` dir segments;
  `package-lock.json`/`yarn.lock`/`tsconfig.tsbuildinfo`/image/font extensions —
  `tsconfig.tsbuildinfo` confirmed live as real, unanticipated noise, ~100KB).
  Content pass always fetches manifest/config files in full (`*.csproj`,
  `package.json`, `tsconfig.json`, `openapi.yaml`, `Program.cs`/`Startup.cs`,
  `appsettings*.json`), then fills a ~60k-character budget with the largest
  remaining source files by size, descending.
- **Layer 2 backstop (existing-service mismatch):** if `get_repo_tree()` finds zero
  blobs under `services/<existing_service>/`, raises `EnhancementServiceNotFoundError`
  (non-zero exit, red step) and posts a best-effort comment naming the mismatch —
  never silently falls back to guessing `request_id` or any other value. Same
  "strict rejection over silent auto-remap" precedent as Open Item #8's `.github/`
  guard. Distinct from a clean Greenfield no-op (which never invokes this agent at
  all). The mismatch comment respects `--dry-run` (printed, not posted) exactly like
  every other agent's dry-run contract.
- **Output:** `commit_files()` to `docs/<request_id>/existing-architecture-summary.md`
  on `pipeline-state` (same branch/rationale as `requirements.md`).
- **Important:** any comment this agent posts (mismatch or generic ADR-0011 failure)
  must carry the `forge:agent-comment` marker — an unmarked comment would be
  misread as a BA answer by `requirements_agent.py`'s clarification-answer parsing.

**Fix during template work:** `docs/Intake Template.xlsx`'s "If Enhancement —
Existing Service Name" field example was `client-portal (the folder name under
services/...)` — a descriptive-slug example that didn't match the real
`services/REQ-2026-0X/` request-ID-based naming convention. Corrected to a real
`REQ-2026-03`-style example so a BA following the example produces a value the
Ingestion Agent can actually resolve.

**Live-verified 2026-08-27** via three real throwaway tracking issues
(`forge-template#7`/`#8`/`#9`, all closed after verification):
- **Case A (Greenfield no-op):** real REQ-2026-03 intake spreadsheet (re-downloaded
  from the real tracking issue `forge-template#6`) → `00-intake.yml`'s new
  "Determine Enhancement status" step correctly logged `Request Type = 'Greenfield'
  -- Greenfield or unrecognized, skipping Ingestion.` and the "Run Ingestion Agent"
  step correctly no-opped.
- **Case B (Enhancement happy path):** scratch request `REQ-TEST-01`, existing
  service `REQ-2026-03` → Intake Agent posted its own clarifying questions AND
  Ingestion Agent independently committed a real, accurate 14792-char
  `existing-architecture-summary.md` to `pipeline-state` — both succeeded without
  interfering with each other. Scratch artifact deleted after verification.
- **Case C (Layer 2 mismatch):** scratch request `REQ-TEST-02`, existing service
  `REQ-NONEXISTENT-999` → "Run Ingestion Agent" step correctly exited non-zero
  (real job status: `failure`), and a real, correctly-marked mismatch comment was
  posted (confirmed via the GitHub API, not dry-run) naming the bad value. The
  generic pre-agent-failure-comment step correctly stayed silent (ingestion_agent.py
  self-reported). Comment left in place on the closed issue as evidence.
- All three runs confirmed on the pushed `main` branch (not a stale local-only
  version) after an earlier same-day run first surfaced that the local commits
  hadn't yet been pushed to `origin` — the first Case A attempt ran against the
  pre-Phase-7 workflow and had to be redone after `git push`.

`requirements_agent.py`/`design_agent.py` both gained an optional
`existing-architecture-summary.md` fetch (see their own subsections below) — zero
regression confirmed live (real dry-runs) when the file is absent, which is every
request prior to this phase.

### file_io.py — formatting helpers (added Step 3.3)

Two new public functions render parsed spreadsheet data as Markdown for LLM prompts:

- `format_overview_markdown(overview: dict) -> str` — renders all six Overview sections; sections
  with no BA input show `_(left blank by BA)_` rather than being omitted.
- `format_requirements_markdown(requirements: list[dict]) -> str` — renders each requirement row
  with req number, type, priority, user story, acceptance criteria, and notes.

Both live in `file_io.py` (not in agent scripts) so every stage agent can import them without
duplicating the formatting logic.

### github_helper.py — get_issue_comments() (added Step 3.3)

`get_issue_comments(issue_or_pr_number: int) -> list[dict]`

Retrieves all comments on a tracking issue in `forge-template`, oldest first. Uses `GITHUB_TOKEN`.
Each returned dict includes `"id"`, `"user"` (with `"login"`), `"body"`, `"created_at"`.

**Agent comment marker (added Step 3.3):**
Every agent-authored comment begins with an invisible HTML marker:
`<!-- forge:agent-comment stage=<stage> request_id=<id> -->`

The Requirements Agent (and all subsequent agents) uses `_is_agent_comment()` to filter out
FORGE-authored comments from the issue thread, treating only the remaining comments as
BA/human input. This identification is based on the marker body text, NOT on the GitHub
account/login — safe even if the bot account changes.

### requirements_agent.py — Stage 1

Entry point: `python -m core.agents.requirements_agent --spreadsheet <path> --issue-number <n> --request-id <id>`

- `--request-id` is **required** for a real run (determines `docs/<request-id>/` path in the
  monorepo). Omitting it on a real run raises `ValueError` rather than silently writing to
  `docs/unknown/`.
- `--dry-run` flag: fetches comments, calls Claude, prints `requirements.md` and
  `ado-work-items.json` to stdout. Does NOT commit or post.
- `_MAX_TOKENS = 8000` — model produces ~3,500–3,900 output tokens for a 4-requirement intake.
  Raise if output is regularly truncated (`stop_reason == "max_tokens"`).
- Structured output via `invoke_agent(..., output_schema=SCHEMA)` (Item #31, 2026-08-31) —
  `result.structured_output` is read directly as a dict; no separate JSON-parsing function
  exists anymore. The forced tool-use call guarantees the shape, so a malformed response
  now surfaces as a wrapper-level `RuntimeError` (raw response persisted to disk for
  diagnosis first), not a `json.JSONDecodeError` from this file.
- **Phase 7 step 7.1:** for an Enhancement-flagged spreadsheet, also attempts to fetch
  `docs/<request_id>/existing-architecture-summary.md` from `pipeline-state` (committed by
  `ingestion_agent.py`, Stage 0a) and folds it into the prompt. A 404 is tolerated (logged,
  proceeds without it); any other fetch error propagates into the existing failure-comment
  path. See "ingestion_agent.py — Stage 0a" above.

**Output artifacts (committed to `forge-demo-apps` on the `pipeline-state`
branch, not `main`** — moved off `main` in the Phase 4 step 4.8 retrofit once
branch protection required a PR review for every push to `main` with no
bypass available on this personal-account repo; `pipeline-state` is a
dedicated, intentionally-unprotected bookkeeping branch, created once and
reused across every request, not per-request like `design/<request-id>`/
`feature/<request-id>`):**
- `docs/<request-id>/requirements.md` — full structured requirements document
- `docs/<request-id>/ado-work-items.json` — draft ADO hierarchy (Epic → Features → User Stories)

**ADO payload shape:**
```json
{
  "epic": {"title": "...", "description": "..."},
  "features": [
    {
      "title": "...", "description": "...",
      "user_stories": [
        {
          "title": "...", "description": "...",
          "acceptance_criteria": "...",
          "source_req_number": "R-001"
        }
      ]
    }
  ]
}
```
Every requirement row maps to exactly one User Story; `source_req_number` preserves traceability
back to the spreadsheet. ADO work items are NOT created by this agent — only after a human
applies `requirements-approved` (Phase 4 wiring).

### Managed Agents API — current schema (verified against Anthropic reference docs)

**Agent creation — multi-step, no inline subagents:**
- `name` is required on every `POST /v1/agents` call
- Subagents must be created as separate agent resources first, then the coordinator references them by ID:
  ```json
  "multiagent": {"type": "coordinator", "agents": ["<subagent_id>", ...]}
  ```
- The old `"subagents": [...]` inline field is gone — rejected with HTTP 400 (`"unknown field subagents"`)
- Coordinator needs `"tools": [{"type": "agent_toolset_20260401"}]` to delegate; omit when no subagents

**Resource hierarchy — all top-level, not nested:**
- `POST /v1/environments` (body: `{"name": ..., "config": {"type": "anthropic_cloud"}}`)
- `POST /v1/sessions` (body: `{"agent": {"type": "agent", "id": ..., "version": ...}, "environment_id": ...}`)
- Old nested paths (`/v1/agents/{id}/environments`, `/v1/agents/{id}/environments/{eid}/sessions`) no longer exist

**`create_agent_session()` return dict keys:** `coordinator_id`, `coordinator_version`, `subagent_ids`, `environment_id`, `session_id`
(old key `agent_id` is gone — use `coordinator_id`)

**Error detection — do NOT treat `idle` status as success:**
- Errors surface as `session.error` events in the event stream, not as a distinct status
- `poll_until_idle()` scans `GET /v1/sessions/{sid}/events` after reaching idle and raises on any `session.error` events
- `session.status_idle` event carries `stop_reason.type`:
  - `"end_turn"` → completed normally
  - `"requires_action"` → blocked on tool confirmation — unexpected in FORGE's autonomous mode, raises explicitly

**Session status values:** `idle`, `running`, `rescheduling`, `terminated`
(old states `failed`, `cancelled` no longer exist; `terminated` = unrecoverable orchestration error)

**Archive order:** session → environment → coordinator agent → each subagent agent
`archive_session(coordinator_id, environment_id, session_id, subagent_ids=[...])`

**Audit trail:** `get_subagent_audit_trail()` uses `GET /v1/sessions/{sid}/threads` — returns one thread per agent (coordinator has `parent_thread_id=null`; subagents have `parent_thread_id` set and `agent.name` identifying them). Per-thread events at `GET /v1/sessions/{sid}/threads/{tid}/events`.

**Other unchanged behaviours:**
- Beta header: `managed-agents-2026-04-01` required on every request
- Events endpoint body must be nested: `{"events": [{"type": "user.message", "content": [...]}]}`
- Archive race condition: session can flip `idle → running` briefly; archive wrapped in 3-attempt exponential-backoff retry (2s base)
- Model split per ADR-0010: coordinator = Opus tier, subagents = Sonnet tier (`FORGE_COORDINATOR_MODEL` / `FORGE_SUBAGENT_MODEL`)

---

## Smoke Tests

Located in `core/agents/utils/smoke_tests/`. Run manually from the repo root — NOT part of CI.

```bash
python -m core.agents.utils.smoke_tests.smoke_file_io       # no credentials needed
python -m core.agents.utils.smoke_tests.smoke_claude_agent  # needs ANTHROPIC_API_KEY
python -m core.agents.utils.smoke_tests.smoke_ado           # needs ADO_PAT
python -m core.agents.utils.smoke_tests.smoke_github        # needs all FORGE_APP_* vars
python -m core.agents.utils.smoke_tests.smoke_managed_agents # needs ANTHROPIC_API_KEY + beta access
```

Copy `.env.example` to `.env` and fill in values before running. `.env` is gitignored.

---

## Smoke Test Status

| Test | Status | Notes |
|------|--------|-------|
| `smoke_file_io` | **PASSED 7/7** | Path bug fixed (`parents[5]` → `parents[4]`); xlsx + markdown + yaml all passing |
| `smoke_claude_agent` | **PASSED 5/5** | Rewritten for anthropic Messages API (ADR-0011); rate-table cost verified ($0.00021 for 30in/8out tokens on Sonnet 4.6) |
| `smoke_ado` | **PASSED 4/4** | Fixed: drop `System.State` from all four `_make_patch` calls — only `"New"` is valid as initial state in FORGE-Build |
| `smoke_github` | **PASSED 8/8** | post_comment/add_label retargeted to forge-template; commit_files + open_pr verified against forge-demo-apps; get_file_contents round-trip added (Step 3.4) |
| `smoke_managed_agents` | **PASSED 10/10** | Extended for Files API: specialist writes file to /mnt/session/outputs/, list_session_output_files + download_file_content verified, content match exact, 4-thread audit trail, archive clean |

`.env` vars needed: `FORGE_APP_ID`, `FORGE_APP_PRIVATE_KEY`, `FORGE_APP_CLIENT_ID`, `FORGE_GITHUB_OWNER`, `FORGE_TARGET_REPO`, `FORGE_SOURCE_REPO`, `GITHUB_TOKEN`, `ADO_PAT`, `ANTHROPIC_API_KEY`

**PEM format in `.env`:** wrap the full key in double quotes to preserve real newlines — `python-dotenv` requires this for multiline values. A trailing `""` (double double-quote) will break parsing.

---

## Pipeline Stage Reference (Agent-by-Agent)

Phase 3 and Phase 4 are both complete. The original step-by-step checklist (Steps
3.1-3.10, Build Plan 4.1-4.9) and every dated live-run verification live in
`docs/CLAUDE-archive-2026-08-phase3-5.md`.

---

### github_helper.py — get_file_contents() (added Step 3.4)

`get_file_contents(path: str, branch: str = "main") -> str`

Reads a file from the target monorepo (`forge-demo-apps`) via the GitHub Contents API.
Uses the GitHub App installation token (same auth context as `create_branch`/`commit_files`).
Decodes the base64-encoded response body and returns UTF-8 string content.
Required by the Design Agent (and all subsequent agents) to read artifacts committed by
earlier pipeline stages without needing a local checkout of the monorepo.

### file_io.py — format_stack_preferences_markdown() (added Step 3.4)

`format_stack_preferences_markdown(prefs: dict) -> str`

Renders a parsed `team/stack-preferences.yaml` dict as Markdown for an LLM prompt.
Team-layer fields still at their template placeholder value (any string starting with
`"your-"`) are called out as **not yet set** so the Design Agent proposes a default and
flags it for Technical Approver confirmation rather than presenting it as a settled standard.

### design_agent.py — Stage 2

Entry point: `python -m core.agents.design_agent --issue-number <n> --request-id <id>`

- `--request-id` is **required** for a real run (determines `docs/<request-id>/` path and
  `design/<request-id>` branch in the monorepo).
- `--dry-run` flag: fetches `requirements.md` + stack prefs, calls Claude, prints all three
  artifacts to stdout. Does NOT create a branch, commit, or post.
- `--stack-preferences`: local path to `team/stack-preferences.yaml` (default). No GitHub
  API call needed — the file lives in `forge-template`, available in the local checkout.
- `_MAX_TOKENS = 20000` — model produces ~12,700 output tokens for a 4-requirement intake.
- First stage to use the full `create_branch() → commit_files() → open_pr()` chain.
- `yaml.safe_load()` validates the model's `openapi_yaml` before committing — rejects
  malformed YAML and posts a failure comment instead of committing broken output.
- **Phase 7 step 7.1:** also attempts the same `existing-architecture-summary.md` fetch as
  `requirements_agent.py` — but unconditionally (this agent never reads the original
  spreadsheet, so it has no direct Greenfield-vs-Enhancement signal; a 404 degrades
  identically either way). See "ingestion_agent.py — Stage 0a" above.

**Output artifacts (committed to `forge-demo-apps` on `design/<request-id>` branch):**
- `docs/<request-id>/design.md` — C4 architecture narrative, component breakdown, tech choices
- `docs/<request-id>/openapi.yaml` — OpenAPI 3.0 API contract (YAML-validated before commit)
- `docs/<request-id>/tasks.md` — implementation task breakdown for Backend / Frontend / Test Writer subagents

A draft PR is opened against `main` in `forge-demo-apps`; a summary comment linking to the
PR is posted on the FORGE tracking issue. Human merges the PR → applies `design-approved`
label → triggers Implementation (Gate 2, Document 6).

### managed_agents_wrapper.py — Files API additions (added Step 3.5)

`_FILES_API_BETA = "files-api-2025-04-14"` — separate beta constant from `_BETA_HEADER`.

`_files_headers() -> dict` — builds headers with **both** beta values comma-separated
(`files-api-2025-04-14,managed-agents-2026-04-01`). Both are required together when
scoping a file list to a session via `scope_id`; omitting either causes 400 or silent
mis-filtering.

`list_session_output_files(session_id, limit=100) -> list[dict]` — lists files persisted
from `/mnt/session/outputs/` in the session sandbox. Only files written to that exact
path are visible; scratch files elsewhere in the container are discarded on archive.

`download_file_content(file_id) -> bytes` — downloads raw bytes for a file ID returned
by `list_session_output_files`. Returns binary-safe bytes (caller decodes as needed).

### core/agents/subagents/ — specialist subagent configs (added Step 3.5)

`__init__.py` — exports `DEFAULT_SCOPED_TOOLS`: `agent_toolset_20260401` with
`always_allow` permission policy and `web_search`/`web_fetch` disabled. All three
specialists use this (offline, deterministic code generation — no network egress).

Also exports `SHARED_DOCS_DIR = "/mnt/session/shared-docs"` (added in the shared-docs
retrofit below) — the one path constant both the coordinator and Backend/Frontend
import, so neither side can silently disagree on where design.md/openapi.yaml/tasks.md
live on the sandbox filesystem.

`backend_agent.py` — .NET specialist. `get_config(service_root)` returns name +
system prompt (writes to `<service_root>/backend/`) + scoped tools. Instructs the
agent to run `dotnet build` and fix compile errors before declaring done.

`frontend_agent.py` — Next.js/TypeScript specialist. `get_config(service_root)` writes
to `<service_root>/frontend/`. TypeScript mandated (no `.js`/`.jsx`). Instructs `npm run build`.

`test_writer_agent.py` — xUnit + Jest specialist. `get_config(service_root)` targets
both backend and frontend directories. Reads subagent output from shared filesystem
rather than waiting for an explicit hand-off. Instructs `dotnet test` + `npm test` sanity check.

### implementation_coordinator.py — Stage 3

Entry point: `python -m core.agents.implementation_coordinator --issue-number <n> --request-id <id>`

- `--request-id` is **required** for a real run (determines `services/<request-id>/` target dir
  and `feature/<request-id>` branch).
- `--dry-run`: runs the REAL Managed Agents session (no cheap substitute exists for this), but
  skips commit/PR/comment. Prints session ID, Console link, and file list.
- Reads `design.md`, `openapi.yaml`, `tasks.md` from `forge-demo-apps` `main` via `get_file_contents()`.
  **Prerequisite: the Design Agent's PR must be merged to `main` before running.**

**Packaging convention:** coordinator tars the entire `services/<request-id>/` tree into
`/mnt/session/outputs/implementation.tar.gz` before finishing. Python's `tarfile` module
(not the model) reconstructs the exact path dict `commit_files()` expects. This sidesteps
any ambiguity about whether the Files API's flat `filename` field preserves nested paths.

**`_extract_archive_to_file_dict(archive_bytes, expected_prefix)`** — extracts the tar.gz,
filters members to those starting with `expected_prefix` (guards against wrong working dir),
decodes UTF-8 (raises `ValueError` on binary), returns `{path: content}` dict for `commit_files()`.

**Output on a real run:**
- All files committed to `feature/<request-id>` branch in `forge-demo-apps`
- Draft PR opened against `main`; summary comment (with session ID + Console link) posted to tracking issue

**Do NOT simply re-run `implementation_coordinator.py` after a kill/timeout like this.**
`create_agent_session()` runs again and creates a second, duplicate, billable set of
agents/environment/session on top of the one that may still be running or already
finished — an orphaned resource with no cleanup. Before retrying, check for the
`managed_agents_session_start` log line to recover the IDs, check whether
`feature/<request-id>` already exists on `forge-demo-apps` (a sign of a prior partial
completion), and prefer writing a resume script over a fresh invocation.

Also observed: `commit_files()`'s `git/trees` call 422'd once and succeeded immediately
on identical retry with no changes — treat a single `git/trees` 422 as possibly
transient GitHub API flakiness, not necessarily a real path/data conflict, and retry
before deep-diagnosing.

### Retrofit: Backend/Frontend read design docs from shared sandbox path, not coordinator relay (2026-07-30)

Previously Backend and Frontend only had design.md/openapi.yaml/tasks.md via the coordinator's
own paraphrase in its delegation message — the same relay risk that `test_writer_agent.py`
was already built to avoid for Backend/Frontend's *code* (it reads their files from the shared
filesystem directly rather than trusting a hand-off summary). This retrofit closes the same
gap for the design docs themselves: a paraphrased relay of a structured contract like
openapi.yaml risks a dropped or renamed field neither subagent could catch without the literal
source.

- `_COORDINATOR_SYSTEM_PROMPT` gained a new **step 0**, ahead of delegation: write
  design.md, openapi.yaml, and tasks.md verbatim to `{SHARED_DOCS_DIR}/design.md`,
  `{SHARED_DOCS_DIR}/openapi.yaml`, `{SHARED_DOCS_DIR}/tasks.md` before delegating to Backend
  and Frontend. Old steps 1–5 renumbered to 2–6.
- `backend_agent.py` / `frontend_agent.py` `SYSTEM_PROMPT` now instructs each specialist to
  read those files directly from `SHARED_DOCS_DIR` once the coordinator confirms they're
  written, rather than relying on the delegation message's summary.
- `SHARED_DOCS_DIR` ("/mnt/session/shared-docs") is intentionally outside `service_root`
  ("services/<request-id>"), so it is never swept into `implementation.tar.gz` — no change
  needed to the packaging tar command or `_extract_archive_to_file_dict()`.
- Coordinator's own delegation message can still summarize the docs for convenience; the
  requirement is only that Backend/Frontend treat the shared-path files as the source of
  truth, not the summary.

### github_helper.py — post_pr_comment() / get_pr_comments() (added Step 3.8)

`post_pr_comment(pr_number: int, body: str) -> dict` / `get_pr_comments(pr_number: int) -> list[dict]`

Both use the GitHub App installation token, targeting a PR in `forge-demo-apps` (not
`forge-template`). Needed by the QA Agent, which posts its test report on the feature
PR in the monorepo rather than on the FORGE tracking issue — `post_comment()`/
`get_issue_comments()` are same-repo-only (`GITHUB_TOKEN`) and cannot reach
`forge-demo-apps`. Both reuse the same `/issues/{number}/comments` endpoint shape as
`post_comment()`/`get_issue_comments()` (GitHub treats PRs as issues for comments) —
just a different repo and a different auth context.

### ado_helper.py — create_bug()'s parent_story_id is now optional (added Step 3.8)

`create_bug(title, repro_steps, severity, parent_story_id: int | None = None)`

Previously `parent_story_id` was required. As of the QA Agent (Step 3.8), Phase 4's
ADO item-creation step (4.3) hadn't been built/run for any request yet, so no real
ADO User Story IDs existed to link Bugs against. When `None`, `create_bug()` skips
the `link_items()` call and logs a warning instead of raising — the Bug is still
filed, just without a parent link. **Phase 4's `create_ado_items.py` (step 4.3) now
exists and writes real IDs to `docs/<request-id>/ado-work-items.json` on the
`pipeline-state` branch** (see the "Phase 4 — Pipeline Wiring" section) — callers
should now always pass a real ID once that script has run for a request; this
parameter stays optional in the function signature only so `create_bug()` doesn't
break on a request where it hasn't run yet (e.g. an older request, or before
`requirements-approved` triggers Design).

### qa_agent.py — Stage 4 (QA) (added Step 3.8)

Entry point: `python -m core.agents.qa_agent --issue-number <n> --request-id <id> --pr-number <n> --repo-path <path>`

Unlike every prior stage, QA needs the actual repository contents on disk to run
tests — not just individual file reads via the Contents API. Assumes a local
checkout of `forge-demo-apps` at the feature branch already exists at `--repo-path`
(populated by the invoking GitHub Actions job's own `actions/checkout` step, Phase 4
step 4.5, **not yet wired**). This script does not clone anything itself.

- Runs `dotnet test` (backend, parses the TRX report) and `npm test -- --ci --json
  --outputFile=...` (frontend, parses the Jest JSON report) against
  `services/<request-id>/{backend,frontend}` under `--repo-path`.
- Presence of the TRX/JSON report file (not process exit code) determines whether a
  suite actually ran — `dotnet test`/`npm test` also exit non-zero on mere test
  failures, so exit code alone can't distinguish "ran, some failed" from "never ran"
  (e.g. a compile error).
- Severity classification (`_classify_failure_severity()`) is a deterministic
  substring heuristic (Document 3: "FORGE automatic, not AI judgment") — assertion-
  library markers (`xunit.sdk`, `expect(`, `tobe(`, etc.) → Medium; anything else
  (unhandled exception/crash, build/run failure) → High. Claude is not asked to
  decide pass/fail or severity.
- Retry-attempt number is derived statelessly (ADR-0002): `1 + count of this
  agent's own prior comments on the PR`, identified by the
  `<!-- forge:agent-comment stage=qa request_id=<id> ... -->` marker via
  `get_pr_comments()`. No separate counter to keep in sync.
- `_MAX_RETRIES = 3` (Document 6: QA retries up to three times before escalating).
  Applies `qa-approved` (all pass), `qa-loop-back` (failures, attempts ≤ 3), or
  `qc-retry-limit-reached` (failures, attempts > 3) to the FORGE tracking issue.
- Claude is used only once per run: given the already-computed deterministic test
  summary (counts, failures, severities, bugs filed, attempt number, label), it
  writes the human-facing Markdown test report comment posted to the feature PR —
  instructed not to re-judge pass/fail or severity.
- `_resolve_parent_story_id(request_id)` looks for a real ADO User Story ID at
  `docs/<request-id>/ado-work-items.json`'s `primary_user_story_id` key, read
  from the `pipeline-state` branch (updated in the Phase 4 step 4.8 retrofit —
  was `main` before); returns `None` (logs a warning) if that request hasn't
  had `create_ado_items.py` run for it yet — see the `ado_helper.py` entry
  above. Bugs are filed either way.
- `--dry-run`: runs tests and computes everything (including the Claude call) but
  prints to stdout instead of filing ADO Bugs, posting to GitHub, or applying labels.

**Frontend runner auto-detection (added during the REQ-2026-03 fix cycle):**
`_detect_frontend_test_runner()` checks for a `vitest.config.{ts,js,mjs}` file or
`"vitest"` in `package.json`'s deps, defaulting to `jest`. Vitest's `--reporter=json`
output is close enough to Jest's schema that `_parse_jest_json()` handles both without a
separate parser — but see Open Items for its file-collection blind spot (a suite where
every file fails to *collect* reports 0/0/0 and is currently treated as a pass).

**`not_applicable` is a real third outcome, not a pass/fail variant (Phase 5 pre-flight
Fix 3):** a suite with no test script at all (`_frontend_test_script_exists()`) or no
`*.Tests.csproj` anywhere under the service root (`_resolve_backend_test_dir()`, which
globs for the real test project rather than assuming a fixed path) is reported as "not
applicable", never counts against the 3-attempt retry budget, and never files a synthetic
"suite failed to run" bug.

### github_helper.py — get_pr() / create_check_run() / create_review_with_comments() / create_single_review_comment() (added Step 3.9)

Four new functions, all using the GitHub App installation token against
`forge-demo-apps` (same auth context as `create_branch`/`commit_files`/
`post_pr_comment`):

- `get_pr(pr_number: int) -> dict` — fetches PR metadata; the Security Agent
  uses it only for `pr["head"]["sha"]`, needed to anchor the check run and
  inline review comments to the right commit.
- `create_check_run(head_sha, name, conclusion, title, summary) -> dict` —
  creates a completed GitHub check run (not "in progress" — the scan already
  finished by the time this is called). `name="security-check"` is the fixed
  string Build Plan 4.8's branch-protection rule requires as its required
  check.
- `create_review_with_comments(pr_number, commit_sha, comments: list[dict]) -> dict`
  — batches multiple line-anchored comments into a single PR review
  (`comments`: `{"path", "line", "body"}` dicts). Preferred over posting
  comments one at a time — fewer API calls, one review object instead of N.
- `create_single_review_comment(pr_number, commit_sha, path, line, body) -> dict`
  — single-comment fallback, used when the batch review call fails (most
  commonly because a finding's line falls outside the PR's diff — GitHub
  rejects review comments anchored to unchanged lines).

### security_agent.py — Stage 5 (Security)

Entry point: `python -m core.agents.security_agent --issue-number <n> --request-id <id> --pr-number <n> --repo-path <path>`

Like QA (Step 3.8), Security needs the actual repository contents on disk —
not just individual file reads via the Contents API — to run Semgrep and
Gitleaks against `services/<request-id>/` under `--repo-path`. This script
does not clone anything itself; the same "local checkout satisfies the
manual-invocation case" pattern from the QA Agent applies here too. The
third scanner, dependency vulnerabilities, is API-based (Dependabot, see
below) and does not need the local checkout at all.

- Runs all three scanners unconditionally, even if one fails — `ScanResult.ran`
  (set from report-file presence, not process exit code, same principle as
  QA's TRX/Jest-JSON check) lets the run continue and report partial results
  rather than aborting on the first tool failure.
- Severity mapping is fixed and deterministic per tool (Document 7: "Locked"),
  never an LLM judgment call:
  - **Gitleaks** → every finding is Critical (no lesser-severity category of
    its own). Test/fixture paths are excluded entirely via
    `team/gitleaks-allowlist.toml` before a finding can even reach this
    classifier — see below.
  - **Dependabot** → `security_advisory.severity` arrives pre-computed as
    critical/high/medium/low; mapped 1:1, Medium default if a future alert
    somehow lacks the field.
  - **Semgrep** → ERROR→High, WARNING→Medium, INFO→Low. Can never produce a
    Critical under this fixed table.
- `has_critical` (any Critical finding across all three tools) drives both
  the check-run conclusion (`failure` if true, else `success`) and the label
  (`security-approved` only if false — no label at all when Critical findings
  exist, since nothing should imply the block is lifted).
- Claude is used only once per run: given already-computed deterministic
  counts/severities/conclusion, it writes the short human-facing overview
  comment — instructed not to re-judge severity or write individual finding
  bodies. Individual findings are posted separately as inline PR review
  comments (`post_findings()`), built entirely by deterministic string
  formatting, no LLM involved.
- `_GITLEAKS_ALLOWLIST_CONFIG` (`team/gitleaks-allowlist.toml`) is passed to
  Gitleaks via `--config` if the file exists; if missing, `_run_gitleaks()`
  logs a warning and falls back to Gitleaks' default ruleset with no
  test-path exclusions, rather than failing the run.
- Unlike QA, there is no retry-loop/attempt-counting — Document 6 has no
  `security-loop-back` label. Security re-scans on every PR update; the
  failing check run itself blocks merge until findings are resolved.
- `--dry-run`: runs all three scans and the Claude call, prints the scan
  summary/overview comment/check-run verdict/label decision to stdout, but
  posts nothing, creates no check run, and applies no label.


**Verdict gating also considers scanner-run failures, not just findings:**
`any_tool_failed = any(not r.ran for r in all_results)`; `check_conclusion`/label
decision now gate on `has_critical OR any_tool_failed` — a scanner that failed to run at
all (crash, timeout, missing report) blocks merge and withholds `security-approved`
exactly like a Critical finding does, no new label or retry mechanism introduced.
Check-run title is a three-way branch: "blocked" / "incomplete — scanner failure" /
"passed".

**Dependency scanner swapped from OWASP Dependency-Check to GitHub Dependabot alerts
(2026-08-19)** — see `docs/FORGE-DependencyScanner-Dependabot-Swap-Spec.md` for the full
spec. Root cause, not just a tool swap: Dependency-Check timed out twice consecutively in
CI at its 1800s ceiling (confirmed live: NVD database sync much slower over GitHub
Actions' network path than locally — local cold-cache run ~6-7 min, CI timed out at 30
min both times), and separately required a suppression file to handle a CPE-fuzzy-matching
false-positive class (Open Item #13, now resolved differently — see below).

- `_run_dependabot_check(repo_full_name, request_id)` replaces `_run_dependency_check()`
  entirely — same `ScanResult` interface, so `has_critical`/`any_tool_failed` gating is
  unchanged. Confirmed live: **18 seconds** for the Security Agent step in CI (vs. two
  prior 30-minute timeouts).
- `github_helper.py`'s `get_dependabot_alerts(repo_full_name, state)` paginates via the
  `Link` header and raises `RuntimeError` on 403/404 — confirmed against GitHub's own REST
  API reference that it does **not** document a way to distinguish "Dependabot alerts
  disabled for this repo" from "the App installation lacks the permission" from the
  response alone; the raw response body is included in the exception so a human can read
  GitHub's actual message text. A real, flagged API limitation, not papered over.
- The App's actual granted permission key is `vulnerability_alerts` (confirmed live via
  the App's own JWT against `GET /app/installations`) — not `dependabot_alerts`, despite
  that being the human-facing name everywhere else (App settings UI, casual conversation).
- `get_dependency_graph_package_count(repo_full_name)` (SBOM package count) is a secondary
  check used only when `get_dependabot_alerts()` returns an empty list, to distinguish
  "dependency graph not populated" from "genuinely clean repo" — GitHub gives no other
  documented signal for this. Confirmed empirically: `forge-demo-apps`' SBOM reports 1512
  real packages.
- Dependabot alerts are **repo-wide**, not path-scoped like Dependency-Check's
  `--scan services/<request-id>/` was — `_run_dependabot_check()` filters to
  `dependency.manifest_path` starting with `services/<request_id>/`. Confirmed necessary
  live: 102 total open alerts across REQ-2026-01/02/03 combined, only ~28 under
  REQ-2026-03; without the filter every PR would see every other request's findings too.
- Native per-alert dismissal (`PATCH /repos/{owner}/{repo}/dependabot/alerts/{n}`,
  `state: dismissed`, `dismissed_reason`) replaces the suppression-file mechanism for
  future dev-only findings — `dismissed_comment` is capped at **280 characters**
  (confirmed live via a real 422). Dismissal stays a manual human action (via `gh api` or
  the Security tab); the Security Agent does not auto-dismiss anything — that's a
  deliberately separate, still-open design question.
- `_TOOL_TIMEOUT_SECONDS` reduced **1800s → 600s** after confirming Semgrep/Gitleaks's
  real run times first (live CI: Semgrep ~4.6s, Gitleaks ~0.05s) — neither needed the old
  ceiling, which existed only for Dependency-Check's NVD sync.
- `team/dependency-check-suppressions.xml` is left on disk (git history preserved) but no
  longer referenced by `security_agent.py`. `NVD_API_KEY` Actions secret left configured
  for now, in case of rollback.
- Prerequisites (Mike, manual, one-time): Dependabot alerts + dependency graph enabled on
  both repos (Settings → Code security and analysis), and the `forge-pipeline` App's
  installation granted the "Dependabot alerts: Read-only" permission with the
  installation re-approved. Both were confirmed **missing** on first check, then confirmed
  **present** after Mike completed them — verified live both times via `GET
  .../vulnerability-alerts` (404→204) and the App's own installation permissions, not
  assumed from "done."

**Stale-image-after-merge pattern (recurring — second-plus occurrence, 2026-08-19):** a
merged fix PR does not guarantee the running container reflects it. REQ-2026-03's
frontend "too many redirects" bug (reported live, post-deploy) turned out to be PR #21's
*already-merged* `pages.signIn` fix — the deployed image was still tagged from the
earlier pre-fix commit (`e26363f...`, the PR #20 merge SHA) because nothing rebuilt the
frontend after PR #21 landed. Same failure shape as the earlier missing
`frontend/public/` directory issue (REQ-2026-02/03, see `_ensure_frontend_public_dir()`
above) — "verbally confirmed deployed" and "actually deployed" keep turning out to be
different things. After merging any fix PR, confirm the fix is actually present in the
redeployed image's build SHA (diff the deployed image's source commit against the fix
commit via `az containerapp show --query properties.template.containers[0].image`), not
just that the PR shows merged on GitHub.

---

### deploy_agent.py — Stage 6 (Deploy, staging)

Entry point: `python -m core.agents.deploy_agent --issue-number <n> --request-id <id> --repo-path <path> --commit-sha <sha> --pr-number <n> [--dry-run]`

Needs the actual repository contents on disk (`--repo-path`) — does not clone anything
itself. Never calls Claude/`invoke_agent()` — unit detection, Dockerfile generation, and
the PR comment are all deterministic string/template work ("FORGE automatic, not AI
judgment", same discipline as QA/Security's severity classifiers, taken one step further).

**Unit detection:** walks `services/<request-id>/backend/` for `*.csproj` files (skipping
any path with a case-insensitive "test" segment), classifies each as `web` (references
`Microsoft.NET.Sdk.Web`/`Microsoft.AspNetCore.App`) or `worker` (references
`Microsoft.Extensions.Hosting`, no ASP.NET reference; also the default for an
unclassifiable project — the safer failure mode, since `web` implies public ingress).
`services/<request-id>/frontend/package.json` becomes one additional `frontend` unit if
present.

**Unit naming and validation (retrofit 2026-08-18 — see Open Items #2's resolution):**
each unit's Container App / image name is `<request-id>-<slug>`. `_slugify()` treats any
non-alphanumeric run (not just PascalCase boundaries) as a word separator —
`OnCallRosterTracker.Api` → `on-call-roster-tracker-api`. `_finalize_unit_name()` (replaced
the old `_validate_unit_name()`, now deleted — no truncation) checks the full name against
Docker tag grammar *and* Azure Container Apps' naming rules (lowercase alphanumeric +
hyphen, starts with a letter, no leading/trailing/double hyphen). A charset failure (should
not happen post-`_slugify()`, but still a real, live check) raises `ValueError` — this
scheme does not attempt to fix that. A **length-only** failure is now handled
automatically: the true Azure CLI constraint is `len < 32`, not `<= 32` (confirmed live
2026-08-17 against `az containerapp create --help`'s own wording, "must be less than 32
characters" — see the `_MAX_CONTAINER_APP_NAME_LEN` comment), so the slug is truncated to
fit a 31-char budget (`31 - len(request_id) - 2 hyphens - 6-char hash`) and a 6-hex-char
sha256 suffix of the *untruncated* full name is appended — deterministic, so the same
`(request_id, slug)` pair always yields the same final name across re-runs. A request_id
alone too long to leave any room for a slug still raises `ValueError` (a genuinely
different, worse problem no truncation scheme should silently paper over). The backend
"web" unit's name is finalized *before* either cross-service FQDN is derived (below), so a
name that's invalid even after this (charset failure, or request_id-alone-too-long) falls
back to the "no web backend unit" no-wiring warning instead of baking a broken URL into the
frontend.

Verified live against REQ-2026-03's backend (`OnCallRosterTracker.Api`, previously blocked
at 38 chars): now resolves deterministically to `req-2026-03-on-call-rost-5bb949` (31
chars); a real non-dry-run `deploy_agent.py` re-run against forge-demo-apps' merged main
(PR #20) built, pushed, and deployed it for real —
`req-2026-03-on-call-rost-5bb949.yellowmeadow-894377a9.canadacentral.azurecontainerapps.io`
— alongside `req-2026-03-frontend`, wired to the correct backend FQDN. All 4
previously-passing unit names (`req-2026-01-document-api`, `req-2026-01-email-worker`,
`req-2026-02-auditor-api`, `req-2026-03-frontend`) confirmed byte-identical under the new
scheme.

**Dockerfiles/`.dockerignore`** are generated from the three templates
(`core/agents/templates/dockerfiles/`) only when a project directory doesn't already have
one of its own — never overwrites an existing Dockerfile (Implementation's subagents
often commit their own). `_ensure_frontend_public_dir()` creates an empty
`services/<request-id>/frontend/public/` directory pre-build if missing, regardless of
whether the Dockerfile is Deploy-Agent-generated or pre-existing — fixes a `COPY
--from=builder /app/public ./public` failure that's hit twice now (REQ-2026-02,
REQ-2026-03) on apps with no static assets.

**Fixed target ports:** web units 8080 (ASP.NET Core 8+ container default), frontend 3000
(`next start` default), worker units get no ingress at all.

**Cross-service wiring:** `_get_env_default_domain()` (`az containerapp env show ...
--query properties.defaultDomain`, once per run) plus each unit's deterministic name lets
a unit's real FQDN be predicted *before that Container App exists* — no chicken-and-egg
ordering problem. When a backend "web" unit is present and valid, the frontend build gets
`--build-arg NEXT_PUBLIC_API_BASE_URL=<predicted backend FQDN>`; the backend "web" unit's
create/update command gets `FRONTEND_ORIGIN=<predicted frontend FQDN>` added to its
env-vars. Neither is set if there's no web backend unit in the request.

**`docker build`/`docker push` and the read-only `az containerapp show` existence check
run for real in both `--dry-run` and a real run** (only `az containerapp create`/`update`
itself is print-only, redacted, in `--dry-run`). **`create` uses `--env-vars`, `update`
uses `--set-env-vars`** — Azure CLI rejects the other on each (a real bug caught the first
time this path ran fully live).

**Per-unit build+push+deploy is interleaved in one loop with a `try`/`except` per unit** —
one unit's build/push/deploy failure no longer blocks a different unit that would
otherwise succeed. `DeployResult` carries an `error` field; the PR comment shows a
`❌ **failed** — <error>` row for failed units plus a "N of M unit(s) failed" summary line
when any exist (wording is conditional on the real count — it used to hardcode "the rest
were deployed successfully" even at 0-of-N). On any unit failure, a second, distinct
summary comment is also posted to the FORGE tracking issue, and the run raises so CI still
reflects a real problem — even though the (partial) PR comment reporting successes is
always posted.

**`_detect_design_gaps()`** flags (never blocks) any unit whose project label doesn't
appear in `docs/<request-id>/design.md`, checking both the literal identifier and a
de-camelCased spaced variant ("EmailWorker" → "Email Worker") case-insensitively.

**No label applied on success** — Document 6's Label Reference table has no deploy-stage
label; staging is a verification step, not a release gate.

**App-secrets wiring (`_wire_keyvault_secret()`, added 2026-08-19) — see Open Items #1 for
what's still unresolved.** Three independent apps had hit this gap (EmailWorker's Service
Bus connection string, REQ-2026-02's D365 config, REQ-2026-03's NextAuth
`NEXTAUTH_SECRET`) before a generic primitive was built:

- `_wire_keyvault_secret(env_var_name, kv_secret_name, app_secret_key, container_app_name,
  resource_group, vault_name)` wires an *already-existing* Key Vault secret into a
  Container App as an env var, via a Key Vault reference resolved through the app's own
  system-assigned managed identity (`identityref:system`) — never a plain Container App
  secret, never plaintext in `config.yaml`/git. Does **not** create or rotate the secret
  value — raises if `kv_secret_name` doesn't already exist, rather than silently skipping
  the env var or fabricating a value.
- `app_secret_key` (the Container App's own internal secret reference name) is a
  **separate parameter** from `kv_secret_name` (the Key Vault secret's own name) —
  confirmed live via `az containerapp secret set --help` that the former is capped at
  **20 characters**, a different, unrelated constraint from the latter (no such limit).
  Reusing one name for both breaks for any Key Vault secret name longer than 20 chars.
- Exposed via a `--wire-keyvault-secret` CLI mode on `deploy_agent.py` (not wired into the
  normal per-unit deploy loop) since there is still no machine-readable convention
  anywhere — checked `.env.example`, `design.md`, `tasks.md`, `package.json`, all agent
  code — for an app to declare which secrets it needs (Open Items #1). Normal deploy-flow
  CLI args remain required when this flag isn't passed.
- Bootstrap infra (one-time, done manually under Mike's own account — the staging deploy
  SP only has Contributor on `forge-build-rg`, insufficient to register the
  `Microsoft.KeyVault` resource provider or create RBAC role assignments): Key Vault
  **`forge-build-kv`** in `forge-build-rg`; staging SP granted **"Key Vault Secrets
  Officer"** scoped to just this vault (can read/write secrets, cannot grant RBAC roles to
  anything else); each Container App needing a secret gets its own system-assigned
  managed identity, granted **"Key Vault Secrets User"** (read-only), also scoped to just
  the vault — never the resource group or subscription.
- `NEXTAUTH_URL` (next-auth's own canonical site URL — a full `https://` URL, confirmed
  against next-auth's warning text and this app's `.env.example`, not a bare hostname) is
  **not** a secret and doesn't go through Key Vault — it's wired via the same
  `--set-env-vars` mechanism `FRONTEND_ORIGIN` already uses, computed from the same
  `frontend_fqdn` the cross-service wiring block already derives, added directly to the
  normal per-unit deploy loop. Known structural limitation: `frontend_fqdn` is only
  computed today when a backend "web" unit also exists (inherited from the existing
  `FRONTEND_ORIGIN` cross-service-wiring gate) — a future frontend-only app would silently
  get `NEXTAUTH_URL` withheld too. Flagged in-code, not fixed — fixing it means decoupling
  `frontend_fqdn`'s computation from `backend_web_unit`'s existence, a real (if small)
  restructuring beyond mirroring the existing pattern.
- Verified live for REQ-2026-03: `NEXTAUTH_SECRET` (Key Vault secret
  `req-2026-03-nextauth-secret`, app secret key `nextauth-secret`) and `NEXTAUTH_URL`
  (plain env var) both attached to `req-2026-03-frontend`; the `/api/auth/error?error=
  Configuration` redirect (missing-secret symptom) is gone, replaced first by a
  `NEXTAUTH_URL`-misconfiguration redirect loop (fixed by the `NEXTAUTH_URL` wiring), then
  by a real app-code bug (`pages.signIn` self-reference, PR #21, merged — see Current
  Build Phase).

### Azure AD wiring + Postgres provisioning (added 2026-08-19, REQ-2026-03 write-path verification)

**Azure AD wiring — confirmed pattern, reusable for future apps:**
- Frontend: `AZURE_AD_CLIENT_ID` / `AZURE_AD_TENANT_ID` as plain env vars (normal
  `--set-env-vars` deploy path — not secrets), `AZURE_AD_CLIENT_SECRET` via the existing
  `_wire_keyvault_secret()` primitive (`app_secret_key='azuread-secret'`) — no new
  wiring mechanism needed.
- Backend (ASP.NET Core + `Microsoft.Identity.Web`): confirmed real config-binding is
  `.AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"))` (verified
  via grep across every `.cs` file — no custom `TokenValidationParameters` override
  anywhere), so the standard double-underscore env var convention (`AzureAd__TenantId`,
  `AzureAd__ClientId`, `AzureAd__Audience`) applies safely.
- `AzureAd__Audience` must match the exact "Application ID URI" string shown under the
  app registration's **Expose an API** blade in the Portal — for a default (non-custom)
  registration this is `api://<client-id>`, but this must be confirmed per-registration
  via the Portal, not assumed, since a Contributor-scoped deploy SP typically lacks
  Graph read access to check this itself (`az ad app show` → `AuthorizationFailed` under
  `forge-deploy-staging`, confirmed live) — this requires a human with Portal access or a
  properly-permissioned `az login`.

**`az login` MFA workaround (confirmed twice now):** the default Windows auth broker
flow (plain `az login`) has unreliably failed to surface an MFA prompt. Use
`az login --use-device-code` instead when switching to a personal elevated account for
any bootstrap operation the staging SP can't perform (resource provider registration,
first-time resource creation, role assignments). Always confirm the account actually
switched with `az account show --query user.name -o tsv` before proceeding, and confirm
the switch-back to the SP the same way afterward.

**Azure Database for PostgreSQL Flexible Server — new pattern, first use this session:**
- Provisioned for REQ-2026-03's backend: Burstable B1MS, 32GB storage (Azure's storage
  floor — cannot go smaller; storage can only be increased later, never decreased),
  Canada Central.
- Real Canada Central pricing (via the Azure Retail Prices API, not the commonly-cited
  US East figure): compute $0.0185/hr (~$13.51/mo continuous), storage $0.1265/GB/mo
  (~$4.05/mo, billed regardless of stop/start state), backup free at this size. **~$17.56/mo
  if left running continuously; ~$4.05/mo floor when stopped.**
- `az postgres flexible-server stop` pauses compute billing immediately but **not**
  storage billing. Server auto-restarts after 7 days if never manually started again —
  fine as long as it's touched at least weekly during active testing.
- Do **not** pass `--public-access None` on server-create if firewall rules will be
  needed afterward — firewall rule operations are not supported without public access
  enabled (hit and fixed live this session).
- Container Apps' documented static outbound IP (`properties.staticIp` on the
  environment) is **not** reliably usable for narrow firewall allowlisting in a no-VNet
  `WorkloadProfiles` config — tested and failed live (`TimeoutException` connecting from
  the backend). The working fallback is the broad `AllowAzureServices` sentinel rule
  (`0.0.0.0`–`0.0.0.0`), a known tradeoff (opens to any Azure-internal source, not just
  this Container App) — test the narrow option first rather than reaching for the broad
  rule by default.
- Connection string format for `Npgsql.EntityFrameworkCore.PostgreSQL`: ADO.NET
  key=value format, not a `postgres://` URI — confirm against the actual `.csproj`
  package reference and any fallback default already in `Program.cs` before assuming
  which format a given app expects.
- Container Apps managed identity is **not automatic** — check `identity.type` before
  assuming a Key Vault-wiring primitive will work; REQ-2026-03's backend had
  `type: "None"` and needed identity enabled (`az containerapp identity assign
  --system-assigned`) plus the Key Vault Secrets User role granted before
  `_wire_keyvault_secret()` would succeed.
- azure-cli 2.89.0 flag names differ from some documented examples: `--database-name` →
  `--name` (for `flexible-server db create`), `--rule-name` → `--name`/`--server-name`
  split (for `firewall-rule create`). Worth double-checking exact flags against `--help`
  on this install rather than assuming older docs/examples match.

**REQ-2026-03 write-path verification — passed, confirmed clean this session:**
`POST /api/v1/shifts/{id}/claim` and `DELETE /api/v1/shifts/{id}/claim` both verified via
real HTTP calls (a real signed Azure AD bearer token, tenant `af2dd50c-...`) **and**
direct DB query (`psql` via a throwaway `docker run postgres:16-alpine`) — not just API
response trust. Invalid operations (double-claim, release-when-unclaimed) correctly
rejected with `409` and produce **zero** spurious audit entries — confirms the
audit-write code path only runs on the success branch. Known minor bug, not blocking:
the `SHIFT_ALREADY_CLAIMED` error message text ("claimed by someone else") is imprecise
for the self-claim-retry case (same user re-claiming their own already-held shift);
status code and rejection logic are correct, only the wording is off.

---

### Pipeline Wiring & Triggers

Every `.github/workflows/*.yml` follows the same shape: guard clause re-checks trigger
state at run time (labels/PR state can change between event and runner start) → resolve
request-id/PR context → invoke the real stage agent script (no `--dry-run`) → label
lifecycle cleanup → a catch-all step posts a failure comment if a *pre-agent* glue step
failed (stage agents self-report their own internal failures per ADR-0011; this only
covers the gap before that point, skipped whenever the agent step actually ran).

**Trigger mapping:**

| Workflow | Trigger | Clears on success |
|---|---|---|
| `00-intake.yml` | `intake-ready` label | `intake-ready` |
| `01-requirements.yml` | `clarification-complete` label | `clarification-complete`, `clarification-pending` |
| `02-design.yml` | `requirements-approved` label | `requirements-approved` |
| `03-implementation.yml` | `design-approved` label | `design-approved` |
| `03b-recover-implementation.yml` | `workflow_dispatch` only, manual | n/a — see "Implementation completion detection & recovery" below |
| `04-qa.yml` | `repository_dispatch` (`feature-pr-opened`, from forge-demo-apps) | none (qa_agent.py labels itself) |
| `05-security.yml` | `repository_dispatch` (`feature-pr-opened`) | none (security_agent.py labels itself) |
| `06-deploy.yml` | BOTH `qa-approved` AND `security-approved` present | none (Document 6 has no deploy-stage label) |

**Stage 0a (Codebase Ingestion, Phase 7 step 7.1)** is not a separate workflow/trigger —
it's a conditional step inside `00-intake.yml` itself, right after "Run Intake Agent",
firing only when the spreadsheet's Request Type is Enhancement. See "ingestion_agent.py
— Stage 0a" above for the full wiring/verification writeup.

**Cross-repo trigger:** `forge-demo-apps` has its own `.github/workflows/notify-forge.yml`
(pushed there directly — the FORGE App has no `workflows` permission and can't write
workflow files itself) firing on `pull_request` (`opened`, `synchronize`) for `feature/*`
branches, forwarding `{pr_number, head_sha, head_ref}` to `forge-template` as a
`repository_dispatch` event `feature-pr-opened`. `forge-demo-apps` also has
`.github/workflows/design-pr-security-noop.yml`, giving `design/*` PRs a no-op
`security-check` (`conclusion: success`, clearly labeled as not a real scan) — `main`'s
branch protection requires that check on every PR, but only `feature/*` PRs ever get a
real one.

**`request_id` and feature-PR resolution — both fixed to not trust weak signals:**
- `04-qa.yml`/`05-security.yml` resolve `request_id` via `workflow_glue.py`'s
  `resolve-request-id` subcommand (scans tracking-issue comments for a prior stage's
  `<!-- forge:agent-comment ... request_id=... -->` marker), **not** a bash prefix-strip
  of the branch name. The old prefix-strip silently produced a wrong `request_id` (and a
  false-positive `qa-approved` with zero real coverage) the one time a `feature/*` branch
  had extra suffix text.
- `workflow_glue.py`'s `resolve_feature_pr()` (used by `06-deploy.yml`) asks GitHub
  directly for the currently-open PR on `feature/<request_id>` (via
  `github_helper.list_open_prs_by_head()`), instead of trusting the *original*
  Implementation Coordinator's tracking-issue comment — which goes stale the moment a
  follow-up feature PR opens on an already-implemented request. Raises `ValueError` on
  zero or more than one open match rather than silently picking one.

**`create_ado_items.py`** wires `ado_helper.py`'s `create_epic`/`create_feature`/
`create_user_story` to `docs/<request-id>/ado-work-items.json` (read from the
`pipeline-state` branch), writing real IDs back plus `primary_user_story_id` (the first
User Story, in document order — `qa_agent.py`'s `_resolve_parent_story_id()` looks for
exactly this key). No rollback on partial failure (ADO has no multi-item transaction);
exits non-zero and posts a failure comment naming what succeeded.

**`workflow_glue.py`** also provides `download-issue-attachment` (finds/downloads the
BA's intake spreadsheet from the tracking issue) and `resolve-tracking-issue` (finds the
tracking issue number from a forge-demo-apps PR body's "Related FORGE tracking issue:
owner/repo#N" line).

**Branch protection on `forge-demo-apps`' `main`:** requires the `security-check` status
check (app_id `4388813`) and 1 approving review; no `bypass_pull_request_allowances`
(GitHub rejects that field outright on a personal-account repo — confirmed via a 422, not
assumed). `requirements_agent.py`/`create_ado_items.py` write `requirements.md`/
`ado-work-items.json` to a dedicated, intentionally-unprotected `pipeline-state` branch
(not `main`) for exactly this reason — `design_agent.py`/`qa_agent.py` read from the same
branch. **`enforce_admins` is currently `false`**, contradicting the originally-confirmed
`true` — see Open Items; not something any known session action changed.

**`github_helper.py`'s `add_label()` uses the GitHub App installation token, not
`GITHUB_TOKEN`.** GitHub Actions' anti-recursion rule means a `GITHUB_TOKEN`-authored
label never triggers a new workflow run — this silently broke `06-deploy.yml`'s
label-driven dispatch for every agent-applied `qa-approved`/`security-approved` until
fixed. `post_comment`/`get_issue`/`get_issue_comments`/`remove_label` stay on
`GITHUB_TOKEN` (none of them need to trigger a downstream label-driven workflow).

---

### implementation_coordinator.py / managed_agents_wrapper.py — completion detection & recovery

Real Stage 3 runs have taken 35-55+ minutes; `wait_for_all_threads_idle()` (in
`managed_agents_wrapper.py`) is the one real completion signal for the whole stage — the
coordinator's own `idle`/`end_turn` status can land in under a second (reflecting only its
first turn ending after kicking off delegation), long before subagents actually finish.
Polls every 15s up to `_COMPLETION_POLL_TIMEOUT` (default 5400s/90min, override via
`FORGE_IMPLEMENTATION_COMPLETION_TIMEOUT`). `_ARCHIVE_RETRY_ATTEMPTS` (3, 2s/4s/8s) exists
only to absorb the separate, genuinely transient idle→running archive-call race — it is
**not** a substitute for the completion wait.

**`SessionStillRunningError`** (carries `session_id`/`thread_statuses`, and — attached by
the coordinator — `coordinator_id`/`environment_id`/`subagent_ids`) is raised when threads
aren't all idle within the completion-wait ceiling. **This is not a failure** — the session
is left alive, not archived, specifically so it can be resumed by ID.
`run_implementation_coordinator()` catches it distinctly: posts a "still running, not
failed, check back later" comment to the tracking issue (not the generic failure comment)
and exits `75` (vs. `1` for a real failure).

**Known gap, confirmed live on REQ-2026-03:** `wait_for_all_threads_idle()` only checks
thread `status`, never `session.error` events — a session that hits a fatal
session-level error (e.g. Anthropic billing exhaustion) mid-run has every thread report
`idle` once nothing can run, indistinguishable from a genuinely finished one. See Open
Items.

**`--recover-session SESSION_ID`** (CLI mode on `implementation_coordinator.py`,
`--request-id` still required): derives all resource IDs via `get_session_resource_ids()`
(a single `GET /sessions/{id}` — no need to dig a `managed_agents_session_start` log line
out of Actions logs), checks live thread status, and returns cleanly with **no mutation at
all** if anything is still busy ("not ready yet" is a normal, successful outcome here). If
idle, runs `_sanity_check_extracted_files()` (rejects an archive under 3 files/500 bytes;
requires ≥2 files under `services/<request-id>/<unit>/` for each unit `tasks.md` actually
mentions — doesn't assume every request needs both backend and frontend) before reusing
the exact same commit/PR/comment path the happy path uses, then archives the session
itself. `.github/workflows/03b-recover-implementation.yml` is `workflow_dispatch`-only,
deliberately manual, not automatic or polling — a human deciding "it's been long enough"
is the intended amount of automation.

**Standing rule, reconfirmed across four separate incidents (REQ-2026-01,
DRYRUN-2026-01, REQ-2026-02, REQ-2026-03): never simply re-run
`implementation_coordinator.py` after a local kill/timeout or an Actions job failure.**
`create_agent_session()` creates a second, duplicate, billable set of agents/environment/
session on top of one that may still be running or already finished. Always recover by
session ID first (`--recover-session`, or check for a `managed_agents_session_start` log
line / whether `feature/<request-id>` already exists as a sign of prior partial
completion).

### Manually killing a runaway Managed Agents session (raw curl, no repo tooling)

**This repo's own `archive_session()` deliberately refuses to touch a session that
isn't already idle** (it calls `wait_for_all_threads_idle()` first and does not catch
`SessionStillRunningError`) — by design, so nothing in the codebase can accidentally
archive a genuinely still-running Stage 3 session out from under itself. That means
there is **no script in this repo** for force-stopping a session someone decides (e.g.
mid-Console-review) needs to be killed right now. Live-verified end-to-end 2026-08-28
against a real running session (`sesn_01MwLQkRnUCb54aguyJLknvX`, REQ-2026-04, killed
~16 min in, coordinator+backend+frontend all mid-turn, test_writer not yet started).

**Step 1 — interrupt the running turn(s):**
```bash
set -a; source .env; set +a
curl -sS https://api.anthropic.com/v1/sessions/<SESSION_ID>/events \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: managed-agents-2026-04-01" \
  -H "content-type: application/json" \
  -d '{"events": [{"type": "user.interrupt"}]}'
```
This stops the active turn(s) but does **not** archive anything — the session,
environment, coordinator, and subagent resources are all still live (and billable)
afterward.

**Step 2 — confirm it actually landed** (mirrors `get_thread_statuses()`):
```bash
curl -sS "https://api.anthropic.com/v1/sessions/<SESSION_ID>/threads?limit=100" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: managed-agents-2026-04-01"
```
Wait for every thread's `status` to read `idle` before archiving. Note this is
interrupt-idle, not real-completion-idle — do not treat it as "the implementation
finished," just "it stopped."

**Step 3 — check for output before archiving (worth doing, cheap):**
```bash
curl -sS "https://api.anthropic.com/v1/files?scope_id=<SESSION_ID>&limit=100" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: files-api-2025-04-14,managed-agents-2026-04-01"
```
An interrupted session almost never has `implementation.tar.gz` in
`/mnt/session/outputs/` yet (packaging is the coordinator's last step) — confirmed
empty on the 2026-08-28 kill — but it costs nothing to check before the environment
(and its sandbox filesystem) is gone for good.

**Step 4 — get `environment_id`/`coordinator_id`/`subagent_ids`** (mirrors
`get_session_resource_ids()`; the coordinator's own `multiagent.agents[]` list may
include a subagent — e.g. `test_writer_agent` — that never actually started a thread
if the run was killed early; it still needs archiving as an agent resource):
```bash
curl -sS "https://api.anthropic.com/v1/sessions/<SESSION_ID>" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: managed-agents-2026-04-01"
```

**Step 5 — archive everything, in order** (same order as `archive_session()`: session
→ environment → coordinator → each subagent):
```bash
for path in "sessions/<SESSION_ID>" "environments/<ENV_ID>" "agents/<COORD_ID>" \
            "agents/<SUBAGENT_ID_1>" "agents/<SUBAGENT_ID_2>" "agents/<SUBAGENT_ID_3>"; do
  curl -sS -X POST "https://api.anthropic.com/v1/$path/archive" \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -H "anthropic-beta: managed-agents-2026-04-01" \
    -H "content-type: application/json" \
    -d '{}'
done
```
Each response's `archived_at` field confirms success; the session response's own
`status` flips to `terminated`. All calls 200'd on the first try in the 2026-08-28
run — no need for the wrapper's idle→running archive-retry dance, since by this point
every thread was already confirmed idle in Step 2.

**Why this isn't wrapped into a repo script (yet):** it's a rare, manual,
human-in-the-loop action (someone in the Console deciding to kill a session), not
something any automated pipeline stage should ever do to itself. If this keeps coming
up, the right fix is a small `--force-kill SESSION_ID` CLI mode alongside
`--recover-session` — not yet built.

---

## Open Items / Known Gaps

1. ~~**Deploy Agent had no app-secrets wiring mechanism, and no way to discover in
   advance that a given app needs a given secret.**~~ — **FULLY RESOLVED 2026-08-31.**
   `_wire_keyvault_secret()` (built 2026-08-19) solves wiring an already-known secret
   into a Container App via Key Vault + managed identity — it does not, by itself,
   solve discovery. Two flags now close that gap: Option 3 (reactive, flags an
   already-crash-looping app post-deploy) and Option 1 (proactive, flags a `design.md`
   missing its `## Required Secrets` section before merge, checked at Stage 3).
   `req-2026-01-email-worker` itself is still crash-looping — a separate, still-open
   app-level fact, not a gap in the mechanism. Full narrative:
   `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
2. ~~**REQ-2026-03's backend unit name doesn't fit Azure's Container App name length
   limit.**~~ — **RESOLVED 2026-08-18.** `_finalize_unit_name()` (deterministic
   truncation + 6-char sha256-hash suffix) replaced the old raise-only
   `_validate_unit_name()`; real Azure limit confirmed as `len < 32`, not `<= 32`.
   Verified live and byte-identical for all previously-passing unit names. Full
   narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
3. ~~**No pipeline stage validated that the app actually builds before Stage 6
   (Deploy).**~~ — **FIXED AND VERIFIED 2026-08-24**, per
   `docs/FORGE-Pipeline-Hardening-Spec.md` Fix 3. QA now runs `npm run build`/
   `next build` alongside the test suite; a build failure supersedes the test report
   and blocks `qa-approved`. Deliberately scoped to the language-level build only, not
   `docker build`. Full narrative:
   `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
4. ~~**`qa_agent.py`'s Jest/Vitest JSON parsing had a file-collection blind spot** (a
   suite where every file fails to *collect* reported 0/0/0 and was treated as a
   pass).~~ — **FIXED AND VERIFIED 2026-08-24**, per
   `docs/FORGE-Pipeline-Hardening-Spec.md` Fix 1. New `_jest_collection_failures()`
   detects empty `assertionResults[]` on a `status: "failed"` entry and routes it into
   the existing `ran=False` path. Full narrative:
   `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
5. ~~**QA's `_MAX_RETRIES = 3` only picked which label to apply — it never blocked or
   gated a re-run.**~~ — **FIXED AND VERIFIED 2026-08-24**, per
   `docs/FORGE-Pipeline-Hardening-Spec.md` Fix 2. `run_qa_agent()` now checks for an
   existing `qc-retry-limit-reached` label before running any test suite and skips
   entirely if present, consuming no attempt. A human can still recover by removing
   the label. Full live Stage 4→6 cycle confirmed 2026-08-25 with nothing regressed.
   Full narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
6. ~~**`wait_for_all_threads_idle()` couldn't distinguish "genuinely finished" from
   "every thread hit a fatal session-level error"; `run_implementation_stage()` also
   archived unconditionally once idle, before confirming real output existed.**~~ —
   **RESOLVED 2026-08-26**, per `docs/FORGE-Item6-Item8-Fix-Spec.md`. Two separate
   fixes: `SessionBudgetExhaustedError` now raises directly off a `budget_reached`
   stop_reason; `run_implementation_stage()` gained an optional
   `expected_output_filename` check-before-archive. Verified via a 10-case mocked
   harness; a real live Stage 3 end-to-end dry-run was deliberately deferred on
   cost/time grounds, not yet done. Full narrative:
   `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
7. **Archive-prefix mismatch, confirmed once on REQ-2026-02, root cause unconfirmed** —
   the Implementation Coordinator's packaging command may be cwd-relative rather than
   pinned to the sandbox root. `_extract_archive_to_file_dict()`'s prefix guard is kept
   strict (rejects, doesn't auto-remap) per Mike's explicit call; worth investigating
   properly only if it recurs.
8. ~~**CI-workflow scope creep** — the Implementation Coordinator/subagents twice
   generated unrequested `.github/workflows/*.yml` files nested under
   `services/<id>/`.~~ — **RESOLVED 2026-08-26**, per
   `docs/FORGE-Item6-Item8-Fix-Spec.md`. Root cause: `tasks.md`'s prompt had no
   restriction on deliverable scope. Fixed as prevention (Layer 1: prompt now states
   CI/CD is out of scope for task items) + backstop (Layer 2:
   `_extract_archive_to_file_dict()` rejects any archive member with a literal
   `.github` path segment). Full narrative:
   `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
9. ~~**Admin-merge pattern for ad hoc `fix/*` branches — 4 occurrences (PRs #7, #8,
   #11, #16).**~~ — **RESOLVED 2026-08-27 — no code fix needed, closed on live
   evidence** (`docs/FORGE-Item9-Item15-AdHocFixDispatch-Spec.md`). `notify-forge.yml`'s
   `feature/*` dispatch filter already correctly forwards `feature/fix-*` for a real
   scan — confirmed live via PR #27. The 4 original cases predated the `feature/fix-*`
   convention. Full narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
10. ~~**`enforce_admins` on `forge-demo-apps`' `main` branch protection was `false`,
    contradicting the originally-confirmed `true`.**~~ — **RESOLVED 2026-08-27**, on
    Mike's go-ahead. Flipped `false → true` via the dedicated API endpoint; confirmed
    via before/after reads that no other protection field changed. Full narrative:
    `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
11. **21 `next@14.2.35` CVE findings have no 14.x backport** (8 High + 11 Medium + 2 Low)
    — accepted ongoing risk from the deliberate decision to stay on the 14.x line, not a
    bug. **Count refined 2026-08-21** (see Item #19's triage pass): the original count
    only tallied the 8 HIGH-severity findings; the full "no 14.x backport" population is
    21 unique CVEs — the disposition itself (accepted risk) is unchanged, only the count
    was incomplete.
12. ~~**Cost log (`docs/FORGE-pipeline-cost-log.md`) needed REQ-2026-03 figures
    backfilled**, including the Deploy Agent fix cycle.~~ — **RESOLVED 2026-08-31.**
    Pulled real cost/token data from GitHub Actions logs and the Managed Agents
    sessions API. Real total: **$57.64** across all costed Anthropic API stages to date
    (see `docs/FORGE-pipeline-cost-log.md` §2/§3). Also surfaced and fixed a narrative
    gap in Item #25 (the 2026-08-28 stale-code incident actually recurred twice, not
    once). Full narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
13. ~~**A `forge-template`-level Dependency-Check suppression file** for confirmed
    dev-only npm findings.~~ — **RESOLVED DIFFERENTLY, 2026-08-19.** Rather than build
    the suppression file (hit a real XSD gotcha), the whole dependency scanner was
    swapped from OWASP Dependency-Check to GitHub Dependabot alerts (see
    security_agent.py reference). Native per-alert dismissal replaces the suppression
    mechanism. Full narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
14. ~~**Backend AzureAd config still placeholder — blocked real Azure AD login
    end-to-end for REQ-2026-03.**~~ — **RESOLVED 2026-08-19.** Both frontend and
    backend wired; a real Postgres Flexible Server provisioned; claim/release
    write-path verified end-to-end via real HTTP + direct DB query. `AzureAd__Audience`
    confirmed as `api://b59886c1-12ac-42c1-895f-5fafa8e57318`. Full narrative:
    `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
15. ~~**Ad hoc PRs needed the `Related FORGE tracking issue: <owner>/<repo>#N` body
    line added manually if not opened by a FORGE stage agent.**~~ — **RESOLVED
    2026-08-27 via Option A** (process fix — documented as a standing convention, no
    code change to `resolve_tracking_issue()`), per Mike's explicit choice over a
    code-level fallback. Historical occurrence: PR #21 hit exactly this gap. Full
    narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
16. ~~**Cleanup debt from the 2026-08-19 write-path verification session, not
    urgent.**~~ — **RESOLVED 2026-08-19.** Test user flipped back to
    `IsCoordinator=false` and independently re-verified; both firewall rules removed;
    Postgres server confirmed `Stopped`. Full narrative:
    `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
17. ~~**`workflow_glue.py`'s `resolve_feature_pr()` couldn't find ad hoc fix PRs for
    Deploy — confirmed live on PR #22.**~~ — **RESOLVED AND LIVE-VERIFIED 2026-08-20**,
    per `docs/FORGE-DeployAgent-ResolveFeaturePR-AdHocFix-Spec-v2.md`.
    `resolve_feature_pr()` now falls back to scanning open PRs for the tracking-issue
    body line when the `feature/<request_id>` branch match finds nothing. Full
    narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
18. ~~**New bug uncovered by Item #17's live verification: `deploy_agent.py`'s
    `_az_login()` ran too late relative to `_get_env_default_domain()`.**~~ — **FIXED
    AND VERIFIED 2026-08-20.** Silently blocked every fully-automated deploy for any
    two-unit (frontend + backend-web) request since the pipeline's inception; every
    past successful deploy had been a manual invocation from an already-authenticated
    shell. `_az_login()` moved ahead of the cross-service-wiring block. Full narrative:
    `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
19. ~~**Dependabot alert triage pass completed 2026-08-21**~~ — **FULLY CLOSED OUT.**
    Full report: `docs/FORGE-Dependabot-Triage-Report-2026-08-21.md`. Headline finding
    (REQ-2026-01/02 pinned to `next@14.2.5` vs. REQ-2026-03's `next@14.2.35`) became PR
    `forge-demo-apps#24` (merged 2026-08-24), closing 24 alert rows with zero
    regression confirmed. 9 dev-only alerts dismissed 2026-08-21, independently
    re-verified. Full narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
20. ~~**One real, one false-alarm `next build` failure.**~~ — **RESOLVED 2026-08-26.**
    REQ-2026-02's failure was a Windows-only false alarm (builds clean on Linux).
    REQ-2026-01's was real — a duplicate `@microsoft/applicationinsights-core-js`
    resolution — fixed via a `package.json` `overrides` entry (`forge-demo-apps#27`,
    merged), manually deployed and independently verified live via `az containerapp
    show` matching image tags on all 3 units. Full narrative:
    `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
21. ~~**Deploy Agent's `_SHELL_TIMEOUT_SECONDS` (1800s) was too tight for real
    frontend builds.**~~ — **RESOLVED 2026-08-26.** Bumped `1800 → 3600`; proven safe
    by Item #20's own real retry at 3600s succeeding cleanly. Commit `ac13529`. Full
    narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
22. ~~**Deploy Agent didn't wire any scale rule for non-ingress worker units** (they
    scaled to zero with nothing able to wake them).~~ — **RESOLVED 2026-08-26.**
    Non-ingress units now default to `minReplicas: 1`; web/frontend units unchanged.
    Only affects units generated from this fix forward — existing live configs
    deliberately left untouched. Commit `9d57398`. Full narrative:
    `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
23. ~~**No on-demand way to verify a service's language build or Docker build outside
    the full pipeline.**~~ — **RESOLVED 2026-08-26.** New `forge-demo-apps` workflow
    `.github/workflows/verify-build.yml` (`workflow_dispatch`-only, manual). Live
    verification surfaced and fixed a real backend Docker-build-context bug along the
    way. A cross-cutting note on this session's overall verification posture for Items
    #6/#8/#21/#22/#23 was also moved to the archive alongside these items. Full
    narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
24. ~~**Stage 3 (Implementation) never extended for Enhancement requests.**~~ —
    **RESOLVED AND LIVE-VERIFIED 2026-08-28**, per
    `docs/FORGE-Item23-Stage3-Enhancement-Spec.md`. This is also the fix cycle that
    used REQ-2026-04 (`forge-template#10`) as its real live test target — a
    reconciliation pass on 2026-08-31 confirmed this was Build Plan Phase 7 step
    7.2's actual chosen enhancement (a coverage-history view for REQ-2026-03),
    never explicitly logged as such at the time; see Build Plan v10 and Backlog
    Item #32/#33 for the full reconciliation. `implementation_coordinator.py`
    now resolves `service_root` to the real `services/<existing_service>/` for an
    Enhancement, with a Managed Agents mount-path rewrite fix
    (`/mnt/session/uploads/...`) discovered along the way. Real verification via
    `forge-demo-apps#32`: 19 files changed, all under `services/REQ-2026-03/`, zero
    under a new folder. This zero-Enhancement-awareness pattern recurred twice more
    (Items #25, #28) before Item #32 found a fourth instance in Stage 2/ADO item
    creation. Full narrative:
    `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
25. ~~**QA and Security both assumed `services/<request_id>/`, never
    `services/<existing_service>/`.**~~ — **RESOLVED AND LIVE-VERIFIED 2026-08-28**,
    per `docs/FORGE-Item25-QASecurity-EnhancementTarget-Spec.md`. New shared
    `resolve_service_root()` helper; both stages now fail loud (not silently
    false-pass/crash) on a missing target. The same stale-code re-dispatch incident
    recurred twice during verification (corrected in Item #12's backfill) before a
    genuine `qa-approved` + `security-approved` pass was confirmed. Also surfaced Item
    #27 (found during this same pass). Same zero-Enhancement-awareness pattern as
    Item #24 before it, and Items #28/#32 after it. Full narrative:
    `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
26. ~~**No human gate exists between a feature PR opening and Deploy firing.**~~ —
    **RESOLVED 2026-08-29**, per `docs/Specs/FORGE-Item26-DeployTriggerGate-Spec.md`.
    Mike chose Option A: `notify-forge.yml` dispatches a `pr-merged` event on real
    merge; `06-deploy.yml`'s guard clause now requires both labels *and* a confirmed
    merge before deploying. Live-verified end-to-end via a real Mike-initiated merge of
    `forge-demo-apps#32` triggering a real Deploy run. Landing this surfaced Item #30,
    now also resolved. Full narrative:
    `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
27. ~~**`04-qa.yml`'s "clear a stale label on pass" step decided "did we just pass" by
    re-querying current label state, not this run's own outcome.**~~ — **RESOLVED
    2026-08-28**, found live during Item #25's §5 verification. `qa_agent.py`'s
    `main()` now writes this run's real `label_applied` outcome to `$GITHUB_OUTPUT`;
    the cleanup step gates on that instead of re-deriving from current labels. Commit
    `5d07169`. Full narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
28. ~~**Deploy Agent (Stage 6) had zero Enhancement-target awareness.**~~ —
    **RESOLVED AND LIVE-VERIFIED 2026-08-29**, per
    `docs/FORGE-Item28-DeployAgent-EnhancementTarget-Spec.md`. Introduced `naming_id`
    (existing_service when set, else request_id) so an Enhancement deploy updates the
    existing live `req-<existing_service>-*` Container Apps in place rather than a new
    parallel slot. Live-verified: zero new `req-2026-04-*` resources created, image
    tags updated in place. Mike separately confirmed the visual result (coverage-history
    filter feature) renders correctly. Third occurrence of the same
    zero-Enhancement-awareness pattern as Items #24/#25 — Item #32 later found a
    fourth, in Stage 2/ADO item creation. Full narrative:
    `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
29. ~~**`README.md` describes a materially different (partly aspirational, never-built)
    pipeline** (fictional slash-command approvals, a never-built production-deploy
    stage).~~ — **RESOLVED 2026-08-29.** README rewritten to match the real,
    label-driven pipeline; intake template path and `tracking/` directory description
    both corrected. Landed alongside `docs/Archives/FORGE-Open-Items-Backlog-v2.md` (supersedes
    v1). Full narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
30. ~~**No `security-check` mechanism existed for a non-`feature/*`/non-`design/*`
    branch PR** (e.g. an ops/infra change to `.github/workflows/*` itself).~~ —
    **RESOLVED 2026-08-29, permanently.** New `ops-pr-security-noop.yml` in
    `forge-demo-apps`, mirroring `design-pr-security-noop.yml`'s existing pattern,
    scoped to `ops/*` branches. Confirmed a same-repo PR's own head-branch workflow
    file can satisfy its own first-PR check — no manual bootstrap needed. Full
    narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
31. ~~**`design_agent.py`'s `_parse_model_json()` had zero resilience to a malformed
    large JSON-mode response.**~~ — **RESOLVED 2026-08-31**, per
    `docs/Specs/FORGE-Item31-StructuredModelOutput-Spec.md`. Root-cause fixed via
    forced tool-use structured output (`invoke_agent()`'s new `output_schema` param) —
    not just a persist-and-retry mitigation. Scope grew from `design_agent.py` alone to
    all 5 stage agents that call `invoke_agent()` for JSON output
    (`requirements_agent.py`/`qa_agent.py`/`security_agent.py` found during this fix's
    own investigation; `ingestion_agent.py` found afterward during the four-stage
    migration's own close-out sweep). Real live-verification spend: **$0.526872**
    across 5 stages + 1 deliberate `max_tokens` probe. Full narrative:
    `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
32. ~~**ADO Enhancement work lands as a new parallel Epic, never linked to the
    existing Epic.**~~ — **RESOLVED AND LIVE-VERIFIED 2026-08-31**, per
    `docs/Specs/FORGE-Item32-ADOEpicLinkage-Spec.md`. `create_ado_items.py` gained
    a new `existing_service` param/`--existing-service` CLI arg and a
    `_resolve_existing_epic_id()` helper — for an Enhancement, Features/User
    Stories are now created as children of the existing service's own real Epic
    (looked up from its `ado-work-items.json`) instead of a brand-new,
    disconnected one; `02-design.yml` (the one remaining stage with zero
    Enhancement awareness) gained the matching "Determine Enhancement status"
    step. **This is the fourth occurrence of the same underlying pattern** — a
    pipeline stage built with zero `existing_service`/Enhancement awareness —
    following Item #24 (Stage 3), Item #25 (QA/Security), and Item #28 (Deploy).
    Live-verified against a throwaway, non-production existing-service Epic
    rather than REQ-2026-03's real Epic #134, to avoid polluting real backlog
    data with test items: Feature/User Story correctly parented under the reused
    Epic (independently confirmed via a fresh ADO API read); Greenfield path
    confirmed byte-for-byte unchanged (still creates a brand-new Epic); the
    deliberate-failure case (a bogus `--existing-service`) correctly raised
    before any ADO call and posted a real, readable failure comment. Commits:
    `bbbe3d0`, `759cc58`, `c4b3d0c`.
34. ~~**Stage 3 had no pre-flight cost estimate or human cost gate before a
    real Managed Agents session started.**~~ — **RESOLVED AND LIVE-VERIFIED
    2026-08-31/09-01**, per `docs/Specs/FORGE-Item34-CostEstimator-Spec.md`.
    New `cost-approved` label (required alongside `design-approved`, same
    two-label AND-gate shape as Item #26) gates the real coordinator run; a
    new estimate-only step posts a coarse, shape-bucketed cost estimate first.
    Live testing surfaced and fixed a real P0 bug found via this feature's own
    verification, not pre-existing: `usage.list_cost.amount` from the Managed
    Agents API is a string, not a number — an un-cast divide would have
    crashed the commit/PR/comment step on every real completed Stage 3 run.
    Both Greenfield (the first-ever real `(1, False)` single-unit data point)
    and Enhancement (`(2, True)` bucket, live existing-service seed-file
    scaling against the real REQ-2026-03) verified live end to end. Full
    narrative: `docs/CLAUDE-archive-2026-08-resolved-open-items.md`.
35. ~~**`verify-setup.yml` (and 8 other stage workflows, two layers deep) hardcoded
    `forge-demo-apps`/`spike99`/`Flamespiker` instead of reading config** — a genuinely
    new OM's App/target repo hit a real 404 on a fresh clone.~~ — **RESOLVED
    2026-09-01.** New repo Variables (`FORGE_TARGET_REPO`, `FORGE_GITHUB_OWNER`,
    `FORGE_ADO_ORG_URL`) replace two separate layers of hardcoding: Layer 1 (job-level
    `env:` blocks, all 9 stage workflows) and Layer 2 (the `create-github-app-token`/
    `checkout` steps' own `repositories:`/`owner:`/`repository:` inputs, which didn't
    even reference Layer 1's env vars — the exact bug pattern, fixed so it can't recur
    the same way). `qa_agent.py`/`security_agent.py`'s silent
    `os.environ.get(..., 'forge-demo-apps')` fallbacks now fail loud instead. Verified
    twice: against the real setup (a live run went from a real 404 to fully green), and
    via a genuine fresh-clone/different-target scratch retest confirming the fix reads
    `${{ vars.* }}` for real rather than coincidentally matching the old hardcoded
    values. Commits: `d40b761`, `5b8ace6`, `71424df`.
36. ~~**`team/config.yaml` had three mutually incompatible schemas** — README's example,
    the OM Guide's example, and the real shipped file each used different key names/
    nesting; neither doc's example keys existed in the real file at all.~~ —
    **RESOLVED 2026-09-01.** A full codebase grep found only two real consumers
    (`ado_helper.py` reads the nested `ado:` block; `deploy_agent.py` reads
    `container_apps.staging`) — every other key (`ado_org`, `ado_project`,
    `monorepo_name`, a top-level `area_path`/`tags`, `intake_method`,
    `notification_channel`, the entire `container_apps.production` block) was read by
    zero code. Trimmed the file to its two live blocks; fixed both docs' examples to
    match exactly; corrected the OM Guide's "repo path" intake alternative, which
    doesn't exist in code (only issue-attachment does). Commits: `53b3fd5`, `baddc8c`.
37. **`team/config.yaml`'s `ado:` block ships real live values (`spike99`/
    `FORGE-Build`), not placeholders** — investigated, not a bug. These are the correct,
    intentional values for the live deployment; trimming the dead keys around them
    (Item #36) was the right action, not a placeholder-ization. The real, still-open
    question this surfaced is architectural, not a code fix — see Item #41. Commit:
    `53b3fd5`.
38. **Single-repo model unsupported, undocumented** — all three governing docs
    (README, OM Guide, Customization Ref) assume a two-repo model throughout; none say
    what a team should do with only one repo available. Confirmed real during the 8.4
    walkthrough (a scratch repo had to play both roles as a judgment call, not a
    documented path). Not urgent — no team has hit this for real yet.
39. **GitHub "required reviewers" environment protection needs a paid plan on private
    repos** — neither the OM Guide nor the Customization Ref mention this; hit a real
    422 during the 8.4 walkthrough creating a protected `production` GitHub Environment
    on a private scratch repo. Two parts still open: a doc fix, and the real-stakes
    follow-up check of whether `forge-demo-apps`'s actual `production` environment has
    this protection genuinely active today (never independently confirmed).
40. **Doc-completeness batch — five small gaps from the 8.4 walkthrough, clubbable.**
    "Build Plan" referenced but undefined anywhere in README's reference table; ACR
    creation steps (SKU choice, admin-user enablement) undocumented; no documented way
    to confirm the Anthropic key is active; README Step 5 places Container App sizing
    directly after `az containerapp env create`, implying flags that don't exist on
    that command; ADO PAT creation UI mechanics undocumented. Also open: deciding where
    the verbatim gap log (`phase8-4-gaps.md`) should permanently live.
41. **`forge-template` conflates "Mike's live instance" and "public template source"**
    — confirmed live: the repo is `is_template: true`, and a real
    `gh repo create --template ...` test proved `team/config.yaml`'s live `ado:` block
    values (`spike99`/`FORGE-Build`) get copied verbatim into every new instantiation,
    not just this one. Design decision needed, no urgency: is this acceptable (a new OM
    overwrites `config.yaml` as their first setup step anyway), or does the dual role
    need untangling (e.g. a separate `config.yaml.example`)?
42. **Node.js 20 deprecation warning on `actions/checkout@v4`/`actions/setup-python@v5`**
    — surfaced as an unrelated annotation during Item #35's verification run. Low
    priority, not yet a functional break, but worth bumping action versions before
    GitHub makes it a hard failure.
43. ~~**No way for a requester to declare, at intake, how far the pipeline should
    go** — every run went all the way to Deploy once a human kept applying gate
    labels, with nothing but discipline stopping a request from rolling further
    (and spending more real Anthropic/Managed Agents/Azure cost) than
    intended.~~ — **RESOLVED AND LIVE-VERIFIED 2026-09-03**, per
    `docs/Specs/FORGE-Item43-PipelineDepth-Spec-v3.md` (Claude.ai, 3 revisions —
    v1 investigation-only, v2/v3 resolving Mike's design forks down to tier
    structure/parsing-location). New Intake Template Section B field, **Pipeline
    Depth** (`Just Requirements` / `Up to Design` / `Up to Implementation` /
    `Up to Deployment`, blank defaults to full pipeline) — a contiguous prefix
    selector, not a stage picker. Built across 6 commits: `4ab81a0` (Intake
    Template.xlsx field + Instructions tab + v1.1 bump), `ab5d8fb`
    (`requirements_agent.py` — parses the field, writes
    `docs/<request-id>/pipeline-config.json` to `pipeline-state`), `875b8d1`
    (`workflow_glue.py` — new `check-pipeline-depth` subcommand: tier
    comparison, terminal-stop comment + `pipeline-complete-at-depth` label,
    idempotent against a repeat trigger), `cd7431c`
    (`implementation_coordinator.py` — configured-depth note on the Item #34
    cost estimate), `fb8581a` (depth-check guard wired into
    `02-design.yml`/`03-implementation.yml`/`04-qa.yml`/`05-security.yml`/
    `06-deploy.yml`, Stage 3/4/5 sharing one "implementation" tier since QA/
    Security have no separate human gate to split on), `df557fc`
    (`06_Orchestration_v7.md` + `07_Customization_Ref_v4.md` documentation).
    One correction made during build, not in the original spec: the
    guard-clause insertion point is after each workflow's `Resolve request ID`
    step, not immediately after the label guard clause as v3's table assumed
    — `request_id` isn't resolved that early in Design/Implementation/QA/
    Security. **Live-verified via 3 real throwaway-issue tests, all passed**
    (`forge-template#14`/`#15`/`#16`, all closed, zero orphaned branches/PRs,
    **zero Azure infrastructure ever created**): Test 1 (Greenfield, `Up to
    Design`) confirmed Stage 2 ran normally and Stage 3 stayed blocked even
    with both `design-approved` and `cost-approved` present (isolating the
    depth gate from the ordinary two-label gate); Test 2 (Enhancement,
    `Up to Implementation`, existing service `REQ-2026-03`) confirmed Stage 0a/
    3/QA/Security all ran for real (real cost **$0.66**, PR
    `forge-demo-apps#44` merged) while Deploy stayed blocked even after a real
    confirmed merge with both `qa-approved`/`security-approved` present,
    verified independently via `az containerapp list` (nothing created); Test
    3 (blank depth) confirmed byte-for-byte pre-feature behavior — no
    depth-related comment anywhere, full backward compatibility. Surfaced two
    unrelated findings during verification, not Item #43 regressions: a
    transient `anthropic.OverloadedError: 529` (resolved via a routine
    label-reapply retry) and Item #44 below.
44. **`implementation_coordinator.py`'s `run_cost_estimate()` reads `tasks.md`
    from `main`, not the not-yet-merged `design/<request-id>` branch** — found
    live during Item #43's Test 1 verification (2026-09-03). If `design-approved`
    is applied before the design PR is merged, the pre-flight cost-estimate
    step 404s and fails the job outright, even though this is exactly the
    label-application order Document 6/the Orchestration Guide's own Gate 2
    text describes as *correct* (approve → merge → apply `design-approved`) —
    it only bites when that order is skipped, which is why it had never
    surfaced in any real request before. Worked around live via merge-then-
    retry, not fixed at the code level. Open.
45. **The `mike-digital-platform` swap's B.2 provisioning step created the
    GitHub repo but never seeded it — real Stage 1 (Requirements) failure,
    2026-09-04.** `commit_files()` (Git Data API: blob → tree → commit → ref
    update) requires the target branch to already exist and requires at
    least one commit to build a base tree from; a genuinely empty repo
    (`GET .../commits` → `409 Git Repository is empty`, `GET .../branches` →
    `[]`) has neither. This silently blocked Stage 1 the first time anything
    tried to write to the new target, on the very first real request run
    against it (`REQ-2026-01`, `forge-template#17`). **The swap's own
    "fully green `verify-setup.yml` run" claim (see Current Build Phase
    above) did not actually exercise this path** — `verify-setup.yml` only
    checks config/connectivity, not that `commit_files()` can write to the
    target; the post-swap checklist's "real (not dry-run) pipeline smoke
    test" bullet was satisfied by that connectivity check rather than an
    actual Stage 0→1 run, which is the only thing that would have caught
    this. Fixed live: seeded `main` with an initial commit (Contents API),
    then created `pipeline-state` pointing at that commit (Git Refs API) —
    `commit_files()`'s own docstring already says the branch "must already
    exist", so this was always a provisioning prerequisite, just never
    written down. `docs/FORGE-platform-swap-runbook.md` B.2 and the
    post-swap checklist updated 2026-09-04 to seed both proactively on every
    future swap, and to require a real Stage 1 run (not just
    `verify-setup.yml`) before signing off. A second failure on the same
    request, found immediately after fixing this one and also since fixed
    (a `_MAX_TOKENS` truncation on a 17-requirement intake — see Item #46's
    sibling note below) — separate root cause, same request.
46. **`requirements_agent.py`'s `_MAX_TOKENS = 8000` truncated on a
    17-requirement intake** (`stop_reason: "max_tokens"`, correctly detected
    and raised by the existing guard) — **found live 2026-09-04 on the same
    `REQ-2026-01` request as Item #45.** Raised to `16000`; comfortably
    covers this intake (8388 output tokens used) but remains a fixed
    ceiling, not a scaling one — a much larger intake (e.g. 50 requirements)
    could truncate again, and `invoke_agent()`/`claude_agent_wrapper.py` has
    no streaming support today, so pushing `_MAX_TOKENS` far higher risks
    the Anthropic SDK's own non-streaming ~10-minute-estimate guard
    (`ValueError`, raised before the request is even sent) rather than a
    clean truncation. Deliberately not built here: dynamic sizing off
    parsed requirement count + streaming support in the shared wrapper —
    scoped as a real fix, not a config bump, if a much larger intake
    actually shows up. Open (as a scaling question; today's real intake is
    fixed).

    **Recurred same day on the same request, Design stage — and this was the
    trigger to actually fix it, per the note above.** `design_agent.py`'s
    `_MAX_TOKENS = 20000` first truncated (used all 20000 tokens, cost
    $0.319032, 288s) generating `design.md` + `openapi.yaml` + `tasks.md`
    for REQ-2026-01's 6 Features / 17 User Stories — bumped to `32000`, but
    that config-bump attempt never even reached the API: `client.messages
    .create()` raised `ValueError: Streaming is required for operations
    that may take longer than 10 minutes` before sending anything. This is
    a proactive SDK-side guard keyed off `max_tokens`, not a request that
    actually ran long — so no further constant bump could ever have
    unblocked it. **Fixed at the root 2026-09-04:** `invoke_agent()` in
    `claude_agent_wrapper.py` now always calls `client.messages.stream(...)`
    + `stream.get_final_message()` instead of `client.messages.create()` —
    unconditionally, not just above some `max_tokens` threshold, since
    streaming has no downside at small `max_tokens` either and this removes
    the whole class of guard permanently for all 5 (now 6, still Stage-3-
    exempt) agents that share this wrapper. `get_final_message()` returns
    the identical `Message` shape `create()` did, so nothing downstream of
    that one call site changed — no ripple into token/cost logging or
    `output_schema` extraction. Live-verified against the real API on both
    paths this wrapper supports: plain text (existing
    `smoke_claude_agent.py`, unchanged, still 5/5) and forced tool-use
    structured output (a one-off script — `output_schema` produced the
    exact expected dict under streaming, `stop_reason: "tool_use"`). With
    the guard gone, `design_agent.py`'s `_MAX_TOKENS` was raised again, to
    `64000` — generous headroom now that generation time is no longer a
    proactive-block risk, only a real one (Sonnet's actual 128K output
    ceiling). Dynamic per-request-size sizing (mentioned above) is still
    not built — a static generous ceiling was sufficient once the real
    blocker (the non-streaming guard) was removed.
47. **A blank "Request ID" field on the intake spreadsheet silently
    resolves to `request_id="unknown"` with no warning anywhere** —
    confirmed live 2026-09-04, same `REQ-2026-01` request (`forge-template#17`,
    caught only because a human noticed "`docs/unknown/`" in the Requirements
    Agent's posted comment). `intake_agent.py`'s existing fallback-to-
    `"unknown"` behavior (documented, intentional, per its own `--request-id`
    docstring) means the pipeline runs to completion under a placeholder ID
    with zero surfaced error — and because `resolve_request_id()` (used by
    every stage from `01-requirements.yml` onward) returns the *first*
    `forge:agent-comment` marker found on the tracking issue, there is no
    supported code path to correct this after the fact: fixing it required
    manually editing both existing bot comments' markers and moving the
    already-committed `docs/unknown/*` artifacts to `docs/REQ-2026-01/*` on
    `pipeline-state` by hand. Fixed for this request only. **Not fixed at
    the code level** — no change made to `intake_agent.py`'s validation, no
    visible warning added to its posted comment, no pre-commit check added
    anywhere in the pipeline. A real fix (proposed, not built): either
    reject a blank Request ID outright at Stage 0 (posting a comment asking
    the BA to fill it in before proceeding), or at minimum have the Intake
    Agent's first comment carry a loud, impossible-to-miss warning banner
    when it falls back to `"unknown"`, so a human catches it at Stage 0
    instead of days later. Open.
48. **`implementation_coordinator.py`'s coordinator ended its own final turn
    without ever running the packaging step it was explicitly instructed to
    — real, expensive incident on REQ-2026-01, 2026-09-04.** After a real
    ~52-minute, ~$14.22 (`list_cost.amount` is cents, per Item #34) Stage 3
    run in which Backend, Frontend, and Test Writer subagents all genuinely
    completed (confirmed by the coordinator's own messages: "Backend and
    Frontend are both verified and complete" / Test Writer finished), the
    coordinator's last turn ended with `stop_reason: end_turn` — no tool
    call, no message — right where it should have run the `tar` packaging
    command into `implementation.tar.gz`. No `session.error`, no budget
    exhaustion, nothing pointing to a systemic cause; this reads as a
    one-off model lapse, not a reproducible bug, so nothing was changed in
    the coordinator's own prompt/instructions. **Recovered without
    redoing any of the paid-for work**: since the session was left idle but
    *not archived* (per Item #6/#8's existing safety check — exactly the
    scenario it was built for), a single follow-up `user.message` was sent
    to the live session asking it to run the exact packaging command from
    its own original instructions. It complied immediately, verified 117
    source files / 0 build artifacts / 278KB, and confirmed "IMPLEMENTATION
    COMPLETE." `--recover-session` then found the archive and completed the
    normal commit/PR/comment path (`mike-digital-platform#2`, 117 files,
    16458 additions) — for a small fraction of a full retry's cost.
    **This surfaced a second, real, previously-unobserved bug along the
    way, which WAS fixed at the code level:**
    `managed_agents_wrapper.py`'s `list_session_output_files()` defaulted
    to `limit=100` with no pagination — this session had accumulated **991**
    output files (Backend/Frontend/Test Writer apparently wrote real
    build/dependency artifacts into `/mnt/session/outputs/` over the
    52-minute run, not just the final archive), so the first recovery
    attempt genuinely failed to find `implementation.tar.gz` even though it
    existed (confirmed directly via the Files API with a raised limit).
    Fixed by raising the default to `1000` — the API's actual per-page
    ceiling, not an arbitrary guess — since this function has no
    pagination beyond one page; a session exceeding 1000 output files
    would need real pagination, not yet built since it hasn't been
    observed. Standing takeaway for any future stuck/failed Stage 3
    session: **don't assume a missing archive means the work is gone** —
    check whether the session is still alive (idle, not archived) before
    considering a costly full retry; a follow-up message or a
    `list_session_output_files` limit fix can be far cheaper than redoing
    real subagent work.
49. **The `mike-digital-platform` swap shipped with none of the cross-repo
    dispatch workflows — QA, Security, and Deploy would have silently never
    fired for any request.** Found live 2026-09-04, same day and same
    `REQ-2026-01` request as Items #45/#46/#48, after PR #2 (the recovered
    Implementation PR) sat with no QA/Security activity at all. Root cause:
    `notify-forge.yml` (forwards a feature PR's `opened`/`synchronize`/
    `closed` events to `forge-template` as `repository_dispatch`, which
    `04-qa.yml`/`05-security.yml`/`06-deploy.yml` all depend on) and its two
    companion no-op status workflows (`design-pr-security-noop.yml`,
    `ops-pr-security-noop.yml`) were never pushed to `mike-digital-platform`
    during the swap — `.github/workflows/` didn't exist on it at all.
    **Worse, this class of gap had no recovery path built in**:
    `docs/FORGE-platform-swap-runbook.md`'s B.3 (repoint the orchestration
    repo) never mentioned these files, and they had **never been committed
    to `forge-template` itself** — per the File Reference section elsewhere
    in this doc, they only ever lived in the *target* repo. Since Phase A of
    a swap deletes the old target repo, a swap with no separate backup of it
    would have made these files unrecoverable by any means. The only reason
    this one was recoverable at all: Mike happened to have a stale local
    clone of the deleted `forge-demo-apps` sitting on disk, predating Items
    #26/#30 (missing the `pr-merged` dispatch and `ops-pr-security-noop.yml`
    entirely) — recovered from there, not from anything in `forge-template`.

    **Fixed properly, not just patched for this one repo:**
    - Reconstructed all three files (extending the recovered `notify-forge.yml`
      with Item #26's `pr-merged` dispatch, and writing `ops-pr-security-noop.yml`
      fresh per Item #30's documented behavior) and committed **reference
      copies into `forge-template` itself**, at
      `core/templates/target-repo-workflows/` — the two no-op files rewritten
      to be fully self-referential via GitHub Actions' own `github.*` context
      (`github.repository_owner`, `github.event.repository.name`,
      `github.repository`), so copying them to any future target repo needs
      **zero edits**; only `notify-forge.yml` needs its two
      `YOUR_FORGE_OWNER`/`YOUR_FORGE_REPO` placeholders filled in, since it
      must point at a different, fixed repo (the orchestration repo) that
      can't be inferred from context.
    - Pushed all three to `mike-digital-platform` via personal git credentials
      (Contents API) — the App itself cannot write `.github/workflows/*`
      files (no `workflows` permission), confirmed live via a real 403 from
      `commit_files()` before switching approaches.
    - Set `FORGE_APP_CLIENT_ID` (variable) and `FORGE_APP_PRIVATE_KEY`
      (secret) on `mike-digital-platform` itself — neither existed there;
      these don't cross repos from the orchestration repo's own copies.
    - Manually fired the `feature-pr-opened` dispatch for the already-open
      PR #2 (pushing the workflow file doesn't retroactively trigger an
      already-open PR) — confirmed live that QA and Security both then
      started running against it for real.
    - `README.md` (new Step 4), `docs/06_Orchestration_v9.md` (new Step 5,
      v8→v9), and `docs/FORGE-platform-swap-runbook.md` (new B.3 §5, plus
      two new post-swap checklist items and a strengthened smoke-test bullet
      requiring a real run through Stage 5, not just Stage 1) all updated so
      a future fresh setup *or* swap has both the instructions and the
      actual files to copy from, not tribal knowledge or luck.
50. **Security Agent's Dependabot scanner failed (`403`) against
    `mike-digital-platform` — a documented one-time prerequisite from the
    old platform was never redone for the new one.** Found live 2026-09-04,
    same `REQ-2026-01` PR (`mike-digital-platform#2`) as Item #49, once
    Security actually started running for the first time. Verdict:
    `INCOMPLETE` — Semgrep and Gitleaks both ran clean (0 findings), but
    Dependabot alerts returned `403`, and `security_agent.py`'s own gating
    (`any_tool_failed`) correctly withheld `security-approved` rather than
    passing on partial results. Per this file's own security_agent.py
    section (written during the original `forge-demo-apps` setup): Security
    Agent's Dependabot check requires (a) Dependabot alerts + dependency
    graph enabled on the target repo, and (b) the `forge-pipeline` GitHub
    App's installation granted the `vulnerability_alerts` permission
    (Read-only) — both **repo-specific**, so neither carried over when the
    target repo changed. QA also did not pass on this same PR, for an
    unrelated real reason (a genuine frontend TypeScript compile error,
    `session` referenced out of scope in `app/(app)/assets/page.tsx:94` —
    `qa-loop-back` applied, ADO Bug #270 filed, attempt 1 of 3) — tracked
    here only for completeness of this PR's state, not as a platform gap.
    Fix requires Mike's own action (repo-owner + App-owner permissions,
    neither available to an API token) — open until done:
    1. Enable **Dependabot alerts** and **Dependency graph** on
       `mike-digital-platform` (Settings → Code security and analysis).
    2. Grant the `forge-pipeline` App the **Dependabot alerts: Read-only**
       permission (App settings → Permissions & events → add "Vulnerability
       alerts" as Read-only), then approve the resulting pending permission
       request on the installation (Settings → Applications → Installed
       GitHub Apps → forge-pipeline → Configure).
    3. Confirm via `GET /repos/Flamespiker/mike-digital-platform/vulnerability-alerts`
       returning `204` (not `404`) — same live-confirmation pattern used
       the first time this was set up for `forge-demo-apps`.
    4. Re-fire the `feature-pr-opened` dispatch for PR #2 (or push a new
       commit once the QA fix lands, which does it automatically) to get a
       real Security verdict.

    **Resolved 2026-09-05** — both manual steps done (Dependabot alerts
    enabled on the repo; the App's `vulnerability_alerts` permission turned
    out to already be granted at the App level, not per-repo, so nothing
    further was needed there). `GET .../vulnerability-alerts` confirmed
    `204`, and `get_dependabot_alerts()` succeeded for real (`0` alerts —
    at the time, correctly, since nothing had been scanned yet). **This
    fully fixed the 403 itself, but immediately surfaced a second, deeper,
    previously-unknown problem — see Item #52**: the resulting "0 findings"
    was not a real clean result either, for a structural reason unrelated
    to permissions.
51. **`create_ado_items.py` has zero idempotency protection — every
    re-trigger of `02-design.yml` creates a brand-new, complete, duplicate
    ADO Epic→Features→User-Stories hierarchy from scratch.** Found live
    2026-09-05 on `REQ-2026-01`: three separate, identically-titled Epics
    (#198, #222, #246) existed in ADO, each with its own full 24-item tree
    (1 Epic + 6 Features + 17 User Stories), confirmed via direct ADO
    queries — not a WIQL/display artifact. Root cause: `create_ado_items.py`
    runs as step 1 of `02-design.yml`, **before** `design_agent.py`'s own
    Claude call, and has no check for whether real ADO items already exist
    for this request — so it re-created a full tree on all three
    `requirements-approved`-triggered runs of `02-design.yml` for this
    request (19:09, 19:43, 20:02 on 2026-09-04), including the first two,
    which both later failed downstream (the `_MAX_TOKENS` truncation fixed
    earlier the same day) — the ADO side effect had already committed real,
    billable-nowhere-but-messy work items before that later failure
    occurred. Cleaned up live: the two orphaned trees (#198, #222 — 48 items
    total) confirmed via full parent-child traversal and soft-deleted via
    the ADO REST API (recoverable, not permanent); the real bugs filed
    during QA retries (`#270`, `#272`) were independently confirmed still
    correctly linked to Story `#248` in the surviving tree (`#246`), so
    nothing real was lost. **Not fixed at the code level** — no idempotency
    check was added to `create_ado_items.py`. A real fix would need it to
    check `docs/<request-id>/ado-work-items.json` for already-populated
    real ADO IDs (written back by a prior successful run) and skip
    re-creation, or a query against ADO itself for an existing Epic with a
    matching title/tag. Open.
52. **Security Agent's Dependabot check produces a false-clean result on a
    Greenfield request's first-ever Implementation PR — a structural gap,
    not a permissions issue.** Found live 2026-09-05, immediately after
    Item #50's fix: with the 403 resolved, Security passed with "0 findings"
    across all three tools — but direct inspection of
    `mike-digital-platform`'s dependency-graph SBOM showed only **2**
    entries total (the repo itself and one GitHub Action dependency from
    the workflow files) — zero npm or NuGet packages. `main` was confirmed
    to have **no application code at all** (only `.github/`, `README.md`,
    `docs/` — the real `package.json`/`.csproj` files exist only on the
    unmerged `feature/REQ-2026-01` branch). This is not a "wait for the
    dependency graph to catch up" timing issue: GitHub's dependency graph
    only scans the **default branch**, and QA/Security gate **before**
    merge by design (Document 6) — so there is structurally nothing for
    Dependabot to ever find on a brand-new repo's first Implementation PR,
    no matter how long it waits. `security_agent.py`'s existing safeguard
    (`get_dependency_graph_package_count() == 0` → treat as a scan failure,
    not a clean pass — see Item #50's own code excerpt) exists for exactly
    this situation, but only fires on a package count of **exactly 0**; a
    partially-populated graph (our real count: 2) slips through as if fully
    populated. Likely always a latent gap in the original design — never
    surfaced before because every prior live validation of this scanner
    happened against `forge-demo-apps`, whose `main` already had substantial
    real application history merged from earlier requests by the time it
    was tested (confirmed 1512 real SBOM packages there). This is the first
    time the scanner was ever exercised against a repo's true first-ever
    Implementation PR. `security-approved` is currently sitting on
    `REQ-2026-01` (`forge-template#17`) as a false-clean — the real
    dependency vulnerability status of Fiddy5's actual packages (including
    `next@14.2.5`, a version with a documented history of real CVEs per
    Item #19/#20's Dependabot triage) is genuinely unknown.

    **Resolved 2026-09-05, at the code level.** Investigated GitHub's actual
    first-party answer to "scan a PR's real dependencies before merge" —
    the Dependency Review API (`dependency-graph/compare/{basehead}`) — and
    confirmed live it returns `403` on `mike-digital-platform` specifically
    because it requires paid **GitHub Advanced Security** on private repos
    (confirmed via GitHub's own docs, not assumed). Not available on this
    instance's current plan. Built the free substitute instead: two new
    scanners in `security_agent.py`, `_run_npm_audit()` and
    `_run_dotnet_audit()`, using `npm audit --json` and `dotnet list package
    --vulnerable --include-transitive --format json` — both read the real
    manifests on the actual PR checkout directly, with no dependence on any
    other branch's state, the same way Semgrep/Gitleaks already do. Kept
    alongside Dependabot (still the right tool for continuous, repo-wide,
    post-merge monitoring) rather than replacing it. Confirmed live against
    a real historical checkout: `npm audit` needs only `package.json`/
    `package-lock.json` (works with `node_modules` absent — verified by
    removing it and re-running, identical result); `dotnet list package
    --vulnerable` requires `dotnet restore` first (errors clearly otherwise)
    — both scanners handle this. Backend unit discovery reuses
    `deploy_agent.py`'s own convention (`rglob("*.csproj")`, skip any path
    segment containing "test") so this scans the same real units Deploy
    will later build. `05-security.yml` gained explicit `actions/setup-
    dotnet@v4`/`actions/setup-node@v4` steps (matching `04-qa.yml`'s pinned
    versions, `8.0.x`/`20`) since this job previously only needed Python;
    also removed a stale OWASP Dependency-Check install step left over from
    before the 2026-08-19 Dependabot swap (never invoked by any code since
    then — wasted CI time, found while already in this file). Live-tested
    both new scanners directly against a real checkout before pushing:
    correctly found 8 real npm findings and 25 real NuGet findings on an
    un-patched historical checkout, and correctly returned a clean
    `ran=True, 0 findings` (not a false failure) when no frontend/backend
    directory exists at all. **Caveat found minutes later (see Item #54):**
    that historical checkout happened to already have a real committed
    `package-lock.json` from months of actual dev work — the untested case
    was a real request's frontend with no lockfile at all, which is exactly
    what Fiddy5 turned out to have, and it silently broke `npm audit` in a
    different way than any case this test suite covered. **Immediate
    app-level fix, same commit cycle:**
    bumped Fiddy5's `next` 14.2.5 → 14.2.35 (the exact fix already validated
    for `REQ-2026-03`) and, going one step further than that historical fix
    did, also bumped the paired `eslint-config-next` to the same version
    (a devDependency, lower real risk, but a one-line fix that fully closes
    this finding class rather than leaving the known partial gap the
    original fix left behind). **Forward-looking note, per Mike:** this
    instance will likely move to a GitHub plan with Advanced Security
    included at some point — `security_agent.py`'s own comment block now
    flags this explicitly: prefer switching to the Dependency Review API
    when that happens (richer data — "was this vulnerability newly
    introduced by this PR," not just "does it exist at all") rather than
    treating npm audit/dotnet list package as the permanent answer.
53. **QA's retry-limit guard doesn't actually block a 4th attempt — the
    label it checks for is never applied at the boundary where the report
    text says it is.** Found live 2026-09-05 on `REQ-2026-01`: QA's
    attempt-3 report explicitly said "Retry Limit Reached... Manual triage
    required... No further automated retries will occur," but the label
    actually applied was `qa-loop-back` — not `qc-retry-limit-reached`,
    which is what `run_qa_agent()`'s own pre-run guard checks for (per this
    file's qa_agent.py section: "checks for an existing `qc-retry-limit-
    reached` label before running any test suite and skips entirely if
    present"). Confirmed live: pushing a fix after attempt 3 triggered a
    real attempt 4 (which passed), proving the guard never engaged. Likely
    an off-by-one between the message-text threshold (`attempt >= 3`,
    "no more retries" wording) and the actual label-application threshold
    (`attempt > 3`, per this file's existing qa_agent.py docs: "`qa-loop-
    back` (failures, attempts ≤ 3), or `qc-retry-limit-reached` (failures,
    attempts > 3)") — attempt 3 is `≤ 3`, so `qa-loop-back` was correctly
    applied *by that rule*, while the human-facing message text was written
    as if attempt 3 were already the final, blocked attempt. Not fixed at
    the code level — needs either the message softened to match the real
    (`attempt > 3`) blocking threshold, or the threshold itself changed to
    match the message's stated intent (block starting at attempt 3, not 4).
    Open.
54. **`_run_npm_audit()` (added the same day, Item #52's own fix) silently
    treated its own tool-level error as a clean scan — a false-clean bug in
    a fix for a false-clean bug.** Found live 2026-09-05, minutes after
    declaring Item #52 fixed and verified, only because Mike asked "I still
    don't understand how zero findings came up" instead of accepting the
    reported all-clear at face value. Root cause: Fiddy5's real
    `frontend/` has no committed `package-lock.json`, and `npm audit`
    hard-requires one — without it, it exits 1 with a top-level `{"error":
    {"code": "ENOLOCK", ...}}` JSON body that has no `"vulnerabilities"`
    key at all. The parser only ever checked for that key's presence, so
    the missing lockfile silently produced `ran=True, 0 findings` instead
    of a scan failure — confirmed by reproducing the exact subprocess call
    locally (`shutil.which("npm")`-resolved, matching `_run_shell()`
    exactly) and inspecting the real stdout byte-for-byte. Fixed two ways:
    generate a lockfile on the fly with `npm install --package-lock-only`
    when one's missing (npm's own suggested remedy in the ENOLOCK message;
    confirmed live at ~37s for a real Next.js app, well under the 600s
    ceiling) — turning "can't scan" into "scans for real" rather than
    perpetually reporting incomplete — plus an explicit top-level `"error"`
    key check as defense in depth against any other error shape npm audit
    might return. **Re-verified locally before pushing, this time against
    the real generated lockfile, not just the error path:** 5 real HIGH
    findings surface for Fiddy5, including `next` itself — 21 CVEs with no
    14.x backport (vulnerable range `9.3.4-canary.0 - 16.3.0-preview.10`,
    published after 14.2.35 shipped), the exact same already-known,
    already-accepted-risk category this file's Item #11 already documents
    for other requests on the 14.x line — plus 4 dev/build-tooling-only
    findings (`glob`, `postcss`, `eslint-config-next`,
    `@next/eslint-plugin-next`) not shipped to the deployed runtime app.
    **Standing lesson, worth restating given this is the second false-clean
    found in one afternoon (the first being Item #52 itself):** a
    deterministic scanner returning "0 findings" is not self-verifying —
    always check what a zero actually means (tool genuinely ran clean vs.
    tool couldn't run at all and defaulted to zero) before trusting a
    result, especially for a scanner that's brand new and has not yet been
    exercised against a real, previously-known-vulnerable target.
55. **Frontend Lockfile Commit Gap — the same missing-`package-lock.json` root
    cause behind Items #52/#54 also broke Deploy's own `npm ci` Docker build
    step (Fiddy5, 2026-09-04), fixed live via a targeted manual unblock at the
    time (commit lockfile to `main`, replay `pr-merged`) with the systemic
    fix deferred to this item.** Built and locally verified 2026-09-05, two
    parts:
    - **Part A (Deploy Agent safety net):** new `_ensure_frontend_lockfile()`
      in `deploy_agent.py`, called from the per-unit pre-build loop right
      alongside `_ensure_frontend_public_dir()` (same established pattern —
      a filesystem-level fixup applied to every frontend unit before
      `_docker_build()`). No-ops if `package-lock.json` already exists.
      Otherwise reuses `_run_npm_audit()`'s exact `npm install
      --package-lock-only` pattern (Item #54) rather than reimplementing it;
      a failure there raises `RuntimeError`, handled by `run_deploy_agent()`'s
      existing ADR-0011 try/except — not a new failure mode. The generated
      lockfile is committed back to `main` (Deploy always builds from an
      already-merged commit — see `run_deploy_agent()`'s own "Deploys against
      the feature PR's HEAD commit" note) via a new `commit_files()` call,
      but only after a **fresh** API read (new `github_helper.
      get_branch_head_sha()`, added alongside `commit_files()` and reusing
      its exact `git/ref/heads/{branch}` lookup) confirms `main`'s current
      tip still equals `commit_sha`. A mismatch, or the commit itself
      failing for any other reason, is logged and skipped — never blocks the
      build, which always proceeds against the just-generated local file
      either way.
    - **Part B (Implementation-stage source fix) — confirmed real insertion
      point, investigated rather than assumed:** the Frontend subagent's
      task instructions live in `core/agents/subagents/frontend_agent.py`'s
      `SYSTEM_PROMPT`, **not** `tasks.md` generation. But subagents make "no
      direct commits" (confirmed via both `backend_agent.py`'s and
      `frontend_agent.py`'s own module docstrings) — the real commit happens
      later, in Python, when `implementation_coordinator.py` tars the shared
      sandbox filesystem and `commit_files()`s the archive. So this is
      genuinely **two** insertion points, not one — flagged per the original
      spec's own instruction to report back if the structure turned out to
      differ from a single clean location — matching this codebase's
      existing Item #8 "Layer 1 prevention + Layer 2 backstop" shape rather
      than inventing a new pattern:
      - Layer 1 (`frontend_agent.py` `SYSTEM_PROMPT`): the existing "only
        source and config files... belong there" line was ambiguous enough
        to plausibly read `package-lock.json` as excluded
        installed-dependency output like `node_modules/` — added an explicit
        exception clarifying it must be committed, generated as a normal
        `npm install`/`npm run build` side effect.
      - Layer 2 (`implementation_coordinator.py`'s `_COORDINATOR_SYSTEM_PROMPT`,
        step 5 "Critical packaging rules"): added an explicit pre-archive
        check — confirm `package-lock.json` exists in `frontend/` for any
        Node-based unit, generating one itself via `npm install
        --package-lock-only` if Frontend didn't leave one behind, before
        `tar`-ing the archive.
    - **Test results:** all four scenarios from the original spec were run.
      Tests 1/3/4 (self-heal-and-commit on a ref match; no-op when a
      lockfile already exists; self-heal-locally-but-skip-the-commit on a
      ref mismatch) were run as real local functional tests against
      `_ensure_frontend_lockfile()` — a real `npm install --package-lock-only`
      genuinely executes and produces a real lockfile in all three;
      `commit_files()`/`get_branch_head_sha()` were monkeypatched only to
      avoid a real GitHub write, not to fake the core logic under test — all
      three passed, including confirming zero npm/API calls fire at all when
      a lockfile is already present (test 3). **Test 2 (confirm Part B's
      prompt change actually prevents the gap in a real Stage 3 run) was
      deliberately deferred, not run** — verifying a prompt-only change
      requires a real Managed Agents session (real cost, 35-55+ min per this
      file's own "Implementation completion detection" section), and unlike
      Parts A/1/3/4 there's no cheaper local proxy for LLM prompt-following
      behavior; same cost/time deferral precedent as Item #6's live
      Stage 3 re-test. Flagged here rather than silently claimed as verified.
    - Commits: `core/agents/utils/github_helper.py` (`get_branch_head_sha()`),
      `core/agents/deploy_agent.py` (Part A), `core/agents/subagents/
      frontend_agent.py` (Part B Layer 1), `core/agents/
      implementation_coordinator.py` (Part B Layer 2), this CLAUDE.md entry —
      five separate commits, one per logical unit (same convention as
      Item #43).
56. **Google sign-in was completely non-functional on the deployed Fiddy5
    app, and investigation surfaced a deeper backend gap than the missing
    credentials alone.** Found live 2026-09-05: `req-2026-01-frontend` had
    only `NEXTAUTH_URL` set — `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/
    `NEXTAUTH_SECRET` were all missing, so no sign-in could ever complete.
    Fixing that alone would not have been enough — `UserSyncMiddleware.cs`
    already auto-provisions a `User` row for any authenticated Google
    account, but `HouseholdController.cs` only ever exposed `ListMembers`/
    `InviteMember`/`ListInvitations`, all three requiring the caller to
    **already** belong to a household. There was no endpoint anywhere that
    let a brand-new user with no pending invitation create their own
    household — meaning the very first user of this app could never
    actually get in, regardless of OAuth credentials being correct.

    **Built and locally verified 2026-09-05:** new `POST /api/household` in
    `HouseholdController.cs` (`mike-digital-platform`, branch
    `feature/google-oauth-setup`, commit `e90ed8d`) — the caller becomes the
    new household's admin (`Household.AdminUserId` + `HouseholdMember.
    IsAdmin=true`), matching the shape every other household-aware endpoint
    already expects. Verified via a standalone throwaway console program
    (not part of either repo) that loads the real `HouseholdController`
    class against EF Core's InMemory provider — not a real Postgres
    container, per the new Docker Desktop convention above: create-then-
    create-again for the same user correctly rejects the second call with
    `400 ALREADY_HAS_HOUSEHOLD` and creates no duplicate row; two different
    users each get their own independent household with no cross-
    contamination. 18/18 checks passed. `dotnet build` also confirmed clean
    beforehand. Also added a repo-wide `.gitignore` to `mike-digital-
    platform` (commit `a24fb62`) — the repo had none at all, so a first
    local `dotnet build` left `bin/`/`obj/` showing as untracked.

    **Not yet done:** the Google Cloud Console OAuth client itself (Mike's
    own action — consent screen, credentials, redirect URI pointed at
    `req-2026-01-frontend.braveground-19119157.canadacentral.
    azurecontainerapps.io/api/auth/callback/google`); wiring the resulting
    `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/a generated `NEXTAUTH_SECRET`
    into the Container App via the existing `_wire_keyvault_secret()`
    pattern; a frontend onboarding step so a new user without a household
    is routed to create one (today's login page still only has a single
    "Continue with Google" button); and a live end-to-end test through
    real Google sign-in, since the InMemory check above only covers the
    backend logic in isolation. Tracked under ad hoc issue
    `forge-template#18` (opened specifically for this work, separate from
    REQ-2026-01's original tracking issue `#17`, per Mike's choice) — seeded
    with a `forge:agent-comment` marker comment so `resolve_request_id()`
    resolves it to `REQ-2026-01` for QA/Security dispatch once a PR opens;
    confirmed live via a direct `resolve-request-id` run. Local clone of
    `mike-digital-platform` now exists at `C:\Users\mikef\projects\
    mike-digital-platform` (sibling to this repo), on branch
    `feature/google-oauth-setup` — not yet pushed to origin, no PR opened
    yet.

Full narrative for Items #35-#42: `docs/FORGE-Open-Items-Backlog-v9.md`.

## Further reading

- The newest `docs/FORGE-context_v*.md` — Claude.ai-maintained narrative/open-items doc;
  read this alongside this file each session.
- `docs/CLAUDE-archive-2026-08-phase3-5.md` — Phase 3/4 build-out + Phase 5 pre-flight
  fixes, verbatim.
- `docs/CLAUDE-archive-2026-08-req2026-02.md` — REQ-2026-02 fix cycle, verbatim.
- `docs/CLAUDE-archive-2026-08-req2026-03.md` — REQ-2026-03 build + PR #20/Deploy cycle,
  verbatim.
- `docs/CLAUDE-archive-2026-08-resolved-open-items.md` — full verbatim narratives for
  every resolved Open Item (all except #7/#11, which remain open in this file), moved
  here 2026-08-31 to keep this file lean.
- `docs/FORGE-pipeline-cost-log.md` — token/Managed Agents/ACR cost tracking.
- `docs/CLAUDE-archive-2026-09-platform-swap-mdp.md` — full platform-swap narrative
  (forge-demo-apps → Mike Digital Platform), verbatim.
