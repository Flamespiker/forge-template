# Backlog v9 → v10 delta (apply against the LIVE file, not this project's v6 copy)

The only Backlog copy in project knowledge is v6. Per this session's own
history, the live repo is on v9 (possibly further by now). Do not use this
file as a full replacement — it's a delta to apply against whatever the
live `docs/FORGE-Open-Items-Backlog-v9.md` actually contains, preserving
everything else in it unchanged.

## Changes to make

**Header:**
- Bump to v10. Supersedes: v9. One-line summary: "Item #43 (Configurable
  Pipeline Depth) built, live-verified, and closed this session; one new
  bug (#44) found during verification, logged not fixed."

**"Configurable Pipeline Depth" — remove from wherever it currently sits
as an un-numbered/not-yet-investigated item** (v6 had it in "Suggested
sequencing" #2; confirm where v9 moved it, since v9 apparently already
listed it as "known but unnumbered" per this session's investigation
findings) — replace with an entry in the **"Resolved since v1" table**:

| Item | One-line resolution | Date | Commit(s)/PR(s) |
|---|---|---|---|
| #43 | No enforced stopping point existed for a pipeline run short of full Deploy — a requester could only rely on nobody applying the next gate label by mistake, with real Azure/API cost exposure if that discipline slipped | **RESOLVED 2026-09-03** — new "Pipeline Depth" Intake Template field, four tiers (`Just Requirements`/`Up to Design`/`Up to Implementation`/`Up to Deployment`), contiguous-prefix-only per Mike's constraint. QA and Security bundled into the Implementation tier since they auto-trigger off the Implementation PR event rather than a human label — a split tier there would've needed a new gate that doesn't exist. `pipeline-config.json` persisted to `pipeline-state` by the Requirements Agent as soon as it runs (earliest architecturally-possible point); read by a new depth-check guard clause ANDed into every later stage's real-agent-invoking step. One mid-build correction: `request_id` isn't resolved until after the label guard clause in Design and Implementation (not just QA/Security as first flagged) — all four insertion points corrected, only Deploy's was already right. Live-verified via 3 real throwaway-issue tests (Greenfield/Up-to-Design, Enhancement/Up-to-Implementation, blank/regression), two deliberately re-run to isolate the new depth check from the pre-existing two-label gates. Zero Azure infra created across all three tests (confirmed via `az containerapp list`). Full narrative: `docs/FORGE-Item43-PipelineDepth-Spec-v3.md`, session context v87. | 2026-09-03 | `4ab81a0`, `ab5d8fb`, `875b8d1`, `cd7431c`, `fb8581a`, `df557fc` |

**New "Real Bugs" section entry (or add to it if v9 already has open bugs
— don't overwrite others):**

### Item #44 — `run_cost_estimate()` 404s if `design-approved` applied before design PR merge
Found during Item #43's Test 1 verification (label applied before merge,
deliberately, to isolate the depth-check event from the ordinary gate).
`run_cost_estimate()` reads `tasks.md` from `main`, which doesn't exist
until the design PR merges. Pre-existing, unrelated to Item #43's own
code — never hit in normal use because the documented Gate 2 flow always
merges before applying `design-approved`. Low urgency; worth a defensive
check or clearer failure message when it's picked up. Not yet scoped or
spec'd.

**"Suggested sequencing" section** — remove the old "Configurable Pipeline
Depth now unblocked" line (superseded, it's #43 now and it's closed), add:

- **Item #44** — well-scoped, good spec-and-fix candidate whenever picked
  up. Low urgency.
- **ADO cleanup** (not a numbered item, just a note) — real Epic/Feature/
  User Story items from Item #43's three test runs sitting under
  `spike99/FORGE-Build`, uncleaned per existing "whenever convenient"
  precedent.

---

**Prompt for Claude Code CLI to apply this:**

```
Fetch the live docs/FORGE-Open-Items-Backlog-v9.md from main (not any
cached/local copy). Apply the delta in FORGE-Backlog-v9-to-v10-delta.md
(pasted/attached) against it, preserving all v9 content not mentioned in
the delta unchanged. Save as v10, commit, push, and confirm the push
landed via a fresh GitHub API read (not local git). Report the commit SHA
and paste back the final "Resolved since v1" table row and Item #44 entry
so I can confirm they match what was intended before closing this out.
```
