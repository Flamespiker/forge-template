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
- **Full project context:** `docs/FORGE-context_v48.md` — read this for architecture decisions,
  agent roster, pipeline stages, and session history

---

## Current Build Phase

**Phase 3 — Agent Implementation: complete. Phase 4 — Pipeline Wiring: complete**
(4.1–4.9 wired 2026-08-06; 4.10 full dry-run, `DRYRUN-2026-01`, completed
2026-08-09 — see below). **Phase 5 — App 1 (`REQ-2026-02`, Inactive User &
License Auditor): substantially complete.** Reached staging, confirmed
working in a real browser; production deliberately not attempted. Close-out
doc written 2026-08-13 (`FORGE-Phase5-Closeout.md`) — full detail on what
shipped, the R-001 descope, every confirmed structural gap, and real
manual-intervention count. **App 1's Azure Container Apps and D365
connection decommissioned 2026-08-13** (App User disabled, secret deleted,
app registration kept for potential reuse; code retained in
`forge-demo-apps`). **Cost log transcription complete (2026-08-13)** —
`docs/FORGE-pipeline-cost-log.md` now has real QA/Security per-run tables,
backfilled Intake/Requirements figures, and corrected §3 cumulative totals
(commit `8f7fc24`), per `docs/FORGE-cost-log-transcription-patch.md`. Three
REQ-2026-02 cost gaps (Requirements, QA partial, Security missing) remain
flagged as open gaps in that log, not resolved.

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

**Step 4.10 (full pipeline dry-run, request-id `DRYRUN-2026-01`, tracking issue
`forge-template#4`) is in progress, being run in a separate/parallel session**
— not yet fully written back here (that session documents its own stages when
it concludes). This session's own contribution is limited to recovering a
stalled Implementation Coordinator run and spot-checking the result; see the
"Step 4.10 — Implementation recovery" section at the end of this file for detail.

**Phase 4 (Build Plan steps 4.1–4.9) — all seven `.github/workflows/*.yml`
stubs rewritten with real triggers, guard clauses, and agent invocations**;
committed and pushed directly to `main` 2026-08-06 (`8a702ee`). Full detail in
the "Phase 4 — Pipeline Wiring" section below. **Verified via a real
`repository_dispatch` end-to-end against the existing PR #5/issue #2 pair**:
the cross-repo dispatch chain, payload shape, and guard-clause logic are all
confirmed working. **Not yet verified: a real `qa_agent.py`/`security_agent.py`
invocation actually running through this dispatch path** — PR #5 is merged, so
both guard clauses correctly (and harmlessly) stopped before invoking the real
agents; that requires a fresh open PR, not yet created. **Step 4.8 (branch
protection on forge-demo-apps requiring the `security-check` status check)
is complete** — confirmed live via `gh api repos/.../branches/main/protection`:
`security-check` (app_id 4388813) required, 1 approving review required,
`enforce_admins: true`, force-pushes/deletions blocked, **no
`bypass_pull_request_allowances`** (GitHub rejects that field entirely on a
personal-account repo like forge-demo-apps — confirmed empirically via a 422,
not assumed from the docs alone).

Getting to a clean rule required a real conflict resolution, not just a
config change: `requirements_agent.py` and `create_ado_items.py` both wrote
`requirements.md`/`ado-work-items.json` **straight to `main`** via
`commit_files()` — which the required-review rule above would reject outright
(a GitHub App with no bypass path on a personal repo has no way around it).
**Fix: both files moved to a dedicated, intentionally-unprotected
`pipeline-state` branch in forge-demo-apps** (created once, branched from
`main`'s tip) — bookkeeping/traceability records, not application code; the
real human review already happens via the posted issue-comment draft, not a
git diff on `main`. `design_agent.py` and `qa_agent.py`'s reads of these two
files were updated to the same branch. Full detail in the "Phase 4 — Pipeline
Wiring" section below.

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

**Live run verified 2026-07-29:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- 2,281 input tokens / 3,876 output tokens / `total_cost_usd: $0.064983` / 62.5 s
- `requirements.md` + `ado-work-items.json` committed to `forge-demo-apps` on `main`
  (historical — this run predates the Phase 4 step 4.8 retrofit that moved both
  files to the `pipeline-state` branch; see above)
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
- Phase 3 complete. Phase 4 (pipeline wiring, all seven workflows + branch
  protection) is also complete as of 2026-08-06 — see the "Phase 4 — Pipeline
  Wiring" section below. Next: a real end-to-end agent run through the new
  `repository_dispatch` path (requires an actually-open PR).

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
  `docs/<request-id>/ado-work-items.json`. Reads that file (`pipeline-state`
  branch, moved off `main` — see the Step 4.8 entry below), creates the real
  Epic → Features → User Stories hierarchy, writes the real
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
addition — committed and pushed together). `55a1384`/`3201fa8` document this
Phase 4 section itself in `CLAUDE.md`.

**Step 4.8 — branch protection: complete, after resolving a real conflict it
surfaced (not just a config change).** `forge-demo-apps`'s `main` branch
protection is live, confirmed via `gh api repos/Flamespiker/forge-demo-apps/
branches/main/protection`:
- `required_status_checks.checks`: `[{"context": "security-check", "app_id":
  4388813}]` (pinned to the FORGE App's own check run from
  `security_agent.py`'s `create_check_run()`), `strict: false`
- `required_pull_request_reviews.required_approving_review_count`: `1`,
  `dismiss_stale_reviews: false`, `require_code_owner_reviews: false`,
  `require_last_push_approval: false`
- `enforce_admins: true`, `allow_force_pushes: false`, `allow_deletions: false`,
  `required_linear_history: false`
- **No `bypass_pull_request_allowances`** — not needed; see below.

This is what actually makes a Critical security finding block merge (the
`security-check` check run's `failure` conclusion, not the `security-approved`
label, per Document 2 §4.7 — the label is informational for humans, this is
the enforcement mechanism).

**How this actually got applied — first attempt found a real conflict, second
attempt hit a platform limitation, third attempt resolved it properly:**
1. First applying required-PR-review protection to `main` would have broken
   `requirements_agent.py` and `create_ado_items.py`, both of which wrote
   `requirements.md`/`ado-work-items.json` **straight to `main`** via
   `commit_files()` — a direct ref update, which required-review protection
   rejects identically to a `git push`. Found by reading the live source
   before applying anything, not discovered by breaking something.
2. Considered adding the FORGE App to
   `required_pull_request_reviews.bypass_pull_request_allowances.apps`
   (confirmed the correct field expects the app **slug**, `"forge-pipeline"`,
   not the numeric app ID — those are two different formats; the app ID
   *is* used, but only in `required_status_checks.checks[].app_id`). Rejected
   by GitHub with a 422 (`"Only organization repositories can have users and
   team restrictions"`) even with only `apps` populated — confirmed
   empirically that `bypass_pull_request_allowances` cannot be used at all on
   a personal-account-owned repo like forge-demo-apps, not just its
   `users`/`teams` sub-fields as the docs' wording alone would suggest.
3. **Resolution: moved `requirements.md`/`ado-work-items.json` off `main`
   entirely, onto a dedicated, intentionally-unprotected `pipeline-state`
   branch** (created once, branched from `main`'s tip — persistent and
   shared across every request, unlike the per-request `design/<request-id>`/
   `feature/<request-id>` branches, so neither writer calls `create_branch()`
   itself). Framing: these two files are pipeline bookkeeping/traceability
   records, not application code — the real human review for Requirements
   already happens via the posted issue-comment draft, not a git diff on
   `main`, so this doesn't rework the approval gate at all.
   - Writers updated: `requirements_agent.py`, `create_ado_items.py`.
   - Readers updated to the same branch (explicitly, not via a changing
     default): `design_agent.py` (`requirements.md`), `qa_agent.py`
     (`ado-work-items.json`, in `_resolve_parent_story_id()`).
   - Not affected: `implementation_coordinator.py`/`deploy_agent.py`'s reads
     of `design.md`/`openapi.yaml`/`tasks.md` — those still land on `main`
     for real, via a human-reviewed PR, exactly as before.
   - Verified without spending on a real Requirements/Design run or filing
     duplicate ADO items: `create_ado_items.py --dry-run` still creates real
     ADO work items (no dry-run mode exists on ADO's side) and
     `requirements_agent.py --dry-run` never reaches its `commit_files()`
     call at all — so neither flag actually exercises the changed branch
     name. Verified the real mechanism directly instead: read both files
     from `pipeline-state` (confirmed inherited correctly from `main` at
     branch-creation), then round-tripped a no-op write via `commit_files()`
     against `pipeline-state` and confirmed the content came back
     byte-identical — proves the full blob→tree→commit→ref-update chain
     works against the new branch.
   - Commit `780a93f` on `main`.
4. Protection re-applied cleanly (payload above) once the conflict no longer
   existed, and read back via a fresh `GET` (not trusted from the `PUT`
   response) to confirm no `bypass_pull_request_allowances` leaked in from
   the earlier rejected attempts.

**Not done:**
- A real end-to-end agent run through the new dispatch path (see above) —
  requires an actually-open PR, not yet created.

---

### Step 4.10 — Implementation recovery (DRYRUN-2026-01, cross-session)

Step 4.10 is a full pipeline dry-run exercising Stages 0–6 end-to-end against
a fresh intake (request-id `DRYRUN-2026-01`, tracking issue `forge-template#4`),
being driven from a separate/parallel session. This section documents only
what happened in *this* session: recovering a stalled Implementation
Coordinator run and verifying the result. Confirmed with Mike 2026-08-10 that
`DRYRUN-2026-01`/issue #4 are real and simply hadn't been written back here
yet — the other session's full Step 4.10 status (Intake/Requirements/Design
that presumably preceded this, and QA/Security/Deploy that follow it) lands
here separately when that session concludes.

**A distinct root cause from REQ-2026-01's incident, sharing only the recovery
principle.** REQ-2026-01's earlier incident (see the `implementation_coordinator.py`
entry above) was the *local* process/tracker getting killed mid-flight by the
invoking shell tool's own timeout, while the remote Managed Agents session kept
working independently. Today's failure was different: the
`03-implementation.yml` Actions job ran to completion and explicitly failed —
`managed_agents_wrapper.py`'s session-archive step exhausted its fixed 3-attempt
exponential-backoff retry (2s/4s/8s) and gave up while Test Writer was still
legitimately still working underneath. The top-level coordinator had already
reported `idle`/`end_turn`, but a subagent thread was still active, so the
archive call kept hitting the same "still running" rejection until the retry
budget ran out — a genuinely slow-but-healthy session, not a killed process.
The Managed Agents session itself reached real `idle` shortly after. Per the
standing rule from REQ-2026-01, the recovery principle still applies even
though the trigger differs: resume by reusing the known session ID, never
re-invoke the coordinator.

**Recovery script: `resume_implementation.py`** (repo root, one-off — not a
permanent module), hardcoding the IDs recovered from the failed job's log:
`session sesn_01XefEai7XEyGBgAMDxUJh3u`, coordinator `agent_01VMj1F7w1tsRe8wqQXjGcoc`,
environment `env_01TkNm9Xy5z5ANEVwopaRViR`, 3 subagents. It re-runs only the
tail end `run_implementation_coordinator()` would have: download the
already-produced archive → extract → `create_branch()`/`commit_files()` →
`open_pr()` → `post_comment()` → `archive_session()`.

**Run verified 2026-08-06:**
- Extracted 24 files from a 15,072-byte archive under
  `services/DRYRUN-2026-01/` — a minimal .NET health-check API
  (`HealthController`, `HealthCheckResponse`) + xUnit tests + Next.js
  frontend, consistent with a deliberately small dry-run scope (vs.
  REQ-2026-01's full DocumentApi/EmailWorker pair)
- Committed to new branch `feature/DRYRUN-2026-01` (SHA `f99d2a01`) in
  `forge-demo-apps`
- Draft **PR #10** opened: "FORGE Implementation: DRYRUN-2026-01"
- Comment posted to tracking issue `forge-template#4`
- Session, environment, coordinator, and all 3 subagents archived cleanly —
  no lingering billed resources, no fallback warning path triggered

**PR #10 spot-checked against a real local checkout:** fetched
`feature/DRYRUN-2026-01` into `forge-demo-apps-clone` (same local clone used
for QA/Security's manual runs) and ran `dotnet test` directly against
`services/DRYRUN-2026-01/backend.tests` — **3/3 passed, 0 failed**
(`HealthCheckApi.Tests.dll`). Confirms the resumed archive's backend content
actually builds and its tests actually run, not just that the commit
succeeded.

**Not exercised in this session:** QA/Security/Deploy stages for
`DRYRUN-2026-01`, the frontend unit, and whatever Stage 0–2 work in the other
session preceded this Implementation step. Full Step 4.10 status to be
written back by that session when it concludes.

### qa_agent.py — backend test directory resolution fix (found via DRYRUN-2026-01)

**Root cause:** `_run_backend_tests()` hardcoded the backend test directory
as `services/<request-id>/backend` — the API project's own folder — rather
than the actual xUnit test project's location. Test Writer correctly places
tests in a sibling folder (e.g. `backend.tests/`); neither Document 3 nor
Document 7 mandates a specific layout, so the hardcoded path was simply
wrong, not an enforcement of a documented convention.

**Symptom:** the QA Agent reported "test suite failed to run (build/compile
error)" for a backend suite that actually passes cleanly — confirmed via a
local `dotnet test` run: 3/3 passed.

**Fix:** added `_resolve_backend_test_dir()`, which globs for the actual
`*.Tests.csproj` file under the service root instead of assuming a fixed
path. Warns (but proceeds) if multiple are found. **Superseded 2026-08-10 by
the Phase 5 pre-flight Fix 3 below: "no test project found" now resolves to
`not_applicable`, not a fall-back-and-fail.**

**Verification:** re-ran QA against PR #10 after the fix — backend suite
came back `ran: true`, 3/3 passed.

**Committed and pushed to `main`:** `e2a123eb45476e501dfca0e0b628297a3f4153f2`.

**Open follow-up, not yet done:** this may also be the root cause of
REQ-2026-01's long-standing, previously-undiagnosed "QA backend TRX report
failure" — worth checking that repo's structure against this same pattern to
confirm, but not verified yet. **Update 2026-08-10: re-ran QA `--dry-run`
against REQ-2026-01's real local checkout while verifying Fix 3 below —
backend suite ran cleanly (62/62 passed), no TRX report failure reproduced.**
Not conclusively "closed" (a single clean run isn't the same as a root-cause
diagnosis of what the original undiagnosed failure actually was), but it did
not recur.

---

### Phase 5 pre-flight fixes (per `docs/FORGE-Phase5-Preflight-Fixes-Spec.md`)

Three fixes made ahead of Phase 5's real App 1 ("Inactive User & License
Auditor") run, per the spec drafted in Claude.ai chat 41. All three verified
individually and committed separately, per the spec's own standing
convention. `docs/FORGE-Phase5-Preflight-Fixes-Spec.md` is the source
document — this section records only what actually happened running it, not
a restatement of the spec itself.

**Fix 1 — Managed Agents archive-retry backoff
(`core/agents/utils/managed_agents_wrapper.py`).** Root cause (DRYRUN-2026-01
Stage 3 incident, already documented above): `archive_session()` trusted
only the coordinator's own idle/end_turn signal, with a 3-attempt (~14s)
retry-with-backoff as the sole cushion — too thin when a subagent thread is
still legitimately running under an idle coordinator.

- Added `_get_thread_statuses()` (lightweight `GET /sessions/{id}/threads`,
  no per-thread event fetch) and `_wait_for_subagent_threads_idle()`, called
  as a new step 0 inside `archive_session()` before the archive call is even
  attempted. Polls every 5s for up to 120s; returns immediately once every
  thread reports idle, or immediately (with a warning) if the API doesn't
  expose a thread status field at all — degrading cleanly to the backoff
  loop as the sole safety net in that case.
- Widened `_ARCHIVE_RETRY_ATTEMPTS` from 3 to 6 (same 2×-doubling schedule:
  2s/4s/8s/16s/32s/64s, ~126s total) as the secondary safety net for the
  separate idle→running race — unchanged from before, just given more room.
- Each 400 retry now logs the actual per-thread statuses observed at that
  attempt (not just "still running"), per the spec's explicit ask.
- **Resolved the spec's open design fork:** confirmed live via
  `smoke_managed_agents.py` (10/10 passed) that
  `GET /v1/sessions/{id}/threads` DOES expose a real, usable `status` field
  ("idle") on both coordinator and subagent thread objects — this was
  "not confirmed in current docs" per the spec, and now is. The
  still-busy/retry-logging code paths themselves were not exercised by this
  run (the smoke test's subagent finished before the coordinator went idle,
  so the pre-check found everything already idle on its first poll) —
  reasoned through rather than reproduced under load; no incident has
  surfaced to force the busy path deterministically.
- Committed separately: `cab6995`.

**Fix 2 — `security-check` permanently unsatisfiable on design-stage PRs
(`forge-demo-apps`).** Root cause (already documented in the Phase 4
section above): `main`'s branch protection requires `security-check` on
every PR, but only `feature/*` PRs ever trigger it via
`notify-forge.yml`/`05-security.yml`. `design/*` PRs sit "Waiting for status
to be reported" forever.

- Added `.github/workflows/design-pr-security-noop.yml` in
  `forge-demo-apps` — triggered on `pull_request` (`opened`, `synchronize`),
  guarded to `design/*` branches both at the job-level `if:` and again via an
  explicit shell case-statement inside the job (fails loudly, not silently,
  if that inner check is ever reached on a non-`design/*` ref). Creates a
  `security-check` check run with `conclusion: success` and a summary that
  explicitly states this is a no-op, not a real scan, using the same
  `actions/create-github-app-token@v3` pattern `notify-forge.yml` already
  uses (Checks: Write permission already granted, no new grant needed).
- **Had to be pushed via Mike's own `gh` credentials (workflow scope), not
  the FORGE App's installation token** — `commit_files()` 403'd against
  `.github/workflows/*` for the same reason `notify-forge.yml` originally
  needed manual push: the App has no `workflows` permission. Branch
  `fix/design-pr-security-noop` created via the App token (that part is a
  normal branch, not a workflow file), the workflow file itself written via
  `gh api ... --method PUT` under Mike's own token, then draft **PR #11**
  opened via the App token (opening a PR doesn't need `workflows` either).
  Left open, unmerged, pending Mike's review at the time this fix was built —
  matches the existing PR #7/#8 "small mechanical fix, agent doesn't merge
  its own PR" pattern (ADR-0009). **Merged 2026-08-11 in a follow-up
  session — see the PR #11 merge entry below.**
- **Verified live** with a throwaway `design/fix2-smoketest` branch/PR
  (branched from `fix/design-pr-security-noop` so the new workflow file was
  actually present in the head ref — a `design/*` branch cut from `main`
  alone would not have picked it up yet, since `main` won't have the file
  until PR #11 merges): `security-check` check run appeared within ~20s,
  `conclusion: success`, with the intended "design-stage PR — not a real
  scan" summary text. PR's `mergeable_state` was `blocked` only on the
  still-intact required-review gate, not on the status check. Throwaway PR
  closed and branch deleted immediately after verification — nothing left
  behind in `forge-demo-apps` from the test itself.
- Re-read `main`'s branch protection after all of the above: `checks`,
  `allow_force_pushes`, `allow_deletions` all unchanged from before this
  fix's own work.
- **Flagging, not fixing, a pre-existing discrepancy found while re-checking
  protection per the spec's own acceptance criteria:** live
  `enforce_admins.enabled` is currently `false`. This directly contradicts
  what Step 4.8 (Phase 4 section, above) documented as confirmed —
  `enforce_admins: true`. Nothing in this session's own work touched
  `enforce_admins` (confirmed by checking it both before and after Fix 2's
  changes — `false` both times). Best guess: this is a side effect of
  whatever admin action was used to force-merge the `DRYRUN-2026-01` design
  PR past the then-unsatisfiable `security-check` gate — an admin-merge
  override on a single PR shouldn't normally touch the persistent protection
  setting, but something did, and it wasn't this session. **Not restored
  here** — a branch-protection setting is shared infrastructure and the spec
  explicitly asks to surface exactly this kind of thing rather than resolve
  it silently. Mike should decide whether to flip it back to `true` (closing
  the gap `enforce_admins: true` was originally meant to close) now that
  Fix 2 removes the reason an admin bypass was needed in the first place.

**Fix 3 — QA Agent `not_applicable` outcome
(`core/agents/qa_agent.py`).** Root cause: `_run_frontend_tests()` assumed
every service has a real Jest setup; a backend-only service (e.g.
`DRYRUN-2026-01`, no `"test"` script in `package.json`) got reported as a
hard failure identical in shape to a genuinely broken suite, burning the
full 3-attempt retry budget on a non-issue (this is what actually forced the
manual `qc-retry-limit-reached` → `qa-approved` override on
`DRYRUN-2026-01` that the Phase 4 write-up alludes to).

- `TestSuiteResult` gained a `not_applicable: bool` field — a real third
  outcome, not a variant of pass or fail. Never counts against the retry
  budget, never files an ADO Bug, reported plainly in the PR comment
  ("Not applicable — no test suite in scope for this service").
- New `_frontend_test_script_exists()` checks for a `package.json` with a
  non-empty `"test"` script before ever invoking `npm test`.
- `_resolve_backend_test_dir()` changed to return `(None, warning)` — not a
  guessed fallback path — when no `*.Tests.csproj` exists anywhere under the
  service root at all, so "no test project exists" no longer falls through
  to the old hardcoded-path-then-fail behavior described in the entry above
  this one.
- `suite_run_failed` / `tests_pass` / the synthetic "suite failed to run" bug
  filing loop all updated to treat `not_applicable` suites as excluded from
  the verdict entirely, not as failures.
- Scoped deliberately to inference from what's on disk, per the spec — not
  the more thorough explicit in-scope/out-of-scope declaration from
  `design.md`/a manifest field, which is logged in `_frontend_test_script_exists()`'s
  own docstring as a real future enhancement requiring a Design Agent change.
- **Verified against two real local checkouts** (`forge-demo-apps-clone`,
  `--dry-run`, real `dotnet test`/`npm test`, real Claude write-up call — no
  GitHub/ADO calls in dry-run mode):
  - `DRYRUN-2026-01` (backend-only): frontend → `not_applicable`, backend →
    3/3 real pass, `qa-approved` on attempt 1 of 3 — not `qa-loop-back`
    against a phantom frontend failure.
  - `REQ-2026-01` (both suites in scope, re-verified for regression): backend
    62/62 pass, frontend 6 genuine failures correctly detected and bugs
    computed, `qa-loop-back` on attempt 1 of 3 — confirms `not_applicable`
    logic doesn't fire when a suite is actually in scope, and doesn't change
    behavior for a suite that's in scope and genuinely failing.
- Committed separately: `0560b39`.

**Not done this session, per the spec's own scoping:** `FORGE-context_v42.md`
is intentionally not updated here — that's the Claude.ai chat's job at the
close of this mini-cycle, per the standing two-tool convention. Also not
done: deciding the `enforce_admins` question above, and a root-cause (not
just non-reproduction) diagnosis of REQ-2026-01's original "QA backend TRX
report failure."

---

### PR #11 merge (Fix 2 cleanup, 2026-08-11 follow-up session)

Single-purpose follow-up to the Phase 5 pre-flight fixes session above:
merge PR #11 (the `design/*` `security-check` no-op workflow) into `main` on
`forge-demo-apps`. No Phase 5 work started in this session.

- **Re-verified before merging, not assumed unchanged:** pulled the live PR
  #11 diff and byte-diffed it against the exact file content verified last
  session — identical, no drift (trigger filter, in-job branch-prefix guard,
  and the check-run summary text distinguishing this from a real Security
  Agent pass were all still intact).
- **Confirmed the throwaway verification PRs were actually cleaned up**:
  both PR #12 (the first, mis-based attempt) and PR #13 (the one that
  actually verified the fix) show `state: closed`; branch
  `design/fix2-smoketest` returns 404 (deleted). No leftover test artifacts.
- **Merged PR #11** — merge commit
  `2e00e3f3c3dbda2723349b8127233bb473eddc9c`. Required an admin-privilege
  merge (`gh pr merge --admin`): PR #11's own head branch
  (`fix/design-pr-security-noop`) is not itself `design/*`, so the new
  workflow's own job-level guard correctly skipped on this PR and never
  produced a `security-check` run for it — a one-time bootstrapping
  limitation of this specific fix (it can't satisfy its own required check
  on the branch that introduces it), not a bypass of the review/scan
  requirement it exists to enforce for `design/*` PRs going forward. Zero
  reviews were also present at merge time. `enforce_admins: false` (see
  above) is what made the admin override possible at all.
- **Re-verified branch protection on `main` immediately after merge**, fresh
  `GET`, not trusted from any cached state: `required_status_checks.checks`
  = `[{"context":"security-check","app_id":4388813}]` (unchanged),
  `enforce_admins.enabled` = `false` (unchanged — expected and accepted per
  this session's brief, not something this session touched or was asked to
  touch), `allow_force_pushes`/`allow_deletions` both `false` (unchanged).
  Nothing changed as a side effect of the merge itself.
- Confirmed `.github/workflows/design-pr-security-noop.yml` is now present
  on `main` (blob sha `622d3bc3...`, matching the blob created when the file
  was first written to the fix branch — content didn't change in transit).
- **Not done, deliberately out of scope for this cleanup task:** the
  `enforce_admins` question flagged above is still Mike's open call, not
  decided or changed here.
- **Follow-up, same session:** merged branch `fix/design-pr-security-noop`
  (tip `148099a7...`, confirmed matching PR #11's merged head before
  deleting) removed via `DELETE /git/refs/heads/fix/design-pr-security-noop`
  at Mike's explicit request, confirmed gone via a follow-up 404 on the
  branch lookup.

---

### REQ-2026-02 (Phase 5, App 1) — Stage 3 completion-detection fix and a formal recovery tool (2026-08-11)

Session started as "monitor Phase 5 App 1 (Inactive User & License Auditor)
through the fully automated, label-triggered pipeline." Found on arrival that
Stages 0–2 had already run (issue `forge-template#5`: Intake questions
answered, `requirements.md`/`ado-work-items.json` committed, design PR
[#14](https://github.com/Flamespiker/forge-demo-apps/pull/14) merged,
`design-approved` applied) and Stage 3 had already **failed** — this section
covers diagnosing and fixing that failure, not the Stage 0–2 work itself.

**Root cause, confirmed live, not assumed:** the `03-implementation.yml` run
([31451985838](https://github.com/Flamespiker/forge-template/actions/runs/31451985838))
failed with `Coordinator session ... completed but did not produce
'implementation.tar.gz'`. A read-only poll of the session's own thread
statuses (`GET /sessions/{id}/threads`) showed it was NOT stuck —
`forge-coordinator`/`backend_agent`/`frontend_agent` were idle but
`test_writer_agent` was still genuinely `running`, well past the job's own
failure. The coordinator's top-level session status had gone `idle
(end_turn)` in **under half a second** after the initial message — reflecting
only the coordinator's first turn ending after kicking off delegation, not
real completion of the multi-agent work. Real completion (all four threads
idle, `implementation.tar.gz` produced) took **~37 minutes**
(`2026-08-11T02:19:08Z` → `T02:55:47Z`) — consistent with, not an outlier
against, REQ-2026-01's already-logged 38.5 min (dry run) / 55.2 min (real)
durations in `docs/FORGE-pipeline-cost-log.md`. Phase 5 pre-flight Fix 1's
~246s total wait budget (120s thread pre-check + 6-attempt/~126s archive
retry-backoff) was never going to be enough for a real run, and that was
visible from the cost log alone before Fix 1 shipped — flagged, not
re-litigated.

**Fix 1 (`core/agents/utils/managed_agents_wrapper.py`) — completion
detection and archive-retry are now two separate mechanisms, not one
conflated loop:**
- New `SessionStillRunningError(RuntimeError)` — carries `session_id`,
  `thread_statuses`, and (attached by `run_implementation_stage()`)
  `coordinator_id`/`environment_id`/`subagent_ids`. Raised when threads
  aren't all idle within the completion-wait ceiling. **Not a failure** — the
  session is left alive, not archived, specifically so it can be resumed by
  ID later.
- `_wait_for_subagent_threads_idle()` renamed to public
  `wait_for_all_threads_idle()` — the ONE real completion signal for the
  whole stage. Ceiling widened from 120s to `_COMPLETION_POLL_TIMEOUT`
  (default 5400s/90 min, overridable via
  `FORGE_IMPLEMENTATION_COMPLETION_TIMEOUT`), chosen with ~1.6x headroom over
  the largest real duration logged so far (55.2 min). Poll interval widened
  5s → 15s. Per-tick logging now only fires when thread statuses actually
  change (was logging every tick — noisy over a 90-minute ceiling).
- `_ARCHIVE_RETRY_ATTEMPTS` reduced 6 → 3 (2s/4s/8s, ~14s total) — it no
  longer does the real waiting (that regressed to premature-retry-as-backoff,
  which was the actual bug: a 400 from `archive` while a thread is genuinely
  still running isn't new information every retry). Now purely absorbs the
  separate, genuinely transient idle→running archive-call race from the
  Phase 2.9 build notes, on a session `wait_for_all_threads_idle()` has
  already confirmed idle.
- `archive_session()` no longer catches its own completion-wait step —
  `SessionStillRunningError` propagates untouched; the archive call is never
  reached on a still-running session.
- `run_implementation_stage()` restructured: `poll_until_idle()` (still just
  confirms the coordinator's own turn ended without a `session.error`) →
  `wait_for_all_threads_idle()` (the real gate) → audit trail fetched
  *before* archiving (unconfirmed whether an archived session's threads stay
  queryable — kept the original safer order) → `archive_session()`.
  `SessionStillRunningError` re-raised with the extra IDs attached and
  deliberately NOT archived; any other exception still gets a best-effort
  archive attempt so failures don't leak billed resources.
- New `get_session_resource_ids(session_id)` — derives `coordinator_id`
  (`agent.id`), `environment_id`, and `subagent_ids`
  (`agent.multiagent.agents[].id`) directly from `GET /sessions/{id}`,
  confirmed live to carry all three. Means a recovery tool needs only a
  session ID, not a dig through a GitHub Actions log for the
  `managed_agents_session_start` line. Also surfaces `usage` (token/cost) —
  confirmed live this closes the "not yet confirmed to return it" open item
  from chat 28 (see the pipeline cost log update below).
- `get_thread_statuses()` (was `_get_thread_statuses`) made public for the
  same reason.

**Fix 2 (`.github/workflows/03-implementation.yml`) — job `timeout-minutes`
raised 60 → 120.** Necessary, not optional: Fix 1's new completion-wait
ceiling is 90 minutes, but the GitHub Actions runner would have SIGKILLed the
whole job at the old 60-minute mark before the script's own graceful
still-running handling ever got a chance to run — the exact same
process-killed-out-from-under-a-live-session failure mode as the original
REQ-2026-01/DRYRUN-2026-01 incidents, just moved one layer up. 120 minutes
gives the 90-minute internal ceiling ~30 minutes of buffer for setup and the
commit/PR steps.

**Fix 3 (`core/agents/implementation_coordinator.py`) — formal recovery
tool, replacing the ad hoc uncommitted script pattern used for
DRYRUN-2026-01 and (initially, before being redirected mid-session) for this
same incident:**
- `run_implementation_coordinator()` now catches `SessionStillRunningError`
  distinctly from a real failure: posts a clearly-worded "still running, not
  failed, check back" comment to the tracking issue (session ID + live
  per-thread status, explicit instruction not to re-apply `design-approved`)
  instead of the generic failure comment, then re-raises. `main()` exits
  `75` for this case (vs. `1` for a real failure) — an arbitrary but
  documented convention so tooling can tell the two apart; the issue comment
  is the real human-facing signal.
- New `--recover-session SESSION_ID` CLI mode (`--request-id` still
  required): derives all resource IDs via `get_session_resource_ids()`,
  checks live thread status directly, and returns cleanly with no
  monorepo/GitHub mutation at all if anything is still busy — "not ready
  yet" is a normal, successful outcome here, not an error. If idle, sanity-
  checks the archive (`_sanity_check_extracted_files()` — below) before
  reusing the exact same commit/PR/comment logic the happy path uses
  (factored out to `_commit_and_open_pr()`, so there is exactly one copy of
  that logic, not two), then archives the session itself (left alive
  precisely so this recovery could reach it).
- New `.github/workflows/03b-recover-implementation.yml` —
  `workflow_dispatch` ONLY (session ID / issue number / request ID / dry-run
  as inputs), deliberately not automatic, scheduled, or polling. A human
  deciding "it's been long enough, let's check" is the intended amount of
  automation — auto-recovery would remove the one checkpoint that has
  already caught real issues in manual recoveries (see the two findings
  below).
- New `_sanity_check_extracted_files()`: rejects an archive under
  `_MIN_ARCHIVE_FILES`(3)/`_MIN_ARCHIVE_BYTES`(500), and — for each unit
  (`backend`/`frontend`) that `tasks.md` actually mentions — requires ≥2
  files under `services/<request-id>/<unit>/`. Deliberately does NOT
  hardcode "every request needs both units" (DRYRUN-2026-01 was legitimately
  backend-only); ties the check to what that request's own tasks.md called
  for. Verified against 4 constructed cases (realistic two-unit, legitimate
  backend-only, truncated-missing-frontend, degenerate single-file) — the
  two truncated cases both correctly raised.
- Wired into the happy path too (`run_implementation_coordinator()`), not
  just the recovery path.

**Two real, previously-latent issues the recovery process itself caught —
exactly what the sanity checks/format checks exist for, not hypothetical:**
1. **Cross-repo issue reference format.** `workflow_glue.py`'s
   `resolve_tracking_issue()` greps a PR body for `<source_repo>#N`; a bare
   `#5` (no `owner/` prefix) is what broke QA/Security's dispatch on the
   DRYRUN-2026-01 recovery. Checked before touching anything this time:
   `FORGE_GITHUB_OWNER=Flamespiker` is set, and `_commit_and_open_pr()`
   reuses the same qualified-format logic as the original happy path — PR
   #15's body confirmed to contain `Flamespiker/forge-template#5` before
   relying on it.
2. **Archive rooted at the wrong prefix — OPEN, unconfirmed root cause, guard
   reverted to strict.** REQ-2026-02's archive was tarred as `REQ-2026-02/...`,
   not the `services/REQ-2026-02/...` the coordinator's own system prompt
   asked for — `_extract_archive_to_file_dict()`'s existing prefix guard
   correctly rejected every member on the first dry run rather than silently
   committing to a wrong path. A remap fallback was added same-session to
   unblock the recovery, then **deliberately reverted the same day** once
   reviewed: it was a standing, general loosening of the guard for every
   future run (both the recovery path and the normal happy path), based on
   a single occurrence with no reproducibility test (n=1) and only a
   plausible-but-unverified hypothesis for why it happened (the system
   prompt's packaging command is a path relative to the coordinator's shell
   cwd at the time, which is never explicitly pinned to the sandbox root —
   plausible if the coordinator or a subagent `cd`'d into `services/` at
   some point before packaging, but not confirmed). `_extract_archive_to_file_dict()`
   is back to hard-failing on any prefix mismatch, for both callers.
   **Logged as an open item, not a closed finding — if this recurs, that's
   real evidence to act on with a proper fix, not a reason to bring the
   fallback back on a guess.**

**REQ-2026-02 recovered for real using the new tool** (not a synthetic
test — this was the live incident): dry run first (confirmed 69 files, all
correctly remapped and sanity-checked, back when the now-reverted fallback
was still in place) → real run → committed to `feature/REQ-2026-02` (69
files) → draft **PR [#15](https://github.com/Flamespiker/forge-demo-apps/pull/15)**
opened → comment posted to issue #5 → session + environment + coordinator +
all 3 subagents archived cleanly. QA and Security both fired automatically
via the existing `repository_dispatch` wiring the moment the PR opened (no
special-casing needed for a recovered PR) — **QA came back `qa-loop-back`
(real backend/frontend build/compile errors, attempt 1 of 3, unexamined —
separate app-code work for Mike)**, **Security initially came back
`security-approved`** with 0 Critical / 7 Medium (Semgrep flagging a mutable
GitHub Actions tag reference in the generated `backend-ci.yml`/`frontend-ci.yml`).

**CI workflow scope creep — OPEN, confirmed second occurrence of the same
coordinator behavior, not fixed at the root.** REQ-2026-01 already had this
exact issue (unrequested `services/REQ-2026-01/backend/.github/workflows/ci.yml`,
dead weight since GitHub only discovers workflows at the true repo root,
`git rm`'d before merge). Checked whether REQ-2026-02's two Semgrep-flagged
files were the same pattern: confirmed via `gh api .../pulls/15/files` —
both `services/REQ-2026-02/.github/workflows/{backend-ci.yml,frontend-ci.yml}`
were nested under the service directory, never discoverable by GitHub
Actions, and nothing in the coordinator's or any subagent's system prompt
asks for CI workflow files at all. **Two occurrences now — this is a real
recurring coordinator behavior pattern, not a one-off, though the
underlying cause (why the model keeps generating these unprompted) has
still never been diagnosed, only removed after the fact both times.**
Removed both files from PR #15 (`delete_files()`, new addition to
`github_helper.py` — no prior stage needed to delete a monorepo file
before this) and posted a PR comment making explicit that this is dead-code
cleanup, not a security fix: Security's 7 Medium findings against those two
files are moot as a side effect of the files being gone, not because they
were investigated or remediated in place. Confirmed, not assumed: the
deletion commit fired `notify-forge.yml`'s `synchronize` trigger, both
QA/Security re-ran automatically, and Security came back genuinely clean
(`✅ Clear`, `security-approved` re-applied).

**Side effect worth flagging: the cleanup commit also consumed one of QA's
3 retry attempts.** `qa_agent.py` counts attempts from prior PR comments,
so this synchronize-triggered re-run counted as "attempt 2 of 3" against
the exact same real backend/frontend build error the CI-file deletion had
nothing to do with — Mike now has one fewer real retry attempt on this PR
than if the cleanup had been deferred until after a real fix, or done in a
way that didn't re-trigger QA. Not reverted or worked around this session;
flagging so it's a known cost of the cleanup, not a surprise later.

**Real cost data pulled for REQ-2026-02 and logged in
`docs/FORGE-pipeline-cost-log.md`:** `GET /sessions/{id}`'s own `usage`
object carries `active_seconds` and `list_cost` — confirmed live (closing
the "not yet confirmed" item from chat 28) at 6,684,549 cache-read tokens,
138,996 output tokens, 2,218.4 active seconds, `list_cost.amount: "663"`
(units not cross-checked against the Console, read as ~$6.63).

**Resolved by the end of this session (follow-up to the initial report):**
- `design-approved` cleared from issue #5 (`gh issue edit ... --remove-label`)
  — it was left applied after the manual recovery since the workflow step
  that normally clears it never ran (the automated `03-implementation.yml`
  job had already failed before that point, and the recovery tool doesn't
  touch trigger labels). Confirmed via a follow-up label read: only
  `qa-loop-back`/`security-approved` remain.
- The archive-prefix auto-remap fallback was reverted to strict rejection
  (see above) — this was raised as "loosened general behavior on a guess,"
  Mike's call was to revert, done.
- The four completion-detection/recovery-tool commits, the revert commit,
  and the `delete_files()` commit were all pushed to `main` (see commit list
  below) — not left local-only.

**Still genuinely open, logged as open items rather than closed findings —
neither is fixed at the root:**
- **Archive-prefix deviation:** guard is strict again, but *why* the
  coordinator rooted the archive wrong on REQ-2026-02 is still just a
  hypothesis (system prompt's packaging command is cwd-relative, never
  pinned to the sandbox root) — not confirmed, not reproduced. If it
  recurs, that's the signal to actually investigate, not guess again.
- **CI workflow scope creep:** two occurrences now (REQ-2026-01,
  REQ-2026-02), both manually `git rm`/`delete_files()`'d after the fact.
  The coordinator/subagent system prompts still don't ask for CI files and
  nothing was changed in them this session to stop a third occurrence —
  this is a confirmed recurring pattern with no root-cause fix yet, only a
  cleanup response that's now been applied twice.
- `SessionStillRunningError`'s propagation through a *fresh*
  `run_implementation_stage()` call (as opposed to the recovery path, which
  calls `wait_for_all_threads_idle()`/`archive_session()` directly) was not
  exercised live — reproducing it deliberately would mean spending on a new
  real Stage 3 session just to hit the timing window. Reasoned through, not
  reproduced under load, same honesty standard the original Fix 1 held
  itself to.
- QA's `qa-loop-back` result on PR #15 (real backend/frontend build errors,
  now at attempt 2 of 3 after the CI-file-cleanup commit consumed one
  attempt) is unexamined — separate app-code work for Mike, out of scope
  for this session's own brief.

---

### PR #15 QA fix, deploy-trigger bug, and REQ-2026-02 staging deploy (same day, follow-up)

Mike merged PR #15 after QA/Security passed on attempt 3 of 3, then
reported the Deploy Agent hadn't triggered. Three genuinely separate real
bugs surfaced chasing that down to an actual live staging deploy — none
guessed, all reproduced directly.

**Bug 1 — `06-deploy.yml` never fires off an agent-applied label, only a
human-applied one. Confirmed, not assumed, via real run history.**
`06-deploy.yml` triggers on `issues: types: [labeled]`, gated on both
`qa-approved` and `security-approved` being present. Both are applied by
`qa_agent.py`/`security_agent.py` via `add_label()`, which used
`GITHUB_TOKEN`. GitHub Actions has a documented anti-recursion rule:
actions performed with the default `GITHUB_TOKEN` never trigger a NEW
workflow run (exempting only `workflow_dispatch`/`repository_dispatch`).
Checked `06-deploy.yml`'s full run history: the only successful run ever
was triggered by `qa-approved` being applied by `Flamespiker` (a human,
personal token) on DRYRUN-2026-01 — every agent-applied label, before and
after, produced zero deploy runs. **This silently affected every request
that passes QA/Security cleanly without a human touching a label in
between — not something specific to REQ-2026-02.** Every other stage
transition is either human-applied or uses `repository_dispatch`
(exempt); Stage 6 was the only one relying on an agent-applied label.

Fix: `add_label()` (`core/agents/utils/github_helper.py`) switched to the
GitHub App installation token. Confirmed no knock-on effects first:
`get_installation_token()`'s existing lookup (via `FORGE_TARGET_REPO`)
already resolves to the same installation id (`148876680`) for both
forge-template and forge-demo-apps — no change needed there.
`post_comment`/`get_issue`/`get_issue_comments`/`remove_label` stay on
`GITHUB_TOKEN` since none of them need to trigger a downstream
label-driven workflow. Also corrected a stale docstring on
`post_comment()` claiming the App wasn't installed on forge-template — it
has been since the Phase 4 step 4.8 retrofit. Smoke-tested against the
`forge-smoke-test` label on issue #1 before trusting it live, then used
for real: re-applied `qa-approved` on issue #5 (after first confirming
via a full grep of every workflow that nothing listens for `unlabeled`
events, and that `qa_agent.py`'s retry counter is comment-based, not
label-based, so the toggle was safe) — `06-deploy.yml` fired for real
this time. Committed separately (`9f54135`).

**Bug 2 — frontend `package-lock.json` was generated with the wrong
npm/Node version.** The resulting real deploy run built the backend image
fine, then failed on the frontend's `npm ci` inside the Dockerfile.
First attempts to pull the real error out of the Actions log kept
surfacing only npm's generic `ci` usage/help trailer, not the actual
reason — traced to a genuinely truncated/lost log line, resolved by
reproducing directly: `npm ci` succeeds fine against this repo's
`package.json`/`package-lock.json` pair locally (npm 11.6.2/Node 24.11.1)
but fails inside the actual `node:20-alpine` deploy image (npm 10.8.2)
with `Missing: @emnapi/core@1.11.3` / `Missing: @emnapi/runtime@1.11.3
from lock file` — npm 10 and 11 resolve platform-conditional optional
dependencies differently, and `npm ci` is strict about exact sync.
Root-caused because the Jest rewrite's lockfile had only ever been
regenerated/tested locally, never inside the actual deploy target.

Fix: regenerated `package-lock.json` by running `npm install` *inside* a
real `node:20-alpine` container (not locally), extracted it via `docker
cp`, and verified `npm ci` now succeeds both inside that same image and
locally. Full Jest suite re-confirmed 44/44 passing, `next build`/`next
lint` both clean, against the regenerated lockfile.

**Bug 3 — missing `public/` directory breaks the Dockerfile's final
stage.** Even past Bug 2, `COPY --from=builder /app/public ./public`
failed with `"/app/public": not found` — this app has no static assets
and therefore no `public/` directory at all; Git doesn't track empty
directories, so nothing ever created one. Fixed with
`public/.gitkeep`. Verified the complete multi-stage Dockerfile (`deps`
→ `builder` → `runner`) now builds end-to-end with zero errors.

**Non-bug, worth recording so it doesn't get re-investigated:** partway
through verifying Bug 2's fix, a `next build` run threw `Cannot read
properties of null (reading 'useContext')` across every page including
Next's own internal `/404`/`/500` — looked like a real regression at
first. Root cause: a Windows path-casing artifact specific to this local
machine (the real folder is `C:\Users\mikef\Projects\...`, capital P, but
builds were being invoked via git-bash's lowercase `/c/Users/mikef/projects/...`
mount, so webpack saw two differently-cased copies of the same module and
crashed). Confirmed by building the identical code from an unambiguous
path — clean pass. Cannot occur on the real Linux CI runners; no code
change needed or made for it.

**Also encountered and resolved, infrastructure not code:** Docker
Desktop was found hung (daemon unresponsive to `docker version` even
after 20s+ timeouts, despite all `Docker Desktop`/`com.docker.*`
processes showing `Responding: True` in `Get-Process`) partway through
reproducing Bug 2. Killed all Docker-related processes and relaunched
`Docker Desktop.exe`; daemon came back responsive (server 24.0.7) within
~30s. Not a code issue, just a local-machine note in case it recurs.

**Delivery, since `feature/REQ-2026-02` no longer exists** (PR #15's
branch was deleted on merge, confirmed via a 404 on the branch lookup —
so Bugs 2/3's fixes couldn't just be pushed to the old branch): opened a
new, small, separate PR **[#16](https://github.com/Flamespiker/forge-demo-apps/pull/16)**
off `main` (same "mechanical fix, agent doesn't merge its own PR" pattern
as PRs #7/#8/#11) containing only the lockfile regen and `public/.gitkeep`
— no application/business logic touched. **Left open, unmerged** (per
ADR-0009). Since Deploy Agent's own design already tolerates deploying an
unmerged commit SHA, `deploy_agent.py` was invoked manually against PR
#16's head commit (`77aac8a`) to actually unblock staging now rather than
wait on a merge — same "manual invocation satisfies the requirement"
pattern already used for QA/Security's own real runs earlier in this
project.

**Real (non-dry-run) deploy verified live, both units, both confirmed
actually serving traffic (not just CLI-reported success):**
- `req-2026-02-auditor-api` (backend): `https://req-2026-02-auditor-api.yellowmeadow-894377a9.canadacentral.azurecontainerapps.io/api/health`
  → HTTP 200, `{"status":"healthy"}`.
- `req-2026-02-frontend` (frontend): `https://req-2026-02-frontend.yellowmeadow-894377a9.canadacentral.azurecontainerapps.io/`
  → HTTP 200. **First time this project's frontend deploy path has been
  verified end-to-end** — REQ-2026-01's frontend was parked (unrelated
  app-insights dependency issue) and never actually deployed.
- Deploy comment posted to PR #16. No label applied (Document 6 has no
  deploy-stage label, unchanged from prior deploys).

**Not done this session, flagged rather than resolved:**
- PR #16 is unmerged — Mike's call whether/when to merge it. Since its
  head branch isn't `feature/*` or `design/*`, `notify-forge.yml` won't
  dispatch QA/Security for it, so the `security-check` required status
  check will be permanently unsatisfiable on this PR the same way it was
  for `design/*` PRs before Fix 2 — merging it will need the same kind of
  admin override PR #11 needed (`enforce_admins` is still `false`, so
  that path is open), or a deliberate decision about how to handle
  non-`feature/*`/`design/*` fix PRs generally. Not designed or built.
- The two deploy bugs (lockfile npm-version mismatch, missing `public/`)
  were never caught earlier because this project's frontend Docker deploy
  path had never been exercised end-to-end before now for ANY request —
  REQ-2026-01's frontend was parked. Worth considering whether Deploy
  Agent (or CI generally) should build the frontend Docker image earlier
  in the pipeline (e.g. at PR-open time) so a `npm ci`/lockfile issue
  surfaces before Stage 6, not after everything else has already passed.
  Flagged, not designed.

---

### R-001 descope to a license-status report (REQ-2026-02, follow-up session)

Root cause confirmed live (not guessed): a Dataverse metadata investigation
against `EntityDefinitions(LogicalName='systemuser')/Attributes` found no
field matching login/logon/signin/last-activity anywhere among `systemuser`'s
221 attributes in this environment. R-001's original "inactive user" audit
scope was formally descoped by Mike as a result — `GET /api/users/inactive`
became `GET /api/users/license-status`, a license-status report only (no
login timestamps, no inactivity filter). Backend DTOs/service/repository
renamed to match (`LicensedUserDto`, `LicenseStatusResponseDto`,
`LicenseStatusService`/`ILicenseStatusService`); frontend columns/CSV/copy
updated so the UI doesn't imply data it no longer has;
`AppConstants.INACTIVITY_THRESHOLD_DAYS` removed. `openapi.yaml` and both
READMEs updated to match. Real backend tests 49/49, frontend tests 38/38,
`next build`/`next lint` clean before opening a PR. Where real login-activity
data could come from (Graph/Entra sign-in activity, a custom Dataverse
field, or Dataverse audit history) is an open question, not resolved here —
logged as exactly that, an open question, not a TODO with an assumed answer.

**A genuinely new pipeline bug found and root-caused during this work**
(not present in any prior session's notes): the first attempt used branch
name `feature/REQ-2026-02-license-status-fix`. `04-qa.yml`/`05-security.yml`
derive `request_id="${HEAD_REF#feature/}"` — a bash prefix-strip that
assumes the branch is exactly `feature/<request-id>`, nothing more. Stripping
`feature/` left `REQ-2026-02-license-status-fix`, not `REQ-2026-02`, so both
agents looked for a nonexistent `services/REQ-2026-02-license-status-fix/`.
Security crashed loudly (`FileNotFoundError`); QA got a **silent false
positive** — found nothing at the wrong path, correctly-but-wrongly treated
everything as `not_applicable` (Phase 5 Fix 3's own logic, working exactly
as designed, just fed a wrong path), and applied `qa-approved` on zero real
test coverage. Fixed by renaming the branch to the conforming
`feature/REQ-2026-02` (not by touching pipeline code) — re-run confirmed
real coverage (87/87 tests) and a genuine Security pass. The false
`qa-approved` label from the broken run was removed from tracking issue #5
before re-running. **Not fixed at the root**: `04-qa.yml`/`05-security.yml`'s
`request_id` derivation is still a bare prefix-strip with no validation that
the result matches a real `services/<request_id>/` directory — a
differently-named `feature/*` branch would silently reproduce this exact
QA false-positive again. Flagged, not built.

**A second, separate pipeline gap found while watching Deploy auto-fire**:
when the (corrected) `qa-approved` label landed via the App token, `06-deploy.yml`
fired automatically as designed — but `workflow_glue.py`'s
`resolve_feature_pr()` finds "the feature PR" by reading the *original
Implementation Coordinator's comment* on the tracking issue, which still
pointed at PR #15 (the original Stage 3 implementation PR, merged days
earlier). It has no notion of "the current open feature PR for this
request" — so the automatic deploy tried to rebuild PR #15's old,
pre-descope commit, not the new fix. This is a structural gap for any
follow-up feature PR on a request that's already been through
Implementation once, not specific to this fix. Worked around the same way
PR #16 was handled: `deploy_agent.py` invoked manually against PR #18's real
merge commit (`9e4054c`, then `d8823cf` after PR #16 also merged — see
below). Not fixed at the root — `resolve_feature_pr()`'s comment-anchored
lookup is unchanged.

**PR #16 (frontend deploy fix, open since the prior session) admin-merged
this session, at Mike's explicit request**, once it became the direct
blocker for the above manual deploy: `deploy_agent.py`'s build-then-deploy
loop (`deploy_agent.py:590-626` — builds+pushes **every** unit first, *then*
runs `az containerapp create/update` for every unit in a separate pass) means
a single unit's build failure aborts before ANY unit's Container App gets
touched, even ones that built fine. So PR #18's backend image built and
pushed to ACR cleanly, but the frontend build failed on the exact bug PR #16
fixes, and the whole run aborted before the backend's Container App was
ever updated — the real fix was pushed to the registry but never actually
went live until PR #16 merged and the deploy was re-run. Confirmed before
merging: PR #16 was 3 purely mechanical files (regenerated
`package-lock.json`, `public/.gitkeep`, the previously-only-auto-generated
backend `Dockerfile`), no application logic. `gh pr merge --admin` used
(same as PR #11) since PR #16's branch (`fix/req-2026-02-frontend-deploy`)
hit the identical two-part block PR #18 hit initially: no review
(`reviewDecision: REVIEW_REQUIRED`) plus a `security-check` that can never
populate on a non-`feature/*`/non-`design/*` branch.

**Standing item, explicitly logged per Mike's request rather than fixed —
do not lose this count before it's actually decided:** PR #16 admin-merging
is the **fourth** occurrence of this exact pattern — an ad hoc `fix/*`
branch for a small mechanical fix, hitting the permanently-unsatisfiable
`security-check` (because `notify-forge.yml` only dispatches for
`feature/*`/`design/*` branches) plus no human review, resolved by admin
override each time:
1. PR #7 — `fix/req-2026-01-test-infra`
2. PR #8 — `fix/req-2026-01-navigation-aria-types`
3. PR #11 — `fix/design-pr-security-noop`
4. PR #16 — `fix/req-2026-02-frontend-deploy`

Fix 2 (the `design-pr-security-noop.yml` no-op check) already solved this
exact class of problem for `design/*` branches specifically. It was never
generalized to cover ad hoc `fix/*` branches, and four occurrences in is
long enough that this is a real recurring cost (an admin override every
time), not a one-off. Options for whenever this gets decided: extend the
no-op-check pattern to any branch prefix used for these mechanical fixes,
adopt a fixed naming convention for them that's already covered by an
existing dispatch filter, or accept admin-merge as the standing procedure
and stop treating it as a gap. Not decided here — logged only so the count
is not lost.

**Two more real, previously-undiscovered `deploy_agent.py` bugs found while
verifying the live REQ-2026-02 frontend after this deploy — both patched as
one-off, throwaway fixes on the running Azure resources only, `deploy_agent.py`
itself untouched, so both will reproduce on the next real deploy of any
request's frontend unit:**

1. **`NEXT_PUBLIC_API_BASE_URL` is never passed as a Docker build-arg, for
   any unit, on any request.** The frontend Dockerfile declares `ARG
   NEXT_PUBLIC_API_BASE_URL=""` (empty default); `_docker_build()`
   (`deploy_agent.py:345-352`) runs a bare `docker build -f ... -t ... <context>`
   with no `--build-arg` anywhere in the file (confirmed:
   `grep -n "NEXT_PUBLIC_API_BASE_URL\|build-arg" deploy_agent.py` returns
   nothing). Next.js bakes `NEXT_PUBLIC_*` vars in at build time, so every
   deployed frontend build has always shipped with an empty base URL — the
   client's `fetch()` calls resolve to a same-origin relative path against
   the frontend container itself, which has no such route, so Next.js's own
   404 HTML page comes back instead of JSON. `apiClient.ts`'s JSON-parse
   fallback then surfaces a generic "An unexpected error occurred" — a
   real, silent, 100%-of-the-time failure that nothing in this project's
   prior verification ever caught, because every past frontend check only
   confirmed `/` returns 200, never that the actual data fetch succeeds.
   **Not just a missing line, either**: `run_deploy_agent()` builds+pushes
   *all* units in one loop (`deploy_agent.py:590-594`) before creating/
   updating *any* Container App in a second loop (`:600-626`), so the
   backend's real FQDN doesn't exist yet at the point the frontend image
   would need it as a build-arg on a brand-new deploy. A real fix needs
   either a build-order change (backend first, discover FQDN, then build
   frontend) or a predictable FQDN computed from the environment's fixed
   domain suffix + the unit's deterministic name — plausible (Container
   Apps FQDNs are `<app-name>.<env-suffix>.<region>.azurecontainerapps.io`,
   and the suffix/region are fixed per environment) but unconfirmed, not
   designed.
2. **`FRONTEND_ORIGIN` is never set on any backend Container App either** —
   confirmed via `az containerapp show ... properties.template.containers[0].env`
   on the live `req-2026-02-auditor-api`: no `FRONTEND_ORIGIN` entry at all.
   `Program.cs` defaults it to `http://localhost:3000` when unset, so the
   CORS policy only ever allows `localhost` — a real deployed frontend
   origin gets no `Access-Control-Allow-Origin` header back at all
   (confirmed by curling the backend with `-H "Origin: <real frontend
   URL>"` and finding the header absent). Even with bug 1 fixed, a real
   browser's cross-origin fetch would still be CORS-blocked, surfacing a
   *different* generic error ("Unable to reach the Auditor API — check
   your network connection and try again.", the `NETWORK_ERROR` branch)
   rather than the JSON-parse-fallback one. `deploy_agent.py` never sets
   this env var for any unit on any request either.

**Manual patch applied to unblock REQ-2026-02 specifically** (per Mike's
explicit direction, `deploy_agent.py` deliberately not touched):
`docker build --build-arg NEXT_PUBLIC_API_BASE_URL=<real backend FQDN>` →
new tag `d8823cf...-fix-buildarg` → pushed to ACR → `az containerapp update
--image` on `req-2026-02-frontend`; `az containerapp update --set-env-vars
FRONTEND_ORIGIN=<real frontend FQDN>` on `req-2026-02-auditor-api`. Verified
both empirically (not assumed): the deployed JS bundle now shows the real
backend URL concatenated before `/api/users/license-status`; the backend's
CORS response now echoes the exact frontend origin back in
`Access-Control-Allow-Origin`; **Mike confirmed live in a real browser** —
page loads real data, no error banner. Neither fix touched application
source or `deploy_agent.py` — both are Azure-resource-only patches specific
to this one running app, and will need to be reapplied (or `deploy_agent.py`
fixed at the root) the next time this app is redeployed from scratch, or
for any other request's frontend unit.

**Follow-up the same session: the "unconfirmed" caveat on bugs 1/2's fix
shape is now resolved — confirmed empirically, not assumed.** `az
containerapp env list --resource-group forge-build-rg --query
"[].{name:name, defaultDomain:properties.defaultDomain}"` returns
`defaultDomain` at the **environment** level (`forge-staging` →
`yellowmeadow-894377a9.canadacentral.azurecontainerapps.io`, matching
exactly what both REQ-2026-02 units' real FQDNs have been built from all
along). This means a unit's FQDN (`f"{unit.name}.{env_domain}"`) is fully
predictable **before that unit's Container App exists** — there is no
chicken-and-egg ordering problem after all. Bug 1 (missing
`NEXT_PUBLIC_API_BASE_URL` build-arg) and bug 2 (missing `FRONTEND_ORIGIN`)
both have a concrete, verified fix shape now, not just a flagged gap:

1. **Missing `NEXT_PUBLIC_API_BASE_URL` build-arg** (`_docker_build()`,
   `deploy_agent.py:345-352`) — before building a frontend unit, compute the
   backend unit's expected FQDN via one `az containerapp env show --query
   properties.defaultDomain` call (done once per run) + the backend unit's
   already-deterministic name, pass it via `--build-arg`.
2. **Missing `FRONTEND_ORIGIN`** (`_build_containerapp_command()`,
   `deploy_agent.py:403-438`) — same predictable-FQDN trick in reverse: add
   `--set-env-vars FRONTEND_ORIGIN=https://{frontend_fqdn}` to the backend
   unit's create/update command.
3. **Batched build-then-deploy** (`run_deploy_agent()`,
   `deploy_agent.py:590-626`) — builds+pushes *every* unit before running
   `az containerapp create/update` for *any* unit, so one unit's build
   failure blocks even a successfully-built unit's deploy (this is exactly
   what happened to REQ-2026-02's backend earlier this session). Not
   strictly required to fix 1/2 now that FQDNs are predictable without
   needing creation order, but a separate, real robustness gap — fix shape:
   interleave build+push+deploy per unit in one loop instead of two batched
   passes.
4. **`resolve_feature_pr()` anchored to the original Implementation
   Coordinator comment** (`workflow_glue.py`, used by `06-deploy.yml`) —
   different file/mechanism from 1-3, can't discover a newer follow-up
   feature PR for a request that's already been through Implementation
   once (caused the auto-deploy-on-`qa-approved` trigger to target stale
   PR #15 instead of PR #18 earlier this session). No verified fix shape
   yet — not investigated as deeply as 1-3.

**Explicit decision, Mike's call: not implemented this session.** All four
gaps are logged here as confirmed findings (1-3 with a verified fix shape,
4 without yet) specifically so they're ready to pick up in a dedicated
pre-Phase-6 session, rather than folded into whatever unrelated work
surfaces them next.

---

### Phase 5 close-out and REQ-2026-02 decommission (2026-08-13)

Phase 5 close-out doc written (`FORGE-Phase5-Closeout.md`) from records
already in the context doc — no new screenshots/data pulled first, per
Mike's call. REQ-2026-02's live Azure/D365 resources then decommissioned in
the same session, with two deliberate deviations from the original teardown
plan: the D365 Application User was disabled but not deleted (Dataverse
rejected the delete even post-disable; left as-is — disabled is sufficient
to close the security exposure); the app registration was kept for
potential future reuse, only its client secret deleted.
`req-2026-02-auditor-api`/`req-2026-02-frontend` Container Apps deleted from
`forge-staging`. `dryrun-2026-01-backend`/`dryrun-2026-01-frontend` and PR
#10 were both confirmed already gone/closed from an earlier undocumented
session — crossed off, not re-investigated. ACR images for both apps left
in place (low-priority). See context doc chat 44 entry and
`FORGE_Build_Plan_v8.md` for the checklist-level record.

---

### Deploy Agent cross-service wiring fixes (per `docs/FORGE-DeployAgent-CrossService-Wiring-Spec.md`)

Three fixes implemented against `core/agents/deploy_agent.py`, each verified
and committed separately per the spec's own convention. Line numbers below
are post-drift, confirmed against the real file at the time each fix
landed, not the spec's own (stale) estimates.

**Fix 1 — `NEXT_PUBLIC_API_BASE_URL` build-arg.** New `_get_env_default_domain()`
(next to `_get_fqdn()`) runs `az containerapp env show ... --query
properties.defaultDomain`, raising rather than returning empty/None on
failure. `_docker_build()` gained an optional `build_args` dict, appending
`--build-arg KEY=VALUE` pairs. `run_deploy_agent()` computes the backend
"web" unit's FQDN once (from the environment's `defaultDomain` + the unit's
deterministic name — confirmed no chicken-and-egg problem, matching the
spec's own verified premise) and passes it only when building the frontend
unit; a frontend with no "web" backend unit in the request logs a warning
and skips the build-arg rather than guessing. Confirmed live:
`az containerapp env show --resource-group forge-build-rg --name
forge-staging` returned `yellowmeadow-894377a9.canadacentral.azurecontainerapps.io`,
matching the spec's assumption exactly. Verified with a local (no ACR push,
no live Container App touch) build of REQ-2026-02's real frontend via the
actual `_docker_build()` function, both with and without the fix's
`build_args` — grep for the backend FQDN inside `/app/.next` found it in
both the server and client-chunk bundles only in the with-build-arg case
(exit 0 vs. exit 1 on the negative control), confirming the fix's effect
empirically rather than by code inspection alone. Committed `2bd8679`.

**Fix 2 — `FRONTEND_ORIGIN` on the backend Container App.**
`_build_containerapp_command()` gained `extra_env_vars: dict[str, str] |
None`, building one merged `--set-env-vars KEY=VALUE ...` flag (confirmed
first that no other `--set-env-vars` usage existed anywhere in the function
to clobber — there wasn't one). `run_deploy_agent()` reuses Fix 1's already-
cached `env_default_domain` to derive the frontend unit's FQDN too (no
second `az` call), passing it as `FRONTEND_ORIGIN` only to the backend
"web" unit's create/update command. Verified locally (no live `az` calls)
by calling `_build_containerapp_command()` directly for all four
create/update × with/without-`extra_env_vars` combinations — confirmed
exact expected command shape each time. Committed `3acab2c`.

**Fix 3 — interleaved per-unit build+push+deploy.** `run_deploy_agent()`'s
two batched passes (build-all-then-deploy-all) merged into one loop with a
per-unit `try/except` — a failure on one unit's build/push/deploy no longer
blocks a different unit that would otherwise succeed. `DeployResult` gained
an `error: str | None` field (and `action`/`image` defaults, since a unit
that fails during its own docker build never reaches the point of having a
containerapp command built at all). `_build_pr_comment()`'s existing
per-unit table now renders a `❌ **failed** — <first line of error>` status
cell for failed units instead of a staging URL, plus a summary line
("N of M unit(s) failed to deploy") when any exist.

**Design fork surfaced, not resolved silently, per the spec's own
instruction:** the spec's acceptance criteria only required that (a) other
units still succeed and (b) the failure is reported against only the
broken unit — it didn't specify what should happen to the run's own
success/failure signal (CI exit code, tracking-issue comment) on a
*partial* failure. There was no existing partial-failure reporting
precedent anywhere in this agent to "match" (confirmed by reading the
whole file first: before this fix, ANY exception anywhere aborted the
entire function immediately, and the only failure surface was one generic
comment on the FORGE tracking issue — the PR comment was never even
reached on failure). Resolved by: still posting the (partial) PR comment
via the existing `post_pr_comment()` on ANY outcome (all successes now
visible even if a sibling unit failed, which is strictly more information
than before, not less), and — if any unit failed — additionally posting a
second, distinct summary comment to the tracking issue via the existing
`post_comment()`, then raising so the job still exits non-zero. This
preserves the pre-existing "CI reflects real problems" guarantee while
adding the new partial-success visibility Fix 3 asks for. The dry-run path
mirrors this (raises on partial failure too, but posts nothing, per the
existing dry-run convention of posting nothing at all).

**Verified via local simulation, not a live multi-unit deploy** (mocking
every function that would touch Docker/Azure/GitHub, feeding one unit a
forced `_docker_build` failure): confirmed the failing unit's error landed
in `results` without preventing the second unit from reaching a fully-built
`az containerapp create` command (including its correct
`NEXT_PUBLIC_API_BASE_URL` build-arg, itself computed from the backend
unit's *name* rather than its actual success — confirming Fix 1/2's
FQDN-prediction mechanism is independent of unit processing order or
success, exactly as the spec's point 3 asked to confirm explicitly rather
than assume); confirmed the resulting PR-comment markdown correctly showed
one failure row, one internal-no-ingress row, and the "1 of 2 failed"
summary line; confirmed the function raised
`RuntimeError("Deploy Agent dry-run: 1 of 2 unit(s) failed: ...")` as
designed. Not verified: a real multi-unit live deploy with a genuine build
failure — this session did not push to ACR or touch any live Container App
for Fix 3 (per the same "confirm before touching forge-staging" convention
already established for Fix 1).

**Incident during this session's Fix 3 verification, caught and cleaned up
immediately — logged because this project's whole process is built around
catching exactly this failure mode:** the first version of the local
simulation script mocked every higher-level function
(`_docker_build`/`_docker_push`/`_containerapp_exists`/`_get_fqdn`/
`post_pr_comment`/`post_comment`) but never mocked `_run_shell()` itself,
and was run with `dry_run=False`. That combination let a **real**
`az containerapp create` execute against the live `forge-build-rg`/
`forge-staging` environment, using fake image/registry data. Caught
immediately via `az containerapp show --name req-sim-frontend
--resource-group forge-build-rg`, which showed a real Container App
resource with `provisioningState: "Failed"` (image never resolved — no
real container ever ran, no traffic, nothing pulled). Deleted via `az
containerapp delete`, confirmed gone via a follow-up `az containerapp show`
(`ResourceNotFound`) **and** `az containerapp list --resource-group
forge-build-rg` (only the two legitimate REQ-2026-01 apps remained) — not
trusted from the delete command's own exit code alone, per Mike's explicit
instruction. No live impact beyond the stray inert resource itself. Fixed
the simulation script before re-running: `_run_shell` is now hard-mocked to
raise `AssertionError` if ever actually called (a safety net independent of
whether every higher-level function happens to be mocked), and the script
defaults to `dry_run=True` unless deliberately overridden. Re-ran
successfully with zero live calls reached.

**Real end-to-end verification against `forge-staging`, per the spec's own
acceptance criteria — a genuinely live deploy, not a mocked/local test.**
Ran `python -m core.agents.deploy_agent` for real (no `--dry-run`) against
REQ-2026-02's actual code in `forge-demo-apps-clone` (`main` @ `d8823cff`,
confirmed matching `origin/main`), targeting `forge-demo-apps` PR #18 and
FORGE tracking issue #5.

**First attempt surfaced a real bug, exactly because this was the first
genuinely live `create` call any of these three fixes had ever gone
through:** `az containerapp create` takes `--env-vars`; `--set-env-vars`
(what `_build_containerapp_command()` used for both branches) is
`update`-only and errors with "unrecognized arguments" — confirmed via
`az containerapp create --help`/`update --help`. Neither Fix 2's own
verification (checked the Python-level command list only) nor Fix 3's
mocked simulation (deliberately hard-mocks `_run_shell` so nothing real
ever runs) could have caught this — both were scoped that way on purpose,
to avoid touching `forge-staging` before this dedicated step. The backend
create failed at CLI arg-parsing, before reaching Azure — confirmed via
`az containerapp show` (`ResourceNotFound`), so no partial/broken resource
was left behind by the failed attempt itself. Fixed
(`_build_containerapp_command()` now uses `--env-vars` for `create`,
`--set-env-vars` for `update`) and, same commit, widened
`_build_pr_comment()`'s error snippet from the first line only (usually
just `"...failed for unit X:"`, no real detail) to the first three
non-empty lines — the real failure above would otherwise have shown no
useful error text in the PR comment at all. Committed `e0986d0`.

**Re-run after the fix: both units deployed clean.** `provisioningState:
Succeeded` for both `req-2026-02-auditor-api` and `req-2026-02-frontend`,
FQDNs matching the predicted pattern exactly (this run also exercised the
`update` path for the frontend, since its first-attempt `create` had
already succeeded — confirms `--set-env-vars` is correct there, unchanged).

- **Fix 1, confirmed against the live-served bundle, not a local build:**
  `curl`'d the running frontend's actual JS chunk
  (`/_next/static/chunks/app/page-05411a420c1e92a5.js`) and found the real
  backend FQDN baked in.
- **Fix 2, confirmed against the live resource and live HTTP behavior:**
  `az containerapp show ... properties.template.containers[0].env` shows
  `FRONTEND_ORIGIN` set to the real frontend FQDN; `curl -H "Origin:
  <real frontend FQDN>"` against the backend gets back
  `access-control-allow-origin: <that exact origin>`.
- **Fix 3, confirmed in two real scenarios, not one:** the first (failing)
  attempt showed the backend's error isolated from the frontend's success
  in both the PR comment (per-unit table + "1 of 2 failed" summary) and a
  distinct tracking-issue comment, while the frontend still deployed for
  real; the second (clean) attempt shows both units' real staging URLs
  with the failure-summary line correctly absent. `git diff` between the
  Fix 3 commit and the `e0986d0` bug-fix commit confirms the per-unit
  `try/except` loop itself was untouched by the bug fix — only the CLI
  flag and error-snippet formatting changed — so the live partial-failure
  behavior observed on the first attempt is the same loop running on the
  second.

**Non-issue, confirmed via container logs, not assumed:** the real
`/api/users/license-status` endpoint returned HTTP 500
(`System.InvalidOperationException: Missing required configuration:
D365_TENANT_ID`, from `az containerapp logs show`). Expected — REQ-2026-02's
D365/Dataverse connection was deliberately decommissioned in the Phase 5
close-out (App User disabled, client secret deleted), and
`deploy_agent.py` has never wired D365 application config for any
request (out of scope for this agent). Unrelated to Fix 1/2/3.

**Cleanup, per Mike's explicit direction:** both Container Apps were
deleted after verification (`az containerapp delete`, both) to restore the
decommissioned state from the Phase 5 close-out, rather than leaving them
live. Confirmed actually gone via **both** a follow-up `az containerapp
show` (`ResourceNotFound` for each) **and** `az containerapp list
--resource-group forge-build-rg` (only the two legitimate REQ-2026-01
apps remained) — not trusted from the delete commands' exit codes alone.
ACR images pushed during this verification
(`req-2026-02-auditor-api:d8823cff...`, `req-2026-02-frontend:d8823cff...`)
were left in place, consistent with the existing "ACR images left in
place, low-priority" convention from the original Phase 5 decommission.

---

### `request_id` derivation & `resolve_feature_pr()` staleness fixes (per `docs/FORGE-RequestId-FeaturePR-Resolution-Spec.md`)

Two independent structural bugs, confirmed unrelated (different files,
mechanisms, and consumers — see the spec's own investigation section),
fixed per spec. Both pre-flight-verified against live file content before
editing; line numbers in the spec were descriptive, not authoritative, and
matched the live files as found.

**Fix 1 — `request_id` derivation (`04-qa.yml`, `05-security.yml`).** Both
workflows previously derived `request_id` via a bare bash prefix-strip
(`request_id="${HEAD_REF#feature/}"`), with no validation that the result
named a real `services/<request_id>/` directory — confirmed live as the
root cause of the exact silent-false-positive class already seen once (the
REQ-2026-02 `feature/REQ-2026-02-license-status-fix` incident: wrong
`request_id` → both suites `not_applicable` → `qa-approved` applied with
zero real test coverage). Fixed by adding a new "Resolve request id" step
to both workflows, immediately after "Resolve tracking issue number",
calling the already-existing, already-proven `resolve-request-id` glue
subcommand (marker-based, same mechanism every stage from
`01-requirements.yml` onward already trusts) instead of re-parsing
`HEAD_REF`. Both workflows' two remaining `HEAD_REF`-derived
`request_id` usages (frontend dependency install in `04-qa.yml`; the QA/
Security Agent invocation in both files) now read
`${{ steps.request_id.outputs.request_id }}`. `HEAD_REF` itself left in
the env block unchanged — no other consumer, no reason to remove it.
No changes needed to `workflow_glue.py`, `qa_agent.py`, or
`security_agent.py` for this fix — `resolve-request-id` already existed
and already did the right thing.

**Verified live, read-only, no mutation:** ran
`python -m core.agents.workflow_glue resolve-request-id --issue-number 5`
directly against the real tracking issue for REQ-2026-02 — returned
`request_id=REQ-2026-02`, confirming the subcommand this fix now relies on
resolves correctly against real issue history.

**Fix 2 — `resolve_feature_pr()` staleness (`workflow_glue.py`).** The
function previously scanned tracking-issue comments for the *first*
`stage=implementation` marker and returned that PR's number/SHA forever —
stale the moment a follow-up feature PR opened on the same issue (e.g. the
R-001 descope pattern), with no mechanism to detect or prefer a newer one.
`06-deploy.yml` uses this to decide what to actually build and deploy, so
a stale result risks silently deploying a superseded commit.

Fixed by asking GitHub directly for the PR that's actually open right now,
using Stage 3's own deterministic branch-naming convention
(`feature/<request_id>`, confirmed in `implementation_coordinator.py`)
instead of trusting comment history:
- New `list_open_prs_by_head(branch_name)` in `github_helper.py` — lists
  open PRs in `forge-demo-apps` whose head branch matches exactly, via the
  GitHub App installation token (same auth context as `get_pr()`).
- `resolve_feature_pr()` rewritten: resolves `request_id` via the existing
  `resolve_request_id()` (stable for the life of the issue), looks up
  `feature/<request_id>`'s open PRs, and returns the single match. Zero
  matches or more than one both raise `ValueError` loudly — no silent
  fallback to "pick the first one." No signature change; `06-deploy.yml`
  needed no edits at all, since it only ever consumed the function's
  `pr_number`/`head_sha` outputs, not its internals.
- `_IMPLEMENTATION_STAGE_MARKER`/`_PR_URL_RE` removed — confirmed via grep
  first that nothing else in the file referenced either constant, so they
  were genuinely dead code after the rewrite, not just orphaned by it.

**Verified live and via simulation, per the spec's own acceptance
criteria:**
- Real, read-only call against tracking issue #5 (REQ-2026-02):
  `resolve_feature_pr(5)` raised `ValueError` — correct, since both of
  REQ-2026-02's feature PRs (#15, #18) are merged/closed and no
  `feature/REQ-2026-02` PR is currently open. This *is* the real
  historical case the spec asked to check against (an issue whose
  Implementation-stage comment points at a since-superseded PR) — the old
  code would have returned stale PR #15 data forever; the new code
  correctly refuses to guess instead.
- Simulated (mocked `list_open_prs_by_head`/`resolve_request_id`, no live
  API calls) single/zero/multiple-open-PR cases: single → returns
  `(pr_number, head_sha)` correctly; zero and multiple both raise
  `ValueError` with the expected message; confirms all three branches
  independent of live state, since no `feature/*` PR is open anywhere
  right now to exercise the single-match path live.

**Both fixes:** `py_compile` clean on `workflow_glue.py`/`github_helper.py`;
both edited workflow YAML files parse cleanly via `yaml.safe_load`. **Committed
2026-08-13** as two separate commits per the spec's own handoff notes: Fix 1
(`04-qa.yml` + `05-security.yml` together, `5271342`) and Fix 2
(`github_helper.py` + `workflow_glue.py` together, `457f1b9`) — both pushed to
`main`, documented in `7fc46dc`.

---
