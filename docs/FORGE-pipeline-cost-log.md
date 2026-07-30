# FORGE — Pipeline Cost & Stage Log

**Purpose:** A running ledger of where cost is actually incurred in the FORGE pipeline, and what each real invocation of each stage has actually cost. This is separate from Document 3 (which estimates cost for planning/procurement purposes) and separate from `FORGE-context_vN.md` (which is chat-continuity, not a data record). This file is the one place actuals accumulate over time; Document 3 should eventually cite it rather than re-derive estimates once enough runs exist.

**Maintenance:** Append a new row to the relevant stage's table after every real (non-dry-run) invocation. Dry runs are worth recording too if they're the only data point for a stage, but mark them clearly as dry runs — they don't include commit/PR/comment steps and can run cheaper or more expensive depending on the stage. This file lives in `forge-template` at `docs/FORGE-pipeline-cost-log.md` and is committed like any other doc — not gitignored, not local-only.

---

## 1. Pipeline Stage → Cost Mechanism Reference

| Stage | Agent | Invocation Mechanism | Cost Model | Auto-Logged? |
|---|---|---|---|---|
| Intake | `intake_agent.py` | `anthropic` Messages API (single-turn, ADR-0011) | Per-token (input/output) | ✅ `forge_event: agent_invocation` JSON line, `claude_agent_wrapper.py` |
| Requirements | `requirements_agent.py` | Messages API (single-turn) | Per-token | ✅ same |
| Design (Spec & Design) | `design_agent.py` | Messages API (single-turn) | Per-token | ✅ same |
| **Implementation** | `implementation_coordinator.py` + Backend/Frontend/Test Writer subagents | **Anthropic Managed Agents** (ADR-0010), separate mechanism from the Messages API | Per-token (input/output/cache read/cache write) **+ $0.08/session-hour active runtime** | ❌ **No equivalent to `agent_invocation` exists yet** — cost data currently requires a manual pull from the Claude Console session detail page (`usage` object) or `GET /v1/sessions/{id}` (not yet confirmed to return it — open item from chat 28). This is a real automation gap; every row below for Stage 3 was hand-copied from the Console. |
| QA | `qa_agent.py` (not yet built — next step, 3.8) | Messages API (planned) | Per-token | Planned: ✅ (same wrapper as Intake/Requirements/Design) |
| Security | (not yet built) | Messages API (planned) | Per-token | Planned: ✅ |
| Deploy | (not yet built) | Messages API (planned) | Per-token | Planned: ✅ |

**Model tier split (ADR-0010):** Stage 3's coordinator runs on the Opus tier; Backend/Frontend/Test Writer subagents run on the Sonnet tier (`FORGE_COORDINATOR_MODEL` / `FORGE_SUBAGENT_MODEL`). All other stages currently default to Sonnet 4.6 (see `_MODEL_RATES` in `claude_agent_wrapper.py`).

**Known caching asymmetry:** Stage 3 caches automatically at the Managed Agents session level with no `cache_control` set anywhere in `managed_agents_wrapper.py` — cache reads have dominated the token bill by four orders of magnitude over fresh input in both runs recorded below. The six Messages-API stages currently cache **zero** tokens on every call (no `cache_control` set in `claude_agent_wrapper.py` either) — a queued, not-yet-actioned follow-up from chat 28/29 is adding it there, which should show up as a visible drop in per-run cost for those stages once done. Worth watching this log for that change when it lands.

---

## 2. Per-Run Actuals

### Intake — `intake_agent.py`

| Date | Request ID | Run Type | Input Tok | Output Tok | Cost (USD) | Duration | Notes |
|---|---|---|---|---|---|---|---|
| 2026-07-30 | REQ-2026-01 | Real | — | — | — | — | Verified end-to-end on issue #2 (6 targeted clarifying questions, correct label applied). **Cost not captured** — ran before this log existed. Gap, not a zero. |

### Requirements — `requirements_agent.py`

| Date | Request ID | Run Type | Input Tok | Output Tok | Cost (USD) | Duration | Notes |
|---|---|---|---|---|---|---|---|
| 2026-07-30 | REQ-2026-01 | Real | — | — | — | — | Verified end-to-end on issue #2 (`requirements.md` + `ado-work-items.json` committed, correctly no label applied). **Cost not captured** — same gap as Intake. |

### Design (Spec & Design) — `design_agent.py`

| Date | Request ID | Run Type | Input Tok | Output Tok | Cost (USD) | Duration | Notes |
|---|---|---|---|---|---|---|---|
| 2026-07-29 | REQ-2026-01 | Dry run | 2,929 | 12,745 | $0.1999 | 207 s | `end_turn`, no truncation. All 3 artifacts valid. |
| 2026-07-30 | REQ-2026-01 | **Real** | 2,929 | 12,738 | $0.199857 | 222 s | Committed to `design/REQ-2026-01`; PR #4 opened. |

### Implementation — `implementation_coordinator.py` (coordinator + Backend/Frontend/Test Writer, Managed Agents)

| Date | Request ID | Run Type | Cache Read Tok | Cache Creation (5m) | Output Tok | Input Tok (fresh) | Cost (USD) | Active Duration | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-07-30 | REQ-2026-01 | Dry run | 11,868,067 | 358,148 | 125,693 | 253 | **$7.65** | 2,309 s (~38.5 min) | Pre-shared-docs-patch. 96 files, 156,728-byte archive. |
| 2026-07-30 | REQ-2026-01 | **Real** | 17,512,129 | 604,497 | 235,190 | 239 | **$12.31** | 3,310.6 s (~55.2 min) | Post-shared-docs-patch (Backend/Frontend read `design.md`/`openapi.yaml`/`tasks.md` directly instead of via coordinator relay). PR #5 opened, 101 files → 98 after stripping 3 unrequested files (CI workflow, compliance checklist, verify script). **+61% cost / +43% duration vs. dry run — attributed to the extra real file reads the patch introduced, not a regression.** |

### QA / Security / Deploy

Not yet built. Tables to be added when each stage's agent is implemented and first run (3.8 onward).

---

## 3. Cumulative Totals (Anthropic API cost, tracked stages only)

| Stage | Runs Recorded | Total Cost (USD) |
|---|---|---|
| Intake | 1 (uncosted) | — |
| Requirements | 1 (uncosted) | — |
| Design | 2 | $0.399757 |
| Implementation | 2 | $19.96 |
| **Total (costed runs only)** | | **$20.36** |

This excludes Managed Agents' separate $0.08/session-hour billing component, which is already folded into the $12.31/$7.65 figures above per the Console's `list_cost` — worth confirming that assumption the first time `GET /v1/sessions/{id}`'s own cost field (if one exists) is checked against the Console total, since right now both Stage 3 rows are taken as a single all-in number rather than split token-cost vs. session-hour-cost.

---

## 4. How to Add a Row

1. **Messages-API stages (Intake, Requirements, Design, QA, Security, Deploy):** grep the GitHub Actions job log for `"forge_event": "agent_invocation"` — the JSON line already has `input_tokens`, `output_tokens`, `total_cost_usd`, `latency_seconds`. Copy directly into the relevant table; no manual math needed.
2. **Implementation (Stage 3):** no automatic equivalent yet. Open the Claude Console session detail page for the `session_id` printed by `implementation_coordinator.py`'s dry-run output or PR comment, and copy the `usage` object's fields as shown above. (Flagged in §1 as an open automation gap — closing it would mean adding an `agent_invocation`-equivalent log line to `managed_agents_wrapper.py`, queued but not yet built.)
3. Update the cumulative totals table in §3 after adding any costed row.
4. If a stage's cost mechanism or model tier changes (e.g. cache_control lands on the Messages-API stages), note the change inline in §1 rather than silently starting a new pattern with no explanation.
