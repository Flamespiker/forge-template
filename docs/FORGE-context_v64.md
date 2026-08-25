# FORGE Context — v64

**Session date:** 2026-08-21 to 2026-08-24
**Prior doc:** v63
**Prepared by:** Claude.ai, from this session's work plus Claude Code CLI's live execution and verification

---

## Purpose & context

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment. Phase 6 (Repeatability) is complete; the project is now in a maintenance/hardening posture rather than active phase-building. Two apps remain live: REQ-2026-01 and REQ-2026-03. REQ-2026-02's infrastructure was decommissioned in Phase 5 (code retained).

**Two-repo model:**
- `forge-template` (public, `Flamespiker/forge-template`) — orchestration/agent code
- `forge-demo-apps` (private) — target monorepo where generated app code lands

**Firm two-tool convention (unchanged):**
- Claude.ai: strategy, spec authorship, context documents, PR gate comment drafting
- Claude Code CLI: live execution, git operations, CLAUDE.md updates, README.md updates
- Mike shuttles between tools and holds all unilateral architecture/scope decisions

**Context doc convention (unchanged):** Mike uploads the latest `FORGE-context_v[N].md` at the start of each new chat. This session ran long and covered multiple specs in one chat by Mike's explicit override of the usual one-doc-per-chat default — not a new standing convention, just this session's exception.

---

## Current state — Open Items

**10 resolved/closed as of this session:** #2, #3, #4, #5, #13, #14, #16, #17, #18, #19

**10 genuinely still open:**

| # | Item | Nature |
|---|---|---|
| 1 | Deploy Agent has no way to learn an app needs a given secret (wiring mechanism exists; nothing declares which secrets are needed) | Design gap, tribal knowledge |
| 6 | `wait_for_all_threads_idle()` can't distinguish "finished" from "every thread hit a fatal session error" | Known bug, not yet fixed |
| 7 | Archive-prefix mismatch (REQ-2026-02, once, root cause unconfirmed) | Deliberately left alone unless it recurs |
| 8 | Implementation Coordinator sometimes generates unrequested `.github/workflows/*.yml` scope creep | Root cause never diagnosed |
| 9 | Ad hoc `fix/*` branches hit `security-check` and need `--admin` merge (4 occurrences) | Undecided: fix the branch convention or accept as standing procedure |
| 10 | `enforce_admins` on `forge-demo-apps` `main` is `false`, should arguably be `true` again | Mike's call, not yet made |
| 11 | 21 CVEs (not just 8) have no `next` 14.x backport | Accepted risk, not actionable — a decision, not a todo. Count corrected this session (was tracked as 8, actually 21) |
| 12 | Cost log needs REQ-2026-03 figures backfilled | Bookkeeping |
| 15 | Ad hoc PRs need the tracking-issue body line added manually if not opened by a stage agent | Known gap, manual workaround exists |
| 20 | REQ-2026-01's `lib/app-insights.ts:70` — `ITelemetryPlugin` type conflict (duplicate nested `@microsoft/applicationinsights-core-js` resolutions, incompatible `Tags`/`ITelemetryPlugin` shapes between the top-level package and the one nested under `applicationinsights-analytics-js`) — **real, unfixed, currently blocking `next build`.** See "Item #20 — full history" below for why this took two corrections to state accurately. |

Of the open items: **#1, #9, #10 are genuine design/policy decisions waiting on Mike**, not something to unilaterally spec and fix. **#6, #7, #8 are real bugs/gaps nobody's picked up yet** — reasonable next spec-and-fix candidates. **#12, #15 are low-stakes bookkeeping/manual-workaround items.** **#20 needs a real code fix** (dedupe `@microsoft/applicationinsights-core-js` in the dependency tree, or a type-cast workaround — not yet scoped).

A companion planning doc, `FORGE-Open-Items-Backlog-v1.md`, breaks down all ten open items in more detail for picking up next session.

---

## Item #20 — full history (worth preserving verbatim; this took two corrections)

1. **Found during PR #24 verification (this session):** running each app's before/after `next build` (as part of verifying the next.js version bump caused no regression) surfaced that `next build` was failing on **both** REQ-2026-01 and REQ-2026-02, apparently pre-existing and unrelated to the version bump.
2. **First correction:** during Fix 3's implementation (pipeline hardening), re-verification in a real Linux CI container (not Windows) showed REQ-2026-02's failure was a **Windows-only false alarm** — it builds cleanly in the actual CI environment. Only REQ-2026-01's failure is real.
3. **Second correction:** an initial "what's left" summary bucketed Item #20 as resolved, on the reasoning that Fix 3 now catches this class of failure. That was imprecise — Fix 3 makes QA **detect and block** the failure going forward; it does not fix the underlying `lib/app-insights.ts` code. Confirmed directly against the live file on `main` (byte-identical to when first found) — nobody has touched it.
4. **Accurate current state:** REQ-2026-01 genuinely cannot produce a working production build today. Before Fix 3, this was invisible to the pipeline (QA silently passed). After Fix 3, QA correctly catches and blocks it. The bug itself is unchanged and still needs a real fix.

**Why this matters going forward:** since Mike decided this session **not** to decommission REQ-2026-01 (see below), this app stays live and this bug needs a real resolution at some point — it's no longer moot.

---

## This session's work, in order

### 1. Item #17 — `resolve_feature_pr()` ad hoc PR fallback
Spec authored (Claude.ai), reviewed against live code by Claude Code (three minor corrections: wrong `github_helper.py` path, backwards wording on `issue_number` vs `request_id`, missing `per_page=100` pagination insurance — all fixed in the spec before implementation). Implemented, committed, live-verified via a real PR/label cycle. **Closed.**

### 2. Item #18 (new) — `_az_login()` ordering bug
Discovered and fixed during Item #17's implementation session, not separately specced. Verified via direct call-order testing against real staging. **Closed.**

Commit chain for #17/#18: `42ab6ab → a41d304 → a5b2df0 → a5bc499 → 955361f`, pushed to `origin/main`.

### 3. Dependabot triage (Item #19)
Spec authored, executed, report produced (`docs/FORGE-Dependabot-Triage-Report-2026-08-21.md`):
- **101 open alerts total**, all in `forge-demo-apps` (`forge-template` clean).
- **Item #11 corrected:** 63 rows / 21 CVEs have no `next` 14.x backport (not 8 as previously tracked) — accepted risk, decision unchanged, just a scope correction.
- **Real, actionable — 24-row headline finding:** REQ-2026-01 and REQ-2026-02 were pinned to `next@14.2.5`; REQ-2026-03 already runs `14.2.35` in production. Bumping the two older apps to match closed a Critical plus 11 other CVEs at essentially zero risk (proven-safe version, not a new upgrade). Opened as PR #24, verified with real before/after test runs on both apps (zero regression), merged.
- **Dev-only — 9 rows dismissed** (`vite`, `glob`, `esbuild`, `minimatch`; alert #s 44, 49, 50, 51, 76, 77, 82, 94, 95; `dismissed_reason: not_used`). Executed and independently re-verified (including catching that alert #93 was a pre-existing, unrelated dismissal from two days prior — correctly not part of this batch). Open count: 101 → 92 → confirmed.
- **False positives: 0** — expected, since Dependabot uses direct semver matching, not the CPE fuzzy-matching that caused Dependency-Check's false positives.
- **REQ-2026-01's 33 "needs your call" rows resolved:** `az containerapp list` confirmed no `req-2026-01-frontend` Container App exists (only `req-2026-01-document-api` and `req-2026-01-email-worker` are live) — marked dormant/not-urgent. Report file updated to reflect this.
**Closed.**

### 4. REQ-2026-01 decommission — considered, spec drafted, ultimately not executed
Mike initially decided to fully decommission REQ-2026-01 (tear down live Azure infra, retain code — same pattern as REQ-2026-02's Phase 5 precedent). A full spec was drafted (`FORGE-REQ2026-01-Decommission-Spec.md`) with an enumerate-then-confirm-then-delete structure. **Before execution, Mike reversed the decision — REQ-2026-01 stays live.** The spec is shelved, not deleted, in case this comes up again. This reversal is why Item #20's REQ-2026-01 build failure is a live concern rather than moot.

### 5. NavItem `aria-hidden` type fix — merged
An old, unmerged branch (`fix/req-2026-01-navigation-aria-types`, never had a PR) was discovered during branch cleanup. Confirmed as a real, unrelated fix (different bug from Item #20 — this one's in `NavItem`/`lucide-react`, Item #20 is in `lib/app-insights.ts`). Opened as a PR, passed QA/Security, merged.

### 6. Branch cleanup — both repos
`forge-demo-apps`: reduced from 12 branches to `main` + `pipeline-state` (confirmed via architecture doc: `pipeline-state` is permanent, intentionally-unprotected orchestration bookkeeping infrastructure that Requirements/ADO-creation stages commit to on every request — **never delete**). All others confirmed merged or deliberately-closed-without-merging (`feature/DRYRUN-2026-01`, confirmed via Mike's own PR #10 closing comment: a deliberate Step 4.10 pipeline dry-run, findings already captured in CLAUDE.md independent of merge status) before deletion.
`forge-template`: reduced from 2 branches to just `main` (`feature/step-3.10-deploy-agent` confirmed merged, deleted).

### 7. Pipeline hardening — Items #3, #4, #5, all closed with live end-to-end verification
Spec authored covering three independent root causes in `qa_agent.py`/`04-qa.yml`:
- **Fix 1 (commit `3508f55`):** `_parse_jest_json()` no longer silently reports a Jest/Vitest collection failure (0/0/0, e.g. from a broken import) as a clean pass. Verified with real broken-import fixtures on both test runners; confirmed no regression on normal pass/fail/`not_applicable` cases.
- **Fix 2 (commit `524b2d0`):** `qc-retry-limit-reached` now actually blocks further automatic QA runs (previously advisory-only — nothing enforced the 3-attempt ceiling). Verified via scoped mock harness; human-override path (manually removing the label) preserved per Document 4's human-gate principle.
- **Fix 3 (commit `e4be3be`):** QA now runs a real `next build` (frontend) alongside existing tests, before Deploy is ever reached; confirmed `dotnet test` already covers backend build validation (verified twice — once via a syntax-error injection, once via a genuine semantic type-error injection into a `.csproj` project's `Program.cs`, both producing the compiler's own real diagnostic, not inferred from documentation). Real measured build time in CI: ~33s (a much-lower, more accurate figure than an earlier ~417s Windows-local estimate, which was inflated by local filesystem overhead).
- Item #20 correction (commit `152b950`, later corrected again to `f1458b8`) discovered as a byproduct of Fix 3's measurement work — see "Item #20 — full history" above.
- All three fixes given a real, live Stage 4→6 cycle against REQ-2026-03 (PR #26, no-op marker) — **passed cleanly**: 39 backend + 29 frontend tests, clean security scan, Deploy fired automatically and completed, independently verified via `az containerapp show` (not just the PR comment) that both live Container Apps run the new commit's image.
- **New standing fact discovered:** the `qa-approved`+`security-approved` → Deploy trigger has **no interception window**. GitHub's `labeled` webhook fires faster than any human or agent can poll and intervene between both labels landing and `06-deploy.yml` starting. "Pause before Deploy fires for a check-in" is not actually enforceable at that point — the only real pause points are *before* both gate labels are present.
- **Unrelated blocker hit and resolved mid-verification:** `ANTHROPIC_API_KEY` was invalid (confirmed both in CI and locally, not a GitHub-secrets misconfiguration). Mike generated a new key, handed it off via the established file-handoff convention (never pasted in chat), updated locally by Claude Code and on GitHub (`forge-template` repo secret) by Mike directly. Re-dispatch succeeded cleanly afterward.
**All three items closed, both individually and end-to-end.**

---

## Key learnings & principles (new/updated this session)

- **`pipeline-state` branch is load-bearing infrastructure, not a stale branch** — confirmed via architecture doc during this session's branch cleanup. Every request's Requirements/ADO-creation stages commit orchestration state there directly (not through a PR, since `main`'s branch protection would otherwise block it). Never delete.
- **A "closed without merging" PR isn't automatically stale/abandoned work** — confirmed twice this session (NavItem fix branch: real unmerged work, worth landing; DRYRUN-2026-01: deliberately closed, findings already captured elsewhere, safe to delete). Always check the actual PR body/comments before assuming either way.
- **Windows-vs-Linux CI discrepancies are real and have already caused one false diagnosis** — REQ-2026-02's "broken build" only existed on Windows. Any build/test finding surfaced from a local Windows session should be re-verified in the actual Linux CI environment before being recorded as a real bug.
- **Container Apps on consumption plan genuinely cost $0 at zero active replicas** — confirmed live across REQ-2026-01's `document-api`, REQ-2026-03's frontend and backend (all `minReplicas: 0`, empty replica lists). **Worker units with no ingress and no custom scale rule do not auto-scale to zero** — `req-2026-01-email-worker` was found running continuously despite `minReplicas: 0`, because `rules: null` means nothing ever triggers a scale-down. This needs either a manual `--min-replicas 0 --max-replicas 0` toggle or a real Service Bus-queue-depth-based KEDA scale rule (not yet built) to actually idle when unused.
- **The Postgres server (`forge-req2026-03-pg`) remains the one resource requiring manual, recurring shutdown discipline** — doesn't auto-scale like Container Apps; auto-restarts after 7 days of being stopped if untouched.
- **Deploy's `labeled`-trigger has no interception window** — see Fix 3 section above. Relevant any time a "run this live but let me check in before the mutating step" request comes up again.
- **A duplicate/nested dependency version conflict (two resolved copies of the same package at different `node_modules` paths, with incompatible types) is a distinct failure class from a straightforward outdated-version CVE** — Item #20's Application Insights conflict is this; the next.js CVEs were the more familiar kind. Worth not conflating the two when triaging future build/dependency issues.
- **A branch found during cleanup that turns out to contain real, unmerged work should be evaluated on its own merits, independent of any related decommission decision** — the NavItem fix was merged even after REQ-2026-01's decommission was (briefly) decided, since the code stays in the repo either way.

---

## On the horizon

- **Item #20's real fix** — REQ-2026-01's `lib/app-insights.ts` type conflict, now correctly blocking `qa-approved` rather than silently passing. No longer moot since REQ-2026-01 stays live.
- **Items #6, #7, #8** — real bugs/gaps, well-scoped candidates for the next spec-and-fix cycle.
- **Items #1, #9, #10** — design/policy decisions still waiting on Mike.
- **Items #12, #15** — low-stakes bookkeeping/manual-workaround items, pick up opportunistically.
- **Bigger direction question, still open:** production promotion (pushing REQ-2026-03 through the Stage 6 *production* gate for the first time — everything so far has stopped at staging), cloud-portability abstraction (deferred since v61), a third greenfield app, or org-facing onboarding groundwork. Not decided this session; pipeline hardening was chosen as the priority instead.
- See `FORGE-Open-Items-Backlog-v1.md` for a fuller breakdown of all ten open items to plan the next session(s) from.

---

## Tools & resources (unchanged from v63 except where noted)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **Azure:** Container Apps (`forge-staging`, `forge-production` environments in `forge-build-rg`), Azure Container Registry, Azure Database for PostgreSQL Flexible Server (`forge-req2026-03-pg`, Burstable B1ms, Canada Central — **remember to `az postgres flexible-server stop` after each testing session**), Key Vault (`forge-build-kv`), Azure AD (single-tenant app registration `FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **Live Container Apps as of this session's close:** `req-2026-01-document-api`, `req-2026-01-email-worker` (⚠️ running continuously, does not auto-scale to zero — see Key Learnings), `req-2026-03-frontend`, `req-2026-03-on-call-rost-5bb949`
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **`ANTHROPIC_API_KEY` was rotated this session** (previous key invalidated/expired) — updated in both `forge-template`'s GitHub Actions secret and local `.env`
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`, `C:\Users\mikef\Projects\forge-demo-apps`
- **Security scanning:** GitHub Dependabot (default); Semgrep; Gitleaks
- **Anthropic Managed Agents:** Stage 3 only; all other stages use base `anthropic` Python client (Messages API)

---

## Other instructions (unchanged)

- For FORGE project work, do not use organizational skills (`laa-brand`, `laa-security-review`, `freshservice-kb-article`) unless Mike explicitly requests one.
- One context doc per chat is the default; suspendable by explicit request (as this session was).
