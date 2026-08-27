# FORGE Context — v68

**Session date:** 2026-08-26
**Prior doc:** v67
**Prepared by:** Claude.ai, from this session's intake-drafting, live-diagnosis, and design-decision work (no Claude Code CLI execution this session — diagnosis only, no fixes built yet)

---

## Purpose & context

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment. Phase 7 (Enhancement Workflow) is open; this session picked up at Build Plan step 7.2 and ran into a real structural gap at Stage 3.

**Two-repo model (unchanged):**
- `forge-template` (public, `Flamespiker/forge-template`) — orchestration/agent code
- `forge-demo-apps` (private) — target monorepo where generated app code lands

**Firm two-tool convention (unchanged):**
- Claude.ai: strategy, spec authorship, context documents
- Claude Code CLI: live execution, git operations, CLAUDE.md updates, README.md updates
- Mike shuttles between tools and holds all unilateral architecture/scope decisions

**This session's shape:** Build Plan step 7.2 (choose + write the enhancement's intake spreadsheet), followed unexpectedly into live diagnosis when Stage 3 (Implementation) hit a real bug on first Enhancement run. No CLI execution happened this session — this is a diagnosis-and-decisions session; the actual fix is deferred to a fresh chat per the one-doc-per-chat convention.

---

## Current state

**Build Plan step 7.2 is done.** Enhancement target confirmed by Mike: a read-only coverage-history view for REQ-2026-03 (On-Call Roster Tracker), surfacing the claim/release event log already recorded per REQ-2026-03's own R-010. Intake spreadsheet drafted (`FORGE-Intake-REQ-2026-04-CoverageHistoryView.xlsx`), attached to `forge-template` tracking issue #10, `intake-ready` applied.

**Stage 0a (Ingestion) ran and correctly failed once, then passed.** First real (non-throwaway) production use of the Codebase Ingestion Agent's Layer 2 backstop — see §1 below. This is a genuine, positive validation of Phase 7's build, not a new bug.

**Stage 3 (Implementation) hit a real structural gap and was interrupted mid-run.** `implementation_coordinator.py` was never extended to handle Enhancement requests — see §2 below. This is now **Item #23**, open, not yet fixed. Stage 3 on issue #10 shows **Failed** — this is the expected, correct result of the interrupt (ADR-0011's failure-comment-then-re-raise pattern), not a separate failure to chase.

**No code changes were made this session.** Everything below is diagnosis plus one decided design fork; the fix spec is the next session's work.

---

## This session's work, in order

### 1. Intake spreadsheet drafted and one real bug caught by Stage 0a's own backstop

Drafted `FORGE-Intake-REQ-2026-04-CoverageHistoryView.xlsx` from the `Intake Template.xlsx` structure and REQ-2026-03's own intake as a style/convention reference. Overview + 5 Requirements rows (R-001–R-005), all read-only/additive, explicitly scoped to not touch REQ-2026-03's write-path concurrency logic.

**First draft had a real bug:** the "If Enhancement — Existing Service Name" cell was filled with `REQ-2026-03  (the folder name under services/ in the monorepo)` — the template's own instructional parenthetical, copied in verbatim instead of just the clean value. Stage 0a's Layer 2 mismatch backstop (built in the v67 session, tested only against throwaway issues until now) caught this correctly on the real run: `get_repo_tree()` found 0 blobs under that literal (garbled) path, logged a clear warning, and the agent raised — exactly the "fail loudly, don't guess" behavior it was built for. **This is the backstop's first real production catch, not a new problem.**

Fixed by stripping both the Existing Service Name cell (C13) and, preemptively, the Request ID cell (C4) — which had the same class of leftover-annotation text (`REQ-2026-04  (provisional — confirm actual ID with Orchestration Manager before submission)`) — down to clean values only. Corrected file re-attached to issue #10; `intake-ready` re-applied; Stage 0a re-ran clean this time.

### 2. Stage 3 structural gap discovered — Item #23

With Stage 0a and Intake/Requirements/Design presumably completed (design-approved label applied, off-screen between sessions per the normal async gate flow), Stage 3 (`implementation_coordinator.py`) started. Console session log showed the coordinator's own reasoning: `ls services/` in its sandbox came back empty, `find services/REQ-2026-03/ -type f` came back empty, `services/REQ-2026-04/` didn't exist — concluding "no pre-existing code, fresh implementation" and beginning to delegate Backend/Frontend to write from scratch.

**Root cause, confirmed by reading the live source** (`implementation_coordinator.py`, fetched via `raw.githubusercontent.com` after `api.github.com` rate-limited — same workaround v67 already used):

```python
resolved_request_id = request_id or "unknown"
service_root = f"services/{resolved_request_id}"
```

`service_root` is **always** derived from the new request's own ID, never from the Enhancement's Existing Service Name field. The coordinator's sandbox is also never populated with any existing repo content at all — no clone, no checkout, nothing beyond `design.md`/`openapi.yaml`/`tasks.md` written to `SHARED_DOCS_DIR`. This was invisible through REQ-2026-01/02/03 because all three were Greenfield, where "write fresh code into a new folder" is exactly correct. **This is the first Enhancement request to reach Stage 3**, and it exposed that Stage 3 — unlike Stage 0a and the optional-fetch retrofits in Requirements/Design — was never actually extended for the Enhancement case.

**Effect if left running:** Backend/Frontend would have hallucinated a full On-Call Roster Tracker implementation with no access to the real REQ-2026-03 code, packaged it into a brand-new, disconnected `services/REQ-2026-04/`, and opened an unusable PR — real session cost spent on unusable output.

**Action taken:** session interrupted before completion (see §3). No commit, no PR opened. Issue #10's Stage 3 now shows Failed, which is the correct, expected outcome of an interrupt under the existing ADR-0011 pattern — not a new failure mode.

### 3. Session-interrupt procedure discovered and used live

CLAUDE.md documents session *recovery* (`--recover-session`) and *archiving* in detail, but nothing on actively stopping a running session — because FORGE has never needed to before. Checked Anthropic's Managed Agents docs directly: **a running session cannot be deleted; you send a `user.interrupt` event to stop it.** Cancelling the GitHub Actions run alone does **not** stop the session — confirmed against CLAUDE.md's own existing note that killing the local polling process only orphans the runner's wait loop, not the server-side session.

Used successfully:
```bash
curl https://api.anthropic.com/v1/sessions/<session_id>/events \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: managed-agents-2026-04-01" \
  -H "content-type: application/json" \
  -d '{"events": [{"type": "user.interrupt"}]}'
```
Session confirmed killed. Mike will hand this to Claude Code CLI to add to CLAUDE.md's Managed Agents session-lifecycle section as a documented "stopping a running session" procedure — **not yet done**, flagged for CLI next.

### 4. Design fork resolved: Request ID naming convention for Enhancement requests

Surfaced explicitly rather than guessed at, per project convention. Two options:

- **Option A (decided):** Request IDs stay sequential and independent of the target service (`REQ-2026-04`, plain tracking ID). The intake template's existing two-field split — `Request ID` for tracking, `Existing Service Name` for the target folder — is the right shape; Stage 0a already reads it correctly. Item #23's fix makes Stage 3 do the same. Readability (a human wanting to see at a glance that REQ-2026-04 enhances REQ-2026-03) gets solved separately and cheaply: a "Related service: `services/REQ-2026-03`" line alongside the existing "Related FORGE tracking issue" line already written into PR bodies/tracking-issue comments — no ID, branch, or path changes needed.
- **Option B (rejected):** Version-suffixed IDs (`REQ-2026-03-v2`). Still requires code to strip the suffix before deriving `service_root` — doesn't remove the need for a code fix, just changes what it parses — and cascades further: `docs/<request-id>/` paths, `feature/<request-id>` branches, ADO area paths would all start encoding version suffixes, and concurrent enhancements to the same service would need a real versioning scheme decided now rather than deferred.

**Decision: Option A.** Item #23's fix spec should include the small PR-body/tracking-issue cross-reference addition alongside the core `service_root` fix.

### 5. Follow-up scope identified for Item #23: intake-time safeguard on Existing Service Name

Raised by Mike: even with Stage 3 fixed, a BA filling out the intake spreadsheet has no way to know which real request ID backs which app by name — today's bug (leftover annotation text in that field) is one symptom of a broader "free text, nothing validates it until pipeline run time" problem. Proposed two-layer fix, to fold into Item #23 rather than treat separately (same root cause, one step earlier):

- **Layer 1 (prevention):** Excel data-validation dropdown on "Existing Service Name," sourced from a small maintained list of real `services/` folders paired with their plain-English app names (e.g. on the Instructions tab). Eliminates typo/leftover-text bugs at the source. Requires small team-layer upkeep (one line added per new Greenfield app).
- **Layer 2 (verification, already built):** Stage 0a's Ingestion Agent backstop stays exactly as-is — real defense-in-depth against drift between the maintained dropdown list and actual repo state.

This template edit belongs to Claude Code CLI (repo-committed artifact in `forge-template/docs/`), not to Claude.ai directly.

---

## Key learnings & principles (new/updated this session)

- **A backstop's first real catch is validation, not a new problem** — Stage 0a's Layer 2 mismatch check fired exactly as designed on its first non-throwaway use. Worth remembering the difference between "the safety net caught something" and "something is broken" — they can look identical in the moment.
- **A structural gap can hide indefinitely behind a category the pipeline hasn't exercised yet** — `implementation_coordinator.py`'s Greenfield-only assumption was invisible through three real requests because all three were Greenfield. The same caution that applied to Stage 0a/Requirements/Design's Enhancement paths (built and tested against throwaway issues before trusting them) apparently didn't get applied uniformly to Stage 3 — worth a broader sweep of "was this stage actually updated for Enhancement, or does it just not error yet" before assuming Phase 7 wiring is complete end-to-end.
- **"Stop a running session" and "cancel the workflow that's watching it" are different actions with different effects** — confirmed live, not just from documentation: only `user.interrupt` against the session itself stops cost; cancelling the GitHub Actions run only stops local polling. This generalizes the project's existing "killing the local process doesn't stop the server-side session" note from a recovery scenario to an active-stop scenario.
- **Design forks surfaced before they're needed, not just when they block progress** — the naming-convention question wasn't strictly required to unblock Item #23, but resolving it now (Option A, sequential IDs) prevents Item #23's fix spec from having to guess at or later rework path/branch conventions.

---

## On the horizon

- **Item #23 (new, open):** Stage 3 (`implementation_coordinator.py`) never extended for Enhancement requests — `service_root` always resolves to the new request's own ID instead of the Enhancement's Existing Service Name, and the sandbox is never populated with the real existing code for the subagents to modify. Fix spec needed: (1) `service_root` resolution reads Existing Service Name for Enhancement requests, (2) real existing code fetched into the sandbox before Backend/Frontend/Test Writer start (likely reusing the read-only-checkout pattern the Ingestion Agent already has), (3) PR-body/tracking-issue "Related service" cross-reference line added per the Option A naming decision, (4) intake template dropdown + services-index safeguard per §5 above. **Next action: fresh chat, per one-doc-per-chat convention, to write this spec** — this is the actual next step, not 7.2 (done) or a repeat of this session's diagnosis.
- **CLAUDE.md update pending (Mike → Claude Code CLI):** document the `user.interrupt` stop procedure from §3 in the Managed Agents session-lifecycle section. Not done yet — flagged so it isn't lost.
- **Issue #10 tracking issue** currently shows Stage 3 Failed (expected, from the interrupt) — leave as-is until Item #23's fix is built and re-run; do not re-apply `design-approved` or otherwise retry Stage 3 before the fix lands, per the existing "don't just re-invoke after a kill" guidance in CLAUDE.md.
- **REQ-2026-03's Postgres server** (`forge-req2026-03-pg`) — confirm stopped if any REQ-2026-03 data was touched this session (it wasn't — this session's work was intake drafting and Stage 3 diagnosis only, no app-level DB access).
- **Carried forward, unchanged from v67:** items #1, #7, #9, #10, #11, #15 (accepted-risk/standing-procedure, no action expected); Item #22's third test case (scale-rule units, untestable until something generates one); the ad hoc admin-merge pattern (still just flagged, no new occurrences).

---

## Tools & resources (unchanged from v67)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **Azure:** Container Apps (`forge-staging`, `forge-production` environments in `forge-build-rg`), Azure Container Registry, Azure Database for PostgreSQL Flexible Server (`forge-req2026-03-pg`, Burstable B1ms, Canada Central — stop after each session), Key Vault (`forge-build-kv`), Azure AD (single-tenant app registration `FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **New this session:** `FORGE-Intake-REQ-2026-04-CoverageHistoryView.xlsx` (attached to `forge-template` issue #10); `user.interrupt` session-stop procedure (not yet in CLAUDE.md — pending)
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`, `C:\Users\mikef\Projects\forge-demo-apps`
