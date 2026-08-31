# FORGE — Session Context v81

**Session date:** 2026-08-31 (Claude.ai)
**Carries forward from:** v80, unchanged except where noted below.

---

## What changed this session

### 1. `req-2026-01-email-worker` crash-loop — closed, no action taken

Confirmed against Mike's own scope filter: this is a pure app-level bug (bad
Service Bus connection string in `EmailWorker`'s config), doesn't block any
FORGE pipeline mechanism, and was in fact used as the real test target that
verified Item #1's Option 3 crash-loop flag end-to-end. Checked
`FORGE-Open-Items-Backlog-v2.md` — it was never tracked there either. Mike's
call: ignore entirely, no ADO logging, no code fix. Closed with zero action.

### 2. Item #31 — fully resolved (grew from 1 stage to 5 during investigation)

Item #31 was logged in v80 against `design_agent.py`'s `_parse_model_json()`
fragility only. This session's investigation-first pass (before writing any
spec) found the identical fragile pattern — free-text JSON-mode output parsed
via an unguarded `json.loads()`, with the raw model output never persisted
anywhere on failure — independently duplicated in three more stages
(`requirements_agent.py`, `qa_agent.py`, `security_agent.py`), and later a
fifth (`ingestion_agent.py`, found during the four-stage migration's own
close-out sweep, not the original investigation).

**Mike's two scope decisions, made before any spec was written:**
- Scope: all affected stages, not just design (later expanded to include
  ingestion_agent.py once found).
- Fix depth: **root-cause** — forced-schema tool-use output via the Anthropic
  Messages API, not a mitigation (persist-raw-text and/or bounded retry
  alone).

**Spec:** `FORGE-Item31-StructuredModelOutput-Spec.md`, authored this
session. Centralizes the fix once in `claude_agent_wrapper.py` rather than
reproducing per-stage logic — directly addresses the "same bug at multiple
layers" pattern already named as a recurring FORGE risk.

**Built and verified:**
- `29fed6e` — `claude_agent_wrapper.py`: `invoke_agent()` gained
  `output_schema: dict | None = None`; when passed, forces a single tool call
  and extracts `AgentResult.structured_output` (new field) from the
  `tool_use` block's `.input` directly — no `json.loads()` at any call site.
  `stop_reason == "max_tokens"` is checked before ever touching `.input`,
  preserving the exact ordering all four original stages already had.
  Extraction failures (zero/multiple `tool_use` blocks, non-dict `.input`)
  raise `RuntimeError` only after persisting the full raw response to a
  diagnostic JSON file — the original Item #31 gap (unrecoverable raw output
  on failure) is now closed structurally, not just for design. Verified via a
  13-case local mock harness (no real API calls).
- `ccb23fa`, `43b11d4`, `89985d7`, `ad74ba8` — `design_agent.py`,
  `requirements_agent.py`, `qa_agent.py`, `security_agent.py` migrated to the
  new schema-based path; each stage's dead parsing code deleted (helper
  functions and/or inlined fence-stripping blocks), redundant "Respond with
  ONLY a single JSON object" prompt framing trimmed. `requirements_agent.py`'s
  manual `"epic"/"features"` key-check folded into the schema's `required`
  fields (strictly more general — per §3.4 of the spec, Mike's default
  accepted, no objection raised).
- **Fifth migration (Mike's explicit approval mid-session):**
  `ingestion_agent.py` — same pattern, same fix, its own commit. Not part of
  the original spec's investigated scope; caught during the four-stage
  migration's dead-code sweep.

**Artifact-upload question (spec's §2.1 mentioned reusing the
`06-deploy.yml` artifact-upload pattern):** deferred, not built. Mike's call:
the wrapper's file-write-to-disk is the safety net for now; only wire up
GitHub Actions artifact upload if §5's live verification showed a non-trivial
residual failure rate. It didn't (see below), so this stays deferred/likely
unnecessary rather than becoming a tracked open item.

**§5 live verification — real evidence, all 5 stages, Mike's explicit
cost go-ahead given beforehand:**
- Total real spend: **$0.526872** (estimated $0.75–$2.00) across 5 real
  `invoke_agent()` calls against real input (real `forge-demo-apps` clones,
  real `dotnet test`/Gitleaks/Dependabot scans, a real intake spreadsheet, a
  real `requirements.md`) plus one deliberate `max_tokens=50` truncation
  probe against `design_agent.py`'s schema.
- All 5: `result.structured_output` populated with every expected key, no
  `KeyError`s, all downstream processing unaffected (YAML validation, ADO
  payload rendering, QA/Security label decisions all correct against real
  scan results).
- **`max_tokens` guard empirically confirmed**, not just per Anthropic's
  docs: forced a genuine truncation, confirmed `stop_reason == "max_tokens"`,
  `structured_output` stayed `None`, wrapper never touched the truncated
  `.input` — no crash, no garbage data.
- No GitHub state touched anywhere (`--dry-run`/`dry_run=True` throughout,
  confirmed by each stage's own log line).

**Surprises found during verification, both resolved:**
- A frontend build failure during QA's real run — confirmed to be an
  artifact of the verification setup itself (shallow clone, skipped `npm
  install`), not a regression.
- A pre-existing Semgrep Windows-codepage crash (`UnicodeEncodeError`
  writing its own JSON output) — confirmed unrelated to Item #31, doesn't
  reproduce on `ubuntu-latest` CI. **Mike's call: ignore entirely**, not
  logged anywhere in tracking docs (recorded only as a note in the relevant
  commit message, per instruction not to silently drop the decision).

**Closed out in CLAUDE.md and Backlog v2** (`c6fca2d`, before the
restructuring below): full narrative inline (no archive file existed yet at
that point), explicitly noting `ingestion_agent.py` was outside the original
investigated scope.

### 3. CLAUDE.md documentation restructuring (separate task, same session)

Mike asked for a review of CLAUDE.md, Backlog v2, and the context doc for
redundancy. Finding: CLAUDE.md's "Open Items / Known Gaps" section was 1,461
lines, of which **97.6% (1,426 lines) was full historical narrative for
items already marked resolved** — only 3 items (#7, #11, #31-at-the-time)
were genuinely open. Backlog v2 already served as the intended one-line
index for resolved items (its own text says so); CLAUDE.md had just never
been trimmed to match.

**Executed via Claude Code CLI, two commits:**
- `b611193` — new `docs/CLAUDE-archive-2026-08-resolved-open-items.md`
  created (1,687 lines). **All 29 resolved items** (#1–#6, #8–#10, #12–#31)
  moved there verbatim — Item #31 had already been resolved by the time this
  ran (closed out in the immediately preceding part of this same session),
  so it correctly got swept in alongside the other 28, not left as a 3rd
  "genuinely open" item as the original task framing assumed. Verified via a
  programmatic byte-identical diff across all 29 items, not just spot-checks.
  Only Items #7 and #11 remain genuinely open, in place, unarchived.
  CLAUDE.md's Open Items section: **1,461 → ~180 lines** (short pointers only).
- `142940e` — "Current Build Phase" section's ~97-line re-narration of Items
  #24/#25/#26/#28/#30 replaced with two short paragraphs pointing at the
  (now-archived) entries. Two sections renamed to reflect their actual
  content (durable reference, not session-scoped): "Key Decisions Made This
  Session" → "Agent Invocation & Infrastructure Reference"; "Outstanding
  Before Phase 3 Continues" → "Pipeline Stage Reference (Agent-by-Agent)".
  "Further reading" updated with the new archive file.

**Net result: CLAUDE.md 3,100 → 1,703 lines (45% reduction), zero
information lost** (everything preserved verbatim in the new archive file).

**Backlog v2 needed no changes** — already consistent by the time this ran
(Item #31's earlier close-out this session had already updated it correctly).

**Follow-up fix, same session (`a27f311`):** a stale reference found in
CLAUDE.md's "Pipeline Stage Reference" section — `requirements_agent.py`'s
entry still described the now-deleted `_parse_model_json()`. Corrected to
describe the real current mechanism (`output_schema`/`structured_output`,
`RuntimeError` on extraction failure rather than `JSONDecodeError`). Swept
`design_agent.py`/`qa_agent.py`/`security_agent.py`'s entries too — none had
an equivalent stale description.

### 4. NEW standing convention — Documentation Ownership (`a27f311`)

This session surfaced a real overlap problem: Claude.ai's own end-of-session
prompt asked Claude Code CLI to directly edit `FORGE-Open-Items-Backlog-v2.md`
— which is how that file ended up briefly stale (still showing Item #1 as
open after CLAUDE.md already showed it resolved). **Fixed going forward** by
adding a `## Documentation Ownership` section to CLAUDE.md (placed right
after Project Overview):

- **`CLAUDE.md`** — owned by Claude Code CLI only. Claude.ai never edits it
  directly; may only flag staleness and hand Claude Code CLI a prompt.
- **`docs/FORGE-Open-Items-Backlog-v2.md`** — owned by Claude.ai only. Claude
  Code CLI never edits it directly, even mid-task — flags back instead.
- **`docs/FORGE-context_v*.md`** — owned by Claude.ai only (unchanged from
  how this already worked).
- **Default for newly-resolved CLAUDE.md items going forward:** a short
  pointer (3–8 lines) plus a dated archive-file entry for the full
  narrative — not full narrative inline — unless the resolution is
  genuinely short to begin with. Prevents the Open Items section from
  re-bloating the way it did before this session's cleanup.

---

## Open items — updated status

- **`req-2026-01-email-worker` crash-loop:** **closed, no action** (this
  session). Was never actually a tracked item; Mike's scope-filter call.
- **Item #31:** **now fully resolved** (this session), scope grown from 1
  stage to 5. Remove from "open" going forward.
- **Item #7, #11:** unchanged, still deliberately-left-as-is /
  accepted-ongoing-risk respectively — untouched by this session's
  restructuring.
- **Cost Estimator spec:** unchanged, not yet started.
- **Phase 7 end-to-end Enhancement Workflow validation run:** unchanged,
  still worth a dedicated fresh-intake pass.
- **Process question (self-approval/`enforce_admins` deadlock):** unchanged
  from v80 — no decision made this session, not touched.
- **Semgrep Windows-codepage bug:** found and explicitly **not tracked**
  per Mike's call (local-dev-only, doesn't affect `ubuntu-latest` CI).
  Recorded only in a commit message, not in any tracking doc — noting here
  so the decision itself isn't lost even though the bug isn't tracked.

## Azure infrastructure

Nothing started this session — all work was code/doc commits, GitHub API
calls, and real (but non-Azure) Anthropic API calls for Item #31's live
verification (~$0.53 total). No shutdown prompt needed. Postgres
(`forge-req2026-03-pg`) was not touched.

---

## On the horizon (unchanged from v80 unless noted)

- Cost Estimator spec — five open design forks, not yet started
- A dedicated Phase 7 validation run from a genuinely fresh intake
- The self-approval/`enforce_admins` deadlock — permanent decision still
  needed
- Ongoing Open Items Backlog discipline — now backed by the new
  Documentation Ownership convention, should be less likely to drift again
- CLAUDE.md is now in a clean, trimmed state (1,703 lines) with an
  established archive pattern — future resolved items should default to the
  short-pointer-plus-archive-entry style from the start, not accumulate and
  need a second cleanup pass
