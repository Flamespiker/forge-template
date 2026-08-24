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

**Standing convention — ad hoc fix-PR branch naming (decided 2026-08-13):** use
`feature/fix-<short-description>`, not `fix/*` — `fix/*` branches never get dispatched
to QA/Security by `forge-demo-apps`' `notify-forge.yml` (only `feature/*`/`design/*`
are), so they hit the permanently-unsatisfiable `security-check` gate and need an admin
merge every time. This has already happened 4 times (PRs #7, #8, #11, #16) — see Open
Items.

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
3. **No pipeline stage validates that the app actually builds before Stage 6 (Deploy).**
   QA only runs `vitest`/`jest`/`dotnet test`; the first real `next build`/`docker build`
   happens inside `deploy_agent.py`. Already let two real issues go undetected until
   Deploy or a manual investigation (a `lucide-react`/`aria-hidden` type mismatch on
   REQ-2026-01; a `vitest.config.ts` nested-`vite`-types conflict on REQ-2026-03).
4. **`qa_agent.py`'s Jest/Vitest JSON parsing has a file-collection blind spot** — a
   suite where every test file fails to *collect* (not just fails) reports `0 passed / 0
   failed / 0 total`, currently treated as a clean pass. Already let one real broken
   REQ-2026-03 frontend suite slip through as `qa-approved` before it was caught by
   chance.
5. **QA's `_MAX_RETRIES = 3` only picks which label to apply — it never blocks or gates a
   re-run.** A passing run always gets `qa-approved` regardless of attempt number;
   `04-qa.yml` has no attempt-count guard clause. The retry counter also doesn't
   distinguish real app-test failures from FORGE-tooling/infra noise, so a redundant
   manual rerun burns a real attempt.
6. **`wait_for_all_threads_idle()` can't distinguish "genuinely finished" from "every
   thread hit a fatal session-level error"** (e.g. billing exhaustion mid-run, confirmed
   live on REQ-2026-03). `run_implementation_stage()` also archives unconditionally once
   idle, before confirming real output was produced.
7. **Archive-prefix mismatch, confirmed once on REQ-2026-02, root cause unconfirmed** —
   the Implementation Coordinator's packaging command may be cwd-relative rather than
   pinned to the sandbox root. `_extract_archive_to_file_dict()`'s prefix guard is kept
   strict (rejects, doesn't auto-remap) per Mike's explicit call; worth investigating
   properly only if it recurs.
8. **CI-workflow scope creep** — the Implementation Coordinator/subagents have twice
   (REQ-2026-01, REQ-2026-02) generated unrequested, non-functional
   `.github/workflows/*.yml` files nested under `services/<id>/` (never discoverable by
   GitHub Actions there), cleaned up manually both times. Root cause (why the model keeps
   generating these unprompted) never diagnosed.
9. **Admin-merge pattern for ad hoc `fix/*` branches — 4 occurrences (PRs #7, #8, #11,
   #16).** Each hit the permanently-unsatisfiable `security-check` (only `feature/*`/
   `design/*` branches get dispatched a real or no-op check) plus no review, resolved via
   `gh pr merge --admin`. Not decided: extend the no-op-check pattern to a `fix/*`-style
   prefix, adopt a naming convention already covered by an existing dispatch filter (see
   the branch-naming convention above), or accept admin-merge as standing procedure.
10. **`enforce_admins` on `forge-demo-apps`' `main` branch protection is currently
    `false`**, contradicting the originally-confirmed `true` from Step 4.8. Nothing any
    known session action changed it. Mike's call whether to flip it back now that the
    design-PR no-op-check fix removed the original reason an admin bypass was needed.
11. **8 HIGH-severity `next@14.2.35` CVE findings have no 14.x backport** — accepted
    ongoing risk from the deliberate decision to stay on the 14.x line, not a bug.
    **Count refined 2026-08-21** (see Item #19's triage pass): the full "no 14.x
    backport" population is actually 21 unique CVEs (8 High + 11 Medium + 2 Low), not
    just the 8 HIGH ones — the disposition itself (accepted risk) is unchanged, only the
    count was incomplete.
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
15. **Ad hoc PRs need the `Related FORGE tracking issue: <owner>/<repo>#N` body line
    added manually if not opened by a FORGE stage agent.** `workflow_glue.py`'s
    `resolve_tracking_issue()` (used by `04-qa.yml`/`05-security.yml`) requires this
    line in the PR body; `design_agent.py`/`implementation_coordinator.py` always write
    it, but a human- or Claude-opened ad hoc fix PR (e.g. PR #21) does not, by default —
    confirmed live: both QA and Security failed outright on `resolve-tracking-issue`
    until the PR body was edited to add the line and the `repository_dispatch` event was
    manually replayed (`gh api repos/.../dispatches`) to get a real (re-)scan. Distinct
    from the `feature/*` vs. `fix/*` branch-naming issue (#9) — this one bites even on a
    correctly-named `feature/fix-*` branch.
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

19. **Dependabot alert triage pass completed 2026-08-21** (per
    `docs/FORGE-Dependabot-Triage-Spec.md`). Full report:
    `docs/FORGE-Dependabot-Triage-Report-2026-08-21.md`. Data-gathering and
    classification only — no packages upgraded, no alerts dismissed (report includes a
    ready-to-run `gh api` dismissal list for the dev-only bucket, not yet executed,
    awaiting Mike's go-ahead). 101 open alerts on `forge-demo-apps` (0 on
    `forge-template`), a drift of 1 from the 102 recorded 2026-08-19. Headline finding:
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
    file). **The triage report's headline `next` version-catch-up fix is now a real PR:**
    `forge-demo-apps#24` bumps `next` 14.2.5 → 14.2.35 in both REQ-2026-01 and
    REQ-2026-02, closing 24 alert rows (12 CVEs, 1 Critical). Both apps' Jest suites and
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

20. **Two pre-existing `next build` failures, found 2026-08-21/22 during PR #24's
    before/after test verification — not fixed, tracked here for future remediation.**
    Both confirmed identical whether run against the original `next@14.2.5` pin or the
    bumped `next@14.2.35` (PR #24), so neither is caused by that version bump — genuinely
    pre-existing breakage that had simply never been caught before, since no pipeline
    stage has ever run a real `next build`/`dotnet build` (Open Item #3).
    - **REQ-2026-01:** TypeScript compile error in `lib/app-insights.ts:70` — the
      `ReactPlugin` passed to `extensions: [_reactPlugin]` isn't assignable to
      `ITelemetryPlugin`. Root cause: two different, incompatible copies of
      `@microsoft/applicationinsights-core-js` get resolved in `node_modules` — one
      top-level, one nested under `@microsoft/applicationinsights-analytics-js`'s own
      dependency tree — whose `ITelemetryPlugin`/`Tags` type shapes don't structurally
      match each other, so TypeScript rejects the assignment even though both packages
      are semver-compatible at the JS level. A classic duplicate-nested-package problem,
      not a real logic bug.
    - **REQ-2026-02:** a React prerender error (`TypeError: Cannot read properties of
      null (reading 'useContext')`) during `next build`'s static-page generation step,
      failing on `/404`, `/500`, `/_not-found`, and `/`.
    - Both used directly as real Fix-3 test material for
      `docs/FORGE-Pipeline-Hardening-Spec.md`'s new QA build-validation step, rather than
      constructed fixtures.

---

## Further reading

- The newest `docs/FORGE-context_v*.md` — Claude.ai-maintained narrative/open-items doc;
  read this alongside this file each session.
- `docs/CLAUDE-archive-2026-08-phase3-5.md` — Phase 3/4 build-out + Phase 5 pre-flight
  fixes, verbatim.
- `docs/CLAUDE-archive-2026-08-req2026-02.md` — REQ-2026-02 fix cycle, verbatim.
- `docs/CLAUDE-archive-2026-08-req2026-03.md` — REQ-2026-03 build + PR #20/Deploy cycle,
  verbatim.
- `docs/FORGE-pipeline-cost-log.md` — token/Managed Agents/ACR cost tracking.
