# FORGE — Configurable Pipeline Depth ("Phase Checkpoint") — Spec v1

**Status:** DRAFT — pre-investigation. Written by Claude.ai per the two-tool
convention; not yet validated against live code. Claude Code CLI must
falsify every assumption below against the real repo before implementing.

**Item number:** Proposed **#43** — based on Items #1–#42 all being either
resolved or already claimed in the Backlog/CLAUDE.md as of the last session
recorded in memory. **Confirm this against the live `docs/CLAUDE.md` and the
newest `docs/FORGE-Open-Items-Backlog-v*.md` before filing** — the project
knowledge copy of the Backlog here is v6, but memory indicates a v9 already
exists live. Do not trust the number in this doc as final.

**Also known as:** "Phase Checkpoint" (Mike's term this session), tracked in
prior sessions as "Configurable Pipeline Depth." This spec treats them as the
same feature and uses "Pipeline Depth" as the canonical name (matches
existing Backlog/context-doc references) — flag if you'd rather rename it.

---

## 1. Problem Statement

Right now every pipeline run goes all the way to Deploy once a human keeps
applying gate labels — there's no way to declare, at intake time, "only run
this as far as Design" or "stop after Implementation, I just want to see the
code." The stopping point today is enforced by nothing but Mike's own
discipline in not applying the next label. That's fragile: a label applied
by the wrong person, a misclick, or simple forgetfulness about intent lets a
request roll further (and spend more — real Anthropic API cost, real
Managed Agents session-hours, real Azure Container Apps deployments) than
originally intended.

**Goal:** let the requester declare, at intake, how far the pipeline should
go — and have the pipeline itself refuse to go further, not rely on nobody
applying the next label by mistake.

## 2. Your Constraint (confirmed this session)

> The user can choose **up to** what agent/stage is needed — not an
> arbitrary subset. Choosing "Design" means every stage before Design runs
> too, in the existing locked order. There is no menu of "run Requirements
> and Security but skip Design" — that would violate Document 07's locked
> rule that stages 0a–6 execute in order, none skipped or reordered.

This spec is scoped as a **contiguous prefix selector**, not a stage picker.
It changes *where the pipeline stops*, never *which stages run* along the
way.

## 3. Selectable Depth Tiers

Stages 0a and 0b have no human gate (Document 02 §4.1–4.2) — they're not
meaningful "stopping points," they're prerequisites that always run before
the first real gate. QA (Stage 4) and Security (Stage 5) share a single
trigger (PR opened/updated) and run in parallel, so they can't be split into
separate depth tiers either. That leaves four real tiers plus the implicit
full run:

| Tier | Depth value | Last stage that runs | Stops before |
|---|---|---|---|
| 1 | `requirements` | Stage 1 — Requirements | Design |
| 2 | `design` | Stage 2 — Design (+ Cost Estimator) | Implementation |
| 3 | `implementation` | Stage 3 — Implementation | QA / Security |
| 4 | `qa_security` | Stage 4/5 — QA + Security | Deploy |
| 5 | `full` *(default)* | Stage 6 — Deploy | — nothing, full run |

Stages 0a (Enhancement-only ingestion) and 0b (Intake) always run regardless
of depth — they're prerequisites, not selectable stops.

**Design fork for Mike:** is bundling QA+Security into one tier acceptable,
or is there a real use case for "run QA but not Security" (or vice versa)?
Given they share one trigger today, splitting them would be a much bigger
change (a new trigger/gate shape) — recommend leaving them bundled unless
you have a concrete reason not to.

## 4. Greenfield vs. Enhancement Interaction

Depth is **orthogonal** to Request Type (Document 06's Greenfield/Enhancement
distinction). Both fields live independently in Intake Template Section B.
Every depth tier applies identically to both request types:

- **Greenfield, depth=`design`:** Stage 0b → Stage 1 → Stage 2, then stop.
  (Stage 0a never runs for Greenfield regardless of depth — that's existing
  locked behavior, unchanged.)
- **Enhancement, depth=`design`:** Stage 0a → Stage 0b → Stage 1 → Stage 2,
  then stop. Stage 0a still runs automatically because it's a prerequisite,
  not a depth-gated stage.

This spec does **not** touch the existing-service resolution logic (Items
#24/#25/#28/#32) or the Stage 0a enhancement-only trigger (Document 07:
Locked). Those stay exactly as they are for whatever tiers actually execute.

## 5. Where Depth Is Captured

Add one new field to Intake Template Section B (same section as Request
Type), e.g.:

| Field | Example value |
|---|---|
| Pipeline Depth | `Full Pipeline` \| `Through Requirements` \| `Through Design` \| `Through Implementation` \| `Through QA & Security` (choose one; leave blank for Full Pipeline) |

Mirrors the existing Request Type field's style (free-text yellow cell with
an example/enum in brackets, parsed and normalized by the Intake Agent — see
Document 07: Request Type is handled the same way). Blank/missing/unrecognized
values must default to `full` — same graceful-degradation posture the Intake
Agent already applies elsewhere, so older intake spreadsheets don't start
behaving differently.

## 6. Where Depth Is Enforced

**Open question for Claude Code CLI's investigation pass**, not settled
here: exactly which stage first has enough information to persist this
value, and in what file.

Proposed shape (verify against real code before building):

- Intake Agent parses the new field alongside Request Type, includes it in
  its summary comment (so it's visible on the tracking issue from the
  start).
- At `requirements-approved` time — the same moment `requirements.md` and
  `ado-work-items.json` get written to `pipeline-state` (Document 02 §4.3) —
  also write a small `pipeline-config.json` (e.g. `{"pipeline_depth":
  "design"}`) to the same branch, same location convention as the existing
  per-request docs. This makes it available to every later stage via the
  existing `get_file_contents()` helper (added Step 3.4, used by Design
  Agent onward) without needing a fresh spreadsheet parse.
- Every stage-2-through-6 agent script gains a depth check as **the first
  guard-clause step**, ahead of its existing precondition-label check
  (Document 07: "Guard clause on every workflow" is already Locked
  behavior — this is additive, not a new pattern):
  - Fetch `pipeline-config.json`.
  - If the tier about to run is beyond the configured depth, do **not**
    invoke the agent. Post a comment to the tracking issue stating the
    pipeline stopped at the configured depth (e.g. "Pipeline Depth was set
    to 'Through Design' at intake — stopping here. Implementation was not
    run."). Apply a terminal marker label (e.g. `pipeline-complete-at-depth`)
    so it's visible without reading comments. Exit **0**, not a failure —
    this is intended behavior, not an error, and shouldn't show a red X on
    a normal run.
  - If the tier is within depth, proceed exactly as today.

This deliberately does **not** try to stop a human from applying the next
gate label (e.g. `design-approved`) — GitHub doesn't give a clean way to
block a label application itself, and Document 07's existing guard-clause
pattern already assumes "label applied → workflow decides whether to
actually act," not "label application itself is gated." The workflow simply
refuses to act on a label that's beyond the configured depth, the same way
it already refuses to act on an out-of-order label today.

## 7. Design Forks — need your call, not mine

1. **Bundled QA+Security tier** (§3) — accept as one tier, or is there a
   real case for splitting them? (Recommend: accept as one tier.)
2. **Manual override / raise depth mid-flight.** If you set `design` at
   intake and later decide you actually want Implementation to run too, how
   does that happen? Options: (a) not supported — file a fresh request; (b)
   Orchestration Manager manually edits `pipeline-config.json` on
   `pipeline-state` and re-applies the relevant gate label; (c) a dedicated
   override label (`depth-override-implementation`) that any stage's guard
   clause also checks. (Recommend: (b) — no new mechanism, consistent with
   "Orchestration Manager can always intervene directly" precedent
   elsewhere in FORGE.)
3. **Terminal-stop UX.** Is a comment + label enough, or do you want the
   tracking issue itself closed/relabeled to make "this request is done, on
   purpose" unmistakable at a glance? (Recommend: comment + label, leave the
   issue open — matches how QA retry-limit halts are handled today.)
4. **Interaction with the Cost Estimator (Item #34).** Optional, not core:
   should the Stage 2 cost-estimate comment also note "Pipeline Depth is set
   to X, so stages beyond Design will not run" so the Technical Approver
   reads the estimate with the right scope in mind? (Recommend: yes, cheap
   to add, avoids a confusing juxtaposition of "here's the full-pipeline
   cost context" language next to a run that's about to stop early — but
   defer until the core mechanism is built and verified.)
5. **Classification in Document 07.** Once built, this needs a new row in
   `07_Customization_Ref_v4.md` — is the *existence* of the depth field
   Locked (core platform, every team gets it) with the *tiers* fixed, or
   should teams be able to define their own tier boundaries? (Recommend:
   Locked shape, same as Request Type — the tier list in §3 above is fixed
   by the stage structure itself, not a team preference.)

## 8. Backward Compatibility

- Missing/blank/unrecognized Pipeline Depth field → default `full`. No
  behavior change for any request that doesn't set the field, including
  every request run before this feature ships.
- No change to any Locked behavior in Document 07 (stage order, no
  skip/reorder, Stage 0a enhancement-only trigger, enhancement-target
  resolution). This feature only changes *where the run stops*, never *what
  runs along the way*.

## 9. Files Likely Touched (for Claude Code CLI's investigation, not final)

- `docs/Intake Template.xlsx` — new Section B field + Instructions tab
  update documenting the five tier values.
- `core/agents/intake_agent.py` — parse/normalize the new field, include in
  summary comment.
- `core/agents/requirements_agent.py` (or wherever `ado-work-items.json` is
  written) — write `pipeline-config.json` to `pipeline-state` at
  `requirements-approved` time.
- `core/lib/github_helper.py` (or a new small module) — read/write helper
  for `pipeline-config.json`, reusing the existing `get_file_contents()`
  pattern.
- `core/agents/design_agent.py`, `implementation` workflow/coordinator
  trigger, `qa_agent.py`/`security_agent.py` trigger, `deploy_agent.py` — add
  the depth guard clause ahead of each existing precondition check.
- `docs/06_Orchestration_v7.md` — document the new field, the terminal-stop
  label, and what Orchestration Managers see when a run stops early.
- `docs/07_Customization_Ref_v4.md` — new row per Design Fork #5 above.

## 10. Verification Plan (once built)

Mirrors the Item #34 precedent — real throwaway test issues, not
dry-run-only, since this gates real downstream spend:

1. Greenfield, depth=`design` — confirm Stage 2 runs and posts normally,
   confirm Stage 3 does **not** fire even if `design-approved` is applied,
   confirm the terminal comment/label appear.
2. Enhancement, depth=`implementation` — confirm Stage 0a still runs
   (prerequisite, not depth-gated), confirm Stage 3 runs, confirm Stage 4/5
   do not fire.
3. Default/blank depth (regression) — confirm an ordinary request with the
   field left blank runs Full Pipeline exactly as before, unaffected.

Real API/Managed Agents spend only for the stages actually exercised in
each test — same cost-discipline go-ahead required before running Test 2
(it reaches Stage 3, the expensive one) as for any other live Stage 3 run.

## 11. Out of Scope (this spec)

- No changes to Cost Estimator internals (Item #34) beyond the optional note
  in Design Fork #4.
- No changes to Enhancement/Greenfield existing-target resolution.
- No UI/dashboard — this is entirely spreadsheet-field + label + comment
  driven, consistent with "no separate dashboard to learn" (README).

---

**Next step:** hand this to Claude Code CLI for an investigation-only pass
(no code yet) — confirm the actual write site for `ado-work-items.json`,
confirm `get_file_contents()`'s real signature, confirm the current item
numbering against live `CLAUDE.md`/Backlog, and report back before any spec
revision or implementation begins.
