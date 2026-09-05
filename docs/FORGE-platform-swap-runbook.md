# FORGE Platform Swap Runbook

**Purpose:** decommission an old FORGE target platform (monorepo + its Azure/ADO
footprint) and stand up a new one, while leaving `forge-template` (the
orchestration engine) untouched. This is the "keep the forge, change the app"
pattern — you're not cloning `forge-template` again, just repointing it at a
new target.

**When to use this:** you're retiring an old app/monorepo and its
infrastructure and starting a new one under a new name, using the same
FORGE orchestration instance.

**Not for:** standing up a genuinely *second, independent* FORGE instance
(a separate clone of `forge-template` via "Use this template", with its own
GitHub App installation, its own secrets, its own everything). That's a
different, simpler process — see Doc 6 (Orchestration Manager Guide),
Build Plan Phase 1–2.

---

## Before you start: conventions this runbook assumes

- **Two-tool split:** the human + a strategy assistant (e.g. Claude.ai) own
  planning, naming decisions, and confirming what's safe to delete. A live
  execution tool (e.g. Claude Code CLI) owns the actual `az`/`gh`/ADO API
  calls. Neither substitutes for the other — don't let an execution tool
  make naming or scope decisions, and don't hand-execute steps a live tool
  can verify more reliably.
- **Investigation before deletion, always.** Never delete based on what a
  doc *says* exists — confirm live, via API, immediately before acting.
  Docs and memory go stale; live resource lists don't.
- **Explicit go-ahead per irreversible action.** Deleting a resource group,
  an app registration, a repo, or an ADO project are all one-way doors.
  Get a human's explicit yes on the *confirmed* list, not the assumed one,
  before executing.
- **Real verification after every step**, not "the command returned
  success." Long-running deletes (resource groups especially) return a
  202 Accepted immediately — poll until the resource is actually gone
  before treating the step as done.
- **CLI has direct tool access for investigation.** Your execution tool
  (e.g. Claude Code CLI) should be given working `az`, `gh`, and ADO REST
  API access (via PAT) before running Phase A.1. This means the "old
  platform" placeholders below (`<OLD_RESOURCE_GROUP>`,
  `<OLD_APP_REGISTRATION>`, `<OLD_REPO>`, etc.) do **not** need to be
  filled in from memory or docs first — the investigation prompt is
  written so the execution tool *discovers* and reports the real names
  live, which then becomes the confirmed list for A.2 sign-off. Only the
  **new platform** names (Phase B.1) are a naming/scope decision the human
  and strategy assistant make deliberately — those aren't something to
  discover, so fill in that worksheet before generating B.2/B.3 prompts.

---

## Phase A — Decommission the old platform

### A.1 — Investigate first (read-only, no deletions)

Give your execution tool an investigation-only pass before any decision is
made. This assumes the tool already has working `az`, `gh`, and ADO REST
API (PAT) access — no placeholder names need to be supplied up front,
since the whole point of this pass is for the tool to discover and report
the real, current names and IDs rather than working from assumed ones.
Example prompt:

> Investigate and report back the exact current live state of everything
> below. Do not delete, modify, or provision anything in this pass.
>
> 1. **Azure resource group `<OLD_RESOURCE_GROUP>`**: list every resource
>    inside it (name, type, location). Confirm whether things you'd expect
>    to be co-located (registry, database, Key Vault) actually are, or are
>    split across resource groups — don't assume they're all in one place.
> 2. **Any Azure AD app registration(s)** used for application sign-in:
>    confirm they still exist, list active secrets/certs, and check what
>    *currently running* resources reference their client ID (check live
>    Container App / App Service configs directly, not just docs).
> 3. **ADO project** being retired: list work item counts by type, and
>    confirm whether your account has actual delete permission on the
>    project (Organization Settings → Overview → is "Delete" present, not
>    just "Rename"?) — this usually can't be confirmed via a
>    narrowly-scoped PAT, so say so plainly if you can't check it rather
>    than guessing.
> 4. **GitHub repo(s)** being retired: confirm branch protection state,
>    confirm exactly which repos the relevant GitHub App installation
>    covers (an installation can span multiple repos — check this
>    precisely, don't assume "installed on repo X" means "scoped to repo
>    X only"), and list open PRs/issues that would be lost.
> 5. **Secrets/variables currently in the orchestration repo**: list names
>    only (not values) of what's referencing the old platform, and confirm
>    which are stored as secrets vs. plain variables.
>
> Report back findings only. Nothing gets deleted until this is reviewed.

### A.2 — Review findings and get explicit sign-off

Before executing anything, confirm with the human:
- Any *live, currently-working* thing (auth, a running app) that will break
  immediately — get an explicit yes on that specifically, not just a
  blanket "delete everything."
- Whether the ADO project can be hard-deleted or only renamed/archived —
  if delete permission isn't confirmed, plan for rename-and-archive as the
  fallback (e.g. rename to `<OLD_NAME>-ARCHIVED`) rather than blocking on
  it.
- The exact resource list, not a remembered or assumed one.

### A.3 — Execute the decommission

Example prompt once sign-off is given:

> Execute the decommission below. Verify each deletion via a live
> follow-up read (404 / not-found) — don't report done on an initial
> "accepted" response for long-running operations like resource group
> deletion; poll until it's actually gone.
>
> 1. Delete Azure AD app registration `<OLD_APP_REGISTRATION>`. Confirm
>    gone via a follow-up read.
> 2. Delete resource group `<OLD_RESOURCE_GROUP>` in full
>    (`az group delete --name <OLD_RESOURCE_GROUP> --yes`) — this cascades
>    everything inside it in one operation. Poll until complete.
>    Note: Key Vault soft-delete may reserve the vault's name for a
>    retention window afterward — irrelevant if the new vault gets a
>    different name; otherwise you may need an explicit purge.
> 3. Delete GitHub repo `<OLD_REPO>` entirely.
> 4. Delete-or-archive the ADO project: attempt a real delete via the ADO
>    REST API; if it 403s, fall back to renaming to `<OLD_NAME>-ARCHIVED`.
>    Report which path was taken.

---

## Phase B — Provision the new platform

### B.1 — Naming worksheet

Fill this in with the human before generating any prompts — Azure naming
rules are strict and vary by resource type, so confirm the slug fits all
of them before committing to it:

| Item | Naming rule | Your value |
|---|---|---|
| Platform slug | short, lowercase | |
| New GitHub target repo | lowercase, hyphens OK | |
| New Azure resource group | lowercase, hyphens OK | |
| New Container Apps environments (staging/prod) | lowercase, hyphens OK | |
| New ACR name | **alphanumeric only, no hyphens**, globally unique across Azure | |
| New Key Vault name | alphanumeric + hyphens, globally unique across Azure | |
| New ADO project name | org-unique | |

### B.2 — Provision

Example prompt:

> Provision the new platform infrastructure:
>
> 1. Create resource group `<NEW_RESOURCE_GROUP>` (same region as before,
>    unless directed otherwise).
> 2. Create two Container Apps environments in it via
>    `az containerapp env create` (prefer CLI over the Azure Portal — the
>    Portal has no standalone "create environment" option and requires a
>    throwaway placeholder app; the CLI creates the environment directly):
>    `<NEW_STAGING_ENV>`, `<NEW_PRODUCTION_ENV>`.
> 3. Create ACR `<NEW_ACR_NAME>` in the new resource group — confirm name
>    availability first (globally unique).
> 4. Create Key Vault `<NEW_KV_NAME>` in the new resource group — confirm
>    name availability first.
> 5. Create ADO project `<NEW_ADO_PROJECT>` in the existing org.
> 6. Create GitHub repo `<NEW_TARGET_REPO>` (confirm public/private with
>    the human before creating).
> 7. **Seed the new repo — do not skip this.** A repo created via the API/UI
>    with no template and no initial commit has zero commits and zero
>    branches (`GET .../commits` returns `409 Git Repository is empty`).
>    FORGE's `commit_files()` (used by the Requirements, Design, QA, and
>    Security agents) writes via the Git Data API — blob → tree → commit →
>    ref update — which requires an existing base commit/tree to build on;
>    against a genuinely empty repo it fails outright the first time any
>    stage tries to write to it. Confirmed live 2026-09-04 during the
>    `mike-digital-platform` swap (see `CLAUDE.md` Open Item #45) — this
>    step didn't exist in the runbook at the time, and the gap wasn't caught
>    until a real Stage 1 run failed against the new target days later.
>    Two sub-steps:
>    a. Push an initial commit to `main` (a README is enough) — e.g. via the
>       Contents API: `PUT /repos/{owner}/{repo}/contents/README.md` with
>       `branch: "main"`.
>    b. Create the `pipeline-state` branch (FORGE's dedicated, permanent,
>       intentionally-unprotected bookkeeping branch — created once, reused
>       across every request) pointing at that same initial commit, via the
>       Git Refs API: `POST /repos/{owner}/{repo}/git/refs` with
>       `ref: "refs/heads/pipeline-state"` and `sha: <main's HEAD sha>`.

### B.3 — Repoint the orchestration repo

This is FORGE-specific: only two blocks in `team/config.yaml` are actually
read at runtime (`ado:` and `container_apps.staging` — confirm this is
still accurate against the live file before assuming it, config.yaml has
drifted before). The target repo identity itself lives in repo
**Variables**, not config.yaml.

Example prompt:

> Repoint the orchestration repo (`<FORGE_REPO>`) at the new platform:
>
> 1. Check whether the existing GitHub App installation already covers
>    multiple repos as one installation (common pattern: the orchestration
>    repo needs App-token access to itself for anti-recursion reasons). If
>    so, add `<NEW_TARGET_REPO>` to that *same* installation's repository
>    access rather than creating a new installation. If this can't be done
>    via API with current credentials, stop and provide the exact GitHub
>    UI path instead of guessing.
> 2. Update repo variable `FORGE_TARGET_REPO` → `<NEW_TARGET_REPO>`. Leave
>    `FORGE_GITHUB_OWNER`/`FORGE_ADO_ORG_URL` unchanged unless the org/owner
>    is actually changing too.
> 3. Update `team/config.yaml`: `ado.project`, `ado.area_path` →
>    `<NEW_ADO_PROJECT>`; `container_apps.staging.environment`,
>    `.resource_group` → `<NEW_STAGING_ENV>`, `<NEW_RESOURCE_GROUP>`.
>    Verify against the live file first — don't assume its current schema
>    without checking; it may have changed since this runbook was written.
>    Commit directly (confirm branch protection state first) as its own
>    commit.
> 4. Pull fresh ACR credentials (`az acr credential show`) and update the
>    orchestration repo's `ACR_LOGIN_SERVER`/`ACR_USERNAME`/`ACR_PASSWORD`
>    secrets.
> 5. **Push the cross-repo dispatch workflows to the new target repo — do not
>    skip this.** `notify-forge.yml`, `design-pr-security-noop.yml`, and
>    `ops-pr-security-noop.yml` must exist in `<NEW_TARGET_REPO>`'s own
>    `.github/workflows/` or QA, Security, and Deploy will never fire for any
>    request — silently, with nothing anywhere pointing at why. Confirmed
>    live 2026-09-04: these three files are documented at length in
>    `CLAUDE.md`/the Orchestration Guide, but until that day they only ever
>    lived in the *old* target repo, not `forge-template` itself — a platform
>    swap that deletes the old target repo (Phase A) with no separate backup
>    would have made them unrecoverable. Reference copies now live in
>    `core/templates/target-repo-workflows/` in `forge-template`. Steps:
>    a. Copy all three files from that directory to `<NEW_TARGET_REPO>`'s
>       `.github/workflows/`. **The GitHub App cannot push these itself**
>       (no `workflows` permission) — push via your own git credentials
>       (e.g. the Contents API, `PUT /repos/{owner}/{repo}/contents/
>       .github/workflows/{name}` with `branch: "main"`), not `commit_files()`.
>    b. Edit `notify-forge.yml`'s two `YOUR_FORGE_OWNER`/`YOUR_FORGE_REPO`
>       placeholders to point at `<FORGE_REPO>` — the other two files need no
>       edits (fully self-referential via GitHub Actions' own context).
>    c. Set `FORGE_APP_CLIENT_ID` (variable) and `FORGE_APP_PRIVATE_KEY`
>       (secret) on `<NEW_TARGET_REPO>` itself — repo secrets/variables don't
>       cross repos, so the orchestration repo's copies aren't visible here.
>    d. Confirm the GitHub App installation (already extended to
>       `<NEW_TARGET_REPO>` per step 1 above) covers this repo — the token
>       these workflows generate needs write access to fire the dispatch.
>
> Report back: confirmation each new resource exists, confirmation of the
> App-installation change (or the manual UI path if API couldn't do it),
> the commit SHA for the config change, and confirmation (via a real test PR,
> not just file-existence) that `notify-forge.yml` actually fires a dispatch
> that `forge-template` receives.

---

## Post-swap verification checklist

- [ ] Old resource group confirmed gone (live API read, not assumed)
- [ ] Old app registration confirmed gone
- [ ] Old GitHub repo confirmed gone
- [ ] Old ADO project deleted or renamed+archived (confirmed which)
- [ ] New resource group, environments, ACR, Key Vault all confirmed to
      exist via live reads
- [ ] New ADO project exists
- [ ] New GitHub repo exists, correct visibility
- [ ] **New GitHub repo has an initial commit on `main`** (confirm via
      `GET /repos/{owner}/{repo}/commits` — a `409 Git Repository is empty`
      means this step was skipped)
- [ ] **New GitHub repo has `notify-forge.yml`, `design-pr-security-noop.yml`,
      and `ops-pr-security-noop.yml` in its own `.github/workflows/`**, with
      `notify-forge.yml`'s owner/repo placeholders pointed at the real
      `<FORGE_REPO>` — confirm via `GET /repos/{owner}/{repo}/contents/
      .github/workflows`, not just that the copy step "ran"
- [ ] **New GitHub repo has its own `FORGE_APP_CLIENT_ID` variable and
      `FORGE_APP_PRIVATE_KEY` secret** — these don't cross repos from the
      orchestration repo and must be set separately here
- [ ] **Dependabot alerts + Dependency graph enabled on the new target repo,
      and the `forge-pipeline` App granted `vulnerability_alerts`
      (Read-only) on it** — confirmed live 2026-09-04 (`CLAUDE.md` Open
      Item #50) that this repo-specific prerequisite from the *old* target
      doesn't carry over: Security Agent's Dependabot check `403`'d on the
      new repo until this was redone. Confirm via `GET /repos/{owner}/
      {repo}/vulnerability-alerts` returning `204`, not `404`.
- [ ] **`pipeline-state` branch exists on the new target repo**
      (`GET /repos/{owner}/{repo}/branches` should list it)
- [ ] GitHub App installation includes the new target repo
- [ ] `FORGE_TARGET_REPO` variable updated and confirmed
- [ ] `team/config.yaml` updated and committed; commit SHA confirmed via
      API as landed on the branch Actions actually runs from
- [ ] ACR credentials rotated in orchestration repo secrets
- [ ] **A real (not dry-run) pipeline smoke test run against the new
      target, through Stage 5 (Security) — not just Stage 1 — before
      treating the swap as done.** `verify-setup.yml` alone is *not*
      sufficient — it checks config/connectivity, not that `commit_files()`
      can write to the target repo, nor that the cross-repo dispatch
      workflows actually exist and fire. Confirmed live 2026-09-04, twice,
      on the same swap: a fully-green `verify-setup.yml` run gave false
      confidence while the target repo was still unseeded (`CLAUDE.md` Open
      Item #45, caught at Stage 1), *and separately*, after that was fixed,
      QA/Security silently never fired at all because `notify-forge.yml`
      and its two companion workflows didn't exist on the new target
      (`CLAUDE.md` Open Item #49) — a gap that Stage 1 alone can never
      surface, since it doesn't depend on either workflow. A throwaway
      tracking issue taken through Intake → clarification → Requirements →
      Design → merge → Implementation → a real feature PR is the minimum
      test that exercises both gaps; confirm the feature PR actually shows
      real `qa-approved`/`security-approved` activity (not just that the
      job ran) before closing it out.

## Ongoing cost note

New Container Apps environments with no apps deployed and a fresh ACR with
no images pushed sit at effectively zero cost (scale-to-zero). There's
nothing to manually shut down immediately after provisioning — the real
cost/shutdown discipline kicks in once an actual app is deployed onto the
new platform. Don't forget the standard end-of-deploy-session shutdown
prompt at that point.

---

*This runbook captures the general pattern. Fill in `<PLACEHOLDERS>` with
your specific values each time you run through it — don't copy prior
runs' concrete names forward without re-checking they still apply.*
