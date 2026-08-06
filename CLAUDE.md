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

**Phase 3 — Agent Implementation: complete.** **Phase 4 — Pipeline Wiring: wired and
dispatch-verified, 2026-08-06** (see below for what "verified" does and doesn't cover).

Step 3.1 (shared agent utilities) is complete. Step 3.2 (Intake Agent) is complete.
Step 3.3 (Requirements Agent) is complete. Step 3.4 (Design Agent) is complete.
Step 3.5 (Implementation Coordinator) is complete, including a real (non-dry-run)
live run verified 2026-07-30 (PR #5 opened on forge-demo-apps). Step 3.8 (QA Agent)
is complete, including a real (non-dry-run) live run verified 2026-08-04 against a
manually-provided local checkout (8 ADO Bugs filed, PR #5 comment posted,
`qa-loop-back` applied to issue #2) — the "needs Phase 4's checkout wiring" caveat
only blocks the GitHub Actions automation, not a manual `--repo-path` invocation.
Step 3.9 (Security Agent) is complete, including a real (non-dry-run) live run
verified 2026-08-05 against the merged PR #5 (0 findings across Semgrep/Gitleaks/
Dependency-Check, `security-check` check run created with conclusion `success`,
`security-approved` applied to issue #2) — same manual `--repo-path` pattern as
the QA Agent's real run. Step 3.10 (Deploy Agent) is complete, including a real
(non-dry-run) live run verified 2026-08-05 against the merged PR #5's backend
units (`req-2026-01-document-api`, `req-2026-01-email-worker` deployed to
`forge-staging`; PR #5 comment posted) — the frontend unit and a real runtime
gap found on EmailWorker are still open, see below.

**Phase 4 (Build Plan steps 4.1–4.7, 4.9) — all seven `.github/workflows/*.yml`
stubs rewritten with real triggers, guard clauses, and agent invocations**;
committed and pushed directly to `main` 2026-08-06 (`8a702ee`). Full detail in
the "Phase 4 — Pipeline Wiring" section below. **Verified via a real
`repository_dispatch` end-to-end against the existing PR #5/issue #2 pair**:
the cross-repo dispatch chain, payload shape, and guard-clause logic are all
confirmed working. **Not yet verified: a real `qa_agent.py`/`security_agent.py`
invocation actually running through this dispatch path** — PR #5 is merged, so
both guard clauses correctly (and harmlessly) stopped before invoking the real
agents; that requires a fresh open PR, deliberately not created this session.
Step 4.8 (branch protection tied to the `security-check` required status check)
not yet actioned.

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
    04-qa.yml
    05-security.yml
    06-deploy.yml
requirements.txt
.env.example
```

(`security_agent.py` was missing from this list in a prior session despite
being complete and live-run-verified since Step 3.9 — added here alongside
`deploy_agent.py`, not a new file.)

Also, in `forge-demo-apps` (not this repo): `.github/workflows/notify-forge.yml`
— see the Phase 4 section below.

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

### github_helper.py — two auth contexts, two repo targets

| Function | Auth | Target repo |
|---|---|---|
| `post_comment`, `add_label`, `remove_label` | `GITHUB_TOKEN` | `forge-template` (tracking issue lives here) |
| `create_branch`, `commit_files`, `open_pr`, `get_file_contents`, `post_pr_comment`, `get_pr_comments` | App installation token | `forge-demo-apps` (cross-repo work) |

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
- Step 3.5 Implementation Coordinator (`core/agents/implementation_coordinator.py`) — done; dry run verified on issue #2 (96 files, 156 KB archive); **real live run verified 2026-07-30 (PR #5 opened on forge-demo-apps, 101 files)**.
- Step 3.8 QA Agent (`core/agents/qa_agent.py`) — done; **real live run verified 2026-08-04** (8 ADO Bugs filed #96–103, comment posted on forge-demo-apps PR #5, `qa-loop-back` applied to issue #2 — see below).
- Step 3.9 Security Agent (`core/agents/security_agent.py`) — done; **real live run verified 2026-08-05** (PR #5 comment posted, `security-check` check run created (conclusion `success`), `security-approved` applied to issue #2 — see below).
- Step 3.10 Deploy Agent (`core/agents/deploy_agent.py`) — done for the staging path; **real live run verified 2026-08-05** against the two backend units (`req-2026-01-document-api`, `req-2026-01-email-worker`) — see below. Frontend unit and the EmailWorker runtime-config gap are open follow-ups, not blockers on Step 3.10 itself.
- Phase 3 next step: Phase 4 wiring (all six stage agents now exist for the staging path).

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

**Dry run verified 2026-07-30:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- session `sesn_0158Mvs91wfr9rNHPfa9W1oH` — 4 threads (coordinator + 3 specialists), `idle (end_turn)`
- Archive: 156,728 bytes → 96 files extracted under `services/REQ-2026-01/`
  (full .NET solution with DocumentApi + EmailWorker, Next.js frontend, xUnit + Jest tests)

**Live (real, non-dry-run) run verified 2026-07-30:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- session `sesn_01EP8tcHcgdkSz7m14wKL4k6` — 4 threads (coordinator + 3 specialists), `idle (end_turn)`
- Archive: 79,601 bytes → 101 files extracted under `services/REQ-2026-01/`
  (full .NET solution with DocumentApi + EmailWorker, Next.js/TypeScript frontend,
  xUnit + Jest tests, Playwright e2e tests, `COMPLIANCE_CHECKLIST.md`)
- Committed to `feature/REQ-2026-01` in `forge-demo-apps`; draft **PR #5** opened
  against `main`; summary comment posted to tracking issue #2
- Session, environment, coordinator, and all 3 subagents archived cleanly after commit

**Operational incident during this run — resumed by ID, not by re-invoking the script:**
The `python -m core.agents.implementation_coordinator` process was killed by the
invoking shell tool's own timeout (background commands are capped around 10 minutes
in that tooling) while `poll_until_idle()` was still waiting. This killed the *local*
script only — the Managed Agents session itself runs server-side and kept working
independently, reaching `idle (end_turn)` on its own. Recovery was a small one-off
script that reused the already-known `session_id` / `coordinator_id` / `subagent_ids`
/ `environment_id` (from the `managed_agents_session_start` JSON log line printed
before the kill) to resume exactly where `run_implementation_coordinator()` left off —
`poll_until_idle()` (instant, since already idle) → audit trail → list/download output
files → `_extract_archive_to_file_dict()` → `commit_files()` → `open_pr()` →
`post_comment()` → `archive_session()`.

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

Previously `parent_story_id` was required. As of the QA Agent, Phase 4's ADO
item-creation step (4.3) hasn't been built/run for any request yet, so no real ADO
User Story IDs exist to link Bugs against. When `None`, `create_bug()` skips the
`link_items()` call and logs a warning instead of raising — the Bug is still filed,
just without a parent link. Once Phase 4 exists and writes real IDs to
`docs/<request-id>/ado-work-items.json`, callers should always pass a real ID; this
parameter stays optional in the function signature so `create_bug()` doesn't break
existing callers, but is expected to always receive a real ID in practice going forward.

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
  `docs/<request-id>/ado-work-items.json`'s `primary_user_story_id` key; returns
  `None` (logs a warning) since Phase 4 hasn't written one for any request yet —
  see the `ado_helper.py` entry above. Bugs are filed either way.
- `--dry-run`: runs tests and computes everything (including the Claude call) but
  prints to stdout instead of filing ADO Bugs, posting to GitHub, or applying labels.

**Verified 2026-08-03:** unit-tested with synthetic data in Claude.ai chat (no live
API/GitHub/ADO calls). `py_compile` clean; `smoke_github` (8/8) and `smoke_ado`
(4/4) re-run clean after the additive `github_helper.py`/`ado_helper.py` changes.
Confirmed `forge-demo-apps`' frontend `package.json` has `"test": "jest"` (a bare
script with no args of its own), so `npm test -- --ci --json --outputFile=...`
correctly forwards those flags to Jest, matching the module docstring's assumption.

**Real `--dry-run` verified 2026-08-04** against an actual local checkout
(`C:\Users\mikef\projects\forge-demo-apps-clone`, `services/REQ-2026-01/{backend,frontend}`)
— first time this script ran real `dotnet test` / `npm test` rather than synthetic
data. Results: backend 9/11 passed, frontend 38/44 passed, 8 deterministic bug
candidates computed, Claude wrote the PR report, correctly recommended
`qa-loop-back` (attempt 1 of 3). Confirms the TRX/Jest-JSON parsing, severity
heuristic, and retry-attempt logic all work against real tool output, not just
hand-built fixtures.

**Two Windows-only bugs found and fixed in `_run_shell()` during that run**
(both in the helper only — no behavior change on the Linux GitHub Actions
runners this normally runs on):
1. `subprocess.run(["npm", ...])` raised `FileNotFoundError` on Windows — `npm`
   is actually `npm.cmd`, and Win32 `CreateProcess` doesn't consult `PATHEXT`
   the way `cmd.exe` does, so a bare `"npm"` never resolves. Fixed by resolving
   `command[0]` through `shutil.which()` before passing to `subprocess.run`.
2. Jest's UTF-8/ANSI output (checkmarks, color codes) crashed a `subprocess`
   reader thread with `UnicodeDecodeError` under Windows' default `cp1252`
   text decoding. Fixed by passing `encoding="utf-8", errors="replace"`
   explicitly. Didn't corrupt the first run's result (frontend parsing reads
   the JSON report file, not stdout) but would have crashed the "suite failed
   to produce a report" diagnostic path, which does fall back to a stdout/stderr
   tail.

**Discovered during that same session: PR #5 was already merged, and the checkout
had uncommitted local patches never pushed to `forge-demo-apps`.** The dry-run's
8 failures were run against a checkout someone had hand-patched to even get
`dotnet restore`/`npm test` to run at all (missing `SendGrid.Extensions.
DependencyInjection` package ref, missing `using Microsoft.Extensions.
Configuration;`, an unresolvable `Microsoft.AspNetCore.Http.Features` package
ref, an invalid Jest config key `setupFilesAfterFramework` instead of
`setupFilesAfterEnv`, and missing frontend test devDependencies) — none of
which were ever committed. Filed as **PR #7** (`fix/req-2026-01-test-infra` →
`main`), reviewed, one stale/contradictory code comment removed, merged
2026-08-04 (`fcae2b6`). Re-verified with a fully clean checkout
(`git clean -xdf` in both `backend/` and `frontend/`, fresh `dotnet restore` +
`npm install`) — **identical 8-failure result**, confirming these are real
application bugs, not artifacts of the earlier patched state.

**Real (non-dry-run) live run verified 2026-08-04**, against that clean,
post-PR#7 checkout, invoked manually with `--repo-path` pointing at the local
clone (no Phase 4 workflow wiring involved — `--pr-number` is only required
for a real run per the script's own argparse help text; a manually-supplied
checkout satisfies the "needs a repo on disk" requirement just as well as an
Actions `actions/checkout` step would):
- 8 ADO Bugs filed in FORGE-Build: #96–97 (backend, Severity 3-Medium),
  #98–103 (frontend, Severity 2-High) — all with no parent User Story link
  (expected; Phase 4 ADO item creation hasn't run for this request yet)
- PR comment posted: `forge-demo-apps#5` comment
  (`issuecomment-5184902825`), attempt 1 of 3
- Label `qa-loop-back` applied to tracking issue `forge-template#2`
  (alongside the pre-existing `clarification-pending`)
- Claude call: 3,361 in / 947 out tokens, $0.024288, 15.58s

**Still not exercised: the actual Phase 4 GitHub Actions checkout wiring**
(step 4.5) — this run used a manually-provided local clone, not an
Actions-driven checkout. Functionally equivalent for the script's own logic,
but the workflow-level wiring itself remains unbuilt.

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
not just individual file reads via the Contents API — to run Semgrep,
Gitleaks, and OWASP Dependency-Check against `services/<request-id>/` under
`--repo-path`. This script does not clone anything itself; the same "local
checkout satisfies the manual-invocation case" pattern from the QA Agent
applies here too.

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
  - **OWASP Dependency-Check** → CVSS thresholds (≥9.0 Critical, ≥7.0 High,
    ≥4.0 Medium, else Low; cvssv3 preferred, cvssv2 fallback, Medium default
    if neither score is present).
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

**Verified 2026-08-05:** `py_compile` clean throughout.

**Real `--dry-run` first surfaced a genuine false positive**, run against
the merged PR #5 checkout at `services/REQ-2026-01/`: Gitleaks flagged 1
Critical finding — a hardcoded fake credential in
`backend/DocumentApi.IntegrationTests` (`WebApplicationFactory` test setup
config), the same class of expected-fixture-secret already anticipated in
the module's own severity-mapping design. Fixed by adding
`team/gitleaks-allowlist.toml` (Document 7's Flexible/Locked model — team-
configurable allowlist, `useDefault = true` keeps Gitleaks' full default
ruleset active everywhere else) with a path regex excluding any
`.../*test*/...` directory, and wiring `--config` into `_run_gitleaks()`
(see `github_helper.py` entry above for the four supporting GitHub API
functions this stage needed). Re-run confirmed the fix: Critical → 0,
Semgrep/Dependency-Check results unaffected, `check_conclusion` flipped to
`success`.

**Real (non-dry-run) live run verified 2026-08-05**, against that same
clean, post-allowlist-fix checkout, invoked manually with `--repo-path`
pointing at the local clone of the merged PR #5 (same "manual invocation
satisfies the on-disk-repo requirement" pattern as the QA Agent's real run
— Phase 4's checkout wiring, step 4.6, still not built):
- All three scanners ran clean: 0 findings (Semgrep, Gitleaks, Dependency-
  Check all 0), 0 Critical
- Overview comment posted to `forge-demo-apps` PR #5
- `security-check` check run created on PR #5's head commit (`0f5f1c57`),
  conclusion `success`
- Label `security-approved` applied to tracking issue `forge-template#2`
- Claude call: 599 in / 269 out tokens, $0.005832, 5.37s

### deploy_agent.py — Stage 6 (Deploy, staging)

Entry point: `python -m core.agents.deploy_agent --issue-number <n> --request-id <id> --repo-path <path> --commit-sha <sha> --pr-number <n> [--dry-run]`

Like QA and Security, this stage needs the actual repository contents on
disk (`--repo-path`) — it does not clone anything itself. Unlike every
prior stage, **it never calls Claude/`invoke_agent()`** — unit detection,
Dockerfile generation, and the PR comment are all deterministic
string/template work with no judgment call to hand to a model, the same
"FORGE automatic, not AI judgment" discipline QA's severity classifier and
Security's severity tables already established, just taken one step
further (no model call at all, not even for a write-up).

- **Unit detection** walks `services/<request-id>/backend/` for `*.csproj`
  files (skipping any path with a case-insensitive "test" segment, same
  convention as `team/gitleaks-allowlist.toml`), classifies each as `web`
  (references `Microsoft.NET.Sdk.Web`/`Microsoft.AspNetCore.App`) or
  `worker` (references `Microsoft.Extensions.Hosting`, no ASP.NET
  reference; also the default for an unclassifiable project, logged as a
  warning — the safer failure mode, since `web` implies public ingress).
  `services/<request-id>/frontend/package.json` becomes one additional
  `frontend` unit if present. Each unit's Container App / image name is
  `<request-id>-<slug>` (all lowercase — both Docker repository names and
  Azure Container App names reject uppercase; e.g. `DocumentApi` →
  `req-2026-01-document-api`).
- **Dockerfiles are generated from the three new templates
  (`core/agents/templates/dockerfiles/`) only when a project directory
  doesn't already have one of its own** — never overwrites an existing
  Dockerfile. A matching `.dockerignore` is generated the same way (not
  in the original brief, but required for a correct build — without it,
  `COPY . .` in the generated templates would overwrite the fresh,
  correct-platform artifacts from the earlier build stage with
  host-platform ones, and balloon the build context with node_modules/
  bin/obj).
- **Target ports are fixed, not configurable per run:** web units 8080
  (ASP.NET Core 8+ container default), frontend 3000 (`next start`
  default), worker units get no ingress at all.
- **`docker build`/`docker push` run for real in both `--dry-run` and a
  real run** — same "exercise the real tool, skip only the posting"
  pattern as QA/Security. `az login --service-principal` (parsing the
  `AZURE_STAGING_CREDENTIALS` JSON blob) and the read-only `az containerapp
  show` existence check also run for real in both modes, so the printed
  dry-run command reflects an accurate create-vs-update decision. Only the
  `az containerapp create`/`update` mutation itself is print-only (redacted
  `--registry-password`) in `--dry-run`.
- **`_detect_design_gaps()`** flags (never blocks) any unit whose project
  label doesn't appear in `docs/<request-id>/design.md`, surfaced in the PR
  comment. Checks both the literal identifier and a de-camelCased spaced
  variant ("EmailWorker" → "Email Worker") case-insensitively — design.md
  is human-authored prose and never uses the bare camelCase identifier; a
  literal-only check produced a false-positive gap on `DocumentApi` during
  this session's own verification (see below).
- No label applied on success — Document 6's Label Reference table has no
  deploy-stage label; staging is a verification step, not a release gate.

**Verified 2026-08-05:** `py_compile` clean throughout.

**Real `--dry-run` against the merged PR #5 checkout surfaced a genuine,
previously-undiscovered app bug**, not a Deploy Agent bug: `next build`
failed its type-check on `frontend/components/Navigation.tsx:28` —
`lucide-react` icon components inherit React's full `AriaAttributes`,
where `aria-hidden` is typed `Booleanish` (`boolean | "true" | "false"`),
but `NavItem.icon`'s custom prop type declared `aria-hidden` as plain
`boolean`, making the icons structurally incompatible. Never caught before
because QA's `npm test` only runs Jest, never `next build`/`tsc`. Fixed on
`forge-demo-apps` branch `fix/req-2026-01-navigation-aria-types` (widened
to `React.AriaAttributes["aria-hidden"]`, the exact type React itself
uses) — **opened as PR #8, deliberately left unmerged pending Mike's
review**, same "small, separate, mechanical fix" pattern as QA's PR #7.

**A second, unrelated, pre-existing type error surfaced immediately
after** in `lib/app-insights.ts:70` — a duplicate `@microsoft/
applicationinsights-core-js` dependency resolution (hoisted at top-level
`node_modules` vs. nested inside `applicationinsights-analytics-js/
node_modules/`), so TypeScript sees two structurally-identical-but-
nominally-different `ITelemetryPlugin`/`ITelemetryItem` types. **Explicitly
not investigated or fixed this session, per Mike's direction** — flagged
as an open follow-up. As a result, **the frontend unit was not verified
end-to-end this session**: it was parked (its `package.json` renamed aside
in the local checkout only, no code change) so unit detection would skip
it, and dry-run/real-run verification proceeded backend-units-only.

**Real (non-dry-run) live run verified 2026-08-05**, backend units only,
against the same merged-PR-#5 checkout used for QA/Security's real runs:
- 2 units detected: `req-2026-01-document-api` (web),
  `req-2026-01-email-worker` (worker)
- Both Dockerfiles already existed (committed by Stage 3 back in PR #5) —
  neither template was actually exercised for this run; the templates are
  verified structurally but not yet by a real from-template build. The
  Next.js template is similarly unexercised (frontend parked).
- Both images built and pushed to `forgedemoacr.azurecr.io` for real
- Both Container Apps created for real via `az containerapp create`
  against `forge-staging` (`forge-build-rg`, per `team/config.yaml`)
- PR comment posted: forge-demo-apps#5
  (issuecomment-5197961121)
- **`req-2026-01-document-api` confirmed actually working**: its staging
  FQDN (`req-2026-01-document-api.yellowmeadow-894377a9.canadacentral.
  azurecontainerapps.io`) resolves and responds over HTTPS (~0.3s once
  warm; first request timed out during cold-start scale-from-zero,
  `min_replicas: 0` per `team/config.yaml`, then responded fine on retry).
  404s on `/` and `/swagger/index.html` are expected (no root route;
  Swagger UI is Development-only, this container runs
  `ASPNETCORE_ENVIRONMENT=Production`) — this confirms the ingress/TLS/
  container layer is genuinely live, not that every route is mapped.
- **`req-2026-01-email-worker` deployed but is crash-looping — a real,
  previously-undiscovered gap, not a Deploy Agent bug.** `az containerapp
  revision list` shows `healthState: Unhealthy` / `runningState: Failed`.
  Container logs show `System.FormatException: The connection string
  could not be parsed` from `ServiceBusClient`'s constructor at host
  startup (`Program.cs:20`) — EmailWorker's hosted service builds its
  Service Bus client eagerly at startup and crashes immediately with no
  connection string configured. **Deploy Agent (as scoped this session)
  has no mechanism at all for wiring application secrets/connection
  strings (Service Bus, SQL, Blob Storage, SendGrid, App Insights) into
  the Container App** — only `--image`/`--registry-*`/`--cpu`/`--memory`/
  `--min-replicas`/`--max-replicas`/`--target-port`/`--ingress` are ever
  set. DocumentApi doesn't crash the same way because EF Core/Blob clients
  are constructed lazily (only touched on first actual request), so a
  missing connection string there just means the *first real API call*
  would fail, not the whole host at startup — the ingress-level check
  above cannot distinguish this from full correctness. **This needs an
  explicit decision (Key Vault references? Container App secrets driven
  from a new team/config.yaml or GitHub-secrets source? something else?)
  before EmailWorker can actually run in staging** — flagged here, not
  designed or built.
- Two bugs found and fixed in `deploy_agent.py` itself while getting to
  the clean runs above: an em-dash console-encoding issue in log messages
  (same class of fix already applied to `security_agent.py`'s log lines —
  fixed to ASCII `--`), and the design.md-gap false-positive described
  above (fixed to check both the literal and spaced form).
- `.env.example` gained `ACR_LOGIN_SERVER`/`ACR_USERNAME`/`ACR_PASSWORD`
  and `AZURE_STAGING_CREDENTIALS` entries (were previously undocumented
  there despite being referenced in other project docs).
- Local tooling: Docker Desktop and Azure CLI (64-bit) already installed
  and confirmed working per chat 33's setup — no new install steps this
  session.

**Still open, not built/fixed this session (explicitly out of scope per
the brief, or newly flagged):**
- Frontend unit unverified end-to-end (parked — see PR #8 and the
  app-insights dependency issue above).
- EmailWorker's runtime connection-string gap (needs a design decision,
  not just a fix).
- Production path, rollback, and Phase 4 GitHub Actions wiring for either
  environment — all explicitly deferred per the original brief.

---

### Phase 4 — Pipeline Wiring (Build Plan steps 4.1–4.7, 4.9)

All seven `.github/workflows/*.yml` files rewritten from `workflow_dispatch`-only
stubs to real triggers, wired 2026-08-05/06. Every workflow follows the same
shape: guard clause re-checks trigger state at run time (not just at the
event, since labels/PR state can change between event and runner start) →
resolve request-id/PR context → invoke the real stage agent script (no
`--dry-run`) → label lifecycle cleanup → a final catch-all step posts a
failure comment if a *pre-agent* glue step failed (the agent scripts
themselves already self-report their own internal failures per ADR-0011 —
this only covers the gap before that point, and is skipped whenever the
agent step actually ran, to never double-post).

**Trigger mapping:**

| Workflow | Trigger | Clears on success |
|---|---|---|
| `00-intake.yml` | `intake-ready` label | `intake-ready` |
| `01-requirements.yml` | `clarification-complete` label | `clarification-complete`, `clarification-pending` |
| `02-design.yml` | `requirements-approved` label | `requirements-approved` |
| `03-implementation.yml` | `design-approved` label | `design-approved` |
| `04-qa.yml` | `repository_dispatch` (`feature-pr-opened`, from forge-demo-apps) | none (qa_agent.py labels itself; a pass also clears a stale `qa-loop-back`/`qc-retry-limit-reached` from an earlier attempt) |
| `05-security.yml` | `repository_dispatch` (`feature-pr-opened`) | none (security_agent.py labels itself; no retry-loop label exists for this stage) |
| `06-deploy.yml` | BOTH `qa-approved` AND `security-approved` present | none (Document 6 has no deploy-stage label; `qa-approved`/`security-approved` stay as valid historical markers) |

**Cross-repo trigger problem and its fix:** `04-qa.yml`/`05-security.yml` need
to run off a PR event that happens in `forge-demo-apps`, but a workflow can
only be triggered by an event in the repo where it's defined. Fixed via
`repository_dispatch`: `forge-demo-apps` gained its own
`.github/workflows/notify-forge.yml` (pushed there directly via `gh api`,
since the FORGE App itself has no `workflows` permission and can't write
workflow files programmatically) that fires on `pull_request` (`opened`,
`synchronize`), filters to `feature/*` branches only, and forwards
`{pr_number, head_sha, head_ref}` to forge-template as a `repository_dispatch`
event type `feature-pr-opened`, using a GitHub App token freshly scoped to
forge-template (`actions/create-github-app-token@v3`).

**Three manual prerequisites this required, all completed 2026-08-06:**
1. The FORGE App (app_id 4388813, installation id 148876680) is now
   installed on **both** forge-template and forge-demo-apps — confirmed via
   a JWT-authenticated `GET /repos/.../installation` check on both repos
   (both return 200 with identical permissions:
   `checks/contents/issues/pull_requests: write`, `metadata: read`). This had
   to be done via the GitHub web UI — the API rejects attempts to modify an
   App's own installation repository list from anywhere other than that UI.
2. `forge-demo-apps` gained its own copies of `FORGE_APP_CLIENT_ID` (repo
   variable) and `FORGE_APP_PRIVATE_KEY` (repo secret) — repo secrets/vars
   don't cross repos in GitHub Actions, so forge-template's existing values
   weren't visible there.
3. `notify-forge.yml` itself, pushed to forge-demo-apps' `main`.

**New scripts:**
- `core/agents/create_ado_items.py` — no driver existed to wire
  `ado_helper.py`'s `create_epic`/`create_feature`/`create_user_story` to
  `docs/<request-id>/ado-work-items.json`. Reads that file (main branch),
  creates the real Epic → Features → User Stories hierarchy, writes the real
  IDs back plus a new top-level `primary_user_story_id` key (the first User
  Story created, in document order — `qa_agent.py`'s
  `_resolve_parent_story_id()` already looks for exactly this key and had
  been silently no-op'ing on its absence since Step 3.8). If ANY ADO call
  fails partway through, posts a failure comment naming what succeeded before
  the failure (items already created are NOT rolled back — ADO has no
  multi-item transaction) and exits non-zero, so `02-design.yml` never
  invokes the Design Agent against a partial traceability chain.
- `core/agents/workflow_glue.py` — four subcommands used only by the
  workflows themselves, with no equivalent in any stage agent:
  `download-issue-attachment` (finds and downloads the BA's intake
  spreadsheet from the tracking issue's body/comments — handles both GitHub
  attachment URL shapes), `resolve-request-id` (scans issue comments for any
  prior stage's `<!-- forge:agent-comment ... request_id=... -->` marker —
  one tracking issue maps to exactly one request for its whole life),
  `resolve-feature-pr` (finds the feature PR number/head SHA from the
  Implementation Coordinator's own tracking-issue comment, for
  `06-deploy.yml`), `resolve-tracking-issue` (the reverse — finds the
  tracking issue number from a forge-demo-apps PR body's own "Related FORGE
  tracking issue: owner/repo#N" line, for `04-qa.yml`/`05-security.yml`,
  which only ever learn a PR number from the dispatch payload).
- `github_helper.py` gained `get_issue()` (issue object incl. current labels
  — needed by every guard clause; didn't exist before since no prior stage
  needed to re-read an issue's own label set).

**Design decision made where the brief was silent:** `06-deploy.yml` deploys
against the feature PR's **HEAD commit**, not a merged one. Nothing in the
label-driven trigger chain guarantees the PR has been merged by the time both
`qa-approved`/`security-approved` land (both gate *before* merge, by design —
see `04-qa.yml`/`05-security.yml`'s own header comments), and
`deploy_agent.py` only ever needed a commit SHA to tag the image with, not a
merged one. Confirmed intentional: staging is a pre-merge verification
environment for the human reviewer (Document 2 §4.8's framing — "a
verification step, not a release"), not a post-merge release gate.

**Verified 2026-08-06** via a real `repository_dispatch` fired manually
against the existing PR #5 / tracking issue #2 pair (deliberately not a fresh
PR — reusing already-completed Stage 3 output to avoid re-running the
Managed Agents coordinator, whose cost is out of proportion to what this
verification needed):
- Confirmed both App-installation and forge-demo-apps secrets prerequisites
  above were actually in place first (not assumed).
- Fired `POST /repos/Flamespiker/forge-template/dispatches` with
  `event_type: feature-pr-opened`, `client_payload: {pr_number: 5, head_sha:
  "0f5f1c57ea5812537bc6d0150aa55d3722f3b190", head_ref:
  "feature/REQ-2026-01"}` — the same payload shape `notify-forge.yml`
  produces for a real event.
- Both `04-qa.yml` ([run 31068863663](https://github.com/Flamespiker/forge-template/actions/runs/31068863663))
  and `05-security.yml` ([run 31068863654](https://github.com/Flamespiker/forge-template/actions/runs/31068863654))
  fired for real off the dispatch, both concluded `success`. Logs confirm the
  `client_payload` crossed the repo boundary intact (`PR_NUMBER: 5`,
  `HEAD_SHA: 0f5f1c57...`, `HEAD_REF: feature/REQ-2026-01`), and both guard
  clauses correctly read PR #5's live state (`closed`, since it's merged) and
  correctly skipped every downstream step (checkout, toolchain setup, the
  real `qa_agent.py`/`security_agent.py` invocation) rather than running
  against a stale event — confirmed no new PR #5 comment resulted.
- **What this confirms:** the full cross-repo dispatch mechanism, payload
  shape, and guard-clause decision logic all work correctly end-to-end.
- **What this does NOT confirm:** a real `qa_agent.py`/`security_agent.py`
  invocation actually completing through this dispatch path (posting a PR
  comment, applying a label) — that requires an actually-open PR, which
  would mean either a new throwaway PR or re-running Stage 3, both
  deliberately out of scope this session.

**Commit:** `8a702ee` on `main` (all ten Phase 4 files — seven workflows,
`create_ado_items.py`, `workflow_glue.py`, `github_helper.py`'s `get_issue()`
addition — committed and pushed together).

**Not done / explicitly deferred:**
- Step 4.8 (branch protection wiring the `security-check` required status
  check to forge-demo-apps) — not actioned this session.
- A real end-to-end agent run through the new dispatch path (see above).
- `docs/FORGE-context_v37.md` exists in the repo root as an untracked file
  (present before this session started) — not read, not committed, not
  touched; flagged here only so a future session doesn't assume it's part of
  Phase 4's work.
