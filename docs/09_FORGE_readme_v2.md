# FORGE

**Full-SDLC Orchestration with Review Gates for Engineers**

FORGE is an AI-orchestrated software development lifecycle platform for Legal Aid Alberta. It takes a BA-produced requirements spreadsheet, moves it through a fully staged pipeline (requirements → design → code → QA → security → deploy), and delivers a working application — with humans reviewing and approving at every gate.

Agents do the work. Humans approve the outcomes.

---

## How it works

FORGE is a GitHub template repository. You clone it, configure it for your team, and it orchestrates development work *into* your existing codebase via a GitHub App — your application code never lives here.

The pipeline is event-driven through GitHub Actions. Each stage spins up a Claude agent, produces an artifact, and waits for a human to approve before the next stage begins.

```
BA uploads spreadsheet
        ↓
Intake & clarification  (no gate)
        ↓
Requirements            ✅ Approve ADO work items
        ↓
Spec & design           ✅ Approve architecture + API contracts
        ↓
Implementation          ✅ Review draft PR  (Implementation Coordinator runs Backend, Frontend, Test Writer subagents in parallel)
        ↓
QA + security           ✅ QA sign-off  ✅ Security sign-off  (run in parallel)
        ↓
Deploy                  ✅ One-click production approval
```

---

## Prerequisites

Before you start, make sure you have:

- **GitHub** — a repository for your application code (the "target" monorepo) and permissions to create a GitHub App
- **Azure** — an active subscription with permissions to create Container Apps environments and a Container Registry
- **Azure DevOps** — a project with Boards enabled; a Personal Access Token with Work Items (Read & Write) scope
- **Anthropic API** — an API key with **Managed Agents beta access** (`managed-agents-2026-04-01` header) for Stage 3; Opus tier for the Implementation Coordinator, Sonnet tier for all other stages
- **Node.js 20+** and **Docker** installed locally

> **Build phase note:** A personal Anthropic API account and personal Azure subscription are fine for initial setup. Before going to production, plan to migrate to your organisation's accounts.

---

## Getting started

### 1. Create your FORGE repository (5 min)

Click **Use this template** on GitHub and create a new private repository. This is your team's Orchestration Manager instance — you own and maintain it.

```bash
git clone https://github.com/your-org/your-forge-instance.git
cd your-forge-instance
```

### 2. Create the GitHub App (10 min)

FORGE authenticates into your target monorepo through a GitHub App — never a personal token.

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**
2. Name it `forge-pipeline`
3. Set the Webhook URL to your repo's Actions URL (or disable webhooks for now)
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

Save the App ID and private key — you'll need them in the next step.

### 3. Configure secrets (5 min)

In your FORGE repository, go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|---|---|
| `FORGE_APP_ID` | Your GitHub App ID |
| `FORGE_APP_PRIVATE_KEY` | Contents of the downloaded `.pem` file |
| `ADO_PAT` | Your Azure DevOps Personal Access Token |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `AZURE_CREDENTIALS` | Azure service principal credentials (JSON) |

### 4. Edit `team/config.yaml` (5 min)

Open `team/config.yaml` and fill in your team's values:

```yaml
# Target repository (where agents will open branches and PRs)
target_repo: your-org/your-monorepo

# Azure DevOps
ado_org: https://dev.azure.com/your-org
ado_project: YourProject
ado_area_path: YourProject\\YourTeam

# Azure Container Apps
registry: yourregistry.azurecr.io
staging_env: forge-staging
production_env: forge-production
resource_group: your-rg

# Intake
intake_method: issue_attachment   # or: repo_path
```

### 5. Provision Azure Container Apps environments (5 min)

Run the setup script to create both environments with the default FORGE configuration:

```bash
./scripts/bootstrap-azure.sh \
  --resource-group your-rg \
  --location canadacentral \
  --registry yourregistry
```

This creates:
- **forge-staging** — scale to zero, max 2 replicas, 0.25 vCPU / 0.5 Gi
- **forge-production** — min 1 replica, max 5, 0.5 vCPU / 1.0 Gi

### 6. Verify your setup

Run the verification workflow:

```bash
gh workflow run verify-setup.yml
```

Check the Actions tab — all steps should pass. If anything fails, the output will point you to the misconfigured item.

---

## Running your first pipeline

1. Your BA fills out the Excel intake template (`templates/forge-intake-template.xlsx`) and uploads it as an attachment to a new GitHub Issue in the FORGE repository
2. The Intake Agent reads the spreadsheet and posts clarifying questions in the issue comments
3. The BA answers the questions and applies the label **`clarification-complete`** to the issue
4. The pipeline runs from here automatically, pausing at each gate for your approval

Each gate shows up as a required PR review or a GitHub Environment approval — no separate dashboard to learn.

> **Intake template:** A copy of the intake template is at `templates/forge-intake-template.xlsx`. Instructions and examples are on the first tab.

---

## Approving a gate

| Gate | Where to approve |
|---|---|
| Requirements | Comment `/approve-requirements` on the tracking issue |
| Design | Approve the `design/<request-id>` PR |
| Implementation | Approve the `feature/<request-id>` PR |
| QA sign-off | Comment `/approve-qa` on the tracking issue |
| Security sign-off | Comment `/approve-security` on the tracking issue |
| Production deploy | Approve the **forge-production** GitHub Environment |

If you need to send a stage back, comment `/reject-<stage> <reason>` on the tracking issue.

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

See `docs/07-forge-customization-reference.md` for a full list of what is locked, flexible, and fully open.

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
├── templates/
│   └── forge-intake-template.xlsx
├── tracking/               # Per-request tracking issue metadata
└── scripts/
    └── bootstrap-azure.sh
```

Your application code lives in your **target monorepo** — not here. FORGE opens branches and PRs there on your behalf.

---

## Reference documentation

| Document | Purpose |
|---|---|
| [FORGE Introduction](docs/00-forge-introduction.md) | What FORGE is and why — start here if you're evaluating |
| [Product Specification](docs/01-forge-product-specification.md) | Personas, feature set by pipeline stage, NFRs |
| [Architecture Document](docs/02-forge-architecture-document.md) | Event-driven orchestration, agent topology, two-repo model, traceability |
| [Tool & Licensing Inventory](docs/03-forge-tool-licensing-inventory.md) | Every tool, license, cost — including security tooling defaults |
| [Governance Model](docs/04-forge-governance-model.md) | RFC process, ADRs, decision authority, core vs team layer boundaries |
| [AI Foundations Guide](docs/05-forge-ai-foundations-guide.md) | How LLMs and agents work — required reading for all developers using FORGE |
| [Orchestration Manager Guide](docs/06-forge-orchestration-manager-guide.md) | Full setup, gate-by-gate operations, failure handling, production checklist |
| [Customization Reference](docs/07-forge-customization-reference.md) | ~65 items explicitly marked Locked / Flexible / Fully Open |

---

## Cost reference

Per full pipeline run (estimate — measure your actuals during App 1):

| Item | Cost |
|---|---|
| Anthropic API (token costs) | ~$1–5 USD (Sonnet tier) |
| Managed Agents runtime (Stage 3 coordinator + subagents) | ~$0.08–0.32 USD (session-hour billing, in addition to token costs — estimate 1–4 hours per implementation run) |
| Azure Container Registry | ~$0.17/day |
| GitHub Actions minutes | Included in most plans |
| Security tooling (Semgrep, Gitleaks, OWASP Dependency-Check) | Free (open source) |

No net-new SaaS contracts are required with the default tool choices.

---

## Getting help

- **Setup issues:** Check the `verify-setup` workflow output first — it identifies the failing component
- **Pipeline failures:** See the [Orchestration Manager Guide](docs/06-forge-orchestration-manager-guide.md) failure handling section
- **Proposing a core layer change:** Open a GitHub Discussion in this repository under the RFC category
- **Questions about what you can customize:** See the [Customization Reference](docs/07-forge-customization-reference.md)
