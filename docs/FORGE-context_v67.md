# FORGE Context — v67

**Session date:** 2026-08-26
**Prior doc:** v66
**Prepared by:** Claude.ai, from this session's spec authorship plus Claude Code CLI's live execution and verification

---

## Purpose & context

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment. Phase 6 (Repeatability) is complete; this session opened **Phase 7 (Enhancement Workflow)**.

**Two-repo model (unchanged):**
- `forge-template` (public, `Flamespiker/forge-template`) — orchestration/agent code
- `forge-demo-apps` (private) — target monorepo where generated app code lands

**Firm two-tool convention (unchanged):**
- Claude.ai: strategy, spec authorship, context documents
- Claude Code CLI: live execution, git operations, CLAUDE.md updates, README.md updates
- Mike shuttles between tools and holds all unilateral architecture/scope decisions

**This session's shape:** normal one-doc-per-chat convention (resumed after v66's deliberate multi-item batch). Single deliverable: `docs/FORGE-Phase7-Ingestion-Agent-Spec.md`, authored, iteratively hardened across three CLI review passes before build, then executed and live-verified by Claude Code CLI in the same thread. This doc closes the thread out.

---

## Current state

**Build Plan step 7.1 (and 3.11) is done, live-verified, checked off.** Mike's direction at kickoff: next phase is Phase 7 — Enhancement Workflow, starting with the Codebase Ingestion Agent since it's app-agnostic core-template mechanism that the rest of Phase 7 depends on.

**No blocking items remain.** Next action is Build Plan step 7.2 — choosing and writing the actual enhancement's intake spreadsheet — explicitly out of scope for this session, belongs in a fresh chat.

---

## This session's work, in order

### 1. Spec authored: `docs/FORGE-Phase7-Ingestion-Agent-Spec.md`

Covers Build Plan 3.11/7.1 only (not 7.2+). Built from a live-code review (fetched by `main` ref rather than pinned SHA — GitHub API was rate-limiting unauthenticated requests this session; flagged explicitly in the doc as a caveat rather than silently proceeding).

Two design forks traced and resolved by control-flow inspection rather than escalated as open questions:
- **Fork A (Stage 0a trigger placement):** despite the "0a before 0b" naming, Ingestion can only run after the intake spreadsheet is parsed (Stage 0b's job), since the Enhancement flag and existing-service name live there. Resolved as a conditional step *inside* `00-intake.yml` itself, running in parallel with the BA's clarification round — no new label, no new workflow file, no added latency.
- **Fork B (commit location):** `existing-architecture-summary.md` commits to `docs/<request-id>/` on `pipeline-state`, same rationale/pattern as `requirements.md`/`ado-work-items.json` (Phase 4 step 4.8 retrofit — `main` requires PR review, this content was never meant to go through one).

### 2. Three CLI review passes hardened the spec before build

- **Pass 1 (live-verification pass):** CLI confirmed every cited line/function against real code, and surfaced a genuine gap the spec had only flagged as a hypothetical — the intake template's "Existing Service Name" example text (`client-portal`, a descriptive slug) doesn't match how `services/` folders are actually named in the live monorepo (`services/REQ-2026-0X/`, request-ID-based). Resolved with a two-layer fix mirroring the v66 Item #8 precedent ("strict rejection over silent auto-remap"): (1) fix the template's example text at the source, (2) a defensive backstop in the new agent — if the given service name doesn't resolve to a real `services/` folder, don't guess; fail loudly.
- **Pass 2:** CLI caught that the Layer 2 backstop's exit-code semantics and `--dry-run` interaction were both left implicit. Resolved: the backstop **raises** (non-zero exit, red step, post-comment-then-re-raise — the standard ADR-0011 failure contract), not a quiet skip; and its tracking-issue comment follows the same `--dry-run` print-instead-of-post contract as every other agent, no exception carved out for this path.
- **Pass 3:** CLI caught a cosmetic leftover — §7's sequencing section still described the Layer 2 case as "comment-and-skip" after §3.3 had already been resolved to "comment-then-raise." One-line fix; both sections now agree.

### 3. Full-chain live test — practical API blocker, resolved with a manual step

`00-intake.yml`'s attachment-download step needs a real GitHub `user-attachments` URL, which only the web UI's drag-and-drop produces — not exposed via REST/GraphQL/`gh` CLI. Resolved the same way the project has handled this exact class of gap before (Azure AD live-token capture): one manual step (Mike drag-and-drop-attaches the fixture to a throwaway issue), everything else automated and live-verified around it. Precedent explicitly cited: settling for invocation-only verification would leave the real webhook→label→workflow trigger chain unconfirmed, against this project's "real executed evidence required before logging closed" standard.

Three throwaway issues (`forge-template` #7, #8, #9), scratch request IDs (not real REQ-2026-0X numbers, to avoid any collision with real pipeline data), all closed after verification:
- **#7 (Greenfield no-op):** real REQ-2026-03 intake spreadsheet reused as the fixture — confirmed the new Stage 0a step correctly no-ops.
- **#8 (Enhancement happy path):** real summary produced and committed to `pipeline-state`, confirmed, then cleaned up.
- **#9 (Layer 2 mismatch backstop):** real non-zero exit, real posted comment — confirmed the backstop fires as designed, not just as mocked.

**Real bug caught mid-test, not just at the end:** the first live attempt against #7 silently exercised the *old* pre-Phase-7 workflow — local commits hadn't been pushed to `origin` before the test started. Caught by noticing the new steps were missing from the Actions run's step list (not by a failure — it would have silently "passed" against stale code), pushed, redid the case against real code. Same "verify before trusting" discipline this project has leaned on repeatedly (v66's SHA-pinning convention, `gh run rerun`'s stale-SHA gotcha) — worth carrying forward explicitly as a reminder to confirm the remote is current before trusting any live-test result, not just before editing a file.

### 4. Build artifacts, all live-verified

1. `github_helper.get_repo_tree()` — new Git Trees API wrapper (`recursive=1`, filtered client-side by path prefix). Confirmed live: bare branch names resolve directly against the real API, no separate branch→SHA lookup needed.
2. `docs/Intake Template.xlsx` — "Existing Service Name" example text corrected (Pass 1 fix).
3. `core/agents/ingestion_agent.py` — the Codebase Ingestion Agent. Two-pass file-selection (full filtered tree always included; manifest/config files always read in full; remaining token budget spent on largest/most-central source files by descending size). Layer 2 mismatch backstop raises `EnhancementServiceNotFoundError`-equivalent, non-zero exit, dry-run-respecting comment.
4. `00-intake.yml` — new conditional Stage 0a step, guarded on `overview["request_type"]` (confirmed live as plain free text, not a checkbox as Document 02 describes — case-insensitive matching was the right call).
5. `requirements_agent.py` — optional `existing-architecture-summary.md` fetch, graceful absence handling (missing summary logs a warning, doesn't block the stage).
6. `design_agent.py` — same fetch, same graceful-absence handling.
7. `CLAUDE.md` and `FORGE_Build_Plan_v9.md` updated; Build Plan steps 3.11/7.1 checked off.

---

## Key learnings & principles (new/updated this session)

- **A confirmed live mismatch beats a hypothetical flagged-as-open-question** — the spec's §3.3 explicitly flagged the existing-service-name field as unverified; CLI's live pass turned that into a confirmed, concrete bug (wrong example text) rather than leaving it as an assumption either direction. Flagging honest uncertainty in a spec, rather than guessing confidently, is what let the live pass catch something real.
- **A resolved design fork should still be fully specified, not just directionally resolved** — Pass 2 showed that "raise on mismatch" alone wasn't enough; exit-code semantics and `--dry-run` interaction both needed to be explicit, or an implementer would default to whichever was easiest to code. Resolving *what* happens doesn't automatically specify *how* it's observable.
- **Cross-references within a single doc need a consistency pass, not just a correctness pass** — Pass 3's catch (§7 vs. §3.3 disagreeing after only one was updated) is a reminder that fixing one section of a spec can leave a stale echo elsewhere; worth a final skim of the whole doc after any resolved-fork edit, not just the section that changed.
- **When an API genuinely can't automate a step, do the one manual step and verify everything else live around it** — same principle as the Azure AD token-capture workaround, now confirmed to generalize (GitHub attachment upload has the same shape of gap). Don't downgrade to invocation-only verification just because full automation isn't available.
- **"Push before you trust a live test" is a distinct check from "verify against live code before editing"** — the unpushed-commits near-miss shows the same discipline needs to run at test time, not just at edit time: a live-looking test result against stale remote code is a silent false pass, not a failure that announces itself.

---

## On the horizon

- **Build Plan step 7.2** — choose and write the actual enhancement's intake spreadsheet. Fresh chat, per one-doc-per-chat convention. A candidate was proposed (not decided) at spec-authorship time: REQ-2026-03's own intake spreadsheet already flags a low-risk gap — R-010 explicitly deferred a "dedicated reporting UI" for the claim/release event log that's already being recorded, and the Overview tab's out-of-scope list separately excludes "historical reporting or analytics." A read-only coverage-history view would be additive (no changes to the write-path concurrency logic that actually matters for correctness), and a real test of whether the underlying event-log data model was actually built to support it — exactly what Codebase Ingestion should surface if it's missing. Needs Mike's explicit confirmation before the next chat starts drafting the spreadsheet.
- **First real Enhancement-flagged request through the full pipeline** is also the first live exercise of everything Ingestion feeds into (Requirements/Design's optional-fetch paths) beyond the throwaway test-issue fixtures — worth treating as integration verification for this session's work, similar to how v66 treated the enhancement phase's first run as integration verification for its own batch.
- **Carried forward, unchanged from v66:** items #1, #7, #9, #10, #11, #15 (accepted-risk/standing-procedure, no action expected); Item #22's third test case (scale-rule units, untestable until something generates one); the ad hoc admin-merge pattern (four occurrences in v66's session, none since — still just flagged for future attention, not urgent).
- **Postgres server** (`forge-req2026-03-pg`) — confirm stopped if this session touched it (it didn't — no live app testing occurred, only pipeline-mechanism test issues).

---

## Tools & resources (unchanged from v66)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **Azure:** Container Apps (`forge-staging`, `forge-production` environments in `forge-build-rg`), Azure Container Registry, Azure Database for PostgreSQL Flexible Server (`forge-req2026-03-pg`, Burstable B1ms, Canada Central — stop after each session), Key Vault (`forge-build-kv`), Azure AD (single-tenant app registration `FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **New this session:** `core/agents/ingestion_agent.py`, `github_helper.get_repo_tree()`, Stage 0a conditional step in `00-intake.yml`, `docs/FORGE-Phase7-Ingestion-Agent-Spec.md`
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`, `C:\Users\mikef\Projects\forge-demo-apps`
