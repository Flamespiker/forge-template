# FORGE Context — v76

**Session date:** 2026-08-29
**Prior doc:** v75
**Prepared by:** Claude.ai, from this session's Item #26 spec-through-close-out
cycle (spec authored by Claude.ai this session; all investigation,
implementation, live merge/deploy, and verification executed by Claude Code
CLI this session)

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

**This session's shape:** the full Item #26 arc, start to finish — spec
authorship (investigation-first), Claude Code CLI's live investigation
(confirming and correcting parts of the spec's assumptions), two design forks
resolved by Mike, implementation across both repos, an unplanned but real
architectural gap discovered and permanently fixed along the way (Item #30),
and live §5 verification via a real first-ever merge to `forge-demo-apps`'
`main` and a real staging Deploy. Item #26 is now fully resolved and closed.

---

## Current state

### Item #26 — RESOLVED, closed this session

**Root cause (confirmed):** no human gate existed between a feature PR opening
and Deploy firing. `06-deploy.yml` triggered on `issues: [labeled]` against the
tracking issue, gated only by `qa-approved`/`security-approved` both being
present — it never checked whether the underlying feature PR in
`forge-demo-apps` had actually been merged to `main`. `resolve_feature_pr()`
resolved the *currently open* PR with no merge-state awareness at all.

**Design forks resolved by Mike:**
- **§3.1** — Option A: `notify-forge.yml` dispatches a new `pr-merged` event on
  real PR merge (`pull_request: closed` filtered on `merged == true`),
  mirroring the existing QA/Security dispatch pattern, rather than polling
  merge state from inside Deploy's own guard clause (Option B, rejected —
  can't guarantee a re-fire once merge finally happens).
- **§3.3** — branch protection on `forge-demo-apps` `main` left as-is.
  Investigation confirmed it already enforces a real human gate (1 approving
  review, required `security-check` status, `enforce_admins: true`) —
  Item #26's fix rides on top of that existing gate rather than needing to
  build a new one.

**Key investigation finding beyond the spec's own assumptions:**
`resolve_feature_pr()`/`list_open_prs_by_head()`/`list_open_prs()` hardcode
`state=open` against GitHub's list-PRs endpoint — structurally incapable of
resolving an already-merged PR, not just untested for it. The `pr-merged`
trigger path therefore had to use the dispatch payload's own PR number/head SHA
directly, and resolve the tracking issue number via the existing
`resolve-tracking-issue` (which reads the PR body regardless of state), not
`resolve-feature-pr`. A related plumbing gap — `ISSUE_NUMBER` only ever
resolves from `github.event.issue.number` on the `issues: labeled` trigger,
which doesn't exist on `repository_dispatch` — was caught and fixed before
implementation, request-type-agnostic (applies identically to Greenfield and
Enhancement, since the gate itself never branches on request type).

**Implementation:**
- `06-deploy.yml` (`forge-template`) — commit `92a20b7`, confirmed on
  `origin/main`. Adds the `repository_dispatch: [pr-merged]` trigger alongside
  `issues: [labeled]`, resolves `ISSUE_NUMBER` via `resolve-tracking-issue` on
  that path, uses the dispatch payload's own PR number/SHA for checkout, and
  gates the guard clause on both labels **and** merge state regardless of
  which trigger fired.
- `notify-forge.yml` (`forge-demo-apps`) — PR #33, merged (commit `9f3bc24c`
  on `main`). Adds the `pull_request: [closed]` → `pr-merged` dispatch.
- **Item #30 (new, resolved same session):** PR #33 hit a real, previously
  undiscovered gap — no mechanism produced a `security-check` status for
  ops/`.github` file changes (only `feature/*` and `design/*` branches were
  covered), and `enforce_admins: true` (Item #10) meant the old
  admin-merge workaround (used for Item #23's similar ops PRs) no longer
  applied. Fixed permanently, not one-off: `ops-pr-security-noop.yml`
  (PR #34, merged, commit `34f40dd5`) — a committed, narrowly-scoped no-op
  check mirroring `design-pr-security-noop.yml`'s already-accepted pattern,
  scoped to an `ops/*` branch prefix with the same double-guard discipline.
  **Live correction to the plan's own premise:** the anticipated
  "chicken-and-egg" bootstrap problem (new workflow can't check its own first
  PR) turned out not to apply — GitHub evaluates `pull_request`-triggered
  workflows using the head branch's own files for same-repo (non-fork) PRs,
  so `ops-pr-security-noop.yml` satisfied its own first run automatically.
  A one-off manual bootstrap check was posted per the original plan but
  confirmed redundant after the fact (harmless, not needed). PR #33 then
  needed a `main`-merge-into-branch to pick up the new file and get a real,
  non-manual `security-check` pass before merging cleanly.
- Both ops branches confirmed deleted post-merge (404 on lookup). `main` tip
  is `9f3bc24c`.

**Live verification (§5, real merge of `forge-demo-apps#32`):**
- Pre-merge state confirmed clean: `security-check: success` already on
  PR #32's head commit (`2febc2a3...`), `forge-template#10` still carrying
  both `qa-approved`/`security-approved`, PR #32 blocked only on the missing
  approving review.
- Mike approved and merged #32 for real — the first genuine merge to
  `forge-demo-apps`' `main`.
- `pr-merged` dispatch fired for real; `06-deploy.yml` ran (not skipped);
  Deploy resolved `services/REQ-2026-03/` as the existing service (Item #28)
  and built/pushed real images from PR #32's actual head commit.
- Confirmed via `az containerapp show` (not job log) that REQ-2026-03's live
  Container App image SHA changed to the new commit.
- Reachability confirmed: frontend redirects cleanly to
  `/api/auth/signin?callbackUrl=%2F` (NextAuth alive), backend's
  `/api/v1/shifts` returns `401 Unauthorized` (endpoint alive, correctly
  enforcing auth).
- **Same visual-confirmation gap as Item #28:** no authenticated browser
  session available in Claude Code CLI's environment to visually confirm the
  coverage-history filter feature itself renders — reachability-level
  confirmation only. **Mike's own sign-in to visually confirm the actual
  feature still outstanding**, same pattern as Item #28's closeout.
- `CLAUDE.md` close-out: commit `206fd18`, confirmed on `origin/main`. Item #26
  marked resolved with the full narrative and complete §5 evidence chain
  (real merge → real dispatch → real Deploy run → independently confirmed
  Container App image change).

**End-of-session Azure checks (per standing convention):**
- `forge-req2026-03-pg` — confirmed shut down.

---

## On the horizon

- **Visual sign-in confirmation for the coverage-history filter feature
  (REQ-2026-03's live change from PR #32)** — reachability confirmed, feature
  itself not yet visually verified. Mike to confirm directly, same as Item
  #28's own outstanding item last session.
- **`FORGE-Open-Items-Backlog-v1.md`** — still stale (only reflects up through
  roughly Item #20; missing #24–#30 entirely). Needs Item #26 added as
  resolved and Item #30 added and marked resolved, alongside the still-pending
  Item #28 addition flagged in v75. Worth a dedicated reconciliation pass
  rather than piecemeal edits, given how far behind it now is.
- **Item #1** — Deploy Agent secret-declaration convention — unchanged, Mike's
  design decision alone, no spec until decided.
- **Cost Estimator spec (Stage 3 Implementation Coordinator)** — scoped in
  v72, still not specced. Unchanged from v73–v75.
- **`req-2026-01-email-worker` crash-loop** — still unresolved, still tracked
  under Item #1's framing. Not touched this session.
- **Item #7** — deliberate leave-as-is, revisit only if it recurs on a
  still-live app.
- **Phase 7 Enhancement Workflow validation** — with Item #26 now resolved
  (alongside Item #28 last session), no known blocker remains for a clean
  Stage 3–6 Enhancement cycle. Worth confirming this explicitly next session
  rather than assuming — no dedicated end-to-end validation run has been
  called out and executed as such yet.

---

## Key learnings & principles

**New this session:**
- **A mechanism-level fix (a trigger/gate change) should be checked for
  hidden assumptions that only work for one request type** — Item #26's
  `ISSUE_NUMBER` resolution gap on the new `repository_dispatch` trigger would
  have broken identically for Greenfield and Enhancement alike, since the gate
  itself never branches on request type. Caught before implementation by
  explicitly asking "are we sure this applies to both" rather than assuming a
  mechanism fix is automatically request-type-neutral just because it doesn't
  mention request type anywhere in its own logic.
- **A helper function's real behavior can differ from its apparent contract
  in a way that matters for a *different* caller than the one it was built
  for.** `resolve_feature_pr()`'s `state=open` hardcoding was fine for its
  original callers (which only ever needed an open PR) but structurally wrong
  for a new caller needing to act *after* merge — confirmed live via
  `get_pr()`'s actual response fields on PR #32, not assumed from reading the
  function's docstring alone.
- **A "chicken-and-egg" bootstrap problem anticipated in a spec can turn out
  not to exist, and this is only knowable by checking live Actions run
  history, not by reasoning about the YAML in the abstract.** Same-repo
  (non-fork) `pull_request`-triggered workflows evaluate using the head
  branch's own files, so a new workflow file can satisfy its own first PR
  automatically. Worth checking this empirically before assuming a manual
  bootstrap step is required, on any future "new workflow needs to pass its
  own gate" situation.
- **A real architectural gap (Item #30) can surface as a side effect of
  routine implementation work, not from a dedicated investigation pass.**
  PR #33 hit it organically; treating it as worth a permanent fix rather than
  a one-off workaround (even though the one-off was faster) kept the fix from
  needing to be redone the next time an ops/`.github` file needs to change —
  a repeat of Item #23's exact same gap, previously closed off by coincidence
  (`enforce_admins` flipping) rather than by design.
- **A verification pass that flags its own visual-confirmation gap honestly**
  (no authenticated browser session available) **is more trustworthy than one
  claiming full coverage it can't back up** — same pattern already noted in
  v75 for Item #28, recurring identically for Item #26's §5. Worth treating
  as an expected, standing limitation of Claude Code CLI's environment for any
  future item needing a real signed-in visual check, not a one-off surprise
  each time.

See v71–v75 for the full prior list (fix-at-one-layer-≠-fix-everywhere,
spec-evidence-can-be-wrong, unpushed-commits-are-the-same-failure-mode, a
tracker's "still outstanding" note can itself be stale, etc.) — unchanged, not
restated here.

---

## Tools & resources (unchanged from v75)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps`
  (private)
- **Azure:** Container Apps (`forge-staging`/`forge-production` environments,
  `forge-build-rg`), Container Registry, Key Vault (`forge-build-kv`),
  PostgreSQL Flexible Server (`forge-req2026-03-pg`, stopped this session),
  Azure AD (`FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`,
  tenant `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
  — note (confirmed this session): the App lacks `workflows` permission, so
  any `.github/workflows/*` file change must be pushed via Mike's own
  gh-authenticated credentials first, then opened as a PR via the App
  identity per ADR-0009 (agents open PRs, humans approve/merge). This matches
  why `notify-forge.yml` itself was originally "pushed there directly" per
  earlier CLAUDE.md history.
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`,
  `C:\Users\mikef\Projects\forge-demo-apps`
- **`docs/FORGE-Item26-DeployTriggerGate-Spec.md`** — committed this session
  as historical reference, alongside Items #24/#25/#28's specs.

---

## Standing reminders (unchanged)

- Confirm via GitHub API (not local git, not verbal confirmation) that any
  commit is actually present on `origin/main` before treating work as
  complete or dispatching anything label-driven.
- Do not use organizational skills (`laa-brand`, `laa-security-review`,
  `freshservice-kb-article`) for FORGE project work unless Mike explicitly
  asks for one.
- Stop `forge-req2026-03-pg` at the end of every session that starts it —
  done this session.
- Any future `.github/workflows/*` file change in either repo needs to go
  through the App-permission workaround above — not a one-off, now a standing
  fact about how these agents can (and can't) write to workflow files.
