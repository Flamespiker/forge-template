# FORGE — Extend Stage 3 (Implementation) for Enhancement Requests (Item #23): Spec for Claude Code

**Prepared:** 2026-08-27 (Claude.ai)
**For:** Claude Code CLI session against `forge-template` (workflow + agent code) and
`docs/Intake Template.xlsx` (template safeguard), with live verification against
`forge-demo-apps` and the pending GitHub tracking issue #10.
**Context:** Item #23 in the Open Items backlog — "Stage 3 never extended for Enhancement
requests." Phase 7 step 7.1 (Codebase Ingestion Agent, Stage 0a) is done and
live-verified (2026-08-27) — Requirements and Design already get real existing-code
context on an Enhancement request. Stage 3 (`implementation_coordinator.py`) does not:
it always resolves `service_root` from the **new** `request_id` and always hands
subagents an empty directory, so an Enhancement's implementation would land in a brand
new `services/<request_id>/` folder instead of the real existing service, and the
subagents would have no view of the code they're supposed to be modifying. This is
Build Plan step 7.6's actual acceptance bar ("confirm the enhancement lands on the
correct existing `services/<n>/` folder, not a new one") and blocks GitHub tracking
issue #10, which has been sitting at "Stage 3 Failed" since v68's interrupt, deliberately
left alone pending this fix.

**Standing conventions to follow (per CLAUDE.md / context doc):**
- Verify every current file/behavior live before writing code — this spec's read of
  `implementation_coordinator.py`, `03-implementation.yml`, and `managed_agents_wrapper.py`
  is from CLAUDE.md's notes and may have drifted.
- Windows environment: `shutil.which()` for subprocess calls, `encoding="utf-8"` on
  subprocess readers, no bash heredocs.
- `invoke_agent()` / equivalent stays wrapped per the ADR-0011 try/except-then-raise
  contract; any new failure path posts a best-effort comment first.
- Report every design fork back to Mike rather than resolving silently — this spec
  deliberately leaves some open (see §3).
- Commit each of the pieces in §2 **separately**, verified against real `git diff HEAD`.
- Do not touch Items #1, #7, #12, or Build Plan steps 7.2/7.3 (choosing/writing the
  actual enhancement content) — those are explicitly out of scope here.

---

## 1. Investigate first (do this before designing anything)

Per the project's "verify against the live file, don't assume" discipline, confirm all
of the following live before writing the fix — several later decisions depend on the
answers:

1. **Current `03-implementation.yml`** — read it in full. Confirm it currently has no
   Enhancement-detection step (unlike `00-intake.yml`, which does), and confirm exactly
   what it currently passes to `implementation_coordinator.py`.
2. **`implementation_coordinator.py`'s actual current `service_root`/target-dir
   resolution** — confirm it's unconditionally `services/<request_id>/` with no
   Enhancement branch, per CLAUDE.md's notes.
3. **Coordinator's tool access vs. subagents'** — `DEFAULT_SCOPED_TOOLS` (offline,
   `web_search`/`web_fetch` disabled) is documented for the three specialists. Confirm
   whether the **coordinator** session uses the same scoped toolset or a broader one —
   this determines whether the coordinator could ever fetch/write existing code itself
   mid-session versus needing it pre-seeded before the session starts.
4. **Whether `managed_agents_wrapper.py` (or the underlying Managed Agents API) supports
   seeding files into the sandbox before/at session creation**, the mirror image of the
   already-used Files API *download* path (`list_session_output_files` /
   `download_file_content`). Check the Managed Agents API docs and any existing
   upload/seed helper. This is the single most load-bearing unknown in this spec — the
   sandbox-population design in §2.2 cannot be finalized without this answer.
5. **`workflow_glue.py`'s `download-issue-attachment` and Overview-parsing path**
   (`file_io.py`) — confirm the exact subcommand signatures already used by
   `00-intake.yml`'s "Determine Enhancement status" step, since §2.1 proposes reusing
   them rather than inventing a new mechanism.
6. **GitHub tracking issue #10's current live state** — confirm it still shows Stage 3
   Failed as noted in context v69, and pull its Enhancement metadata (existing service
   name, request ID) so it can be reused as the live verification vehicle in §5 instead
   of spinning up a fresh throwaway request.

Report findings from this section back before proceeding if anything contradicts the
assumptions below — in particular, if #4 comes back negative (no seed-file capability
exists), the sandbox-population design needs a different shape than proposed in §2.2
and that's a design fork, not something to route around silently.

---

## 2. Scope

### 2.1 Enhancement detection + `service_root` resolution

**Goal:** Stage 3 knows, before the coordinator session starts, whether this is an
Enhancement request and — if so — which existing `services/<n>/` folder is the real
target.

**Proposed approach (mirrors `00-intake.yml`'s already-working, already-live-verified
pattern — reuse over reinvention):**
- Add a "Determine Enhancement status" step to `03-implementation.yml`, structurally
  parallel to `00-intake.yml`'s: re-download the intake spreadsheet via
  `workflow_glue.py download-issue-attachment`, parse `request_type` and the "If
  Enhancement — Existing Service Name" Overview field via the existing `file_io.py`
  parsing (same canonical-key dict already used elsewhere — no new parsing logic).
- Pass the resolved value to `implementation_coordinator.py` as a new optional
  `--existing-service` flag, exactly mirroring `ingestion_agent.py`'s existing CLI
  shape.
- Inside `implementation_coordinator.py`: if `--existing-service` is present,
  `service_root = services/<existing_service>/` and the feature branch stays
  `feature/<request_id>` (the *new* request's ID — branch naming doesn't change,
  only the file-tree target does). If absent, current Greenfield behavior
  (`services/<request_id>/`) is unchanged.
- Reuse the Layer 2 "strict rejection over silent auto-remap" precedent from Ingestion
  Agent / Open Item #8: if `--existing-service` is given but
  `github_helper.get_repo_tree(f"services/{existing_service}/")` comes back empty,
  raise (don't guess, don't silently fall back to `request_id`) and post a failure
  comment before re-raising, same ADR-0011 contract every other agent follows.

**Considered and not chosen (flag to Mike, don't silently pick if the live
investigation in §1 changes the calculus):** embedding the resolved `existing_service`
value inside `design.md` itself (which Stage 3 already reads) instead of re-deriving it
from the spreadsheet. Rejected as the default because it would require modifying the
already-shipped, already-live-verified Design Agent output format for a value it has no
independent need to carry, and because re-downloading the spreadsheet is a proven path
with zero new failure surface. Worth re-raising only if §1's investigation surfaces a
concrete reason the spreadsheet re-download is unreliable by Stage 3 time (e.g. the
attachment having been edited or removed between Intake and Implementation).

### 2.2 Sandbox population with real existing code

**Goal:** when `service_root` resolves to an existing service, the Backend/Frontend/Test
Writer subagents see the real current code at that path before they start working, not
an empty directory.

**This design is intentionally left unfinished pending §1.4's investigation.** Two
shapes are possible depending on what the Managed Agents API actually supports:

- **If a seed-files-at-session-creation mechanism exists:** fetch the existing service's
  full file tree + contents via `github_helper.get_repo_tree()` (reusing/adapting
  Ingestion Agent's own tree-walk and noise-filtering logic — `node_modules`/`bin`/
  `obj`/`.next`/`dist`/`coverage`/`.git` exclusions already proven there) from Python,
  before `create_agent_session()`, and seed them into the sandbox at `service_root`
  via that mechanism.
- **If no such mechanism exists:** this needs a genuine design decision — e.g. giving
  the coordinator itself a scoped, read-only fetch capability for exactly this one
  path (a real toolset change, more invasive) versus some other shape not yet
  considered. **Do not invent a workaround silently — report back to Mike with what §1
  found and what the real options are before writing this piece.**

Either way, the **existing-file budget should follow the same two-pass,
budget-conscious pattern Ingestion Agent already established** (manifests/config files
always in full, remaining source files filling a bounded budget by size) rather than a
naive full-tree dump, since Enhancement services are real production code and could be
large.

**Packaging on the way out is unaffected** — the coordinator already tars the entire
`service_root` tree into `implementation.tar.gz` regardless of whether that tree started
empty or pre-populated, and `commit_files()` re-writing identical content for
untouched files is a no-op diff. Confirm this holds rather than assuming it.

### 2.3 PR-body / tracking-issue "Related service" cross-reference line

**Goal:** human traceability — a reviewer looking at the Stage 3 PR or the tracking
issue comment should be able to see at a glance which existing service this
Enhancement targeted, the same way `Related FORGE tracking issue:
Flamespiker/forge-template#N` already gives that traceability for tracking-issue
linkage.

- When `--existing-service` is set, add a line to both the draft PR body and the
  tracking-issue summary comment the coordinator already posts, e.g.:
  `Related service: services/<existing_service>/`
- Omit the line entirely on a Greenfield run — don't print an empty/placeholder
  version of it.

### 2.4 Intake-template dropdown safeguard

**Goal:** reduce typo risk in the "If Enhancement — Existing Service Name" free-text
field at the point of BA entry, as defense-in-depth alongside (not instead of) Ingestion
Agent's existing Layer 2 raise-on-mismatch backstop.

- Edit `docs/Intake Template.xlsx` (in `forge-template`) to add Excel data validation
  (a dropdown list) on that cell, populated with the real current service folder names
  (`REQ-2026-01`, `REQ-2026-02`, `REQ-2026-03` as of today).
- Do this via `openpyxl`'s data-validation API in a small standalone script, same
  category of change as the earlier "Existing Service Name" example-text fix — its own
  commit, separate from the code changes in §2.1/§2.2/§2.3.
- **Known, accepted limitation — not a fork, just note it in the commit message:** this
  list is static and will need manual maintenance as new services ship. No attempt to
  make it dynamic; the medium (an Excel dropdown) doesn't support that cheaply, and the
  Layer 2 backstop already exists precisely to catch the case where this list drifts
  out of date.

---

## 3. Design forks explicitly surfaced (Mike's call, not Claude Code's)

1. **§2.1's spreadsheet-re-download approach vs. embedding `existing_service` in
   `design.md`** — recommended default is the spreadsheet re-download; revisit only if
   §1's investigation finds a concrete reliability problem with it.
2. **§2.2's sandbox-population mechanism** — genuinely undecided pending §1.4's live
   investigation. Report back with findings and concrete options rather than picking
   one and proceeding.

Do not resolve either of these by inference — bring them back explicitly if the
investigation doesn't make the answer obvious.

---

## 4. Out of scope

- Build Plan steps 7.2/7.3 (choosing and writing the actual enhancement's intake
  content) — a separate Mike decision, not part of this mechanism fix.
- Any change to ADO bug/parent-linking logic (Build Plan 7.7) — that's downstream of
  this fix working, not part of it.
- Items #1, #6, #7, #8, #12 — untouched, unrelated.
- Re-litigating Ingestion Agent (Stage 0a) itself — it's done, live-verified, and not
  part of this spec's surface area.

---

## 5. Live verification

**Use GitHub tracking issue #10 as the verification vehicle rather than spinning up a
new throwaway request** — it's a real Enhancement request already sitting at "Stage 3
Failed" specifically waiting on this fix (confirmed still in that state per §1.6). Once
the fix lands:

1. Confirm issue #10's Enhancement metadata (existing service, request ID) live rather
   than assuming it matches any value mentioned in this spec.
2. Re-apply `design-approved` (per context v69's explicit instruction not to do this
   until the fix lands) and let Stage 3 run for real.
3. Confirm the resulting PR lands its files under the **correct existing**
   `services/<n>/` folder, not a new one — this is Build Plan 7.6's literal acceptance
   criterion.
4. Confirm the PR body and tracking-issue comment carry the new "Related service" line.
5. Confirm a genuinely new Greenfield run (any recent or throwaway Greenfield request)
   is completely unaffected — no `--existing-service` flag, no behavior change, same as
   today.
6. Report the live evidence (PR link, commit SHA, before/after folder path) back
   explicitly — same "real executed evidence before closing" bar as every other item.

Do **not** treat a passing `--dry-run` as sufficient here — §2.2 in particular has no
cheap substitute for a real Managed Agents session, same reasoning already established
for why Stage 3's own tests have always required a real run.

---

## 6. Sequencing

1. §1 investigation — all six points, reported back before any code is written.
2. §2.4 (intake template dropdown) — cheap, standalone, do it early per the project's
   own "do the cheap standalone piece early so it doesn't get forgotten" pattern from
   the Ingestion Agent spec.
3. §2.1 (Enhancement detection + `service_root` resolution) — foundational; §2.2 and
   §2.3 both depend on `--existing-service` existing and being correctly resolved.
4. §2.2 (sandbox population) — the hard, investigation-gated piece. Do not start
   writing this until §1.4's answer is in hand.
5. §2.3 (PR-body / tracking-issue line) — small, layers on top of §2.1 and the
   coordinator's existing PR/comment posting code.
6. §5 live verification via tracking issue #10.
7. `CLAUDE.md` close-out: mark Item #23 resolved with the real fix narrative and live
   evidence; update Build Plan v9's step 7.6 status note (still `[ ]` — 7.6 itself isn't
   satisfied until a real enhancement runs end-to-end per 7.2–7.8, but note that the
   mechanism blocking it is now fixed and verified via issue #10).

---

## Next chat after this one (Claude.ai)

Once Claude Code reports back with live-verification evidence from issue #10, fold the
outcome into a fresh context doc (v70), close Item #23 in the backlog, and return to
Build Plan step 7.2 — confirming the proposed enhancement target (REQ-2026-03 read-only
coverage-history view) with Mike before writing that enhancement's intake spreadsheet.
