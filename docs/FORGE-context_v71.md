# FORGE Context — v71

**Session date:** 2026-08-28
**Prior doc:** v70
**Prepared by:** Claude.ai, from this session's spec authorship + Claude Code CLI's live execution, incident handling, and root-causing (relayed back into this chat)

---

## Purpose & context

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment.

**Two-repo model (unchanged):**
- `forge-template` (public, `Flamespiker/forge-template`) — orchestration/agent code
- `forge-demo-apps` (private) — target monorepo where generated app code lands

**Firm two-tool convention (unchanged):**
- Claude.ai: strategy, spec authorship, context documents
- Claude Code CLI: live execution, git operations, CLAUDE.md updates
- Mike shuttles between tools and holds all unilateral architecture/scope decisions

**This session's shape:** v70's flagged next target — **Item #25 (QA/Security have no Enhancement-target awareness)** — tackled end-to-end. What started as a four-part fix (shared target-resolution helper, QA fail-loud fix, Security fail-loud fix, a real latent Dependabot-filter bug) surfaced, mid-verification, two more real bugs the fix itself exposed: an incomplete Priority 1 (a workflow-level bash step independently reconstructing the same stale path), and a genuinely pre-existing, previously-undiscovered stale-label-clearing bug. Both got fixed, both got their own commits, both got logged as their own items. A real live re-dispatch against the same PR #32/issue #10 evidence from last session confirmed everything end-to-end for real — including a second live confirmation of Item #26's still-open gap (Deploy auto-fired, raised cleanly, no Azure impact).

**One process note this session, worth naming:** an instruction to "close ADO Bug #178 with a note" was executed literally as written, but the phrasing genuinely supported two readings (close-with-explanation vs. annotate-while-leaving-open) on something touching a real external system of record. Flagged and discussed rather than silently left — the standing lesson (see below) is to flag ambiguity on anything touching a record outside FORGE's own repos before acting, even when one reading feels more likely.

---

## Current state

**Item #25 is resolved and closed in CLAUDE.md.** Full resolution, four priorities plus two mid-session discoveries:

- **Priority 1 (§2.1) — shared Enhancement-target resolution.** New `core/agents/utils/enhancement_target.py` with `resolve_service_root(request_id, existing_service)`; both `04-qa.yml` and `05-security.yml` gained a "Determine Enhancement status" step mirroring `03-implementation.yml`'s own (spreadsheet re-download, not comment-line parsing — the recommended default from the spec's own design fork, confirmed with no reason to deviate); `qa_agent.py`/`security_agent.py` both gained a new `--existing-service` flag.
- **Priority 2 (§2.2) — QA's real bug, fixed.** QA previously **false-positive-passed** an Enhancement request with zero real test coverage — its existing `not_applicable` handling couldn't distinguish "genuinely no tests" from "looking in a directory that doesn't exist at all." Fixed: a directory-existence check now runs *before* `_resolve_backend_test_dir()`/`_frontend_test_script_exists()` are ever called (not wrapped around their results, since both silently no-op either way) — missing target raises `EnhancementTargetNotFoundError`, ADR-0011 comment-then-reraise, does **not** count against the 3-attempt retry budget (confirmed default per the spec's own fork).
- **Priority 3 — Dependabot manifest-path filter, a real latent bug caught before it could bite.** `_run_dependabot_check()` built its filter prefix independently from raw `request_id`, never touching the resolved target at all — confirmed unreachable *only* because Security's earlier crash aborted the run first; would have silently returned zero findings against the wrong path the moment the crash was fixed. Fixed to use the resolved target.
- **Priority 4 (§2.3) — Security's failure mode, clarified rather than newly fixed.** Live investigation corrected the spec's own framing here: Security's missing-directory crash was **already caught** by the existing outer ADR-0011 try/except — a real comment was already posted, `security-approved` was already correctly withheld, the job already failed loud. The actual gap was a raw Python exception string in that comment instead of a message naming the real problem. Fixed: a clear "could not run" comment plus a distinct check-run title ("blocked — target directory not found").
- **Priority 5 (§2.4, Greenfield-unaffected) — confirmed via existing evidence, no new live dispatch.** Scoped regression tests (real function calls, not just diffs) covering the "directory exists, `existing_service` unset" case, combined with last session's real live baseline (PR #27/REQ-2026-01, 2026-08-25) which already showed correct pre-fix Greenfield behavior. Explicitly decided *not* to re-dispatch PR #27 live for this check — doing so would have refiled duplicate ADO Bugs for 6 known pre-existing frontend Jest failures and risked a surprise redeploy, for zero additional evidence value over what already existed.

**Two real bugs discovered mid-verification, not part of the original spec, both fixed and logged:**

- **Item #27 — `04-qa.yml`'s "clear stale label on pass" step checked current label presence, not this run's own outcome.** Newly exposed (not caused) by this session's fix: after a stale, unpushed re-dispatch (see incident below) left a leftover `qa-approved` sitting on issue #10, this step saw that stale label, assumed a fresh pass, and deleted the freshly-and-correctly-applied `qa-loop-back` label the real run had just set — leaving the issue in an inaccurate all-clear state. Root logic fixed to key off this run's own actual outcome; re-verified on the final clean dispatch (cleanup step correctly found nothing stale to remove because the pass was genuine).
- **A second, distinct gap in Priority 1 itself — `04-qa.yml`'s separate "Install frontend dependencies" step.** This bash step independently reconstructed `frontend_dir` from raw `request_id`, never updated to use the resolved `existing_service` — Priority 1's Python-level fix (`qa_agent.py`) was correct, but this workflow-level step wasn't touched by it. Effect: `npm install` silently skipped ("no frontend package.json... skipping"), so when the now-correctly-pointed `qa_agent.py` tried `npm run build` against the real `services/REQ-2026-03/frontend`, it failed on a missing `next` binary — producing a real, misleadingly-app-defect-shaped ADO Bug (#178). Fixed by resolving `frontend_dir` the same way `qa_agent.py` now does; re-verified live (695 packages installed, real build success).

**Repeated procedural incident, same shape as Item #24's earlier one:** a first re-dispatch attempt after the fix was made without confirming the push had landed on `origin/main` first — the run executed stale code, reproduced the original crash/false-pass, and re-applied the stale `qa-approved` that triggered the Item #27 discovery above. Caught, root-caused, both fixes then verified live via the GitHub API (real commit SHAs confirmed present on `origin/main`) before the final, clean re-dispatch.

**Live verification: real, clean pass, confirmed end-to-end against the same PR #32/issue #10 evidence preserved from last session.** `existing_service` resolved to `REQ-2026-03` for real; frontend install ran for real (695 packages, 23s); `npm run build` succeeded for real; QA applied `qa-approved` (attempt 4) for a genuine reason, 0 bugs filed. Security re-confirmed its earlier genuine pass (22 findings, 0 Critical). Item #27's fix ran correctly for the right reason (label state was genuinely current this time, correctly found nothing stale). Issue #10 now shows `qa-approved` + `security-approved` as an accurate reflection of reality, not a stale artifact.

**Deploy fired automatically — second live confirmation of Item #26's unresolved gap.** Both labels genuinely present triggered `06-deploy.yml` with no human gate in between. Raised cleanly (`ValueError: No deployable units detected under services/REQ-2026-04/ ... nothing to deploy`) — an early, pre-infrastructure check; no docker build, no `az` CLI call, no real Azure resource touched, confirmed via the job log. This run also newly **confirms live** (not just infers) that Deploy Agent itself has zero Enhancement-target awareness — a distinct gap from Item #26, logged separately below.

**ADO Bug #178 — closed, with the real root cause documented** (comment id `16491004`, pointing at commit `b08ad31`, the frontend-install fix). See the process note above re: how the close-vs-annotate ambiguity was handled.

**PR #32 remains open, unmerged** — untouched throughout this session's re-verification.

---

## This session's work, in order

### 1. Spec written: `FORGE-Item25-QASecurity-EnhancementTarget-Spec.md`

Investigation-first structure mirroring Item #24's own spec shape: six things to verify live before any code was written. Three design forks deliberately left open: resolution mechanism (spreadsheet re-download vs. parsing the already-posted "Related service" comment line — recommended default: re-download, consistent with the project's own established precedent against trusting weak/parsed signals), whether Stage 3's own working logic should migrate to the new shared helper (recommended: no, don't touch working code for a cosmetic win), and whether a QA Layer 2 raise should count against the retry budget (recommended: no, matching Stage 3's own precedent).

### 2. Live investigation corrected the spec's own problem framing

Claude Code CLI's §1 investigation confirmed QA's false-positive-pass bug exactly as described, but found Security's crash was **already being caught** by the existing ADR-0011 try/except — a real comment already posted, `security-approved` already correctly withheld. This re-prioritized the fix: QA's false-positive (Priority 2) became the urgent item; Security's fix (Priority 4) became a clarity improvement, not a silent-failure fix. Investigation also surfaced the Dependabot filter bug as real-but-currently-unreachable, worth fixing proactively rather than waiting for it to bite once the higher-priority fixes started working.

### 3. Four priorities built and committed separately

`ea9c85a` (Priority 1 — shared resolution + workflow wiring), `18e51e5` (Priority 2 — QA fail-loud fix), `2b1f2a6` (Priority 3 — Dependabot filter fix), `9a88421` (Priority 4 — Security's clearer failure comment). Every change verified via real function calls against scoped local harnesses (missing-directory, dry-run, and present-directory-regression cases for both QA and Security), not just read-throughs.

### 4. Priority 5 — decided not to re-dispatch live, on the evidence already in hand

Explicitly surfaced as a decision point rather than assumed: re-running QA/Security against the real PR #27/REQ-2026-01 to "confirm Greenfield behavior live" would itself have been a real, side-effecting dispatch (duplicate ADO Bugs for 6 known pre-existing Jest failures, possible surprise redeploy) for a question the scoped regression tests plus last session's real live baseline already answered. Decided: skip it.

### 5. Live re-dispatch against PR #32/issue #10 surfaced two real bugs

First dispatch attempt was made without confirming the push had landed — reproduced the exact "flip a label before confirming the remote has the commit" mistake from Item #24's own session, on the exact same class of infrastructure. This stale run re-exposed the original crash/false-pass pattern and left a stale `qa-approved` label sitting on issue #10.

That stale label then triggered the real, previously-undiscovered **Item #27** bug: `04-qa.yml`'s "clear stale label on pass" step checked current label presence rather than this run's own outcome, and deleted a freshly-and-correctly-applied `qa-loop-back` label because it saw the leftover stale `qa-approved` and assumed a fresh pass.

Separately, the corrected code's real QA run surfaced the **frontend-install gap**: Priority 1's Python-level fix was correct, but a workflow-level bash step (`04-qa.yml`'s "Install frontend dependencies") independently reconstructed the same stale path and was never touched by Priority 1's change — producing a misleading, app-defect-shaped ADO Bug (#178) when the real cause was CI wiring.

### 6. Both bugs fixed, verified, and closed out properly

Frontend-install step fixed to use the resolved target (commit `b08ad31`); stale-label-clearing logic fixed to key off this run's own actual outcome (logged as **Item #27**). Both confirmed present on `origin/main` via the GitHub API (real commit SHAs, not "I ran git push") before any further dispatch was attempted. ADO Bug #178 closed with a comment documenting the real root cause.

### 7. Final clean re-dispatch — genuine, real, end-to-end pass

QA passed for a real reason (frontend build succeeded, 0 bugs filed, attempt 4). Security re-confirmed. Item #27's fix ran correctly (found nothing stale to clear, because the pass was genuine). Deploy auto-fired per Item #26's still-open gap, raised cleanly with zero Azure impact, and in doing so **confirmed live** that Deploy Agent itself has no Enhancement-target awareness either — logged as a new item.

### 8. Committed and closed

`ea9c85a`, `18e51e5`, `2b1f2a6`, `9a88421` (the four Item #25 priorities), plus separate commits for the frontend-install fix (`b08ad31`) and the Item #27 stale-label-logic fix. CLAUDE.md updated: Item #25 marked resolved with the full real narrative; **Item #27** (stale-label-clearing bug) added as its own numbered item; **Item #28** (Deploy Agent's confirmed Enhancement-target blindness) added as its own numbered item, distinct from Item #26.

---

## Key learnings & principles (new/updated this session)

- **A fix can correct the described bug while the investigation that precedes it corrects the bug's own framing** — Security's "crash" turned out to already be a caught, ADR-0011-compliant failure; the real gap was message clarity, not a silent failure. Worth treating a spec's own problem description as unverified until confirmed live, the same discipline already applied to a spec's cited evidence.
- **A fix at one layer doesn't guarantee every independent reconstruction of the same value got updated** — Priority 1 fixed `qa_agent.py`'s own path resolution correctly, but missed a separate workflow-level bash step reconstructing the identical path independently. The lesson isn't "check twice" in the abstract; it's that any value derived in more than one place (Python script *and* YAML step, in this case) needs each site checked explicitly, not assumed to inherit a fix made elsewhere.
- **The same "flip a label before confirming the push landed" mistake recurred, on the exact same class of infrastructure, in back-to-back sessions.** Worth treating this as a standing pre-dispatch checklist item going forward, not just a lesson learned once — the fact that it recurred despite being explicitly named last session suggests naming it in a doc isn't sufficient on its own.
- **A stale label from an aborted/incorrect run can cause a *second*, unrelated bug to fire** — Item #27 was only discovered because the push-timing mistake happened to leave a stale label sitting in exactly the state that exposed a previously-dormant logic gap. Genuinely useful accidental coverage, but also a reminder that incident cleanup (correcting label state) and root-cause fixes (correcting the logic that let bad label state persist) are two different obligations — fixing the symptom doesn't fix the mechanism.
- **When re-verifying a fix, "did the outcome look right" and "did the actual mechanism get fixed" are different questions** — asked explicitly this session whether Item #27's underlying logic was fixed in code versus the symptom just resolving because the frontend fix let QA pass normally; the two are not the same and needed separate confirmation.
- **Ambiguous instructions touching an external system of record (ADO, Azure, anything outside FORGE's own git repos) deserve a flag-before-acting check, even when one reading feels clearly more likely** — "close X with a note" genuinely supports two readings; the miss wasn't picking the more plausible one, it was not noticing the ambiguity was worth a check given what was at stake (a real ticket's real state).
- **Deciding *not* to do a live verification step is itself a decision worth surfacing explicitly, with the actual cost/benefit stated** — Priority 5's skip (no re-dispatch against PR #27) and the original spec's own live-verification gate (confirm with Mike before re-dispatching against PR #32, given Item #26) are both examples of treating "should we trigger this real side-effecting thing" as a first-class question, not a default yes.

---

## On the horizon

- **Item #26 (no human gate before Deploy) — now has two live confirmations, not one.** Both were self-corrected cleanly with zero real Azure impact, but the pattern is proven, not theoretical: Deploy fires the instant both labels land, regardless of whether the underlying code has anything sensible to deploy. Worth bringing to Mike as an actual decision point now rather than staying indefinitely deferred — **next action: fresh chat, dedicated to this decision alone, not bundled with a spec.**
- **Item #28 (Deploy Agent has zero Enhancement-target awareness) — newly confirmed live, needs its own spec eventually.** Distinct from Item #26 (this is Deploy Agent's own path resolution, same category of gap as Item #25 was for QA/Security, just one stage further downstream). Not urgent — every Enhancement run so far has hit the "no deployable units" raise before doing anything costly — but worth fixing before an Enhancement scenario exists where Deploy Agent's wrong-path resolution *would* find something to deploy.
- **`FORGE-Open-Items-Backlog-v1.md` reconciliation — still outstanding, now more stale.** Carried from v70, still not done. Needs #25 (now resolved), #27, and #28 folded in, on top of the already-outstanding #24 renumbering note. **Next action: fresh chat.**
- **PR #32 / issue #10 — no longer "left as evidence."** Both labels are now genuinely present and accurate; the PR itself remains open/unmerged (Deploy's raise means nothing was actually built to merge toward). No further action needed on this specific PR unless Mike wants it formally closed.
- **Carried forward, unchanged:** Items #1, #7, #9, #10, #11, #12. Item #22's third test case (scale-rule units, still untestable). CLAUDE.md's `user.interrupt` documentation task (carried since v68, still not addressed).
- **Standing pre-dispatch discipline, worth re-stating given the recurrence:** confirm via the GitHub API (not local git, not verbal confirmation) that any commit is actually present on `origin/main` before flipping any label-driven trigger — this is now the second session in a row this exact mistake happened.

---

## Tools & resources (unchanged from v70 except where noted)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **Azure:** Container Apps (`forge-staging`/`forge-production` environments, `forge-build-rg`), Container Registry, Key Vault (`forge-build-kv`), PostgreSQL Flexible Server (`forge-req2026-03-pg`, stop after each session), Azure AD (`FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **New this session:** `FORGE-Item25-QASecurity-EnhancementTarget-Spec.md`; `core/agents/utils/enhancement_target.py`; `EnhancementTargetNotFoundError`; corrected "clear stale label on pass" logic in `04-qa.yml` (Item #27); corrected "Install frontend dependencies" step in `04-qa.yml`
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`. Bug #178 closed this session (comment id `16491004`).
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`, `C:\Users\mikef\Projects\forge-demo-apps`
