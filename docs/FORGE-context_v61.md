# FORGE Context — v61
**Session date:** 2026-08-19
**Carries forward from:** v60

---

## Purpose & context (unchanged)

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment, with human approval gates at defined stages.

Two-repo model: `forge-template` (public, orchestration/agents) and `forge-demo-apps` (private, target monorepo). Two-tool convention firm: Claude.ai owns strategy/spec authorship/context docs; Claude Code CLI owns live execution/git/CLAUDE.md. Mike shuttles between tools and holds all unilateral decisions.

---

## Current state

**Phase 6 (Repeatability) remains CLOSED** (per v60). This session was housekeeping cleanup plus one ad hoc fix PR — no new build phase started. Next phase is still undefined; see "Still open" below.

### Resolved this session

1. **`IsCoordinator` test flag flipped off.** The "Mike App Test" user's bootstrap `IsCoordinator=true` flag (needed in v59 to create a test shift via the real API) is confirmed off. Closes the first v60 cleanup item.

2. **Azure AD App Registration renamed.** `FORGE-REQ-2026-03-OnCallRoster` → **`FORGE-DemoApps-SSO`**, reflecting the standing architectural decision (made in an earlier session) that this one registration is the shared IdP for every app in `forge-demo-apps`, not scoped to REQ-2026-03 alone. Client ID/tenant ID unchanged (`b59886c1-12ac-42c1-895f-5fafa8e57318`); cosmetic Portal-legibility fix only, via `az ad app update --display-name`.

3. **Firewall rule cleanup — confirmed already resolved, not actioned this session.** Mike reported `forge-req2026-03-pg`'s firewall rule list already shows only `AllowAzureServices` — `AllowAdminVerificationIp` and `AllowContainerAppsEnvOutboundIp` are already gone (delete calls errored as not-found, consistent with prior removal in an unsynced session). No action taken; closes the v60 cleanup item as already-done.

4. **New cleanup item identified: stale local clone.** Mike has two local checkouts — `forge-demo-apps` (active, current) and `forge-demo-apps-clone` (a disposable QA-verification checkout created 2026-08-05 during Phase 4 dry-run prep, never needed since). Mike confirmed working exclusively in `forge-demo-apps` going forward. Deletion of the clone folder was planned (git status/log sanity check first) but not yet confirmed executed this session — carry forward as an open item.

5. **`SHIFT_ALREADY_CLAIMED` wording fix — implemented, PR #22 open, not yet merged.**
   - Spec drafted this session (small, single-fix version of the deploy-agent-fix spec pattern) and handed to Claude Code CLI.
   - **Backend** (`ShiftsRepository.cs`/`ShiftsController.cs`): message now distinguishes self-claim-retry ("You have already claimed this shift.") from a different claimant (existing wording unchanged). Error code (`SHIFT_ALREADY_CLAIMED`) and HTTP 409 status untouched. Also fixed an adjacent bug found during implementation: the `StaleRowVersion` concurrency path was re-reading the in-memory entity (reflecting the attempted write) rather than the actual current claimant — corrected to re-read real state.
   - **Frontend scope fork, resolved by Mike (extend now):** Claude Code found `ShiftRow.tsx` was ignoring the backend's `message` field entirely, rendering a hardcoded string regardless of self-vs-other. Root cause: the frontend's own `shift` prop is stale at the moment the claim error fires (reflects pre-request state), so a client-side self/other check would hit the same race just fixed server-side — `err.body.message` from the backend is the only reliable source. Mike approved extending the fix into the frontend (swap hardcoded string for `err.body.message`, update two test fixtures) rather than deferring as a separate follow-up.
   - Branch `feature/fix-shift-claim-message-wording`, off freshly-pulled `main` (`7596ff7`, includes PR #21). Single commit `0c5e18c4c644850dc8ac168136c37fdcaaa64d58`. 39 backend + 29 frontend tests pass (2 new).
   - QA and Security both passed automatically on PR #22.
   - **New Deploy-pipeline gap found (Open Item #17 — see below):** `resolve_feature_pr()` in `workflow_glue.py` only matches an open PR on branch `feature/<request-id>` (the original implementation branch, long merged as PR #20) — it has no concept of "any open PR referencing this tracking issue," so it couldn't find ad hoc fix PR #22 at all. Deploy failed to auto-run for this reason.
   - **Resolution (Mike's call):** worked around via a manual `deploy_agent.py` invocation (`--issue-number 6 --request-id REQ-2026-03 --pr-number 22 --commit-sha <PR #22 head>`) rather than fixing `resolve_feature_pr()` in-session — treated as a separate architectural decision deserving its own spec, not folded into this fix. Confirmed via `az containerapp show` that both running Container Apps now serve the fix commit (`d53bebd`).
   - **Verification:** per Mike's call, the live HTTP smoke test (both self-claim and other-user-claim cases) was **skipped** — no bearer tokens were exchanged this session. Instead, the `req-2026-03-database-url` secret was read directly from Key Vault (no new credentials needed) and the audit table was confirmed internally consistent (no spurious rows) — this reflects existing state, not a fresh exercise of today's code path, and is noted as a verification gap, not a pass. Temporary firewall rule used for this check was removed and the Postgres server re-stopped afterward.
   - **PR #22 status: open, awaiting Mike's review/merge in `forge-demo-apps`.** Not yet merged as of this session's close.

6. **Cloud-portability question raised and answered, deferred to later.** Mike asked whether FORGE is architecturally Azure-specific or could be made cloud-agnostic. Assessment given: the orchestration core (GitHub Actions, agent scripts, Managed Agents/Claude API layer, Stages 0–5) is already cloud-agnostic and doesn't touch Azure at all. Genuine coupling is concentrated in Stage 6: the Deploy Agent's direct `az containerapp` calls are the one deep coupling point (would need a real rewrite to target another platform); ACR (image registry) and Azure DevOps (traceability) are shallow, swappable couplings; Azure AD as shared IdP is a deliberate choice, not a hard dependency (OAuth/OIDC generally is portable). Mike's call: revisit later, not now — no action taken. If picked up in future, the natural framing is a pluggable deploy-target interface behind the Deploy Agent.

### Still open / next session's starting point

- **Delete stale local clone `forge-demo-apps-clone`** — planned this session (git status/log check first), not yet confirmed executed.
- **PR #22 needs Mike's review/merge** in `forge-demo-apps` — backend + frontend `SHIFT_ALREADY_CLAIMED` wording fix, tests passing, QA/Security clean, manually deployed and confirmed live at commit `d53bebd`, but the live HTTP smoke test (self-claim vs. other-user-claim, both cases) has **not yet been run** — do this once real bearer-token testing is convenient, don't treat PR #22 as fully verified until then.
- **New Open Item #17 (Deploy pipeline gap):** `resolve_feature_pr()` in `workflow_glue.py` only recognizes the original `feature/<request-id>` branch as a tracking issue's PR — cannot resolve ad hoc fix PRs against an already-merged issue. This will recur for every future ad hoc fix PR until fixed. Needs its own spec/session (design question: resolve via issue linkage? branch-name pattern? PR body parsing?) — not a quick patch, per Mike's explicit deferral this session. Logged in `CLAUDE.md` already (per Claude Code's session summary).
- **102 Dependabot alerts repo-wide, 74 outside REQ-2026-03** — still not triaged. Carried forward from v58/v59/v60. Largest remaining housekeeping item; will need a dedicated pass (severity + individual NVD-source verification for CPE fuzzy-match hits, per existing root-cause discipline) rather than a quick fix.
- **Cloud-portability / multi-cloud deploy-target abstraction** — raised and discussed this session, explicitly deferred by Mike to a future session. Not urgent, no spec drafted.
- **Next phase still undefined.** With Phase 6 closed and today's items being pure housekeeping, the "what comes after repeatability" decision from v60 remains open.

---

## Key learnings & principles (new this session)

**Local git state can silently drift when a checkout sits on a stale feature branch.** The `forge-demo-apps` clone was left on `feature/fix-nextauth-signin-loop` since an earlier session; switching to `main` for this fix showed 36 commits behind. Confirmed as expected drift (clean fast-forward, no divergence), not a red flag — but worth remembering to check out `main` and pull before branching for any new ad hoc fix, rather than assuming the last-used branch is current.

**A backend fix without a matching frontend read is invisible to users.** The `SHIFT_ALREADY_CLAIMED` case is a concrete example: a component that branches only on error *code* and renders its own hardcoded string will silently swallow any backend message-text improvement. When a fix is purely about message content, check whether the consuming layer actually surfaces that content before considering the fix complete.

**A stale in-memory entity can be wrong in more than one place.** The `StaleRowVersion` concurrency path bug (found as an unplanned adjacent fix) is the same failure shape as the frontend's stale-`shift`-prop issue: code re-using an in-memory value from the *attempted* write instead of re-reading actual current state, in a path specifically about detecting staleness. Worth treating "does this path re-read reality or reuse the write attempt" as a checklist item whenever touching claim/concurrency logic.

**Ad hoc ('fix/*') PRs against an already-merged tracking issue are structurally invisible to `resolve_feature_pr()`.** This is a new, real Deploy-stage gap (Open Item #17), distinct from the earlier-fixed QA/Security `resolve_tracking_issue()` issue (Open Item #15). Every future ad hoc fix PR will hit this same wall until it's fixed — worth prioritizing before too many more manual `deploy_agent.py` workarounds accumulate.

**FORGE's Azure coupling is concentrated, not systemic.** The orchestration core (Stages 0–5) is already cloud-agnostic; only the Deploy Agent's direct Container Apps calls represent deep coupling. Useful reference point if a portability discussion resumes later.

---

## Approach & patterns (reconfirmed, unchanged)

- Two-tool convention firm; Claude Code CLI prompts/specs drafted in full in Claude.ai chat, copy-pasted.
- Spec-first for non-trivial fixes reconfirmed this session, scaled down appropriately for a small single-fix (one-fix version of the multi-fix spec pattern), drafted and approved in-chat before handoff.
- Design forks with real implications (frontend scope extension, Deploy gap workaround vs. root-cause fix) surfaced explicitly to Mike rather than resolved silently — reconfirmed twice this session.
- Verification honesty: the live HTTP smoke test was explicitly *not* run and is logged as a gap, not glossed over as complete — consistent with the project's verification-discipline principle (verbal "done" and skipped verification are treated as real gaps, not closed items).

---

## Tools & resources (updates this session)

- **Azure AD App Registration display name:** now `FORGE-DemoApps-SSO` (was `FORGE-REQ-2026-03-OnCallRoster`). Client ID unchanged: `b59886c1-12ac-42c1-895f-5fafa8e57318`.
- **`forge-req2026-03-pg` firewall rules:** confirmed only `AllowAzureServices` remains (temporary verification rule added and removed again this session, server re-stopped after).
- **New branch/PR:** `feature/fix-shift-claim-message-wording`, PR #22 in `forge-demo-apps` (open, awaiting merge), commit `0c5e18c4c644850dc8ac168136c37fdcaaa64d58`. Manually deployed to `forge-staging` at commit `d53bebd`.
- **Local checkouts:** `forge-demo-apps` (active) and `forge-demo-apps-clone` (stale, planned for deletion — see Still Open).
