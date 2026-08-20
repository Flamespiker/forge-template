# FORGE Context — v63
**Session date:** 2026-08-20
**Carries forward from:** v62

---

## Purpose & context (unchanged)

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment, with human approval gates at defined stages.

Two-repo model: `forge-template` (public, orchestration/agents) and `forge-demo-apps` (private, target monorepo). Two-tool convention firm: Claude.ai owns strategy/spec authorship/context docs; Claude Code CLI owns live execution/git/CLAUDE.md. Mike shuttles between tools and holds all unilateral decisions.

---

## Current state

**Phase 6 (Repeatability) remains CLOSED** (per v60). This session closed out the last open housekeeping item from v62 — the live HTTP smoke test for the `SHIFT_ALREADY_CLAIMED` fix — via Claude Code CLI. No new build phase started. Next phase is still undefined.

### Resolved this session

1. **Live HTTP smoke test for the `SHIFT_ALREADY_CLAIMED` fix (PR #22) — genuinely verified, both message branches and the audit-write path.**

   - **Blocker encountered first:** the original token-acquisition method from 2026-08-19 was undocumented anywhere retrievable — not in `docs/CLAUDE-archive-2026-08-req2026-03.md`, not in v62, no script in either repo. `az login --use-device-code` / `az account get-access-token` against the API's own resource URI failed twice (`AADSTS65001`, then `AADSTS650057`) — the On-Call Roster API's app registration doesn't authorize the Azure CLI client at all, and widening it (`knownClientApplications`) would have meant a real change to shared production app-registration config. Correctly identified as a decision requiring Mike's sign-off, not something to try unilaterally.
   - **Actual method recalled and confirmed:** manually sign into the live frontend in a browser, capture the `Authorization: Bearer <token>` header via devtools Network tab from a real authenticated request. Not `az` CLI, not MSAL device-code. **This is now recorded in memory** (previously it existed only as tribal knowledge from a single prior session) so it doesn't need rediscovering again.
   - **Identity-count check (read-only, before touching anything live):** only one Users row existed (`Mike App Test`), one Open shift, 4 pre-existing audit rows. Two Azure AD identities (`MikeTest1`, `Mike Test 2`) existed in the tenant but had never authenticated against the app. Decision made to reuse the single existing Open shift sequentially for both test cases rather than re-flip the coordinator flag to create a second shift — kept DB mutation to a minimum.
   - **Token handoff:** a local gitignored file (`C:\Users\mikef\forge-smoke-test-tokens.txt`, outside both repo checkouts, confirmed absent from `git status`) was created empty by Claude Code; Mike captured both tokens via browser devtools and pasted them in directly — never typed into chat — following the same credential-handling discipline as the 2026-08 exposure incident. `TOKEN_A` = MikeTest1, `TOKEN_B` = Mike Test 2.
   - **Case 1 (self-claim-retry), TOKEN_A claims shift `3999a386-...` twice:** `409 SHIFT_ALREADY_CLAIMED`, message *"You have already claimed this shift."* — correct self-specific wording. ✅
   - **Case 2 (other-user-claim), TOKEN_A claims, TOKEN_B attempts the same shift:** `409 SHIFT_ALREADY_CLAIMED`, message *"This shift was just claimed by someone else — please refresh and choose another."* — correct other-user wording. ✅
   - **Audit-table regression check:** 8 total rows post-test (4 pre-existing + 4 new: one Claimed/Released pair per case, both under MikeTest1). Mike Test 2's rejected claim attempt produced **zero** audit rows — confirms the audit-write path only fires on the success branch, unaffected by this fix. Users table went from 1 → 3 rows (MikeTest1 and Mike Test 2 auto-provisioned on first login) — expected, not a new gap.
   - **DB and cleanup, independently verified (not just reported as done):** shift `3999a386-...` confirmed back to `Open`; token file deleted and confirmed gone; temporary firewall rule `AllowSmokeTestVerificationIp` removed (firewall-rule list shows only `AllowAzureServices`); Postgres server confirmed `Stopped`; local DB connection-string scratch copy deleted; `az` CLI confirmed switched back to the `forge-deploy-staging` SP session (`be88677c-...`).
   - **CLAUDE.md updated by Claude Code** with the full closure note (both response bodies, audit regression results, cleanup confirmation), per the two-tool convention — Claude.ai's context doc (this file) is the corresponding update on the other side.

### Still open / next session's starting point

- **Open Item #17 (Deploy pipeline gap)** — `resolve_feature_pr()` in `workflow_glue.py` only recognizes the original `feature/<request-id>` branch as a tracking issue's PR; cannot resolve ad hoc fix PRs. Confirmed twice in v62 (manual verification + live automated workflow failure on PR #22's merge). Needs its own spec (design question: issue linkage? branch-name pattern? PR body parsing?) before Claude Code implements anything — every future ad hoc fix PR will hit this same wall otherwise. **This is the main candidate for next session's focus** — likely a fresh chat, since it's a spec document (one-doc-per-chat convention).
- **102 Dependabot alerts repo-wide, 74 outside REQ-2026-03** — still not triaged. Carried forward across v58–v62. Needs a dedicated pass (severity + individual NVD-source verification for CPE fuzzy-match hits, per existing root-cause discipline).
- **Cloud-portability / multi-cloud deploy-target abstraction** — raised and discussed in v61, explicitly deferred by Mike. Not urgent, no spec drafted. Assessment on record: orchestration core (Stages 0–5) is cloud-agnostic; Deploy Agent's direct `az containerapp` calls are the one deep Azure coupling point.
- **Next phase still undefined.** With Phase 6 closed and the last two sessions being pure housekeeping/verification, the "what comes after repeatability" decision remains open — worth a dedicated conversation whenever Mike is ready to have it, separate from the smaller cleanup/spec items above.

---

## Key learnings & principles (new this session)

**Credential-acquisition methods used only once, informally, don't survive in institutional memory by default.** The 2026-08-19 live-token method existed only as an unrecorded action — not in the archive doc, not in CLAUDE.md, no script — and had to be fully rediscovered (including a real dead-end down the `az`/MSAL path first) before Mike recalled it directly. Now recorded permanently (memory, outside this doc) specifically so this doesn't recur. General principle: any manual, interactive, one-off credential step that a future session will need to repeat should be written down the first time, not just performed.

**A custom API's app registration not authorizing a standard tool (Azure CLI, MSAL device-code) is itself informative, not just a blocker.** Claude Code correctly stopped rather than widening `knownClientApplications` on a shared production app registration unilaterally — that's a real, if narrow, change to shared infrastructure and appropriately escalated rather than just done to unblock a smoke test.

**Reusing existing state (one shift, sequential claim/verify/release) instead of creating new state (a second shift via a coordinator-flag flip) is the right default when both achieve the same verification goal** — less DB mutation, less cleanup surface, less chance of leaving something behind.

---

## Approach & patterns (reconfirmed, unchanged)

- Two-tool convention firm; Claude Code CLI prompts/specs drafted in full in Claude.ai chat, copy-pasted.
- Verification honesty maintained end-to-end: the smoke test was not marked closed until real HTTP responses and an independent audit-table check confirmed it, not just "tests pass."
- Credential handling: tokens/secrets always handed off via a local file the user populates directly, never typed into chat — reconfirmed this session with a clean execution (file created, populated, deleted, all independently verified).
- Structural/infrastructure decisions (widening an app registration's known clients) surfaced explicitly to Mike rather than resolved unilaterally, even under mild time pressure (token expiry).

---

## Tools & resources (updates this session)

- **`forge-demo-apps` PR #22 (`SHIFT_ALREADY_CLAIMED` wording fix):** now fully verified live, not just unit-tested — both message branches and the audit-write regression path confirmed via real HTTP calls with real Azure AD bearer tokens.
- **Test identities:** `Mike App Test`, `MikeTest1`, and `Mike Test 2` all now have provisioned Users rows in the REQ-2026-03 Postgres DB (3 total, up from 1).
- **Live staging state unchanged from v62:** both Container Apps serving commit `d53bebd`.
- **Token-acquisition method for future live smoke tests:** manual browser sign-in → devtools Network tab → capture `Authorization: Bearer` header. Now recorded in memory going forward, not just this doc.
