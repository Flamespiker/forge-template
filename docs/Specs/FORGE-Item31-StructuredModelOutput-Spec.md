# FORGE — Structured Tool-Use Output for Design/Requirements/QA/Security (Item #31): Spec for Claude Code

**Prepared:** 2026-08-31 (Claude.ai)
**For:** Claude Code CLI session against `forge-template`
(`core/agents/utils/claude_agent_wrapper.py`, `design_agent.py`,
`requirements_agent.py`, `qa_agent.py`, `security_agent.py`).
**Context:** Item #31 in CLAUDE.md's Open Items list, originally logged 2026-08-31
against `design_agent.py`'s `_parse_model_json()` after a real, costed Messages API
call ($0.205, 12,973 output tokens) produced a `JSONDecodeError` with zero
diagnostic signal recoverable (`run_design_agent()` re-raises without persisting
`output_text` anywhere). This session's investigation (before writing this spec)
found the same fragile pattern independently duplicated in three more stage
agents — see §1 findings below. Per Mike's explicit decision this session: scope
is **all four affected stages**, and fix depth is **root-cause** (forced-schema
tool-use output), not a mitigation (persist-raw-text and/or bounded retry alone).

**Standing conventions to follow (per CLAUDE.md / context doc):**
- Verify against the live file, not this spec — `view`/fetch the real current
  `claude_agent_wrapper.py`, `design_agent.py`, `requirements_agent.py`,
  `qa_agent.py`, `security_agent.py` before writing anything. This spec's
  understanding of line numbers and exact shapes comes from this session's
  investigation pass, which may have drifted by the time this is picked up.
- Report every design fork back to Mike rather than resolving silently — see §3.
- ADR-0011 comment-then-raise contract still applies on any failure path — this
  spec changes *how* a failure is detected/diagnosed, not whether a failure still
  produces a tracking-issue comment before re-raising.
- Commit each piece in §2 **separately** (wrapper change is its own commit,
  each stage's migration is its own commit) — not bundled, per standing
  convention. Confirm via GitHub API (not local git, not verbal) that each lands
  on `origin/main`.
- Windows environment: no bash heredocs; standard subprocess conventions if any
  are touched (none expected here — this is a pure Python/prompt change).
- Real-money verification: each stage's real-call verification costs roughly
  $0.15–$0.40 per attempt (same rate as Item #1's $0.406 precedent). Four stages
  means this session's total verification cost could run $0.60–$1.60 if every
  stage needs only one clean attempt — get Mike's explicit go-ahead before
  running any of §5's real calls, same as Item #1's practice.
- Do not touch `deploy_agent.py` or `intake_agent.py` — confirmed out of scope
  (see §1 findings).

---

## 1. Investigation findings (already established this session — confirm, don't re-derive)

This session already fetched and read all five files live. Findings to confirm
still hold (things may have drifted since):

1. **`claude_agent_wrapper.py`'s `invoke_agent()`** makes a single-turn Messages
   API call (`client.messages.create(model=..., max_tokens=..., system=...,
   messages=[{"role": "user", "content": user_prompt}])`) with **no `tools`
   parameter at all**. `output_text` is assembled by joining every
   `TextBlock.text` in `response.content`. There is no structured-output path
   today.
2. **Four stage agents independently parse free-text JSON** the model was merely
   *asked* (via system-prompt instructions: "Respond with ONLY a single JSON
   object...") to produce:
   - `design_agent.py` — dedicated `_parse_model_json()` helper (line ~217),
     called once (line ~266). Expected shape: `{"design_markdown": str,
     "openapi_yaml": str, "tasks_markdown": str}`.
   - `requirements_agent.py` — a near-identical dedicated `_parse_model_json()`
     helper (line ~222), called once (line ~284). Expected shape:
     `{"requirements_markdown": str, "ado_payload": {"epic": {...}, "features":
     [...]}}` — the richest/most-nested schema of the four.
   - `qa_agent.py` — same fence-stripping + `json.loads(text)` logic inlined at
     the call site (line ~1004), not factored into a helper. Expected shape:
     `{"pr_comment_markdown": str}` — the simplest schema of the four.
   - `security_agent.py` — same inlined pattern (line ~698). Expected shape:
     `{"overview_markdown": str}`.
   All four: on `json.loads` failure, the exception propagates into that stage's
   generic `except Exception as exc:` block. `logger.exception()` logs the
   traceback/message but **never `output_text` itself**; the failure-comment body
   posted to the tracking issue is just `f"Error: \`{exc}\`"`. The raw malformed
   text is unrecoverable in all four cases today, not just design's.
3. **`deploy_agent.py`** never calls `invoke_agent()` at all (confirmed via its
   own module docstring: "No Claude/invoke_agent call anywhere in this stage").
   **Not affected, not in scope.**
4. **`intake_agent.py`** calls `invoke_agent()` but its output is prose (a
   tracking-issue comment), never parsed as JSON. **Not affected, not in scope.**

**Confirm before writing code (this session did not verify):**
5. Anthropic's forced tool-use behavior when `stop_reason == "max_tokens"` mid
   tool-argument generation — does `response.content` still include a `tool_use`
   block (with truncated/invalid JSON in `.input`), or is the block omitted
   entirely? This determines whether the existing `if result.stop_reason ==
   "max_tokens": raise ValueError(...)` guard in all four stages remains
   sufficient as-is, or whether a new guard is needed specifically for a
   malformed/partial `tool_use.input` under a forced tool_choice. Check current
   Anthropic API docs/changelog rather than assuming either way.
6. Confirm the exact current system-prompt wording in all four stages'
   "Output format — this is strict: Respond with ONLY a single JSON object..."
   sections (quoted above from this session's fetch) — these become redundant
   (and potentially confusing to the model, since it will also see a forced tool
   definition) once §2 lands, and should be trimmed or removed, not left in
   alongside the new tool schema.

Report confirmation of #5 and #6 back before implementing §2.

---

## 2. Scope

### 2.1 `claude_agent_wrapper.py` — add an optional forced-schema path (single change point)

**Goal:** fix this once, centrally, rather than reproducing the same "same bug at
multiple layers" pattern CLAUDE.md already flags as a recurring FORGE risk (Items
#24/#25/#28 all hit variants of this for a different kind of duplicated logic).

**Proposed approach:**
- Add an optional `output_schema: dict[str, Any] | None = None` parameter to
  `invoke_agent()`.
- When provided, build a single tool internally (e.g. name
  `"submit_structured_output"`, `input_schema` = the caller's `output_schema`),
  pass it as `tools=[...]`, and force it via `tool_choice={"type": "tool", "name":
  "submit_structured_output"}` on the `client.messages.create()` call.
- Extract the parsed result from the `tool_use` content block's `.input`
  (already a Python dict via the SDK — no `json.loads` needed at the call site at
  all) instead of joining text blocks.
- Add a new `AgentResult.structured_output: dict | None = None` field, populated
  only when `output_schema` was passed. `output_text` stays populated as today
  (still useful for logging/diagnostics) when `output_schema` is used — the SDK
  makes both available on the same response, so this costs nothing extra.
- **Defensive diagnostics, kept even with forced schema:** if extracting the
  `tool_use` block fails for any reason (no such block present, `stop_reason`
  anomaly per §1.5's finding, or any other unexpected shape), persist the full
  raw API response (JSON-serialized `response.model_dump()` or equivalent) as a
  GitHub Actions artifact before raising — reusing the existing artifact-upload
  pattern already live in `06-deploy.yml` (the `deploy-context` artifact,
  confirmed working per CLAUDE.md's Item #26 verification) rather than
  inventing a new upload mechanism. This is the one piece of the original
  "persist raw output on failure" idea from Item #31's initial scoping that's
  still worth keeping even after the root-cause fix — belt-and-suspenders for the
  residual, much-narrower failure surface that remains.
- Callers that don't pass `output_schema` (currently just `intake_agent.py`)
  are completely unaffected — this is purely additive to the wrapper's contract.

### 2.2 Per-stage migration (four separate commits, one per stage)

For each of `design_agent.py`, `requirements_agent.py`, `qa_agent.py`,
`security_agent.py`:
- Define the stage's JSON schema as a Python dict (translate the existing
  system-prompt-documented shape — quoted in §1.2 above — into a proper JSON
  Schema `object` with `required` fields set for every key the code currently
  accesses via `parsed_output["..."]`).
- Pass it to `invoke_agent(..., output_schema=SCHEMA)`.
- Replace `_parse_model_json(result.output_text)` (or the inlined
  fence-stripping + `json.loads` block in `qa_agent.py`/`security_agent.py`)
  with `result.structured_output` directly.
- Delete the now-dead `_parse_model_json()` helper in `design_agent.py` and
  `requirements_agent.py`; delete the inlined fence-stripping block in
  `qa_agent.py` and `security_agent.py`.
- Per §1.6: trim each system prompt's "Output format — this is strict: Respond
  with ONLY a single JSON object..." section, since the tool schema now carries
  that contract structurally. Keep any content-level guidance that isn't purely
  about JSON formatting (e.g. design's per-field descriptions of what
  `design_markdown` should contain) — only the "respond as JSON text" framing
  itself is now redundant.
- `design_agent.py` specifically: keep the existing `yaml.safe_load(openapi_yaml_text)`
  validation step unchanged — the schema guarantees `openapi_yaml` is a JSON
  string, not that its *contents* are valid YAML. That check still earns its
  keep.
- `requirements_agent.py` specifically: keep the existing `if "epic" not in
  ado_payload or "features" not in ado_payload: raise ValueError(...)` check, or
  fold it into the JSON Schema's `required` array instead (recommended — this
  makes it a schema-level guarantee rather than a manual post-hoc check,
  removing one more hand-written validation the schema can now subsume). Note
  as a finding either way, not a silent choice.

---

## 3. Design forks — resolve before implementing (already partly resolved by Mike this session)

### 3.1 Scope: all four stages vs. design-only — **RESOLVED by Mike:** all four.

### 3.2 Fix depth: minimal-persist vs. minimal+retry vs. root-cause — **RESOLVED by
Mike:** root-cause (forced-schema tool-use), per §2.1/§2.2 above. The defensive
raw-response persistence in §2.1 is kept as a secondary safety net, not the
primary fix.

### 3.3 NEW fork this spec introduces — centralize in the wrapper vs. four independent call-site changes

**Recommended (as written in §2.1/§2.2 above): centralize the tool-building/
extraction logic once in `claude_agent_wrapper.py`,** with each stage only
supplying its own schema dict. This directly addresses the pattern CLAUDE.md's
"Key learnings" section already names as a recurring risk ("Same bug at multiple
layers" — Items #24/#25/#28 all hit variants of exactly this for a different
kind of duplicated logic).

**Alternative not recommended, flagged for completeness:** have each of the
four stage agents build its own `tools=[...]`/`tool_choice` call directly against
the raw `anthropic` client, bypassing `invoke_agent()`'s abstraction for this
one case. This would avoid changing the shared wrapper's contract at all, but
reproduces the exact duplication problem this item exists to fix — a fifth
independent copy of "how do I get structured JSON out of Claude," just using a
different (more reliable) underlying mechanism than today's four copies. Not
proposed as the default.

### 3.4 NEW fork — required-field validation: schema-level vs. code-level

`requirements_agent.py` currently has one manual post-parse validation
(`"epic" not in ado_payload...`) that the other three stages don't have an
equivalent of. Once schemas exist, this could become declarative (`required`
arrays in the JSON Schema) instead of a hand-written `if`. Recommended: fold it
into the schema, since it's strictly more general (JSON Schema `required` also
covers the top-level `requirements_markdown`/`ado_payload` keys, which today
have no explicit check at all — they'd simply `KeyError` if missing, an even
less diagnostic failure mode than what Item #31 originally flagged). No live-
resource consequence either way — default to the recommendation unless Mike
objects.

---

## 4. Out of scope

- `deploy_agent.py`, `intake_agent.py` — confirmed unaffected (§1.3/§1.4).
- Any change to what each stage's *content* asks the model to produce (the
  substantive instructions for what `design_markdown`, `ado_payload`, etc.
  should contain) — this spec only changes the transport/parsing mechanism, not
  the prompts' subject matter, beyond trimming the now-redundant "respond as
  JSON" framing per §2.2.
- Bounded retry-on-failure — considered and explicitly not chosen as the primary
  mechanism (§3.2); the residual failure surface after §2.1/§2.2 is expected to
  be small enough that manual re-run (same as today, for any other stage
  failure) is sufficient. Revisit only if live verification (§5) shows the
  residual failure rate is non-trivial.
- `req-2026-01-email-worker`'s crash loop — unrelated, separately closed out
  this session (app-level, no FORGE-mechanism action needed).

---

## 5. Live verification

**Real, costed Messages API calls are required for all four stages** — a
`--dry-run` alone doesn't prove the new schema produces output the rest of each
pipeline stage can actually consume (e.g. `design_agent.py`'s `yaml.safe_load()`
check on `openapi_yaml`, `requirements_agent.py`'s downstream ADO-payload
rendering). Same "real evidence, not a passing dry run" bar as every other item.

1. **Before running any real call: confirm with Mike that spending on all four
   stages' verification is acceptable** — per the cost estimate in "Standing
   conventions" above ($0.60–$1.60 total if each stage needs only one clean
   attempt; more if a stage needs a retry, same as Item #1's first attempt being
   wasted).
2. For each of the four stages, in any order:
   - Run a real (non-dry-run-equivalent, i.e. an actual `invoke_agent()` call
     with the new `output_schema`) invocation against real input (reuse
     REQ-2026-01/02/03's real `requirements.md`/`design.md`/PR content, matching
     whatever that stage would see in production — do not synthesize fake
     input).
   - Confirm `result.structured_output` is populated and contains every key the
     stage's code reads, with no `KeyError`.
   - Confirm the stage's own downstream processing of that output still works
     unchanged (design's YAML validation; requirements' ADO summary rendering;
     QA/Security's comment posting — dry-run the posting step itself, i.e. print
     rather than actually post, to avoid a redundant real GitHub comment during
     verification).
   - Confirm token/cost logging (`total_cost_usd`, structured log line) still
     fires correctly — §2.1 didn't change any of that path, but confirm rather
     than assume.
3. Confirm `_parse_model_json()`/inlined-parsing removal didn't leave any dead
   imports (`json` module may still be needed elsewhere in a given file — check
   before removing the import wholesale).
4. Confirm §1.5's `max_tokens`-mid-tool-call behavior once, deliberately, if
   feasible to trigger safely (e.g. temporarily lowering `_MAX_TOKENS` for one
   throwaway test call on the stage with the largest typical output —
   `design_agent.py`, per its documented ~12–13k-token typical size) — this
   confirms whether the existing guard is sufficient or needs the new check
   flagged in §1.5. If not safely triggerable without excess cost, note that
   this remains unverified and document it as a known residual risk rather than
   spending real money to force it.
5. Report all four stages' real-call evidence (structured output shape, cost,
   any surprises) back explicitly before closing the item.

---

## 6. Sequencing

1. §1 investigation points 5–6 — confirm before writing any code.
2. §2.1 — wrapper change, its own commit, own review (this is the foundational
   piece every stage migration depends on).
3. §2.2 — four separate commits, one per stage, in any order (no
   inter-dependency between stages beyond §2.1 already being live).
4. §3.4's schema-required-fields decision — apply per the recommendation unless
   Mike objects; no need to pause and ask given no live-resource consequence.
5. §5 live verification — **gated on Mike's explicit cost go-ahead (§5 step 1)**
   — run after all code is committed, not incrementally per-commit, so each
   stage's real call tests the final migrated code, not an intermediate state.
6. `CLAUDE.md` close-out: mark Item #31 resolved with the real fix narrative and
   all four stages' live evidence, same format as Items #24/#25/#28's entries.
   Note explicitly that scope grew from "design_agent.py only" (as originally
   logged) to all four stages, and why (this session's investigation, confirmed
   by Mike).

---

## Next chat after this one (Claude.ai)

Once Claude Code reports back with live-verification evidence for all four
stages, fold the outcome into a fresh context doc, close Item #31 in CLAUDE.md,
and update `FORGE-Open-Items-Backlog-v2.md` accordingly. No other open item
depends on this one, so no follow-on spec is implied — this can close cleanly.
