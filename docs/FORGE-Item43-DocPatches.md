# Item #43 doc patches — README, Product Spec, Architecture Doc

Three docs to patch, none of them CLAUDE.md (that's already closed out).
Apply as three separate small commits, or one combined commit if you'd
rather — these are documentation-only, no code, so bundling is reasonable
here (unlike the build commits, which were split by concern for
bisect/revert safety).

---

## 1. Architecture Document — REAL GAP, fix this one for sure

**File:** `docs/02-forge-architecture-document-v4.md`
**Location:** §3 Agent Topology table, the Requirements Agent row (line 89
in the reviewed copy — confirm against live line numbers).

**Current:**
```
| **Requirements Agent** | Clarification round marked complete | Spreadsheet + Q&A record (+ ingestion summary, if enhancement) | `requirements.md` (committed to `monorepo:docs/<request-id>/`), draft ADO work item payloads (not yet created) |
```

**Replace with:**
```
| **Requirements Agent** | Clarification round marked complete | Spreadsheet + Q&A record (+ ingestion summary, if enhancement) | `requirements.md`, `pipeline-config.json` (committed to `monorepo:docs/<request-id>/`), draft ADO work item payloads (not yet created) |
```

This table duplicates `06_Orchestration_v7.md`'s artifact table (which
already got the `pipeline-config.json` row added during Item #43's build)
— same information, different framing (trigger/input/output vs. artifact/
description/producer). It was missed during the build because nobody
cross-checked this second table against the first. Worth a version bump
note at the top of the doc per its existing changelog convention, e.g.:

```
**Post-review addition (Item #43):** Requirements Agent's Outputs column
now includes `pipeline-config.json`, matching the artifact already added
to `06_Orchestration_v7.md`'s table during Item #43's build.
```

---

## 2. Product Specification — cross-cutting feature addition

**File:** `docs/01-forge-product-specification_v2.md`
**Location:** §3.7 Cross-Cutting Features (apply across all stages)

**Add one bullet** after the existing four:

```
- **Configurable pipeline depth:** a requester can declare, at intake, how
  far a run should go (Just Requirements / Up to Design / Up to
  Implementation / Up to Deployment) — a contiguous prefix of the fixed
  stage sequence, not an arbitrary stage picker. Every later stage checks
  this before running, so an accidentally-applied gate label can't push a
  run further than intended (Item #43).
```

Placement rationale: this genuinely is cross-cutting (every stage 2-6
checks it, not just one stage's concern), matching the shape of the
existing bullets in this section (traceability, state tracking) rather
than belonging under any single stage's numbered subsection (3.1-3.6).

---

## 3. README — user-facing quickstart mentions

**File:** `README.md`

**(a) "Running your first pipeline" section** — add one line after the
existing intake-template note:

```
> **Pipeline depth:** the intake template also has an optional "Pipeline
> Depth" field — leave it blank for a normal full run, or set it to stop
> the pipeline early (e.g. "Up to Design") if you only need to review
> architecture without paying for implementation, QA, security, and
> deploy. See the Orchestration Manager Guide for the full tier list.
```

**(b) "Approving a gate" table** — add a closing note directly under the
existing table (not a new row, since depth isn't a gate itself — it
changes whether later gates ever get reached):

```
> If the intake spreadsheet's Pipeline Depth field was set to something
> short of "Up to Deployment," the pipeline stops on its own once that
> tier completes — applying a later `*-approved` label won't push it
> further. A comment and a `pipeline-complete-at-depth` label appear on
> the tracking issue when this happens.
```

Both additions are deliberately light — README is onboarding material, not
a full spec; the Orchestration Manager Guide (`06_Orchestration_v7.md`)
already has the complete tier-by-tier detail from Item #43's build, and
that's where README should point rather than duplicating it.

---

**Prompt for Claude Code CLI:**

```
Apply the three doc patches in FORGE-Item43-DocPatches.md (attached/pasted)
against the live repo:
1. docs/02-forge-architecture-document-v4.md — Requirements Agent row fix
   (real gap, matches 06_Orchestration_v7.md's already-patched table)
2. docs/01-forge-product-specification_v2.md — new cross-cutting feature
   bullet in §3.7
3. README.md — two small additions (Running your first pipeline section,
   Approving a gate table note)

Confirm each file's exact current line numbers before editing — the ones
cited in the patch doc are from a point-in-time review copy and may have
shifted. Commit (one commit per file or combined, your call), push, and
confirm via a fresh GitHub API read against main. Report commit SHA(s).
```
