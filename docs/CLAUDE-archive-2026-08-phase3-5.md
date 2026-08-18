# CLAUDE.md archive — Phase 3-5 (Stage build-out through Phase 5 close-out)

Archived from CLAUDE.md on 2026-08-18 to keep the live file lean. This is verbatim
historical narrative — dated live-run verifications, incident write-ups, and the
Phase 4 pipeline-wiring/branch-protection saga — moved out of CLAUDE.md because it's
no longer needed on every session load. Current, still-relevant behavior extracted
from this material lives in CLAUDE.md itself; `docs/FORGE-context_v57.md` (and later)
carries the narrative forward. Nothing here has been edited from the original text.

---

**Live run verified 2026-07-29:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- 1,045 input tokens / 472 output tokens / `total_cost_usd: $0.010215` / 13.3 s
- 6 questions posted; `clarification-pending` label applied


**Live run verified 2026-07-29:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- 2,281 input tokens / 3,876 output tokens / `total_cost_usd: $0.064983` / 62.5 s
- `requirements.md` + `ado-work-items.json` committed to `forge-demo-apps` on `main`
  (historical — this run predates the Phase 4 step 4.8 retrofit that moved both
  files to the `pipeline-state` branch; see above)
- Summary comment posted to issue #2; no label applied (label is human action)


**Live run verified 2026-07-30:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- 2,929 input tokens / 12,738 output tokens / `total_cost_usd: $0.199857` / 222 s
- `design.md` + `openapi.yaml` + `tasks.md` committed to `forge-demo-apps` on `design/REQ-2026-01`
- Draft PR #4 opened; summary comment posted to issue #2


**Dry run verified 2026-07-30:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- session `sesn_0158Mvs91wfr9rNHPfa9W1oH` — 4 threads (coordinator + 3 specialists), `idle (end_turn)`
- Archive: 156,728 bytes → 96 files extracted under `services/REQ-2026-01/`
  (full .NET solution with DocumentApi + EmailWorker, Next.js frontend, xUnit + Jest tests)

**Live (real, non-dry-run) run verified 2026-07-30:**
- Issue `forge-template#2`, request-id `REQ-2026-01`
- session `sesn_01EP8tcHcgdkSz7m14wKL4k6` — 4 threads (coordinator + 3 specialists), `idle (end_turn)`
- Archive: 79,601 bytes → 101 files extracted under `services/REQ-2026-01/`
  (full .NET solution with DocumentApi + EmailWorker, Next.js/TypeScript frontend,
  xUnit + Jest tests, Playwright e2e tests, `COMPLIANCE_CHECKLIST.md`)
- Committed to `feature/REQ-2026-01` in `forge-demo-apps`; draft **PR #5** opened
  against `main`; summary comment posted to tracking issue #2
- Session, environment, coordinator, and all 3 subagents archived cleanly after commit

**Operational incident during this run — resumed by ID, not by re-invoking the script:**
The `python -m core.agents.implementation_coordinator` process was killed by the
invoking shell tool's own timeout (background commands are capped around 10 minutes
in that tooling) while `poll_until_idle()` was still waiting. This killed the *local*
script only — the Managed Agents session itself runs server-side and kept working
independently, reaching `idle (end_turn)` on its own. Recovery was a small one-off
script that reused the already-known `session_id` / `coordinator_id` / `subagent_ids`
/ `environment_id` (from the `managed_agents_session_start` JSON log line printed
before the kill) to resume exactly where `run_implementation_coordinator()` left off —
`poll_until_idle()` (instant, since already idle) → audit trail → list/download output
files → `_extract_archive_to_file_dict()` → `commit_files()` → `open_pr()` →
`post_comment()` → `archive_session()`.


**Verified 2026-08-03:** unit-tested with synthetic data in Claude.ai chat (no live
API/GitHub/ADO calls). `py_compile` clean; `smoke_github` (8/8) and `smoke_ado`
(4/4) re-run clean after the additive `github_helper.py`/`ado_helper.py` changes.
Confirmed `forge-demo-apps`' frontend `package.json` has `"test": "jest"` (a bare
script with no args of its own), so `npm test -- --ci --json --outputFile=...`
correctly forwards those flags to Jest, matching the module docstring's assumption.

**Real `--dry-run` verified 2026-08-04** against an actual local checkout
(`C:\Users\mikef\projects\forge-demo-apps-clone`, `services/REQ-2026-01/{backend,frontend}`)
— first time this script ran real `dotnet test` / `npm test` rather than synthetic
data. Results: backend 9/11 passed, frontend 38/44 passed, 8 deterministic bug
candidates computed, Claude wrote the PR report, correctly recommended
`qa-loop-back` (attempt 1 of 3). Confirms the TRX/Jest-JSON parsing, severity
heuristic, and retry-attempt logic all work against real tool output, not just
hand-built fixtures.

**Two Windows-only bugs found and fixed in `_run_shell()` during that run**
(both in the helper only — no behavior change on the Linux GitHub Actions
runners this normally runs on):
1. `subprocess.run(["npm", ...])` raised `FileNotFoundError` on Windows — `npm`
   is actually `npm.cmd`, and Win32 `CreateProcess` doesn't consult `PATHEXT`
   the way `cmd.exe` does, so a bare `"npm"` never resolves. Fixed by resolving
   `command[0]` through `shutil.which()` before passing to `subprocess.run`.
2. Jest's UTF-8/ANSI output (checkmarks, color codes) crashed a `subprocess`
   reader thread with `UnicodeDecodeError` under Windows' default `cp1252`
   text decoding. Fixed by passing `encoding="utf-8", errors="replace"`
   explicitly. Didn't corrupt the first run's result (frontend parsing reads
   the JSON report file, not stdout) but would have crashed the "suite failed
   to produce a report" diagnostic path, which does fall back to a stdout/stderr
   tail.

**Discovered during that same session: PR #5 was already merged, and the checkout
had uncommitted local patches never pushed to `forge-demo-apps`.** The dry-run's
8 failures were run against a checkout someone had hand-patched to even get
`dotnet restore`/`npm test` to run at all (missing `SendGrid.Extensions.
DependencyInjection` package ref, missing `using Microsoft.Extensions.
Configuration;`, an unresolvable `Microsoft.AspNetCore.Http.Features` package
ref, an invalid Jest config key `setupFilesAfterFramework` instead of
`setupFilesAfterEnv`, and missing frontend test devDependencies) — none of
which were ever committed. Filed as **PR #7** (`fix/req-2026-01-test-infra` →
`main`), reviewed, one stale/contradictory code comment removed, merged
2026-08-04 (`fcae2b6`). Re-verified with a fully clean checkout
(`git clean -xdf` in both `backend/` and `frontend/`, fresh `dotnet restore` +
`npm install`) — **identical 8-failure result**, confirming these are real
application bugs, not artifacts of the earlier patched state.

**Real (non-dry-run) live run verified 2026-08-04**, against that clean,
post-PR#7 checkout, invoked manually with `--repo-path` pointing at the local
clone (no Phase 4 workflow wiring involved — `--pr-number` is only required
for a real run per the script's own argparse help text; a manually-supplied
checkout satisfies the "needs a repo on disk" requirement just as well as an
Actions `actions/checkout` step would):
- 8 ADO Bugs filed in FORGE-Build: #96–97 (backend, Severity 3-Medium),
  #98–103 (frontend, Severity 2-High) — all with no parent User Story link
  (expected; Phase 4 ADO item creation hasn't run for this request yet)
- PR comment posted: `forge-demo-apps#5` comment
  (`issuecomment-5184902825`), attempt 1 of 3
- Label `qa-loop-back` applied to tracking issue `forge-template#2`
  (alongside the pre-existing `clarification-pending`)
- Claude call: 3,361 in / 947 out tokens, $0.024288, 15.58s

**Still not exercised: the actual Phase 4 GitHub Actions checkout wiring**
(step 4.5) — this run used a manually-provided local clone, not an
Actions-driven checkout. Functionally equivalent for the script's own logic,
but the workflow-level wiring itself remains unbuilt.


**Verified 2026-08-05:** `py_compile` clean throughout.

**Real `--dry-run` first surfaced a genuine false positive**, run against
the merged PR #5 checkout at `services/REQ-2026-01/`: Gitleaks flagged 1
Critical finding — a hardcoded fake credential in
`backend/DocumentApi.IntegrationTests` (`WebApplicationFactory` test setup
config), the same class of expected-fixture-secret already anticipated in
the module's own severity-mapping design. Fixed by adding
`team/gitleaks-allowlist.toml` (Document 7's Flexible/Locked model — team-
configurable allowlist, `useDefault = true` keeps Gitleaks' full default
ruleset active everywhere else) with a path regex excluding any
`.../*test*/...` directory, and wiring `--config` into `_run_gitleaks()`
(see `github_helper.py` entry above for the four supporting GitHub API
functions this stage needed). Re-run confirmed the fix: Critical → 0,
Semgrep/Dependency-Check results unaffected, `check_conclusion` flipped to
`success`.

**Real (non-dry-run) live run verified 2026-08-05**, against that same
clean, post-allowlist-fix checkout, invoked manually with `--repo-path`
pointing at the local clone of the merged PR #5 (same "manual invocation
satisfies the on-disk-repo requirement" pattern as the QA Agent's real run
— Phase 4's checkout wiring, step 4.6, still not built):
- All three scanners ran clean: 0 findings (Semgrep, Gitleaks, Dependency-
  Check all 0), 0 Critical
- Overview comment posted to `forge-demo-apps` PR #5
- `security-check` check run created on PR #5's head commit (`0f5f1c57`),
  conclusion `success`
- Label `security-approved` applied to tracking issue `forge-template#2`
- Claude call: 599 in / 269 out tokens, $0.005832, 5.37s

### deploy_agent.py — Stage 6 (Deploy, staging)

Entry point: `python -m core.agents.deploy_agent --issue-number <n> --request-id <id> --repo-path <path> --commit-sha <sha> --pr-number <n> [--dry-run]`

Like QA and Security, this stage needs the actual repository contents on
disk (`--repo-path`) — it does not clone anything itself. Unlike every
prior stage, **it never calls Claude/`invoke_agent()`** — unit detection,
Dockerfile generation, and the PR comment are all deterministic
string/template work with no judgment call to hand to a model, the same
"FORGE automatic, not AI judgment" discipline QA's severity classifier and
Security's severity tables already established, just taken one step
further (no model call at all, not even for a write-up).

- **Unit detection** walks `services/<request-id>/backend/` for `*.csproj`
  files (skipping any path with a case-insensitive "test" segment, same
  convention as `team/gitleaks-allowlist.toml`), classifies each as `web`
  (references `Microsoft.NET.Sdk.Web`/`Microsoft.AspNetCore.App`) or
  `worker` (references `Microsoft.Extensions.Hosting`, no ASP.NET
  reference; also the default for an unclassifiable project, logged as a
  warning — the safer failure mode, since `web` implies public ingress).
  `services/<request-id>/frontend/package.json` becomes one additional
  `frontend` unit if present. Each unit's Container App / image name is
  `<request-id>-<slug>` (all lowercase — both Docker repository names and
  Azure Container App names reject uppercase; e.g. `DocumentApi` →
  `req-2026-01-document-api`).
- **Dockerfiles are generated from the three new templates
  (`core/agents/templates/dockerfiles/`) only when a project directory
  doesn't already have one of its own** — never overwrites an existing
  Dockerfile. A matching `.dockerignore` is generated the same way (not
  in the original brief, but required for a correct build — without it,
  `COPY . .` in the generated templates would overwrite the fresh,
  correct-platform artifacts from the earlier build stage with
  host-platform ones, and balloon the build context with node_modules/
  bin/obj).
- **Target ports are fixed, not configurable per run:** web units 8080
  (ASP.NET Core 8+ container default), frontend 3000 (`next start`
  default), worker units get no ingress at all.
- **`docker build`/`docker push` run for real in both `--dry-run` and a
  real run** — same "exercise the real tool, skip only the posting"
  pattern as QA/Security. `az login --service-principal` (parsing the
  `AZURE_STAGING_CREDENTIALS` JSON blob) and the read-only `az containerapp
  show` existence check also run for real in both modes, so the printed
  dry-run command reflects an accurate create-vs-update decision. Only the
  `az containerapp create`/`update` mutation itself is print-only (redacted
  `--registry-password`) in `--dry-run`.
- **`_detect_design_gaps()`** flags (never blocks) any unit whose project
  label doesn't appear in `docs/<request-id>/design.md`, surfaced in the PR
  comment. Checks both the literal identifier and a de-camelCased spaced
  variant ("EmailWorker" → "Email Worker") case-insensitively — design.md
  is human-authored prose and never uses the bare camelCase identifier; a
  literal-only check produced a false-positive gap on `DocumentApi` during
  this session's own verification (see below).
- No label applied on success — Document 6's Label Reference table has no
  deploy-stage label; staging is a verification step, not a release gate.

**Verified 2026-08-05:** `py_compile` clean throughout.

**Real `--dry-run` against the merged PR #5 checkout surfaced a genuine,
previously-undiscovered app bug**, not a Deploy Agent bug: `next build`
failed its type-check on `frontend/components/Navigation.tsx:28` —
`lucide-react` icon components inherit React's full `AriaAttributes`,
where `aria-hidden` is typed `Booleanish` (`boolean | "true" | "false"`),
but `NavItem.icon`'s custom prop type declared `aria-hidden` as plain
`boolean`, making the icons structurally incompatible. Never caught before
because QA's `npm test` only runs Jest, never `next build`/`tsc`. Fixed on
`forge-demo-apps` branch `fix/req-2026-01-navigation-aria-types` (widened
to `React.AriaAttributes["aria-hidden"]`, the exact type React itself
uses) — **opened as PR #8, deliberately left unmerged pending Mike's
review**, same "small, separate, mechanical fix" pattern as QA's PR #7.

**A second, unrelated, pre-existing type error surfaced immediately
after** in `lib/app-insights.ts:70` — a duplicate `@microsoft/
applicationinsights-core-js` dependency resolution (hoisted at top-level
`node_modules` vs. nested inside `applicationinsights-analytics-js/
node_modules/`), so TypeScript sees two structurally-identical-but-
nominally-different `ITelemetryPlugin`/`ITelemetryItem` types. **Explicitly
not investigated or fixed this session, per Mike's direction** — flagged
as an open follow-up. As a result, **the frontend unit was not verified
end-to-end this session**: it was parked (its `package.json` renamed aside
in the local checkout only, no code change) so unit detection would skip
it, and dry-run/real-run verification proceeded backend-units-only.

**Real (non-dry-run) live run verified 2026-08-05**, backend units only,
against the same merged-PR-#5 checkout used for QA/Security's real runs:
- 2 units detected: `req-2026-01-document-api` (web),
  `req-2026-01-email-worker` (worker)
- Both Dockerfiles already existed (committed by Stage 3 back in PR #5) —
  neither template was actually exercised for this run; the templates are
  verified structurally but not yet by a real from-template build. The
  Next.js template is similarly unexercised (frontend parked).
- Both images built and pushed to `forgedemoacr.azurecr.io` for real
- Both Container Apps created for real via `az containerapp create`
  against `forge-staging` (`forge-build-rg`, per `team/config.yaml`)
- PR comment posted: forge-demo-apps#5
  (issuecomment-5197961121)
- **`req-2026-01-document-api` confirmed actually working**: its staging
  FQDN (`req-2026-01-document-api.yellowmeadow-894377a9.canadacentral.
  azurecontainerapps.io`) resolves and responds over HTTPS (~0.3s once
  warm; first request timed out during cold-start scale-from-zero,
  `min_replicas: 0` per `team/config.yaml`, then responded fine on retry).
  404s on `/` and `/swagger/index.html` are expected (no root route;
  Swagger UI is Development-only, this container runs
  `ASPNETCORE_ENVIRONMENT=Production`) — this confirms the ingress/TLS/
  container layer is genuinely live, not that every route is mapped.
- **`req-2026-01-email-worker` deployed but is crash-looping — a real,
  previously-undiscovered gap, not a Deploy Agent bug.** `az containerapp
  revision list` shows `healthState: Unhealthy` / `runningState: Failed`.
  Container logs show `System.FormatException: The connection string
  could not be parsed` from `ServiceBusClient`'s constructor at host
  startup (`Program.cs:20`) — EmailWorker's hosted service builds its
  Service Bus client eagerly at startup and crashes immediately with no
  connection string configured. **Deploy Agent (as scoped this session)
  has no mechanism at all for wiring application secrets/connection
  strings (Service Bus, SQL, Blob Storage, SendGrid, App Insights) into
  the Container App** — only `--image`/`--registry-*`/`--cpu`/`--memory`/
  `--min-replicas`/`--max-replicas`/`--target-port`/`--ingress` are ever
  set. DocumentApi doesn't crash the same way because EF Core/Blob clients
  are constructed lazily (only touched on first actual request), so a
  missing connection string there just means the *first real API call*
  would fail, not the whole host at startup — the ingress-level check
  above cannot distinguish this from full correctness. **This needs an
  explicit decision (Key Vault references? Container App secrets driven
  from a new team/config.yaml or GitHub-secrets source? something else?)
  before EmailWorker can actually run in staging** — flagged here, not
  designed or built.
- Two bugs found and fixed in `deploy_agent.py` itself while getting to
  the clean runs above: an em-dash console-encoding issue in log messages
  (same class of fix already applied to `security_agent.py`'s log lines —
  fixed to ASCII `--`), and the design.md-gap false-positive described
  above (fixed to check both the literal and spaced form).
- `.env.example` gained `ACR_LOGIN_SERVER`/`ACR_USERNAME`/`ACR_PASSWORD`
  and `AZURE_STAGING_CREDENTIALS` entries (were previously undocumented
  there despite being referenced in other project docs).
- Local tooling: Docker Desktop and Azure CLI (64-bit) already installed
  and confirmed working per chat 33's setup — no new install steps this
  session.

**Still open, not built/fixed this session (explicitly out of scope per
the brief, or newly flagged):**
- Frontend unit unverified end-to-end (parked — see PR #8 and the
  app-insights dependency issue above).
- EmailWorker's runtime connection-string gap (needs a design decision,
  not just a fix).
- Production path, rollback, and Phase 4 GitHub Actions wiring for either
  environment — all explicitly deferred per the original brief.

---

### Phase 4 — Pipeline Wiring (Build Plan steps 4.1–4.7, 4.9)

All seven `.github/workflows/*.yml` files rewritten from `workflow_dispatch`-only
stubs to real triggers, wired 2026-08-05/06. Every workflow follows the same
shape: guard clause re-checks trigger state at run time (not just at the
event, since labels/PR state can change between event and runner start) →
resolve request-id/PR context → invoke the real stage agent script (no
`--dry-run`) → label lifecycle cleanup → a final catch-all step posts a
failure comment if a *pre-agent* glue step failed (the agent scripts
themselves already self-report their own internal failures per ADR-0011 —
this only covers the gap before that point, and is skipped whenever the
agent step actually ran, to never double-post).

**Trigger mapping:**

| Workflow | Trigger | Clears on success |
|---|---|---|
| `00-intake.yml` | `intake-ready` label | `intake-ready` |
| `01-requirements.yml` | `clarification-complete` label | `clarification-complete`, `clarification-pending` |
| `02-design.yml` | `requirements-approved` label | `requirements-approved` |
| `03-implementation.yml` | `design-approved` label | `design-approved` |
| `04-qa.yml` | `repository_dispatch` (`feature-pr-opened`, from forge-demo-apps) | none (qa_agent.py labels itself; a pass also clears a stale `qa-loop-back`/`qc-retry-limit-reached` from an earlier attempt) |
| `05-security.yml` | `repository_dispatch` (`feature-pr-opened`) | none (security_agent.py labels itself; no retry-loop label exists for this stage) |
| `06-deploy.yml` | BOTH `qa-approved` AND `security-approved` present | none (Document 6 has no deploy-stage label; `qa-approved`/`security-approved` stay as valid historical markers) |

**Cross-repo trigger problem and its fix:** `04-qa.yml`/`05-security.yml` need
to run off a PR event that happens in `forge-demo-apps`, but a workflow can
only be triggered by an event in the repo where it's defined. Fixed via
`repository_dispatch`: `forge-demo-apps` gained its own
`.github/workflows/notify-forge.yml` (pushed there directly via `gh api`,
since the FORGE App itself has no `workflows` permission and can't write
workflow files programmatically) that fires on `pull_request` (`opened`,
`synchronize`), filters to `feature/*` branches only, and forwards
`{pr_number, head_sha, head_ref}` to forge-template as a `repository_dispatch`
event type `feature-pr-opened`, using a GitHub App token freshly scoped to
forge-template (`actions/create-github-app-token@v3`).

**Three manual prerequisites this required, all completed 2026-08-06:**
1. The FORGE App (app_id 4388813, installation id 148876680) is now
   installed on **both** forge-template and forge-demo-apps — confirmed via
   a JWT-authenticated `GET /repos/.../installation` check on both repos
   (both return 200 with identical permissions:
   `checks/contents/issues/pull_requests: write`, `metadata: read`). This had
   to be done via the GitHub web UI — the API rejects attempts to modify an
   App's own installation repository list from anywhere other than that UI.
2. `forge-demo-apps` gained its own copies of `FORGE_APP_CLIENT_ID` (repo
   variable) and `FORGE_APP_PRIVATE_KEY` (repo secret) — repo secrets/vars
   don't cross repos in GitHub Actions, so forge-template's existing values
   weren't visible there.
3. `notify-forge.yml` itself, pushed to forge-demo-apps' `main`.

**New scripts:**
- `core/agents/create_ado_items.py` — no driver existed to wire
  `ado_helper.py`'s `create_epic`/`create_feature`/`create_user_story` to
  `docs/<request-id>/ado-work-items.json`. Reads that file (`pipeline-state`
  branch, moved off `main` — see the Step 4.8 entry below), creates the real
  Epic → Features → User Stories hierarchy, writes the real
  IDs back plus a new top-level `primary_user_story_id` key (the first User
  Story created, in document order — `qa_agent.py`'s
  `_resolve_parent_story_id()` already looks for exactly this key and had
  been silently no-op'ing on its absence since Step 3.8). If ANY ADO call
  fails partway through, posts a failure comment naming what succeeded before
  the failure (items already created are NOT rolled back — ADO has no
  multi-item transaction) and exits non-zero, so `02-design.yml` never
  invokes the Design Agent against a partial traceability chain.
- `core/agents/workflow_glue.py` — four subcommands used only by the
  workflows themselves, with no equivalent in any stage agent:
  `download-issue-attachment` (finds and downloads the BA's intake
  spreadsheet from the tracking issue's body/comments — handles both GitHub
  attachment URL shapes), `resolve-request-id` (scans issue comments for any
  prior stage's `<!-- forge:agent-comment ... request_id=... -->` marker —
  one tracking issue maps to exactly one request for its whole life),
  `resolve-feature-pr` (finds the feature PR number/head SHA from the
  Implementation Coordinator's own tracking-issue comment, for
  `06-deploy.yml`), `resolve-tracking-issue` (the reverse — finds the
  tracking issue number from a forge-demo-apps PR body's own "Related FORGE
  tracking issue: owner/repo#N" line, for `04-qa.yml`/`05-security.yml`,
  which only ever learn a PR number from the dispatch payload).
- `github_helper.py` gained `get_issue()` (issue object incl. current labels
  — needed by every guard clause; didn't exist before since no prior stage
  needed to re-read an issue's own label set).

**Design decision made where the brief was silent:** `06-deploy.yml` deploys
against the feature PR's **HEAD commit**, not a merged one. Nothing in the
label-driven trigger chain guarantees the PR has been merged by the time both
`qa-approved`/`security-approved` land (both gate *before* merge, by design —
see `04-qa.yml`/`05-security.yml`'s own header comments), and
`deploy_agent.py` only ever needed a commit SHA to tag the image with, not a
merged one. Confirmed intentional: staging is a pre-merge verification
environment for the human reviewer (Document 2 §4.8's framing — "a
verification step, not a release"), not a post-merge release gate.

**Verified 2026-08-06** via a real `repository_dispatch` fired manually
against the existing PR #5 / tracking issue #2 pair (deliberately not a fresh
PR — reusing already-completed Stage 3 output to avoid re-running the
Managed Agents coordinator, whose cost is out of proportion to what this
verification needed):
- Confirmed both App-installation and forge-demo-apps secrets prerequisites
  above were actually in place first (not assumed).
- Fired `POST /repos/Flamespiker/forge-template/dispatches` with
  `event_type: feature-pr-opened`, `client_payload: {pr_number: 5, head_sha:
  "0f5f1c57ea5812537bc6d0150aa55d3722f3b190", head_ref:
  "feature/REQ-2026-01"}` — the same payload shape `notify-forge.yml`
  produces for a real event.
- Both `04-qa.yml` ([run 31068863663](https://github.com/Flamespiker/forge-template/actions/runs/31068863663))
  and `05-security.yml` ([run 31068863654](https://github.com/Flamespiker/forge-template/actions/runs/31068863654))
  fired for real off the dispatch, both concluded `success`. Logs confirm the
  `client_payload` crossed the repo boundary intact (`PR_NUMBER: 5`,
  `HEAD_SHA: 0f5f1c57...`, `HEAD_REF: feature/REQ-2026-01`), and both guard
  clauses correctly read PR #5's live state (`closed`, since it's merged) and
  correctly skipped every downstream step (checkout, toolchain setup, the
  real `qa_agent.py`/`security_agent.py` invocation) rather than running
  against a stale event — confirmed no new PR #5 comment resulted.
- **What this confirms:** the full cross-repo dispatch mechanism, payload
  shape, and guard-clause decision logic all work correctly end-to-end.
- **What this does NOT confirm:** a real `qa_agent.py`/`security_agent.py`
  invocation actually completing through this dispatch path (posting a PR
  comment, applying a label) — that requires an actually-open PR, which
  would mean either a new throwaway PR or re-running Stage 3, both
  deliberately out of scope this session.

**Commit:** `8a702ee` on `main` (all ten Phase 4 files — seven workflows,
`create_ado_items.py`, `workflow_glue.py`, `github_helper.py`'s `get_issue()`
addition — committed and pushed together). `55a1384`/`3201fa8` document this
Phase 4 section itself in `CLAUDE.md`.

**Step 4.8 — branch protection: complete, after resolving a real conflict it
surfaced (not just a config change).** `forge-demo-apps`'s `main` branch
protection is live, confirmed via `gh api repos/Flamespiker/forge-demo-apps/
branches/main/protection`:
- `required_status_checks.checks`: `[{"context": "security-check", "app_id":
  4388813}]` (pinned to the FORGE App's own check run from
  `security_agent.py`'s `create_check_run()`), `strict: false`
- `required_pull_request_reviews.required_approving_review_count`: `1`,
  `dismiss_stale_reviews: false`, `require_code_owner_reviews: false`,
  `require_last_push_approval: false`
- `enforce_admins: true`, `allow_force_pushes: false`, `allow_deletions: false`,
  `required_linear_history: false`
- **No `bypass_pull_request_allowances`** — not needed; see below.

This is what actually makes a Critical security finding block merge (the
`security-check` check run's `failure` conclusion, not the `security-approved`
label, per Document 2 §4.7 — the label is informational for humans, this is
the enforcement mechanism).

**How this actually got applied — first attempt found a real conflict, second
attempt hit a platform limitation, third attempt resolved it properly:**
1. First applying required-PR-review protection to `main` would have broken
   `requirements_agent.py` and `create_ado_items.py`, both of which wrote
   `requirements.md`/`ado-work-items.json` **straight to `main`** via
   `commit_files()` — a direct ref update, which required-review protection
   rejects identically to a `git push`. Found by reading the live source
   before applying anything, not discovered by breaking something.
2. Considered adding the FORGE App to
   `required_pull_request_reviews.bypass_pull_request_allowances.apps`
   (confirmed the correct field expects the app **slug**, `"forge-pipeline"`,
   not the numeric app ID — those are two different formats; the app ID
   *is* used, but only in `required_status_checks.checks[].app_id`). Rejected
   by GitHub with a 422 (`"Only organization repositories can have users and
   team restrictions"`) even with only `apps` populated — confirmed
   empirically that `bypass_pull_request_allowances` cannot be used at all on
   a personal-account-owned repo like forge-demo-apps, not just its
   `users`/`teams` sub-fields as the docs' wording alone would suggest.
3. **Resolution: moved `requirements.md`/`ado-work-items.json` off `main`
   entirely, onto a dedicated, intentionally-unprotected `pipeline-state`
   branch** (created once, branched from `main`'s tip — persistent and
   shared across every request, unlike the per-request `design/<request-id>`/
   `feature/<request-id>` branches, so neither writer calls `create_branch()`
   itself). Framing: these two files are pipeline bookkeeping/traceability
   records, not application code — the real human review for Requirements
   already happens via the posted issue-comment draft, not a git diff on
   `main`, so this doesn't rework the approval gate at all.
   - Writers updated: `requirements_agent.py`, `create_ado_items.py`.
   - Readers updated to the same branch (explicitly, not via a changing
     default): `design_agent.py` (`requirements.md`), `qa_agent.py`
     (`ado-work-items.json`, in `_resolve_parent_story_id()`).
   - Not affected: `implementation_coordinator.py`/`deploy_agent.py`'s reads
     of `design.md`/`openapi.yaml`/`tasks.md` — those still land on `main`
     for real, via a human-reviewed PR, exactly as before.
   - Verified without spending on a real Requirements/Design run or filing
     duplicate ADO items: `create_ado_items.py --dry-run` still creates real
     ADO work items (no dry-run mode exists on ADO's side) and
     `requirements_agent.py --dry-run` never reaches its `commit_files()`
     call at all — so neither flag actually exercises the changed branch
     name. Verified the real mechanism directly instead: read both files
     from `pipeline-state` (confirmed inherited correctly from `main` at
     branch-creation), then round-tripped a no-op write via `commit_files()`
     against `pipeline-state` and confirmed the content came back
     byte-identical — proves the full blob→tree→commit→ref-update chain
     works against the new branch.
   - Commit `780a93f` on `main`.
4. Protection re-applied cleanly (payload above) once the conflict no longer
   existed, and read back via a fresh `GET` (not trusted from the `PUT`
   response) to confirm no `bypass_pull_request_allowances` leaked in from
   the earlier rejected attempts.

**Not done:**
- A real end-to-end agent run through the new dispatch path (see above) —
  requires an actually-open PR, not yet created.

---

### Step 4.10 — Implementation recovery (DRYRUN-2026-01, cross-session)

Step 4.10 is a full pipeline dry-run exercising Stages 0–6 end-to-end against
a fresh intake (request-id `DRYRUN-2026-01`, tracking issue `forge-template#4`),
being driven from a separate/parallel session. This section documents only
what happened in *this* session: recovering a stalled Implementation
Coordinator run and verifying the result. Confirmed with Mike 2026-08-10 that
`DRYRUN-2026-01`/issue #4 are real and simply hadn't been written back here
yet — the other session's full Step 4.10 status (Intake/Requirements/Design
that presumably preceded this, and QA/Security/Deploy that follow it) lands
here separately when that session concludes.

**A distinct root cause from REQ-2026-01's incident, sharing only the recovery
principle.** REQ-2026-01's earlier incident (see the `implementation_coordinator.py`
entry above) was the *local* process/tracker getting killed mid-flight by the
invoking shell tool's own timeout, while the remote Managed Agents session kept
working independently. Today's failure was different: the
`03-implementation.yml` Actions job ran to completion and explicitly failed —
`managed_agents_wrapper.py`'s session-archive step exhausted its fixed 3-attempt
exponential-backoff retry (2s/4s/8s) and gave up while Test Writer was still
legitimately still working underneath. The top-level coordinator had already
reported `idle`/`end_turn`, but a subagent thread was still active, so the
archive call kept hitting the same "still running" rejection until the retry
budget ran out — a genuinely slow-but-healthy session, not a killed process.
The Managed Agents session itself reached real `idle` shortly after. Per the
standing rule from REQ-2026-01, the recovery principle still applies even
though the trigger differs: resume by reusing the known session ID, never
re-invoke the coordinator.

**Recovery script: `resume_implementation.py`** (repo root, one-off — not a
permanent module), hardcoding the IDs recovered from the failed job's log:
`session sesn_01XefEai7XEyGBgAMDxUJh3u`, coordinator `agent_01VMj1F7w1tsRe8wqQXjGcoc`,
environment `env_01TkNm9Xy5z5ANEVwopaRViR`, 3 subagents. It re-runs only the
tail end `run_implementation_coordinator()` would have: download the
already-produced archive → extract → `create_branch()`/`commit_files()` →
`open_pr()` → `post_comment()` → `archive_session()`.

**Run verified 2026-08-06:**
- Extracted 24 files from a 15,072-byte archive under
  `services/DRYRUN-2026-01/` — a minimal .NET health-check API
  (`HealthController`, `HealthCheckResponse`) + xUnit tests + Next.js
  frontend, consistent with a deliberately small dry-run scope (vs.
  REQ-2026-01's full DocumentApi/EmailWorker pair)
- Committed to new branch `feature/DRYRUN-2026-01` (SHA `f99d2a01`) in
  `forge-demo-apps`
- Draft **PR #10** opened: "FORGE Implementation: DRYRUN-2026-01"
- Comment posted to tracking issue `forge-template#4`
- Session, environment, coordinator, and all 3 subagents archived cleanly —
  no lingering billed resources, no fallback warning path triggered

**PR #10 spot-checked against a real local checkout:** fetched
`feature/DRYRUN-2026-01` into `forge-demo-apps-clone` (same local clone used
for QA/Security's manual runs) and ran `dotnet test` directly against
`services/DRYRUN-2026-01/backend.tests` — **3/3 passed, 0 failed**
(`HealthCheckApi.Tests.dll`). Confirms the resumed archive's backend content
actually builds and its tests actually run, not just that the commit
succeeded.

**Not exercised in this session:** QA/Security/Deploy stages for
`DRYRUN-2026-01`, the frontend unit, and whatever Stage 0–2 work in the other
session preceded this Implementation step. Full Step 4.10 status to be
written back by that session when it concludes.

### qa_agent.py — backend test directory resolution fix (found via DRYRUN-2026-01)

**Root cause:** `_run_backend_tests()` hardcoded the backend test directory
as `services/<request-id>/backend` — the API project's own folder — rather
than the actual xUnit test project's location. Test Writer correctly places
tests in a sibling folder (e.g. `backend.tests/`); neither Document 3 nor
Document 7 mandates a specific layout, so the hardcoded path was simply
wrong, not an enforcement of a documented convention.

**Symptom:** the QA Agent reported "test suite failed to run (build/compile
error)" for a backend suite that actually passes cleanly — confirmed via a
local `dotnet test` run: 3/3 passed.

**Fix:** added `_resolve_backend_test_dir()`, which globs for the actual
`*.Tests.csproj` file under the service root instead of assuming a fixed
path. Warns (but proceeds) if multiple are found. **Superseded 2026-08-10 by
the Phase 5 pre-flight Fix 3 below: "no test project found" now resolves to
`not_applicable`, not a fall-back-and-fail.**

**Verification:** re-ran QA against PR #10 after the fix — backend suite
came back `ran: true`, 3/3 passed.

**Committed and pushed to `main`:** `e2a123eb45476e501dfca0e0b628297a3f4153f2`.

**Open follow-up, not yet done:** this may also be the root cause of
REQ-2026-01's long-standing, previously-undiagnosed "QA backend TRX report
failure" — worth checking that repo's structure against this same pattern to
confirm, but not verified yet. **Update 2026-08-10: re-ran QA `--dry-run`
against REQ-2026-01's real local checkout while verifying Fix 3 below —
backend suite ran cleanly (62/62 passed), no TRX report failure reproduced.**
Not conclusively "closed" (a single clean run isn't the same as a root-cause
diagnosis of what the original undiagnosed failure actually was), but it did
not recur.

---

### Phase 5 pre-flight fixes (per `docs/FORGE-Phase5-Preflight-Fixes-Spec.md`)

Three fixes made ahead of Phase 5's real App 1 ("Inactive User & License
Auditor") run, per the spec drafted in Claude.ai chat 41. All three verified
individually and committed separately, per the spec's own standing
convention. `docs/FORGE-Phase5-Preflight-Fixes-Spec.md` is the source
document — this section records only what actually happened running it, not
a restatement of the spec itself.

**Fix 1 — Managed Agents archive-retry backoff
(`core/agents/utils/managed_agents_wrapper.py`).** Root cause (DRYRUN-2026-01
Stage 3 incident, already documented above): `archive_session()` trusted
only the coordinator's own idle/end_turn signal, with a 3-attempt (~14s)
retry-with-backoff as the sole cushion — too thin when a subagent thread is
still legitimately running under an idle coordinator.

- Added `_get_thread_statuses()` (lightweight `GET /sessions/{id}/threads`,
  no per-thread event fetch) and `_wait_for_subagent_threads_idle()`, called
  as a new step 0 inside `archive_session()` before the archive call is even
  attempted. Polls every 5s for up to 120s; returns immediately once every
  thread reports idle, or immediately (with a warning) if the API doesn't
  expose a thread status field at all — degrading cleanly to the backoff
  loop as the sole safety net in that case.
- Widened `_ARCHIVE_RETRY_ATTEMPTS` from 3 to 6 (same 2×-doubling schedule:
  2s/4s/8s/16s/32s/64s, ~126s total) as the secondary safety net for the
  separate idle→running race — unchanged from before, just given more room.
- Each 400 retry now logs the actual per-thread statuses observed at that
  attempt (not just "still running"), per the spec's explicit ask.
- **Resolved the spec's open design fork:** confirmed live via
  `smoke_managed_agents.py` (10/10 passed) that
  `GET /v1/sessions/{id}/threads` DOES expose a real, usable `status` field
  ("idle") on both coordinator and subagent thread objects — this was
  "not confirmed in current docs" per the spec, and now is. The
  still-busy/retry-logging code paths themselves were not exercised by this
  run (the smoke test's subagent finished before the coordinator went idle,
  so the pre-check found everything already idle on its first poll) —
  reasoned through rather than reproduced under load; no incident has
  surfaced to force the busy path deterministically.
- Committed separately: `cab6995`.

**Fix 2 — `security-check` permanently unsatisfiable on design-stage PRs
(`forge-demo-apps`).** Root cause (already documented in the Phase 4
section above): `main`'s branch protection requires `security-check` on
every PR, but only `feature/*` PRs ever trigger it via
`notify-forge.yml`/`05-security.yml`. `design/*` PRs sit "Waiting for status
to be reported" forever.

- Added `.github/workflows/design-pr-security-noop.yml` in
  `forge-demo-apps` — triggered on `pull_request` (`opened`, `synchronize`),
  guarded to `design/*` branches both at the job-level `if:` and again via an
  explicit shell case-statement inside the job (fails loudly, not silently,
  if that inner check is ever reached on a non-`design/*` ref). Creates a
  `security-check` check run with `conclusion: success` and a summary that
  explicitly states this is a no-op, not a real scan, using the same
  `actions/create-github-app-token@v3` pattern `notify-forge.yml` already
  uses (Checks: Write permission already granted, no new grant needed).
- **Had to be pushed via Mike's own `gh` credentials (workflow scope), not
  the FORGE App's installation token** — `commit_files()` 403'd against
  `.github/workflows/*` for the same reason `notify-forge.yml` originally
  needed manual push: the App has no `workflows` permission. Branch
  `fix/design-pr-security-noop` created via the App token (that part is a
  normal branch, not a workflow file), the workflow file itself written via
  `gh api ... --method PUT` under Mike's own token, then draft **PR #11**
  opened via the App token (opening a PR doesn't need `workflows` either).
  Left open, unmerged, pending Mike's review at the time this fix was built —
  matches the existing PR #7/#8 "small mechanical fix, agent doesn't merge
  its own PR" pattern (ADR-0009). **Merged 2026-08-11 in a follow-up
  session — see the PR #11 merge entry below.**
- **Verified live** with a throwaway `design/fix2-smoketest` branch/PR
  (branched from `fix/design-pr-security-noop` so the new workflow file was
  actually present in the head ref — a `design/*` branch cut from `main`
  alone would not have picked it up yet, since `main` won't have the file
  until PR #11 merges): `security-check` check run appeared within ~20s,
  `conclusion: success`, with the intended "design-stage PR — not a real
  scan" summary text. PR's `mergeable_state` was `blocked` only on the
  still-intact required-review gate, not on the status check. Throwaway PR
  closed and branch deleted immediately after verification — nothing left
  behind in `forge-demo-apps` from the test itself.
- Re-read `main`'s branch protection after all of the above: `checks`,
  `allow_force_pushes`, `allow_deletions` all unchanged from before this
  fix's own work.
- **Flagging, not fixing, a pre-existing discrepancy found while re-checking
  protection per the spec's own acceptance criteria:** live
  `enforce_admins.enabled` is currently `false`. This directly contradicts
  what Step 4.8 (Phase 4 section, above) documented as confirmed —
  `enforce_admins: true`. Nothing in this session's own work touched
  `enforce_admins` (confirmed by checking it both before and after Fix 2's
  changes — `false` both times). Best guess: this is a side effect of
  whatever admin action was used to force-merge the `DRYRUN-2026-01` design
  PR past the then-unsatisfiable `security-check` gate — an admin-merge
  override on a single PR shouldn't normally touch the persistent protection
  setting, but something did, and it wasn't this session. **Not restored
  here** — a branch-protection setting is shared infrastructure and the spec
  explicitly asks to surface exactly this kind of thing rather than resolve
  it silently. Mike should decide whether to flip it back to `true` (closing
  the gap `enforce_admins: true` was originally meant to close) now that
  Fix 2 removes the reason an admin bypass was needed in the first place.

**Fix 3 — QA Agent `not_applicable` outcome
(`core/agents/qa_agent.py`).** Root cause: `_run_frontend_tests()` assumed
every service has a real Jest setup; a backend-only service (e.g.
`DRYRUN-2026-01`, no `"test"` script in `package.json`) got reported as a
hard failure identical in shape to a genuinely broken suite, burning the
full 3-attempt retry budget on a non-issue (this is what actually forced the
manual `qc-retry-limit-reached` → `qa-approved` override on
`DRYRUN-2026-01` that the Phase 4 write-up alludes to).

- `TestSuiteResult` gained a `not_applicable: bool` field — a real third
  outcome, not a variant of pass or fail. Never counts against the retry
  budget, never files an ADO Bug, reported plainly in the PR comment
  ("Not applicable — no test suite in scope for this service").
- New `_frontend_test_script_exists()` checks for a `package.json` with a
  non-empty `"test"` script before ever invoking `npm test`.
- `_resolve_backend_test_dir()` changed to return `(None, warning)` — not a
  guessed fallback path — when no `*.Tests.csproj` exists anywhere under the
  service root at all, so "no test project exists" no longer falls through
  to the old hardcoded-path-then-fail behavior described in the entry above
  this one.
- `suite_run_failed` / `tests_pass` / the synthetic "suite failed to run" bug
  filing loop all updated to treat `not_applicable` suites as excluded from
  the verdict entirely, not as failures.
- Scoped deliberately to inference from what's on disk, per the spec — not
  the more thorough explicit in-scope/out-of-scope declaration from
  `design.md`/a manifest field, which is logged in `_frontend_test_script_exists()`'s
  own docstring as a real future enhancement requiring a Design Agent change.
- **Verified against two real local checkouts** (`forge-demo-apps-clone`,
  `--dry-run`, real `dotnet test`/`npm test`, real Claude write-up call — no
  GitHub/ADO calls in dry-run mode):
  - `DRYRUN-2026-01` (backend-only): frontend → `not_applicable`, backend →
    3/3 real pass, `qa-approved` on attempt 1 of 3 — not `qa-loop-back`
    against a phantom frontend failure.
  - `REQ-2026-01` (both suites in scope, re-verified for regression): backend
    62/62 pass, frontend 6 genuine failures correctly detected and bugs
    computed, `qa-loop-back` on attempt 1 of 3 — confirms `not_applicable`
    logic doesn't fire when a suite is actually in scope, and doesn't change
    behavior for a suite that's in scope and genuinely failing.
- Committed separately: `0560b39`.

**Not done this session, per the spec's own scoping:** `FORGE-context_v42.md`
is intentionally not updated here — that's the Claude.ai chat's job at the
close of this mini-cycle, per the standing two-tool convention. Also not
done: deciding the `enforce_admins` question above, and a root-cause (not
just non-reproduction) diagnosis of REQ-2026-01's original "QA backend TRX
report failure."

---

### PR #11 merge (Fix 2 cleanup, 2026-08-11 follow-up session)

Single-purpose follow-up to the Phase 5 pre-flight fixes session above:
merge PR #11 (the `design/*` `security-check` no-op workflow) into `main` on
`forge-demo-apps`. No Phase 5 work started in this session.

- **Re-verified before merging, not assumed unchanged:** pulled the live PR
  #11 diff and byte-diffed it against the exact file content verified last
  session — identical, no drift (trigger filter, in-job branch-prefix guard,
  and the check-run summary text distinguishing this from a real Security
  Agent pass were all still intact).
- **Confirmed the throwaway verification PRs were actually cleaned up**:
  both PR #12 (the first, mis-based attempt) and PR #13 (the one that
  actually verified the fix) show `state: closed`; branch
  `design/fix2-smoketest` returns 404 (deleted). No leftover test artifacts.
- **Merged PR #11** — merge commit
  `2e00e3f3c3dbda2723349b8127233bb473eddc9c`. Required an admin-privilege
  merge (`gh pr merge --admin`): PR #11's own head branch
  (`fix/design-pr-security-noop`) is not itself `design/*`, so the new
  workflow's own job-level guard correctly skipped on this PR and never
  produced a `security-check` run for it — a one-time bootstrapping
  limitation of this specific fix (it can't satisfy its own required check
  on the branch that introduces it), not a bypass of the review/scan
  requirement it exists to enforce for `design/*` PRs going forward. Zero
  reviews were also present at merge time. `enforce_admins: false` (see
  above) is what made the admin override possible at all.
- **Re-verified branch protection on `main` immediately after merge**, fresh
  `GET`, not trusted from any cached state: `required_status_checks.checks`
  = `[{"context":"security-check","app_id":4388813}]` (unchanged),
  `enforce_admins.enabled` = `false` (unchanged — expected and accepted per
  this session's brief, not something this session touched or was asked to
  touch), `allow_force_pushes`/`allow_deletions` both `false` (unchanged).
  Nothing changed as a side effect of the merge itself.
- Confirmed `.github/workflows/design-pr-security-noop.yml` is now present
  on `main` (blob sha `622d3bc3...`, matching the blob created when the file
  was first written to the fix branch — content didn't change in transit).
- **Not done, deliberately out of scope for this cleanup task:** the
  `enforce_admins` question flagged above is still Mike's open call, not
  decided or changed here.
- **Follow-up, same session:** merged branch `fix/design-pr-security-noop`
  (tip `148099a7...`, confirmed matching PR #11's merged head before
  deleting) removed via `DELETE /git/refs/heads/fix/design-pr-security-noop`
  at Mike's explicit request, confirmed gone via a follow-up 404 on the
  branch lookup.

---

