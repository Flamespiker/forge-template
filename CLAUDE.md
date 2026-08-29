# FORGE — Claude Reference

This file captures decisions, conventions, and setup notes for the forge-template project.
Read this at the start of every session before making changes.

---

## Project Overview

FORGE is an AI-orchestrated SDLC platform for Legal Aid Alberta. It takes BA-produced Excel
intake spreadsheets through a full pipeline (requirements → design → implementation → QA →
security → deploy) with human approval gates at each stage.

- **FORGE repo:** `forge-template` (GitHub: `Flamespiker`) — orchestration machinery only
- **Target repo:** `forge-demo-apps` (GitHub: `Flamespiker`, private) — stand-in for LAA's
  application monorepo during the build/demo phase
- **ADO org:** `https://dev.azure.com/spike99` — project `FORGE-Build`
- **Full project context:** the newest `docs/FORGE-context_v*.md` — read this for
  architecture decisions, agent roster, pipeline stages, and session history
- **This file's history:** trimmed 2026-08-18 to stay lean (it's loaded into every
  session). Full pre-trim narrative lives in `docs/CLAUDE-archive-2026-08-*.md` — see
  "Further reading" at the end of this file.

---


## Current Build Phase

**Phase 7 (Enhancement Workflow) is underway — Build Plan step 7.1 (Codebase
Ingestion Agent, Stage 0a) is complete and live-verified (2026-08-27).** New
`core/agents/ingestion_agent.py`, a new `github_helper.get_repo_tree()`, Stage 0a
wiring in `00-intake.yml`, and optional existing-architecture-summary.md fetches in
`requirements_agent.py`/`design_agent.py` — see "ingestion_agent.py — Stage 0a
(Codebase Ingestion)" below for the full writeup. Build Plan step 7.2 (choosing/
writing the actual enhancement request's intake spreadsheet) has not started —
per `docs/FORGE-Phase7-Ingestion-Agent-Spec.md`, that's explicitly a separate,
later session's work.

**Stage 3 (Implementation) now correctly extends to Enhancement requests — built
and live-verified 2026-08-28.** Previously `implementation_coordinator.py` always
targeted `services/<request_id>/` unconditionally, so an Enhancement would have
built a brand-new folder from scratch instead of editing the real existing service
— this was Build Plan step 7.6's literal acceptance bar and the mechanism blocking
it. See Open Item #24 below for the full fix narrative (mount-path rewrite
discovery, the Layer-2 comment fix, the stale-code trigger incident, and live
verification via `forge-demo-apps#32`). Build Plan v9's own step 7.6 checkbox
still needs updating on the Claude.ai side — this session only touched
`CLAUDE.md` per its own scope.

**QA (Stage 4) and Security (Stage 5) now correctly resolve an Enhancement
request's real target directory too — built and live-verified 2026-08-28.**
Item #24 fixed Stage 3; QA and Security had never been updated to match, so
an Enhancement request reaching those stages hit `services/<request_id>/`
(nonexistent) instead of the real `services/<existing_service>/` — QA
silently false-positive-passed with zero real test coverage, Security
crashed. See Open Item #25 below for the full fix narrative (the shared
`resolve_service_root()` helper, QA/Security fail-loud fixes, the Dependabot
filter fix, a second stale-code incident, a real frontend-install CI gap the
fix itself exposed, and full live re-verification against
`forge-demo-apps#32`/`forge-template#10` ending in a genuine `qa-approved` +
`security-approved` pass). Item #27 (a related, separately-discovered
stale-label-clearing bug in `04-qa.yml`) was found and fixed during this same
verification pass — see its own entry below.

**Deploy (Stage 6) now correctly resolves and updates an Enhancement
request's real existing-service Container Apps too — built and
live-verified 2026-08-29.** Items #24/#25 fixed Stage 3/QA/Security; Deploy
had never been updated to match, so an Enhancement reaching Deploy hit
`services/<request_id>/` (nonexistent) and raised `ValueError: No
deployable units detected`. Unlike the other three stages, Deploy also owns
a live, named Azure resource — fixing directory resolution alone would have
deployed the existing service's real code under a brand-new, never-touched
Container App set. See Open Item #28 below for the full fix narrative (the
`naming_id` concept, the `_finalize_unit_name()` byte-for-byte reproduction
confirmation, and full live re-verification against
`forge-demo-apps#32`/`forge-template#10` ending in a genuine update-in-place
redeploy).

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

## Key Decisions Made This Session

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
- `_parse_model_json()` defensively strips ` ```json ``` ` fences if the model adds them despite
  instructions; raises `json.JSONDecodeError` otherwise, caught by the outer `try/except`.
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

## Outstanding Before Phase 3 Continues

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
mid-Console-review) needs to be killed right now. Live-verified end-to-end 2026-08-27
against a real running session (`sesn_01AbaBvHhDkLpkRPHRFdrFLF`, REQ-2026-04, killed
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
empty on the 2026-08-27 kill — but it costs nothing to check before the environment
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
`status` flips to `terminated`. All calls 200'd on the first try in the 2026-08-27
run — no need for the wrapper's idle→running archive-retry dance, since by this point
every thread was already confirmed idle in Step 2.

**Why this isn't wrapped into a repo script (yet):** it's a rare, manual,
human-in-the-loop action (someone in the Console deciding to kill a session), not
something any automated pipeline stage should ever do to itself. If this keeps coming
up, the right fix is a small `--force-kill SESSION_ID` CLI mode alongside
`--recover-session` — not yet built.

---

## Open Items / Known Gaps

1. **Deploy Agent had no app-secrets wiring mechanism — the wiring *primitive* is now
   built (2026-08-19), but the harder question is still open.** `_wire_keyvault_secret()`
   (see deploy_agent.py above) solves "how do we wire an already-known secret into a
   Container App" — Key Vault references via managed identity, generic, reusable. It does
   **not** solve "how does Deploy Agent learn a given app needs a given secret in the
   first place" — that's still pure tribal knowledge, confirmed zero machine-readable
   declaration exists anywhere (checked `.env.example`, `design.md`, `tasks.md`,
   `package.json`, all agent code). Every wiring so far (REQ-2026-03's
   `NEXTAUTH_SECRET`/`NEXTAUTH_URL`) has been a manual, one-off `--wire-keyvault-secret`
   invocation, not something Deploy Agent decides to do on its own.
   **Concrete real-world instance, found 2026-08-26 (app-level, not fixed, not a
   forge-mechanism bug — out of scope for that session's "forge mechanism, not apps"
   filter):** `req-2026-01-email-worker` is crash-looping in staging — revision
   `req-2026-01-email-worker--0000001` is `healthState: Unhealthy`/`runningState: Failed`,
   its one replica stuck `NotRunning`/`Waiting`. Live container logs show an unhandled
   `System.FormatException` on every startup attempt — `"The connection string could not
   be parsed; either it was malformed or contains no well-known tokens"` — thrown
   constructing `ServiceBusClient` at `Program.cs:20`. Pre-dates 2026-08-26's session
   (the crash is in `EmailWorker`'s own code/config, unrelated to that session's
   app-insights-fix image tag); the Service Bus connection string was apparently never
   given a valid value — exactly the kind of secret Deploy Agent has no mechanism to
   discover it needs, per this item. Left as-is deliberately — not investigated, not
   fixed, flagged here for whenever this item gets picked up for real.
2. ~~**REQ-2026-03's backend unit name doesn't fit Azure's Container App name length
   limit**~~ — **RESOLVED 2026-08-18.** `deploy_agent.py`'s `_validate_unit_name()`
   (raise-only) replaced with `_finalize_unit_name()` (deterministic truncation + 6-char
   sha256-hash suffix on a length-only failure); see "Unit naming and validation" above
   for the full scheme and its 2026-08-17 boundary correction (real Azure limit is
   `len < 32`, not `<= 32`). Verified live: `req-2026-03-on-call-roster-tracker-api` (38
   chars, previously raised) now resolves deterministically to
   `req-2026-03-on-call-rost-5bb949` (31 chars); a real non-dry-run deploy against
   forge-demo-apps' merged main (PR #20) built, pushed, and deployed it — live at
   `req-2026-03-on-call-rost-5bb949.yellowmeadow-894377a9.canadacentral.azurecontainerapps.io`.
   All 4 previously-passing unit names confirmed byte-identical under the new scheme (no
   regression).
3. ~~**No pipeline stage validates that the app actually builds before Stage 6
   (Deploy).**~~ — **FIXED AND VERIFIED 2026-08-24** (per
   `docs/FORGE-Pipeline-Hardening-Spec.md`'s Fix 3). New `_validate_frontend_build()` in
   `qa_agent.py` runs `npm run build` (`next build`) alongside the existing frontend test
   suite — not instead of it — and reports a failure the same way Fix 1 (below) treats a
   collection failure: High severity, blocks `qa-approved`, subject to Fix 2's retry
   ceiling, no new outcome category beyond pass/fail/`not_applicable`. A build failure
   supersedes whatever the test suite already reported, since nothing about the suite can
   be trusted as deployable if the build itself is broken.
   **No equivalent backend step was needed** — confirmed live via two separate real
   injected errors into REQ-2026-03's API project (not its test project), each followed
   by running only `dotnet test` (never `dotnet build` directly) from the test project:
   (1) a syntax error (garbage tokens) → `CS1733`/`CS1002`; (2) a genuine semantic type
   error (`int x = "a string";`) → `CS0029: Cannot implicitly convert type 'string' to
   'int'`, confirmed via the compiler's own diagnostic output, not assumed from
   documented `ProjectReference` behavior. Both times `dotnet test` failed (exit 1)
   before producing a TRX report, which `_run_backend_tests()`'s existing "no TRX
   produced" path already reports as a genuine QA failure. `dotnet test`'s implicit
   build already covers the referenced API project transitively via the test project's
   own `ProjectReference` — a separate `dotnet build` step would be redundant. Both
   injected errors were reverted immediately after (`git checkout --`/clone discarded),
   confirmed via a clean `git status` / directory removal.
   Deliberately scoped to the language-level build only (not `docker build` — that needs a
   working Dockerfile, which for a request with none yet committed depends on Deploy
   Agent's own template-generation logic, out of order for Stage 4).
   **Real finding surfaced during verification:** the two "pre-existing `next build`
   failures" originally recorded below this item (Open Item #20) were tested on a Windows
   machine. Re-verifying inside a `node:20-bullseye` Linux container (matching
   `04-qa.yml`'s actual `ubuntu-latest` runner) showed REQ-2026-02 and REQ-2026-03 both
   build cleanly on Linux — only REQ-2026-01's TypeScript type-conflict error is real and
   OS-independent. Item #20 and PR #24 were both corrected. This also confirms Fix 3 is
   safe to land as designed, since it runs in the same `ubuntu-latest` environment that
   container reproduces.
   Verified against real code: the extracted build-validation logic, run inside that same
   Linux container, correctly reports `ran=False` with the real compiler error surfaced
   for REQ-2026-01, and `ran=True` (no false positive) for both REQ-2026-02 and
   REQ-2026-03. A scoped local integration harness against `run_qa_agent()` itself
   confirmed 4 cases: tests-pass+build-passes → `qa-approved`; tests-pass+build-**fails**
   (the actual shape of both real incidents) → build failure supersedes, blocks
   `qa-approved`; tests-fail+build-passes → still fails, from the test failure; no build
   script declared → build step never invoked, zero behavior change. Timing: QA's real
   per-suite ceiling is `_TEST_TIMEOUT_SECONDS=1800s` (confirmed by reading the constant,
   not assumed — Security's 600s figure does not apply here); a Windows-Docker-bind-mount
   timing measurement came in at 417s, almost certainly inflated by cross-filesystem I/O
   overhead rather than representative of native Linux CI — still comfortably within
   1800s even under that pessimistic reading, but real confirmation should come from the
   first live GitHub Actions run.
4. ~~**`qa_agent.py`'s Jest/Vitest JSON parsing has a file-collection blind spot**~~ —
   **FIXED AND VERIFIED 2026-08-24** (per `docs/FORGE-Pipeline-Hardening-Spec.md`'s
   Fix 1). New `_jest_collection_failures()` scans every `testResults[]` entry for
   `status == "failed"` with an **empty** `assertionResults[]` — the real, confirmed shape
   (via a live broken-import fixture, both Jest and Vitest) of a file that failed to
   *collect* at all, as opposed to one that collected fine and had real per-test
   assertion failures (non-empty `assertionResults[]`). Critically, this does **not** key
   off the top-level `numFailedTestSuites` counter — confirmed live that a genuine
   per-test assertion failure *also* sets `numFailedTestSuites: 1`, so that field alone
   can't distinguish the two cases. A detected collection failure routes into the
   existing `ran=False`/`run_failure_message` path (the same one already used for "no
   JSON report produced at all"), which already gets High severity, blocks
   `qa-approved`, and counts against the retry ceiling with zero other code changes.
   Verified against all four acceptance criteria using real captured Jest/Vitest
   `--reporter=json` output (not assumed from memory): a broken-import fixture on both
   runners now reports a genuine failure; a genuine mixed pass/fail suite is unaffected;
   a fully clean suite is unaffected; the `not_applicable` path never calls this parser
   at all (structurally unreachable, no regression possible).
5. ~~**QA's `_MAX_RETRIES = 3` only picks which label to apply — it never blocks or gates
   a re-run.**~~ — **FIXED AND VERIFIED 2026-08-24** (per
   `docs/FORGE-Pipeline-Hardening-Spec.md`'s Fix 2). `run_qa_agent()` now checks — before
   running any test suite or filing any bug — whether `qc-retry-limit-reached` is already
   applied to the tracking issue; if so, the run is skipped entirely and a comment
   explains why, consuming no attempt and re-labeling nothing. Read-only check
   (`get_issue`), so it also runs correctly under `--dry-run` (prints instead of posting).
   **Design decision** (per Document 4's human-gate-at-every-stage principle, chosen over
   an alternative that would gate directly on `attempt_number > _MAX_RETRIES` pre-execution
   — rejected because it would break manual recovery, since comment-count-based
   `attempt_number` doesn't reset when a label is removed, and would require the skip path
   to also apply labels itself): the ceiling blocks further *automatic* QA runs, but a
   human can still recover by removing `qc-retry-limit-reached` — the next PR push or a
   manually replayed dispatch event then runs QA normally with a fresh attempt count. Not
   a permanent dead end. `_MAX_RETRIES`'s value (3) and `_count_prior_qa_attempts()`'s
   counting mechanism are both unchanged — this only adds enforcement on top of the
   existing, correct counting logic.
   Verified via a scoped local test harness (mocking `get_issue`/test execution/
   `post_comment`/`add_label`/`create_bug`) rather than a live 4-cycle PR run, which would
   mean filing real ADO bugs and burning real PR cycles just to test enforcement logic:
   ceiling already present → skipped before any test execution, comment posted, no label
   re-applied, no bugs filed (holds even when this run's tests would have passed — the
   guard checks label state, not test outcome); normal 1-attempt-pass and
   3rd-attempt-then-pass cases → zero behavior change; the attempt that first exceeds
   `_MAX_RETRIES` on a genuine failure still runs and sets `qc-retry-limit-reached` for
   the first time, as today — only a *subsequent* dispatch after that point gets skipped;
   dry-run respects the ceiling and never reaches test execution.
   **Full live Stage 4 → Stage 6 cycle completed 2026-08-25 — nothing regressed.** Ran
   the spec's own closing step for real: removed `qa-approved`/`security-approved` from
   issue #6 (kept `design-approved`), opened a real no-op PR (`forge-demo-apps#26`) on
   `feature/REQ-2026-03` — the standard branch-naming convention, not the ad hoc-PR
   fallback already covered by Item #17's verification — with the tracking-issue body
   line, and let `notify-forge.yml` dispatch it for real.
   **First attempt surfaced a real, unrelated infrastructure problem, not a fix
   regression:** both QA and Security failed at the identical last step —
   `anthropic.AuthenticationError: 401 - API key is invalid` — after all of their
   deterministic work had already completed successfully. Confirmed from the raw log
   that all three Pipeline Hardening fixes' actual mechanics ran correctly against
   REQ-2026-03's real code before that unrelated failure: `dotnet test`, `npx vitest run`,
   and (Fix 3's new step) `npm run build` all executed in the right working directories
   with no crash in any of qa_agent.py's own new/changed logic. Confirmed the key itself
   (not a GitHub-secrets-specific issue) was invalid by testing the identical local
   `.env` value against a real Anthropic API call — same 401. Mike supplied a new key
   (handed off via a local file, never pasted in chat, deleted immediately after use) and
   updated both the local `.env` and the `forge-template` GitHub Actions secret himself.
   **Re-dispatched the same PR after the key fix — genuinely passed for real:** QA
   reported 39 backend + 29 frontend tests passing (Attempt 1 of 3), confirmed via the
   raw log that `npm run build` actually ran and took **~33s** in real `ubuntu-latest` CI
   (the authoritative timing figure — supersedes the earlier 417s Windows-Docker-bind-mount
   estimate, which was correctly flagged at the time as likely inflated by cross-filesystem
   I/O overhead, not real CI performance). Security reported a clean scan. Both
   `qa-approved` and `security-approved` were genuinely reapplied by these fresh runs, not
   carried over from before.
   **Deploy fired automatically the moment both labels landed** (`06-deploy.yml`'s
   `issues: labeled` trigger — inherent to the existing automated pipeline design, faster
   than any external check-in could intercept between label-application and
   workflow-trigger) and completed successfully for both units. **Verified independently
   via `az containerapp show`** (not just trusting the Deploy Agent's PR comment) that
   both live Container Apps' image tags exactly match PR #26's real head commit
   (`ba994a8531fbd0b5dd8380bd885241230ed7be0e`) — a genuine, live redeploy, not a
   simulated or dry-run one. Test PR closed and branch deleted immediately after.
6. ~~**`wait_for_all_threads_idle()` can't distinguish "genuinely finished" from "every
   thread hit a fatal session-level error"** (e.g. billing exhaustion mid-run, confirmed
   live on REQ-2026-03). `run_implementation_stage()` also archives unconditionally once
   idle, before confirming real output was produced.~~ — **RESOLVED 2026-08-26**, per
   `docs/FORGE-Item6-Item8-Fix-Spec.md`. Two separately-fixable, separately-committed bugs:
   - **Bug 6a (budget exhaustion invisible to idle detection):** the `/threads` status
     endpoint uses `"idle"` for both a genuinely finished thread and one that only went
     idle because it ran out of budget mid-work — that distinction only exists in the
     per-thread event stream (`stop_reason: budget_reached`), which the polling loop
     deliberately never fetched (too expensive per-interval). Added
     `SessionBudgetExhaustedError` — a plain `RuntimeError` subclass, deliberately **not**
     a `SessionStillRunningError` subclass, since a budget-exhausted thread is never
     coming back on its own (unlike "still running"). `poll_until_idle()` now raises it
     directly off the coordinator's own `status_idle` event.
     `wait_for_all_threads_idle()` makes exactly one `get_subagent_audit_trail()` call —
     only at the point of declaring success, not on every poll iteration — to check every
     thread's event stream before returning.
   - **Bug 6b (archived before validating real output existed):** the audit-fetch/archive
     block in `run_implementation_stage()` was actually already correctly *ordered*
     (fetch before archive) — the real gap was that nothing validated what was fetched.
     The caller's own "did we get a real archive" check ran only *after*
     `run_implementation_stage()` had already unconditionally archived, so by the time a
     missing-output failure was discovered, the session's evidence trail was already gone
     (the corroborating live incident: a $9.12 Stage 3 session with no
     `implementation.tar.gz` produced, archived anyway). `run_implementation_stage()` now
     takes an optional `expected_output_filename` param (default `None` = unchanged
     behavior for any other caller); when given, it's checked via
     `list_session_output_files()` after the existing `try/except` but before
     `archive_session()` — **design fork resolved**: no new exception type was needed,
     since a plain `RuntimeError` raised from that point (outside the `try` block, by
     construction) propagates without ever touching the `try`'s best-effort-archive
     cleanup path, mirroring `recover_implementation_session()`'s existing
     check-before-archive pattern. Also returns `output_files` in the result dict (an
     efficiency addition beyond the original spec) so the caller doesn't need a second,
     redundant API call to locate the archive's file ID.
   - **Verification:** a scoped local mock harness (matching the pattern already used for
     Item #5) — 10 cases total across both bugs, mocking the threads/events endpoints and
     `run_implementation_stage()`'s own dependencies, no real API calls — confirmed: (6a)
     per-thread `budget_reached` raises rather than reporting success; a clean completion
     is unaffected; a still-busy session never pays the extra events-fetch cost; the
     coordinator-level case and the existing `requires_action` branch are both unaffected;
     (6b) real output present → succeeds and archives exactly once, returning
     `output_files`; output missing → raises and does **not** archive; the default
     (no filename given) path is byte-for-byte unchanged; `SessionStillRunningError` is
     unaffected; a genuine mid-run failure still gets best-effort archived as before
     (proves the new check bypasses cleanup only for its own case, not generally).
     **Deliberately deferred, not performed:** the spec's own acceptance criteria also
     calls for a live, real Stage 3 dry-run end-to-end. Skipped this cycle on cost/time
     grounds (historically 35-55+ min, $5-15+ per the pipeline cost log, plus
     session/environment cleanup) — Mike's explicit call, given both changes are small,
     isolated, and already covered by 10 mocked cases including explicit regression
     checks on every untouched path. Live end-to-end verification of this fix is deferred
     to the first real Stage 3-6 cycle of the next enhancement phase, not skipped
     permanently — this is a deliberate deferral, not an oversight, and should not be
     read as a claim that live verification already happened.
   - Commits: `e300ddc` (Bug 6a), `24ceb85` (Bug 6b).
7. **Archive-prefix mismatch, confirmed once on REQ-2026-02, root cause unconfirmed** —
   the Implementation Coordinator's packaging command may be cwd-relative rather than
   pinned to the sandbox root. `_extract_archive_to_file_dict()`'s prefix guard is kept
   strict (rejects, doesn't auto-remap) per Mike's explicit call; worth investigating
   properly only if it recurs.
8. ~~**CI-workflow scope creep** — the Implementation Coordinator/subagents have twice
   (REQ-2026-01, REQ-2026-02) generated unrequested, non-functional
   `.github/workflows/*.yml` files nested under `services/<id>/` (never discoverable by
   GitHub Actions there), cleaned up manually both times. Root cause (why the model keeps
   generating these unprompted) never diagnosed.~~ — **RESOLVED 2026-08-26**, per
   `docs/FORGE-Item6-Item8-Fix-Spec.md`. Root cause confirmed: `design_agent.py`'s
   `tasks.md` prompt section put no restriction on what kind of deliverable a task item
   could describe, so nothing told the model that CI/CD infrastructure — fixed, owned by
   `forge-template`, never regenerated per-request — was out of scope for a
   Backend/Frontend/Test Writer task item. Two historical incidents confirmed real via
   `git log` in `forge-demo-apps`: REQ-2026-01 (`3397617`, cleaned up in `0f5f1c5`) and
   REQ-2026-02 (`47b3fef`, cleaned up in `ba3b3a7`). Fixed as a **prevention + backstop
   pair** — either layer alone leaves a gap:
   - **Layer 1 (prevention, prompt-only):** `_SYSTEM_PROMPT`'s `tasks.md` section now
     states explicitly that task items must describe only files under
     `services/<request-id>/`; CI/CD and other repo-root infrastructure must never be
     proposed. Scoped to `tasks.md`'s task items specifically — `design.md`'s own
     architecture narrative can still mention GitHub Actions as a fixed core-layer
     choice, unaffected.
   - **Layer 2 (backstop, extraction-time guard):** `_extract_archive_to_file_dict()`
     gained a second rejection rule alongside its existing `expected_prefix` guard —
     same strict-rejection-no-auto-remap philosophy: any archive member with a literal
     `.github` path segment is skipped with a warning. Matches on an exact path segment
     (`path.split("/")`), not a substring, so a legitimately named path like
     `.../mygithubutil/foo.cs` is never false-flagged. Never auto-promotes a nested
     `.github/` file to the real repo-root location — that stays a deliberate human
     decision.
   - **Verification:** Layer 2 confirmed via an adversarial local harness building real
     in-memory `tar.gz` fixtures (no mocking — the function is pure bytes-in/dict-out):
     a nested `.github/workflows/fake.yml` member is skipped while sibling legitimate
     files still extract; the required negative case (`github` as a path/filename
     *substring*, e.g. `mygithubutil/`) is correctly **not** caught; a normal archive
     with zero `.github` content is unaffected; the existing `expected_prefix` guard is
     unaffected. Layer 1 confirmed via a **live** single Messages API call (not just
     mocked) against deliberately adversarial synthetic requirements text explicitly
     asking for "a CI/CD pipeline configuration" — the real patched prompt produced a
     `tasks.md` with zero CI/CD-flavored task items, correctly redirecting the ask into
     backend/frontend test infrastructure instead ($0.09, single call).
   - Commits: `78a2f3f` (Layer 1), `5ef29de` (Layer 2).
9. ~~**Admin-merge pattern for ad hoc `fix/*` branches — 4 occurrences (PRs #7, #8, #11,
   #16).**~~ — **RESOLVED 2026-08-27 (per `docs/FORGE-Item9-Item15-AdHocFixDispatch-Spec.md`)
   — no code fix needed, closed on live evidence.** `notify-forge.yml`'s dispatch filter
   (`startsWith(head.ref, 'feature/')`) already correctly forwards `feature/fix-*` for a
   real `security-check` scan — confirmed live via PR #27
   (`feature/fix-appinsights-core-js-dedupe`): `notify` dispatch `SUCCESS`,
   `security-check` ran for real and returned `SUCCESS`. The 4 original admin-merge cases
   all used bare `fix/*`, predating the 2026-08-13 `feature/fix-*` convention (PR #16
   merged the same day the convention was decided) — correctly excluded by design, not a
   bug. PRs #28/#29 (initially suspected as recent evidence the gap persisted) actually
   used `chore/*` branch names, never `feature/fix-*` at all — again correctly skipped,
   for an unrelated reason (convention not used). See the standing convention note above
   for the full write-up. No admin-merge should be needed going forward as long as the
   `feature/fix-*` convention is actually followed.
10. ~~**`enforce_admins` on `forge-demo-apps`' `main` branch protection was `false`,
    contradicting the originally-confirmed `true` from Step 4.8.**~~ — **RESOLVED
    2026-08-27, on Mike's explicit go-ahead.** Flipped `false` → `true` via
    `POST repos/Flamespiker/forge-demo-apps/branches/main/protection/enforce_admins`
    (the dedicated endpoint, not a full protection PATCH, so nothing else could be
    touched by construction). Confirmed via a `GET` on
    `.../branches/main/protection` immediately before and after: `enforce_admins.enabled`
    was the only field that changed — `required_status_checks` (`contexts:
    ["security-check"]`, `strict: false`, `app_id: 4388813`),
    `required_pull_request_reviews` (`required_approving_review_count: 1`,
    `dismiss_stale_reviews: false`, `require_code_owner_reviews: false`), and every other
    flag (`required_signatures`, `allow_force_pushes`, `allow_deletions`,
    `block_creations`, `required_conversation_resolution`, `lock_branch`,
    `allow_fork_syncing`, all `false`) were byte-identical before and after.
11. **21 `next@14.2.35` CVE findings have no 14.x backport** (8 High + 11 Medium + 2 Low)
    — accepted ongoing risk from the deliberate decision to stay on the 14.x line, not a
    bug. **Count refined 2026-08-21** (see Item #19's triage pass): the original count
    only tallied the 8 HIGH-severity findings; the full "no 14.x backport" population is
    21 unique CVEs — the disposition itself (accepted risk) is unchanged, only the count
    was incomplete.
12. **Cost log (`docs/FORGE-pipeline-cost-log.md`) needs REQ-2026-03 figures backfilled**,
    including the Deploy Agent fix cycle.
13. ~~**A `forge-template`-level Dependency-Check suppression file** for confirmed
    dev-only npm findings~~ — **RESOLVED DIFFERENTLY, 2026-08-19.** Rather than build the
    suppression file (which was briefly built, then hit a real XSD gotcha — a
    `<suppress>` block needs a vulnerability-matching child element, not just a
    file/package matcher, confirmed live via `SuppressionParseException` — fixed once,
    then superseded), the whole dependency scanner was swapped from OWASP Dependency-Check
    to GitHub Dependabot alerts (see security_agent.py above). Native per-alert dismissal
    replaces the suppression-file mechanism going forward.
14. ~~**Backend AzureAd config still placeholder — blocks real Azure AD login end-to-end
    for REQ-2026-03.**~~ — **RESOLVED 2026-08-19.** Both frontend and backend wired
    (see "Azure AD wiring + Postgres provisioning" above); a real Postgres Flexible
    Server provisioned; claim/release write-path verified end-to-end via real HTTP +
    direct DB query. `AzureAd__Audience` confirmed as `api://b59886c1-12ac-42c1-895f-5fafa8e57318`
    (the default, non-custom Application ID URI) via the Portal.
15. ~~**Ad hoc PRs need the `Related FORGE tracking issue: <owner>/<repo>#N` body line
    added manually if not opened by a FORGE stage agent.**~~ — **RESOLVED 2026-08-27 via
    Option A (process fix), per Mike's explicit choice** (per
    `docs/FORGE-Item9-Item15-AdHocFixDispatch-Spec.md`'s design fork) **over Option B**
    (making `resolve_tracking_issue()` tolerant of a missing line via a fallback,
    mirroring `resolve_feature_pr()`'s Item #17 pattern) — rejected because an ad hoc PR
    has no natural tracking issue to fall back to if one was never opened, and loosening
    `resolve_tracking_issue()`'s contract would be a real behavior change other stages
    rely on, not a small fix. Resolved instead by documenting the requirement as a
    standing convention (see above) alongside the `feature/fix-*` branch-naming rule —
    no code change to `workflow_glue.py`. `resolve_tracking_issue()` still requires this
    line in the PR body; `design_agent.py`/`implementation_coordinator.py` always write
    it, but a human- or Claude-opened ad hoc fix PR (e.g. PR #21) does not, by default —
    confirmed live: both QA and Security failed outright on `resolve-tracking-issue`
    until the PR body was edited to add the line and the `repository_dispatch` event was
    manually replayed (`gh api repos/.../dispatches`) to get a real (re-)scan. Going
    forward, any ad hoc fix PR must include this line at open time per the standing
    convention above — no live throwaway-PR re-test was run for this closure (see that
    convention note for why).
16. ~~**Cleanup debt from the 2026-08-19 write-path verification session, not urgent:**~~
    — **RESOLVED 2026-08-19.** Test user "Mike App Test"
    (`AzureAdOid=3100bd61-03a4-4ebc-9327-4d2731f172f5`) flipped back to
    `IsCoordinator=false` in the REQ-2026-03 Postgres DB, verified via an independent
    `SELECT` (not just the `UPDATE...RETURNING` clause). Both firewall rules removed
    (`AllowAdminVerificationIp`, and the stale `AllowContainerAppsEnvOutboundIp` which
    never actually worked) — verified via `firewall-rule list`, which now shows only
    `AllowAzureServices`. Postgres server confirmed `Stopped` again after this cleanup.
17. ~~**`workflow_glue.py`'s `resolve_feature_pr()` can't find ad hoc fix PRs for
    Deploy — confirmed live on PR #22 (the `SHIFT_ALREADY_CLAIMED` wording fix).**~~ —
    **RESOLVED AND LIVE-VERIFIED 2026-08-20** (per
    `docs/FORGE-DeployAgent-ResolveFeaturePR-AdHocFix-Spec-v2.md`). `resolve_feature_pr()`
    now tries the original `feature/<request_id>` branch match first (Step 1, unchanged,
    zero behavior change for the common case), and — only if that finds nothing — falls
    back to scanning every open PR in `forge-demo-apps` (new
    `github_helper.list_open_prs()`, paginated via the Link header, `per_page=100`) for
    one whose body references this tracking issue via the same `Related FORGE tracking
    issue: owner/repo#N` line `resolve_tracking_issue()` reads (parsing now shared via a
    single `_parse_tracking_issue_number()` helper both functions call, not two
    independently-maintained regexes). Raises `ValueError` on zero or more than one match
    at whichever step resolves it, same strictness as before — never silently guesses.
    Item #15's separate gap (an ad hoc PR missing the tracking-issue body line entirely)
    is explicitly out of scope here: Step 2 correctly finds nothing in that case and the
    existing manual remediation still applies.
    Verified two ways: (1) unit-level simulation (monkeypatched
    `list_open_prs_by_head()`/`list_open_prs()`/`get_pr()`) covering all six spec
    acceptance criteria — branch-match regression, PR #22's actual shape via the
    fallback, zero-match wording, multi-match on both Step 1 and Step 2, and
    `resolve_tracking_issue()`'s callers confirmed byte-identical; (2) a real live run —
    opened a throwaway ad hoc PR (`forge-demo-apps#23`, README-only diff, tracking-issue
    body line present), removed and re-added `security-approved` on issue #6 to fire a
    fresh `labeled` webhook, and confirmed via `gh run view` that `06-deploy.yml`'s
    "Resolve feature PR number and head commit SHA" step succeeded, resolving PR #23's
    real number and head SHA via the Step 2 fallback (no open PR existed on
    `feature/REQ-2026-03` — PR #20 is long since merged). Test PR closed and branch
    deleted immediately after; issue #6's labels confirmed back to their original state
    (`design-approved`, `qa-approved`, `security-approved`).

18. ~~**New, previously-hidden bug uncovered by Item #17's live verification:
    `deploy_agent.py`'s `_az_login()` runs too late relative to
    `_get_env_default_domain()`.**~~ — **FIXED AND VERIFIED 2026-08-20.** In the old
    code, the cross-service FQDN lookup (`_get_env_default_domain()`, needed whenever a
    request has both a frontend and a "web" backend unit — true for REQ-2026-03) ran
    before `_az_login()` did, so `az containerapp env show` executed before the CLI had
    ever authenticated in that process. Confirmed live: a test run got all the way
    through Docker ACR login, then failed with `RuntimeError: az containerapp env show
    failed ... ERROR: Please run 'az login' to setup account.` — before any `docker
    build`/`push` or Container App create/update, so no live resource was touched. The
    prior automated run (2026-08-20T03:25, pre-Item-#17-fix) never reached this far — it
    died earlier at the old `resolve_feature_pr()` bug — so this ordering bug had
    silently blocked **every** fully-automated deploy for any two-unit (frontend +
    backend-web) request for as long as the pipeline has existed; every past successful
    REQ-2026-03 deploy was a manual local `deploy_agent.py` invocation, where the
    operator's own shell was already authenticated.
    **Fix:** moved `_az_login(azure_credentials)` to immediately after `_docker_login()`,
    ahead of the entire cross-service-wiring block (including the `backend_web_unit`
    name-finalization and `_get_env_default_domain()` call) — same single call, no
    signature change, no change to what it's called with. The old call site
    (immediately before the per-unit build/push/deploy loop) was removed rather than
    left as a redundant second call.
    **Verified directly** (not via a full `deploy_agent.py` dry-run, which per its own
    design does real `docker build`/`push` even in `--dry-run` — unnecessary cost just to
    test call ordering): imported `_az_login()`/`_get_env_default_domain()`/
    `_load_staging_config()` directly and ran them back-to-back in the new order against
    the real `forge-staging` environment — `az login` succeeded, and the same domain
    lookup that failed in CI now returned `yellowmeadow-894377a9.canadacentral.
    azurecontainerapps.io` (matches the known live domain) with zero errors. az CLI
    session confirmed unchanged afterward (same `forge-deploy-staging` SP as before — no
    switch, no cleanup needed).

19. ~~**Dependabot alert triage pass completed 2026-08-21**~~ (per
    `docs/FORGE-Dependabot-Triage-Spec.md`) — **FULLY CLOSED OUT.** Full report:
    `docs/FORGE-Dependabot-Triage-Report-2026-08-21.md`. Originally data-gathering and
    classification only. **The dev-only dismissal list (9 alerts: 44, 49, 50, 51, 76, 77,
    82, 94, 95) was executed 2026-08-21 with Mike's explicit go-ahead** — each dismissal
    independently re-verified afterward via a fresh per-alert `gh api` fetch confirming
    `state: dismissed` (not just trusted from exit codes); open-alert count on
    `forge-demo-apps` dropped 101 → 92 exactly as expected, confirming nothing outside
    the intended 9 was touched. 101 open alerts on `forge-demo-apps` (0 on
    `forge-template`) at the time of the pull, a drift of 1 from the 102 recorded
    2026-08-19. Headline finding:
    REQ-2026-01/02 are pinned to `next@14.2.5` while REQ-2026-03 already runs
    `next@14.2.35` in production — 24 alert rows (12 CVEs, including 1 Critical) can
    close via a same-line patch bump with no major-version risk, previously
    unidentified as an action item. Zero likely-false-positives found (Dependabot's
    native GHSA semver-matching doesn't share the CPE fuzzy-match failure mode that
    motivated dropping Dependency-Check). One open question flagged for Mike: whether
    REQ-2026-01's frontend is serving any live traffic anywhere (no
    `req-2026-01`-prefixed frontend Container App exists in `forge-build-rg` today, but
    its deploy history predates `deploy_agent.py` and wasn't investigated further) —
    affects how urgently its 33 alert rows should be treated.
    **Update 2026-08-22:** the open question above is resolved — `az containerapp list`
    re-confirmed no `req-2026-01`-prefixed frontend Container App exists; its 33 alert
    rows are dormant-code risk, not live-traffic risk (report updated in place, same
    file). **The triage report's headline `next` version-catch-up fix is now a real,
    merged PR:** `forge-demo-apps#24` (merged 2026-08-24) bumps `next` 14.2.5 → 14.2.35 in
    both REQ-2026-01 and REQ-2026-02, closing 24 alert rows (12 CVEs, 1 Critical). Both
    apps' Jest suites and
    `next build` were run twice each (before/after the bump) to isolate any real
    regression: Jest results are byte-identical before and after on both apps (REQ-01:
    38 pass / 6 pre-existing unrelated failures; REQ-02: 38/38 pass); `next build` also
    fails identically before and after on both apps — a pre-existing TypeScript/prerender
    issue, unrelated to this bump, not fixed by this PR (ties into Open Item #3 — no
    pipeline stage has ever validated a real production build for either app). Net: zero
    regression from the version bump itself, confirmed by direct comparison rather than
    assumed. The Dependabot-flagged `postcss`/`Microsoft.Identity.Web` fixes from the
    same report were **not** included in this PR — only the `next` catch-up, since that
    was the specific ask.

20. ~~**One real, one false-alarm `next build` failure**~~ — **RESOLVED 2026-08-26.**
    REQ-2026-01's real bug (below) is fixed, merged, and manually deployed + verified live
    in staging. Originally recorded 2026-08-21/22 (during PR #24's
    before/after test verification) as two pre-existing failures, both run locally on a
    Windows machine. Re-running both inside a `node:20-bullseye` Linux container (matching
    `04-qa.yml`'s actual `ubuntu-latest` CI environment, and how Deploy Agent's real
    `docker build` behaves) revealed the REQ-2026-02 finding was a **Windows-only false
    alarm** — it builds cleanly (`exit 0`, all pages generated) on Linux. REQ-2026-03 was
    also re-checked the same way (never previously suspected, but tested for completeness
    since it showed the identical symptom locally) and is likewise clean on Linux, matching
    its known-good live production deployment. Only REQ-2026-01's failure is genuine —
    confirmed identical on both Windows and Linux, as expected for a TypeScript
    type-checking error (OS-independent).
    - **REQ-2026-01 — RESOLVED 2026-08-26 (fixed, merged, manually deployed, and verified
      live — see the full narrative below). Was still genuinely unfixed as of 2026-08-25
      (re-confirmed at that point by pulling `lib/app-insights.ts` fresh from `main` — line
      70 was byte-identical to when this was first found; nothing had touched this file
      since).** TypeScript compile
      error at line 70 — the `ReactPlugin` passed to `extensions: [_reactPlugin]` isn't
      assignable to `ITelemetryPlugin`. Root cause: two different, incompatible copies of
      `@microsoft/applicationinsights-core-js` get resolved in `node_modules` — one
      top-level, one nested under `@microsoft/applicationinsights-analytics-js`'s own
      dependency tree — whose `ITelemetryPlugin`/`Tags` type shapes don't structurally
      match each other, so TypeScript rejects the assignment even though both packages
      are semver-compatible at the JS level. A classic duplicate-nested-package problem,
      not a real logic bug.
      **Important distinction, since this item's own title says "corrected":** what was
      corrected here was the *diagnosis* (this failure is real; REQ-2026-02's identical
      symptom was a false alarm) — not the underlying app code, which nobody has touched.
      **What changed as a side effect of Fix 3 (Open Item #3, same session):** this bug is
      no longer invisible to the pipeline — QA now correctly detects it and blocks
      `qa-approved`, where before Fix 3 it would have silently passed. The bug itself is
      unchanged and still needs a real fix (dedupe `@microsoft/applicationinsights-core-js`
      in the dependency tree, or a type-cast workaround) — this is a genuine, still-open
      action item, not something to file away as resolved just because Item #20's own
      diagnosis-correction task is done.
      - **Update 2026-08-25 — fixed via `forge-demo-apps#27`. Merged 2026-08-26
        (merge commit `71890f7e239947619cd0d951ee4ebe6b90d7d9a7`, confirmed on `main`
        via `gh pr view`/`git log`).** Root cause confirmed precisely via `npm ls`:
        `applicationinsights-react-js@3.4.3` pins `applicationinsights-common@^2.8.14`,
        which hoists `core-js@2.8.18` to the top level, while `applicationinsights-web`'s
        own tree needs `3.4.3`, resolved as a separate nested copy under
        `applicationinsights-analytics-js` — a genuine 2.x/3.x type-shape mismatch
        (`Tags`, `ITelemetryPlugin.setNextPlugin`), not a cosmetic duplicate. Confirmed
        `applicationinsights-react-js`'s runtime bundle never `require()`s `core-js` at
        all — it receives its `core` instance via duck-typed injection from the real
        `ApplicationInsights` object at runtime — so forcing its resolved version is a
        type-only change with no runtime risk. Fixed with a `package.json` `overrides`
        entry pinning `applicationinsights-react-js`'s own `applicationinsights-common`/
        `core-js` to `3.4.3`; the scoped type-cast fallback was not needed. `npm ls` now
        shows a single deduped `core-js@3.4.3` resolution tree-wide (previously: `2.8.18`
        top-level plus a separate nested `3.4.3`). Verified two ways: `next build` passes
        cleanly inside a `node:20-bullseye` container (matching `04-qa.yml`'s
        `ubuntu-latest` runner); and live via PR #27's real QA run — the raw CI log shows
        `npm run build` completing with no failure reported, meaning Fix 3's
        build-validation step (which would otherwise supersede the whole report) stayed
        silent. At the time this was recorded, PR #27 had not reached `qa-approved` — it
        landed `qa-loop-back` on 6 pre-existing, unrelated frontend Jest failures
        (`UploadPage`/`HistoryPage` accessibility/DOM-query issues, byte-identical to the
        already-known baseline; ADO Bugs #163-168 filed automatically), so Deploy never
        triggered at that point. Those 6 failures are a separate, already-known issue,
        deliberately left untouched here — out of scope for this fix, tracked in ADO only
        per Mike's call, no further CLAUDE.md entry for them. `security-approved` was
        reached cleanly (only the already-accepted no-14.x-backport CVE population from
        Item #11).

        **PR #27 merged 2026-08-26** (merge commit `71890f7e239947619cd0d951ee4ebe6b90d7d9a7`,
        confirmed on `main` via `gh pr view`/`git log` in a later session). How it got from
        `qa-loop-back` to merged (a later passing QA run vs. a manual/admin merge) was not
        investigated — not needed, since the fix itself was independently re-verified live
        below regardless of merge path.

        **Deploy Stage 6 never fired automatically for this merge.** `06-deploy.yml` only
        triggers when the tracking issue (`forge-template#2`) carries both `qa-approved`
        AND `security-approved`; issue #2's labels at merge time were
        `clarification-pending` / `qa-loop-back` / `security-approved` — `qa-approved` was
        never applied (consistent with PR #27's own body, which explicitly said "Do not
        merge — flagging back to Mike once QA/Security pass" and left the real-QA-cycle
        checkbox unchecked). Confirmed via `06-deploy.yml`'s run history: no run exists
        after the merge timestamp.

        **Deliberately bypassed the `qa-approved` gate and deployed manually** — same
        precedent as PR #22 (see "Deploy Agent — Stage 6" above). Justification: the fix
        itself was independently verified (Linux-container `next build` pass matching
        `04-qa.yml`'s real runner, PR #27's own real QA run showing `npm run build`
        succeeding cleanly, `security-approved` reached cleanly) and the only thing
        blocking `qa-approved` was the 6 pre-existing, confirmed-unrelated Jest failures
        above. `06-deploy.yml` has no `workflow_dispatch` trigger (confirmed by reading the
        workflow file before assuming a mechanism existed, per standing practice) — a
        direct `deploy_agent.py` invocation is the only manual path, matching the PR #22
        precedent. Ran it against a checkout pinned to the exact merge commit, with
        `--commit-sha 71890f7e239947619cd0d951ee4ebe6b90d7d9a7 --pr-number 27`.

        **First attempt: 2 of 3 units deployed; the frontend build timed out at the 1800s
        ceiling.** `req-2026-01-document-api` and `req-2026-01-email-worker` (both backend
        .NET units, unaffected by this frontend-only bug) deployed successfully carrying
        the new commit tag — but `req-2026-01-frontend`, the one unit that actually
        contains the fix, failed: `docker build` hit `deploy_agent.py`'s
        `_SHELL_TIMEOUT_SECONDS` (1800s) ceiling before finishing. At that point the fix
        was **not** verified live anywhere — matching commit tags on the two unaffected
        backend units proved nothing about the actual frontend fix.

        **Retry with the timeout raised 1800s → 3600s (one retry only, by design — see new
        Open Item below) succeeded cleanly with zero app changes**, confirming this was a
        Deploy Agent ceiling problem, not a slow/broken app build. `_run_shell`'s default
        timeout was patched at runtime for this one run only (`deploy_agent.py` itself was
        not modified) and the full deploy re-run; all 3 units completed with no errors.
        `req-2026-01-frontend` didn't exist as a Container App before this (consistent with
        Item #19's earlier finding that no `req-2026-01`-prefixed frontend Container App
        existed), so this was a `create`, not an `update`.

        **Verified live via direct `az containerapp show` on all 3 units** (not trusted
        from the deploy script's own reported success) — every unit's
        `properties.template.containers[0].image` matches
        `71890f7e239947619cd0d951ee4ebe6b90d7d9a7` exactly: `req-2026-01-document-api` ✅,
        `req-2026-01-email-worker` ✅, `req-2026-01-frontend` ✅ (`provisioningState:
        Succeeded`).

        **This was a manual override of the automated pipeline, not the automated pipeline
        path itself** — `qa-approved` was never satisfied on issue #2, and Deploy Stage 6
        never fired on its own.
    - **REQ-2026-02 (false alarm, no action needed):** the `TypeError: Cannot read
      properties of null (reading 'useContext')` prerender error on `/404`, `/500`,
      `/_not-found` only reproduces when running `next build` bare on this Windows
      machine — never a real defect in the app itself.
    - **Why this matters for Fix 3** (`docs/FORGE-Pipeline-Hardening-Spec.md`'s new QA
      build-validation step): confirms the new step is safe to land as designed, since
      `04-qa.yml` already runs on `ubuntu-latest` — it will correctly catch REQ-2026-01's
      real failure and correctly NOT flag REQ-2026-02/03 as broken, exactly matching this
      Linux-container evidence rather than the earlier, misleading Windows-local result.
    - PR #24's description (which asserted REQ-2026-02's build failure was pre-existing
      and unrelated to the version bump) has been corrected with a follow-up PR comment —
      the version bump itself is unaffected either way, but the build-failure claim for
      REQ-2026-02 specifically was wrong and needed retracting, not just the bump's safety.
21. ~~**Deploy Agent's `_SHELL_TIMEOUT_SECONDS` (1800s) is too tight for real frontend
    builds**~~ — **RESOLVED 2026-08-26.** Confirmed via `grep`/read that this is the exact
    constant governing `_docker_build()`'s (and every other `_run_shell()` caller's)
    default timeout — the same one that timed out the real REQ-2026-01 frontend deploy
    during Item #20's fix cycle. Bumped `1800 → 3600`, one-line value change, no other
    logic touched. No separate live-deploy re-verification performed for this change —
    Item #20's earlier retry at 3600s (zero app changes, succeeded cleanly) already **is**
    the live proof this value works. Commit: `ac13529`.
22. ~~**Deploy Agent doesn't wire any scale rule (KEDA or otherwise) for non-ingress worker
    units.**~~ — **RESOLVED 2026-08-26.** `_build_containerapp_command()`'s `create` branch
    applied the global `staging_cfg["min_replicas"]` (0) to every unit uniformly,
    regardless of whether anything could ever trigger it back up from zero. Confirmed
    Deploy Agent generates no scale rule anywhere today (no KEDA or otherwise), so
    `unit.unit_type in _TARGET_PORTS` (has external ingress) is currently the complete
    "safe to scale to zero" test — an ingress-backed unit wakes on the next HTTP request
    (Container Apps' default HTTP-concurrency scaler, confirmed live for
    `req-2026-01-document-api`); a `"worker"` unit has neither ingress nor a scale rule
    (confirmed live for `req-2026-01-email-worker`), so `minReplicas: 0` there was a
    broken/stuck config, not a cost optimization. Non-ingress units now default to
    `minReplicas: 1`; web/frontend units are unchanged. Verified via a scoped local check
    calling `_build_containerapp_command()` directly with mock units (no real `az`
    calls): worker → `minReplicas=1`; web/frontend → `minReplicas=0` unchanged; the
    `update` path (never sets `--min-replicas`) is unaffected. **Only affects units Deploy
    Agent generates from here forward** — `req-2026-01-email-worker`'s live config was
    deliberately left untouched, per explicit instruction (existing app, out of scope for
    this fix). Note: the spec's third acceptance case ("a unit with a scale rule →
    `minReplicas: 0` unchanged") isn't testable against the current codebase — `DeployUnit`
    has no scale-rule field at all, since Deploy Agent doesn't generate scale rules today;
    flagged rather than resolved by adding an unused field. Commit: `9d57398`.
23. ~~**No on-demand way to verify a service's language build or Docker build outside the
    full pipeline**~~ — **RESOLVED 2026-08-26.** New `forge-demo-apps` workflow
    `.github/workflows/verify-build.yml`: manual (`workflow_dispatch`-only, not part of
    the automated pipeline), takes `ref`/`service-path`/`mode`
    (`language-build`/`docker-build`) inputs, runs on `ubuntu-latest` (matching
    `04-qa.yml`'s real CI environment), detects backend vs. frontend by the same
    `package.json`-vs-`*.csproj` signal Deploy Agent's own `_detect_units()` uses, and
    writes pass/fail + wall-clock timing to the job summary. Replaces ad hoc local Docker
    Desktop verification (slow/flaky on Windows — see Item #20/#21's session). Zero
    interaction with any existing automated workflow, by construction (manual dispatch
    only). Landed via `forge-demo-apps#28` (admin-merged — ad hoc branch naming means
    `security-check` can't fire either way, same precedent as Item #9's ad hoc fix PRs;
    additive-only file, low risk).
    **Live verification surfaced and fixed a real bug, not just confirmed the happy
    path:** `docker-build` mode originally assumed the Docker build context always equals
    `service-path` — correct for frontend (self-contained) but wrong for backend .NET
    units, confirmed live against `services/REQ-2026-01/backend/DocumentApi` (its
    Dockerfile's `COPY Directory.Build.props`/`COPY DocumentApi/DocumentApi.csproj` only
    resolve against the shared `backend/` parent directory — confirmed against
    `deploy_agent.py`'s own `_detect_backend_units()`, which always sets `build_context` to
    that parent for exactly this reason). Fixed to use `dirname(service-path)` as context
    for a detected backend unit, `service-path` itself for frontend; landed via
    `forge-demo-apps#29` (same admin-merge rationale). Also explicitly spot-checked
    (per Mike's call) whether `language-build` mode's `dotnet build` path had the
    analogous issue — it does not: unlike a Docker `COPY`-restricted context, a native
    `dotnet build` runs against the full checked-out repo, and MSBuild's own
    `Directory.Build.props` upward-directory search finds the parent's file
    automatically; confirmed empirically via a live dispatch against the same backend
    path (28s, clean pass), not assumed from documentation alone.
    **Final live-verified state, both modes, both unit types:** `language-build` against
    `services/REQ-2026-01/frontend` (56s, clean `next build`) and against
    `services/REQ-2026-01/backend/DocumentApi` (28s, clean `dotnet build`);
    `docker-build` against `services/REQ-2026-01/frontend` (correctly fails clean — no
    Dockerfile committed at that path, confirmed via `git ls-tree`, not a tool bug) and
    against `services/REQ-2026-01/backend/DocumentApi` (51s, clean, post-context-fix).

---

**Note on today's (2026-08-26) live-verification posture, applying to Items #6, #8, #21,
#22, and #23 as a whole:** every fix above was verified via a scoped local mock/adversarial
harness (or, for #23, real live `workflow_dispatch` runs — a cheap, additive, non-pipeline
tool, unlike the others). The one live end-to-end **pipeline** run explicitly called for by
a spec (Item #6's real Stage 3 dry-run) was deliberately deferred on cost/time grounds — see
Item #6's own entry above for the full rationale. This is a deliberate, recorded deferral
for that one specific piece, not a claim that every fix in this session's batch went
unverified live — #21 and #23 in particular did get real, live confirmation.

24. ~~**Stage 3 (Implementation) never extended for Enhancement requests**~~ —
    **RESOLVED AND LIVE-VERIFIED 2026-08-28**, per
    `docs/FORGE-Item23-Stage3-Enhancement-Spec.md`. Formerly tracked as **Item #23
    in the Open Items Backlog** (`FORGE-Open-Items-Backlog-v1.md`, the Claude.ai
    side's own tracker); renumbered #24 here to avoid collision with this file's
    own, already-existing Item #23 — **"No on-demand way to verify a service's
    language build or Docker build outside the full pipeline,"** resolved
    2026-08-26 via `forge-demo-apps`' `verify-build.yml` (see that entry above) —
    a completely unrelated fix that happened to land on the same number in a
    different, independently-maintained list. Flagging back to Mike to reconcile
    on the backlog-doc side. Previously
    `implementation_coordinator.py` always resolved `service_root` from the
    **new** `request_id`, so an Enhancement would have built a brand-new
    `services/<request_id>/` folder from scratch instead of editing the real
    existing service — Build Plan step 7.6's literal acceptance bar.
    - **§2.4 (cheap, standalone):** Excel dropdown on `docs/Intake Template.xlsx`'s
      `Overview!C13` ("Existing Service Name"), listing current service folders as
      defense-in-depth alongside Ingestion Agent's existing raise-on-mismatch
      backstop.
    - **§2.1:** new "Determine Enhancement status" step in `03-implementation.yml`
      (mirrors `00-intake.yml`'s own pattern) resolves `--existing-service`;
      `implementation_coordinator.py` resolves `service_root` to the real
      `services/<existing_service>/` when set, raising (Layer 2 precedent from
      Ingestion Agent / Item #8) if that folder doesn't exist in the monorepo.
    - **§2.2 (sandbox population):** confirmed live that Managed Agents sessions
      support pre-session file seeding via `resources[]`, but mounts are
      **read-only** — existing-service files can't be edited in place at
      `service_root`. New `EXISTING_SERVICE_MOUNT_DIR` mirrors the existing
      `SHARED_DOCS_DIR` pattern: files mount read-only there, and the
      coordinator's new step 1 copies what's relevant into the real (empty,
      writable) `service_root` before delegating. New
      `core/agents/utils/existing_service_files.py` selects which files to seed
      and `upload_input_file()` (mirror-image, input-side counterpart to the
      existing `list_session_output_files()`/`download_file_content()`) uploads
      them.
      **Deliberate deviation from the spec, flagged explicitly (not just in the
      module docstring):** the spec called for reusing Ingestion Agent's
      character-budget selection shape; the actual implementation is
      **count-based** instead. Ingestion Agent's ~60k-character budget exists
      because its file contents go into an LLM prompt (real per-character token
      cost); here, files are mounted to disk for the coordinator/subagents to
      read selectively with their own tools — mounting carries no token cost, so
      truncating a real app to an arbitrary character budget would risk handing
      subagents an incomplete, unbuildable copy for no actual savings. The real
      constraint is the Managed Agents API's 999-file-resource-per-session cap
      (confirmed live: App1/App2/App3 have 99/70/89 tracked files — nowhere near
      it), so the common case seeds the full filtered tree; a count-based
      two-pass fallback (manifests + largest remaining files) only activates
      near that ceiling.
    - **§2.3:** `Related service: services/<existing_service>/` line added to
      both the PR body and tracking-issue comment when set; omitted entirely on
      Greenfield.
    - **Bug found and fixed during this work, not part of the original spec:**
      the Layer 2 raise (existing service not found) was originally called
      *before* the existing ADR-0011 try/except block in
      `run_implementation_coordinator()`, so it would have propagated to
      `main()`'s bare except with **no failure comment ever posted** — unlike
      Ingestion Agent's own Layer 2 backstop. Wrapped in its own
      log-comment-reraise block matching the identical contract. Verified via a
      persisted test (not just an inline check) calling the real
      `run_implementation_coordinator()` entry point with a mocked empty tree,
      confirming `post_comment()` fires with the right issue number and message
      before the exception propagates.
    - **Second bug, found live and far more consequential — the mount-path
      rewrite:** a real Stage 3 run against tracking issue #10 (`REQ-2026-04`,
      existing service `REQ-2026-03`) was interrupted mid-flight after checking
      the session's **actual attached resources** via the API (not just the
      message text) and finding all 87 seeded files had resolved to
      `/mnt/session/uploads/existing-service/...`, not the plain
      `/mnt/session/existing-service/...` every prompt referenced. The Managed
      Agents API silently inserts `uploads/` immediately after `/mnt/session/`
      for every `type: "file"` session resource — confirmed, not guessed, via a
      minimal throwaway probe session (one agent, one environment, one `idle`
      session with three file resources requesting three different
      `mount_path` values, no `initial_events` so zero model turns were billed):
      the rule is unconditional insertion **unless** the requested path already
      starts with `/mnt/session/uploads/`, in which case it resolves unchanged.
      Fixed by changing the single `EXISTING_SERVICE_MOUNT_DIR` constant to
      `/mnt/session/uploads/existing-service` — propagates to every prompt and
      the resource-building code automatically, since nothing else hardcodes
      the path. `SHARED_DOCS_DIR` was checked and confirmed **unaffected** by
      the same bug — it's never passed through `resources[]` at all (confirmed
      both from the code and from a real historical session, whose `resources`
      field was `[]`, with direct tool-call evidence of the coordinator's own
      `bash`/`write` calls landing at the literal `/mnt/session/shared-docs/...`
      path with no rewriting).
    - **Process incident during this work (own separate lesson, not a code
      bug):** the first live trigger attempt fired the label-driven workflow
      before the day's commits had been `git push`ed to `origin/main` — GitHub
      Actions runs off the remote, not local commits. The run executed the
      **old, unfixed** code, reproduced the original bug for real (a brand-new
      `services/REQ-2026-04/` implementation), and the automatic
      QA→Security→Deploy chain (no human gate exists between them — see Item
      #26) carried it all the way to a real, live, billable Azure Container App
      (`req-2026-04-on-call-rost-ef23ba`). Caught after the fact, not
      prevented — decommissioned via `az containerapp delete` (independently
      re-verified via a fresh `az containerapp show` returning
      `ResourceNotFound`); the stray PR (`forge-demo-apps#31`) and branch were
      closed/deleted manually. The second live trigger attempt (after pushing)
      was itself interrupted mid-flight for the mount-path bug above — killed
      via the documented manual-kill procedure (interrupt → confirm all 4
      threads idle → confirmed no `implementation.tar.gz` existed yet, so
      nothing was lost → archived session/environment/coordinator/3 subagents,
      all 6 confirmed via real `archived_at` timestamps). **Standing lesson:**
      always `git push` before flipping a label-driven trigger, and verify via
      the GitHub API (not local git) that the remote actually carries the
      expected commit before triggering anything costly.
    - **Live verification (third trigger, real fix in place):** confirmed via
      the session's actual first tool-use events (not the message text) that
      the coordinator ran `ls`/`find` against
      `/mnt/session/uploads/existing-service/`, found real content, said in its
      own words *"the existing service has both backend and frontend,"* copied
      all 87 files into `/services/REQ-2026-03`, and read the real existing
      code (`AuditRepository.cs`, `UsersController.cs`, the existing
      `audit/page.tsx`/`AuditTable.tsx`) before editing. Resulting PR:
      `forge-demo-apps#32` (`feature/REQ-2026-04`, commit
      `2febc2a34771248c3ed3cffc02da2d1ad9de8aa0`) — **19 files changed, all
      under `services/REQ-2026-03/`**, zero files under `services/REQ-2026-04/`:
      surgical modifications to existing files (`AuditRepository.cs`,
      `AuditController.cs`, `UsersController.cs`, `UsersRepository.cs`,
      `AuditTable.tsx` reduced 142 lines as logic was extracted out,
      `audit/page.tsx`) plus new supporting files for the coverage-history
      filter feature (`AuditFilterPanel.tsx`, `AuditPageContent.tsx`,
      `useUsers.ts`, `usersApi.ts`, matching new tests) — not a rebuild. PR
      body and tracking-issue comment both confirmed carrying the "Related
      service: services/REQ-2026-03/" line. Greenfield behavior confirmed
      unaffected both at the code level (`resources=[]` omitted entirely when
      `existing_service` is falsy — no `"resources"` key even sent) and by
      shape-matching against `forge-demo-apps#20` (REQ-2026-03's own historical
      Greenfield PR, which has the identical body shape with no "Related
      service" line).
    - Commits: `ca9ef7c` (§2.4), `bf647a4` (§2.1/§2.2), `4b4420c` (§2.3),
      `bb2b18e` (Layer 2 comment fix), `45325be` (mount-path fix).
    - **Left deliberately as-is, not fixed this session (see Items #25/#26
      below):** this live run surfaced that Stage 4 (QA) and Stage 5 (Security)
      both still assume `services/<request_id>/` and were never made aware of
      the Enhancement-target concept — QA passed with zero real test coverage,
      Security crashed. Issue #10 and `forge-demo-apps#32` are being left
      exactly as they landed (`qa-approved` only, no `security-approved`, no
      deploy) as live evidence of that gap, per Mike's explicit call.

25. ~~**QA and Security both assumed `services/<request_id>/`, never
    `services/<existing_service>/`**~~ — **RESOLVED AND LIVE-VERIFIED
    2026-08-28**, per `docs/FORGE-Item25-QASecurity-EnhancementTarget-Spec.md`.
    Originally confirmed live on `forge-demo-apps#32` (REQ-2026-04, existing
    service REQ-2026-03): neither `qa_agent.py` nor `security_agent.py` had
    been updated for Item #24's Enhancement-target concept — both scanned
    `services/REQ-2026-04/{backend,frontend}`, which doesn't exist in this
    checkout (the PR's real 19 changed files are under `services/REQ-2026-03/`).
    QA silently false-positive-passed (`not_applicable` on both suites,
    `qa-approved`, zero real tests run); Security crashed with an unhandled
    `FileNotFoundError` inside `_run_semgrep()`.

    **§1 investigation correction to the original framing (worth keeping,
    not just historical):** Security's crash was already caught by the
    existing ADR-0011 `except` block — a real comment was posted
    ("FORGE Security Agent failed to complete...") and `security-approved`
    was correctly withheld before any fix landed. The gap was a raw Python
    exception string standing in for a message naming the real problem, not
    a silent, uncaught failure as first assumed.

    **Fix (§2, sequenced and committed separately per the spec):**
    - **§2.1 (foundational):** new `core/agents/utils/enhancement_target.py`
      — `resolve_service_root(request_id, existing_service)`, a third
      independent copy of Item #24's resolution rule factored into one
      shared helper (Ingestion Agent and Stage 3 already each had their
      own). `04-qa.yml`/`05-security.yml` gained a "Determine Enhancement
      status" step mirroring `03-implementation.yml`'s Item #24 step
      exactly; `qa_agent.py`/`security_agent.py` gained a matching
      `--existing-service` flag. Per §3.1 (Mike's confirmed default): the
      spreadsheet is re-downloaded, not parsed from the posted "Related
      service" comment line — consistent with the project's existing
      "authoritative lookup over weak-signal parsing" precedent. Commit
      `ea9c85a`.
    - **§2.2 (QA fail-loud):** a directory-existence check on the resolved
      target now runs *before* any backend/frontend test-dir resolution —
      both `_resolve_backend_test_dir()`'s glob and
      `_frontend_test_script_exists()`'s `.exists()` check previously
      silently returned "no test project" for a missing directory,
      identically to a directory that exists but is genuinely test-less. A
      missing directory now raises `EnhancementTargetNotFoundError`
      (log-comment-reraise, same shape as Stage 3's own Layer 2 fix) and —
      per §3.3 (Mike's confirmed default) — does not count against
      `_MAX_RETRIES`, since the request never ran against real code. A
      directory that exists but is genuinely test-less is unchanged
      (`not_applicable` remains legitimate). Commit `18e51e5`.
    - **Dependabot filter fix (found during §1.2's investigation, fixed
      alongside):** `_run_dependabot_check()` built its own manifest-path
      prefix from raw `request_id`, independently of `service_dir` —
      unreachable in the live crash (Semgrep's exception aborted the run
      first) but would have silently returned zero findings against the
      wrong path the moment a working Enhancement run reached it. Renamed
      the param to `service_root` and threaded the same resolved target
      through. Commit `2b1f2a6`.
    - **§2.3 (Security fail-loud):** the same directory-existence check,
      before the three-scanner loop. A missing directory now posts a
      comment naming the real problem (not a stack trace), creates the
      `security-check` run directly with `conclusion=failure` and a
      distinct title ("blocked — target directory not found", a fourth
      branch alongside blocked/incomplete/passed), and applies no label —
      without raising, same non-raising shape as the existing
      `any_tool_failed` path. Commit `9a88421`.
    - **§2.4 (Greenfield unaffected):** confirmed via the scoped regression
      cases inside §2.2/§2.3's own test harnesses (directory-exists,
      `existing_service` unset) plus the original live §1.6 baseline
      (PR #27/REQ-2026-01) — no new live re-dispatch against a Greenfield
      PR was run, per Mike's explicit call (real side effects: duplicate
      ADO Bugs for known pre-existing failures, possible redeploy).

    **§5 live verification against `forge-demo-apps#32`/`forge-template#10`
    — full narrative, including two real problems this run itself
    surfaced:**
    - **Diff review before go-ahead:** the real 19-file diff was read in
      full before triggering anything — a clean, well-scoped coverage-history
      filter feature (no write endpoints added, auth enforced consistently,
      no secrets; the one notable change, audit timestamps displayed in UTC
      instead of `America/Edmonton`, is a disclosed product choice, not a
      bug). `forge-req2026-03-pg` confirmed `Ready` (started) beforehand.
    - **Same stale-code incident as Item #24, reproduced exactly:** the
      first re-dispatch ran against un-pushed local commits (GitHub Actions
      runs off the remote) — reproduced the original crash/false-pass one
      more time, posting a duplicate Security failure comment and
      re-applying the stale `qa-approved`. Caught, commits pushed, verified
      via the GitHub API (not local git) that `main` actually carried the
      fix before re-triggering.
    - **Real fix confirmed working, live:** re-dispatched against the
      pushed fix — Security correctly resolved `services/REQ-2026-03/`, ran
      real Semgrep + Gitleaks (`cwd=.../services/REQ-2026-03` in the log),
      found 22 findings (0 Critical), applied `security-approved` for a
      genuine reason. QA correctly resolved the same target and ran a real
      `dotnet test` (42 backend tests passed) — the Enhancement-target
      resolution and §2.2 fix both worked exactly as designed.
    - **A real bug the fix itself hadn't covered:** QA's frontend suite
      failed with `next: not found`. Root cause: `04-qa.yml`'s *separate*
      "Install frontend dependencies" step independently rebuilds the
      frontend path from raw `request_id`, untouched by §2.1's fix —  it
      looked for `services/REQ-2026-04/frontend/package.json` (absent),
      silently skipped `npm install`, so `node_modules` was missing when
      `qa_agent.py` correctly tried to build the real
      `services/REQ-2026-03/frontend`. Fixed to use the same
      `existing_service` value. Commit `b08ad31`. This filed a real,
      now-misleading ADO Bug (`#178`) — closed with a comment documenting
      the real cause once the fix was confirmed (Mike's explicit
      instruction; see the process note below).
    - **Deploy fired automatically** the first time the stale `qa-approved`
      briefly coincided with a freshly-real `security-approved` — confirmed
      via the job log that `deploy_agent.py` raised
      `ValueError: No deployable units detected under services/REQ-2026-04/
      ... nothing to deploy` immediately, before any `docker build`/`az`
      call — **no real Azure resource was touched**. This is the first live
      confirmation (not just inferred) that `deploy_agent.py`/
      `06-deploy.yml` have zero Enhancement-target awareness at all — out
      of scope for this spec per Mike's explicit instruction not to touch
      Deploy Agent, but now a confirmed gap rather than a theoretical one
      (ties into Item #26).
    - **A second, unrelated latent bug this exposed — logged as Item #27
      below and fixed separately:** the stale `qa-approved` left over from
      the un-pushed re-run caused `04-qa.yml`'s "clear a stale label on
      pass" step to delete a freshly-applied, genuinely-earned
      `qa-loop-back` label, leaving issue #10 showing an incorrect all-clear
      state. Manually corrected (`qa-loop-back` + `security-approved`) via
      direct API calls before the underlying logic itself was fixed and
      committed separately (Item #27, commit `5d07169`).
    - **Final live re-dispatch, with both fixes in place, genuinely passed
      end to end:** `npm install --prefix services/REQ-2026-03/frontend`
      ran for real (695 packages), `npm run build` succeeded, QA applied
      `qa-approved` (attempt 4, 0 bugs) for a real reason; Security
      re-confirmed its genuine pass; Deploy fired again and failed cleanly
      the same safe way (Item #26, still unfixed, still not silently
      dangerous). `forge-template#10` now genuinely carries `qa-approved` +
      `security-approved` — an accurate reflection of reality, not a stale
      artifact. `forge-demo-apps#32` was never merged, closed, or otherwise
      touched throughout.
    - **Process note on the ADO Bug #178 closure:** Mike's instruction was
      "Close ADO Bug #178 with a note pointing to the real cause" — executed
      as a literal, explicit instruction, not an independently-weighed
      judgment call. Flagged in retrospect as an instruction that had a
      plausible second reading (annotate while leaving open) worth
      confirming before acting on a real external system's state, even when
      one reading seems more likely.
    - Commits, in order: `ea9c85a`, `18e51e5`, `2b1f2a6`, `9a88421`,
      `b08ad31`, `5d07169`.

26. **No human gate exists between a feature PR opening and Deploy firing —
    confirmed live 2026-08-28 by re-reading every trigger in the chain, not
    from memory.** `forge-demo-apps`' `notify-forge.yml` dispatches on
    `pull_request: [opened, synchronize]` automatically; `04-qa.yml`/
    `05-security.yml` trigger on that `repository_dispatch` automatically;
    `06-deploy.yml` fires the instant a `qa-approved`/`security-approved` label
    lands (its own job-level `if:` is an `||` on either label event, gated
    internally by a guard-clause step confirming both are actually present
    before doing real work). Nothing in this chain requires a human click —
    this is Document 6's designed behavior (the human gate is PR
    review/merge, which happens *after* Deploy already ran against staging,
    not before). Distinct from Item #25 above: even if QA/Security correctly
    reflected the real diff, a build that happens to pass both would still
    deploy before any human looked at the PR. Confirmed as a real, non-
    theoretical risk by this session's own stale-code incident (Item #24) —
    the first, unfixed run reached exactly this point and deployed a wrong
    Container App before anyone reviewed the diff. Not fixed or scoped this
    session — flagged for a future decision on whether Document 6's design
    should change (e.g. an explicit deploy-stage label a human applies,
    mirroring the other gates) or stays as-is (staging-only, low-stakes by
    design, real review still happens before `main` merge).

27. ~~**`04-qa.yml`'s "Clear a stale qa-loop-back/qc-retry-limit-reached label
    on pass" step decided "did we just pass" by re-querying current label
    state, not this run's own outcome.**~~ — **RESOLVED 2026-08-28**, found
    live during Item #25's §5 verification against `forge-demo-apps#32`. A
    stale `qa-approved` left over from an earlier run against un-pushed
    (pre-fix) code was still present when the real, fixed-code run genuinely
    failed and applied a fresh `qa-loop-back` — the cleanup step's
    `"qa-approved" in labels` check couldn't distinguish "this run just
    passed" from "qa-approved is merely still sitting there," assumed a fresh
    pass, and deleted the just-applied `qa-loop-back`, leaving
    `forge-template#10` showing an incorrect all-clear label state (manually
    corrected back to `qa-loop-back` + `security-approved` before this fix
    landed). Fixed by having `qa_agent.py`'s `main()` write this run's real
    `label_applied` outcome to `$GITHUB_OUTPUT` (empty for the
    retry-ceiling-skip path); the cleanup step now gates on
    `steps.run_agent.outputs.label_applied == 'qa-approved'` instead of
    re-deriving it from current label state. Verified via a scoped local test
    (real `qa_agent.main()`, mocked `run_qa_agent()`): `qa-approved` /
    `qa-loop-back` / skipped (empty) all write the correct output, and only
    the `qa-approved` case satisfies the workflow's gate. Commit: `5d07169`.

28. ~~**Deploy Agent (Stage 6) had zero Enhancement-target awareness.**~~ —
    **RESOLVED AND LIVE-VERIFIED 2026-08-29**, per
    `docs/FORGE-Item28-DeployAgent-EnhancementTarget-Spec.md`. Confirmed live
    2026-08-28 during Item #25's verification pass: a real dispatch against
    `forge-template#10`/`forge-demo-apps#32` (REQ-2026-04, existing service
    REQ-2026-03) reached `deploy_agent.py`, which raised `ValueError: No
    deployable units detected under services/REQ-2026-04/ ... nothing to
    deploy` — a third independent copy of the directory-resolution bug Items
    #24/#25 already fixed, this time in the one stage that also owns a live,
    named Azure resource.

    Root cause confirmed via a dedicated diagnosis pass (spec §1):
    `_detect_units()` built `services/<request_id>/` unconditionally, with no
    `existing_service` concept at all. But directory resolution alone wasn't
    the whole story — Deploy's unit **naming** (`_finalize_unit_name()`) was
    separately keyed on the same `request_id`, so fixing only the directory
    bug (the same way #24/#25 were fixed) would have built a container from
    REQ-2026-03's real code and deployed it under a brand-new, never-touched
    `req-2026-04-*` Container App set — new surface area #24/#25 never had to
    face, since none of those three stages own a persistent, named external
    resource.

    **§1.5's investigation finding, gating the whole fix:** confirmed live via
    `az containerapp list` (`req-2026-03-on-call-rost-5bb949`,
    `req-2026-03-frontend`) plus a direct call to the real
    `_finalize_unit_name('req-2026-03', slug)`, that recomputing the naming
    scheme with `existing_service` substituted for `request_id` reproduces
    both live names byte-for-byte — no one-time manual reconciliation was
    needed before the fix could work as designed.

    **Fix, two separately-committed pieces per the spec's §6 sequencing:**
    - **§2.1 (directory resolution, commit `3a2d5c5`):** third call site of
      the shared `resolve_service_root()` helper (built for Item #25) — a new
      `--existing-service` flag on `deploy_agent.py`, threaded from a new
      "Determine Enhancement status" step in `06-deploy.yml` mirroring
      `03-implementation.yml`'s/`04-qa.yml`'s/`05-security.yml`'s own
      identical steps.
    - **§2.2 (unit naming / resource identity, commit `885b318`):**
      introduces `naming_id` (`existing_service` when set, else
      `request_id`) as a value distinct from the directory-resolution
      target, threaded through `_detect_backend_units()`/
      `_detect_frontend_unit()` and both `_finalize_unit_name()` call sites
      — so an Enhancement deploy updates the existing live
      `req-<existing_service>-*` Container Apps in place, per Mike's
      explicit choice on the spec's §3.2 design fork (over the alternative
      of a new, parallel `req-<request_id>-*` slot requiring an
      undocumented manual cutover step). Cross-service FQDN prediction
      (§2.3) needed no separate code change, confirmed by reading the call
      site — it already only reads `unit.name`, correct by construction
      once naming lands. Greenfield behavior (§2.5) is unaffected by
      construction — `naming_id`/`resolved_service_dir` both fall back to
      `request_id` exactly as before whenever `existing_service` is unset.

    **§3.1's resolution-mechanism fork** (spreadsheet re-download vs. parsing
    the posted "Related service" PR body line) was decided the same way as
    Item #25's identical fork — spreadsheet re-download, for consistency and
    to avoid the ad hoc-PR gap the PR-body path would inherit (spec §2.4,
    flagged not fixed, since it's not live risk under the chosen default).

    **Live verification (spec §5), re-using `forge-template#10`/
    `forge-demo-apps#32` as the vehicle**, gated on Mike's explicit go-ahead
    per the real live-Azure-resource stakes: re-triggered via a label
    removal/re-add on issue #10 (run `33263474117`, `success`). Confirmed
    from the raw log: `Enhancement request -- existing service:
    'REQ-2026-03'`; `Detected 2 unit(s) for REQ-2026-04
    (naming_id=REQ-2026-03): ...`; both Docker builds tagged with PR #32's
    real head SHA (`2febc2a34771248c3ed3cffc02da2d1ad9de8aa0`) against
    `services/REQ-2026-03/...` paths. Independently verified (not trusted
    from the log) via `az containerapp show`/`list`:
    - Names match exactly: `req-2026-03-on-call-rost-5bb949`,
      `req-2026-03-frontend` — zero new `req-2026-04-*` resources
      (`az containerapp list --query "[?starts_with(name,'req-2026-04')]"` →
      `[]`), confirming "update in place" worked as designed, not a parallel
      slot.
    - Both images' tags changed live from the prior `ba994a8531...` (PR
      #26's commit) to `2febc2a3477...` (PR #32's real head SHA) — a genuine
      redeploy, not a stale or simulated one.
    - Cross-service FQDN wiring resolved correctly:
      `FRONTEND_ORIGIN`/`NEXT_PUBLIC_API_BASE_URL`/`NEXTAUTH_URL` all
      pointed at the real, already-live counterpart app's FQDN.
    - Greenfield isolation confirmed live: REQ-2026-01's three units were
      all still on their known-good `71890f7e2399...` commit (Item #20's
      closure commit) after this run — completely untouched, no
      cross-contamination.

    **One item from live verification not completed, flagged rather than
    glossed over:** visual, signed-in browser confirmation that the live
    frontend actually renders REQ-2026-04's coverage-history filter feature
    was not done — no browser-automation/credential tool was available in
    this session's environment to authenticate through the app's real Azure
    AD sign-in. A `WebFetch` check confirmed the app is live and correctly
    serving the sign-in shell (not erroring) on the new image, but that's
    reachability, not a feature-rendering confirmation. The image-SHA match
    to PR #32's exact commit is strong technical evidence the right code is
    running, but this specific visual check is **pending a manual sign-in
    confirmation from Mike**, not an unresolved code issue.

    Commits: `3a2d5c5` (§2.1), `885b318` (§2.2).

29. **`README.md` describes a materially different (partly aspirational,
    never-built) pipeline than what's actually implemented — found
    2026-08-29 during a routine README/memory review, not fixed this
    session (Mike's explicit call — README rewrite deferred).** Checked the
    repo-facing setup doc, last touched 2026-08-19, against current reality:
    - **Approval mechanism described doesn't exist.** README instructs
      commenting `/approve-requirements`, `/approve-qa`,
      `/reject-<stage> <reason>` on the tracking issue. Confirmed via `grep`
      across every `.github/workflows/*.yml` file: there is no slash-command
      handling anywhere in the codebase. The real pipeline is 100%
      label-driven (`clarification-complete`, `requirements-approved`,
      `design-approved`, `qa-approved`, `security-approved` applied as
      GitHub labels, each workflow triggering on `issues: types: [labeled]`
      with a guard clause re-checking the label at run time). A team
      following the README literally would comment a slash command and
      nothing would happen.
    - **Production deploy is claimed but was never built.** README's
      pipeline diagram says "Deploy ✅ One-click production approval" and
      its gate table lists approving a `production` GitHub Environment —
      contradicts this same file's own `deploy_agent.py` module docstring
      ("EXPLICITLY OUT OF SCOPE... Production path... not built, not
      stubbed") and Document 3/FORGE-context's repeated confirmation that
      FORGE has never deployed anything to production, staging only.
    - **Intake template path is wrong.** README points to
      `templates/forge-intake-template.xlsx` — confirmed via `ls` that the
      `templates/` directory doesn't exist at all. The real file is
      `docs/Intake Template.xlsx`.
    - **`tracking/` directory's stated purpose is inaccurate.** README's
      repository-layout section describes it as holding "per-request
      tracking issue metadata." The directory exists but contains only a
      `.gitkeep` placeholder — all real tracking metadata lives in GitHub
      Issues (comments, labels), never as local files in this directory.
    - **Everything else checked out:** `verify-setup.yml` exists as
      described; all seven numbered reference docs (`docs/00...` through
      `docs/07...`) exist and match the README's table; `team/` directory
      structure (`config.yaml`, `stack-preferences.yaml`, `personas/`)
      matches, modulo two extra files not mentioned
      (`gitleaks-allowlist.toml`, `dependency-check-suppressions.xml` — the
      latter itself stale per Item #13's resolution, unrelated to this
      item).
    - **Not fixed this session per Mike's explicit instruction** — a proper
      fix means rewriting the pipeline diagram, the full "Approving a gate"
      table, and every production-deploy reference, not a targeted patch.
      Flagged here so the drift is documented and doesn't need
      rediscovering from scratch next time it's picked up.

## Further reading

- The newest `docs/FORGE-context_v*.md` — Claude.ai-maintained narrative/open-items doc;
  read this alongside this file each session.
- `docs/CLAUDE-archive-2026-08-phase3-5.md` — Phase 3/4 build-out + Phase 5 pre-flight
  fixes, verbatim.
- `docs/CLAUDE-archive-2026-08-req2026-02.md` — REQ-2026-02 fix cycle, verbatim.
- `docs/CLAUDE-archive-2026-08-req2026-03.md` — REQ-2026-03 build + PR #20/Deploy cycle,
  verbatim.
- `docs/FORGE-pipeline-cost-log.md` — token/Managed Agents/ACR cost tracking.
