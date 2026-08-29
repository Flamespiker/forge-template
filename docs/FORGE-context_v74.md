# FORGE Context — v74

**Session date:** 2026-08-29
**Prior doc:** v73
**Prepared by:** Claude.ai, from this session's Item #28 diagnosis-and-spec work (no
Claude Code CLI execution yet — that's the next session)

---

## Purpose & context

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE**
(Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated
software delivery pipeline automating the full development lifecycle from BA intake
through deployment.

**Two-repo model (unchanged):**
- `forge-template` (public, `Flamespiker/forge-template`) — orchestration/agent code
- `forge-demo-apps` (private) — target monorepo where generated app code lands

**Firm two-tool convention (unchanged):**
- Claude.ai: strategy, spec authorship, context documents
- Claude Code CLI: live execution, git operations, CLAUDE.md updates
- Mike shuttles between tools and holds all unilateral architecture/scope decisions

**This session's shape:** Item #28's diagnosis (already scoped as needed, per v73's
"On the horizon") was pasted in and reviewed, then — per Mike's explicit instruction
this session — the spec was authored in the same chat rather than a fresh one,
deliberately suspending one-doc-per-chat for this session only (same category of
one-time override v73 used for its bookkeeping batch, not a silent drift from the
convention). No live investigation or code execution happened this session; both
remain Claude Code CLI's job next.

---

## Current state

### Item #28 — diagnosis reviewed, spec authored this session

**Diagnosis (already completed before this session, reviewed here):** confirmed one
root cause, not two — `deploy_agent.py`'s `_detect_units()` builds
`services/<request_id>/` unconditionally, a third independent copy of the exact bug
Items #24/#25 already fixed, this time in Deploy. For REQ-2026-04 (Enhancement,
existing service REQ-2026-03), this resolves to a nonexistent directory, both
unit-detection helpers return empty, and `run_deploy_agent()` raises `ValueError: No
deployable units detected` — exactly the error confirmed live 2026-08-28 during Item
#25's verification pass. The diagnosis also surfaced a second, harder question that
isn't itself a bug in today's code but would become one if only the directory fix
landed: unit **naming** (`_finalize_unit_name`) is separately keyed on `request_id`
too, so fixing directory resolution alone would deploy REQ-2026-03's real code under
brand-new `req-2026-04-*` Container Apps, never touching REQ-2026-03's actual live
resources — new surface area Items #24/#25 never had to face, since none of those
three stages own a persistent, named external resource.

**Spec authored this session:**
`docs/FORGE-Item28-DeployAgent-EnhancementTarget-Spec.md` (output alongside this
context doc; not yet placed in the repo — Claude Code CLI's job at the start of the
next session).

Spec structure, mirroring Items #24/#25's established shape:
- **§1 Investigate first** — seven points, most load-bearing: §1.5, confirming
  whether `_finalize_unit_name()` can deterministically reproduce REQ-2026-03's live
  Container App names (`req-2026-03-on-call-rost-5bb949`, `req-2026-03-frontend`) if
  the naming key switches from `request_id` to `existing_service`. If the hash suffix
  doesn't reproduce the live names, "update in place" (the spec's recommended
  default) needs a one-time manual reconciliation before it can work as designed —
  this must be confirmed before §2.2 is implemented, not assumed.
- **§2 Scope** — reuses the existing `resolve_service_root()` helper from
  `core/agents/utils/enhancement_target.py` (built for Item #25) as Deploy's third
  call site; introduces a `naming_id` (existing_service if set, else request_id)
  distinct from the directory-resolution target, threaded through unit naming and
  (confirmed, not assumed fixed) cross-service FQDN prediction.
- **§3 Design forks for Mike:**
  - §3.1 (resolution mechanism: spreadsheet re-download vs. parsing the posted
    "Related service" line) — recommended default carries forward Mike's already-
    confirmed Item #25 choice (spreadsheet re-download) for consistency.
  - **§3.2 (the real fork this spec introduces, explicitly not defaultable):** update
    REQ-2026-03's existing live Container Apps in place, vs. deploy under
    `req-2026-04-*` as a separate parallel slot requiring a manual cutover step
    nothing in FORGE today implements. Recommended default is "update in place" (an
    Enhancement is a change to an existing live service, not a new one), but flagged
    as a genuine architecture decision with live-resource consequences — sequencing
    §3 explicitly calls out that §3.2 must be resolved by Mike, not defaulted
    silently the way §3.1 can be.
  - §3.3 (staging vs. production applicability) — flagged for completeness; FORGE has
    never deployed to production, so this should be a non-issue as written.
- **§5 Live verification** — uses tracking issue `forge-template#10` /
  `forge-demo-apps#32` (already `qa-approved` + `security-approved` per Item #25's
  closeout) as the vehicle, gated on Mike's explicit go-ahead before a real Deploy
  fires (same live-Azure-consequence discipline as Item #25's own verification,
  compounded here by §3.2's stakes).

**Not yet done:** any live investigation, any code change, any live dispatch. All of
§1 through §5 are Claude Code CLI's job in a fresh session.

---

## On the horizon

- **Item #28 execution (Claude Code CLI, fresh session)** — start with §1's live
  investigation (all seven points), report back before any code is written; §1.5's
  finding directly determines whether §3.2's recommended default is achievable as
  specced or needs a one-time reconciliation step first.
- **Item #1** — Deploy Agent secret-declaration convention — still Mike's design
  decision alone, no spec until decided. Unchanged from v73.
- **Item #26 (no human gate before Deploy)** — still outstanding, still needs its own
  dedicated fresh chat for the decision alone. Unrelated to Item #28 beyond the shared
  fact that its absence means Deploy still auto-fires the moment both QA/Security
  labels land — relevant again for Item #28's own §5 live verification.
- **Cost Estimator spec (Stage 3 Implementation Coordinator)** — scoped in v72, not
  yet specced. Unchanged from v73; five open forks still need resolving whenever this
  is picked up.
- **Phase 7 Enhancement Workflow validation** — continues; first real Stage 3–6
  Enhancement cycle still pending clean Item #26 resolution (and now also Item #28's
  fix, since #28 is what currently blocks Deploy specifically for an Enhancement
  request).
- **Item #7** — deliberate leave-as-is, revisit only if it recurs on a still-live app.

---

## Key learnings & principles

**New this session:**
- **One-doc-per-chat can be deliberately suspended for a diagnosis-plus-spec pair
  too, not just a bookkeeping batch** — done explicitly this session per Mike's
  instruction, following the same "not a silent drift" discipline v73 established for
  its own exception.
- **A stage that owns a persistent, named external resource introduces a genuinely
  new class of design fork that a stage which only produces ephemeral artifacts
  (a branch, a report) never has to face.** Items #24/#25 both only needed the
  existing-service value to know which directory to read from — the identity of what
  they produced was never tied to it. Deploy's unit naming being separately keyed on
  the wrong id is the same shape of bug as #24/#25's original directory bug, but
  fixing it wrong (or fixing only the directory half) has a materially different
  consequence: duplicate, never-reconciled live cloud resources, not just a wrong
  scan target. Worth checking for on any future stage that manages a named resource.

See v71/v72/v73 for the full prior list (fix-at-one-layer-≠-fix-everywhere,
spec-evidence-can-be-wrong, unpushed-commits-are-the-same-failure-mode, a tracker's
"still outstanding" note can itself be stale, etc.) — unchanged, not restated here.

---

## Tools & resources (unchanged from v73)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps`
  (private)
- **Azure:** Container Apps (`forge-staging`/`forge-production` environments,
  `forge-build-rg`), Container Registry, Key Vault (`forge-build-kv`), PostgreSQL
  Flexible Server (`forge-req2026-03-pg`, stop after each session), Azure AD
  (`FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant
  `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`,
  `C:\Users\mikef\Projects\forge-demo-apps`
- **New this session:** `docs/FORGE-Item28-DeployAgent-EnhancementTarget-Spec.md`
  (output, not yet committed to the repo — Claude Code CLI to place it under `docs/`
  in its next session per standing convention)

---

## Standing reminders (unchanged)

- Confirm via GitHub API (not local git, not verbal confirmation) that any commit is
  actually present on `origin/main` before treating work as complete or dispatching
  anything label-driven.
- Do not use organizational skills (`laa-brand`, `laa-security-review`,
  `freshservice-kb-article`) for FORGE project work unless Mike explicitly asks for
  one.
