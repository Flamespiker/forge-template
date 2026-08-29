# FORGE Context — v73

**Session date:** 2026-08-29
**Prior doc:** v72
**Prepared by:** Claude.ai, from this session's bookkeeping batch (spec authored here, executed by Claude Code CLI, no live investigation performed by Claude.ai directly)

---

## Purpose & context

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment.

**Two-repo model (unchanged):**
- `forge-template` (public, `Flamespiker/forge-template`) — orchestration/agent code
- `forge-demo-apps` (private) — target monorepo where generated app code lands

**Firm two-tool convention (unchanged):**
- Claude.ai: strategy, spec authorship, context documents
- Claude Code CLI: live execution, git operations, CLAUDE.md updates
- Mike shuttles between tools and holds all unilateral architecture/scope decisions

**This session's shape:** Bookkeeping-only session, explicitly framed as small/combinable items rather than a single investigation-first spec (a deliberate, one-time exception to one-doc-per-chat, since none of these carried a design fork). Claude.ai drafted a combined prompt covering four items; Claude Code CLI's live-file check surfaced that the backlog was far staler than the prompt assumed (seven items already resolved, not "leave as-is"); the prompt was corrected and re-issued before any file was touched; Claude Code CLI then executed the corrected reconciliation as a single commit.

---

## Current state

### Backlog reconciliation — DONE this session

`FORGE-Open-Items-Backlog-v1.md` reconciled against CLAUDE.md's live state as of 2026-08-29 (was stale since 2026-08-24). Commit `f715a635` on `origin/main`, confirmed via GitHub API.

**Resolved and marked as such in the backlog (dates per CLAUDE.md):**
- **#6** — `wait_for_all_threads_idle()` idle-vs-fatal-error blindness — resolved 2026-08-26 (`docs/FORGE-Item6-Item8-Fix-Spec.md`, commits `e300ddc`/`24ceb85`)
- **#8** — Implementation Coordinator `.github/workflows/*.yml` scope creep — resolved 2026-08-26 (same spec, commits `78a2f3f`/`5ef29de`)
- **#9** — ad hoc `fix/*` admin-merge — resolved 2026-08-27, turned out not to be a real bug (not a code fix)
- **#10** — `enforce_admins` on `forge-demo-apps` main — resolved 2026-08-27, flipped to `true`
- **#12** — cost log REQ-2026-03 backfill — resolved 2026-08-25 (commit `2fa77c2`), stale in the backlog from birth (one day after the backlog was written)
- **#15** — ad hoc PR tracking-issue line — resolved 2026-08-27, process fix (documented in CLAUDE.md), confirmed no recurrence since (only agent-opened PRs #30–#32 since then)
- **#20** — REQ-2026-01 app-insights type conflict — resolved 2026-08-26, `overrides` pin, merged/deployed/verified live via `az containerapp show`
- **#23** *(this backlog's own numbering)* — Stage 3 never extended for Enhancement requests — resolved 2026-08-27 (`docs/FORGE-Item23-Stage3-Enhancement-Spec.md`), live-verified against `forge-demo-apps#32`. **Numbering collision flagged:** CLAUDE.md independently renumbered this same fix **#24** to avoid colliding with CLAUDE.md's own separate, unrelated, already-resolved Item #23. Cross-reference by spec filename or commit, not bare item number, going forward.
- **#27** — `04-qa.yml` stale-label-clearing bug — resolved 2026-08-28 (commit `5d07169`), found live during Item #25's verification pass

**Left open, confirmed still accurate:**
- **#1** — Deploy Agent has no way to learn an app needs a given secret (Mike's design decision, standalone now that #9/#10 are resolved and no longer coupled to it)
- **#7** — archive-prefix mismatch, REQ-2026-02, one-off — deliberate leave-as-is, revisit only if it recurs on a still-live app

**Newly added as open:**
- **#28** — Deploy Agent has zero Enhancement-target awareness — confirmed live 2026-08-28 during Item #25's verification pass (real dispatch on `forge-template#10`/`forge-demo-apps#32` raised `ValueError: No deployable units detected`). Distinct from Item #26 (missing human gate) — this is about target-directory resolution specifically. Needs diagnosis before a spec, same shape #6/#8 used to be. Not yet specced.

Backlog doc now carries a header note flagging the 2026-08-29 reconciliation, so a future session checks CLAUDE.md before trusting the backlog's item statuses again.

**Suggested sequencing section:** old sequencing (written against a mostly-open backlog) marked superseded/struck through, kept for historical reference only. Current actual state: only **#1** and **#28** are real open work items; **#7** is deliberate leave-as-is.

### Cost log (Item #12) — no action needed

Already resolved 2026-08-25 (see above). No new cost-endpoint pull was needed this session; the corrected reconciliation reflected the existing resolution rather than performing fresh work.

### CLAUDE.md `user.interrupt` documentation — resolved, tracker was stale

The "carried since v68, still not addressed" note in prior context docs was itself stale. CLAUDE.md's "Manually killing a runaway Managed Agents session" section (commit `9e9be76`, 2026-08-26) already fully documents the `user.interrupt` procedure (curl call, thread-status confirmation, output check before archiving) — it predates even v69 (2026-08-27), which kept the item marked outstanding without re-checking CLAUDE.md. **Marking resolved as of this doc.** No CLAUDE.md changes were made this session (nothing needed fixing).

### Item #15 recurrence check — confirmed, no recurrence

No ad hoc (human/Claude-opened) fix PR has existed since the 2026-08-27 process fix landed. The only PRs since then (#30, #31, #32) were all agent-opened via the normal pipeline, which writes the tracking-issue line automatically.

---

## On the horizon

- **Item #1** — Deploy Agent secret-declaration convention — Mike's design decision alone, no spec until decided. Standalone now (no longer coupled to #9/#10, both resolved).
- **Item #28** — Deploy Agent Enhancement-target awareness — needs a diagnosis-first session (real investigation of `deploy_agent.py`'s target-resolution logic) before a spec can be scoped, same pattern #6/#8 used to require. Not yet specced.
- **Item #26 (no human gate before Deploy)** — still outstanding from v71/v72, has two live confirmations, needs its own fresh chat dedicated to the decision alone.
- **Cost Estimator spec (Stage 3 Implementation Coordinator)** — scoped in v72, not yet specced. Next action: fresh chat, investigation-first (read live `managed_agents_wrapper.py`, Stage 3 coordinator code, `04-qa.yml`'s label-gate implementation, `team/config.yaml`). Five open forks from v72 still need resolving in that spec: pre-flight estimate basis, gate mechanism shape, mid-session behavior, threshold storage/ownership, post-run reporting surface.
- **Phase 7 Enhancement Workflow validation** — continues; first real Stage 3–6 Enhancement cycle still pending clean Item #26 resolution.
- **Item #7** — deliberate leave-as-is, revisit only if it recurs on a still-live app.

---

## Key learnings & principles

**New this session:**
- **A tracker's "still outstanding" note can itself be stale.** Both the backlog doc (dated 2026-08-24, actually 7 of 9 "leave as-is" items already resolved) and the context doc's own "user.interrupt, carried since v68" note (already fully addressed by a 2026-08-26 CLAUDE.md commit) turned out to be tracking claims that were never re-checked against live source-of-truth. CLAUDE.md is the live state; any doc that duplicates status information needs to be re-verified against it, not assumed current, especially across multiple session boundaries.
- **Bookkeeping items are still worth a live-check-first prompt**, even when framed as "no investigation needed" — the prompt to Claude Code CLI should default to "verify current status before acting" rather than "assume the framing is accurate and proceed," even for supposedly low-risk documentation work. This session's correction (Claude Code CLI checked live state before touching any file, surfaced the staleness, and got the task re-scoped before committing) is the pattern to repeat.
- **One-doc-per-chat can be deliberately suspended** for a batch of genuinely independent, non-design-fork bookkeeping items — done explicitly this session, not a silent drift from the convention.

See v71/v72 for the full prior list (fix-at-one-layer-≠-fix-everywhere, spec-evidence-can-be-wrong, unpushed-commits-are-the-same-failure-mode, etc.) — unchanged, not restated here.

---

## Tools & resources (unchanged from v72)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **Azure:** Container Apps (`forge-staging`/`forge-production` environments, `forge-build-rg`), Container Registry, Key Vault (`forge-build-kv`), PostgreSQL Flexible Server (`forge-req2026-03-pg`, stop after each session), Azure AD (`FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`, `C:\Users\mikef\Projects\forge-demo-apps`
- **Cost reference:** `claude_agent_wrapper.py`'s `_MODEL_RATES` table (sonnet-4-6 $3/$15 per MTok in/out, opus-4-6 $5/$25, haiku-4-5 $1/$5, as of 2026-07-29); `docs/FORGE-pipeline-cost-log.md` (now fully current through REQ-2026-03, all stages); Managed Agents session cost endpoint; `README.md`'s cost table (~$0.08–0.32 USD Managed Agents runtime per Stage 3 session, 1–4 hours estimated)
- **Reconciled this session:** `docs/FORGE-Open-Items-Backlog-v1.md` — now current as of 2026-08-29, header note added flagging the reconciliation date

---

## Standing reminders (unchanged)

- Confirm via GitHub API (not local git, not verbal confirmation) that any commit is actually present on `origin/main` before treating work as complete or dispatching anything label-driven. Followed correctly this session (`f715a635` confirmed).
- Do not use organizational skills (`laa-brand`, `laa-security-review`, `freshservice-kb-article`) for FORGE project work unless Mike explicitly asks for one.
