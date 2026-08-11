# FORGE — Phase 5 Pre-Flight Fixes: Spec for Claude Code

**Prepared:** 2026-08-10 (Claude.ai, chat 41)
**For:** Claude Code CLI session against `forge-template` (and one small `forge-demo-apps` change, Fix 2)
**Context:** Phase 5 planning (chat 40) identified three fixes worth making before the real App 1 ("Inactive User & License Auditor") run. Priority order below. Do not start Phase 5's real Stage 3 run until at least Fix 1 is in; Fixes 2 and 3 are cheap and should go in the same session.

**Standing conventions to follow (per `CLAUDE.md` / context doc):**
- Verify against live reality, not this doc — `curl` the actual current file contents from `raw.githubusercontent.com` before editing any of the three. This spec describes the *documented* behavior as of context doc v42; the live file is the source of truth for exact line numbers/current code shape.
- Windows environment: `shutil.which()` for subprocess calls, `encoding="utf-8"` on subprocess readers, no bash heredocs (save scripts as files).
- Commit messages must be verified against actual `git diff HEAD`, not intent.
- Never re-invoke the Managed Agents coordinator if a session is still live — reattach to the existing session ID.
- Report findings and any design forks back to Mike rather than resolving silently, especially anything that touches billing (Managed Agents retry budget) or branch protection.
- Smoke-test each fix individually before moving to the next; don't batch all three into one untested commit.

---

## Fix 1 (highest priority): Managed Agents archive-retry backoff

**File:** `core/agents/utils/managed_agents_wrapper.py`, `archive_session()`

**Problem:** `archive_session()` retries the session-archive call 3 times on a fixed 2s/4s/8s exponential backoff (~14s total) before giving up. This is keyed only off the top-level coordinator session's reported status. Observed failure mode (`DRYRUN-2026-01`, Stage 3): the coordinator reported `idle`/`end_turn` while the Test Writer subagent thread was still legitimately executing underneath. All 3 archive attempts hit "still running" and the workflow failed with zero output files, even though the session reached genuine idle minutes later. Recovery required a hardcoded one-off script (`resume_implementation.py`) reusing the known session ID.

**Root cause:** coordinator-level idle does not imply subagent-level idle. The retry budget is also short relative to how long a subagent can legitimately keep working after the coordinator's own turn ends.

**Fix design:**
1. Before attempting to archive, poll actual subagent thread status rather than trusting only the coordinator's idle signal. The wrapper already has `get_subagent_audit_trail()`, which calls `GET /v1/sessions/{sid}/threads` — this returns one thread per agent (coordinator: `parent_thread_id=null`; subagents: `parent_thread_id` set, `agent.name` identifies them). **Verify the exact per-thread status field this endpoint returns** (not confirmed in current docs) — if it exposes a thread-level running/idle state, use it as the real gate for "safe to archive." If it does not expose a usable status field, fall back to design (2) below.
2. Regardless of (1)'s outcome, widen the retry budget so a slow-but-healthy session doesn't get killed by an arbitrarily short timer: increase from 3 attempts / 2s-4s-8s (~14s) to something meaningfully longer — e.g. 6 attempts with 2s/4s/8s/16s/32s/64s (~126s total) — since Phase 5's real app is expected to be larger/slower than the dry-run that triggered this.
3. Combine both: poll thread status in a loop (short interval, generous total window) as the primary check; treat the exponential-backoff archive-call retry as a secondary safety net in case the archive endpoint itself still transiently rejects even after threads report idle (the known `idle → running` flip described in Doc 6 / `CLAUDE.md`).
4. On exhausting the full retry budget, keep today's behavior (fail the job, leave the session live for manual recovery) — do not silently swallow the failure. Log the actual per-thread statuses observed at each attempt, not just "still running," so a future recovery script doesn't need to reverse-engineer it from Console screenshots.
5. Do not build a general-purpose "resume" mechanism as part of this fix — that's out of scope. This fix is about not needing one in the first place.

**Open design fork — flag to Mike, don't decide silently:** if the threads endpoint's status field turns out to be unreliable or missing, the fallback is "just wait longer," which is a blunt instrument that increases GitHub Actions job runtime (and thus minutes cost) on every single Stage 3 run, not just the rare slow ones. Worth surfacing that tradeoff explicitly before committing to a specific number of attempts.

**Acceptance criteria:**
- Existing smoke tests still pass (`smoke_file_io`, `smoke_claude_agent`, plus whatever Managed Agents smoke test exists).
- Simulate or reproduce a case where the coordinator is idle but a subagent thread is still active (worth checking whether this can be forced deterministically, e.g. by holding a subagent open longer than the coordinator's own turn) — confirm the wrapper waits rather than failing prematurely.
- Confirm a genuinely stuck/failed session (not just slow) still fails cleanly within a bounded time, rather than polling forever.
- No change to the archive *order* (session → environment → coordinator → subagents) — only to when the session-archive step decides it's safe to proceed.

---

## Fix 2: `security-check` permanently unsatisfiable on design-stage PRs

**Files:** `forge-demo-apps/.github/workflows/notify-forge.yml` (primary change), possibly a small new workflow file in the same repo.

**Problem:** `main`'s branch protection on `forge-demo-apps` requires the `security-check` status check on every PR. But `notify-forge.yml` only fires its `feature-pr-opened` `repository_dispatch` for PRs on `feature/*` branches, and `05-security.yml` in `forge-template` only ever runs off that dispatch. Design-stage PRs live on `design/*` branches and never trigger it, so `security-check` sits "Waiting for status to be reported" forever — confirmed live, required an admin branch-protection bypass to merge the `DRYRUN-2026-01` design PR. This will recur on every future design PR.

**Fix design (recommended: option 2 from the two logged in the context doc):**

Add a lightweight no-op check-run workflow rather than migrating `main`'s classic branch protection to GitHub Rulesets. Rulesets would work too (scope `security-check` as required only when the head ref matches `feature/*`), but that's a bigger structural change to branch protection itself for a build-phase project — the no-op workflow is smaller, reversible, and doesn't touch the one piece of branch protection config that's already been verified clean (no `bypass_pull_request_allowances`, `enforce_admins: true`, etc. — see context doc chat 36/37 verification).

1. In `forge-demo-apps`, add a new workflow (e.g. `.github/workflows/design-pr-security-noop.yml`) triggered on `pull_request` (`opened`, `synchronize`) **filtered explicitly to `design/*` branches only** — mirror `notify-forge.yml`'s existing branch-filter guard clause pattern so there's no ambiguity or overlap with the `feature/*` path.
2. On trigger, create a `security-check` check run directly on the PR's head SHA with `conclusion: success`, using the same GitHub App token pattern `notify-forge.yml` already uses (`actions/create-github-app-token@v3`, scoped to `forge-demo-apps` this time since the check run is being created in that repo, not dispatched cross-repo). Reuse the FORGE App's existing Checks: Read & Write permission — no new permission grant needed.
3. Title/summary should say explicitly that this is a design-stage PR and no application code security scan applies (e.g. "Design-stage PR — no application code introduced; security scan not applicable at this stage"). This needs to be honestly distinguishable in the GitHub UI from a real Security Agent pass, so nobody mistakes a design PR's green check for an actual scan result later.
4. **Guard clause is the most important part of this fix** — get the branch-prefix filter exactly right (`design/*` only) so this workflow can never fire on a `feature/*` PR and accidentally short-circuit a real security scan. Consider adding a second explicit check inside the job (not just the trigger filter) that verifies the head ref still starts with `design/` before creating the check run, in case the filter syntax is ever loosened later.

**Acceptance criteria:**
- Open a test PR on a `design/*` branch in `forge-demo-apps` → confirm `security-check` check run appears with `success` and the design-stage summary text, within a few seconds of PR open.
- Confirm branch protection on `main` no longer requires an admin bypass to merge a design PR.
- Open (or re-verify with) a real `feature/*` PR → confirm `05-security.yml`'s real dispatch chain still fires normally and is completely unaffected by the new workflow.
- Re-run the exact GET on `main`'s branch protection (`required_status_checks.checks`, `enforce_admins`, `allow_force_pushes`/`allow_deletions`) to confirm nothing there changed as a side effect.

---

## Fix 3: QA Agent — "not applicable" outcome for out-of-scope test suites

**File:** `core/agents/qa_agent.py`, `_run_backend_tests()` / `_run_frontend_tests()` (and whatever aggregates their results into the pass/fail verdict and retry counter)

**Problem:** `_run_frontend_tests()` unconditionally runs `npm test -- --ci --json --outputFile=...`, assuming a real Jest setup exists. A service where a given suite was never in scope (e.g. `DRYRUN-2026-01`, backend-only) has no `"test"` script, and gets reported as a hard failure — identical in shape to a genuinely broken suite. This burned the full 3-attempt retry budget on a non-issue and forced a manual-triage override (`qc-retry-limit-reached` manually cleared, `qa-approved` manually applied). The backend path already got a related fix this cycle (`_resolve_backend_test_dir()` globs for the real `*.Tests.csproj` location instead of a hardcoded path) — this fix is about the *scope* question, not the *location* question, and applies to both suites.

**Fix design:**
1. Before invoking `npm test`, check whether `services/<request-id>/frontend/package.json` exists **and** declares a `"test"` script. If either is missing, record that suite's outcome as `not_applicable` rather than attempting to run it (and rather than `failed`).
2. Mirror the same idea on the backend side: if `_resolve_backend_test_dir()`'s glob for `*.Tests.csproj` finds nothing at all under the service root (not just "wrong path," but "no test project exists"), record `not_applicable` rather than falling through to the old hardcoded-path failure behavior.
3. `not_applicable` must be a real third outcome, not a variant of pass or fail:
   - Does not count against the 3-attempt retry budget.
   - Does not file an ADO Bug.
   - Is reported plainly in the PR comment (e.g. "Frontend: not applicable — no test suite in scope for this service") so a reviewer can see it was a deliberate scope decision, not a silently skipped check.
4. Verdict/labeling logic: `qa-approved` should apply when every *applicable* suite passes, regardless of how many suites were `not_applicable`. `qa-loop-back` / `qc-retry-limit-reached` should only ever be driven by suites that actually ran and actually failed.
5. **Scope this fix to inference from what's on disk** (missing `package.json`/`"test"` script, missing `*.Tests.csproj`) rather than building the more thorough version (an explicit in-scope/out-of-scope declaration sourced from `design.md` or a manifest field) — that's logged as a real future enhancement in the context doc's Open Questions, but it requires a Design Agent change too and is out of scope for a pre-flight fix. Leave a short comment in the code pointing at that future path so it isn't lost.

**Acceptance criteria:**
- Run QA against a service shaped like `DRYRUN-2026-01` (backend tests only, no frontend `"test"` script) → frontend suite reports `not_applicable`, backend suite runs and reports real pass/fail, overall verdict driven only by backend, `qa-approved` applies if backend passes.
- Run QA against a service with both suites present and passing (e.g. re-verify against `REQ-2026-01`'s structure) → confirm no regression, both suites still run and report normally.
- Confirm the retry-attempt counter (`1 + count of prior QA comments on the PR`) doesn't get consumed by a `not_applicable` outcome — a run that's `not_applicable` + `pass` should count as attempt 1 passing, not attempt 1 of 3 against a phantom failure.
- Re-check whether this also resolves (or at least doesn't worsen) the still-unconfirmed `REQ-2026-01` "QA backend TRX report failure" — logged as a separate, not-yet-verified item; don't assume this fix closes it without checking.

---

## After all three are done

- Smoke-test each independently, then commit separately (not one combined commit) so the history stays legible — matches how the backend-test-directory fix was done this cycle (`e2a123eb...` was its own commit).
- Update `CLAUDE.md` with what this session actually did/observed, scoped narrowly per the existing convention (the Claude.ai side owns the context-doc write-back separately).
- Do **not** update `FORGE-context_v42.md` from this Claude Code session — that's the Claude.ai chat's job at the close of this mini-cycle, per the standing two-tool convention.
- Next chat after this one (per the Phase 5 plan): Claude.ai, fresh chat, draft the App 1 intake spreadsheet content for the Inactive User & License Auditor.
