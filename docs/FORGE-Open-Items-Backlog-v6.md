# FORGE — Open Items Backlog: Planning for Next Session(s)

**Prepared:** 2026-08-31 (Claude.ai)
**Supersedes:** v5 (2026-08-31, same day) — Item #34 built, live-verified, and
fully cleaned up this session; see below. No other content changed from v5.

**Headline finding from this pass:** Item #34 (Cost Estimator) — the last
remaining "on the horizon" item from v5 — is now fully resolved, closed out,
and cleaned up. This also unblocks the previously-blocked "Configurable
Pipeline Depth" idea, which had no stage to point at for its "Requirements +
Cost Estimate" stop point until now. **What's left open: nothing new** — same
as v5, just the two long-standing deliberate accepted-risk/leave-as-is items
(#7, #11) and the standing self-approval/branch-protection manual procedure.
Configurable Pipeline Depth remains un-numbered and not yet investigated —
ready to pick up, not yet started.

---

## Design / Policy Decisions — need Mike's call, not a spec

**Nothing open in this section right now.** Item #34's six design forks
(five from the original 2026-08-29 scoping session, one surfaced live by
Claude Code CLI's investigation) were all resolved by Mike this session —
see "Resolved since v1" below for the full list.

---

## Accepted ongoing process — decided, no fix planned

### PR self-approval / branch-protection deadlock — decided 2026-08-31, keep the manual workaround
Unchanged from v5. See v5's full writeup — standing 6-step procedure
documented there, still in force, will recur on the next ad hoc PR under
Mike's own account.

---

## Real Bugs — well-scoped, good spec-and-fix candidates

**None currently open.** Item #34's live verification found and fixed one
real P0 (`usage.list_cost.amount` returned as a string, not numeric — see
"Resolved since v1" below) same-session, before it ever reached production.

---

## Deliberately left as-is — not being pursued

### Item #7 — Archive-prefix mismatch (REQ-2026-02, once)
Unchanged from v5.

---

## Accepted ongoing risk — tracked, no fix planned

### Item #11 — 21 `next@14.2.35` CVE findings have no 14.x backport
Unchanged from v5.

---

## Bookkeeping — no spec needed, just do directly

**Nothing currently open.** Item #34's own scratch-state cleanup (test PRs,
branches, throwaway docs) was completed and confirmed same-session — not a
carried-forward bookkeeping item.

---

## Resolved since v1 (2026-08-24) — historical record, not action items

Full narratives live in CLAUDE.md's Open Items / Known Gaps section and the
relevant `docs/FORGE-Item*-Spec.md` files — this is a one-line-each index so
this doc doesn't need re-deriving from scratch again next time.

| Item | One-line resolution | Date | Commit(s)/PR(s) |
|---|---|---|---|
| #1 | Deploy Agent had no app-secrets wiring mechanism, and no way to discover in advance that a given app needs a given secret | fully resolved 2026-08-31 — Option 3 and Option 1 both live-verified | 2026-08-31 | `29073cd`, `6d1511c`, `a21b4a9`/`forge-demo-apps#35` |
| #2–#6, #8–#31 | See Backlog v5 for the full historical index — unchanged, not reproduced here | — | — | — |
| #32 | `create_ado_items.py` created a new parallel Epic for every Enhancement instead of linking to the existing service's real Epic | RESOLVED 2026-08-31 | 2026-08-31 | `bbbe3d0`, `759cc58`, `c4b3d0c` |
| #33 | `forge-template#10` left open despite the pipeline completing and deploying | RESOLVED 2026-08-31 | 2026-08-31 | — |
| #34 | Stage 3 (Implementation Coordinator) had no cost visibility before or after a real Managed Agents run — a genuinely unpredictable-duration, unpredictable-cost stage with zero pre-flight signal and manual-only post-run cost lookup | **RESOLVED 2026-08-31** — new `cost-approved` label (two-label AND-gate alongside `design-approved`, mirroring Item #26's Deploy shape); coarse shape-bucketed pre-flight estimate (`_estimate_implementation_cost()`) using unit count + Enhancement seed-file scaling + historical baselines; estimate-vs-actual comparison in the final PR comment; new `managed_agents_cost` structured log line closing the standing cost-log automation gap. Six design forks resolved (five scoped 2026-08-29, one — the empty 1-unit historical buckets — surfaced live during this session's build). Live-verified both Greenfield (`(1,False)` bucket, first-ever real data point, $0.51–0.56) and Enhancement (`(2,True)` bucket, live seed-file scaling, 94 files vs. the 87-file historical reference) against real Managed Agents sessions. **Found and fixed a real P0 during live verification:** `usage.list_cost.amount` returns as a string, not numeric — would have silently broken the comment/PR step on every real completed Stage 3 run. Confirmed fixed via a clean re-run before committing. All scratch state (2 test tracking issues, 1 unmerged draft PR + its branch, 2 throwaway doc directories, 5 merge-source branches) fully cleaned up and confirmed via fresh API reads. Full narrative: `docs/FORGE-Item34-CostEstimator-Spec.md` | 2026-08-31 | `1aee048`, `363067b` (P0 fixes) + 5 build commits; forge-demo-apps `#39` (closed, unmerged), `#41` (merged, scratch-doc removal) |

---

## Suggested sequencing

**Nothing open requiring action.** For reference:
1. **Items #7, #11** — leave as-is; revisit only if either recurs or the
   underlying decision changes.
2. **Configurable Pipeline Depth** — now unblocked (Item #34 shipped). Not
   yet numbered or investigated. Good candidate for next session's focus if
   Mike wants to pick it up; otherwise continues waiting, no urgency.
3. **PR self-approval/branch-protection deadlock** — decided, not a to-do;
   standing manual procedure documented above, unchanged from v5.
4. **Cost baseline recalibration** (new, not urgent) — `_COST_BASELINES_USD`'s
   constants are based on very thin historical data (as few as 1 real run
   per bucket in two cases). Worth a lightweight revisit once a handful more
   real Stage 3 runs accumulate — not a bug, expected for a first-cut
   heuristic. No action needed until then.
