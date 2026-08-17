# FORGE Context — v56

## Purpose & context

Mike Faulkner (mfaulkner@legalaid.ab.ca) is building FORGE (Full-SDLC Orchestration with Review Gates for Engineers) for Legal Aid Alberta — an AI-orchestrated software delivery pipeline that automates application development from BA intake through deployment. FORGE uses Claude agents (including Claude Managed Agents for Stage 3), GitHub Actions, Azure DevOps (ADO), and Azure Container Apps. The pipeline operates across two repos: `forge-template` (Flamespiker/forge-template, public — orchestration machinery, agent scripts, no branch protection, direct-to-main commits) and `forge-demo-apps` (Flamespiker/forge-demo-apps, private — target monorepo, branch-protected, feature branches + PRs required, `security-check` status required). ADO org is `dev.azure.com/spike99`, project `FORGE-Build`.

Mike's role is Orchestration Manager. Strict **two-tool convention**: Claude.ai (this chat) handles spec authorship, strategy, planning, document review, and PR gate comment drafting; Claude Code CLI handles all live execution, file writes, git operations, and real infrastructure work. Mike shuttles information between the two tools and makes all unilateral decisions.

Eight-stage pipeline: Intake → Requirements → Design → Implementation (Managed Agents) → QA → Security → Deploy → human gate approvals throughout. A nine-document suite plus supporting files (CLAUDE.md, build plan, cost log, ADRs) defines the system. Key ADRs in `core/decisions/`: ADR-0010 (Managed Agents for Stage 3), ADR-0011 (base Anthropic client for all non-Stage-3 stages).

---

## Current state

FORGE is in **Phase 6 (Repeatability)** — running App 2 (REQ-2026-03, On-Call Roster Tracker) through the full pipeline. This session closed out the vast majority of the run.

**Pipeline progress this session:**
- Stage 0 (Intake) → Stage 1 (Requirements/ADO) → Stage 2 (Design) → Stage 3 (Implementation) all completed and approved.
- Coordinator-role ambiguity (R-005/R-007) resolved via issue-comment clarification during intake, prior to spreadsheet lock: coordinator is a real, enforced app-level flag on the user record — **no Azure AD/IDP integration**, no admin UI to promote/demote (manual/data-seed only). Formalized as R-011 in Design.
- Design Agent hit one transient YAML validation failure (unquoted colon in a generated description string) on first attempt; standalone retry (bypassing the ADO-creation step, since ADO items were already correctly created) succeeded cleanly. Non-repro — treated as a one-off model output fluke, not a prompt-gap bug.
- **Implementation Coordinator billing-exhaustion incident:** first Stage 3 session (`sesn_0135Rbe...`) died mid-Test-Writer when Anthropic credits ran out. Session was `terminated`/archived with `resources: []` — genuinely unrecoverable (`--recover-session` correctly refused with an explicit "not recoverable" error). After topping up credits, a **second, independent** session (`sesn_01BJBnYK...`) had already completed cleanly server-side (all 4 threads idle, `implementation.tar.gz` present) — recovered via the formal `--recover-session` path per the "never re-invoke, always recover a completed session" rule. Produced 88 files (full .NET backend + Next.js frontend), committed to `feature/REQ-2026-03`, PR #20 opened.
- PR #20 went through an extensive CI fix cycle (5 QA attempts, multiple Security re-scans) — see "Key learnings" below for root causes. **PR #20 is approved at both Gate 3 (QA) and Gate 5 (Security) and ready to merge** as of session close — final merge action is Mike's, not yet confirmed done at time of writing.

**App 1 (REQ-2026-02):** Inactive User & License Auditor — Phase 5 fully closed out, resources decommissioned, code retained.

---

## This session's fixes (chronological, each its own commit)

| # | Fix | Repo | Commit | What it addressed |
|---|---|---|---|---|
| 1 | JWT `exp` calculation corrected (`iat + expiry`, not `now + expiry`) | forge-template | `f501146` | GitHub App auth intermittently failing when `iat` skew + expiry exceeded GitHub's 10-min max |
| 2 | `qa_agent.py` detects Vitest vs. Jest before invoking frontend tests | forge-template | `55f9ee9` | Frontend QA crashed (`CACError: Unknown option --ci`) since REQ-2026-03 chose Vitest, not Jest |
| 3 | Backend test suite: shared `WebApplicationFactory` via xUnit collection fixture | forge-demo-apps (`feature/REQ-2026-03`) | `42763d0` | Serilog bootstrap race — parallel test classes racing to freeze one process-wide static logger |
| 4 | `security_agent.py`'s `_run_dependency_check()` captures stdout/stderr on failure | forge-template | `a99471f` | Previously silently discarded the real Dependency-Check error; also fixed a latent `NameError` risk on the failure path |
| 5 | `NVD_API_KEY` GitHub secret set on `forge-template` | (secret, no commit) | — | Was never configured; Mike set it directly via `gh secret set`, verified via masked `***` in a live Actions log |
| 6 | Frontend test import paths corrected (`../msw/...` → `./msw/...`, same for `testUtils`) | forge-demo-apps | `fc647df` | Wrong relative paths broke Vitest collection entirely across all 4 test files |
| 7 | OWASP Dependency-Check version bump v9.2.0 → v12.1.0 | forge-template | `b1419a3` | Old version predates NVD API 2.0; failed even with a valid key |
| 8 | Dependency-Check `--exclude "**/node_modules/**"` | forge-template | (pending confirmation — see Open Items) | General-purpose analyzers were walking tens of thousands of `node_modules` files redundantly; Node Audit Analyzer already covers npm deps via `package-lock.json` directly |
| 9 | `next` bumped 14.2.5 → 14.2.35 | forge-demo-apps | `18ca416` | Patched critical middleware auth-bypass (GHSA-f82v-jwr5-mffw, CVSS 9.1) + 10 other findings; stayed on 14.x line per explicit decision (avoid 15.x App Router/Server Actions breaking changes) |
| 10 | Nested `postcss` forced to 8.5.26 via npm `overrides` | forge-demo-apps | `82090c8` | `next`'s own bundled `postcss@8.4.31` copy carried CVE-2026-45623 (9.1 Critical, arbitrary file read) — top-level devDependency bump didn't touch this nested copy |
| 11 | `tsconfig.json` excludes `vitest.config.ts`/`vitest.setup.ts`/`__tests__` | forge-demo-apps | (pending — verify committed) | `npm run build` failed at type-check: two different major `vite` versions (top-level 7.3.6 vs. vitest's nested 5.4.21) produced incompatible `Plugin` types in `vitest.config.ts`, which was wrongly included in the production type-check |

---

## Key learnings & principles (new this session, in addition to those already established)

- **A "session finished/idle" is not proof of success** — `wait_for_all_threads_idle()` only checks thread status, never inspects `session.error` events or `stop_reason`. A billing-exhaustion failure and genuine completion currently look identical to this check. **Confirmed real bug, not yet fixed** (see Open Items).
- **Archiving a session is irreversible** — `run_implementation_stage()` currently archives unconditionally once idle-check passes, before checking for an output archive. This is what made the first billing-exhaustion session unrecoverable. Fixing the completion-detection gap above would also let this archive decision become conditional (skip archiving on detected error, to preserve resumability).
- **CPE fuzzy-matching produces confident-looking false positives** that require individual, NVD-source verification — not just a first-pass CVSS score. This session found 5 (Azure.Identity vs. its JS SDK; a generic OpenID protocol match; PostgreSQL server vs. the Npgsql .NET driver; two BCL assemblies matched against an Office app and an Android to-do app purely on filename word-collision). Real npm findings (exact `pkg:npm/...` + locked version match) are a fundamentally more reliable signal than fuzzy CPE text matches — verify each on its own terms, don't apply one batch's verdict to another.
- **`package-lock.json`'s own `dev` flag is authoritative for prod/dev classification, but always check for duplicate nested copies at different versions** before concluding a flagged package is dev-only — `next`'s own bundled `postcss` copy was a separate, older, production-path copy independent of the safe top-level devDependency.
- **npm's local package cache can hold a stale dependency-resolution edge** even through `rm -rf node_modules && npm install` — `npm cache clean --force` plus deleting `package-lock.json` was needed before an `overrides` entry took effect end-to-end.
- **A completed Managed Agents session and a terminated one require entirely different recovery paths** — always confirm session status (`GET /sessions/{id}`) and check for `implementation.tar.gz` via `list_session_output_files()` before assuming either recoverability or total loss.
- **`gh run rerun` can silently pin to a stale commit** of a *different* repo than the one you just pushed to — confirm the actual checkout SHA on both repos involved before trusting a rerun's results as testing current code.
- **No pipeline stage before Deploy validates the app actually builds** — QA only runs `vitest`/`dotnet test`; `next build`/`docker build` first happens at Stage 6. A build-breaking bug (like the `vitest.config.ts` type conflict) can sit invisible through Intake→Design→Implementation→QA→Security and only surface at Deploy.

---

## Open items — carried forward to next session

1. **Confirm fix #8 (node_modules exclude) is actually committed and pushed.** It was verified working but there was a mid-session gap where it was believed committed but wasn't — confirm current state via `git log` before assuming done.
2. **Confirm fix #11 (tsconfig exclude) is committed and pushed** to `feature/REQ-2026-03`.
3. **`qa_agent.py`'s `_parse_jest_json()` file-collection blind spot** — a Vitest run where every test file fails to collect (0 passed/0 failed/0 total) currently reports as a clean "✅ Pass." Needs to check Vitest's file-level `success`/`status` fields, not just aggregate test counts. This is a real pipeline-trustworthiness gap: it briefly let PR #20's actually-broken frontend suite report as passing (attempts 2–4) before the real bug (test import paths) was found and fixed.
4. **QA retry limit is not actually enforced** — `_MAX_RETRIES = 3` only selects which label to apply (`qa-loop-back` vs. `qc-retry-limit-reached`); it never blocks, skips, or gates a re-run. The workflow will fire unconditionally forever; a human noticing the label is the only real stop. Separately, the retry counter doesn't distinguish real app-test failures from FORGE-tooling bugs or redundant manual reruns — PR #20 burned 5 "attempts," at least 2 of which were pure infrastructure/tooling noise, not real app-code failures.
5. **Completion-detection gap in `wait_for_all_threads_idle()`** — doesn't distinguish "genuinely finished" from "every thread hit a fatal session-level error and has nothing left to do." Caused the billing-exhaustion incident to go undetected as an error for ~41 minutes. Related: `run_implementation_stage()` archives unconditionally on idle, before checking for output — worth making conditional on confirmed completion, not just idle status, to preserve resumability on genuine transient failures.
6. **8 HIGH-severity `next` CVE findings have no 14.x backport** (fix only exists on 15.x) — accepted, ongoing risk from the deliberate decision to stay on 14.x. Not a gap in any fix landed this session; worth revisiting if/when a 15.x migration is ever considered.
7. **No pipeline stage validates the app actually builds before Stage 6.** Worth considering whether `04-qa.yml` (or a new lightweight stage) should run `npm run build`/`dotnet publish` as a basic buildability gate, rather than leaving first-build-attempt entirely to Deploy.
8. **Dev-only npm CVE findings (esbuild, vite, vitest)** — confirmed `dev: true`, low real-world risk (only matters if a dev/test server is exposed to a network). Accepted as noted in the Gate 5 PR comment rather than formally suppressed. A `forge-template`-level Dependency-Check suppression file (for these recurring dev-tooling findings, and possibly the recurring .NET CPE false positives too) remains a worthwhile future improvement, not done this session.
9. **Cost log** (`docs/FORGE-pipeline-cost-log.md`) needs updating with REQ-2026-03's real figures — Design retry, the billing-exhaustion incident (partial cost, wasted), the full recovered Implementation run, and this session's extensive CI fix cycle.
10. **Confirm PR #20 is actually merged** and `design-approved`/other stale labels are cleared, if not already done by end of session.

---

## Approach & patterns (unchanged, reconfirmed this session)

- Two-tool convention firm; Claude Code CLI prompts drafted in full here for copy-paste.
- Commits: `forge-template` → direct to `main` (confirmed again this session: no branch protection, `enforce_admins` not relevant since there's no protection to bypass). `forge-demo-apps` → feature branches + PRs, branch protection enforced.
- One fix per commit, with commit messages describing actual verified behavior (diffs, real test runs, real re-scans) — never intent or assumption.
- Verify before trusting: live git evidence, actual re-scans, actual session/API status checks — repeatedly the deciding factor this session (npm cache staleness, `gh run rerun` stale-SHA gotcha, session-recovery status, CPE false-positive verification, dev/prod dependency classification).
- Credentials/secrets: never typed through chat or a file Claude can see — Mike runs `gh secret set` directly in his own terminal, verified via masked Actions log output.

---

## Tools & resources (unchanged from v55)

- **Repos**: `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **GitHub App**: `forge-pipeline`, App ID `4388813`
- **Azure**: Container Apps environments `forge-staging` / `forge-production`, resource group `forge-build-rg`; ACR (Basic tier)
- **ADO**: `dev.azure.com/spike99`, project `FORGE-Build`
- **Tools in pipeline**: Gitleaks, OWASP Dependency-Check (now v12.1.0), Semgrep, Vitest/Jest (runner now auto-detected), xUnit, Serilog
- **Local env**: Windows, PowerShell; Git clones at `C:\Users\mikef\projects\forge-template` and `C:\Users\mikef\projects\forge-demo-apps-clone`; WSL/Git Bash also in use — **note:** git-bash's lowercase path mounting is a known source of local-only false-positive errors (confirmed again this session on REQ-2026-03, matching a prior REQ-2026-01 precedent) — does not reproduce on real Linux CI runners.
- **Cost tracking**: `docs/FORGE-pipeline-cost-log.md` — needs REQ-2026-03 figures (open item #9)

---

## Other instructions

- For FORGE project work, do not use organizational skills (laa-brand, laa-security-review, freshservice-kb-article) unless Mike explicitly asks for one.
