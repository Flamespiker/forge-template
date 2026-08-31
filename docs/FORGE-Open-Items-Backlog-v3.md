# FORGE — Open Items Backlog: Planning for Next Session(s)

**Prepared:** 2026-08-31 (Claude.ai)
**Supersedes:** v2 (2026-08-29).

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
against Build Plan v9→v10 (see that doc's v10 update). One new open item
surfaced from that discovery: **Item #32**, a real ADO-linkage design gap. What's
left open: the long-standing PR self-approval/branch-protection deadlock and
#32 (new) — both design/process questions for Mike, not specs — two deliberate
accepted-risk/leave-as-is items (#7, #11), and one small bookkeeping call (#33,
closing `forge-template#10`).

---

## Design / Policy Decisions — need Mike's call, not a spec

**Two items open requiring a decision:** the PR self-approval/branch-protection
deadlock (flagged below, still unresolved) and Item #32 (new, below). Neither
blocks anything else.

*(Item #1 lived in this section through the morning of 2026-08-31; fully
resolved that same day — both Option 3 and Option 1 built and live-verified —
see "Resolved since v1" below. Items #9, #10, and #15 previously lived here
too; all resolved 2026-08-27.)*

### Flagged, not a decision yet — PR self-approval / branch-protection deadlock will recur
Hit for real 2026-08-31 while merging `forge-demo-apps#35` (Item #1 Option 1's
`design.md` backfill PR): the PR was opened under Mike's own GitHub account (the
same identity `gh` authenticates as in this environment), and `main`'s branch
protection requires 1 approving review with `enforce_admins: true` (Item #10) —
GitHub rejects a self-approval outright, and there's no admin-bypass path anymore.
Resolved this one time via a fully-audited temporary workaround (confirm current
protection state → drop `required_approving_review_count` to 0 → merge → confirm
the merge via a fresh API read → immediately restore to 1, independently
re-verified) — see CLAUDE.md's Item #1 entry for the full blow-by-blow. **No
permanent fix was made; this will happen again on the next ad hoc PR opened under
Mike's own account.** Real options for a future decision, not urgent:
- Keep doing the temporary-disable dance each time (fully safe if done carefully,
  as this session showed, but manual and easy to forget a restoration step)
- Drop the required-review count permanently (weakens the human-review gate this
  project has otherwise been protecting since Item #10)
- Route ad hoc/backfill PRs through the `forge-pipeline` App identity instead of
  Mike's personal account, so a human reviewer (Mike) can actually approve them
  normally

### Item #32 — ADO Enhancement work lands as a new parallel Epic, never linked to the existing Epic
**New, found 2026-08-31** during a reconciliation pass confirming Build Plan step
7.7 (see Build Plan v10). `create_ado_items.py` has no concept of "attach to an
existing Epic" at all — for REQ-2026-04 (an Enhancement to REQ-2026-03) it created
a brand-new Epic (#169) with its own Features/User Stories, entirely disconnected
from REQ-2026-03's real Epic (#134). The one QA bug filed during that request
parent-links correctly to a User Story — but that User Story sits under the new,
unlinked Epic, not under #134. The deployed code itself is unaffected (it correctly
updates REQ-2026-03's real services/Container Apps either way) — this is purely an
ADO traceability gap.

**Question for Mike, options worth weighing:**
- Look up the existing service's real Epic (a stored mapping, or an ADO query by
  title/tag/`existing_service`) and create the new Features/User Stories as
  children of it
- Accept a new parallel Epic as fine for now — deployed-code correctness doesn't
  depend on ADO hierarchy, and this may be a rare-enough case to leave manual
- Something in between (flag the mismatch for a human to manually re-parent in ADO,
  no code change)

No spec should be written until this is decided — same pattern Item #1 followed
before its resolution.

---

## Real Bugs — well-scoped, good spec-and-fix candidates

**None currently open.** Item #31 (below) was the last occupant of this section
and is now root-cause resolved — see "Resolved since v1."

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

### Item #33 — `forge-template#10` (REQ-2026-04's tracking issue) left open
**New, found 2026-08-31.** The full pipeline for REQ-2026-04 completed and
deployed — labels `qa-approved`+`security-approved` are on the issue, PR #32
merged 2026-08-29 — but the tracking issue itself was never closed, unlike Phase
5/6's tracking issues. Not blocked on Item #32's ADO-linkage decision above; purely
a "should this be closed now" call for Mike.

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

---

## Suggested sequencing

1. **The PR self-approval / branch-protection deadlock** (flagged under "Design /
   Policy Decisions") — no urgency until the next ad hoc PR needs opening under
   Mike's own account; send to Mike whenever convenient.
2. **Item #32** — a design/policy decision, no urgency, nothing else blocked on
   it; send to Mike whenever there's a natural moment.
3. **Item #33** — a one-click bookkeeping call (close `forge-template#10` or
   leave it); no investigation needed.
4. **Items #7, #11** — leave as-is; revisit only if either recurs or the underlying
   decision (staying on Next.js 14.x) changes.
5. **Phase 7 Enhancement Workflow validation** — **complete**, discovered
   2026-08-31 (see Build Plan v10). REQ-2026-04 proved the full enhancement path
   end-to-end; no further validation run needed unless Mike wants a second,
   deliberately-clean confirmation pass the way Phase 6 re-proved Phase 5.
