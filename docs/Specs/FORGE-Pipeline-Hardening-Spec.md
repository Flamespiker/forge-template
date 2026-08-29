# FORGE — Pipeline Hardening: QA Blind Spot, Retry Ceiling, Pre-Deploy Build Validation: Spec for Claude Code

**Prepared:** 2026-08-20 (Claude.ai)
**For:** Claude Code CLI session against `forge-template` (all three are pipeline/agent bugs, not `forge-demo-apps` application bugs)
**Context:** Three independent, previously-logged Open Items (CLAUDE.md #3, #4, #5), carried forward from the REQ-2026-03 fix cycles. Each has already caused a real, confirmed incident. This is a hardening pass, not new functionality — no new stages, no new labels, no change to the six-gate pipeline shape (Document 4/07: "Locked").

**Standing conventions to follow (per `CLAUDE.md` / context doc):**
- Verify against the live file, not this spec — `grep -n` the actual current `qa_agent.py`, `06-deploy.yml`, and `04-qa.yml` before editing anything. Line numbers/function names below are from CLAUDE.md's own notes and may have drifted (confirmed drift already found once this session in the prior spec — `core/agents/github_helper.py` vs. the real `core/agents/utils/github_helper.py` path).
- Windows environment: `shutil.which()` for subprocess calls, `encoding="utf-8"` on subprocess readers, no bash heredocs.
- Commit each of the three fixes **separately**, verified against actual `git diff HEAD` — these are unrelated root causes in different files and should not land as one commit.
- Smoke-test each fix individually before moving to the next.
- Report any design fork back to Mike rather than resolving silently.
- Do **not** update the context doc (`FORGE-context_v63.md`) from this Claude Code session — that's Claude.ai's job at session close. Do update `CLAUDE.md` with what this session actually did/observed.
- Pipeline stage sequence, count, and human-gate-per-stage are all **Locked** per Document 07 — none of these three fixes may add, remove, reorder, or skip a stage, or bypass a human gate. Fix 3 in particular must land as new validation logic *inside* an existing stage (QA), not a new Stage.

---

## Fix 1: `qa_agent.py`'s Jest/Vitest JSON parser has a file-collection blind spot

**File:** `core/agents/qa_agent.py` — `_parse_jest_json()` (per CLAUDE.md, also used for Vitest's close-enough-to-Jest-schema `--reporter=json` output via `_detect_frontend_test_runner()`).

**Problem, confirmed live (already caused one real incident on REQ-2026-03):** when every test file in a suite fails to *collect* (a config error, a broken import, a type error before any test even runs — as opposed to a test running and asserting falsely), Jest's/Vitest's JSON report reflects that as `0 passed / 0 failed / 0 total`. `_parse_jest_json()` currently has no way to distinguish this from "a suite with genuinely zero tests" and reports it as a clean pass. A real broken REQ-2026-03 frontend suite slipped through as `qa-approved` this way before being caught by chance.

**Important — do not confuse this with the existing, correct `not_applicable` path (Phase 5 pre-flight Fix 3):** `not_applicable` already correctly handles the case where a service genuinely has *no* test script/test project at all (`_frontend_test_script_exists()` / `_resolve_backend_test_dir()`), and that path must be left untouched — a `not_applicable` outcome should keep not counting against the 3-attempt retry budget. This fix is specifically about a suite that **does** have a real test script and **does** attempt to run, but produces 0/0/0 because every file failed to collect — a different case from "no tests exist," and one that should count as a genuine failure, not a pass or a `not_applicable`.

**Fix design:**
1. Read the actual Jest/Vitest JSON report schema being parsed (`view` a real captured report file from a prior run if one still exists on disk, or generate one fresh against a trivial broken fixture) to confirm which field(s) distinguish "0 tests because collection failed" from "0 tests because none exist." Jest's own JSON reporter includes a top-level `numFailedTestSuites`/`testResults[].message` (or similar — confirm exact field names live, don't assume from memory) that reports collection-level failures separately from per-test results; a suite where `numTotalTests === 0` **and** `numFailedTestSuites > 0` (or the Vitest equivalent) is a collection failure, not a clean suite.
2. When a collection failure is detected, `_parse_jest_json()` should report it as a genuine failure (High severity — this is a build/collection-level break, not an assertion failure, matching `_classify_failure_severity()`'s existing "anything other than an assertion-library marker → High" rule) rather than as a pass. It must **not** be misclassified as `not_applicable` either — that path is reserved for "no test script/project exists at all," a distinctly different and already-correctly-handled case.
3. Ensure the retry-attempt counter and `qa-loop-back`/`qc-retry-limit-reached` labeling treat this the same as any other genuine failure — no special-casing needed here if Fix 1 correctly reports it as `failed` upstream, since the existing labeling logic already keys off pass/fail state.

**Acceptance criteria:**
- Construct a deliberately broken frontend fixture (e.g. a `.test.ts` file with a syntax error or an import of a nonexistent module) and confirm QA now reports it as a **failure**, not a pass, with a clear message indicating collection failure (not just "0 tests ran").
- Re-run against a genuinely test-free service (no `"test"` script at all) and confirm it still correctly reports `not_applicable` — no regression to the Phase 5 fix.
- Re-run against a normal passing suite (e.g. REQ-2026-01's or REQ-2026-02's existing frontend) and confirm no regression — real 0-failure suites with real tests still report a clean pass.
- Re-run against a suite with some genuine test failures (real assertions failing) and confirm severity classification is unaffected — this fix only changes the 0/0/0 collection-failure case, not the normal-failure path.

---

## Fix 2: `_MAX_RETRIES` is advisory-only — no actual gate enforces it

**Files:** `core/agents/qa_agent.py` (label selection) and `.github/workflows/04-qa.yml` (guard clause / dispatch).

**Problem, confirmed live:** `_MAX_RETRIES = 3` currently only determines *which label* gets applied (`qa-loop-back` vs. `qc-retry-limit-reached`) — it doesn't actually stop anything. A passing run always gets `qa-approved` regardless of attempt number, and `04-qa.yml` has no guard clause checking attempt count before allowing another QA run to fire. Nothing currently prevents an infinite fail → fix → fail cycle from running well past the intended 3-attempt budget; the label is descriptive, not load-bearing.

**Fix design:**
1. Confirm the exact current trigger condition for `04-qa.yml` (what label/event causes it to re-fire after a `qa-loop-back`-labeled loop-back — presumably a new commit push to the same feature PR, or a specific label transition; read the live workflow file, don't assume).
2. Add an actual guard: before running the test suites, `qa_agent.py` (or the workflow's guard-clause step, whichever is more consistent with the existing guard-clause pattern used elsewhere — Document 07 confirms "guard clause on every workflow" is already a Locked, established pattern) should check whether `qc-retry-limit-reached` is already applied to the tracking issue. If so, **do not re-run the suites** — post a short comment noting the retry ceiling was already reached and this run was skipped, and exit without consuming a fourth attempt or re-labeling anything.
3. Decide (and state the decision, don't silently pick) whether reaching the ceiling should also remove/block the ability for a subsequent push to silently retry, or whether it's purely advisory-until-a-human-acts (e.g. a human bumping the ceiling manually, or explicitly re-opening the loop). Given Document 4's "human gate at every stage" principle, the safer default is: `qc-retry-limit-reached` blocks further *automatic* QA runs, but a human can still manually re-trigger (e.g. via `workflow_dispatch` or by removing the label) — this preserves the human-override principle rather than creating a hard dead end.
4. This does **not** change `_MAX_RETRIES`'s value (3) or the retry-attempt-counting mechanism itself (`1 + count of this agent's own prior comments on the PR`, per ADR-0002) — only adds actual enforcement on top of the existing, correct counting logic.

**Acceptance criteria:**
- Simulate 4 consecutive QA failures on the same PR (or verify via code review + a scoped local test harness if a full live 4-cycle is impractical) — confirm the 4th run is skipped/blocked rather than executing a 4th real test run, and confirm the skip is clearly commented on the PR.
- Confirm a human can still manually re-trigger QA after the ceiling is reached (per the decision in step 3) — this must not become a permanent dead end requiring a code change to recover from.
- Re-run a normal 1-attempt-passes and a normal 2-of-3-attempts-then-passes case — confirm zero behavior change for the common, non-ceiling-hit paths.
- Confirm `qa-approved` is never applied on a run that should have been skipped — the enforcement must happen before any test execution or labeling, not after.

---

## Fix 3: No stage validates a real production build before Stage 6 (Deploy)

**File:** `core/agents/qa_agent.py` (add a build-validation step within Stage 4, since Document 07 locks the stage sequence/count — this must not become a new Stage).

**Problem, confirmed live (already caused two real incidents):** QA currently only runs `dotnet test`/`jest`/`vitest` — none of which perform a real production build. The first time `next build`/`docker build` is actually attempted is inside `deploy_agent.py` at Stage 6, which is the most expensive and most human-gated place to discover a build-breaking issue. Two real issues already slipped past QA and were only caught at Deploy: a `lucide-react`/`aria-hidden` type mismatch (REQ-2026-01) and a `vitest.config.ts` nested-`vite`-types conflict (REQ-2026-03).

**Fix design:**
1. Add a build-validation step to `qa_agent.py`, run alongside (not instead of) the existing test suites — e.g. `next build` for the frontend and `dotnet build` (not `dotnet test`, which already implies a build but may not catch every case `dotnet build` alone would — confirm via a quick live check whether `dotnet test`'s implicit build is actually equivalent, or whether a distinct `dotnet build` step catches anything `dotnet test` doesn't) for the backend, against `services/<request-id>/{backend,frontend}`.
2. Treat a build failure the same way Fix 1 treats a collection failure: High severity, counts as a genuine QA failure, blocks `qa-approved`, subject to the same retry-ceiling enforcement from Fix 2 — do not invent a fourth outcome category beyond pass/fail/`not_applicable`.
3. This is deliberately **not** a full `docker build` — that's a heavier, slower check (needs a working Dockerfile, which for the frontend depends on Deploy Agent's own Dockerfile-generation logic, and for a request with no Dockerfile yet in the repo would need Deploy Agent's template applied first, which is out of order for Stage 4). Scope this fix to the language-level build (`next build`/`dotnet build`) only — that's what actually would have caught both real incidents (a TypeScript/import-resolution failure and a `vitest`/`vite` type-config conflict), without pulling Deploy Agent's Docker-specific logic backward into QA.
4. Confirm build step timing doesn't push QA's total runtime into `_TOOL_TIMEOUT_SECONDS` territory or whatever QA's own timeout ceiling is (check live, don't assume Security's 600s figure applies here) — a `next build`/`dotnet build` is heavier than `jest`/`dotnet test` alone; measure real timing on REQ-2026-03's actual codebase before assuming it's fine.

**Acceptance criteria:**
- **Live test material now available (Open Item #20, found 2026-08-21):** `next build` currently fails on both REQ-2026-01 (TypeScript type conflict) and REQ-2026-02 (React prerender error) — confirmed pre-existing, unrelated to the concurrent next.js version bump (PR #24), same failures reproduced identically before and after that bump. These are live, currently-broken builds, not reconstructed fixtures — use them directly: re-run the new build-validation step against both apps' current `main` and confirm it correctly reports a QA failure for each, with the actual TypeScript/prerender error surfaced in the QA comment.
- Re-run QA against REQ-2026-03's actual historical `vitest.config.ts` conflict (reconstructed minimal repro, since that one has since been fixed) — confirm the same detection.
- Separately from this spec: Item #20's two build failures need their own remediation at some point (tracked, not blocking this hardening work) — Fix 3's job is to make sure a future instance of this class of failure gets caught before Deploy, not to fix these two specific instances.
- Re-run QA against a currently-passing service (REQ-2026-02, or REQ-2026-03 post-fix) — confirm the new build step passes cleanly and adds acceptable runtime (report the actual measured seconds added).
- Confirm the build step's failure output is human-readable in the QA comment — a raw `next build`/`dotnet build` stack trace dumped unformatted into a PR comment is not acceptable; some minimal summarization (even just "first N lines of build output" per the existing deterministic-formatting discipline) is expected.

---

## After all three are done

- Smoke-test each independently, commit separately (three commits, not one) — matches the project's established discipline (Phase 5's three-fix cycle was committed the same way).
- Re-run a full, real Stage 4 → Stage 6 cycle against a currently-working request (REQ-2026-02 or REQ-2026-03) end-to-end after all three land — confirm nothing regresses on the known-good path.
- Update `CLAUDE.md` with what this session actually did/observed for all three fixes. Do **not** update the context doc from this session — that's Claude.ai's job at close.
- Next chat after this one (Claude.ai): fold this session's findings into the context doc, close Open Items #3/#4/#5, and revisit next-phase direction once all three hardening items and the earlier two specs (Item #17, Dependabot triage) have landed.
