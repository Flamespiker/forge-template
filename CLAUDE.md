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

Step 3.1 (shared agent utilities) is complete. Files created:

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
pip install claude-agent-sdk==0.2.128
```

### Version pin rationale

`claude-agent-sdk` is pinned to an **exact version** (`==0.2.128`), not a floor.
The SDK is Alpha-classified and has already had one breaking rename (`ClaudeCodeOptions` →
`ClaudeAgentOptions`). Update the pin deliberately after testing each new version.

---

## Key Decisions Made This Session

### claude-agent-sdk vs anthropic package

- All non-Stage-3 agents use **`claude-agent-sdk`** (`from claude_agent_sdk import query, ClaudeAgentOptions`)
- `query()` is the async one-shot call that drives the full Claude Code agent loop
- The base `anthropic` pip package is NOT imported directly anywhere in FORGE code
  (it is a transitive dependency of claude-agent-sdk)
- Stage 3 (Implementation) uses **raw `requests`** for the Managed Agents beta REST endpoints
  because those endpoints are not exposed through claude-agent-sdk

### Tool scoping (allowed_tools)

`invoke_agent()` accepts `allowed_tools: list[str]`. Each agent script MUST pass only what
that stage needs — the SDK default gives Claude the full toolset (Read, Write, Edit, Bash, etc.):

| Stage | allowed_tools |
|-------|--------------|
| Intake | `["Read"]` |
| Requirements | `["Read"]` |
| Design | `["Read", "Write"]` |
| QA | `["Read", "Bash"]` |
| Security | `["Read", "Bash"]` |
| Deploy | `["Read", "Bash"]` |

### AgentResult — token/cost fields (IMPORTANT: read before using for cost tracking)

`invoke_agent()` returns an `AgentResult` dataclass. The JSON log line emits:
- `input_tokens`, `output_tokens`, `cache_creation_tokens`, `cache_read_tokens`
- `total_cost_usd`, `num_turns`, `stop_reason`, `latency_seconds`

Grep for `"forge_event": "agent_invocation"` in Actions logs to find all invocations.

**CRITICAL — use `total_cost_usd` as ground truth, NOT `input_tokens`:**

The SDK wraps the Claude Code CLI as a subprocess. On every call, the CLI sends its full
system prompt + all built-in tool definitions to the API (~25,693 tokens), regardless of
`allowed_tools`. The `allowed_tools` parameter becomes `--allowedTools` on the CLI — a
runtime execution permission filter, NOT an API token filter. The full tool payload is
prompt-cached after the first call per session:

| Call | cache_creation_tokens | cache_read_tokens | approx cost |
|------|----------------------|-------------------|-------------|
| First (cold) | ~25,693 | 0 | ~$0.096 |
| Subsequent (warm) | 0 | ~25,693 | ~$0.008 |

`input_tokens` reflects only the user message (typically 3–50 tokens) — useless as a cost
proxy. The CLI also makes an internal Haiku call (~500 tokens, ~$0.0005) included in
`total_cost_usd` automatically.

**Document 3 cost tables must key off `total_cost_usd`, not token counts.**

This was verified against real API output during smoke testing:
- `total_cost_usd: 0.09652` (first call) = cache creation of ~25,693 tokens at $3.75/MTok
- `total_cost_usd: 0.00843` (second call) = cache read of ~25,693 tokens at $0.30/MTok
- Arithmetic closes to within rounding on both runs.

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

**Real parsed output confirmed against `docs/Intake Template.xlsx`:**
- Overview: all six canonical keys present, each a dict of field_label → value pairs
- Requirements: R-001 through R-004 parsed correctly (Functional/Non-Functional, High/Medium/Low)

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
| `smoke_claude_agent` | **PASSED 5/5** | cache_creation_tokens / cache_read_tokens now verified in AgentResult and JSON log |
| `smoke_ado` | **PASSED 4/4** | Fixed: drop `System.State` from all four `_make_patch` calls — only `"New"` is valid as initial state in FORGE-Build |
| `smoke_github` | **PASSED 7/7** | post_comment/add_label retargeted to forge-template; commit_files + open_pr verified against forge-demo-apps |
| `smoke_managed_agents` | **PASSED 6/6** | Multi-agent path verified: coordinator + smoke-specialist subagent, 2-thread audit trail, specialist received delegation and replied DONE, archive of both agent resources, session.error scan clean |

`.env` vars needed: `FORGE_APP_ID`, `FORGE_APP_PRIVATE_KEY`, `FORGE_APP_CLIENT_ID`, `FORGE_GITHUB_OWNER`, `FORGE_TARGET_REPO`, `FORGE_SOURCE_REPO`, `GITHUB_TOKEN`, `ADO_PAT`, `ANTHROPIC_API_KEY`

**PEM format in `.env`:** wrap the full key in double quotes to preserve real newlines — `python-dotenv` requires this for multiline values. A trailing `""` (double double-quote) will break parsing.

---

## Outstanding Before Phase 3 Continues

- **Document 4 (Governance)** — ADR-0010 still needs to be added to the seed ADR list.
  Deferred 5+ times. Should land before Phase 3 wraps up.
- **`smoke_managed_agents`** — run once ready; wrapper has been fully rewritten for the current API.
- Phase 3 next step: **3.2 Intake Agent** (`core/agents/intake_agent.py`)
