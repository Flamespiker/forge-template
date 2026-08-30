# FORGE Context — v77

**Session date:** 2026-08-29 (continuing same calendar day as v76's session)
**Prior doc:** v76
**Prepared by:** Claude.ai, from a housekeeping session pairing two doc-only
fixes plus a status check on open design decisions — no code, no live Azure
infrastructure touched

---

## Purpose & context

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE**
(Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated
software delivery pipeline automating the full development lifecycle from BA
intake through deployment.

**Two-repo model (unchanged):**
- `forge-template` (public, `Flamespiker/forge-template`) — orchestration/agent
  code
- `forge-demo-apps` (private) — target monorepo where generated app code lands

**Firm two-tool convention (unchanged):**
- Claude.ai: strategy, spec authorship, context documents
- Claude Code CLI: live execution, git operations, CLAUDE.md updates
- Mike shuttles between tools and holds all unilateral architecture/scope
  decisions

**This session's shape:** deliberately small and doc-only, explicitly pairing
multiple items in one session per Mike's request (one-doc-per-chat convention
suspended by explicit override). Originally scoped as three items (README
rewrite, backlog reconciliation, Item #27 spec); Item #27 turned out to already
be resolved (found during pre-work, not assumed), so the third slot was swapped
for a live status check on Items #1/#9/#10 instead. That check itself
surfaced a second stale-tracking finding — see below.

---

## Current state

### Item #29 (README.md rewrite) — RESOLVED this session

**Root cause (confirmed live against `forge-template` main before writing
anything, not assumed from CLAUDE.md's prior finding):** README described a
pipeline that didn't exist — a slash-command approval interface
(`/approve-requirements`, `/approve-qa`, `/reject-<stage>`), a production
deploy path (a `production` GitHub Environment gate, `forge-production`
provisioning instructions), and a wrong intake template path
(`templates/forge-intake-template.xlsx`, confirmed 404 — real file is
`docs/Intake Template.xlsx`). Independently re-confirmed all four issues via
direct `curl`/API checks this session (workflow files grepped for
slash-command handling — zero matches across all 7; `deploy_agent.py`'s own
docstring confirms production is explicitly out of scope; `templates/`
directory doesn't exist at repo root; `tracking/` contains only `.gitkeep`).

**Fix:** full README rewrite — pipeline diagram and "Approving a gate" table
now describe the real label-driven mechanism (`requirements-approved`,
`design-approved` via PR + label, `qa-approved`/`security-approved` applied
automatically by the QA/Security Agents from real test/scan results, Deploy
firing only once both labels are present **and** the feature PR is merged, per
Item #26). Removed all production-deploy references, replaced with an
explicit "staging only, not yet built" callout. Fixed the intake template
path and the `tracking/` directory description. Added a note about the GitHub
App's missing `workflows` permission (a real operational quirk from Item #26's
session, worth surfacing to any new team doing initial setup).

**Commit:** `0ad7aafd90091de8aed08b5ee4e72d7daf377d37` — confirmed on
`origin/main` via the GitHub API. (Landed as a single combined commit with the
backlog v2 file below, rather than the two separately-messaged commits
originally requested — see "Process note" below.)

### Open Items Backlog — reconciled to v2 this session

`FORGE-Open-Items-Backlog-v1.md` (2026-08-24) had gone stale — it only
reflected status through roughly Item #20 and, worse, still listed **Items
#9, #10, and #15 as open "Design/Policy Decisions"** when all three had
actually been resolved on 2026-08-27, before Item #26's session even started.
This was caught live during this session's status-check step (see below), not
assumed from the old doc.

**v2** (`docs/FORGE-Open-Items-Backlog-v2.md`) reconciles fully against
CLAUDE.md's actual Open Items / Known Gaps list, verified entry-by-entry:
- **"Real Bugs" category is now empty** — every item ever tracked there (#6,
  #8, #20, #24–#28, #30) is resolved.
- Genuinely still open: **Item #1** (Mike's design decision, unchanged),
  **Item #7** (deliberate leave-as-is), **Item #11** (accepted ongoing CVE
  risk, no fix planned), **Item #12** (cost-log bookkeeping backfill), and
  **Item #29** (resolved this same session, see above).
- Full one-line resolution index added for #2–#6, #8–#10, #13–#28, #30 so this
  doesn't need re-deriving from scratch again.

**Commit:** same combined commit as README.md, `0ad7aafd9...`, confirmed on
`origin/main`.

### Status check on Items #1/#9/#10 — completed this session

Requested as a replacement for the already-resolved Item #27 slot. Result:
- **Item #1** — confirmed still genuinely open, unchanged from v76. No spec
  should be written until Mike decides the direction (secrets-declaration
  convention: machine-readable convention vs. permanently manual vs. a
  lightweight non-blocking flag).
- **Item #9** — confirmed already resolved 2026-08-27 (live evidence via PR
  #27 showed the `feature/fix-*` convention already gets a real
  `security-check` scan; no code fix was needed).
- **Item #10** — confirmed already resolved 2026-08-27 (`enforce_admins`
  flipped `true` via the dedicated API endpoint, on Mike's prior go-ahead,
  decided together with #9).

This is the same "a tracker's 'still outstanding' note can itself be stale"
failure mode v76 already named as a lesson from Item #26's own session
(re: Item #28's status) — now confirmed to have also affected the backlog doc
itself and, apparently, this session's own carried-forward memory going into
it. Worth treating as a standing risk of any status summary (backlog doc,
memory, or otherwise) that isn't re-verified against CLAUDE.md/live repo state
before being acted on, not just a one-off surprise.

**CLAUDE.md close-out:** Item #29 marked resolved in CLAUDE.md's Open Items /
Known Gaps section (strikethrough + RESOLVED style, consistent with other
closed items), citing both commit SHAs above. Commit
`d579b2f3d7f7bd44492088a9396cd5757f168a07`, confirmed on `origin/main` via the
GitHub API.

**Process note (minor, not a convention change):** the original handoff
prompt asked for README.md and the backlog v2 file to land as two separate,
separately-messaged commits. Mike committed both together in one commit
("update docs") before Claude Code CLI's turn started. Claude Code CLI
correctly did not re-split or rewrite already-pushed history to force the
letter of the original plan — content was verified correct regardless. No
action needed; noting only so a future session doesn't wonder why the commit
history doesn't match the original prompt's step count.

**End-of-session Azure checks:** none needed — no live Azure infrastructure
was started or touched this session (doc-only work).

---

## On the horizon

- **Item #1** — Deploy Agent secret-declaration convention — unchanged, still
  Mike's design decision alone, no spec until decided.
- **Item #7** — deliberate leave-as-is, revisit only if it recurs on a
  still-live app.
- **Item #11** — accepted ongoing risk (21 `next@14.2.35` CVEs, no 14.x
  backport), no fix planned unless the decision to stay on Next.js 14.x itself
  gets revisited.
- **Item #12** — cost log backfill (REQ-2026-03 figures, including the whole
  Deploy Agent fix cycle #24–#28/#30). Good candidate to fold into whichever
  session next picks up Phase 7 Enhancement Workflow validation, rather than
  its own session.
- **Cost Estimator spec** (Stage 3 Implementation Coordinator) — scoped in
  v72, still not specced. Unchanged from v73–v76.
- **`req-2026-01-email-worker` crash-loop** — still unresolved, still tracked
  under Item #1's framing. Not touched this session.
- **Visual sign-in confirmation for the coverage-history filter feature**
  (REQ-2026-03's live change from PR #32) — still outstanding from v76,
  reachability confirmed but the feature itself not yet visually verified by
  Mike. Not touched this session (doc-only).
- **Phase 7 Enhancement Workflow validation** — with Items #24–#28/#30 all
  resolved, no known blocker remains for a clean Stage 3–6 Enhancement cycle.
  Still worth confirming explicitly with a dedicated end-to-end validation
  run — carried forward from v76, unchanged.

---

## Key learnings & principles

**New this session:**
- **A backlog/status doc can itself be the thing that's gone stale, not just
  individual items within it.** v1 of the Open Items Backlog was trusted
  (including by this session's own opening memory) as reflecting current
  state, but had missed three separate resolutions (#9, #10, #15) that
  happened three sessions ago. The fix isn't just "verify against live repo
  state before writing code or specs" (the existing standing discipline) — it
  needs to extend to status/tracking artifacts themselves before treating
  them as a planning input, not only to code or spec text.
- **Swapping a planned work item mid-session, once new information
  contradicts the plan, is cheaper than executing the stale plan anyway.**
  Item #27 was caught as already-resolved before any spec-writing effort was
  spent on it, and the freed slot was redirected to a status check that itself
  paid off (surfaced the #9/#10 staleness). Worth treating "the thing I was
  about to do turns out to already be done" as a signal to ask what else
  nearby might also be stale, not just a one-off dodge.

See v71–v76 for the full prior list (fix-at-one-layer-≠-fix-everywhere,
spec-evidence-can-be-wrong, unpushed-commits-are-the-same-failure-mode, a
tracker's "still outstanding" note can itself be stale, etc.) — unchanged, not
restated here. This session's second learning above is a direct continuation
of that exact v76-recorded pattern, now confirmed to reach one level higher
(the backlog doc, not just an individual item's status).

---

## Tools & resources (unchanged from v76)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps`
  (private)
- **Azure:** Container Apps (`forge-staging`/`forge-production` environments,
  `forge-build-rg`), Container Registry, Key Vault (`forge-build-kv`),
  PostgreSQL Flexible Server (`forge-req2026-03-pg`, not touched this
  session), Azure AD (`FORGE-DemoApps-SSO`, client ID
  `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant
  `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
  — lacks `workflows` permission (see Item #26/v76); now also documented
  directly in the public-facing README as of this session.
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`,
  `C:\Users\mikef\Projects\forge-demo-apps`
- **`docs/FORGE-Open-Items-Backlog-v2.md`** — supersedes v1, committed this
  session.

---

## Standing reminders (unchanged)

- Confirm via GitHub API (not local git, not verbal confirmation) that any
  commit is actually present on `origin/main` before treating work as
  complete or dispatching anything label-driven.
- Do not use organizational skills (`laa-brand`, `laa-security-review`,
  `freshservice-kb-article`) for FORGE project work unless Mike explicitly
  asks for one.
- Stop `forge-req2026-03-pg` at the end of every session that starts it — not
  applicable this session, not started.
- Any future `.github/workflows/*` file change in either repo needs to go
  through the App-permission workaround (push via Mike's own credentials
  first, then PR via the App identity) — now documented in the public README
  as of this session, not just in CLAUDE.md.
- **New this session:** treat status/tracking docs (Open Items Backlog,
  memory-carried summaries) as needing the same live-verification discipline
  as code or specs before acting on them — don't assume "still open" without
  checking CLAUDE.md's actual current state first.
