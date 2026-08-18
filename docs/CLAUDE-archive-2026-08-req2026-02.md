# CLAUDE.md archive — REQ-2026-02 (Phase 5, App 1) fix cycle

Archived from CLAUDE.md on 2026-08-18 to keep the live file lean. Verbatim historical
narrative covering: Stage 3 completion-detection fix + recovery tool, PR #15's QA
fix/deploy-trigger bug/staging deploy, the R-001 descope, Phase 5 close-out/decommission,
the Deploy Agent cross-service wiring fixes, the request_id/resolve_feature_pr() staleness
fixes, the Security Agent scanner-failure verdict fix, and the doc-cleanup changeset.
Current, still-relevant behavior extracted from this material lives in CLAUDE.md itself.
Nothing here has been edited from the original text.

---

### REQ-2026-02 (Phase 5, App 1) — Stage 3 completion-detection fix and a formal recovery tool (2026-08-11)

Session started as "monitor Phase 5 App 1 (Inactive User & License Auditor)
through the fully automated, label-triggered pipeline." Found on arrival that
Stages 0–2 had already run (issue `forge-template#5`: Intake questions
answered, `requirements.md`/`ado-work-items.json` committed, design PR
[#14](https://github.com/Flamespiker/forge-demo-apps/pull/14) merged,
`design-approved` applied) and Stage 3 had already **failed** — this section
covers diagnosing and fixing that failure, not the Stage 0–2 work itself.

**Root cause, confirmed live, not assumed:** the `03-implementation.yml` run
([31451985838](https://github.com/Flamespiker/forge-template/actions/runs/31451985838))
failed with `Coordinator session ... completed but did not produce
'implementation.tar.gz'`. A read-only poll of the session's own thread
statuses (`GET /sessions/{id}/threads`) showed it was NOT stuck —
`forge-coordinator`/`backend_agent`/`frontend_agent` were idle but
`test_writer_agent` was still genuinely `running`, well past the job's own
failure. The coordinator's top-level session status had gone `idle
(end_turn)` in **under half a second** after the initial message — reflecting
only the coordinator's first turn ending after kicking off delegation, not
real completion of the multi-agent work. Real completion (all four threads
idle, `implementation.tar.gz` produced) took **~37 minutes**
(`2026-08-11T02:19:08Z` → `T02:55:47Z`) — consistent with, not an outlier
against, REQ-2026-01's already-logged 38.5 min (dry run) / 55.2 min (real)
durations in `docs/FORGE-pipeline-cost-log.md`. Phase 5 pre-flight Fix 1's
~246s total wait budget (120s thread pre-check + 6-attempt/~126s archive
retry-backoff) was never going to be enough for a real run, and that was
visible from the cost log alone before Fix 1 shipped — flagged, not
re-litigated.

**Fix 1 (`core/agents/utils/managed_agents_wrapper.py`) — completion
detection and archive-retry are now two separate mechanisms, not one
conflated loop:**
- New `SessionStillRunningError(RuntimeError)` — carries `session_id`,
  `thread_statuses`, and (attached by `run_implementation_stage()`)
  `coordinator_id`/`environment_id`/`subagent_ids`. Raised when threads
  aren't all idle within the completion-wait ceiling. **Not a failure** — the
  session is left alive, not archived, specifically so it can be resumed by
  ID later.
- `_wait_for_subagent_threads_idle()` renamed to public
  `wait_for_all_threads_idle()` — the ONE real completion signal for the
  whole stage. Ceiling widened from 120s to `_COMPLETION_POLL_TIMEOUT`
  (default 5400s/90 min, overridable via
  `FORGE_IMPLEMENTATION_COMPLETION_TIMEOUT`), chosen with ~1.6x headroom over
  the largest real duration logged so far (55.2 min). Poll interval widened
  5s → 15s. Per-tick logging now only fires when thread statuses actually
  change (was logging every tick — noisy over a 90-minute ceiling).
- `_ARCHIVE_RETRY_ATTEMPTS` reduced 6 → 3 (2s/4s/8s, ~14s total) — it no
  longer does the real waiting (that regressed to premature-retry-as-backoff,
  which was the actual bug: a 400 from `archive` while a thread is genuinely
  still running isn't new information every retry). Now purely absorbs the
  separate, genuinely transient idle→running archive-call race from the
  Phase 2.9 build notes, on a session `wait_for_all_threads_idle()` has
  already confirmed idle.
- `archive_session()` no longer catches its own completion-wait step —
  `SessionStillRunningError` propagates untouched; the archive call is never
  reached on a still-running session.
- `run_implementation_stage()` restructured: `poll_until_idle()` (still just
  confirms the coordinator's own turn ended without a `session.error`) →
  `wait_for_all_threads_idle()` (the real gate) → audit trail fetched
  *before* archiving (unconfirmed whether an archived session's threads stay
  queryable — kept the original safer order) → `archive_session()`.
  `SessionStillRunningError` re-raised with the extra IDs attached and
  deliberately NOT archived; any other exception still gets a best-effort
  archive attempt so failures don't leak billed resources.
- New `get_session_resource_ids(session_id)` — derives `coordinator_id`
  (`agent.id`), `environment_id`, and `subagent_ids`
  (`agent.multiagent.agents[].id`) directly from `GET /sessions/{id}`,
  confirmed live to carry all three. Means a recovery tool needs only a
  session ID, not a dig through a GitHub Actions log for the
  `managed_agents_session_start` line. Also surfaces `usage` (token/cost) —
  confirmed live this closes the "not yet confirmed to return it" open item
  from chat 28 (see the pipeline cost log update below).
- `get_thread_statuses()` (was `_get_thread_statuses`) made public for the
  same reason.

**Fix 2 (`.github/workflows/03-implementation.yml`) — job `timeout-minutes`
raised 60 → 120.** Necessary, not optional: Fix 1's new completion-wait
ceiling is 90 minutes, but the GitHub Actions runner would have SIGKILLed the
whole job at the old 60-minute mark before the script's own graceful
still-running handling ever got a chance to run — the exact same
process-killed-out-from-under-a-live-session failure mode as the original
REQ-2026-01/DRYRUN-2026-01 incidents, just moved one layer up. 120 minutes
gives the 90-minute internal ceiling ~30 minutes of buffer for setup and the
commit/PR steps.

**Fix 3 (`core/agents/implementation_coordinator.py`) — formal recovery
tool, replacing the ad hoc uncommitted script pattern used for
DRYRUN-2026-01 and (initially, before being redirected mid-session) for this
same incident:**
- `run_implementation_coordinator()` now catches `SessionStillRunningError`
  distinctly from a real failure: posts a clearly-worded "still running, not
  failed, check back" comment to the tracking issue (session ID + live
  per-thread status, explicit instruction not to re-apply `design-approved`)
  instead of the generic failure comment, then re-raises. `main()` exits
  `75` for this case (vs. `1` for a real failure) — an arbitrary but
  documented convention so tooling can tell the two apart; the issue comment
  is the real human-facing signal.
- New `--recover-session SESSION_ID` CLI mode (`--request-id` still
  required): derives all resource IDs via `get_session_resource_ids()`,
  checks live thread status directly, and returns cleanly with no
  monorepo/GitHub mutation at all if anything is still busy — "not ready
  yet" is a normal, successful outcome here, not an error. If idle, sanity-
  checks the archive (`_sanity_check_extracted_files()` — below) before
  reusing the exact same commit/PR/comment logic the happy path uses
  (factored out to `_commit_and_open_pr()`, so there is exactly one copy of
  that logic, not two), then archives the session itself (left alive
  precisely so this recovery could reach it).
- New `.github/workflows/03b-recover-implementation.yml` —
  `workflow_dispatch` ONLY (session ID / issue number / request ID / dry-run
  as inputs), deliberately not automatic, scheduled, or polling. A human
  deciding "it's been long enough, let's check" is the intended amount of
  automation — auto-recovery would remove the one checkpoint that has
  already caught real issues in manual recoveries (see the two findings
  below).
- New `_sanity_check_extracted_files()`: rejects an archive under
  `_MIN_ARCHIVE_FILES`(3)/`_MIN_ARCHIVE_BYTES`(500), and — for each unit
  (`backend`/`frontend`) that `tasks.md` actually mentions — requires ≥2
  files under `services/<request-id>/<unit>/`. Deliberately does NOT
  hardcode "every request needs both units" (DRYRUN-2026-01 was legitimately
  backend-only); ties the check to what that request's own tasks.md called
  for. Verified against 4 constructed cases (realistic two-unit, legitimate
  backend-only, truncated-missing-frontend, degenerate single-file) — the
  two truncated cases both correctly raised.
- Wired into the happy path too (`run_implementation_coordinator()`), not
  just the recovery path.

**Two real, previously-latent issues the recovery process itself caught —
exactly what the sanity checks/format checks exist for, not hypothetical:**
1. **Cross-repo issue reference format.** `workflow_glue.py`'s
   `resolve_tracking_issue()` greps a PR body for `<source_repo>#N`; a bare
   `#5` (no `owner/` prefix) is what broke QA/Security's dispatch on the
   DRYRUN-2026-01 recovery. Checked before touching anything this time:
   `FORGE_GITHUB_OWNER=Flamespiker` is set, and `_commit_and_open_pr()`
   reuses the same qualified-format logic as the original happy path — PR
   #15's body confirmed to contain `Flamespiker/forge-template#5` before
   relying on it.
2. **Archive rooted at the wrong prefix — OPEN, unconfirmed root cause, guard
   reverted to strict.** REQ-2026-02's archive was tarred as `REQ-2026-02/...`,
   not the `services/REQ-2026-02/...` the coordinator's own system prompt
   asked for — `_extract_archive_to_file_dict()`'s existing prefix guard
   correctly rejected every member on the first dry run rather than silently
   committing to a wrong path. A remap fallback was added same-session to
   unblock the recovery, then **deliberately reverted the same day** once
   reviewed: it was a standing, general loosening of the guard for every
   future run (both the recovery path and the normal happy path), based on
   a single occurrence with no reproducibility test (n=1) and only a
   plausible-but-unverified hypothesis for why it happened (the system
   prompt's packaging command is a path relative to the coordinator's shell
   cwd at the time, which is never explicitly pinned to the sandbox root —
   plausible if the coordinator or a subagent `cd`'d into `services/` at
   some point before packaging, but not confirmed). `_extract_archive_to_file_dict()`
   is back to hard-failing on any prefix mismatch, for both callers.
   **Logged as an open item, not a closed finding — if this recurs, that's
   real evidence to act on with a proper fix, not a reason to bring the
   fallback back on a guess.**

**REQ-2026-02 recovered for real using the new tool** (not a synthetic
test — this was the live incident): dry run first (confirmed 69 files, all
correctly remapped and sanity-checked, back when the now-reverted fallback
was still in place) → real run → committed to `feature/REQ-2026-02` (69
files) → draft **PR [#15](https://github.com/Flamespiker/forge-demo-apps/pull/15)**
opened → comment posted to issue #5 → session + environment + coordinator +
all 3 subagents archived cleanly. QA and Security both fired automatically
via the existing `repository_dispatch` wiring the moment the PR opened (no
special-casing needed for a recovered PR) — **QA came back `qa-loop-back`
(real backend/frontend build/compile errors, attempt 1 of 3, unexamined —
separate app-code work for Mike)**, **Security initially came back
`security-approved`** with 0 Critical / 7 Medium (Semgrep flagging a mutable
GitHub Actions tag reference in the generated `backend-ci.yml`/`frontend-ci.yml`).

**CI workflow scope creep — OPEN, confirmed second occurrence of the same
coordinator behavior, not fixed at the root.** REQ-2026-01 already had this
exact issue (unrequested `services/REQ-2026-01/backend/.github/workflows/ci.yml`,
dead weight since GitHub only discovers workflows at the true repo root,
`git rm`'d before merge). Checked whether REQ-2026-02's two Semgrep-flagged
files were the same pattern: confirmed via `gh api .../pulls/15/files` —
both `services/REQ-2026-02/.github/workflows/{backend-ci.yml,frontend-ci.yml}`
were nested under the service directory, never discoverable by GitHub
Actions, and nothing in the coordinator's or any subagent's system prompt
asks for CI workflow files at all. **Two occurrences now — this is a real
recurring coordinator behavior pattern, not a one-off, though the
underlying cause (why the model keeps generating these unprompted) has
still never been diagnosed, only removed after the fact both times.**
Removed both files from PR #15 (`delete_files()`, new addition to
`github_helper.py` — no prior stage needed to delete a monorepo file
before this) and posted a PR comment making explicit that this is dead-code
cleanup, not a security fix: Security's 7 Medium findings against those two
files are moot as a side effect of the files being gone, not because they
were investigated or remediated in place. Confirmed, not assumed: the
deletion commit fired `notify-forge.yml`'s `synchronize` trigger, both
QA/Security re-ran automatically, and Security came back genuinely clean
(`✅ Clear`, `security-approved` re-applied).

**Side effect worth flagging: the cleanup commit also consumed one of QA's
3 retry attempts.** `qa_agent.py` counts attempts from prior PR comments,
so this synchronize-triggered re-run counted as "attempt 2 of 3" against
the exact same real backend/frontend build error the CI-file deletion had
nothing to do with — Mike now has one fewer real retry attempt on this PR
than if the cleanup had been deferred until after a real fix, or done in a
way that didn't re-trigger QA. Not reverted or worked around this session;
flagging so it's a known cost of the cleanup, not a surprise later.

**Real cost data pulled for REQ-2026-02 and logged in
`docs/FORGE-pipeline-cost-log.md`:** `GET /sessions/{id}`'s own `usage`
object carries `active_seconds` and `list_cost` — confirmed live (closing
the "not yet confirmed" item from chat 28) at 6,684,549 cache-read tokens,
138,996 output tokens, 2,218.4 active seconds, `list_cost.amount: "663"`
(units not cross-checked against the Console, read as ~$6.63).

**Resolved by the end of this session (follow-up to the initial report):**
- `design-approved` cleared from issue #5 (`gh issue edit ... --remove-label`)
  — it was left applied after the manual recovery since the workflow step
  that normally clears it never ran (the automated `03-implementation.yml`
  job had already failed before that point, and the recovery tool doesn't
  touch trigger labels). Confirmed via a follow-up label read: only
  `qa-loop-back`/`security-approved` remain.
- The archive-prefix auto-remap fallback was reverted to strict rejection
  (see above) — this was raised as "loosened general behavior on a guess,"
  Mike's call was to revert, done.
- The four completion-detection/recovery-tool commits, the revert commit,
  and the `delete_files()` commit were all pushed to `main` (see commit list
  below) — not left local-only.

**Still genuinely open, logged as open items rather than closed findings —
neither is fixed at the root:**
- **Archive-prefix deviation:** guard is strict again, but *why* the
  coordinator rooted the archive wrong on REQ-2026-02 is still just a
  hypothesis (system prompt's packaging command is cwd-relative, never
  pinned to the sandbox root) — not confirmed, not reproduced. If it
  recurs, that's the signal to actually investigate, not guess again.
- **CI workflow scope creep:** two occurrences now (REQ-2026-01,
  REQ-2026-02), both manually `git rm`/`delete_files()`'d after the fact.
  The coordinator/subagent system prompts still don't ask for CI files and
  nothing was changed in them this session to stop a third occurrence —
  this is a confirmed recurring pattern with no root-cause fix yet, only a
  cleanup response that's now been applied twice.
- `SessionStillRunningError`'s propagation through a *fresh*
  `run_implementation_stage()` call (as opposed to the recovery path, which
  calls `wait_for_all_threads_idle()`/`archive_session()` directly) was not
  exercised live — reproducing it deliberately would mean spending on a new
  real Stage 3 session just to hit the timing window. Reasoned through, not
  reproduced under load, same honesty standard the original Fix 1 held
  itself to.
- QA's `qa-loop-back` result on PR #15 (real backend/frontend build errors,
  now at attempt 2 of 3 after the CI-file-cleanup commit consumed one
  attempt) is unexamined — separate app-code work for Mike, out of scope
  for this session's own brief.

---

### PR #15 QA fix, deploy-trigger bug, and REQ-2026-02 staging deploy (same day, follow-up)

Mike merged PR #15 after QA/Security passed on attempt 3 of 3, then
reported the Deploy Agent hadn't triggered. Three genuinely separate real
bugs surfaced chasing that down to an actual live staging deploy — none
guessed, all reproduced directly.

**Bug 1 — `06-deploy.yml` never fires off an agent-applied label, only a
human-applied one. Confirmed, not assumed, via real run history.**
`06-deploy.yml` triggers on `issues: types: [labeled]`, gated on both
`qa-approved` and `security-approved` being present. Both are applied by
`qa_agent.py`/`security_agent.py` via `add_label()`, which used
`GITHUB_TOKEN`. GitHub Actions has a documented anti-recursion rule:
actions performed with the default `GITHUB_TOKEN` never trigger a NEW
workflow run (exempting only `workflow_dispatch`/`repository_dispatch`).
Checked `06-deploy.yml`'s full run history: the only successful run ever
was triggered by `qa-approved` being applied by `Flamespiker` (a human,
personal token) on DRYRUN-2026-01 — every agent-applied label, before and
after, produced zero deploy runs. **This silently affected every request
that passes QA/Security cleanly without a human touching a label in
between — not something specific to REQ-2026-02.** Every other stage
transition is either human-applied or uses `repository_dispatch`
(exempt); Stage 6 was the only one relying on an agent-applied label.

Fix: `add_label()` (`core/agents/utils/github_helper.py`) switched to the
GitHub App installation token. Confirmed no knock-on effects first:
`get_installation_token()`'s existing lookup (via `FORGE_TARGET_REPO`)
already resolves to the same installation id (`148876680`) for both
forge-template and forge-demo-apps — no change needed there.
`post_comment`/`get_issue`/`get_issue_comments`/`remove_label` stay on
`GITHUB_TOKEN` since none of them need to trigger a downstream
label-driven workflow. Also corrected a stale docstring on
`post_comment()` claiming the App wasn't installed on forge-template — it
has been since the Phase 4 step 4.8 retrofit. Smoke-tested against the
`forge-smoke-test` label on issue #1 before trusting it live, then used
for real: re-applied `qa-approved` on issue #5 (after first confirming
via a full grep of every workflow that nothing listens for `unlabeled`
events, and that `qa_agent.py`'s retry counter is comment-based, not
label-based, so the toggle was safe) — `06-deploy.yml` fired for real
this time. Committed separately (`9f54135`).

**Bug 2 — frontend `package-lock.json` was generated with the wrong
npm/Node version.** The resulting real deploy run built the backend image
fine, then failed on the frontend's `npm ci` inside the Dockerfile.
First attempts to pull the real error out of the Actions log kept
surfacing only npm's generic `ci` usage/help trailer, not the actual
reason — traced to a genuinely truncated/lost log line, resolved by
reproducing directly: `npm ci` succeeds fine against this repo's
`package.json`/`package-lock.json` pair locally (npm 11.6.2/Node 24.11.1)
but fails inside the actual `node:20-alpine` deploy image (npm 10.8.2)
with `Missing: @emnapi/core@1.11.3` / `Missing: @emnapi/runtime@1.11.3
from lock file` — npm 10 and 11 resolve platform-conditional optional
dependencies differently, and `npm ci` is strict about exact sync.
Root-caused because the Jest rewrite's lockfile had only ever been
regenerated/tested locally, never inside the actual deploy target.

Fix: regenerated `package-lock.json` by running `npm install` *inside* a
real `node:20-alpine` container (not locally), extracted it via `docker
cp`, and verified `npm ci` now succeeds both inside that same image and
locally. Full Jest suite re-confirmed 44/44 passing, `next build`/`next
lint` both clean, against the regenerated lockfile.

**Bug 3 — missing `public/` directory breaks the Dockerfile's final
stage.** Even past Bug 2, `COPY --from=builder /app/public ./public`
failed with `"/app/public": not found` — this app has no static assets
and therefore no `public/` directory at all; Git doesn't track empty
directories, so nothing ever created one. Fixed with
`public/.gitkeep`. Verified the complete multi-stage Dockerfile (`deps`
→ `builder` → `runner`) now builds end-to-end with zero errors.

**Non-bug, worth recording so it doesn't get re-investigated:** partway
through verifying Bug 2's fix, a `next build` run threw `Cannot read
properties of null (reading 'useContext')` across every page including
Next's own internal `/404`/`/500` — looked like a real regression at
first. Root cause: a Windows path-casing artifact specific to this local
machine (the real folder is `C:\Users\mikef\Projects\...`, capital P, but
builds were being invoked via git-bash's lowercase `/c/Users/mikef/projects/...`
mount, so webpack saw two differently-cased copies of the same module and
crashed). Confirmed by building the identical code from an unambiguous
path — clean pass. Cannot occur on the real Linux CI runners; no code
change needed or made for it.

**Also encountered and resolved, infrastructure not code:** Docker
Desktop was found hung (daemon unresponsive to `docker version` even
after 20s+ timeouts, despite all `Docker Desktop`/`com.docker.*`
processes showing `Responding: True` in `Get-Process`) partway through
reproducing Bug 2. Killed all Docker-related processes and relaunched
`Docker Desktop.exe`; daemon came back responsive (server 24.0.7) within
~30s. Not a code issue, just a local-machine note in case it recurs.

**Delivery, since `feature/REQ-2026-02` no longer exists** (PR #15's
branch was deleted on merge, confirmed via a 404 on the branch lookup —
so Bugs 2/3's fixes couldn't just be pushed to the old branch): opened a
new, small, separate PR **[#16](https://github.com/Flamespiker/forge-demo-apps/pull/16)**
off `main` (same "mechanical fix, agent doesn't merge its own PR" pattern
as PRs #7/#8/#11) containing only the lockfile regen and `public/.gitkeep`
— no application/business logic touched. **Left open, unmerged** (per
ADR-0009). Since Deploy Agent's own design already tolerates deploying an
unmerged commit SHA, `deploy_agent.py` was invoked manually against PR
#16's head commit (`77aac8a`) to actually unblock staging now rather than
wait on a merge — same "manual invocation satisfies the requirement"
pattern already used for QA/Security's own real runs earlier in this
project.

**Real (non-dry-run) deploy verified live, both units, both confirmed
actually serving traffic (not just CLI-reported success):**
- `req-2026-02-auditor-api` (backend): `https://req-2026-02-auditor-api.yellowmeadow-894377a9.canadacentral.azurecontainerapps.io/api/health`
  → HTTP 200, `{"status":"healthy"}`.
- `req-2026-02-frontend` (frontend): `https://req-2026-02-frontend.yellowmeadow-894377a9.canadacentral.azurecontainerapps.io/`
  → HTTP 200. **First time this project's frontend deploy path has been
  verified end-to-end** — REQ-2026-01's frontend was parked (unrelated
  app-insights dependency issue) and never actually deployed.
- Deploy comment posted to PR #16. No label applied (Document 6 has no
  deploy-stage label, unchanged from prior deploys).

**Not done this session, flagged rather than resolved:**
- PR #16 is unmerged — Mike's call whether/when to merge it. Since its
  head branch isn't `feature/*` or `design/*`, `notify-forge.yml` won't
  dispatch QA/Security for it, so the `security-check` required status
  check will be permanently unsatisfiable on this PR the same way it was
  for `design/*` PRs before Fix 2 — merging it will need the same kind of
  admin override PR #11 needed (`enforce_admins` is still `false`, so
  that path is open), or a deliberate decision about how to handle
  non-`feature/*`/`design/*` fix PRs generally. Not designed or built.
- The two deploy bugs (lockfile npm-version mismatch, missing `public/`)
  were never caught earlier because this project's frontend Docker deploy
  path had never been exercised end-to-end before now for ANY request —
  REQ-2026-01's frontend was parked. Worth considering whether Deploy
  Agent (or CI generally) should build the frontend Docker image earlier
  in the pipeline (e.g. at PR-open time) so a `npm ci`/lockfile issue
  surfaces before Stage 6, not after everything else has already passed.
  Flagged, not designed.

---

### R-001 descope to a license-status report (REQ-2026-02, follow-up session)

Root cause confirmed live (not guessed): a Dataverse metadata investigation
against `EntityDefinitions(LogicalName='systemuser')/Attributes` found no
field matching login/logon/signin/last-activity anywhere among `systemuser`'s
221 attributes in this environment. R-001's original "inactive user" audit
scope was formally descoped by Mike as a result — `GET /api/users/inactive`
became `GET /api/users/license-status`, a license-status report only (no
login timestamps, no inactivity filter). Backend DTOs/service/repository
renamed to match (`LicensedUserDto`, `LicenseStatusResponseDto`,
`LicenseStatusService`/`ILicenseStatusService`); frontend columns/CSV/copy
updated so the UI doesn't imply data it no longer has;
`AppConstants.INACTIVITY_THRESHOLD_DAYS` removed. `openapi.yaml` and both
READMEs updated to match. Real backend tests 49/49, frontend tests 38/38,
`next build`/`next lint` clean before opening a PR. Where real login-activity
data could come from (Graph/Entra sign-in activity, a custom Dataverse
field, or Dataverse audit history) is an open question, not resolved here —
logged as exactly that, an open question, not a TODO with an assumed answer.

**A genuinely new pipeline bug found and root-caused during this work**
(not present in any prior session's notes): the first attempt used branch
name `feature/REQ-2026-02-license-status-fix`. `04-qa.yml`/`05-security.yml`
derive `request_id="${HEAD_REF#feature/}"` — a bash prefix-strip that
assumes the branch is exactly `feature/<request-id>`, nothing more. Stripping
`feature/` left `REQ-2026-02-license-status-fix`, not `REQ-2026-02`, so both
agents looked for a nonexistent `services/REQ-2026-02-license-status-fix/`.
Security crashed loudly (`FileNotFoundError`); QA got a **silent false
positive** — found nothing at the wrong path, correctly-but-wrongly treated
everything as `not_applicable` (Phase 5 Fix 3's own logic, working exactly
as designed, just fed a wrong path), and applied `qa-approved` on zero real
test coverage. Fixed by renaming the branch to the conforming
`feature/REQ-2026-02` (not by touching pipeline code) — re-run confirmed
real coverage (87/87 tests) and a genuine Security pass. The false
`qa-approved` label from the broken run was removed from tracking issue #5
before re-running. **Not fixed at the root**: `04-qa.yml`/`05-security.yml`'s
`request_id` derivation is still a bare prefix-strip with no validation that
the result matches a real `services/<request_id>/` directory — a
differently-named `feature/*` branch would silently reproduce this exact
QA false-positive again. Flagged, not built.

**A second, separate pipeline gap found while watching Deploy auto-fire**:
when the (corrected) `qa-approved` label landed via the App token, `06-deploy.yml`
fired automatically as designed — but `workflow_glue.py`'s
`resolve_feature_pr()` finds "the feature PR" by reading the *original
Implementation Coordinator's comment* on the tracking issue, which still
pointed at PR #15 (the original Stage 3 implementation PR, merged days
earlier). It has no notion of "the current open feature PR for this
request" — so the automatic deploy tried to rebuild PR #15's old,
pre-descope commit, not the new fix. This is a structural gap for any
follow-up feature PR on a request that's already been through
Implementation once, not specific to this fix. Worked around the same way
PR #16 was handled: `deploy_agent.py` invoked manually against PR #18's real
merge commit (`9e4054c`, then `d8823cf` after PR #16 also merged — see
below). Not fixed at the root — `resolve_feature_pr()`'s comment-anchored
lookup is unchanged.

**PR #16 (frontend deploy fix, open since the prior session) admin-merged
this session, at Mike's explicit request**, once it became the direct
blocker for the above manual deploy: `deploy_agent.py`'s build-then-deploy
loop (`deploy_agent.py:590-626` — builds+pushes **every** unit first, *then*
runs `az containerapp create/update` for every unit in a separate pass) means
a single unit's build failure aborts before ANY unit's Container App gets
touched, even ones that built fine. So PR #18's backend image built and
pushed to ACR cleanly, but the frontend build failed on the exact bug PR #16
fixes, and the whole run aborted before the backend's Container App was
ever updated — the real fix was pushed to the registry but never actually
went live until PR #16 merged and the deploy was re-run. Confirmed before
merging: PR #16 was 3 purely mechanical files (regenerated
`package-lock.json`, `public/.gitkeep`, the previously-only-auto-generated
backend `Dockerfile`), no application logic. `gh pr merge --admin` used
(same as PR #11) since PR #16's branch (`fix/req-2026-02-frontend-deploy`)
hit the identical two-part block PR #18 hit initially: no review
(`reviewDecision: REVIEW_REQUIRED`) plus a `security-check` that can never
populate on a non-`feature/*`/non-`design/*` branch.

**Standing item, explicitly logged per Mike's request rather than fixed —
do not lose this count before it's actually decided:** PR #16 admin-merging
is the **fourth** occurrence of this exact pattern — an ad hoc `fix/*`
branch for a small mechanical fix, hitting the permanently-unsatisfiable
`security-check` (because `notify-forge.yml` only dispatches for
`feature/*`/`design/*` branches) plus no human review, resolved by admin
override each time:
1. PR #7 — `fix/req-2026-01-test-infra`
2. PR #8 — `fix/req-2026-01-navigation-aria-types`
3. PR #11 — `fix/design-pr-security-noop`
4. PR #16 — `fix/req-2026-02-frontend-deploy`

Fix 2 (the `design-pr-security-noop.yml` no-op check) already solved this
exact class of problem for `design/*` branches specifically. It was never
generalized to cover ad hoc `fix/*` branches, and four occurrences in is
long enough that this is a real recurring cost (an admin override every
time), not a one-off. Options for whenever this gets decided: extend the
no-op-check pattern to any branch prefix used for these mechanical fixes,
adopt a fixed naming convention for them that's already covered by an
existing dispatch filter, or accept admin-merge as the standing procedure
and stop treating it as a gap. Not decided here — logged only so the count
is not lost.

**Two more real, previously-undiscovered `deploy_agent.py` bugs found while
verifying the live REQ-2026-02 frontend after this deploy — both patched as
one-off, throwaway fixes on the running Azure resources only, `deploy_agent.py`
itself untouched, so both will reproduce on the next real deploy of any
request's frontend unit:**

1. **`NEXT_PUBLIC_API_BASE_URL` is never passed as a Docker build-arg, for
   any unit, on any request.** The frontend Dockerfile declares `ARG
   NEXT_PUBLIC_API_BASE_URL=""` (empty default); `_docker_build()`
   (`deploy_agent.py:345-352`) runs a bare `docker build -f ... -t ... <context>`
   with no `--build-arg` anywhere in the file (confirmed:
   `grep -n "NEXT_PUBLIC_API_BASE_URL\|build-arg" deploy_agent.py` returns
   nothing). Next.js bakes `NEXT_PUBLIC_*` vars in at build time, so every
   deployed frontend build has always shipped with an empty base URL — the
   client's `fetch()` calls resolve to a same-origin relative path against
   the frontend container itself, which has no such route, so Next.js's own
   404 HTML page comes back instead of JSON. `apiClient.ts`'s JSON-parse
   fallback then surfaces a generic "An unexpected error occurred" — a
   real, silent, 100%-of-the-time failure that nothing in this project's
   prior verification ever caught, because every past frontend check only
   confirmed `/` returns 200, never that the actual data fetch succeeds.
   **Not just a missing line, either**: `run_deploy_agent()` builds+pushes
   *all* units in one loop (`deploy_agent.py:590-594`) before creating/
   updating *any* Container App in a second loop (`:600-626`), so the
   backend's real FQDN doesn't exist yet at the point the frontend image
   would need it as a build-arg on a brand-new deploy. A real fix needs
   either a build-order change (backend first, discover FQDN, then build
   frontend) or a predictable FQDN computed from the environment's fixed
   domain suffix + the unit's deterministic name — plausible (Container
   Apps FQDNs are `<app-name>.<env-suffix>.<region>.azurecontainerapps.io`,
   and the suffix/region are fixed per environment) but unconfirmed, not
   designed.
2. **`FRONTEND_ORIGIN` is never set on any backend Container App either** —
   confirmed via `az containerapp show ... properties.template.containers[0].env`
   on the live `req-2026-02-auditor-api`: no `FRONTEND_ORIGIN` entry at all.
   `Program.cs` defaults it to `http://localhost:3000` when unset, so the
   CORS policy only ever allows `localhost` — a real deployed frontend
   origin gets no `Access-Control-Allow-Origin` header back at all
   (confirmed by curling the backend with `-H "Origin: <real frontend
   URL>"` and finding the header absent). Even with bug 1 fixed, a real
   browser's cross-origin fetch would still be CORS-blocked, surfacing a
   *different* generic error ("Unable to reach the Auditor API — check
   your network connection and try again.", the `NETWORK_ERROR` branch)
   rather than the JSON-parse-fallback one. `deploy_agent.py` never sets
   this env var for any unit on any request either.

**Manual patch applied to unblock REQ-2026-02 specifically** (per Mike's
explicit direction, `deploy_agent.py` deliberately not touched):
`docker build --build-arg NEXT_PUBLIC_API_BASE_URL=<real backend FQDN>` →
new tag `d8823cf...-fix-buildarg` → pushed to ACR → `az containerapp update
--image` on `req-2026-02-frontend`; `az containerapp update --set-env-vars
FRONTEND_ORIGIN=<real frontend FQDN>` on `req-2026-02-auditor-api`. Verified
both empirically (not assumed): the deployed JS bundle now shows the real
backend URL concatenated before `/api/users/license-status`; the backend's
CORS response now echoes the exact frontend origin back in
`Access-Control-Allow-Origin`; **Mike confirmed live in a real browser** —
page loads real data, no error banner. Neither fix touched application
source or `deploy_agent.py` — both are Azure-resource-only patches specific
to this one running app, and will need to be reapplied (or `deploy_agent.py`
fixed at the root) the next time this app is redeployed from scratch, or
for any other request's frontend unit.

**Follow-up the same session: the "unconfirmed" caveat on bugs 1/2's fix
shape is now resolved — confirmed empirically, not assumed.** `az
containerapp env list --resource-group forge-build-rg --query
"[].{name:name, defaultDomain:properties.defaultDomain}"` returns
`defaultDomain` at the **environment** level (`forge-staging` →
`yellowmeadow-894377a9.canadacentral.azurecontainerapps.io`, matching
exactly what both REQ-2026-02 units' real FQDNs have been built from all
along). This means a unit's FQDN (`f"{unit.name}.{env_domain}"`) is fully
predictable **before that unit's Container App exists** — there is no
chicken-and-egg ordering problem after all. Bug 1 (missing
`NEXT_PUBLIC_API_BASE_URL` build-arg) and bug 2 (missing `FRONTEND_ORIGIN`)
both have a concrete, verified fix shape now, not just a flagged gap:

1. **Missing `NEXT_PUBLIC_API_BASE_URL` build-arg** (`_docker_build()`,
   `deploy_agent.py:345-352`) — before building a frontend unit, compute the
   backend unit's expected FQDN via one `az containerapp env show --query
   properties.defaultDomain` call (done once per run) + the backend unit's
   already-deterministic name, pass it via `--build-arg`.
2. **Missing `FRONTEND_ORIGIN`** (`_build_containerapp_command()`,
   `deploy_agent.py:403-438`) — same predictable-FQDN trick in reverse: add
   `--set-env-vars FRONTEND_ORIGIN=https://{frontend_fqdn}` to the backend
   unit's create/update command.
3. **Batched build-then-deploy** (`run_deploy_agent()`,
   `deploy_agent.py:590-626`) — builds+pushes *every* unit before running
   `az containerapp create/update` for *any* unit, so one unit's build
   failure blocks even a successfully-built unit's deploy (this is exactly
   what happened to REQ-2026-02's backend earlier this session). Not
   strictly required to fix 1/2 now that FQDNs are predictable without
   needing creation order, but a separate, real robustness gap — fix shape:
   interleave build+push+deploy per unit in one loop instead of two batched
   passes.
4. **`resolve_feature_pr()` anchored to the original Implementation
   Coordinator comment** (`workflow_glue.py`, used by `06-deploy.yml`) —
   different file/mechanism from 1-3, can't discover a newer follow-up
   feature PR for a request that's already been through Implementation
   once (caused the auto-deploy-on-`qa-approved` trigger to target stale
   PR #15 instead of PR #18 earlier this session). No verified fix shape
   yet — not investigated as deeply as 1-3.

**Explicit decision, Mike's call: not implemented this session.** All four
gaps are logged here as confirmed findings (1-3 with a verified fix shape,
4 without yet) specifically so they're ready to pick up in a dedicated
pre-Phase-6 session, rather than folded into whatever unrelated work
surfaces them next.

---

### Phase 5 close-out and REQ-2026-02 decommission (2026-08-13)

Phase 5 close-out doc written (`FORGE-Phase5-Closeout.md`) from records
already in the context doc — no new screenshots/data pulled first, per
Mike's call. REQ-2026-02's live Azure/D365 resources then decommissioned in
the same session, with two deliberate deviations from the original teardown
plan: the D365 Application User was disabled but not deleted (Dataverse
rejected the delete even post-disable; left as-is — disabled is sufficient
to close the security exposure); the app registration was kept for
potential future reuse, only its client secret deleted.
`req-2026-02-auditor-api`/`req-2026-02-frontend` Container Apps deleted from
`forge-staging`. `dryrun-2026-01-backend`/`dryrun-2026-01-frontend` and PR
#10 were both confirmed already gone/closed from an earlier undocumented
session — crossed off, not re-investigated. ACR images for both apps left
in place (low-priority). See context doc chat 44 entry and
`FORGE_Build_Plan_v9.md` for the checklist-level record (renamed from `v8`
2026-08-13, see the doc-cleanup entry above).

---

### Deploy Agent cross-service wiring fixes (per `docs/FORGE-DeployAgent-CrossService-Wiring-Spec.md`)

Three fixes implemented against `core/agents/deploy_agent.py`, each verified
and committed separately per the spec's own convention. Line numbers below
are post-drift, confirmed against the real file at the time each fix
landed, not the spec's own (stale) estimates.

**Fix 1 — `NEXT_PUBLIC_API_BASE_URL` build-arg.** New `_get_env_default_domain()`
(next to `_get_fqdn()`) runs `az containerapp env show ... --query
properties.defaultDomain`, raising rather than returning empty/None on
failure. `_docker_build()` gained an optional `build_args` dict, appending
`--build-arg KEY=VALUE` pairs. `run_deploy_agent()` computes the backend
"web" unit's FQDN once (from the environment's `defaultDomain` + the unit's
deterministic name — confirmed no chicken-and-egg problem, matching the
spec's own verified premise) and passes it only when building the frontend
unit; a frontend with no "web" backend unit in the request logs a warning
and skips the build-arg rather than guessing. Confirmed live:
`az containerapp env show --resource-group forge-build-rg --name
forge-staging` returned `yellowmeadow-894377a9.canadacentral.azurecontainerapps.io`,
matching the spec's assumption exactly. Verified with a local (no ACR push,
no live Container App touch) build of REQ-2026-02's real frontend via the
actual `_docker_build()` function, both with and without the fix's
`build_args` — grep for the backend FQDN inside `/app/.next` found it in
both the server and client-chunk bundles only in the with-build-arg case
(exit 0 vs. exit 1 on the negative control), confirming the fix's effect
empirically rather than by code inspection alone. Committed `2bd8679`.

**Fix 2 — `FRONTEND_ORIGIN` on the backend Container App.**
`_build_containerapp_command()` gained `extra_env_vars: dict[str, str] |
None`, building one merged `--set-env-vars KEY=VALUE ...` flag (confirmed
first that no other `--set-env-vars` usage existed anywhere in the function
to clobber — there wasn't one). `run_deploy_agent()` reuses Fix 1's already-
cached `env_default_domain` to derive the frontend unit's FQDN too (no
second `az` call), passing it as `FRONTEND_ORIGIN` only to the backend
"web" unit's create/update command. Verified locally (no live `az` calls)
by calling `_build_containerapp_command()` directly for all four
create/update × with/without-`extra_env_vars` combinations — confirmed
exact expected command shape each time. Committed `3acab2c`.

**Fix 3 — interleaved per-unit build+push+deploy.** `run_deploy_agent()`'s
two batched passes (build-all-then-deploy-all) merged into one loop with a
per-unit `try/except` — a failure on one unit's build/push/deploy no longer
blocks a different unit that would otherwise succeed. `DeployResult` gained
an `error: str | None` field (and `action`/`image` defaults, since a unit
that fails during its own docker build never reaches the point of having a
containerapp command built at all). `_build_pr_comment()`'s existing
per-unit table now renders a `❌ **failed** — <first line of error>` status
cell for failed units instead of a staging URL, plus a summary line
("N of M unit(s) failed to deploy") when any exist.

**Design fork surfaced, not resolved silently, per the spec's own
instruction:** the spec's acceptance criteria only required that (a) other
units still succeed and (b) the failure is reported against only the
broken unit — it didn't specify what should happen to the run's own
success/failure signal (CI exit code, tracking-issue comment) on a
*partial* failure. There was no existing partial-failure reporting
precedent anywhere in this agent to "match" (confirmed by reading the
whole file first: before this fix, ANY exception anywhere aborted the
entire function immediately, and the only failure surface was one generic
comment on the FORGE tracking issue — the PR comment was never even
reached on failure). Resolved by: still posting the (partial) PR comment
via the existing `post_pr_comment()` on ANY outcome (all successes now
visible even if a sibling unit failed, which is strictly more information
than before, not less), and — if any unit failed — additionally posting a
second, distinct summary comment to the tracking issue via the existing
`post_comment()`, then raising so the job still exits non-zero. This
preserves the pre-existing "CI reflects real problems" guarantee while
adding the new partial-success visibility Fix 3 asks for. The dry-run path
mirrors this (raises on partial failure too, but posts nothing, per the
existing dry-run convention of posting nothing at all).

**Verified via local simulation, not a live multi-unit deploy** (mocking
every function that would touch Docker/Azure/GitHub, feeding one unit a
forced `_docker_build` failure): confirmed the failing unit's error landed
in `results` without preventing the second unit from reaching a fully-built
`az containerapp create` command (including its correct
`NEXT_PUBLIC_API_BASE_URL` build-arg, itself computed from the backend
unit's *name* rather than its actual success — confirming Fix 1/2's
FQDN-prediction mechanism is independent of unit processing order or
success, exactly as the spec's point 3 asked to confirm explicitly rather
than assume); confirmed the resulting PR-comment markdown correctly showed
one failure row, one internal-no-ingress row, and the "1 of 2 failed"
summary line; confirmed the function raised
`RuntimeError("Deploy Agent dry-run: 1 of 2 unit(s) failed: ...")` as
designed. Not verified: a real multi-unit live deploy with a genuine build
failure — this session did not push to ACR or touch any live Container App
for Fix 3 (per the same "confirm before touching forge-staging" convention
already established for Fix 1).

**Incident during this session's Fix 3 verification, caught and cleaned up
immediately — logged because this project's whole process is built around
catching exactly this failure mode:** the first version of the local
simulation script mocked every higher-level function
(`_docker_build`/`_docker_push`/`_containerapp_exists`/`_get_fqdn`/
`post_pr_comment`/`post_comment`) but never mocked `_run_shell()` itself,
and was run with `dry_run=False`. That combination let a **real**
`az containerapp create` execute against the live `forge-build-rg`/
`forge-staging` environment, using fake image/registry data. Caught
immediately via `az containerapp show --name req-sim-frontend
--resource-group forge-build-rg`, which showed a real Container App
resource with `provisioningState: "Failed"` (image never resolved — no
real container ever ran, no traffic, nothing pulled). Deleted via `az
containerapp delete`, confirmed gone via a follow-up `az containerapp show`
(`ResourceNotFound`) **and** `az containerapp list --resource-group
forge-build-rg` (only the two legitimate REQ-2026-01 apps remained) — not
trusted from the delete command's own exit code alone, per Mike's explicit
instruction. No live impact beyond the stray inert resource itself. Fixed
the simulation script before re-running: `_run_shell` is now hard-mocked to
raise `AssertionError` if ever actually called (a safety net independent of
whether every higher-level function happens to be mocked), and the script
defaults to `dry_run=True` unless deliberately overridden. Re-ran
successfully with zero live calls reached.

**Real end-to-end verification against `forge-staging`, per the spec's own
acceptance criteria — a genuinely live deploy, not a mocked/local test.**
Ran `python -m core.agents.deploy_agent` for real (no `--dry-run`) against
REQ-2026-02's actual code in `forge-demo-apps-clone` (`main` @ `d8823cff`,
confirmed matching `origin/main`), targeting `forge-demo-apps` PR #18 and
FORGE tracking issue #5.

**First attempt surfaced a real bug, exactly because this was the first
genuinely live `create` call any of these three fixes had ever gone
through:** `az containerapp create` takes `--env-vars`; `--set-env-vars`
(what `_build_containerapp_command()` used for both branches) is
`update`-only and errors with "unrecognized arguments" — confirmed via
`az containerapp create --help`/`update --help`. Neither Fix 2's own
verification (checked the Python-level command list only) nor Fix 3's
mocked simulation (deliberately hard-mocks `_run_shell` so nothing real
ever runs) could have caught this — both were scoped that way on purpose,
to avoid touching `forge-staging` before this dedicated step. The backend
create failed at CLI arg-parsing, before reaching Azure — confirmed via
`az containerapp show` (`ResourceNotFound`), so no partial/broken resource
was left behind by the failed attempt itself. Fixed
(`_build_containerapp_command()` now uses `--env-vars` for `create`,
`--set-env-vars` for `update`) and, same commit, widened
`_build_pr_comment()`'s error snippet from the first line only (usually
just `"...failed for unit X:"`, no real detail) to the first three
non-empty lines — the real failure above would otherwise have shown no
useful error text in the PR comment at all. Committed `e0986d0`.

**Re-run after the fix: both units deployed clean.** `provisioningState:
Succeeded` for both `req-2026-02-auditor-api` and `req-2026-02-frontend`,
FQDNs matching the predicted pattern exactly (this run also exercised the
`update` path for the frontend, since its first-attempt `create` had
already succeeded — confirms `--set-env-vars` is correct there, unchanged).

- **Fix 1, confirmed against the live-served bundle, not a local build:**
  `curl`'d the running frontend's actual JS chunk
  (`/_next/static/chunks/app/page-05411a420c1e92a5.js`) and found the real
  backend FQDN baked in.
- **Fix 2, confirmed against the live resource and live HTTP behavior:**
  `az containerapp show ... properties.template.containers[0].env` shows
  `FRONTEND_ORIGIN` set to the real frontend FQDN; `curl -H "Origin:
  <real frontend FQDN>"` against the backend gets back
  `access-control-allow-origin: <that exact origin>`.
- **Fix 3, confirmed in two real scenarios, not one:** the first (failing)
  attempt showed the backend's error isolated from the frontend's success
  in both the PR comment (per-unit table + "1 of 2 failed" summary) and a
  distinct tracking-issue comment, while the frontend still deployed for
  real; the second (clean) attempt shows both units' real staging URLs
  with the failure-summary line correctly absent. `git diff` between the
  Fix 3 commit and the `e0986d0` bug-fix commit confirms the per-unit
  `try/except` loop itself was untouched by the bug fix — only the CLI
  flag and error-snippet formatting changed — so the live partial-failure
  behavior observed on the first attempt is the same loop running on the
  second.

**Non-issue, confirmed via container logs, not assumed:** the real
`/api/users/license-status` endpoint returned HTTP 500
(`System.InvalidOperationException: Missing required configuration:
D365_TENANT_ID`, from `az containerapp logs show`). Expected — REQ-2026-02's
D365/Dataverse connection was deliberately decommissioned in the Phase 5
close-out (App User disabled, client secret deleted), and
`deploy_agent.py` has never wired D365 application config for any
request (out of scope for this agent). Unrelated to Fix 1/2/3.

**Cleanup, per Mike's explicit direction:** both Container Apps were
deleted after verification (`az containerapp delete`, both) to restore the
decommissioned state from the Phase 5 close-out, rather than leaving them
live. Confirmed actually gone via **both** a follow-up `az containerapp
show` (`ResourceNotFound` for each) **and** `az containerapp list
--resource-group forge-build-rg` (only the two legitimate REQ-2026-01
apps remained) — not trusted from the delete commands' exit codes alone.
ACR images pushed during this verification
(`req-2026-02-auditor-api:d8823cff...`, `req-2026-02-frontend:d8823cff...`)
were left in place, consistent with the existing "ACR images left in
place, low-priority" convention from the original Phase 5 decommission.

---

### `request_id` derivation & `resolve_feature_pr()` staleness fixes (per `docs/FORGE-RequestId-FeaturePR-Resolution-Spec.md`)

Two independent structural bugs, confirmed unrelated (different files,
mechanisms, and consumers — see the spec's own investigation section),
fixed per spec. Both pre-flight-verified against live file content before
editing; line numbers in the spec were descriptive, not authoritative, and
matched the live files as found.

**Fix 1 — `request_id` derivation (`04-qa.yml`, `05-security.yml`).** Both
workflows previously derived `request_id` via a bare bash prefix-strip
(`request_id="${HEAD_REF#feature/}"`), with no validation that the result
named a real `services/<request_id>/` directory — confirmed live as the
root cause of the exact silent-false-positive class already seen once (the
REQ-2026-02 `feature/REQ-2026-02-license-status-fix` incident: wrong
`request_id` → both suites `not_applicable` → `qa-approved` applied with
zero real test coverage). Fixed by adding a new "Resolve request id" step
to both workflows, immediately after "Resolve tracking issue number",
calling the already-existing, already-proven `resolve-request-id` glue
subcommand (marker-based, same mechanism every stage from
`01-requirements.yml` onward already trusts) instead of re-parsing
`HEAD_REF`. Both workflows' two remaining `HEAD_REF`-derived
`request_id` usages (frontend dependency install in `04-qa.yml`; the QA/
Security Agent invocation in both files) now read
`${{ steps.request_id.outputs.request_id }}`. `HEAD_REF` itself left in
the env block unchanged — no other consumer, no reason to remove it.
No changes needed to `workflow_glue.py`, `qa_agent.py`, or
`security_agent.py` for this fix — `resolve-request-id` already existed
and already did the right thing.

**Verified live, read-only, no mutation:** ran
`python -m core.agents.workflow_glue resolve-request-id --issue-number 5`
directly against the real tracking issue for REQ-2026-02 — returned
`request_id=REQ-2026-02`, confirming the subcommand this fix now relies on
resolves correctly against real issue history.

**Fix 2 — `resolve_feature_pr()` staleness (`workflow_glue.py`).** The
function previously scanned tracking-issue comments for the *first*
`stage=implementation` marker and returned that PR's number/SHA forever —
stale the moment a follow-up feature PR opened on the same issue (e.g. the
R-001 descope pattern), with no mechanism to detect or prefer a newer one.
`06-deploy.yml` uses this to decide what to actually build and deploy, so
a stale result risks silently deploying a superseded commit.

Fixed by asking GitHub directly for the PR that's actually open right now,
using Stage 3's own deterministic branch-naming convention
(`feature/<request_id>`, confirmed in `implementation_coordinator.py`)
instead of trusting comment history:
- New `list_open_prs_by_head(branch_name)` in `github_helper.py` — lists
  open PRs in `forge-demo-apps` whose head branch matches exactly, via the
  GitHub App installation token (same auth context as `get_pr()`).
- `resolve_feature_pr()` rewritten: resolves `request_id` via the existing
  `resolve_request_id()` (stable for the life of the issue), looks up
  `feature/<request_id>`'s open PRs, and returns the single match. Zero
  matches or more than one both raise `ValueError` loudly — no silent
  fallback to "pick the first one." No signature change; `06-deploy.yml`
  needed no edits at all, since it only ever consumed the function's
  `pr_number`/`head_sha` outputs, not its internals.
- `_IMPLEMENTATION_STAGE_MARKER`/`_PR_URL_RE` removed — confirmed via grep
  first that nothing else in the file referenced either constant, so they
  were genuinely dead code after the rewrite, not just orphaned by it.

**Verified live and via simulation, per the spec's own acceptance
criteria:**
- Real, read-only call against tracking issue #5 (REQ-2026-02):
  `resolve_feature_pr(5)` raised `ValueError` — correct, since both of
  REQ-2026-02's feature PRs (#15, #18) are merged/closed and no
  `feature/REQ-2026-02` PR is currently open. This *is* the real
  historical case the spec asked to check against (an issue whose
  Implementation-stage comment points at a since-superseded PR) — the old
  code would have returned stale PR #15 data forever; the new code
  correctly refuses to guess instead.
- Simulated (mocked `list_open_prs_by_head`/`resolve_request_id`, no live
  API calls) single/zero/multiple-open-PR cases: single → returns
  `(pr_number, head_sha)` correctly; zero and multiple both raise
  `ValueError` with the expected message; confirms all three branches
  independent of live state, since no `feature/*` PR is open anywhere
  right now to exercise the single-match path live.

**Both fixes:** `py_compile` clean on `workflow_glue.py`/`github_helper.py`;
both edited workflow YAML files parse cleanly via `yaml.safe_load`. **Committed
2026-08-13** as two separate commits per the spec's own handoff notes: Fix 1
(`04-qa.yml` + `05-security.yml` together, `5271342`) and Fix 2
(`github_helper.py` + `workflow_glue.py` together, `457f1b9`) — both pushed to
`main`, documented in `7fc46dc`.

---

### Security Agent — scanner-failure verdict fix (per `docs/FORGE-SecurityAgent-ScannerFailureVerdict-Spec.md`)

Root cause (first observed live on `DRYRUN-2026-01`, chat 39, never fixed
until now): `run_security_agent()`'s verdict computation only ever looked
at `all_findings` — a scanner that failed to execute at all (crash,
timeout, missing report; `ScanResult.ran=False`) was computationally
indistinguishable from one that ran clean and found nothing, so
`security-approved` could auto-apply on an incomplete scan.

Fix, exactly per spec, all in `core/agents/security_agent.py`:
- `any_tool_failed = any(not r.ran for r in all_results)`, computed right
  after `all_results` is built.
- `check_conclusion`/`label_to_apply` now gate on `has_critical or
  any_tool_failed` — a tool-run failure blocks merge and withholds the
  label exactly like a Critical finding does, no new label or retry
  mechanism introduced.
- `any_tool_failed` added to `summary_for_model`; `_SYSTEM_PROMPT` gained a
  third case instructing the model to state plainly that the scan is
  **incomplete** (not that vulnerabilities were found) when a scanner
  failed with no Criticals present.
- Check-run title is now a three-way branch: `"Security scan: blocked"` /
  `"Security scan: incomplete — scanner failure"` / `"Security scan:
  passed"`.
- `--dry-run`'s printed "label (not applied)" reason now reflects the real
  cause (Critical findings vs. scanner failure) instead of a hardcoded
  Critical-findings string.

**Verified via unit-level checks against `run_security_agent()`'s
internals** (scanner functions and `invoke_agent()` mocked, `dry_run=True`,
no live GitHub/Anthropic calls) — all four spec cases passed, including
the `--dry-run` printed-reason text for each: baseline clean pass
(`success`/`security-approved`), the fixed case — one tool failed, no
findings elsewhere, the exact `DRYRUN-2026-01` shape (`failure`/`None`,
reason correctly names scanner failure), tool failure plus a genuine
Critical elsewhere (`failure`/`None`, reason correctly still names
Critical findings as the cause), and total scanner collapse
(`failure`/`None`). Live confirmation against a real broken scanner
invocation (the spec's own suggested follow-up) not done this session.

Committed `5492305`. Document 3 §3.5's "open item, not yet fixed in code"
pointer to this spec (added the same day, see the doc-cleanup entry below)
was updated to reflect the fix as closed, in the same doc-cleanup commit.

### Doc-cleanup changeset applied (`docs/FORGE-DocCleanup-Changeset-2026-08-13.md`)

Three pre-Phase-6 doc-drift items, batched per Mike's call, applied
verbatim from the changeset spec (which itself was drafted from the live
`security_agent.py` and known label-ownership discrepancy, not the other
way around):

- **`06_Orchestration_v5.md` → `v6`:** Gate 4/5 narrative corrected — QA
  Agent and Security Agent apply `qa-approved`/`security-approved`
  automatically on a clean pass, the reviewer's job is to review and
  confirm, not to apply the label. Label Reference table rows updated to
  match. The now-redundant footnote describing this as a documented
  human-owner/actual-agent-owner discrepancy was removed — the table
  states the true owner directly now, so there's nothing left to disclaim.
- **`FORGE_Build_Plan_v8.md` → `v9`:** steps 5.7/5.8 reworded to match
  (agent applies the label automatically; reviewer confirms). Added a new
  internal `**v9 update**` log entry at the top of the file, consistent
  with the file's own v6/v7/v8 self-documenting version-log convention.
- **`03_FORGE_Tooling_v7.md` → `v8`:** §3.5 (Security Tooling) rewritten to
  describe the real, live-verified architecture — Security Agent invokes
  Semgrep/Gitleaks/OWASP Dependency-Check directly as CLI subprocesses
  inside one GitHub Actions job and is the sole poster of every PR
  comment/check run/label; no GitHub Actions marketplace step for any of
  the three tools is used anywhere, contrary to what earlier versions of
  this document said. Table's "Who Provisions"/cost columns corrected to
  CLI/binary-install language (pip for Semgrep, standalone binary +
  PATH for Gitleaks, binary + JDK 21 + NVD API key for Dependency-Check).
  Provisioning checklist step 8 reworded to match. The open item pointing
  at the scanner-failure-verdict spec was updated to note the fix as
  closed (commit `5492305`, see above), per the spec's own cross-reference
  instruction.
- Old-version files removed on rename per the project's document-
  supersession convention (Git history is the version record) —
  `06_Orchestration_v5.md`/`FORGE_Build_Plan_v8.md`/`03_FORGE_Tooling_v7.md`
  no longer exist; only the new-version filenames do.

Committed `7d03937`. Both this commit and the security-agent fix commit
(`5492305`) pushed to `main`.

---

