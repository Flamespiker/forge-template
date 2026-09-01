# CLAUDE.md archive — REQ-2026-03 (App 2, On-Call Roster Tracker) build & PR #20/Deploy cycle

Archived from CLAUDE.md on 2026-08-18 to keep the live file lean. Verbatim historical
narrative covering: Design retry + Implementation recovery + the PR #20 hardening cycle,
the three PR #20 CI failures and their fixes, the real-CVE-detail pull, the `next`
14.2.5->14.2.35 bump + postcss override, the `--exclude`/`vitest.config.ts` follow-up
fixes, the consolidated open-items list from that arc, and the Stage 6 Deploy 0-of-2
failure with its four `deploy_agent.py` fixes and two design forks. Current, still-
relevant behavior extracted from this material lives in CLAUDE.md itself; open items
carried forward are consolidated in CLAUDE.md's own Open Items section.
Nothing here has been edited from the original text.

---

### REQ-2026-03 (On-Call Roster Tracker) — Design retry, Implementation recovery, and a real PR-hardening cycle (2026-08-15/16/17)

A single long session covering REQ-2026-03 end-to-end from a failed Design
run through a hardened, re-scanned PR #20. Documented here as one section
since each step's fix fed directly into the next verification.

**Design Agent (Stage 2) — transient failure, not a repeatable bug.** The
automated `02-design.yml` run failed with `yaml.safe_load()` rejecting the
model's `openapi_yaml` (an unquoted colon inside a `message:` example value —
`"Only coordinators can create ..."` parsed as a new mapping key). Retried
standalone via `python -m core.agents.design_agent --issue-number 6
--request-id REQ-2026-03` (confirmed this CLI path already exists, same
pattern as `implementation_coordinator.py`) — **succeeded cleanly on the
first retry**, no repeat of the bug. Draft PR
[#19](https://github.com/Flamespiker/forge-demo-apps/pull/19) opened on
`design/REQ-2026-03`. Since it didn't reproduce, no prompt/validation fix was
made — logged as a one-off model fluke, not a confirmed repeatable gap.
Separately confirmed PR #19's `design.md`/`openapi.yaml`/`tasks.md` correctly
say nothing about the `services/<request-id>/` path convention — that's by
design: the path is computed deterministically in
`implementation_coordinator.py` (`service_root = f"services/{request_id}"`)
from the CLI-supplied request-id, not parsed out of Design's own artifacts.

**Real bug found and fixed while retrying Design: `_build_app_jwt()`'s `exp`
claim exceeded GitHub's 10-minute `iat`-to-`exp` window.** `github_helper.py`
computed `exp = now + 600` on top of an `iat` already skewed back 60s for
clock drift, giving a 660s window — GitHub started hard-rejecting this with
`401: "'Expiration time' claim ('exp') is too far in the future"`, silently
blocking every App-token operation project-wide (not specific to Design).
Fixed by computing `exp` from `issued_at` instead of `now`. Verified live via
`GET /app` (200 OK) before retrying anything. **Committed `f501146` on
`main`** (`forge-template` has no branch protection — confirmed via a live
`gh api .../branches/main/protection` 404 — direct-to-`main` commits are the
established, intentional pattern for this repo, unlike `forge-demo-apps`).

**Implementation Coordinator (Stage 3) — a genuine Anthropic billing
exhaustion, confirmed from the real event stream, not inferred from the
stopping point.** The first real run (session `sesn_0135RbeieLaZVoamUVymowtT`)
hit a `session.error` of `type: "billing_error"` ("Your credit balance is too
low...") at the exact moment Test Writer was mid-flight — this event fired at
the **session level**, not just Test Writer's own thread, so the coordinator
never got a further turn to package `implementation.tar.gz`. Confirmed this
was a genuine, previously-undiscovered gap in Fix 1's completion detection
(from the REQ-2026-02 session): `wait_for_all_threads_idle()` only checks
thread `status`, never `session.error` events or non-`end_turn` stop reasons,
so a billing-exhausted session (every thread reports `idle` once nothing can
run) was indistinguishable from a genuinely finished one. Confirmed via a
live `GET /sessions/{id}` that this session was fully `terminated` and
unrecoverable (`resources: []`) — `--recover-session` would correctly refuse
it ("genuinely failed -- not recoverable by this tool"), consistent with its
own existing design. Backend/Frontend had each finished real work before the
billing wall hit (confirmed via each subagent's own thread events: Backend
wrote 29 files, Frontend 38, both ending in a clean `session.thread_status_idle`)
but none of it was ever persisted to `/mnt/session/outputs/`, so it's
unrecoverable — this had to be a fresh run, not a resume.

**Fresh run (session `sesn_01BJBnYKAc6ontnMnUxDFmy8`) succeeded once funds
were restored**, but the local `implementation_coordinator.py` process itself
got killed by the invoking shell's own timeout while `run_implementation_stage()`
was still polling — same class of incident as the REQ-2026-01/DRYRUN-2026-01
precedents. Per the standing rule, did **not** re-invoke the coordinator.
Confirmed live the session had actually finished server-side
(`status: "idle"`, not archived, `implementation.tar.gz` present, 77,439
bytes) and recovered it via `--recover-session` — dry-run first (88 files,
sanity check passed), then real: committed to `feature/REQ-2026-03` (SHA
`763c27c`), draft **PR [#20](https://github.com/Flamespiker/forge-demo-apps/pull/20)**
opened, session/environment/coordinator/3 subagents all archived cleanly.

---

### PR #20 — three CI failures investigated, four real fixes shipped, one Next.js CVE remediation cycle

QA and Security both failed on PR #20's first real run. Investigated each to
a confirmed root cause (not guessed) before fixing anything, per explicit
instruction each time.

**Finding 1 — OWASP Dependency-Check: INCOMPLETE, generic error only.**
`NVD_API_KEY` was never set as a `forge-template` Actions secret (confirmed:
blank in the live run's env dump, despite a working key existing locally).
Separately, `security_agent.py`'s `_run_dependency_check()` never captured
the scanner's `stdout`/`stderr` on a report-missing failure (unlike
`_run_semgrep()`'s equivalent code) — worse than just "no detail": since the
`CompletedProcess` was never assigned to a variable, this branch would have
raised a bare `NameError` instead of a clean `ScanResult`, had `TimeoutExpired`
not already been ruled out first. **Fixed, committed `a99471f` on `main`** —
now captures and surfaces a real tail of tool output on this failure path,
matching the semgrep pattern exactly.

**Finding 2 — Backend "logger is already frozen" (ADO #153–155), fully
root-caused via a real local repro (not just the error text).** All 6
integration test classes used `IClassFixture<IntegrationTestFactory>`
(one `WebApplicationFactory<Program>` host built per class); `Program.cs`
assigns Serilog's process-wide static `Log.Logger` via `CreateBootstrapLogger()`
then freezes it in `UseSerilog()`. xUnit runs different test classes in
parallel by default, so N separate host builds raced to freeze that one
static logger — non-deterministic, confirmed by reproducing locally and
hitting a *different* failing test than CI did. **Fixed in `forge-demo-apps`
on `feature/REQ-2026-03` (commit `42763d0`)**: all 6 classes now share a
single `IntegrationTestFactory` instance via an xUnit collection fixture
(`[CollectionDefinition("Integration Tests")]` + `[Collection(...)]` on each
class) — removes the race by construction (one host, ever) rather than just
serializing it away, and is faster than disabling parallelization would have
been. Verified: no test assertions relied on per-class DB isolation (read all
6 files first); full suite re-run 3× locally, 39/39 passed every time, no
"frozen" errors; suite runtime dropped from ~22s to 2–7s.

**Finding 3 — Frontend suite silently not collecting.** `qa_agent.py`
hardcoded Jest-style flags (`--ci --json --outputFile=...`) regardless of
which runner the target project actually uses; REQ-2026-03's frontend uses
Vitest (`"test": "vitest run"`), and Vitest's CLI hard-rejects the
unrecognized `--ci` flag, crashing before collecting a single test — the
truncated PR comment only showed Vitest's internal call-stack tail, not the
real `CACError: Unknown option '--ci'`. **Fixed, committed `55f9ee9` on
`main`**: new `_detect_frontend_test_runner()` checks for a
`vitest.config.{ts,js,mjs}` file or `"vitest"` in `package.json`'s deps,
defaulting to `jest` (REQ-2026-02's frontend, unaffected); Vitest's own
`--reporter=json` output deliberately mirrors Jest's schema closely enough
that `_parse_jest_json()` handles both without a separate parser. Verified
against both real checkouts (REQ-2026-03 → vitest detected, no more crash;
REQ-2026-01 → jest detected, unchanged).

**Re-running the fixes together surfaced a real GitHub Actions gotcha:**
`gh run rerun` pins to the exact commit SHA that existed at the *original*
dispatch event, not current `main` — confirmed empirically (the checkout log
showed the stale `55f9ee9`, not `a99471f`, on a rerun fired after the
security fix landed). A genuinely fresh `repository_dispatch` (same payload
shape as the Phase 4 verification) was required to actually test all fixes
together, and correctly picked up current `main`.

**That fresh run surfaced two more findings, one old and one brand new:**
- QA came back `qa-approved` (attempt 4/3 — the retry cap only ever gates the
  *failure* label branch, never blocks a pass; confirmed via `04-qa.yml`
  having no attempt-count guard clause at all, and via `qa_agent.py`'s own
  comment: *"Attempt 4 of 3 (retry limit had been reached prior to this run;
  tests ultimately passed...)"*). But frontend showed `0 passed / 0 failed /
  0 total` reported as a **pass** — a real, separate, still-unfixed gap:
  `_parse_jest_json()` only counts individual test pass/fail, never checks
  whether entire test *files* failed to even collect (Vitest's own
  `success: false` / per-file `status: "failed"`). Root cause of the 0/0/0:
  all 4 frontend test files had a pre-existing, unrelated bad-relative-import
  bug (`../msw/server`/`../utils/testUtils` resolving one directory too high
  — the real files live at `__tests__/msw/...` and `__tests__/utils/...`,
  siblings of the test files, not parents). **Fixed, committed `fc647df` on
  `feature/REQ-2026-03`** — corrected to `./msw/...`/`./utils/...` in all 4
  files (deliberately left `__tests__/utils/testUtils.tsx`'s own `../msw/server`
  untouched — it's one directory deeper, so that path was already correct).
  Verified: `npx vitest run` now genuinely collects and passes 28/28 tests.
  The `_parse_jest_json()` file-collection-failure gap itself is still open,
  not fixed.
- Security's Dependency-Check step got a **specific** error this time (fix 1
  above worked as designed) — a real 403/404 from the live NVD API despite a
  correctly-set, correctly-masked `NVD_API_KEY`. Root cause: `05-security.yml`
  pinned Dependency-Check **v9.2.0** (a 2023 release, predating NIST's NVD API
  2.0 rollout). Confirmed by reproducing locally with the same key on a newer
  installed version (worked in ~2 min) vs. the CI failure (8s, too fast to
  have even attempted a real update). **v12.2.2** (that local install)
  turned out not to be an official release at all — confirmed via both the
  GitHub Releases and Tags APIs for `jeremylong/DependencyCheck`; the real
  latest is **v12.1.0**. **Fixed, committed `b1419a3` on `main`** — bumped the
  pin, verified by downloading the real v12.1.0 release zip fresh (same
  `curl`+`unzip` the workflow uses) and running it with the real key against
  `services/REQ-2026-03/backend`: produced a genuine report, `engineVersion:
  12.1.0`, 313 dependencies scanned, 5 with real CVE findings, zero NVD
  errors.

**A second real Dependency-Check gap found and fixed the same session:**
the general-purpose analyzers (Archive, Assembly, Sonatype OSS Index) were
walking every individual file inside `frontend/node_modules` — tens of
thousands of files — on top of the Node Audit Analyzer, which already covers
npm dependencies correctly via `package.json`/`package-lock.json` without
touching installed source. This made a full REQ-2026-03 scan exceed 10
minutes without completing (killed twice). **Note: the actual fix location is
`security_agent.py`, not `05-security.yml`** — that workflow file only
installs the binary; the invocation and its flags are built in Python.
Confirmed first that the Node Audit Analyzer needs no `--enableExperimental`
or other enabling flag (there's a `--disableNodeAudit` flag but no `--enable`
equivalent — it's on by default) and that excluding `node_modules` from the
general scan can't affect it, since it reads `package-lock.json` directly.
Added `"--exclude", "**/node_modules/**"` to the command list. Verified: full
backend+frontend scan dropped from >10 min (unfinished, killed twice) to
~90–170s; zero `node_modules` mentions anywhere in the log; 964 total
dependencies reported, 643 precisely identified via `pkg:npm/...` URLs
(confirming Node Audit Analyzer still ran and still covers the npm tree).

**⚠️ This last fix (`--exclude` in `security_agent.py`) was shown as a diff
with a proposed commit message but was never actually committed** — the
session moved on to pulling CVE detail before an explicit "commit and push"
landed for it. It is currently sitting as an uncommitted local change in the
`forge-template` working tree. Needs an explicit decision (commit it, or
revisit) before the next real Security run — without it, Dependency-Check
will very likely time out again on this project's frontend. **Resolved later
the same session — see the follow-up section below (`fd4a0b7`).**

---

### Pulling real CVE detail — one set of false positives, one set of genuine findings

Asked twice to pull exact JSON fields (CVE ID, CVSS, description, fixed
version) rather than paraphrase — both times surfaced something beyond the
raw data:

**The 5 .NET findings (pre-`--exclude` scan) are very likely false
positives, not real vulnerabilities.** Every one matched a *different*
product than the real NuGet package, all at `confidence: MEDIUM`:
`Azure.Identity.dll` matched the JavaScript SDK's CPE, not `.net`;
`Microsoft.AspNetCore.Authentication.OpenIdConnect.dll` matched the generic
2007 OpenID *protocol* itself, not Microsoft's library;
`Npgsql.EntityFrameworkCore.PostgreSQL.dll` (57 CVEs) matched the
**PostgreSQL server binary**, not the .NET driver — its version string
"8.0.11" coincidentally collides with a real historic server release;
`System.IO.Pipes.AccessControl.dll` matched **Microsoft Office Access**
purely on the word "Access"; `System.Threading.Tasks.dll` matched an
**Android to-do-list app** called Tasks.org purely on the word "Tasks." None
of this was fixed or suppressed — reported as a finding, not resolved.

**The 5 npm findings (post-`--exclude` scan) are genuine** — matched via
precise `pkg:npm/...` URLs from `package-lock.json`, not fuzzy CPE guessing:
`esbuild@0.21.5`, `next@14.2.5`, `postcss@8.4.31`, `vite@5.4.21`,
`vitest@1.6.1`. Checked devDependency classification via `package-lock.json`'s
own `dev` flag (npm's authoritative classification, not just package.json's
top-level section) rather than assuming: **`vite`/`esbuild`/`vitest` are
genuinely dev-only** (confirmed `dev: true`, reachable only via
`vitest`/`vite-node`'s own nested tree). **`next` is a real production
dependency** (`dev: None`, listed directly in `"dependencies"` —
contradicted the stated premise). **The vulnerable `postcss@8.4.31` copy is
nested inside `next`'s own tree** (`node_modules/next/node_modules/postcss`,
`dev: None`) — also effectively production-path, not the safe top-level
devDependency copy (which resolved to a different, newer 8.5.26).

---

### `next` bumped 14.2.5 → 14.2.35; nested `postcss` forced to 8.5.26 via overrides

Two follow-up commits on `feature/REQ-2026-03`, each shown as a diff and
verified end-to-end before committing.

**`next` → 14.2.35** (latest 14.2.x patch, confirmed via `npm view next
versions` — deliberately not 15.x, per explicit direction that a major bump
is a bigger compatibility risk than this fix warrants). `eslint-config-next`
bumped alongside it (Next.js's own convention — that package tracks `next`'s
version). **Committed `18ca416`.** Real, mixed result, reported honestly
rather than oversold: the specifically-targeted `GHSA-f82v-jwr5-mffw` (9.1
CRITICAL, middleware authorization bypass) is confirmed gone, along with 10
others. **8 HIGH-severity findings remain** — their advisories list a fix
only on the 15.x branch, meaning Next.js never backported them to 14.x;
staying on 14.x is a real ongoing tradeoff, not resolved by this bump. The
nested `postcss@8.4.31` copy inside `next`'s own tree was confirmed
**unchanged** by this bump (predicted correctly before checking). Verified:
frontend 28/28 tests passed (unchanged), backend 39/39 passed (unaffected).
Also found, confirmed pre-existing and unrelated: `npm run build` fails on a
TypeScript conflict in `vitest.config.ts` (duplicate `vite` type definitions
between the top-level package and `vitest`'s own nested copy) — reproduced
identically against a fresh clone of the original `next@14.2.5` state, so not
caused by this bump; not fixed, since QA's real invocation never runs
`next build`.

**Nested `postcss` forced to 8.5.26 via a scoped `npm overrides` entry.**
Confirmed npm 8.3+/lockfile v2+ support first (this project: lockfileVersion
3, npm 11.6.2 locally) before applying. A flat top-level
`"overrides": {"postcss": "8.5.26"}` was rejected by npm itself
(`EOVERRIDE`: conflicts with the existing direct devDependency range) — fixed
by scoping the override to `next`'s own dependency specifically
(`"overrides": {"next": {"postcss": "8.5.26"}}}`), since that's the actual
intent (only the nested copy needs forcing, not the whole tree). **Getting it
to actually take effect needed more than a plain `rm -rf node_modules && npm
install`** — npm's own package cache had already cached the old resolution
for this specific dependency edge and kept reusing it even against a clean
`node_modules`, surfacing as a persistent `npm ls` `invalid`/`ELSPROBLEMS`
error. Required also deleting `package-lock.json` and `npm cache clean
--force` before the override was honored end-to-end. **Committed `82090c8`.**
Verified: `npm ls postcss` shows only `8.5.26` anywhere in the tree (root
marked `overridden`, every nested occurrence including `next`'s own copy
marked `deduped`); a real re-scan confirms both CVEs
(`CVE-2026-45623`/`CVE-2026-69153`) gone — only one `postcss` entry remains
in the report at all, 0 vulnerabilities; frontend 28/28 and backend 39/39
both re-confirmed passing, unaffected.

**Still open, not addressed this session:**
- 8 remaining HIGH-severity `next` findings with no 14.x backport available.
- `_parse_jest_json()`'s file-collection-failure blind spot (a fully-broken
  frontend suite can still report `qa-approved` if every file fails to
  collect rather than fails a specific test).

---

### `security_agent.py`'s `--exclude` fix committed; `vitest.config.ts` build conflict fixed and confirmed Stage-6-only

Two follow-up items from the section above, closed in a later same-project
session.

**The uncommitted `--exclude "**/node_modules/**"` fix was confirmed still
sitting locally** (checked `git status` before assuming anything) and
**committed as `fd4a0b7` on `main`**, using the exact commit message already
drafted when the diff was first shown.

**The `vitest.config.ts` TypeScript conflict was investigated further, fixed,
and re-verified.** Pulled the full (2,941-line) `npm run build` error rather
than the earlier summary: confirmed the exact failure is
`vitest.config.ts:6:13`, and confirmed it's the *same underlying pattern*
already found during the Dependency-Check CVE investigation — `vitest/config`'s
`defineConfig()` types against vitest's own nested `vite@5.4.21`, while
`@vitejs/plugin-react`'s `react()` types against the top-level `vite@7.3.6`.
`skipLibCheck: true` was already set in `tsconfig.json` but doesn't help (it
only skips `.d.ts` files, not real project source like this one). Tested the
fix live before committing anything: adding `vitest.config.ts`,
`vitest.setup.ts`, and `__tests__` to `tsconfig.json`'s `exclude` array
resolves the conflict completely — verified by re-running the build and
confirming zero mentions of `vitest.config.ts` anywhere, progressing past the
type-check stage into static page generation. **Committed `6639e09` on
`feature/REQ-2026-03`.** Re-ran both suites after: frontend 4/4 files, 28/28
tests passed (unchanged); backend 39/39 passed (unaffected).

A second, separate, unrelated error surfaces immediately after during
prerendering (`TypeError: Cannot read properties of null (reading
'useContext')` on `/`, `/404`, `/500`, `/_not-found`, `/audit`) — confirmed
via mixed path casing in its own stack trace (`C:\Users\mikef\Projects\...`
alongside `C:\Users\mikef\projects\...`) to be the same local-machine-only
Windows path-casing artifact already documented for REQ-2026-01. Confirmed
this persists even invoking the build via PowerShell instead of git-bash —
it's baked into this machine's `node_modules` own install-time state (first
populated via a lowercase-mounted shell), not the shell used to invoke the
build command. Cannot reproduce on a real, case-sensitive Linux CI runner;
not fixed, not blocking.

**Confirmed via a direct audit of every workflow file: nothing in the current
pipeline invokes `next build` before Stage 6.** Checked all of
`00-intake.yml` through `06-deploy.yml` (plus `03b-recover-implementation.yml`)
for `next build`/`npm run build`/`docker build`/`Dockerfile` — zero matches
anywhere except inside `06-deploy.yml`'s own invocation of `deploy_agent.py`,
which runs a real `docker build` against the frontend's own `Dockerfile`.
That Dockerfile's own "Stage 2: Build the Next.js app" contains `RUN npm run
build` directly. `04-qa.yml`'s only npm-related step is `npm install --prefix`
before `qa_agent.py` runs `vitest run` — no build step. This confirms the
`vitest.config.ts` conflict (now fixed) could only ever have been caught for
real at Stage 6, never earlier in the pipeline — exactly why it slipped past
QA on this PR.

---

### Open items for next session (REQ-2026-03 / PR #20 arc) — consolidated

Everything below was surfaced during this arc but deliberately not fixed —
each is a real, confirmed gap, not a guess:

1. **`qa_agent.py`'s `_parse_jest_json()` has a file-collection-failure blind
   spot.** It only counts individual test pass/fail (`numPassedTests`/
   `numFailedTests`), and never checks whether entire test *files* failed to
   even collect (Vitest's own top-level `success: false` / per-file
   `status: "failed"`). A Vitest run where every file fails to collect
   reports `0 passed / 0 failed / 0 total` — currently treated as a clean
   **pass**, not a failure. This is exactly what let a real, unrelated
   bad-import bug on REQ-2026-03's frontend slip through as `qa-approved`
   before it was caught by chance while pulling CVE detail (see above; fixed
   in `fc647df`, but the *classifier gap itself* was never fixed).
2. **8 HIGH-severity `next@14.2.35` findings have no 14.x backport.** Their
   advisories list a fix only on the 15.x branch — Next.js never backported
   them to 14.x. This is an accepted ongoing risk from the explicit decision
   to stay on the 14.x major line (see the `next` bump section above), not a
   gap in anything fixed this session. Only resolvable by eventually moving
   to 15.x, or waiting for an upstream 14.x backport that may never come.
3. **No pipeline stage before Deploy (Stage 6) validates that the app
   actually builds.** Confirmed via a direct audit of every workflow file
   (see immediately above): QA only ever runs `vitest run`/`dotnet test`; the
   first real `npm run build`/`docker build` in the entire pipeline happens
   inside `deploy_agent.py`'s Docker build at Stage 6. This is exactly what
   let both the `vitest.config.ts` type conflict and the local-only
   path-casing artifact go completely undetected until deliberately
   investigated this session, on request — nothing in the automated pipeline
   would have caught either on its own. Worth considering whether Deploy
   Agent (or QA) should build the frontend earlier in the pipeline, per the
   near-identical open question already logged for REQ-2026-02's frontend
   deploy bugs.
4. **QA's `_MAX_RETRIES` retry cap is not actually enforced anywhere — it
   only ever picks a label, never blocks a re-run.** Confirmed by reading
   both `qa_agent.py` and `04-qa.yml` directly: `_MAX_RETRIES` is consulted
   in exactly one place (`qa_agent.py`'s label-choice branch), and only when
   `tests_pass` is `False` — a passing run always gets `qa-approved`
   regardless of attempt number (confirmed live: PR #20's real attempt 4
   passed and was approved despite already being past the nominal limit of
   3). `04-qa.yml`'s only guard clause checks PR open-state and head-SHA
   match — nothing about label state or attempt count. The workflow will
   keep firing unconditionally on every push, forever; a human is expected to
   notice `qc-retry-limit-reached` and stop pushing manually, but nothing
   enforces that. Separately, the retry counter has no concept of
   "infrastructure/tooling failure" vs. "real app defect" — it just counts
   every QA comment ever posted, so a redundant manual `gh run rerun` (see
   above) burned a real attempt for zero new information.

---

### REQ-2026-03 Stage 6 Deploy — 0-of-2 failure, four `deploy_agent.py` fixes, two design forks resolved (2026-08-17/18)

Real (non-dry-run) Deploy Agent invocation against REQ-2026-03's merged PR
#20 commit (`e26363f8`) failed 0 of 2 units on first attempt. Root-caused
both failures, fixed four confirmed bugs per a dedicated spec
(`docs/FORGE-DeployAgent-UnitNaming-PublicDir-FailureComment-Spec.md`, drafted
Claude.ai side), each verified and committed separately.

**Pre-flight verification (before any deploy attempt):** confirmed the local
`forge-demo-apps-clone` checkout's `main` HEAD exactly matched PR #20's
`mergeCommit.oid` (`e26363f8beb25a4521fd8a78888a688f31ef689f`, `MERGED`).
Confirmed no stale deploy existed: one earlier `06-deploy.yml` run (2026-08-15)
had targeted REQ-2026-03 but self-skipped via its own guard clause (only
`design-approved`+`qa-approved` present, `security-approved` not yet) — no
resources were ever created from it. `forge-staging`'s `defaultDomain`
unchanged. First invocation attempt itself failed for an unrelated reason —
passing a Windows backslash `--repo-path` unquoted through the Bash tool's
POSIX shell ate the backslashes before Python saw them, producing a bogus
"no deployable units" failure comment on issue #6; not a pipeline bug, fixed
by quoting the path.

**Bug 1 — `_slugify()` produced an invalid Docker tag for any project name
containing a literal `.`.** Confirmed live: REQ-2026-03's backend csproj
directory is `OnCallRosterTracker.Api`; the existing slugifier only
converted PascalCase boundaries to hyphens, leaving the literal `.`
untouched, so the hyphen inserted before `Api` landed immediately after the
dot (`...tracker.-api`) — Docker rejects this outright
(`invalid reference format`). `docker build` never ran; no image, no push,
no Container App for this unit.

**Bug 2 — frontend Dockerfile's `COPY --from=builder /app/public ./public`
failed — second confirmed occurrence of the exact REQ-2026-02 bug.**
`services/REQ-2026-03/frontend` has no `public/` directory (no static
assets, and Git doesn't track empty directories), so the COPY step failed
("not found"), aborting the frontend build independently of Bug 1. Fix 3 of
the earlier Cross-Service Wiring spec's per-unit `try`/`except` isolation
worked exactly as designed — the frontend attempt still ran after the
backend failed.

**Fix 1 (`_slugify()` + new `_validate_unit_name()`, commit `8bbd65f`):**
`_slugify()` now treats any non-alphanumeric run (not just PascalCase
boundaries) as a word separator, collapsing to a single hyphen —
`OnCallRosterTracker.Api` → `on-call-roster-tracker-api` (valid characters).
`_validate_unit_name()` checks the full `<request-id>-<slug>` name against
Docker's tag grammar and Azure Container Apps' naming rules (confirmed live
via `az containerapp create --help`: lowercase alphanumeric + hyphen, starts
with a letter, no leading/trailing/double hyphen, **must be under 32
characters**) and raises a clear, named `ValueError` instead of letting an
invalid name reach `docker build`/`az containerapp create` and fail there.
No regression: `DocumentApi`/`EmailWorker`/`AuditorApi` (REQ-2026-01/02,
already live) produce identical names to before.

**Design fork #1, surfaced and resolved with Mike before implementing:**
even after the character fix, REQ-2026-03's full unit name
(`req-2026-03-on-call-roster-tracker-api`) is **38 characters** — still
invalid, now on length, not characters. Stripping the generic `.Api` suffix
only gets to 34 — still over the limit. No truncation scheme was specified,
so this was flagged rather than guessed at. **Mike's decision: raise a
clear `ValueError`, do not truncate.** Consequence, accepted: REQ-2026-03's
backend unit genuinely cannot deploy under the current
`<request-id>-<slug>` naming convention until a separate naming decision is
made (e.g. renaming the project directory) — this is an open item, not
fixed here.

**Fix 3 (backend-name validation before the frontend build-arg, commit
`6a3d81a`):** `run_deploy_agent()` now validates the backend "web" unit's
name (via Fix 1) *before* deriving either FQDN for cross-service wiring —
previously an invalid backend name would still get baked into the
frontend's `NEXT_PUBLIC_API_BASE_URL` build-arg even though that backend
unit was guaranteed to fail its own build. On validation failure, falls
back to the existing "no web backend unit in this request" no-wiring
warning instead of proceeding with a broken value. Verified via mocked
simulation (all docker/az/GitHub calls stubbed, `_run_shell` hard-mocked to
raise if ever called — same safety pattern the Cross-Service Wiring spec
established after its own live-`containerapp`-creation near-miss): REQ-2026-03
(invalid backend) → frontend `build_args` is `None`; REQ-2026-01 (valid
backend, control) → frontend `build_args` unchanged, still carries the real
FQDN.

**Fix 2 (`_ensure_frontend_public_dir()`, commit `9c732a6`):** creates an
empty `services/<request-id>/frontend/public/` directory in the local
checkout, right before the build, if missing.

**Design fork #2, surfaced and resolved with Mike before implementing:** the
spec's own recommended fix (Option A — make the Dockerfile-generation
template's COPY line conditional) turned out not to actually fix this
failure at all: REQ-2026-03's frontend Dockerfile was already committed by
the Frontend subagent during Implementation (confirmed by reading it
directly), and Deploy Agent's own rule is to never overwrite an existing
Dockerfile (`_generate_dockerfile_if_missing()`) — a template-only fix
would not have touched either of the two real occurrences of this bug (both
REQ-2026-02 and REQ-2026-03 already had committed Dockerfiles). **Mike's
decision: fix at the filesystem level instead** — same outcome either way
(a real directory for `COPY . .` to pick up), works identically regardless
of whether the Dockerfile was generated or pre-existing. Verified: unit test
(create once, no-op on repeat) plus a real local `docker build` (no ACR
push) against REQ-2026-03's actual frontend — completed end-to-end, exit 0;
the previously-failing COPY step now completes in 0.5s. No regression
against REQ-2026-02's frontend, which already has a real `public/.gitkeep`
from its own earlier one-off manual fix.

**Fix 4 (failure-comment wording, commit `71a786a`):** the tracking-issue
partial-failure comment hardcoded `"-- the rest were deployed
successfully"` regardless of the actual success count — confirmed live on
the first REQ-2026-03 attempt (0 of 2 succeeded, comment still claimed a
partial success). Made the clause conditional on the real count. Verified
both the all-failed case (now reads "none of this request's unit(s) were
deployed") and the pre-existing partial-failure case (unchanged wording),
confirming no overcorrection.

**Final re-run after all four fixes: 1 of 2 units deployed for real.**
Backend still fails — expected, per the accepted Design fork #1 decision
(length, not characters). Frontend (`req-2026-03-frontend`) built, pushed to
ACR, and `az containerapp create` succeeded for real:
`req-2026-03-frontend.yellowmeadow-894377a9.canadacentral.azurecontainerapps.io`.
Fix 4 confirmed correct in the real (not simulated) partial-failure case too
— the posted issue #6 comment correctly read "1 of 2 unit(s) failed... the
rest were deployed successfully."

**A third, new, previously-undiscovered gap found while verifying the live
frontend — not fixed, flagged only, same "Deploy Agent doesn't wire
app secrets" class of gap already documented for EmailWorker's Service Bus
connection string and REQ-2026-02's D365 config.** `curl`ing the live
frontend root returns a real HTTP 307 (ingress/TLS layer confirmed
genuinely live) redirecting to `/api/auth/error?error=Configuration` —
container logs show `next-auth][error][NO_SECRET]` /
`MissingSecretError: Please define a 'secret' in production.`. This app uses
NextAuth (`middleware.ts` + `app/api/auth/[...nextauth]/route.ts`), which
requires a `NEXTAUTH_SECRET` (and likely other provider config) as a
Container App env var — `deploy_agent.py` only ever sets
`--image`/`--registry-*`/`--cpu`/`--memory`/`--min-replicas`/
`--max-replicas`/`--target-port`/`--ingress` (plus the Cross-Service Wiring
spec's `NEXT_PUBLIC_API_BASE_URL`/`FRONTEND_ORIGIN`), never arbitrary
application secrets. **Because the backend never deployed (Design fork #1)
and the frontend can't render past its own auth-configuration error, the
requested end-to-end write-path verification (a real POST/PUT/DELETE shift
claim/release call through the live frontend) could not be performed this
session** — there is no live backend to call, and no way to reach the
frontend's actual UI past the auth redirect.

**Open items, explicitly flagged, not fixed:**
- REQ-2026-03's backend unit name doesn't fit the `<request-id>-<slug>`
  naming convention under Azure's 32-character limit — needs an explicit
  naming decision (e.g. renaming the `OnCallRosterTracker.Api` project
  directory) before this unit can ever deploy as-is.
- NextAuth's `NEXTAUTH_SECRET` (and any other required auth provider env
  vars) are never wired by Deploy Agent for any request — a real,
  now third, occurrence of the "Deploy Agent has no app-secret wiring
  mechanism" gap.
- The real write-path (claim/release) verification against a live backend
  + live frontend for REQ-2026-03 has still never been performed, blocked
  by both items above.

Per the spec's own standing convention: this session did not update
`FORGE-context_v56.md` — that's Claude.ai's job at session close.
