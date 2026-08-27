# FORGE Context — v69

**Session date:** 2026-08-27
**Prior doc:** v68
**Prepared by:** Claude.ai, from this session's spec authorship + Claude Code CLI's live-diagnosis correction and execution (relayed back into this chat)

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

**This session's shape:** Not Item #23 (v68's flagged "actual next step" — still pending, see On the horizon). Mike instead requested a spec for the coupled Item #9/#10 backlog pair (ad hoc fix-PR admin-merge pattern, and the `enforce_admins` policy it was propping open). Spec written, handed to Claude Code CLI, which **correctly falsified Fix 1's premise against live evidence before implementing it** — a real example of the project's "verify against the live file, don't assume" discipline catching a spec-level error, not just a code-level one.

---

## Current state

**Items #9, #10, and #15 are all closed.** Full resolution:

- **Item #9 — closed as a non-bug, not a fix.** `notify-forge.yml`'s `startsWith(head.ref, 'feature/')` filter already dispatches `feature/fix-*` branches correctly; live-confirmed via PR #27 (`feature/fix-appinsights-core-js-dedupe`), which got a real Dependabot-backed `security-check: success` and merged normally, no `--admin`. The spec's own premise — that PRs #28/#29 proved the filter was still broken as of 2026-08-26 — was itself wrong: #28/#29 used `chore/*` branch names, never `feature/fix-*` at all, so they were correctly skipped for an unrelated reason. The 4 originally-cited admin-merges (#7, #8, #11, #16) all predate the 2026-08-13 naming convention. No code changed.
- **Item #15 — closed via documented convention (Option A).** The `Related FORGE tracking issue: owner/repo#N` PR-body-line requirement is now documented as a standing rule alongside the branch-naming convention for any ad hoc fix PR. `resolve_tracking_issue()` in `workflow_glue.py` is untouched — no fallback logic added, by explicit choice over the code-fix alternative (Option B), since building tolerance for a missing tracking issue would have changed what a tracking issue means to the pipeline, not just patched a gap.
- **Item #10 — flipped and verified.** `enforce_admins` on `forge-demo-apps`' `main` branch protection is now `true`, confirmed via a `GET` on the branch-protection endpoint showing only that field changed. Commit `d358a8f` closes it in CLAUDE.md. This restores the originally-intended Step 4.8 setting; the `false` value had no known session responsible for it and was only tolerated as a (turns out, unnecessary) escape hatch while Item #9 looked unresolved.

No throwaway PR was needed for verification — PR #27 already served as live proof for both #9 and #15's underlying mechanics.

**Item #23 (Stage 3 never extended for Enhancement requests) is still open, unchanged from v68.** This session did not touch it. It remains the actual next spec-writing target.

---

## This session's work, in order

### 1. Spec written: `FORGE-Item9-Item15-AdHocFixDispatch-Spec.md`

Mike initially asked for "the spec for #10," which surfaced two live ambiguities, both resolved before writing:
- **Which #10:** backlog Item #10 (`enforce_admins` policy) vs. Item #23 (blocking GitHub tracking issue #10). Mike confirmed backlog Item #10.
- **Item #9/#10 are coupled** (the backlog explicitly says #10 shouldn't flip until #9's admin-merge pattern is resolved one way or another) — Mike chose **Option A: fix #9 properly, then flip #10**, over accepting `--admin` merge as standing procedure.
- **A further design fork inside "fix #9 properly":** no-op bypass (mirror `design-pr-security-noop.yml`) vs. real scan via the already-decided `feature/fix-*` naming convention. Mike chose the real-scan path, which pulled in Item #15 (tracking-issue body line) as a coupled dependency.

Spec written accordingly: Fix 1 (make `notify-forge.yml` actually dispatch `feature/fix-*` — based on the then-unverified assumption from CLAUDE.md that PRs #28/#29 proved this was still broken) + Fix 2 (Item #15, with the Option A/B fork explicitly surfaced rather than picked) + a final gate requiring live end-to-end proof before Item #10's flip, with the flip itself explicitly scoped as a separate, later, Mike-approved action.

### 2. Claude Code CLI falsified Fix 1's premise before writing any code

Per the spec's own "verify against the live file, don't assume" instruction, Claude Code CLI checked `notify-forge.yml`'s actual filter and real PR history instead of proceeding straight to the prescribed fix:
- Filter already matches `feature/fix-*` (subset of `feature/*`).
- PR #27 (correctly-named, post-convention) already got a real dispatch and a real passing `security-check`.
- The 4 historical admin-merges (#7/#8/#11/#16) predate the naming convention — expected behavior at the time, not a bug.
- PRs #28/#29 (the spec's cited "still broken" evidence) used `chore/*` branch names, not `feature/fix-*` — a completely different, unrelated reason for being skipped. The spec's inference from CLAUDE.md's Item #23 note was wrong.

Reported this back before touching any code, correctly declining to implement a fix for a problem that didn't exist.

### 3. Path decided: doc-only close, no throwaway PR

Given Fix 1 was a non-issue and Fix 2 (Item #15) was a documentation convention with an already-live proof point (PR #27) plus existing `design_agent.py`/`implementation_coordinator.py` behavior as the "normal case" evidence, the choice was between doc-only closure vs. doc update + one more throwaway PR purely to re-demonstrate something already demonstrated. **Doc-only was chosen** — a throwaway PR would have spent real CI/token cost to re-prove a fact already proven live, with no new information gained.

### 4. Committed and closed

`c4db40c` — Items #9 and #15 closed in CLAUDE.md, with the three-population evidence breakdown (pre-convention / off-convention / correctly-converged) recorded explicitly so a future session doesn't misread old `--admin` merges as an active bug.
`d358a8f` — Item #10 flipped (`enforce_admins: true`, live-verified via before/after `GET`) and closed in CLAUDE.md.

---

## Key learnings & principles (new/updated this session)

- **A spec's own cited evidence can be wrong — "verify against the live file" applies to the spec text itself, not just the code it describes.** This session's Fix 1 was built on a plausible-looking but false inference (PRs #28/#29 "proving" a dispatch bug still existed); Claude Code CLI's live check caught it before any code was written. Specs are a starting hypothesis, not ground truth, even when they cite specific PR numbers.
- **Branch-naming conventions can silently drift into multiple populations over time** (pre-convention / off-convention / correctly-converged) — treating all historical admin-merges as one undifferentiated pattern would have led to "fixing" something already working. Dating and categorizing the evidence mattered more than counting occurrences.
- **Not every acceptance criterion needs fresh live proof if equivalent live proof already exists.** Spending a throwaway PR to re-verify a fact PR #27 already demonstrated would have been cost without signal — recognizing "we already have this evidence" is itself a form of verification discipline, not a shortcut around it.
- **A settings-only change (branch protection) stays out of the code-commit flow entirely** — Item #10's flip was deliberately sequenced as its own explicit, Mike-approved action via `gh api`/Portal, never bundled into the Item #9/#15 commits, even though all three closed in the same session.

---

## On the horizon

- **Item #23 (Stage 3 never extended for Enhancement requests) — still the actual next spec target, unchanged from v68.** `service_root` resolution, sandbox population with real existing code, PR-body/tracking-issue "Related service" cross-reference line, and the intake-template dropdown safeguard. **Next action: fresh chat, per one-doc-per-chat convention.**
- **CLAUDE.md update still pending from v68** (Mike → Claude Code CLI): document the `user.interrupt` session-stop procedure in the Managed Agents lifecycle section. Not addressed this session — carried forward again.
- **Issue #10 tracking issue** (the GitHub tracking issue, distinct from backlog Item #10) still shows Stage 3 Failed from v68's interrupt — leave as-is until Item #23's fix lands; do not re-apply `design-approved` or retry before then.
- **Carried forward, unchanged:** items #1, #7, #11; Item #22's third test case (scale-rule units, still untestable); Item #12 (cost log backfill).
- **New standing-branch-protection state to remember:** `enforce_admins` is now `true` on `forge-demo-apps`' `main` — any future ad hoc PR that doesn't follow the `feature/fix-*` naming + tracking-issue-line convention will now hard-block with no admin bypass available. This is intentional (closes the loophole), but worth remembering the first time it actually blocks something, so it isn't mistaken for a new bug.

---

## Tools & resources (unchanged from v68)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **Azure:** Container Apps (`forge-staging`, `forge-production` environments in `forge-build-rg`), Azure Container Registry, Azure Database for PostgreSQL Flexible Server (`forge-req2026-03-pg`, Burstable B1ms, Canada Central — stop after each session), Key Vault (`forge-build-kv`), Azure AD (single-tenant app registration `FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **New this session:** `FORGE-Item9-Item15-AdHocFixDispatch-Spec.md`; `enforce_admins: true` now live on `forge-demo-apps`' `main` branch protection
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`, `C:\Users\mikef\Projects\forge-demo-apps`
