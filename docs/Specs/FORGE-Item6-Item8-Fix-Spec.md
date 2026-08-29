# FORGE — Item #6 (Idle-Detection / Archive-Ordering) and Item #8 (CI-Workflow Scope Creep): Spec for Claude Code

**Prepared:** 2026-08-26 (Claude.ai)
**For:** Claude Code CLI session against `forge-template` (both are pipeline/agent bugs, not `forge-demo-apps` application bugs)
**Context:** Two independent, previously-diagnosed Open Items (CLAUDE.md/context v65 #6 and #8), root-caused during a diagnosis-only session on 2026-08-25 with no fix written. Per Mike's explicit sequencing call: **#6 first, then #8.** Batched into one spec/session by explicit request — normal one-doc-per-chat convention suspended for this thread only.

**Verified against live code before this spec was written** (not from the diagnosis summary's remembered line numbers): `core/agents/utils/managed_agents_wrapper.py` (872 lines, `main` branch), `core/agents/implementation_coordinator.py` (633 lines), `core/agents/subagents/backend_agent.py`, `core/agents/design_agent.py` — all fetched live from `raw.githubusercontent.com/Flamespiker/forge-template/main/...`. Line numbers below match this fetch; confirm they still match before editing, since `main` may have moved since this spec was written.

**Standing conventions to follow (per `CLAUDE.md` / context doc):**
- Verify against the live file, not this spec, immediately before editing — `grep -n` the actual current file first.
- Windows environment: `shutil.which()` for subprocess calls, `encoding="utf-8"` on subprocess readers, no bash heredocs.
- Commit Item #6 and Item #8 **separately** — unrelated root causes in different files/layers, should not land as one commit. Within Item #6, the two sub-fixes (idle-detection data source, archive-ordering) may also warrant separate commits — Mike's call at commit time, per "commit per fix" for legible history.
- Smoke-test each fix individually before moving to the next.
- Report any design fork back to Mike rather than resolving silently.
- Do **not** update the context doc from this Claude Code session — that's Claude.ai's job at session close. Do update `CLAUDE.md`'s Open Items with what this session actually did/observed.
- Pipeline stage sequence, count, and human-gate-per-stage are all **Locked** per Document 07 — neither fix may add, remove, reorder, or skip a stage, or bypass a human gate.
- Agents never merge their own PRs — all merges are Mike's action, as always.

---

## Item #6: `wait_for_all_threads_idle()` can't distinguish real completion from budget exhaustion, and `run_implementation_stage()` archives before validating output

Two distinct, separately-fixable bugs in the same file. Confirmed live against `managed_agents_wrapper.py`.

### Bug 6a: Budget exhaustion is invisible to the idle check

**File:** `core/agents/utils/managed_agents_wrapper.py`

**Problem, confirmed live:** `wait_for_all_threads_idle()` (line 596) polls only `get_thread_statuses()` (line 575), which hits `GET /sessions/{id}/threads` and reads the bare `status` field. Status values are bucketed into three module-level constants (lines 155–157):

```python
_THREAD_IDLE_STATUSES = {"idle"}
_THREAD_BUSY_STATUSES = {"running", "rescheduling"}
_THREAD_FATAL_STATUSES = {"terminated"}
```

The completion check (lines 644–657) is: log a warning if any thread is `terminated` (but does **not** treat that as blocking), then return success the moment no thread is in `_THREAD_BUSY_STATUSES`. A thread that hit its budget cap goes idle — its `status` field reads `"idle"`, identical to a thread that finished its work normally. The only place this distinction exists is the event stream (`session.thread_status_idle` events carry a `stop_reason: budget_reached` field), which this function never queries — it only ever calls the lightweight `/threads` endpoint, by design (its own docstring explains this was deliberate, to avoid `get_subagent_audit_trail()`'s expensive per-thread event fetch in a tight polling loop).

`poll_until_idle()` (line 348) *does* scan events, but only checks `stop_reason.type == "requires_action"` (lines 407–414) — it has no `budget_reached` branch either, and it's only checking the **coordinator's own** session-level idle event, not per-thread subagent events, so even if it had a `budget_reached` branch it wouldn't catch a subagent-level budget exhaustion.

**Net effect:** a Stage 3 run where a subagent silently exhausts its budget partway through is reported as a clean, successful completion.

**Fix design:**
1. Add a `budget_reached` branch to `poll_until_idle()`'s existing stop_reason check (alongside the existing `requires_action` branch, lines 406–414) — this covers the coordinator's own session-level budget exhaustion, which is a distinct (simpler) case from the per-thread one below. Raise a new `SessionBudgetExhaustedError` rather than folding this into the existing generic `RuntimeError` for `requires_action` — callers need to distinguish "genuinely stuck waiting for a tool confirmation" from "ran out of budget," since the operationally correct response differs (the former is a FORGE misconfiguration bug per the existing docstring; the latter may just mean the budget ceiling needs raising for this class of request).
2. Give `wait_for_all_threads_idle()` a second data source for per-thread budget exhaustion. The lightweight `/threads` endpoint has no `stop_reason` field to read — that only exists in the event stream. Two options, pick based on what's actually available (confirm live against the real API, don't assume):
   - **Option A (cheaper):** extend `get_thread_statuses()` to also surface whatever budget/stop-reason signal the `/threads` endpoint itself might expose per-thread, if the API has added one since this function was written (check current API docs/response shape live — the diagnosis session confirmed `budget_reached` lives in the *event* stream at time of writing, but re-verify before assuming that's still the only place).
   - **Option B (matches current confirmed reality):** when `wait_for_all_threads_idle()` is about to return success (i.e., no threads in `_THREAD_BUSY_STATUSES`), do one `get_subagent_audit_trail()` call (already exists, already used elsewhere) to check the per-thread event stream for any `stop_reason: budget_reached` before declaring success — this is the "expensive per-thread event fetch" the function's docstring says to avoid *in the polling loop*, but doing it exactly once, only at the point of declaring success, is a different cost profile than polling it every interval. Confirm the actual per-call cost/latency live before committing to this approach over Option A.
3. If a `budget_reached` stop_reason is found on any thread, raise `SessionBudgetExhaustedError` (same new exception type from step 1) rather than returning success. This must propagate up through `run_implementation_stage()`'s exception handling (see Bug 6b below) as a genuine failure, not as `SessionStillRunningError` (which means "still working, don't archive yet, come back later" — a budget-exhausted thread is never coming back).
4. Do not change the existing `_THREAD_FATAL_STATUSES` (`terminated`) handling — that's a separate, already-correctly-logged case (line 646's warning), out of scope for this fix.

### Bug 6b: `run_implementation_stage()` archives unconditionally, with no validation gate

**File:** `core/agents/utils/managed_agents_wrapper.py`, function `run_implementation_stage()` (line 756), specifically lines 850–855:

```python
    # Fetch the audit trail before archiving -- an archived session's threads
    # may not remain queryable (unconfirmed either way; safer to fetch first,
    # matching the original working order).
    audit_trail = get_subagent_audit_trail(session_id)
    final_status = _get(f"sessions/{session_id}")
    archive_session(coordinator_id, environment_id, session_id, subagent_ids)
```

**Problem, confirmed live:** the fetch-before-archive *ordering* is actually already correct (line 851–852 fetch before line 855 archives) — this differs slightly from the diagnosis session's shorthand phrasing ("archives before checking output"). The real gap is that nothing between the fetch and the archive call **validates** what was fetched. `audit_trail` and `final_status` are captured and returned to the caller, but `run_implementation_stage()` archives regardless of their content — there is no check here for "did a real `implementation.tar.gz` actually get produced."

The caller, `run_implementation_coordinator()` in `implementation_coordinator.py` (lines 471–491), is the place that actually checks for the output archive — but it does so **after** `run_implementation_stage()` has already returned, which means **after** the session has already been archived at line 855. By the time the caller discovers `archive_meta is None` (line 483) and raises, the session is gone. This matches the live corroborating incident from the Item #12 cost-log backfill: a $9.12 Stage 3 session with no `implementation.tar.gz` produced, archived anyway.

Compare this to `recover_implementation_session()` (`implementation_coordinator.py`, line 354), which gets this right: it checks `list_session_output_files()` for the archive **before** calling `archive_session()` (lines 406–413 check, archive call at line 433, after the commit succeeds) — if there's no archive, it raises before ever touching `archive_session()`, leaving the session alive and inspectable.

**Fix design:**
1. Move the output-archive existence check that currently lives in `run_implementation_coordinator()` (lines 479–488 of `implementation_coordinator.py`) into `run_implementation_stage()` itself, **before** the `archive_session()` call at line 855 — this is the actual "check for real output before archiving" gate `recover_implementation_session()` already has, applied to the happy path.
2. `run_implementation_stage()` currently lives in `managed_agents_wrapper.py`, a lower-level module that doesn't import `_ARCHIVE_FILENAME` or `list_session_output_files()`'s calling convention the way `implementation_coordinator.py` does — check whether `list_session_output_files()` (already defined in `managed_agents_wrapper.py`, line 500) is enough on its own, or whether the check needs the archive-filename constant passed in as a parameter (`run_implementation_stage()` doesn't currently know the filename `implementation.tar.gz` — that constant lives in `implementation_coordinator.py`). Decide live which module should own this check — moving it down into `managed_agents_wrapper.py` (generic wrapper) vs. keeping it in the caller but reordering so the caller's check runs before its own call into `archive_session()` rather than relying on `run_implementation_stage()`'s internal archive call. **This is a real design fork — of the two options below, pick one and state which, don't resolve silently:**
   - **Option A:** `run_implementation_stage()` takes an optional `expected_output_filename` parameter (default `None` = skip the check, preserving behavior for any other future caller that doesn't produce a single named archive), checks for it via `list_session_output_files()` before archiving, and raises a clear `RuntimeError` if absent — mirroring `recover_implementation_session()`'s existing error message pattern (`f"Session {session_id} is idle but produced no '{filename}' in /mnt/session/outputs/. Files present: {...}. This session genuinely failed -- not recoverable by this tool."`, adapted for the non-recovery happy path).
   - **Option B:** leave `run_implementation_stage()` archive-agnostic (its current generic-wrapper design, reusable beyond just the Implementation Coordinator), and instead have `run_implementation_coordinator()` do its own archive-existence check **before** calling into whatever triggers the archive — meaning `run_implementation_stage()` would need to stop archiving internally and instead return control to the caller between "confirmed idle" and "archive," with the caller responsible for calling `archive_session()` itself once it's validated output. This is a larger structural change (moves the archive call out of the convenience wrapper) but keeps validation logic where the archive-filename knowledge already lives.

   **Recommendation: Option A.** It's a smaller, additive change (one new optional parameter, no callers broken), and it makes `run_implementation_stage()`'s existing "convenience wrapper: create, send, wait, retrieve, clean up" contract genuinely complete rather than silently incomplete. Option B is architecturally cleaner but touches more call sites for a benefit (reusability for a hypothetical future non-archive-producing caller) FORGE doesn't currently need. If Claude Code's own read of the code suggests Option A doesn't fit cleanly, raise that back to Mike rather than defaulting to Option B unprompted.
3. Whichever option is chosen, the resulting behavior must match: if the completion is genuine (all threads idle, no budget exhaustion per Bug 6a's fix) but no real output was produced, `run_implementation_stage()`/its caller must **not** archive the session — raise a clear, diagnosable error and leave the session alive, exactly as `recover_implementation_session()` already does for its own no-archive case. This preserves the evidence trail (session remains inspectable/recoverable) instead of destroying it.
4. Confirm the existing `except Exception` block in `run_implementation_stage()` (lines 834–848) — the one that already does a best-effort `archive_session()` on genuine failures like `session.error`/`terminated`/`requires_action` — is not accidentally re-triggered or double-archiving once the new pre-archive validation is added. That except block currently only fires on failures from `poll_until_idle()`/`wait_for_all_threads_idle()` themselves (lines 826–828 are inside the `try`), not from anything after them — the new validation check should raise from a point that's either inside that same `try` (so the existing cleanup logic handles it) or its own distinct `except`, not silently bypass cleanup. Trace this carefully against the real control flow, don't assume.

### Acceptance criteria (Item #6, both bugs)

- Construct a scoped local test harness that mocks the Managed Agents API (events + threads endpoints) rather than trying to trigger a real budget-exhaustion run on demand (expensive, non-deterministic, hard to reproduce reliably) — this matches the pattern already used for Item #5's retry-ceiling logic. Confirm: (a) a thread reporting `stop_reason: budget_reached` in its event stream causes `wait_for_all_threads_idle()` to raise `SessionBudgetExhaustedError` rather than reporting success, and (b) `run_implementation_stage()`/its caller does not archive the session in that case.
- Same harness: confirm a genuinely idle-and-complete session (no budget exhaustion, real output present) still succeeds and archives exactly as before — no regression to the working path.
- Same harness: confirm a genuinely idle session with **no output produced** (the corroborating live incident's shape) raises a clear error and does **not** archive, leaving the session recoverable — this is the actual bug that destroyed evidence; confirm it's closed.
- Re-run a real, cheap Stage 3 dry-run (or the smallest real request available) end-to-end to confirm no regression to the normal happy path outside the mocked-failure scenarios — live verification, not just the mocked harness, per the project's standing "verify before trusting" principle.
- Update `CLAUDE.md`'s Item #6 entry to RESOLVED with the real fix narrative, including which design-fork option was taken for Bug 6b and why.

---

## Item #8: Implementation Coordinator sometimes generates unrequested `.github/workflows/*.yml` scope creep

**Files:** `core/agents/design_agent.py` (root-cause layer), `core/agents/implementation_coordinator.py` (defensive-guard layer).

**Problem, confirmed live (root cause, from the 2026-08-25 diagnosis session, re-verified against live code for this spec):** two real historical incidents (REQ-2026-01 commit `3397617`, cleaned up in `0f5f1c5`; REQ-2026-02 commit `47b3fef`, cleaned up in `ba3b3a7`) where a Stage 3 subagent wrote a `.github/workflows/*.yml` file nested under `services/<request-id>/.github/workflows/...` — technically legal per every rule currently in force, but not what anyone wanted, since a workflow file nested inside a service directory has no effect as CI (GitHub only recognizes `.github/workflows/` at repo root).

Two rules genuinely can't both be satisfied when this happens:
- `design_agent.py`'s `_SYSTEM_PROMPT` (lines 105–109, confirmed live) asks for `tasks.md` items under three headings ("Backend", "Frontend", "Test Writer"), with no restriction on what kind of deliverable each task item can describe — nothing prevents the model from writing a task like "add a CI workflow for X" as if it were a normal Backend/Frontend task item, and nothing in the prompt tells it such an item is out of scope for Stage 3 entirely (CI workflows are fixed pipeline infrastructure owned by `forge-template`, not something regenerated per-request).
- `backend_agent.py`'s `SYSTEM_PROMPT` (confirmed live) has an absolute rule: "Write your files directly under the target directory the coordinator gives you (e.g. `<target>/backend/...`) — do not write outside it." Combined with `frontend_agent.py`'s presumably identical constraint, a subagent handed a task item describing a repo-root artifact can only satisfy both rules by nesting it inside its own confined directory — which is exactly what happened, twice.

**Gap spans two layers, confirmed:** Design Agent proposes an out-of-scope deliverable without knowing it's out of scope; Stage 3 has no logic anywhere to recognize and reject a task item that targets outside its writable area, or a resulting archive member that shouldn't have been produced at all.

### Fix design

**Layer 1 — prevent it at the source (Design Agent prompt):**

1. Add an explicit scope boundary to `design_agent.py`'s `_SYSTEM_PROMPT`, in the `tasks.md` section (currently lines 105–109). State plainly that `tasks.md` task items must describe only files that live under `services/<request-id>/` (backend/frontend/tests) — CI/CD workflows, pipeline configuration, and any other repository-root infrastructure are owned by the FORGE template itself, are already fixed for every request, and must never be proposed as a task item for the Backend, Frontend, or Test Writer subagents to build.
2. If `design.md`'s own architecture narrative (the C4-model section, lines 83–98) has legitimate reason to *mention* CI/CD as part of the tech-choices narrative (it already states "GitHub Actions" as a fixed core-layer mandate, line 91) — that's fine and unrelated; the fix is scoped specifically to `tasks.md`'s per-subagent task items, not to removing CI/CD from the architecture discussion entirely.
3. This is a prompt-only change — no code logic needed for Layer 1, but it depends on the model actually following the new instruction. Layer 2 below is the backstop for when it doesn't.

**Layer 2 — defensive guard at extraction time (belt-and-suspenders, catches it even if Layer 1's prompt guidance is imperfect):**

4. `implementation_coordinator.py`'s `_extract_archive_to_file_dict()` (line 149) already has a precedent for strict rejection of unwanted archive content — the `expected_prefix` check (lines 183–189) already skips (with a warning) any archive member outside `services/<request-id>/`, following the deliberate "strict rejection, no auto-remap" policy documented in that function's own docstring (the REQ-2026-02 remap-fallback-then-revert precedent, lines 168–175).
5. Add a second, narrower rejection rule in the same function: any archive member whose path (after the `expected_prefix` check already passes) contains a `.github/` path segment should be skipped with a warning, same pattern as the existing prefix check — logged clearly enough that a human reviewing the PR/build log can see exactly what was dropped and why, matching the existing style: `"Archive member '%s' is a nested .github/ path -- skipping (CI/workflow files are owned by forge-template, not generated per-request)."`
6. Do not silently promote a `.github/`-nested file to the real repo-root `.github/workflows/` location as an auto-fix — that's a meaningfully different, higher-stakes action (writing to a path outside `services/<request-id>/` for real) than this fix's scope, and should never happen without a human deciding to add a new CI workflow deliberately. Follow the same "strict rejection over silent correction" philosophy already established for the `expected_prefix` guard.
7. This guard belongs in `_extract_archive_to_file_dict()` specifically (not `_sanity_check_extracted_files()`, which only counts files/bytes and doesn't inspect individual paths) — confirm this placement live against the actual function boundaries before implementing, since the two functions' responsibilities should stay cleanly separated.

### Acceptance criteria (Item #8)

- Confirm the updated `design_agent.py` prompt change with a real (or realistically-scoped test) Design Agent run against a request whose requirements might plausibly tempt a CI-related task item — confirm `tasks.md` no longer proposes one.
- Construct a deliberately adversarial test archive (a `.tar.gz` fixture with a `.github/workflows/fake.yml` member nested under a valid `services/<request-id>/` prefix) and confirm `_extract_archive_to_file_dict()` skips it with a clear warning, while still correctly extracting every other legitimate file in the same archive — this is the regression-proof test for Layer 2, independent of whether Layer 1's prompt change actually prevents the model from generating it in the first place.
- Re-run against a normal, legitimate archive (no `.github/` content) and confirm zero behavior change — the new check must not accidentally match anything that isn't actually under a `.github/` segment (e.g. a legitimately named file or directory containing "github" as a substring elsewhere in its path should NOT be caught by this rule — match on the actual path segment, not a substring).
- Update `CLAUDE.md`'s Item #8 entry to RESOLVED with the real fix narrative — both layers, and note this is a prevention + backstop pair, not a single fix, since either layer alone leaves a gap (Layer 1 alone still trusts the model; Layer 2 alone still lets a bad `tasks.md` item get generated even though it's caught before commit).

---

## Sequencing and session structure

1. **Item #6 first** (Bug 6a, then Bug 6b — 6a is the simpler, more self-contained fix; 6b depends on 6a's new `SessionBudgetExhaustedError` existing so its error handling has something correct to distinguish against). Commit separately from #8. Full acceptance criteria above before moving on.
2. **Item #8 second.** Commit separately from #6, and consider whether Layer 1 (prompt) and Layer 2 (extraction guard) warrant separate commits too — they're independently testable and independently valuable (Mike's call at commit time).
3. **CLAUDE.md close-out** — after both land, update both items to RESOLVED with real fix narratives, matching the strikethrough-and-RESOLVED formatting convention used for prior closed items.
4. Do not scope-creep into any of the "accepted, no fix needed" items from this session's earlier review (#1, #7, #9, #10, #15) — those are explicitly out of scope for this spec.
