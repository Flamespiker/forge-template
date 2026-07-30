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
- **Full project context:** `docs/FORGE-context_v20.md` — read this for architecture decisions,
  agent roster, pipeline stages, and session history

---

## Current Build Phase

**Phase 3 — Agent Implementation** (in progress)

Step 3.1 (shared agent utilities) is complete. Step 3.2 (Intake Agent) is complete.
Step 3.3 (Requirements Agent) is complete. Step 3.4 (Design Agent) is complete.
Step 3.5 (Implementation Coordinator) is complete.

Files created:

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
core/agents/subagents/
    __init__.py
    backend_agent.py
    frontend_agent.py
    test_writer_agent.py
core/decisions/
    0011-base-anthropic-client.md
requirements.txt
.env.example
```

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

### github_helper.py — two auth contexts, two repo targets

| Function | Auth | Target repo |
|---|---|---|
| `post_comment`, `add_label`, `remove_label` | `GITHUB_TOKEN` | `forge-template` (tracking issue lives here) |
| `create_branch`, `commit_files`, `open_pr` | App installation token | `forge-demo-apps` (cross-repo work) |

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

**Live run verified 2026-07-29:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- 1,045 input tokens / 472 output tokens / `total_cost_usd: $0.010215` / 13.3 s
- 6 questions posted; `clarification-pending` label applied

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

**Output artifacts (committed to `forge-demo-apps` on `main`):**
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

**Live run verified 2026-07-29:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- 2,281 input tokens / 3,876 output tokens / `total_cost_usd: $0.064983` / 62.5 s
- `requirements.md` + `ado-work-items.json` committed to `forge-demo-apps` on `main`
- Summary comment posted to issue #2; no label applied (label is human action)

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

- Document 4 (Governance) already lists ADR-0010 as the 10th seed ADR — done.
- ADR-0011 committed at `core/decisions/0011-base-anthropic-client.md` — done.
- Step 3.2 Intake Agent (`core/agents/intake_agent.py`) — done; live run verified on issue #2.
- Step 3.3 Requirements Agent (`core/agents/requirements_agent.py`) — done; live run verified on issue #2.
- Step 3.4 Design Agent (`core/agents/design_agent.py`) — done; live run verified on issue #2 (PR #4 opened on forge-demo-apps).
- Step 3.5 Implementation Coordinator (`core/agents/implementation_coordinator.py`) — done; dry run verified on issue #2 (96 files, 156 KB archive).
- Phase 3 next step: **3.6 QA Agent** (Stage 4)

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

**Live run verified 2026-07-30:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- 2,929 input tokens / 12,738 output tokens / `total_cost_usd: $0.199857` / 222 s
- `design.md` + `openapi.yaml` + `tasks.md` committed to `forge-demo-apps` on `design/REQ-2026-01`
- Draft PR #4 opened; summary comment posted to issue #2

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

**Dry run verified 2026-07-30:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- session `sesn_0158Mvs91wfr9rNHPfa9W1oH` — 4 threads (coordinator + 3 specialists), `idle (end_turn)`
- Archive: 156,728 bytes → 96 files extracted under `services/REQ-2026-01/`
  (full .NET solution with DocumentApi + EmailWorker, Next.js frontend, xUnit + Jest tests)
