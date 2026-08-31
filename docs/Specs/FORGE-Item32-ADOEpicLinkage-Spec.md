# FORGE — ADO Enhancement Items Should Link to the Existing Epic, Not Create a Parallel One (Item #32): Spec for Claude Code

**Prepared:** 2026-08-31 (Claude.ai)
**For:** Claude Code CLI session against `forge-template` (`core/agents/create_ado_items.py`, `.github/workflows/02-design.yml`), with live verification against `forge-demo-apps` and ADO project `FORGE-Build`.
**Context:** Backlog Item #32 — found 2026-08-31 during the Phase 7 Build Plan reconciliation (see Build Plan v10, step 7.7). REQ-2026-04 (Enhancement to REQ-2026-03) got its own brand-new Epic (#169), Features, and User Stories in ADO, entirely disconnected from REQ-2026-03's real Epic (#134). Mike's decision: build the real fix — a new Enhancement's Features/User Stories should be created as children of the **existing service's real Epic**, not a new one.

**Verified against live code before this spec was written** (fetched from `raw.githubusercontent.com/Flamespiker/forge-template/main/...` this session): `core/agents/create_ado_items.py`, `core/agents/utils/ado_helper.py`, `core/agents/utils/enhancement_target.py`, `.github/workflows/02-design.yml`, `.github/workflows/04-qa.yml` (for the existing "Determine Enhancement status" pattern to mirror). **Not pinned by commit SHA** (fetched by `main` branch ref) — re-fetch and re-`grep -n` immediately before editing, per standing convention.

**Standing conventions to follow (per CLAUDE.md / context doc):**
- Verify against the live file, not this spec, immediately before editing.
- Commit each numbered component below separately.
- Smoke-test each piece individually before moving to the next.
- Report any design fork back to Mike rather than resolving silently — one is flagged explicitly below, already decided by Mike; confirm it still makes sense against live code before trusting it.
- Agents never merge their own PRs. This is orchestration glue (`create_ado_items.py` already states "no Claude call happens here") — no PR is involved in this fix at all, it's a direct commit to `forge-template`.

---

## 1. What this spec covers, and what it deliberately doesn't

**In scope:** Teaching `create_ado_items.py` to reuse an existing Epic (looked up from the existing service's own `ado-work-items.json`) instead of always creating a new one, for Enhancement requests. Plus the `02-design.yml` wiring needed to actually pass `--existing-service` into it (currently missing entirely — Stage 2 is the one remaining stage that never resolved this).

**Out of scope:**
- Retroactively re-parenting REQ-2026-04's already-created Epic #169/Features/User Stories in live ADO. That's a one-time manual cleanup if Mike wants it, not part of this code fix — flag back if you think it should happen, don't do it unprompted (ADO state change).
- Any change to `qa_agent.py`'s Bug-creation/parent-linking logic — Item #25 already fixed that correctly; Bugs already parent-link to whatever `primary_user_story_id` resolves to, and that will automatically be correct once this spec's fix makes `primary_user_story_id` itself point to a User Story under the right Epic.
- Any change to how `requirements_agent.py` drafts `ado-work-items.json` — see the resolved design fork in §2 below for why.

---

## 2. Design fork — resolved by Mike before this spec was written

**Fork:** Requirements Agent (Stage 1) drafts a full `epic` block (title + description) in `ado-work-items.json` for every request, Enhancement or Greenfield alike — it has no concept of "this request doesn't need its own Epic." Two shapes were possible: (A) teach Requirements Agent to skip drafting an epic block for Enhancements, or (B) leave Requirements Agent untouched and have `create_ado_items.py` itself ignore the drafted epic's title/description for an Enhancement, resolving the real Epic ID from elsewhere instead.

**Resolved as (B).** Smaller blast radius — zero changes to `requirements_agent.py`, which is working correctly today and has no reason to change. The drafted epic title/description for an Enhancement was never going to be used for ADO either way; `create_ado_items.py` already owns the decision of *whether* to call `ado_helper.create_epic()` at all, so it's the natural place to also own *whether to skip it and reuse an ID instead*.

**Confirm this still holds against live `requirements_agent.py` before implementing** — if it's changed since this spec was written such that it already conditionally omits the epic block for Enhancements, adjust accordingly and flag it.

---

## 3. `create_ado_items.py` changes

### 3.1 New `--existing-service` argument

Mirror the existing pattern from `implementation_coordinator.py`/`qa_agent.py`/`security_agent.py`/`deploy_agent.py`: add `--existing-service` (default `""`, empty string means Greenfield or unresolved — same convention `enhancement_target.py`'s `resolve_service_root()` already documents).

### 3.2 New helper: resolve the existing Epic ID

```python
def _resolve_existing_epic_id(existing_service: str) -> int:
    """
    Fetches docs/<existing_service>/ado-work-items.json from pipeline-state
    and returns its epic.ado_id. Raises ValueError (caught by the same
    failure-comment path run_create_ado_items() already has) if the file is
    missing, malformed, or epic.ado_id isn't a populated int -- an Enhancement
    whose existing service has no discoverable Epic ID is a real problem
    worth surfacing loudly, not a case to silently fall back from.
    """
```

Confirm live the exact `get_file_contents()` error behavior on a missing file (404) before deciding whether to catch it separately from a JSON-parse/missing-key failure — the failure comment body should distinguish "couldn't find the existing service's ADO file at all" from "found it but `epic.ado_id` isn't populated," since a human diagnosing this will want to know which.

### 3.3 `run_create_ado_items()` — branch on `existing_service`

Add an `existing_service: str = ""` parameter. When set (truthy):
- Call `_resolve_existing_epic_id(existing_service)` instead of `ado_helper.create_epic(...)`.
- Do **not** write `payload["epic"]["ado_id"]` from a newly-created epic — write it from the resolved existing ID instead, so downstream consumers (and the committed `ado-work-items.json` itself) correctly show which real Epic this Enhancement's items live under. Consider also stamping a note (e.g. `payload["epic"]["reused_existing"] = True`) so a human reading the file later doesn't mistake the ID for one created this run — confirm this extra key doesn't break anything else that reads this file (`qa_agent.py`'s `_resolve_parent_story_id()` per its docstring only looks for `primary_user_story_id`, so should be safe, but check live).
- Everything else — creating Features under that epic ID, creating User Stories under each Feature, setting `primary_user_story_id` — is unchanged; `ado_helper.create_feature(parent_epic_id=...)` already takes an arbitrary epic ID, it doesn't care whether that epic was created this run or three weeks ago.
- Update `created_summary`'s first line accordingly (currently always `f"Epic #{epic['id']}: ..."` — for the reuse path this should read something like `f"Reused existing Epic #{existing_epic_id} (not created this run)"` so the failure-comment-on-partial-failure path, and the success log line, both read correctly).

For Greenfield (`existing_service` falsy): **zero behavior change** — this is the one thing to explicitly re-verify at the end, the same "must stay unbroken" bar every prior Enhancement-awareness fix (#24/#25/#28) held itself to.

---

## 4. `02-design.yml` — resolve and pass `--existing-service`

This workflow currently has **no** Enhancement-detection step at all (confirmed live) — every other stage (`03-implementation.yml`, `04-qa.yml`, `05-security.yml`) already has one. Add a step mirroring `04-qa.yml`'s "Determine Enhancement status and existing service" exactly (re-download the intake spreadsheet, parse `overview["request_type"]`, extract "Existing Service Name"), placed after "Resolve request ID" and before "Create ADO work items," and pass its `existing_service` output into the `create_ado_items` invocation as `--existing-service`.

Confirm live whether `02-design.yml` already has access to the intake spreadsheet download step cached from an earlier stage, or whether (like `04-qa.yml`) it needs its own fresh `download-issue-attachment` call — check before assuming either way.

---

## 5. Acceptance criteria

- A real dry-run or throwaway test issue, Enhancement-flagged, `--existing-service` pointing at a real service with a populated `epic.ado_id` in its own `ado-work-items.json`: confirm the new Features/User Stories are created as real children of that existing Epic (verify live in ADO, not just via the API response — look at the actual Epic in the ADO UI, confirm the hierarchy).
- Confirm `primary_user_story_id` still gets set correctly, and points to a User Story now correctly parented under the existing Epic.
- Confirm a Greenfield request (or an Enhancement fixture with `--existing-service ""`) still creates a brand-new Epic exactly as before — zero regression, byte-for-byte same behavior as pre-fix.
- Confirm the failure-comment path still fires correctly and readably if `_resolve_existing_epic_id()` raises (test with a deliberately bogus `--existing-service` value pointing at a service with no `ado-work-items.json`, or one missing `epic.ado_id`).
- Update `CLAUDE.md` and Backlog (flag back to Claude.ai for the Backlog update — Claude Code CLI doesn't edit that file directly) once live-verified.

---

## 6. Sequencing

1. `_resolve_existing_epic_id()` — build and unit-test against a mocked `get_file_contents()` first, independent of everything else.
2. `run_create_ado_items()` branching — wire the new helper in, confirm Greenfield path untouched via a quick dry-run against a real Greenfield fixture.
3. `02-design.yml` wiring — smallest, most mechanical piece once the Python side works standalone.
4. Full-chain live test against a real (even if throwaway) Enhancement-flagged issue, including the deliberate-failure case.
5. `CLAUDE.md` close-out; flag Claude.ai for the Backlog #32 resolution entry.

Do not touch REQ-2026-04's already-created ADO items (Epic #169 etc.) as part of this task — that's a separate, explicit decision for Mike if he wants it, not an automatic cleanup.
