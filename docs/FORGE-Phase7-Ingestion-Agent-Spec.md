# FORGE — Phase 7 Kickoff: Codebase Ingestion Agent (3.11) + Stage 0a Wiring — Spec for Claude Code

**Prepared:** 2026-08-26 (Claude.ai)
**For:** Claude Code CLI session against `forge-template` (this is a core-layer pipeline/agent build — no `forge-demo-apps` application code changes)
**Context:** Phase 6 (Repeatability) closed clean per context doc v66 — no blocking items remain. Mike's explicit direction: next phase is **Phase 7 — Enhancement Workflow**. Build Plan step 7.1 ("Complete Codebase Ingestion Agent, 3.11 above, if deferred") is the correct starting point — it's the one piece of core-template mechanism the rest of Phase 7 depends on, and it's app-agnostic (doesn't require the actual enhancement target to be chosen first).

**Verified against live code before this spec was written** — fetched from `raw.githubusercontent.com/Flamespiker/forge-template/main/...` this session: `.github/workflows/00-intake.yml`, `.github/workflows/01-requirements.yml`, `core/agents/intake_agent.py`, `core/agents/requirements_agent.py`, `core/agents/design_agent.py`, `core/agents/workflow_glue.py`, `core/agents/utils/github_helper.py`, `core/agents/utils/file_io.py`, `core/agents/utils/claude_agent_wrapper.py`. **Caveat: the GitHub API was rate-limiting unauthenticated requests this session, so these were fetched by `main` branch ref, not pinned by commit SHA** — normally this spec would cite an exact SHA per the project's standing convention (branch refs can serve stale CDN-cached content for several minutes post-push). Re-fetch every file above by SHA and re-run `grep -n` against the real current content immediately before editing — treat every line number below as provisional, not authoritative.

**Standing conventions to follow (per `CLAUDE.md` / context doc):**
- Verify against the live file, not this spec, immediately before editing.
- Windows environment: `shutil.which()` for subprocess calls, `encoding="utf-8"` on subprocess readers, no bash heredocs.
- Commit each numbered component below **separately** for legible history.
- Smoke-test each piece individually before moving to the next.
- Report any design fork back to Mike rather than resolving silently — two are flagged explicitly below as already traced/resolved by control-flow inspection, per the project's "trace first, escalate only if genuinely ambiguous" pattern; confirm the trace still holds against live code before trusting it.
- Do **not** update the context doc from this Claude Code session — that's Claude.ai's job at session close. Do update `CLAUDE.md`'s Open Items / Build Plan tracking with what this session actually did/observed, including checking off Build Plan step 7.1 only once fully live-verified.
- Pipeline stage sequence, count, and human-gate-per-stage are all **Locked** per Document 07. Stage 0a is the one documented exception to "no stage may be skipped" — it is *only* triggered for enhancement requests, never for greenfield. It remains **not human-gated** (Document 01 §3.0a) — do not add an approval label or PR review step for it.
- Agents never merge their own PRs.

---

## 1. What this spec covers, and what it deliberately doesn't

**In scope:** Build Plan 3.11 / 7.1 — the Codebase Ingestion Agent itself, plus the minimum pipeline wiring needed for it to actually run and feed its output into Requirements and Design. This is core `forge-template` mechanism work, independent of which specific enhancement gets built first.

**Out of scope for this spec:**
- Choosing the actual enhancement request (Build Plan 7.2/7.3) and writing its intake spreadsheet — that's a content/business-decision artifact, belongs in its own fresh chat per the one-doc-per-chat convention, and depends on Mike confirming a target. See §6 below for a proposed candidate to consider in that follow-up session.
- Running the enhancement through the live pipeline end-to-end (Build Plan 7.4–7.8) — that's the session *after* the intake spreadsheet exists.
- Anything in `forge-demo-apps` application code.

---

## 2. Two design forks traced and resolved before writing this spec

### Fork A — Where does Stage 0a's trigger actually sit?

Document 07 (Customization Reference) lists stage order as "0a–6" and calls the Codebase Ingestion trigger **Locked**: *"Triggered automatically when the request is flagged as an enhancement. Cannot be manually triggered for greenfield requests."* Document 02 (Architecture) §4.1 says the trigger is *"Request flagged as an enhancement at intake (checkbox/field in the intake spreadsheet)"* and that it feeds **directly into Requirements** with no gate. Document 01 (Product Spec) §3.0a says it runs *"before any requirements work begins."*

The "0a before 0b" naming reads like strict execution order at first glance, but it can't literally be — the Enhancement flag and the existing-service name only become known once the intake spreadsheet is parsed, which is Stage 0b's (Intake Agent's) job. So Stage 0a can only run *after* the spreadsheet has been read once, not before.

Two real implementation shapes were possible: (A) a brand-new label (`ingestion-complete`) chaining a new standalone `00a-ingestion.yml` after Intake and before Requirements, or (B) invoking the Ingestion Agent as an additional conditional step **inside `00-intake.yml` itself**, right after the Intake Agent posts its clarifying questions.

**Resolved as (B).** Reasoning: Ingestion doesn't depend on the BA's clarification answers at all (it only needs the Enhancement flag + existing service name, both already in hand once the spreadsheet is parsed) — so running it as a same-workflow step lets it execute **in parallel with the BA's clarification round** instead of adding a sequential hop after it. This means by the time `clarification-complete` fires and Requirements Agent runs, `existing-architecture-summary.md` is already sitting in the monorepo, ready to read — no extra latency, no new label, no new workflow file, and the "not human-gated" requirement is trivially satisfied since there's nothing for a human to approve either way. It also avoids a subtle race: a new standalone `00a-ingestion.yml` triggered by a new label would need its own guard clause and its own request-ID resolution, duplicating logic `00-intake.yml` already has cheaply available mid-job.

**Confirm this trace still holds against live `00-intake.yml`/`intake_agent.py` before implementing** — if Intake Agent's actual structure has diverged from what's described here, or if there's a reason (found live) that Ingestion genuinely needs to run as a separate job/workflow, stop and flag it to Mike rather than forcing option (B).

### Fork B — Where does `existing-architecture-summary.md` get committed?

Document 02 §4.1 calls it *"a scratch location referenced by the tracking issue"* — deliberately vague. Requirements Agent's own module docstring (confirmed live) already establishes the precedent for exactly this kind of pipeline-internal, non-human-reviewed artifact: `requirements.md` and `ado-work-items.json` commit to the dedicated `pipeline-state` branch (the Phase 4 step 4.8 retrofit), specifically *because* `main` requires a PR review for every push and this content was never meant to go through one.

**Resolved:** commit `existing-architecture-summary.md` to `docs/<request-id>/existing-architecture-summary.md` on `pipeline-state`, same branch, same rationale, same `commit_files()` call shape Requirements Agent already uses. This is not a new pattern — it's the existing one applied to a third file.

---

## 3. New agent: `core/agents/ingestion_agent.py`

### 3.1 New `github_helper.py` function needed first

`get_file_contents(path, branch="main")` (confirmed live, line ~316) only reads a single file — it calls the Contents API and unconditionally treats the response as a file object (`response.json()["content"]`), which throws against a directory path (the Contents API returns a JSON array for directories, with no `"content"` key). Ingestion needs to walk an entire subtree, so add a new function rather than repurposing this one:

```python
def get_repo_tree(path_prefix: str, branch: str = "main") -> list[dict]:
    """
    List every blob under path_prefix in the target monorepo (forge-demo-apps),
    via the Git Trees API (recursive=1), filtered client-side to entries whose
    path starts with path_prefix.

    Returns a list of {"path": str, "size": int} dicts for blobs only (type ==
    "blob" — trees/subdirectories excluded, since callers just need file paths
    and sizes to decide what to read).

    Confirm live: the Trees API needs a commit/branch SHA, not a bare branch
    name, on some GitHub API versions — verify GET /repos/{owner}/{repo}/git/
    trees/{branch}?recursive=1 actually resolves branch names directly against
    the real API before assuming this works as written; if not, resolve the
    branch to its head SHA first via GET /repos/{owner}/{repo}/branches/{branch}.
    """
```

Same auth pattern as every other cross-repo call in this file (`get_installation_token()`, `_repo_url()`, `_auth_headers()`). Confirm the real response shape live (`GET /repos/Flamespiker/forge-demo-apps/git/trees/main?recursive=1` against a real installation token) before finalizing the parsing — in particular, whether `truncated: true` can appear for a repo this size (it's a two-app monorepo, unlikely, but check rather than assume, and log a clear warning if it ever is `true` rather than silently returning a partial tree).

### 3.2 File selection strategy

Reading every file under `services/<request-id>/` verbatim would blow the token budget fast (node_modules-adjacent build output, lockfiles, binaries). Two-pass approach:

1. **Tree pass:** call `get_repo_tree(f"services/{existing_service}/")`, then filter out noise before doing anything else — skip any path containing a segment in `{"node_modules", "bin", "obj", ".next", "dist", "coverage", ".git"}`, and skip files by extension/name in `{"package-lock.json", "yarn.lock", ".png", ".jpg", ".ico", ".svg", ".woff", ".woff2"}` (extend this list once you see the real tree — confirm live what's actually in `services/REQ-2026-01/` or `services/REQ-2026-03/` rather than guessing a complete noise list up front).
2. **Content pass:** always fetch full contents of manifest/config files (`*.csproj`, `package.json`, `tsconfig.json`, `openapi.yaml`, `Program.cs`/`Startup.cs`-equivalent, any `appsettings*.json`) wherever they appear in the filtered tree — these are cheap and high-signal. Then fill remaining token budget (pick a ceiling — start around 60k characters of source content, adjust after a live test shows real sizes) with the largest/most central remaining source files (controllers, route/page files, model/schema files) in descending size order, until the budget is spent. Always include the full filtered path list (just paths, not contents) in the prompt regardless of budget — that alone gives the model the folder/module shape even for files it doesn't get full content for.

This mirrors the existing project's general pattern of being deliberate and budget-conscious about what an agent reads (see `_MAX_TOKENS` constants throughout the other agents) rather than a new invention.

### 3.3 Agent shape

Follow the existing six-stage-agent pattern exactly (`requirements_agent.py` is the closest analog — reads from the monorepo via the GitHub App token, calls `invoke_agent()`, commits to `pipeline-state`):

```
python -m core.agents.ingestion_agent \
    --request-id REQ-2026-03 \
    --existing-service REQ-2026-03 \
    --issue-number 42
python -m core.agents.ingestion_agent --existing-service REQ-2026-03 --dry-run
```

- `--existing-service` — the value from the intake spreadsheet's "If Enhancement — Existing Service Name" field, used to build the `services/<existing_service>/` prefix. Confirm live whether this field's real stored value is already the bare request ID (`REQ-2026-03`) or free text a BA might type differently (e.g. "On-Call Roster Tracker") — if it's free text, this agent needs a mapping step or the field itself needs tightening; don't assume it's always a clean folder name without checking a real filled-in spreadsheet.
- `--dry-run` — same contract as every other agent: print `existing-architecture-summary.md` to stdout instead of committing/posting.
- Wrap `invoke_agent()` in try/except at the call site per ADR-0011 (ingestion_agent.py currently doesn't exist, so there's no existing pattern to preserve here — just follow the established one). On failure, best-effort post a failure comment to the tracking issue (real run only), then re-raise.

**System prompt** should ask for a structured `existing-architecture-summary.md` covering, at minimum:
- Actual tech stack observed (may differ from `team/stack-preferences.yaml` defaults — call out any deviation explicitly, since that's exactly the kind of thing Requirements/Design need to know before assuming a greenfield-style default).
- Folder/module structure and naming conventions actually in use.
- Existing data model / schema, as far as it's inferable from the code read.
- Existing API surface (endpoints, contracts) for a backend service; existing page/route structure for a frontend.
- Testing conventions observed (frameworks, file naming, coverage patterns).
- An explicit "what this summary could NOT determine" section — anything the model couldn't confidently infer from the files it was given should be named as a gap for the Requirements Agent's clarifying-question round to potentially pick up, not silently omitted.

**Output contract:** same `{"summary_markdown": "..."}`-shaped single-JSON-object response pattern the other stage agents use (see `requirements_agent.py`'s `_parse_model_json()` for the exact defensive-parsing pattern to reuse, including stripping an accidental \`\`\`json fence).

**Commit:** `commit_files()` to `docs/<request_id>/existing-architecture-summary.md` on `pipeline-state` (per §2 Fork B above) — reuse the exact call shape `requirements_agent.py` uses for `requirements.md`, confirmed live before writing.

---

## 4. Wiring changes

### 4.1 `00-intake.yml` — add a conditional ingestion step

After the existing "Run Intake Agent" step (confirmed live at the step named `run_agent`), add a new conditional step that:
1. Re-reads the already-downloaded `intake.xlsx` (already on disk from the earlier "Download intake spreadsheet attachment" step — no need to re-download).
2. Parses `overview["request_type"]` via `file_io.read_xlsx()` (already does this generically — confirmed live, no `file_io.py` changes needed) and checks whether the "Request Type" value is "Enhancement" (case-insensitive, trim whitespace — confirm the exact stored string live against a real filled spreadsheet, don't hardcode assuming perfect capitalization).
3. If Enhancement: resolve `request_id` (reuse `workflow_glue resolve-request-id`, same as `01-requirements.yml` already does) and pull the "If Enhancement — Existing Service Name" value from the same `request_type` section dict, then invoke `ingestion_agent.py` with both.
4. If Greenfield (or the field is blank/unrecognized): skip cleanly, log why, and do not fail the workflow.

Guard this the same defensive way the rest of the workflow already does (`if: steps.guard.outputs.proceed == 'true'`), and give it its own `id` so a failure here doesn't silently swallow the Intake Agent's own success — the two are independent concerns and either should be able to fail/succeed without masking the other. Post-failure comment pattern: match the existing "Post failure comment for a pre-agent step failure" step's style, but scoped to say ingestion specifically failed (not the whole intake run), since Intake Agent's own questions may have already posted successfully.

### 4.2 `requirements_agent.py` — read the summary if present

Add an optional fetch: after parsing the spreadsheet, if `overview["request_type"]` indicates Enhancement, attempt `get_file_contents(f"docs/{request_id}/existing-architecture-summary.md", branch="pipeline-state")`. Wrap in try/except for a 404 specifically (ingestion may not have finished yet, or may have failed) — log a clear warning and proceed without it rather than failing Requirements outright; a missing summary on an enhancement request is a real gap worth surfacing to the human reviewer, but it shouldn't hard-block the stage (Requirements can still draft from the spreadsheet + clarification answers alone, same as today, just without the extra grounding). Fold the summary into `_build_user_prompt()` as a new section, and update the `_SYSTEM_PROMPT`'s "Rules for requirements.md" to say: when existing-architecture context is present, requirements.md should note where the new requirement fits into what already exists, and should flag if a requirement appears to conflict with observed existing behavior.

### 4.3 `design_agent.py` — same optional fetch

Same pattern, same branch, same graceful-absence handling. Fold into the design prompt so Design Agent's architecture narrative and `tasks.md` breakdown respect existing conventions (naming, folder layout, existing endpoints) rather than proposing a design as if the folder were empty. Confirm live where `design_agent.py` currently reads `requirements.md` (via `get_file_contents`, per its own docstring) and add the ingestion-summary fetch alongside it, same request-ID-scoped path, same try/except-and-proceed pattern as §4.2.

---

## 5. Acceptance criteria

- `get_repo_tree()`: live call against a real existing service folder (`services/REQ-2026-01/` or `services/REQ-2026-03/`, whichever is more convenient to test against without touching anything) returns a sane, correctly-filtered file list — confirm noise directories are actually excluded and nothing legitimate is accidentally dropped.
- `ingestion_agent.py --dry-run` against that same real folder produces a genuinely useful `existing-architecture-summary.md` — spot-check it against what you actually know about that app's real structure (e.g. confirm it correctly identifies the tech stack, doesn't hallucinate endpoints that don't exist).
- `00-intake.yml`'s new conditional step: confirm it correctly no-ops on a Greenfield spreadsheet (re-use the REQ-2026-03 intake spreadsheet in project knowledge as a real Greenfield fixture) and correctly fires on a spreadsheet with Request Type = Enhancement (construct a minimal test fixture spreadsheet for this — don't wait for the real Phase 7 enhancement request to exist just to test the trigger logic).
- `requirements_agent.py` / `design_agent.py`: confirm both still behave identically to today (zero regression) when no `existing-architecture-summary.md` exists at the expected path — this is the path every request has taken until now, must stay unbroken.
- Confirm the whole chain end-to-end at least once with a real (even if throwaway/test) Enhancement-flagged intake: Intake Agent posts questions as usual AND Ingestion Agent independently produces and commits a real summary, both succeeding without interfering with each other.
- Update `CLAUDE.md` — new agent added, `00-intake.yml` changed, `requirements_agent.py`/`design_agent.py` changed. Note Build Plan step 3.11 and 7.1 as complete only once all of the above is live-verified, not just written.

---

## 6. Proposed enhancement target (for Mike to confirm in the follow-up chat — not decided here)

Not part of this spec's deliverable, but worth flagging now so the next session doesn't start from zero: REQ-2026-03's own intake spreadsheet (in project knowledge) already names a strong, low-risk candidate. R-010 (Non-Functional, Low priority) says claim/release events are already retained with who/when, explicitly noting *"No dedicated reporting UI is required in **this version**"* — and the Overview tab's out-of-scope list separately excludes *"historical reporting or analytics."* A small **read-only coverage-history view** (surface the already-recorded claim/release log per shift or per staff member) would be:
- Genuinely additive and low-risk — no changes to the existing write-path concurrency logic (R-006/R-007, the parts of this app that actually matter for correctness).
- A real test of whether the underlying event-log data model was actually built to support this (Phase 5/6 closeout doesn't confirm one way or the other) — exactly the kind of thing Codebase Ingestion should surface if it's missing, rather than Requirements/Design assuming it's there.
- Well-scoped enough to write a clean intake spreadsheet for in one sitting.

This is a suggestion, not a decision — confirm with Mike before writing the enhancement's intake spreadsheet in the next chat.

---

## 7. Sequencing

1. `github_helper.get_repo_tree()` — build and live-test against a real service folder first, independent of everything else, since every subsequent piece depends on it working.
2. `ingestion_agent.py` — build against that tree function, dry-run test.
3. `00-intake.yml` wiring — smallest, most mechanical piece once the agent works standalone.
4. `requirements_agent.py` fetch + prompt update.
5. `design_agent.py` fetch + prompt update.
6. Full-chain live test (§5, last bullet).
7. `CLAUDE.md` close-out.

Do not start on Build Plan 7.2 (choosing/writing the enhancement intake spreadsheet) in this session — that's explicitly the next chat, per the one-doc-per-chat convention, and depends on Mike confirming §6's direction first.
