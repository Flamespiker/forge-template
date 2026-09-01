# FORGE — Open Items Backlog: Planning for Next Session(s)

**Prepared:** 2026-08-31 (Claude.ai)
**Supersedes:** v4 (2026-08-31, same day) — Item #32 built and live-verified this
session; see below. No other content changed from v4.

**Reconciliation note (Claude Code CLI, before committing):** the original draft
of this file was built from a project-knowledge snapshot of v2 that predated
several 2026-08-31 updates already live in the committed
`docs/FORGE-Open-Items-Backlog-v2.md` (commits `2255058`, `131729a`, `c6fca2d`).
Two real discrepancies were found and corrected against that live file rather
than guessed at:
- The draft reverted **Item #1 to "still open."** It is not — both Option 3
  (reactive post-deploy flag) and Option 1 (proactive pre-merge declaration
  flag) were built and live-verified 2026-08-31, and Item #1 has been in
  "Resolved since v1" since commit `131729a`. Kept resolved here.
- The draft **dropped the "PR self-approval / branch-protection deadlock"**
  flagged item entirely. It's still genuinely unresolved (no permanent fix was
  made) — restored from the live file below.
- Item #31's live entry (commit `c6fca2d`) is more complete than the draft's
  reconstruction — 6 commits vs. 5 (the draft was missing `7cfd87d`, the
  `ingestion_agent.py` migration). Live version kept as-is.

The draft's genuinely new content — Item #32, Item #33, the Phase 7 status
update, and the sequencing rewrite — is applied on top of that live baseline
below. Flagged back to Mike/Claude.ai for visibility; see the session report.

**Headline finding from this pass:** every item v2 classified as a "Real Bug" or
open bookkeeping task has resolved (#12, #29, #31), and Phase 7's Enhancement
Workflow validation — previously tracked only as "next substantive work" — has
already happened, via REQ-2026-04, discovered during a reconciliation pass
against Build Plan v9→v10 (see that doc's v10 update). **Item #32** — a real
ADO-linkage design gap discovered from that reconciliation — is now also
**resolved**, live-verified 2026-08-31 (`create_ado_items.py` reuses the
existing service's real Epic ID for Enhancements instead of creating a parallel
one). The PR self-approval/branch-protection deadlock, flagged earlier this
same session, has also been decided (see "Accepted ongoing process" below):
Mike's call is to keep the manual disable/restore workaround rather than build
anything. **What's left open: nothing new** — just the two long-standing
deliberate accepted-risk/leave-as-is items (#7, #11) and one small bookkeeping
call (#33, closing `forge-template#10` — actually already closed this session,
see below).

---

## Design / Policy Decisions — need Mike's call, not a spec

**Nothing open in this section right now.** Item #32 (below) was decided and
resolved same-day. The PR self-approval/branch-protection deadlock that also
lived here earlier this session has been decided — see "Accepted ongoing
process" below.

*(Item #1 lived in this section through the morning of 2026-08-31; fully
resolved that same day — both Option 3 and Option 1 built and live-verified —
see "Resolved since v1" below. Items #9, #10, and #15 previously lived here
too; all resolved 2026-08-27.)*

---

---

## Accepted ongoing process — decided, no fix planned

### PR self-approval / branch-protection deadlock — decided 2026-08-31, keep the manual workaround
Hit for real 2026-08-31 while merging `forge-demo-apps#35` (Item #1 Option 1's
`design.md` backfill PR): the PR was opened under Mike's own GitHub account (the
same identity `gh` authenticates as in this environment), and `main`'s branch
protection requires 1 approving review with `enforce_admins: true` (Item #10) —
GitHub rejects a self-approval outright, and there's no admin-bypass path anymore.
Resolved that instance via a fully-audited temporary workaround (confirm current
protection state → drop `required_approving_review_count` to 0 → merge → confirm
the merge via a fresh API read → immediately restore to 1, independently
re-verified) — see CLAUDE.md's Item #1 entry for the full blow-by-blow.

**Mike's decision (2026-08-31):** keep doing the manual disable/restore dance
each time, rather than dropping the review requirement permanently or building
App-identity PR routing. Options considered and explicitly declined:
- Drop the required-review count permanently — declined, would weaken the
  human-review gate for *every* PR, not just Mike's ad hoc ones
- Route ad hoc/backfill PRs through the `forge-pipeline` App identity — declined
  for now (would have needed a small new helper script)

**Standing procedure going forward** (repeat exactly, every time an ad hoc PR
needs merging under Mike's own account):
1. Confirm current branch protection state via a fresh API read
2. Drop `required_approving_review_count` to 0
3. Merge the PR
4. Confirm the merge via a fresh API read
5. Immediately restore `required_approving_review_count` to 1
6. Independently re-verify the restoration (a second fresh API read — don't
   trust step 5's own response alone)

**This will recur** on the next ad hoc PR opened under Mike's account — no
permanent fix exists, by deliberate choice. The main risk with this option
(step 6 being skipped, leaving `main` unprotected) is exactly why the
verification step above is spelled out explicitly rather than left implicit.

---

## Real Bugs — well-scoped, good spec-and-fix candidates

**None currently open.** Items #31 and #32 (both below, in "Resolved since v1")
were the last occupants of this section — #32 was the fourth occurrence of the
same "stage has zero existing_service/Enhancement awareness" pattern as Items
#24/#25/#28, this time in Stage 2's ADO item creation.

---

## Deliberately left as-is — not being pursued

### Item #7 — Archive-prefix mismatch (REQ-2026-02, once)
Root cause unconfirmed, only happened once, and REQ-2026-02's infra is
decommissioned anyway so this specific instance can't recur on that app.
**Recommend continuing to leave this exactly as-is** unless it happens again on a
still-live app.

---

## Accepted ongoing risk — tracked, no fix planned

### Item #11 — 21 `next@14.2.35` CVE findings have no 14.x backport
(8 High + 11 Medium + 2 Low, count refined 2026-08-21 per Item #19's triage pass).
Accepted ongoing risk from the deliberate decision to stay on the 14.x line, not a
bug to fix. No action needed unless the decision to stay on 14.x itself gets
revisited.

---

## Bookkeeping — no spec needed, just do directly

**Nothing currently open.** Item #33 (below) was the last occupant — resolved
same-day.

---

## Resolved since v1 (2026-08-24) — historical record, not action items

Full narratives live in CLAUDE.md's Open Items / Known Gaps section and the
relevant `docs/FORGE-Item*-Spec.md` files — this is a one-line-each index so this
doc doesn't need re-deriving from scratch again next time.

| Item | One-line resolution | Date | Commit(s)/PR(s) |
|---|---|---|---|
| #1 | Deploy Agent had no app-secrets wiring mechanism, and no way to discover in advance that a given app needs a given secret | **fully resolved 2026-08-31** — Option 3 (reactive post-deploy flag) and Option 1 (proactive pre-merge declaration flag) both live-verified | 2026-08-31 | `29073cd`, `6d1511c`, `a21b4a9`/`forge-demo-apps#35` (merge `39b99800c0`) |
| #2 | REQ-2026-03 backend unit name exceeded Azure's Container App name length limit | resolved | — |
| #3 | No pipeline stage validated the app actually builds before Stage 6 | resolved | — |
| #4 | `qa_agent.py`'s Jest/Vitest JSON parsing had a file-collection blind spot | resolved | — |
| #5 | QA's `_MAX_RETRIES = 3` only picked which label to apply, never blocked/gated | resolved | — |
| #6 | `wait_for_all_threads_idle()` couldn't distinguish "finished" from "all threads fatally errored" | resolved | — |
| #8 | Implementation Coordinator's CI-workflow scope creep | resolved | — |
| #9 | Ad hoc `fix/*` branches needing `--admin` merge (4 occurrences) | **resolved 2026-08-27 — no code fix needed.** Live evidence (PR #27) confirmed the `feature/fix-*` convention already gets a real `security-check` scan; the 4 original cases predated that convention | 2026-08-27 | `docs/FORGE-Item9-Item15-AdHocFixDispatch-Spec.md` |
| #10 | `enforce_admins` on `forge-demo-apps` `main` was `false` | **resolved 2026-08-27**, flipped to `true` via the dedicated API endpoint (confirmed no other protection field changed), on Mike's go-ahead, coupled with #9's resolution | 2026-08-27 | — |
| #12 | Cost log missing REQ-2026-03 actuals (Stages 1/3/4/5/6, incl. the #24–#28/#30 fix cycle) | **resolved 2026-08-31**, backfilled from GitHub Actions logs and the Managed Agents sessions API; also confirmed to include REQ-2026-04's figures during this session's reconciliation | 2026-08-31 | `103c927`, `8d97bfc` |
| #13 | No `forge-template`-level Dependency-Check suppression file existed | resolved | — |
| #14 | Backend AzureAd config was placeholder, blocked real Azure AD login | resolved | — |
| #15 | Ad hoc PRs needed the tracking-issue body line added manually | **resolved 2026-08-27 via Option A** (documented as a standing convention, no code change to `resolve_tracking_issue()`) | 2026-08-27 | `docs/FORGE-Item9-Item15-AdHocFixDispatch-Spec.md` |
| #16 | Cleanup debt from the 2026-08-19 write-path verification session | resolved | — |
| #17 | `resolve_feature_pr()` couldn't find ad hoc fix PRs | resolved | — |
| #18 | New bug uncovered by Item #17's live verification | resolved | — |
| #19 | Dependabot alert triage pass | completed 2026-08-21 | — |
| #20 | REQ-2026-01's `lib/app-insights.ts:70` Application Insights type conflict | **resolved 2026-08-26** | — |
| #21 | Deploy Agent's `_SHELL_TIMEOUT_SECONDS` too tight for real frontend builds | resolved | — |
| #22 | Deploy Agent didn't wire a scale rule for non-ingress worker apps | resolved | — |
| #23 | No on-demand way to verify a service's build outside the full pipeline | resolved | — |
| #24 | Stage 3 (Implementation) never extended for Enhancement requests | **resolved and live-verified 2026-08-28** | 2026-08-28 | `docs/FORGE-Item24-*-Spec.md` |
| #25 | QA and Security both assumed `services/<request_id>/`, broke on Enhancements | **resolved and live-verified 2026-08-28** | 2026-08-28 | `docs/FORGE-Item25-QASecurity-EnhancementTarget-Spec.md` |
| #26 | No human gate between a feature PR opening and Deploy firing | **resolved and fully live-verified 2026-08-29**, including a real Deploy run triggered by a real merge | 2026-08-29 | `92a20b7`; `forge-demo-apps#33` (`9f3bc24c`) |
| #27 | `04-qa.yml`'s stale-label-clearing step re-queried current label state instead of this run's outcome | **resolved 2026-08-28**, found live during Item #25's §5 verification | 2026-08-28 | `5d07169` |
| #28 | Deploy Agent (Stage 6) had zero Enhancement-target awareness | **resolved and live-verified 2026-08-29**, per `docs/FORGE-Item28-DeployAgent-EnhancementTarget-Spec.md` | 2026-08-29 | `3a2d5c5`, `885b318` |
| #29 | `README.md` described a pipeline that didn't match reality (fictional slash-command approvals, a never-built production-deploy stage) | **resolved 2026-08-29**, rewritten to match the real label-driven pipeline | 2026-08-29 | — |
| #30 | No `security-check` mechanism existed for non-`feature/*`/non-`design/*` branch PRs | **resolved 2026-08-29**, permanently, via `ops-pr-security-noop.yml` | 2026-08-29 | `forge-demo-apps#34` (`34f40dd5`) |
| #31 | Fragile free-text JSON parsing across 5 stage agents (design/requirements/qa/security/ingestion) | **RESOLVED 2026-08-31** — root-cause fix via forced tool-use structured output (`invoke_agent()`'s new `output_schema` param); scope grew from design-only to all 5 during investigation (ingestion found during close-out sweep, not original spec scope); real live-verification spend $0.526872 across 5 stages + 1 deliberate `max_tokens` probe | 2026-08-31 | `29fed6e`, `ccb23fa`, `43b11d4`, `89985d7`, `ad74ba8`, `7cfd87d` |
| #32 | `create_ado_items.py` created a new parallel Epic for every Enhancement instead of linking to the existing service's real Epic | **RESOLVED 2026-08-31** — `_resolve_existing_epic_id()` reads the existing service's own `ado-work-items.json` and reuses its `epic.ado_id`; `02-design.yml` gained the "Determine Enhancement status" step every other stage already had; Greenfield path confirmed byte-for-byte unchanged; deliberate-failure path confirmed live. Fourth occurrence of the #24/#25/#28 "no existing_service awareness" pattern. Full narrative: `docs/FORGE-Item32-ADOEpicLinkage-Spec.md` | 2026-08-31 | `bbbe3d0`, `759cc58`, `c4b3d0c` |
| #33 | `forge-template#10` (REQ-2026-04's tracking issue) left open despite the pipeline completing and deploying | **RESOLVED 2026-08-31** — closed with a summary comment noting Item #32 as a related, non-blocking open item at the time (now also resolved) | 2026-08-31 | — |

---

## Suggested sequencing

**Nothing open requiring action.** For reference:
1. **Items #7, #11** — leave as-is; revisit only if either recurs or the underlying
   decision (staying on Next.js 14.x) changes.
2. **Phase 7 Enhancement Workflow validation** — **complete**, discovered
   2026-08-31 (see Build Plan v10). REQ-2026-04 proved the full enhancement path
   end-to-end; no further validation run needed unless Mike wants a second,
   deliberately-clean confirmation pass the way Phase 6 re-proved Phase 5.
3. **PR self-approval/branch-protection deadlock** — decided, not a to-do; the
   standing manual procedure is documented under "Accepted ongoing process"
   above for whenever it's next needed.
4. **6 throwaway ADO items** (#179–184) and a closed throwaway tracking issue
   (`forge-template#11`) from Item #32's live verification — safe to delete via
   the ADO UI whenever convenient, not urgent, not tracked as a numbered item.
