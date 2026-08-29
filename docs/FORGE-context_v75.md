# FORGE Context — v75

**Session date:** 2026-08-29
**Prior doc:** v74
**Prepared by:** Claude.ai, from this session's Item #28 spec-through-close-out cycle
(spec authored by Claude.ai in v74; all investigation, implementation, and live
verification executed by Claude Code CLI this session)

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

**This session's shape:** the full Item #28 arc, start to finish, spanning the
diagnosis (reviewed in v74), spec authorship (v74), and — in this same chat, per
Mike's explicit one-time suspension of one-doc-per-chat — Claude Code CLI's live
investigation, both design-fork decisions, implementation, live verification, and
session close-out. Item #28 is now fully resolved and closed.

---

## Current state

### Item #28 — RESOLVED, closed this session

**Root cause (confirmed):** `deploy_agent.py`'s `_detect_units()` built
`services/<request_id>/` unconditionally — a third independent copy of the bug Items
#24/#25 already fixed — and separately, unit naming (`_finalize_unit_name`) was also
keyed on `request_id` alone, so fixing directory resolution without fixing naming
would have deployed REQ-2026-03's real code under brand-new, never-reconciled
`req-2026-04-*` Container Apps.

**Design forks resolved by Mike:**
- **§3.1** — Enhancement existing-service resolution via spreadsheet re-download
  (third call site of the existing pattern from Items #24/#25), not PR-body-line
  parsing.
- **§3.2** — "update in place": `naming_id = existing_service` when set, else
  `request_id`. §1.5's live investigation confirmed `_finalize_unit_name()`
  reproduces REQ-2026-03's real live Container App names
  (`req-2026-03-on-call-rost-5bb949`, `req-2026-03-frontend`) byte-for-byte from
  `existing_service` alone — no reconciliation step was needed.

**Implementation:**
- §2.1 (directory resolution + `--existing-service` flag, reusing the existing
  `resolve_service_root()` helper) — commit `3a2d5c5`.
- §2.2 (`naming_id` fallback, threaded through both unit-naming call sites) —
  commit `885b318`.
- §2.3 (cross-service FQDN) — confirmed a no-op; FQDN derivation reads `unit.name`,
  already correct once §2.2 lands.
- §2.5 (Greenfield unaffected) — confirmed via direct local equivalence testing.

**Live verification (`forge-template#10`/`forge-demo-apps#32`, run `33263474117`):**
- Deploy resolved `services/REQ-2026-03/` correctly, detected both units, built and
  pushed real images from PR #32's actual head commit (`2febc2a3...`).
- Container App names matched the pre-existing live names exactly
  (`req-2026-03-frontend`, `req-2026-03-on-call-rost-5bb949`) — confirmed via
  `az containerapp show`/`list`, not the job log. Zero `req-2026-04-*` resources
  created anywhere in `forge-build-rg`.
- Image SHA on both live apps changed from the old `ba994a85...` commit to the real
  new `2febc2a3...` commit — genuine "update in place," not an inferred success.
- Cross-service FQDN wiring confirmed correct (`FRONTEND_ORIGIN`,
  `NEXT_PUBLIC_API_BASE_URL`, `NEXTAUTH_URL` all point at the real live counterpart
  app).
- Greenfield isolation confirmed: REQ-2026-01's three units untouched, still on
  their known-good commit.
- **Visual sign-in confirmation — completed by Mike after this session's Claude Code
  CLI work, since no browser-automation tool was available in that environment.** The
  new coverage-history filter view renders correctly and works as expected on the
  live `req-2026-03-frontend` app. This was the one outstanding item Claude Code CLI
  flagged rather than glossing over — now closed out.

**CLAUDE.md close-out:** commit `fe5c99e4c349769de7af248973a9056185bee1b0`, confirmed
on `origin/main` via GitHub API. Item #28 marked resolved with the full narrative.

**End-of-session Azure checks (per standing convention):**
- `forge-req2026-03-pg` — was running, stopped, independently re-confirmed
  (`state: Stopped`).
- `az containerapp list` against `forge-build-rg` — exactly 5 apps, all accounted
  for (REQ-2026-01's three, REQ-2026-03's two), zero stray `req-2026-04-*` resources.
- `req-2026-01-email-worker`'s known crash-loop (Open Item #1-adjacent, unrelated to
  this session's work) — unchanged, `healthState: Unhealthy`, same pre-existing image
  tag. Confirmed still exactly as documented, not newly broken by this session.

---

## On the horizon

- **Phase 7 Enhancement Workflow validation** — Item #28 was the last known blocker
  for a clean Stage 3–6 Enhancement cycle on the Deploy side specifically. **Item #26
  (no human gate before Deploy) remains the other open blocker** — every successful
  QA+Security pass still auto-triggers a real Deploy the instant both labels land,
  which is exactly what happened again this session (re-applying `security-approved`
  fired Deploy immediately). Item #26 still needs its own dedicated fresh chat for
  the architecture decision alone.
- **Item #1** — Deploy Agent secret-declaration convention — unchanged, Mike's design
  decision alone, no spec until decided.
- **Cost Estimator spec (Stage 3 Implementation Coordinator)** — scoped in v72, not
  yet specced. Unchanged from v73/v74.
- **`req-2026-01-email-worker` crash-loop** — still unresolved, still tracked under
  Item #1's "Deploy Agent has no secret-discovery mechanism" framing (the Service Bus
  connection string was apparently never given a valid value). Confirmed unchanged
  again this session; not touched, not in scope for anything currently active.
- **Item #7** — deliberate leave-as-is, revisit only if it recurs on a still-live app.
- **`FORGE-Open-Items-Backlog-v1.md`** — still needs Item #28 added as resolved (it
  was only ever "newly added as open" per v73's reconciliation); worth folding into
  whichever session next touches the backlog doc, not urgent on its own.

---

## Key learnings & principles

**New this session:**
- **A stage that owns a persistent, named external resource can have two
  independent copies of the "same" bug that must both be fixed together** — Item
  #28's directory-resolution bug and its unit-naming bug were textually separate
  code paths using the same wrong id, and fixing only one would have silently
  created orphaned, never-updated duplicate cloud resources rather than raising
  loud. Confirmed live via §1.5's hash-reproduction check *before* committing to
  the "update in place" design, not assumed — this is the kind of check worth
  running preemptively any time a fix touches naming logic tied to a live external
  resource.
- **A verification pass that flags its own gap honestly (the missing
  browser-automation tool) is more trustworthy than one that claims full coverage
  it can't back up.** Claude Code CLI's explicit "I can't fabricate this" on the
  visual check, followed by Mike's own manual confirmation closing the loop, is the
  pattern worth repeating whenever a live-verification step needs a human's eyes
  and no tool exists to substitute for that.

See v71–v74 for the full prior list (fix-at-one-layer-≠-fix-everywhere,
spec-evidence-can-be-wrong, unpushed-commits-are-the-same-failure-mode, a tracker's
"still outstanding" note can itself be stale, etc.) — unchanged, not restated here.

---

## Tools & resources (unchanged from v74)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps`
  (private)
- **Azure:** Container Apps (`forge-staging`/`forge-production` environments,
  `forge-build-rg`), Container Registry, Key Vault (`forge-build-kv`), PostgreSQL
  Flexible Server (`forge-req2026-03-pg`, stopped this session), Azure AD
  (`FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant
  `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`,
  `C:\Users\mikef\Projects\forge-demo-apps`
- **`docs/FORGE-Item28-DeployAgent-EnhancementTarget-Spec.md`** — committed as part
  of this session's Item #28 fix (spec now lives alongside Items #24/#25's specs as
  historical reference).

---

## Standing reminders (unchanged)

- Confirm via GitHub API (not local git, not verbal confirmation) that any commit is
  actually present on `origin/main` before treating work as complete or dispatching
  anything label-driven.
- Do not use organizational skills (`laa-brand`, `laa-security-review`,
  `freshservice-kb-article`) for FORGE project work unless Mike explicitly asks for
  one.
- Stop `forge-req2026-03-pg` at the end of every session that starts it — done this
  session.
