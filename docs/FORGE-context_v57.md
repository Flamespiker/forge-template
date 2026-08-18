# FORGE Context — v57

## Purpose & context

Mike Faulkner (mfaulkner@legalaid.ab.ca) is building FORGE (Full-SDLC Orchestration with Review Gates for Engineers) for Legal Aid Alberta — an AI-orchestrated software delivery pipeline that automates application development from BA intake through deployment. FORGE uses Claude agents (including Claude Managed Agents for Stage 3), GitHub Actions, Azure DevOps (ADO), and Azure Container Apps. The pipeline operates across two repos: `forge-template` (Flamespiker/forge-template, public — orchestration machinery, agent scripts, no branch protection, direct-to-main commits) and `forge-demo-apps` (Flamespiker/forge-demo-apps, private — target monorepo, branch-protected, feature branches + PRs required, `security-check` status required). ADO org is `dev.azure.com/spike99`, project `FORGE-Build`.

Mike's role is Orchestration Manager. Strict **two-tool convention**: Claude.ai (this chat) handles spec authorship, strategy, planning, document review, and PR gate comment drafting; Claude Code CLI handles all live execution, file writes, git operations, and real infrastructure work. Mike shuttles information between the two tools and makes all unilateral decisions.

Eight-stage pipeline: Intake → Requirements → Design → Implementation (Managed Agents) → QA → Security → Deploy → human gate approvals throughout. A nine-document suite plus supporting files (CLAUDE.md, build plan, cost log, ADRs) defines the system. Key ADRs in `core/decisions/`: ADR-0010 (Managed Agents for Stage 3), ADR-0011 (base Anthropic client for all non-Stage-3 stages).

---

## Current state

FORGE is in **Phase 6 (Repeatability)** — running App 2 (REQ-2026-03, On-Call Roster Tracker) through the full pipeline.

**Prior session (through v56):** Stages 0–5 (Intake through Security) completed and approved. PR #20 approved at Gate 3 (QA) and Gate 5 (Security).

**This session:**
- **PR #20 confirmed merged** into `forge-demo-apps` `main` (`e26363f8beb25a4521fd8a78888a688f31ef689f`) — closes v56's open item #10. Combined with CLAUDE.md's later record, v56's open items #1 (`node_modules` exclude, commit `fd4a0b7`) and #2 (`tsconfig` exclude, commit `6639e09`) are also confirmed done — the context doc had simply lagged CLAUDE.md (a recurring document-drift pattern, not a real gap).
- **Stage 6 (Deploy) run against REQ-2026-03**, real (non-dry-run) invocation of `deploy_agent.py` against the merged commit:
  - **First attempt: 0 of 2 units deployed.** Two independent, confirmed root-cause bugs (backend Docker-tag slugification; frontend missing `public/` dir), plus one cosmetic bug (failure-comment wording). Spec drafted (`docs/FORGE-DeployAgent-UnitNaming-PublicDir-FailureComment-Spec.md`) covering four fixes.
  - **Two design forks surfaced mid-implementation and resolved by Mike** (not guessed at) — see below.
  - **Final re-run after all four fixes: 1 of 2 units deployed for real.** Frontend live (`req-2026-03-frontend.yellowmeadow-894377a9.canadacentral.azurecontainerapps.io`, confirmed real HTTP 307, ingress/TLS genuinely live). Backend still fails — expected, per an accepted design decision (see below), not a bug.
  - **A third occurrence of the "Deploy Agent has no app-secrets wiring" gap** found while verifying the live frontend (NextAuth's `NEXTAUTH_SECRET`, missing → `NO_SECRET` error, app redirects to its own auth-error page). Flagged, not fixed.
  - **The requested write-path (claim/release) end-to-end verification could not be performed** — no live backend to call, and the frontend can't render past its own auth-configuration error.

**REQ-2026-03 pipeline run is not yet complete.** Backend unit blocked on a naming decision; write-path verification still outstanding.

**App 1 (REQ-2026-02):** Inactive User & License Auditor — Phase 5 fully closed out, resources decommissioned, code retained.

---

## This session's fixes (chronological, each its own commit)

| # | Fix | Repo | Commit | What it addressed |
|---|---|---|---|---|
| 1 | `_slugify()` rewritten + new `_validate_unit_name()` | forge-template | `8bbd65f` | Any non-alphanumeric run now treated as a word separator (not just PascalCase boundaries), fixing the `.`-adjacent-`-` invalid Docker tag bug (`OnCallRosterTracker.Api` → previously `...tracker.-api`, now `on-call-roster-tracker-api`). New validator checks the full name against Docker tag grammar + Azure Container Apps naming rules (confirmed live via `az containerapp create --help`) and raises a clear, named `ValueError` instead of letting an invalid name reach `docker build`/`az containerapp create`. No regression: `DocumentApi`/`EmailWorker`/`AuditorApi` (REQ-2026-01/02, already live) produce identical names to before. |
| 2 | `_ensure_frontend_public_dir()` | forge-template | `9c732a6` | Creates an empty `services/<request-id>/frontend/public/` directory pre-build if missing — fixes the `COPY --from=builder /app/public ./public` failure regardless of whether the Dockerfile was Deploy-Agent-generated or (as in this case) already committed by the Frontend subagent. Second confirmed occurrence of the exact REQ-2026-02 bug. |
| 3 | Backend unit-name validated before frontend build-arg derivation | forge-template | `6a3d81a` | `run_deploy_agent()` now validates the backend "web" unit's name (via Fix 1) before deriving either FQDN for cross-service wiring. On failure, falls back to the existing "no web backend unit" no-wiring warning instead of baking a broken/unreachable URL into the frontend's `NEXT_PUBLIC_API_BASE_URL`. |
| 4 | Failure-comment wording made conditional on real success count | forge-template | `71a786a` | The tracking-issue partial-failure comment hardcoded "the rest were deployed successfully" regardless of actual count — wrong at 0-of-N. Now conditional; verified correct at both 0-of-2 (this session's real first attempt) and 1-of-2 (this session's real final re-run). |
| — | CLAUDE.md updated with full session detail | forge-template | `b12545d` | Context doc deliberately left untouched per convention (Claude.ai's job at session close — this document). |

---

## Design forks surfaced this session (resolved by Mike, not guessed at)

**Fork #1 — unit name still too long after character fix.** Even after Fix 1's character-level correction, `req-2026-03-on-call-roster-tracker-api` is 38 characters — over Azure Container Apps' 32-char limit. Stripping the generic `.Api` suffix only gets to 34, still over. No truncation/hashing scheme existed or was specified. **Mike's decision: raise a clear `ValueError`, do not truncate.** Consequence, accepted: REQ-2026-03's backend unit genuinely cannot deploy under the current `<request-id>-<slug>` convention until a separate naming decision is made (e.g. renaming the `OnCallRosterTracker` project directory, shortening the request-id prefix, or designing a truncation/hashing scheme). This is now an open item, not a bug to fix.

**Fork #2 — the spec's recommended Dockerfile-template fix wouldn't have worked.** The original spec's Option A (make the Dockerfile-generation template's `COPY` line conditional) assumed Deploy Agent owns the Dockerfile. In reality, REQ-2026-03's frontend Dockerfile was already committed by the Frontend subagent during Implementation, and Deploy Agent's own rule is to never overwrite an existing Dockerfile — so a template-only fix would not have touched either real occurrence of this bug (both REQ-2026-02's and REQ-2026-03's Dockerfiles already existed). **Mike's decision: fix at the filesystem level instead** (Fix 2 above) — works identically regardless of whether the Dockerfile was generated or pre-existing.

---

## Key learnings & principles (new this session, in addition to those already established)

- **A spec's recommended fix location can be wrong even when the bug diagnosis is right** — always confirm which component actually owns the artifact in question (here: who owns the Dockerfile) before implementing the spec's suggested approach, not just its diagnosis.
- **Character-level and length-level naming constraints are separate failure modes** — fixing invalid characters can fully unmask a *second*, independent validity failure (length) that was previously hidden behind the first error. Validate all constraints together, not just the one that happened to surface first.
- **Three independent apps have now hit "Deploy Agent has no app-secrets wiring mechanism"** (EmailWorker's Service Bus connection string, REQ-2026-02's D365 config, now REQ-2026-03's NextAuth `NEXTAUTH_SECRET`) — no longer a one-off, this is a real recurring gap needing a deliberate design (Key Vault references vs. Container App secrets from `team/config.yaml` vs. something else).
- **A CLI-tool invocation quirk can produce a bogus pipeline-failure comment** — passing a Windows backslash path unquoted through a POSIX-shell bash tool ate the backslashes and produced a "no deployable units detected" comment on the tracking issue that looked like a real pipeline finding but was purely a local invocation error. Worth remembering when reading past run history: not every failure comment reflects a real Deploy Agent or app bug.

---

## Open items — carried forward to next session

1. **REQ-2026-03's backend unit name doesn't fit `<request-id>-<slug>` under Azure's 32-char limit** — needs an explicit naming decision (rename the `OnCallRosterTracker` project directory, shorten the request-id prefix, or design a truncation/hashing scheme) before this unit can ever deploy as-is.
2. **NextAuth's `NEXTAUTH_SECRET` (and any other required auth provider env vars) are never wired by Deploy Agent** — third confirmed occurrence of the broader "no app-secrets wiring mechanism" gap. Worth designing properly now rather than another one-off manual patch.
3. **The real write-path (claim/release) verification for REQ-2026-03 has still never been performed** — blocked by both items above (no live backend, frontend can't render past its own auth-configuration error).
4. **`qa_agent.py`'s `_parse_jest_json()` file-collection blind spot** — a Vitest run where every test file fails to collect (0/0/0) currently reports as a clean "✅ Pass." Real pipeline-trustworthiness gap; briefly let PR #20's broken frontend suite report as passing before the real bug was found.
5. **QA retry limit is not actually enforced** — `_MAX_RETRIES = 3` only selects which label to apply; never blocks, skips, or gates a re-run. Retry counter also doesn't distinguish real app-test failures from FORGE-tooling noise.
6. **Completion-detection gap in `wait_for_all_threads_idle()`** — doesn't distinguish "genuinely finished" from "every thread hit a fatal session-level error." Related: `run_implementation_stage()` archives unconditionally on idle, before checking for output.
7. **8 HIGH-severity `next` CVE findings have no 14.x backport** — accepted, ongoing risk from the deliberate decision to stay on 14.x.
8. **No pipeline stage validates the app actually builds before Stage 6** — QA only runs `vitest`/`dotnet test`; `next build`/`docker build` first happens at Deploy.
9. **Dev-only npm CVE findings (esbuild, vite, vitest)** — confirmed `dev: true`, low real-world risk. A `forge-template`-level Dependency-Check suppression file remains a worthwhile future improvement.
10. **Cost log** (`docs/FORGE-pipeline-cost-log.md`) needs updating with REQ-2026-03's real figures, including this session's Deploy Agent fix cycle.

---

## Approach & patterns (unchanged, reconfirmed this session)

- Two-tool convention firm; Claude Code CLI prompts/specs drafted in full here for copy-paste.
- Commits: `forge-template` → direct to `main` (no branch protection). `forge-demo-apps` → feature branches + PRs, branch protection enforced.
- One fix per commit, with commit messages describing actual verified behavior — never intent or assumption.
- Design forks surfaced explicitly and resolved by Mike before implementation, never guessed at silently — reconfirmed twice this session (unit-name length; Dockerfile-fix location).
- Verify before trusting: live git evidence, real re-scans, real session/API status checks, real HTTP checks against deployed units (not just CLI-reported success).

---

## Tools & resources (unchanged from v56)

- **Repos**: `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **GitHub App**: `forge-pipeline`, App ID `4388813`
- **Azure**: Container Apps environments `forge-staging` / `forge-production`, resource group `forge-build-rg`; ACR (Basic tier). `forge-staging` defaultDomain: `yellowmeadow-894377a9.canadacentral.azurecontainerapps.io`.
- **ADO**: `dev.azure.com/spike99`, project `FORGE-Build`
- **Tools in pipeline**: Gitleaks, OWASP Dependency-Check (v12.1.0), Semgrep, Vitest/Jest (runner auto-detected), xUnit, Serilog
- **Local env**: Windows, PowerShell; Git clones at `C:\Users\mikef\projects\forge-template` and `C:\Users\mikef\projects\forge-demo-apps-clone`; WSL/Git Bash also in use.
- **Cost tracking**: `docs/FORGE-pipeline-cost-log.md` — needs REQ-2026-03 figures (open item #10)

---

## Other instructions

- For FORGE project work, do not use organizational skills (laa-brand, laa-security-review, freshservice-kb-article) unless Mike explicitly asks for one.
