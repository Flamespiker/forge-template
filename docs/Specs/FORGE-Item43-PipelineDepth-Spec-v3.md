# FORGE — Configurable Pipeline Depth ("Phase Checkpoint") — Spec v3

**Status:** Design forks resolved (1, 2, 4, 6 confirmed by Mike; 3
clarified, no change needed; 5 partially resolved, one small open point).
Tier structure simplified from v2's five tiers to four, per Mike's naming.
Ready for a build task once §7's one remaining open point is called.

**v3 changelog:**
- Tier structure collapsed from 5 tiers to 4 — "Implementation" and
  "QA/Security" merged into a single tier (§3). This also resolves a
  mechanical question v2 didn't surface: QA (Stage 4) and Security
  (Stage 5) trigger automatically off "Implementation PR opened or
  updated" (Document 02 §4.6/§4.7) — there's no human gate between
  Implementation finishing and QA/Security firing. A standalone
  "Implementation-only, stop before QA/Security" tier would have required
  adding a new gate that doesn't exist today. Bundling them (as Mike
  independently proposed) avoids that entirely.
- §5's Request Type reference clarified — it's the existing Greenfield/
  Enhancement field in Intake Template Section B, unrelated to Pipeline
  Depth except as a parsing-pattern precedent.
- §6 guard-clause table updated: Stage 3/4/5 now check the same depth
  threshold (all three ARE the "implementation" tier), simplifying the
  insertion versus v2's separate implementation/qa_security thresholds.
- Fork resolutions recorded in §7.

---

## 1. Problem Statement

*(unchanged from v2)* Every pipeline run today goes all the way to Deploy
once a human keeps applying gate labels. There's no enforced stopping
point — only discipline in not applying the next label. Goal: let the
requester declare, at intake, how far the pipeline should go, and have the
pipeline itself refuse to go further.

## 2. Constraint

*(unchanged)* Contiguous prefix selector only — "up to X" runs everything
before X too, in the existing locked order. No arbitrary stage subsets.

## 3. Selectable Depth Tiers — SIMPLIFIED in v3

Four tiers, per Mike's naming:

| Tier | Depth value | Stages that run | Stops before |
|---|---|---|---|
| 1 | `requirements` | Stage 1 — Requirements (includes automatic ADO Epic/Feature/User Story creation on `requirements-approved`, per Document 02 §4.3 — this is existing behavior, not new) | Design |
| 2 | `design` | Stage 2 — Design (+ Cost Estimator) | Implementation |
| 3 | `implementation` | Stage 3 — Implementation, **and** Stage 4/5 — QA + Security (bundled — see changelog) | Deploy |
| 4 | `full` *(default)* | Stage 6 — Deploy | — nothing, full run |

Stages 0a (Enhancement-only ingestion) and 0b (Intake) always run
regardless of depth — no gate exists at either point (Document 02
§4.1–4.2), so they aren't stopping points.

**Why Tier 3 bundles Implementation with QA+Security:** QA and Security's
trigger is "Implementation PR opened or updated," not a label a human
applies (Document 02 §4.6–4.7; confirmed in the guard-clause investigation
— `04-qa.yml`/`05-security.yml` check "PR still open at this head SHA," not
a gate label). Once Stage 3 opens the implementation PR, QA and Security
fire automatically. A separate "stop after Implementation, before QA/
Security" tier would need an entirely new gate mechanism that doesn't exist
today — not worth building for a tier nobody asked for once the mechanics
were clear.

## 4. Greenfield vs. Enhancement Interaction

*(unchanged — reconfirmed per Mike's explicit ask)* Depth is orthogonal to
Request Type. Both fields live independently in Intake Template Section B.
All four tiers apply identically whether the request is Greenfield or
Enhancement:

- **Greenfield, depth=`design`:** Stage 0b → 1 → 2, then stop. (Stage 0a
  never runs for Greenfield, any depth — unchanged locked behavior.)
- **Enhancement, depth=`design`:** Stage 0a → 0b → 1 → 2, then stop.
- **Greenfield, depth=`implementation`:** Stage 0b → 1 → 2 → 3 → 4/5, then
  stop before Deploy.
- **Enhancement, depth=`implementation`:** Stage 0a → 0b → 1 → 2 → 3 → 4/5,
  then stop before Deploy.

This spec does not touch existing-service resolution (Items #24/#25/#28/
#32) or the Stage 0a enhancement-only trigger (Document 07: Locked) — those
apply exactly as today for whichever tiers actually execute.

## 5. Where Depth Is Captured

*(Terminology clarified — "Request Type" = the existing Greenfield/
Enhancement field in Intake Template Section B, distinct from the new
Pipeline Depth field.)*

New Intake Template Section B field:

| Field | Example value |
|---|---|
| Pipeline Depth | `Just Requirements` \| `Up to Design` \| `Up to Implementation` \| `Up to Deployment` (choose one; leave blank for Up to Deployment) |

Blank/missing/unrecognized → default `full` (Up to Deployment) — same
graceful-degradation posture as elsewhere in FORGE.

**Confirmed with Mike (was open item #3):** depth needs to be established
"right away, on submitting the requirements spreadsheet." This is already
what the design does — Pipeline Depth is captured on the Intake Template at
BA submission, and persisted to `pipeline-config.json` on `pipeline-state`
as soon as the Requirements Agent runs (triggered automatically by
`clarification-complete`, before any human reviews the draft or applies
`requirements-approved`). There's no earlier point in the pipeline with a
durable, downstream-readable location — Stage 0a/0b don't write to
`pipeline-state` — so this is as early as architecturally possible.

**Parsing location — one small open point (was Fork #5):** investigation
found Request Type isn't parsed by a reusable Intake Agent function; it's
an inline Python block inside `.github/workflows/00-intake.yml` (lines
92–124). Two ways to handle Pipeline Depth:
- **(a) Mirror the inline pattern** — add an equivalent inline block to the
  same workflow step. Faster, consistent with today's precedent.
- **(b) Lift both into a real shared helper module** — fixes a pre-existing
  testability gap while this code is already open, more work now.

**Defaulting to (a)** unless you'd rather do (b) now — say the word and
I'll flip it, otherwise Claude Code CLI builds it as an inline block
matching the existing Request Type step.

## 6. Where Depth Is Enforced

**Write site — confirmed, unchanged from v2.**
`core/agents/requirements_agent.py`, `run_requirements_agent()`, the
`commit_files()` call at lines 342–349. `pipeline-config.json` becomes a
third key in that same call, alongside `requirements.md` and
`ado-work-items.json`.

**Read helper — confirmed reusable, zero new auth wiring.**
`core/agents/utils/github_helper.py:316`,
`get_file_contents(path: str, branch: str = "main") -> str`. Every
stage-2-through-6 workflow already has the GitHub App env vars set and
already calls this function for other artifacts.

**Guard-clause insertion points — SIMPLIFIED in v3** (Stage 3/4/5 now share
one threshold instead of two):

| Stage | File | Existing guard clause | Line | Depth check inserted |
|---|---|---|---|---|
| 1 Requirements | `01-requirements.yml` | Confirm `clarification-complete` | 51 | None — floor tier, always runs |
| 2 Design | `02-design.yml` | Confirm `requirements-approved` | 71 | Immediately after, same pattern |
| 3 Implementation | `03-implementation.yml` | Confirm `design-approved`/`cost-approved` | 93 | Immediately after, same pattern |
| 4 QA | `04-qa.yml` | Confirm PR still open | 68 | **After request-id resolution (~line 94), not immediately after line 68** |
| 5 Security | `05-security.yml` | Confirm PR still open | 68 | Same wrinkle as QA — after request-id resolution |
| 6 Deploy | `06-deploy.yml` | Confirm `qa-approved`/`security-approved`/merge | 129 | Immediately after, same pattern |

Stages 3, 4, and 5 all check the **same** threshold value (`implementation`
tier) — there's no longer a separate check between Implementation finishing
and QA/Security starting, since they're one tier now.

Each depth check: fetch `pipeline-config.json`; if the current stage's tier
exceeds the configured depth, don't invoke the agent, post a comment naming
the configured depth and the skipped stage, apply a terminal marker label
(`pipeline-complete-at-depth`), exit 0 (intended behavior, not a failure).

Does not attempt to block a human from applying the next gate label — the
workflow just refuses to act on it, same as it already refuses out-of-order
labels today.

## 7. Design Fork Resolutions

| # | Fork | Resolution |
|---|---|---|
| 1 | Bundled QA+Security tier | **Confirmed** — bundled, and further merged with Implementation into one tier (§3) |
| 2 | Manual override / raise depth mid-flight | **Confirmed: manual edit** — Orchestration Manager edits `pipeline-config.json` on `pipeline-state` directly, then re-applies the relevant gate label. No new override-label mechanism. |
| 3 | When depth is established | **Clarified, no change needed** — captured at Intake Template submission, persisted as soon as Requirements Agent runs (§5) |
| 4 | Cost Estimator note | **Confirmed: yes** — Stage 2 cost-estimate comment will also state the configured depth |
| 5 | Parsing location (inline vs. shared helper) | **Defaulting to (a) inline**, matching existing Request Type pattern — flag if you want (b) instead |
| 6 | Document 07 classification | **Confirmed: go with recommendation** — Locked shape, tier list fixed by stage structure, not team-configurable |

## 8. Backward Compatibility

Missing/blank/unrecognized Pipeline Depth → default `full`, no behavior
change for any existing or not-yet-configured request. No change to any
Locked Document 07 behavior.

## 9. Files Touched

- `docs/Intake Template.xlsx` — new Section B field (four values, §5) +
  Instructions tab update.
- `.github/workflows/00-intake.yml` — add Pipeline Depth normalization as an
  inline block alongside the existing Enhancement-status step (lines
  ~92–124), per Fork #5 default.
- `core/agents/requirements_agent.py` — add `pipeline-config.json` as a
  third key in the existing `commit_files()` call (lines 342–349).
- `.github/workflows/02-design.yml` (after line 71), `03-implementation.yml`
  (after line 93), `04-qa.yml` (after request-id resolution, ~line 94, not
  line 68), `05-security.yml` (same wrinkle), `06-deploy.yml` (after line
  129) — one new depth-check step each, `implementation`-tier threshold
  shared by Stage 3/4/5.
- `core/agents/design_agent.py` (or wherever the Stage 2 cost-estimate
  comment is composed) — add configured-depth note, per Fork #4.
- `docs/06_Orchestration_v7.md` — document the new field, the four tier
  values, terminal-stop label, what an early stop looks like on the
  tracking issue.
- `docs/07_Customization_Ref_v4.md` — new Locked row for Pipeline Depth
  (existence + tier list), per Fork #6.

## 10. Verification Plan

1. Greenfield, depth=`design` — Stage 2 runs and posts normally; Stage 3
   does **not** fire even if `design-approved` is applied; terminal
   comment/label appear.
2. Enhancement, depth=`implementation` — Stage 0a still runs (prerequisite);
   Stage 3 runs; QA and Security both run (bundled tier); Deploy does not
   fire even once QA/Security both pass.
3. Default/blank depth (regression) — ordinary request with the field blank
   runs Full Pipeline exactly as before.

Real API/Managed Agents spend only for stages actually exercised — same
cost-discipline go-ahead required before Test 2 (reaches Stage 3) as any
other live Stage 3 run.

## 11. Out of Scope

- Cost Estimator internals beyond the depth note (Fork #4).
- Enhancement/Greenfield existing-target resolution.
- UI/dashboard.

---

**Next step:** confirm Fork #5's default (inline parsing, §5) or say if you
want the shared-helper approach instead — that's the only remaining open
point. Once called, this is ready to hand to Claude Code CLI as a **build**
task (not investigation-only) for the Files Touched in §9.
