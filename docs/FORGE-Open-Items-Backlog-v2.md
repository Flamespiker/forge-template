# FORGE — Open Items Backlog: Planning for Next Session(s)

**Prepared:** 2026-08-29 (Claude.ai)
**Supersedes:** v1 (2026-08-24), which only reflected status through roughly Item #20
and had gone stale — several items it listed as open (#9, #10, #15, #27) were
resolved on 2026-08-27/28 without this doc being updated, and Items #21–#30 were
missing entirely. This version reconciles against CLAUDE.md's actual Open Items /
Known Gaps list and context v76, verified line-by-line rather than assumed.

**Headline finding from this reconciliation pass:** every item v1 classified as a
"Real Bug — well-scoped, good spec-and-fix candidate" (#6, #8, #20) has since been
resolved, along with #24–#28 and #30 discovered afterward. **The "Real Bugs"
category is currently empty.** What's left open is small: one genuine design
decision (#1), two deliberate accepted-risk/leave-as-is items (#7, #11), one
bookkeeping task (#12), and one already-scoped-but-deferred doc fix (#29, being
picked up this session alongside this reconciliation).

---

## Design / Policy Decisions — need Mike's call, not a spec

### Item #1 — Deploy Agent has no way to learn an app needs a given secret
**PARTIALLY RESOLVED 2026-08-31 — do not read as fully closed.** Option 3 (a
lightweight, non-blocking post-deploy crash-loop flag) was built and live-verified
end-to-end this session — see CLAUDE.md's Item #1 entry for the full writeup (two
independent real paths: manual `workflow_dispatch` against the known-broken
`req-2026-01-email-worker`, and a real automatic `workflow_run` trigger via a
`repository_dispatch: pr-merged` replay against `forge-demo-apps#32`). That closes
the "silent forever" half of this item: a crash-loop caused by a missing/invalid
secret now gets flagged on the tracking issue shortly after deploy, without blocking
the pipeline.

**What's still open, unchanged from v1:** the underlying discovery/prevention
question below (Option 1 territory) was explicitly out of scope for the Option 3
work and still needs Mike's call. The wiring *primitive* (`_wire_keyvault_secret()`)
exists and works — the missing piece is how Deploy Agent would ever know, on its
own, that a given app needs a given secret *before* deploying it (Option 3 only
tells you *after*). Every wiring so far has been a manual, one-off CLI invocation.
Real options worth Mike weighing:
- A machine-readable declaration convention (e.g. a `secrets.yaml` per service, or
  a section in `design.md` with a fixed schema Deploy Agent parses)
- Accept this as permanently manual — the primitive exists, tribal knowledge
  handles the "which secret" question, and that's fine given how infrequently new
  secrets get introduced
- Something in between (a lightweight convention checked by
  `_detect_design_gaps()`-style flagging, never blocking)

**Question for Mike:** is this worth solving generally, or is manual-per-secret an
acceptable permanent state given how rarely it comes up? No spec should be written
until this is decided — writing one first would mean guessing at a decision that
isn't Claude's to make.

*(Items #9, #10, and #15 previously lived in this section. All three are now
resolved — see "Resolved since v1" below. #9/#10 were decided together on
2026-08-27 as originally flagged; #15 the same day.)*

---

## Real Bugs — well-scoped, good spec-and-fix candidates

**None currently open.** Every item that ever sat in this category (#6, #8, #20)
has been resolved — see "Resolved since v1" below for each. If a new bug surfaces,
it belongs here, following the same investigation-first pattern used for #20 and
#24–#28.

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

### Item #12 — Cost log needs REQ-2026-03 figures backfilled — **RESOLVED 2026-08-31**
`docs/FORGE-pipeline-cost-log.md` was missing REQ-2026-03's actual Stage 1/3/4/5/6
cost figures, including the whole Deploy Agent fix cycle (#24–#28, #30). Pulled
directly from GitHub Actions logs (`agent_invocation` lines) and the Managed
Agents sessions API (3 Stage 3 sessions tied to the fix cycle, not just the
original build) — real total **$57.64** across all costed stages/requests to
date. See CLAUDE.md's own Item #12 entry and `docs/FORGE-pipeline-cost-log.md`
§2/§3 for the full breakdown. Commit `103c927` (forge-template).

### Item #29 — `README.md` describes a pipeline that doesn't match reality
Found 2026-08-29 during a routine README/memory review; deliberately not fixed
that session per Mike's explicit call (needed a proper rewrite, not a targeted
patch). **Being picked up this session** alongside this backlog reconciliation —
see this session's README.md commit for the resolution.

---

## Resolved since v1 (2026-08-24) — historical record, not action items

Full narratives live in CLAUDE.md's Open Items / Known Gaps section and the
relevant `docs/FORGE-Item*-Spec.md` files — this is a one-line-each index so this
doc doesn't need re-deriving from scratch again next time.

| Item | One-line resolution | Date | Commit(s)/PR(s) |
|---|---|---|---|
| #2 | REQ-2026-03 backend unit name exceeded Azure's Container App name length limit | resolved | — |
| #3 | No pipeline stage validated the app actually builds before Stage 6 | resolved | — |
| #4 | `qa_agent.py`'s Jest/Vitest JSON parsing had a file-collection blind spot | resolved | — |
| #5 | QA's `_MAX_RETRIES = 3` only picked which label to apply, never blocked/gated | resolved | — |
| #6 | `wait_for_all_threads_idle()` couldn't distinguish "finished" from "all threads fatally errored" | resolved | — |
| #8 | Implementation Coordinator's CI-workflow scope creep | resolved | — |
| #9 | Ad hoc `fix/*` branches needing `--admin` merge (4 occurrences) | **resolved 2026-08-27 — no code fix needed.** Live evidence (PR #27) confirmed the `feature/fix-*` convention already gets a real `security-check` scan; the 4 original cases predated that convention | 2026-08-27 | `docs/FORGE-Item9-Item15-AdHocFixDispatch-Spec.md` |
| #10 | `enforce_admins` on `forge-demo-apps` `main` was `false` | **resolved 2026-08-27**, flipped to `true` via the dedicated API endpoint (confirmed no other protection field changed), on Mike's go-ahead, coupled with #9's resolution | 2026-08-27 | — |
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
| #30 | No `security-check` mechanism existed for non-`feature/*`/non-`design/*` branch PRs | **resolved 2026-08-29**, permanently, via `ops-pr-security-noop.yml` | 2026-08-29 | `forge-demo-apps#34` (`34f40dd5`) |

---

## Suggested sequencing

1. **Item #1 (remaining Option 1 discovery/prevention decision only — Option 3
   shipped 2026-08-31)** — send to Mike whenever there's a natural moment; no
   urgency, nothing else is blocked on it.
2. **Item #12** — fold into whichever session next picks up Phase 7 Enhancement
   Workflow validation; low effort, no separate session needed.
3. **Items #7, #11** — leave as-is; revisit only if either recurs or the underlying
   decision (staying on Next.js 14.x) changes.
4. **Phase 7 Enhancement Workflow validation** — not a backlog "item" in the
   bug-fix sense, but the next substantive piece of real work now that #24–#28/#30
   have cleared every known blocker. Tracked in the context doc, not duplicated
   here.
