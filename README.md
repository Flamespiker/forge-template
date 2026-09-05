# FORGE

**Full-SDLC Orchestration with Review Gates for Engineers**

FORGE is an AI-orchestrated software development lifecycle platform for Legal Aid Alberta. It takes a BA-produced requirements spreadsheet, moves it through a fully staged pipeline (requirements → design → code → QA → security → deploy), and delivers a working application — with humans reviewing and approving at every gate.

Agents do the work. Humans approve the outcomes.

---

## How it works

FORGE is a GitHub template repository. You clone it, configure it for your team, and it orchestrates development work *into* your existing codebase via a GitHub App — your application code never lives here.

The pipeline is event-driven through GitHub Actions. Each stage spins up a Claude agent, produces an artifact, and gates on a GitHub label or PR approval before the next stage begins. The whole pipeline is label-driven — there is no chat/slash-command interface.

```
BA uploads spreadsheet
        ↓
Intake & clarification  (no gate)
        ↓
Requirements            ✅ Review ADO work items, apply requirements-approved label
        ↓
Spec & design           ✅ Approve architecture + API contracts (PR), apply design-approved label
        ↓
Implementation          ✅ Approve + merge the feature PR  (Implementation Coordinator runs Backend, Frontend, Test Writer subagents in parallel)
        ↓
QA + security           ⚙️  Automatic — QA Agent and Security Agent apply their own
                             qa-approved / security-approved labels from real test
                             and scan results (run in parallel); each posts a
                             human-readable report on the PR
        ↓
Deploy                  ⚙️  Automatic — fires once both labels are present AND the
                             feature PR is actually merged to main. Staging only —
                             there is no production deploy stage yet.
```

---

## Prerequisites

Before you start, make sure you have:

- **GitHub** — a repository for your application code (the "target" monorepo) and permissions to create a GitHub App
- **Azure** — an active subscription with permissions to create a Container Apps environment and a Container Registry
- **Azure DevOps** — a project with Boards enabled; a Personal Access Token with Work Items (Read & Write) scope
- **Anthropic API** — a standard Anthropic API key. Stage 3 (Implementation) additionally requires the **Managed Agents beta header** (`managed-agents-2026-04-01`) — this worked directly on a standard personal API key during build-phase testing, with no separate approval step observed, though this may vary by account. All other stages call the standard Messages API and need no beta flags. Opus tier is used for the Stage 3 coordinator; Sonnet tier for everything else.
- **Node.js 20+** and **Docker** installed locally

> **Build phase note:** A personal Anthropic API account and personal Azure subscription are fine for initial setup. Before going to production use of FORGE itself, plan to migrate to your organisation's accounts.

> **Production deploys:** FORGE currently deploys to **staging only**. A production deploy stage (a second, GitHub Environment-gated deploy path with its own service principal) is a known, explicitly out-of-scope gap in the Deploy Agent — not yet built, not stubbed. Don't provision production Azure infrastructure expecting FORGE to use it yet.

---

## Getting started

### 1. Create your FORGE repository (5 min)

Click **Use this template** on GitHub and create a new private repository. This is your team's Orchestration Manager instance — you own and maintain it.

```bash
git clone https://github.com/your-org/your-forge-instance.git
cd your-forge-instance
```

### 2. Create (and seed) your target monorepo, then the GitHub App (10 min)

FORGE authenticates into your target monorepo through a GitHub App — never a personal token.

> **If your target monorepo doesn't exist yet, create it now — and push at least one
> commit to `main` before going further.** FORGE writes files via the GitHub Git Data API
> (`commit_files()`), which builds each commit on top of an existing base tree — it fails
> outright against a genuinely empty repo (0 commits). You also need a dedicated,
> permanent `pipeline-state` branch (created once, reused by every request — Requirements/
> Design/QA/Security all read and write docs there) pointing at that same initial commit:
> ```bash
> git init && git commit --allow-empty -m "Initial commit" && git push origin main
> git push origin main:pipeline-state
> ```
> Skipping this surfaces later as a confusing `commit_files()` 404 the first time a real
> request reaches Stage 1 (Requirements) — not at setup time, when it'd be obvious.

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**
2. Name it `forge-pipeline`
3. Uncheck **Active** under Webhook — FORGE's workflows call APIs directly, no webhook is needed
4. Set these **Repository permissions** (select the target monorepo only):

| Permission | Access |
|---|---|
| Contents | Read & Write |
| Pull requests | Read & Write |
| Issues | Read & Write |
| Checks | Read & Write |
| Metadata | Read (required by GitHub) |

5. Install the app on your target monorepo (not org-wide)
6. Generate a private key and download it

Save the **App ID**, **Client ID** (a separate value from the App ID, shown on the same settings page), and the private key — you'll need all three in the next step.

> **Note:** the GitHub App's permissions above do not include `workflows`. If you ever need FORGE's agents to modify a `.github/workflows/*` file in the target monorepo, that change must be pushed via a human's own git credentials first and opened as a PR through the App identity for review — the App cannot push workflow-file changes directly.

### 3. Configure secrets (5 min)

In your FORGE repository, go to **Settings → Secrets and variables → Actions** and add:

**Secrets**

| Secret | Value |
|---|---|
| `FORGE_APP_ID` | Your GitHub App's numeric App ID — used as the JWT issuer by FORGE's Python auth code (`github_helper.py`), separate from the Client ID below |
| `FORGE_APP_PRIVATE_KEY` | Contents of the downloaded `.pem` file |
| `ADO_PAT` | Your Azure DevOps Personal Access Token |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `ACR_LOGIN_SERVER` | Your Azure Container Registry's login server (e.g., `yourregistry.azurecr.io`) |
| `ACR_USERNAME` | Registry admin username (Azure Portal → your ACR → Settings → Access keys) |
| `ACR_PASSWORD` | Registry admin password (same location) |
| `AZURE_STAGING_CREDENTIALS` | One JSON blob — `{"clientId":"...","clientSecret":"...","subscriptionId":"...","tenantId":"..."}` — for a service principal with Contributor on the resource group containing your staging Container Apps environment. Used by the Deploy Agent to authenticate `az login --service-principal` before pushing revisions. |

**Variables** (Settings → Secrets and variables → Actions → Variables tab)

| Variable | Value |
|---|---|
| `FORGE_APP_CLIENT_ID` | Your GitHub App's Client ID — used by the `actions/create-github-app-token` Action; not a secret, this value is publicly visible on the App's settings page |
| `FORGE_TARGET_REPO` | The name of your target monorepo (e.g. `your-monorepo`) — read by every stage workflow and by `github_helper.py` to know which repo to open branches/PRs/issues against |
| `FORGE_GITHUB_OWNER` | The owner (user or org) of both your FORGE repo and target monorepo |
| `FORGE_ADO_ORG_URL` | Your Azure DevOps organization URL (e.g. `https://dev.azure.com/your-org`) — used only by `verify-setup.yml`'s connectivity check; the pipeline agents themselves read the org URL from `team/config.yaml`'s `ado.org_url` instead |

**Container Apps deployment credentials:** in addition to the registry secrets above, the Deploy Agent needs its own service principal (`AZURE_STAGING_CREDENTIALS`, in the table above) to authenticate against your Container Apps environment and push new revisions — Contributor on the resource group is sufficient. This principal cannot register new Azure resource providers or create RBAC role assignments; any one-time bootstrap work of that kind (e.g. provisioning a Key Vault, granting a managed identity a role) needs a human with elevated access instead.

### 4. Wire up your target monorepo's cross-repo dispatch workflows (10 min)

GitHub Actions can only trigger a workflow off an event in the **same** repo where it's
defined. Three of FORGE's stages need to react to events that happen in your **target
monorepo** — a feature PR opening, or merging — so three small workflow files must be
pushed directly to the target monorepo's `.github/workflows/`, not `forge-template`'s.
Skipping this step doesn't fail loudly: QA, Security, and Deploy will simply never fire
for any request, with no error anywhere pointing at why.

Copy these three files from `core/templates/target-repo-workflows/` in this repo to your
target monorepo's `.github/workflows/`:

- **`notify-forge.yml`** — forwards a feature PR opening (and merging) to `forge-template`
  as a `repository_dispatch` event, which `04-qa.yml`/`05-security.yml`/`06-deploy.yml`
  listen for. **Requires two edits** — replace the `YOUR_FORGE_OWNER`/`YOUR_FORGE_REPO`
  placeholders with your actual `forge-template` instance's owner/repo name (this is the
  one part that can't be self-referential, since it points at a different, fixed repo).
- **`design-pr-security-noop.yml`** and **`ops-pr-security-noop.yml`** — your target
  repo's branch protection requires a `security-check` status on every PR, but design-
  stage and ops-stage PRs never touch application code, so the real Security Agent scan
  never runs against them. These create a clearly-labeled no-op pass so those PRs aren't
  stuck waiting forever for a status that will never arrive. Copy these two as-is — no
  edits needed, they're fully self-referential via GitHub Actions' own context.

The GitHub App **cannot** push these itself — it has no `workflows` permission (see the
note in Step 2) — push them with your own git credentials instead.

`notify-forge.yml` also needs its own copies of two values already set on your FORGE
repo in Step 3 — repo secrets/variables don't cross repos in GitHub Actions:

| On your **target monorepo** | Value |
|---|---|
| `FORGE_APP_CLIENT_ID` (variable) | Same value as your FORGE repo's copy |
| `FORGE_APP_PRIVATE_KEY` (secret) | Same value as your FORGE repo's copy |

And the GitHub App must be installed on `forge-template` too, not just the target
monorepo, for the token this workflow generates to have write access to fire the
dispatch there.

### 5. Edit `team/config.yaml` (5 min)

Open `team/config.yaml` and fill in your team's values. This is the exact schema the
code reads — no other keys are consumed at runtime:

```yaml
# Azure DevOps
ado:
  org_url: "https://dev.azure.com/your-org"
  project: "YourProject"
  area_path: "YourProject\\YourTeam"
  default_tags:
    - "forge-managed"

# Azure Container Apps (staging only — there is no production deploy stage yet)
container_apps:
  staging:
    environment: forge-staging
    resource_group: your-rg
    max_replicas: 2
    min_replicas: 0
    cpu: 0.25
    memory: 0.5Gi
```

The target monorepo's owner/name are **not** set here — they're read from the
`FORGE_TARGET_REPO` / `FORGE_GITHUB_OWNER` repository variables (Settings → Secrets and
variables → Actions → Variables tab), set in the next step.

### 6. Provision your Azure Container Apps environment (5 min)

Create the staging environment with the Azure CLI, matching the default `team/config.yaml` expects:

```bash
az containerapp env create \
  --name forge-staging --resource-group your-rg --location canadacentral
```

Then size its Container Apps:
- **forge-staging** — scale to zero, max 2 replicas, 0.25 vCPU / 0.5 Gi

> **Provisioning via the Azure Portal instead:** the Portal currently only offers environment creation as a byproduct of creating an actual Container App — create a throwaway Container App using the built-in quickstart image, choose "Create new" for the environment during that flow, then delete just the placeholder Container App afterward (the environment persists on its own). The CLI path above avoids this workaround entirely.

Also create a **GitHub Environment** in your FORGE repo (**Settings → Environments**) named plainly `staging` — no required reviewers, so staging deploys run automatically once the pipeline's own label/merge gates are satisfied. This is a different, GitHub-native concept from the Azure Container Apps environment name above (`forge-staging`) — don't conflate the two.

### 7. Verify your setup

Run the verification workflow:

```bash
gh workflow run verify-setup.yml
```

Check the Actions tab — all steps should pass. If anything fails, the output will point you to the misconfigured item.

---

## Running your first pipeline

1. Your BA fills out the Excel intake template (`docs/Intake Template.xlsx`) and uploads it as an attachment to a new GitHub Issue in the FORGE repository
2. Apply the label **`intake-ready`** to the issue — this is what triggers Stage 0 and starts the pipeline; nothing happens on issue creation alone
3. The Intake Agent reads the spreadsheet and posts clarifying questions in the issue comments
4. The BA answers the questions and applies the label **`clarification-complete`** to the issue
5. The pipeline runs from here automatically, pausing at each gate for your approval

Each gate is a GitHub label applied to the tracking issue or a required PR review — no separate dashboard to learn.

> **Intake template:** a copy of the intake template is at `docs/Intake Template.xlsx`. Instructions and examples are on the first tab.

> **Fill in Request ID — don't leave it blank.** If the spreadsheet's "Request ID" field
> is empty, the pipeline doesn't stop or warn you — it silently proceeds under
> `request_id="unknown"` for the life of that tracking issue, filing every artifact under
> `docs/unknown/` in the monorepo. This was only caught once by a human noticing
> "`docs/unknown/`" in a posted comment; there's no supported way to correct it after the
> fact short of manually editing bot comments and moving already-committed files. Check
> the field before applying `intake-ready`.

> **Pipeline depth:** the intake template also has an optional "Pipeline
> Depth" field — leave it blank for a normal full run, or set it to stop
> the pipeline early (e.g. "Up to Design") if you only need to review
> architecture without paying for implementation, QA, security, and
> deploy. See the Orchestration Manager Guide for the full tier list.

---

## Approving a gate

| Gate | Where to approve |
|---|---|
| Requirements | Review the ADO work items the Requirements Agent created, then apply the `requirements-approved` label to the tracking issue |
| Design | Approve and merge the `design/<request-id>` PR, then apply the `design-approved` label to the tracking issue |
| Implementation | Approve and merge the `feature/<request-id>` PR — this is what allows QA and Security to run |
| QA sign-off | Automatic — the QA Agent applies `qa-approved` (or sends it back with a retry label) based on real test results; review its posted report on the PR |
| Security sign-off | Automatic — the Security Agent applies `security-approved` based on real scan results; review its posted report on the PR |
| Deploy (staging) | Automatic — fires once both labels above are present **and** the feature PR has actually been merged to `main` |

> If the intake spreadsheet's Pipeline Depth field was set to something
> short of "Up to Deployment," the pipeline stops on its own once that
> tier completes — applying a later `*-approved` label won't push it
> further. A comment and a `pipeline-complete-at-depth` label appear on
> the tracking issue when this happens.

There is no slash-command interface (`/approve-*`, `/reject-*`) anywhere in the pipeline — every gate above is either a GitHub label or a native PR review/merge. If a stage needs to be sent back, the agent's own retry/loop-back label handles it automatically (QA); Requirements and Design currently rely on you not applying the `*-approved` label (or not merging the PR) until you're satisfied — there's no separate reject action to take.

---

## Customising for your team

FORGE has two layers:

- **Core layer** (`core/`) — locked. Security gates, ADO work item structure, naming conventions, branching strategy. Standardised across all teams. Requires an RFC to change.
- **Team layer** (`team/`) — yours to configure. Tech stack preferences, agent personas, notification channels, additional approved tools.

What you can change in `team/config.yaml` and `team/stack-preferences.yaml` without any RFC:

- Agent personas and tone
- CSS framework, component library, ORM, state management choices (fed to the Design Agent)
- Notification channels (Slack, Teams, email)
- Container Apps resource sizing (within approved ranges)
- Linting ruleset

See `docs/07_Customization_Ref_v4.md` for a full list of what is locked, flexible, and fully open.

---

## Repository layout

```
your-forge-instance/
├── .github/
│   └── workflows/          # Pipeline stage workflows (core — do not edit)
├── core/
│   ├── agents/             # Agent prompts and schemas, incl. Implementation Coordinator + subagent definitions (locked)
│   └── decisions/          # Architecture Decision Records
├── team/
│   ├── config.yaml         # Your team configuration
│   ├── stack-preferences.yaml  # Tech choices fed to the Design Agent
│   └── personas/           # Optional agent persona overrides
├── docs/
│   └── Intake Template.xlsx
└── tracking/               # Reserved — currently empty (.gitkeep only); all real
                             # tracking data lives on the GitHub tracking issue
                             # itself (labels, comments), not as local files here
```

Your application code lives in your **target monorepo** — not here. FORGE opens branches and PRs there on your behalf.

---

## Reference documentation

| Document | Purpose |
|---|---|
| [FORGE Introduction](docs/00%20FORGE%20Introduction.md) | What FORGE is and why — start here if you're evaluating |
| [Product Specification](docs/01_FORGE_ProductSpec_v2.md) | Personas, feature set by pipeline stage, NFRs |
| [Architecture Document](docs/02-forge-architecture-document-v4.md) | Event-driven orchestration, agent topology, two-repo model, traceability |
| [Tool & Licensing Inventory](docs/03_FORGE_Tooling_v8.md) | Every tool, license, cost — including security tooling defaults |
| [Governance Model](docs/04_FORGE_Governance-v2.md) | RFC process, ADRs, decision authority, core vs team layer boundaries |
| [AI Foundations Guide](docs/05_FORGE_AI_Foundation_v2.md) | How LLMs and agents work — required reading for all developers using FORGE |
| [Orchestration Manager Guide](docs/06_Orchestration_v9.md) | Full setup, gate-by-gate operations, failure handling |
| [Customization Reference](docs/07_Customization_Ref_v4.md) | ~65 items explicitly marked Locked / Flexible / Fully Open |

---

## Cost reference

Per full pipeline run (estimate — measure your actuals during App 1):

| Item | Cost |
|---|---|
| Anthropic API (token costs, all stages) | ~$0.50–3 USD per run (Sonnet tier for stages 0–2, 4–6; Opus tier for Stage 3 coordinator) |
| Managed Agents runtime (Stage 3 only) | ~$0.08–0.32 USD (session-hour billing, in addition to token costs — estimate 1–4 hours per implementation run) |
| Azure Container Registry | ~$0.17/day (no pause option — only delete/recreate stops the charge) |
| GitHub Actions minutes | Included in most plans |
| Security tooling (Semgrep, Gitleaks, GitHub Dependabot) | Free (open source / included with GitHub) |

No net-new SaaS contracts are required with the default tool choices.

---

## Getting help

- **Setup issues:** Check the `verify-setup` workflow output first — it identifies the failing component
- **Pipeline failures:** See the [Orchestration Manager Guide](docs/06_Orchestration_v9.md) failure handling section
- **Proposing a core layer change:** Open a GitHub Discussion in this repository under the RFC category
- **Questions about what you can customize:** See the [Customization Reference](docs/07_Customization_Ref_v4.md)
