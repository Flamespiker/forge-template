# Platform Swap: forge-demo-apps → Mike Digital Platform (mdp) — 2026-09-04

Full verbatim narrative for the platform swap summarized in `CLAUDE.md`'s Current
Build Phase section. Executed following `docs/FORGE-platform-swap-runbook.md` in a
single Claude Code CLI session, with explicit human sign-off before every
irreversible action.

## Phase A — Decommission

**A.1 Investigation (read-only) findings:**

- `forge-build-rg` (canadacentral) contained: `forgedemoacr` (ACR), `forge-staging`
  (Container Apps env, hosting 5 live apps — `req-2026-01-document-api`,
  `req-2026-01-email-worker`, `req-2026-01-frontend`, `req-2026-03-frontend`,
  `req-2026-03-on-call-rost-5bb949`), `forge-production` (Container Apps env,
  confirmed **empty**, zero apps — never used), `forge-build-kv` (Key Vault),
  `forge-req2026-03-pg` (Postgres Flexible Server, confirmed `Stopped`), and two
  auto-generated Log Analytics workspaces.
- Two Azure AD app registrations found, materially different in kind:
  - `FORGE-DemoApps-SSO` (`b59886c1-12ac-42c1-895f-5fafa8e57318`) — the real
    target-app sign-in registration, confirmed live-referenced by both REQ-2026-03
    Container Apps' env vars (`AZURE_AD_CLIENT_ID`/`AzureAd__ClientId` etc.). One
    secret (`req-2026-03-deploy`, expires 2027-02-14).
  - `forge-deploy-staging` (`be88677c-8a01-4968-b3c9-d153f64efe26`) — the CI/deploy
    service principal `deploy_agent.py` authenticates as. Confirmed via
    `az role assignment list` to be scoped to exactly `forge-build-rg` (Contributor)
    + `forge-build-kv` (Key Vault Secrets Officer) — a FORGE-mechanism resource, not
    target-app data.
- ADO project `FORGE-Build`: wellFormed, 153 work items. Delete-permission check via
  PAT against the Graph API 401'd — consistent with the runbook's own expectation
  that a scoped PAT usually can't confirm this.
- `forge-demo-apps` GitHub repo: private, branch protection live on `main`
  (`security-check` required status check app_id 4388813, 1 approving review,
  `enforce_admins: true`). 45 issues/PRs total, **all closed** — nothing open would
  be lost. The FORGE App installation (id `148876680`) covers **both**
  `forge-template` and `forge-demo-apps` under one "selected" installation.
- `forge-template` secrets/variables touching the old platform: `FORGE_TARGET_REPO`
  and `ACR_LOGIN_SERVER`/`ACR_USERNAME`/`ACR_PASSWORD` (needed rotation);
  `FORGE_ADO_ORG_URL`/`FORGE_GITHUB_OWNER`/`ADO_PAT` unaffected (same org/owner,
  only the ADO project changed); `AZURE_STAGING_CREDENTIALS` (the
  `forge-deploy-staging` SP) kept, needed new role assignments only.

**A.2 Sign-off (three explicit decisions from Mike):**
1. Confirmed OK to take down the 5 live Container Apps immediately as part of the
   RG deletion.
2. `forge-deploy-staging` SP: **keep and re-scope** to the new RG/KV, not delete —
   it's FORGE's own deploy mechanism, not old-platform data.
3. ADO project `FORGE-Build`: Mike opted to handle this himself rather than have
   Claude Code CLI attempt delete-or-archive via API (his own PAT check suggested
   he had the necessary write scope). Confirmed independently later (Phase B) that
   he genuinely hard-deleted it — `GET .../projects/FORGE-Build` returned
   `TF200016: project does not exist`, not a rename.
4. Separate explicit confirmation obtained for the exact A.3 deletion list (SSO app
   registration + `forge-build-rg` + `forge-demo-apps` repo) before executing any
   of it, per the runbook's "explicit go-ahead per irreversible action" rule.

**A.3 Execution — all three confirmed complete via live follow-up reads:**
- `az ad app delete --id b59886c1-...` → confirmed gone (`az ad app show` errors
  "does not exist").
- `az group delete --name forge-build-rg --yes --no-wait` → confirmed gone
  (missing from `az group list`) — cascaded the ACR, both CA environments, 5 live
  apps, Key Vault, Postgres server, and Log Analytics workspaces in one operation.
- `gh repo delete Flamespiker/forge-demo-apps --yes` → initially blocked (`gh`
  token lacked the `delete_repo` scope, a separate scope from `repo`/`admin`).
  Mike ran `gh auth refresh -h github.com -s delete_repo` (interactive device-code
  flow, approved in browser), then the delete succeeded and was confirmed via
  `gh repo view` returning 404.

## Phase B — Provision

**B.1 Naming worksheet (Mike's values, all pre-checked for availability):**

| Item | Value |
|---|---|
| Platform slug | `mdp` |
| GitHub target repo | `mike-digital-platform` (private) |
| Azure resource group | `mdp-rg` |
| Container Apps env (staging) | `mdp-con-stage` |
| Container Apps env (production) | `mdp-con-prod` |
| ACR name | `mdpacr` (checked via `az acr check-name` before creating) |
| Key Vault name | `mdp-kv` (checked via `az keyvault check-name` before creating) |
| ADO project name | `Mike Digital Platform` (checked against the org's existing
  project list before creating — no collision) |

**B.2 Provisioning — all confirmed live:**
- `mdp-rg` created (canadacentral, matching the old platform's region).
- `mdpacr` created (Basic SKU, admin user enabled).
- `mdp-kv` created (RBAC-authorization mode, not access-policy mode).
- `mdp-con-stage` / `mdp-con-prod` Container Apps environments created (each
  auto-generated its own Log Analytics workspace, matching the old platform's
  pattern).
- `Flamespiker/mike-digital-platform` GitHub repo created (private).
- ADO project "Mike Digital Platform" — **blocked via API** (`POST
  .../_apis/projects` 401'd; the `ADO_PAT` has read access but not
  project-creation scope, confirmed by the earlier successful read-only project
  list call succeeding under the same PAT). Mike created it manually in the
  `spike99` org; confirmed live afterward via the projects list.

**B.3 Repointing `forge-template` — all confirmed live:**
- GitHub App installation repo-add **could not be done via API**
  (`PUT /user/installations/{id}/repositories/{repo_id}` → 403 "You do not have
  permission to modify this app on Flamespiker" — this endpoint needs a different
  auth scope than a plain PAT/OAuth token provides). Mike added
  `mike-digital-platform` manually via
  `https://github.com/settings/installations` → Configure → Repository access.
  Confirmed afterward via the installation token's `/installation/repositories`
  listing both `forge-template` and `mike-digital-platform`.
- `FORGE_TARGET_REPO` variable updated to `mike-digital-platform` (`gh variable
  set`), confirmed via `gh variable list`.
- Fresh ACR credentials pulled (`az acr credential show --name mdpacr`) and
  `ACR_LOGIN_SERVER`/`ACR_USERNAME`/`ACR_PASSWORD` secrets rotated in
  `forge-template`, confirmed via `gh secret list` timestamps.
- `team/config.yaml` updated: `ado.project`/`ado.area_path` →
  `"Mike Digital Platform"`; `container_apps.staging.environment`/
  `.resource_group` → `mdp-con-stage`/`mdp-rg`. Committed directly to `main`
  (confirmed unprotected) as commit `f17d307`, confirmed landed via the GitHub
  Contents/Commits API (not just a local `git log` check).
- `forge-deploy-staging` SP re-scoped: `Contributor` on `mdp-rg`,
  `Key Vault Secrets Officer` on `mdp-kv`, via `az role assignment create`.
- Mike separately updated his own local `.env` (`FORGE_TARGET_REPO`, `ACR_*`) —
  confirmed correct by Claude Code CLI on request, matching the rotated repo
  secrets exactly.

**Tooling gotcha hit twice this session, worth remembering:** Git Bash's MSYS path
conversion silently mangles any CLI argument that looks like a POSIX absolute path
— `az role assignment create --scope "/subscriptions/.../resourceGroups/mdp-rg"`
failed with a nonsensical `MissingSubscription` error until run with
`MSYS_NO_PATHCONV=1` prefixed. The exact same class of bug had already surfaced
earlier in this same session as `gh api /app/installations` reporting "invalid API
endpoint" because bash rewrote the leading slash into a Windows path. Any future
`az`/`gh api` call taking a leading-slash argument on this machine should be run
with `MSYS_NO_PATHCONV=1` from the start, not discovered by a confusing error again.

## Post-swap verification checklist — all items confirmed

- Old resource group, app registration, GitHub repo, ADO project: all confirmed
  gone via live reads (not assumed from "the command returned success").
- New resource group, environments, ACR, Key Vault, ADO project, GitHub repo: all
  confirmed to exist via live reads.
- GitHub App installation confirmed to include the new target repo.
- `FORGE_TARGET_REPO` variable and `team/config.yaml` commit both confirmed live
  via API, not just locally.
- ACR credentials confirmed rotated (secret update timestamps).
- **Real (non-dry-run) pipeline smoke test**: `verify-setup.yml` run
  `33829563278` on `main`, triggered via `workflow_dispatch`. Fully green. Log
  inspection (not just the pass/fail summary) confirmed the run genuinely
  resolved the new platform live: the GitHub App token step logged
  `repositories: mike-digital-platform` (pulled from `${{ vars.FORGE_TARGET_REPO
  }}`), "Confirm GitHub App can read the target repo" succeeded against the new
  repo, "Confirm ADO connectivity" reported 9 projects visible in
  `https://dev.azure.com/spike99` (including the new "Mike Digital Platform"),
  and the Anthropic API key check passed independently.

## What's next for this platform

`mike-digital-platform` is an empty repo — no code, no Stage 0-6 history. Per the
runbook's cost note, the new Container Apps environments and ACR sit at effectively
zero cost with nothing deployed. The next real step is Build Plan Phase 1-2's normal
first-app flow (intake spreadsheet → `intake-ready` label) whenever Mike is ready to
build something on the new platform — this session's scope was the swap itself, not
standing up a first app.
