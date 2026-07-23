# FORGE Orchestration Manager Guide

**Full-SDLC Orchestration with Review Gates for Engineers**

---

## Purpose

This guide is for Orchestration Managers — the developers or tech leads who own and operate a team's FORGE instance. By the end of this guide you will be able to:

- Clone the FORGE template and configure it for your team
- Understand exactly what you can change, what you cannot, and why
- Run a FORGE pipeline from intake to deployment
- Recognize and respond to the common failure modes
- Know when your instance is ready for production workloads

This is Track 2 training. It assumes you have completed the AI Foundations Guide (Track 1) and are comfortable with GitHub, GitHub Actions, and Azure DevOps at a working level.

---

## What the Orchestration Manager Does

The Orchestration Manager is the operational owner of one FORGE instance. A team has exactly one Orchestration Manager, though the role can be handed off.

Day-to-day responsibilities:

- Keeping the instance configured correctly and up to date as core-layer updates ship
- Briefing BAs on how to complete the intake spreadsheet
- Watching pipeline runs and acting on failures
- Customizing the team layer to match the team's conventions
- Participating in the RFC process when a core-layer change would benefit your team
- Applying core-layer updates within the required window (30 days for non-security changes; 10 days for security gate changes)

You are not responsible for the agents' outputs. You are responsible for the conditions under which they run, the gates that reviewers use to approve work, and the health of the pipeline infrastructure itself.

---

## Part 1: Setup

### Before You Begin

Confirm you have:

- Owner or Admin access to the organization's GitHub account (to create the FORGE repo from template and install the GitHub App)
- Project Administrator access in Azure DevOps (to create the ADO project or confirm an existing one)
- Contributor access to the custom-apps monorepo (the target repository FORGE will operate on)
- An Azure subscription where you can create a Container Apps environment (for build phase, your personal Azure account is fine; see the moving-to-production checklist before cutover)
- Your Anthropic API key (personal developer account for build phase)

### Step 1 — Create Your FORGE Repo from the Template

In GitHub, open the FORGE template repo and click **Use this template → Create a new repository**.

Settings:

- **Owner:** your organization (or your personal account for build phase)
- **Repository name:** `forge-<team-name>` — e.g., `forge-platform-team`
- **Visibility:** Private

You now own a copy of the FORGE repo. From this point on, the FORGE template repo is upstream — you pull updates from it; you do not push back to it (unless you are the Core Platform Owner).

### Step 2 — Install the GitHub App

FORGE uses a GitHub App named `forge-pipeline` to authenticate into the custom-apps monorepo. You need to create one installation of this app scoped to your target monorepo.

In your organization's GitHub settings:

1. Go to **Settings → Developer Settings → GitHub Apps → New GitHub App**
2. Name it `forge-pipeline`
3. Set permissions:
   - Contents: Read and write
   - Pull requests: Read and write
   - Issues: Read and write
   - Checks: Read and write
   - Metadata: Read (required by GitHub)
4. Under **Where can this GitHub App be installed?**, select **Only on this account**
5. Create the app, generate a private key, and download it
6. Install the app on the custom-apps monorepo (not org-wide)

Store the credentials as repo-level secrets in your FORGE repo:

| Secret name | Value |
|---|---|
| `FORGE_APP_ID` | The App ID shown on the app's settings page |
| `FORGE_APP_PRIVATE_KEY` | The contents of the `.pem` private key file |

These secrets are used by every workflow job to generate a short-lived installation token (via `actions/create-github-app-token`). The token expires after one hour and is never stored.

### Step 3 — Configure the Team Layer

Open `team/config.yaml` in your FORGE repo. This file is yours to edit. Set the following:

```yaml
# ADO connection
ado:
  organization: "https://dev.azure.com/your-org"
  project: "YourProjectName"
  area_path: "YourProjectName\\YourTeamArea"   # default area path for work items

# Target repository
monorepo:
  owner: "your-github-org"
  repo: "custom-apps"

# Azure Container Apps
container_apps:
  staging:
    environment: "forge-staging"
    resource_group: "rg-forge-staging"
    subscription_id: "your-subscription-id"
    min_replicas: 0
    max_replicas: 2
    cpu: 0.25
    memory: "0.5Gi"
  production:
    environment: "forge-production"
    resource_group: "rg-forge-production"
    subscription_id: "your-subscription-id"
    min_replicas: 1
    max_replicas: 5
    cpu: 0.5
    memory: "1.0Gi"

# Notifications (optional)
notifications:
  teams_webhook: ""    # leave blank to disable
  email: ""            # leave blank to disable
```

The values above are the platform defaults. Change them to match your team's Azure setup. The floor and ceiling values for vCPU and memory are defined in `core/` — stay within them.

### Step 4 — Set Remaining Secrets

In your FORGE repo's settings under **Secrets and variables → Actions**, add:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `ADO_PAT` | An Azure DevOps Personal Access Token with work item read/write scope |
| `AZURE_CREDENTIALS` | Service principal credentials JSON for your Azure subscription |

For build phase, a PAT is acceptable for ADO. Before going to production, evaluate replacing the PAT with an ADO service principal — see the moving-to-production checklist.

### Step 5 — Create the Azure Container Apps Environments

In your Azure subscription, create two Container Apps environments. Use the names you set in `team/config.yaml`:

- `forge-staging` — in its own resource group
- `forge-production` — in its own resource group

For the production environment only, add a GitHub Environment in your FORGE repo under **Settings → Environments**:

- Name it `forge-production`
- Add yourself (or the designated Release Approver) as a required reviewer
- Enable **Required reviewers** — this is the gate that makes the production deploy require explicit approval

Staging deploys automatically. Production deploys never do.

### Step 6 — Verify the Setup

Confirm everything is wired up before your first pipeline run:

- [ ] FORGE repo created from template, visibility set to private
- [ ] `forge-pipeline` GitHub App installed on the monorepo only
- [ ] `FORGE_APP_ID` and `FORGE_APP_PRIVATE_KEY` secrets set in FORGE repo
- [ ] `team/config.yaml` updated with your ADO org, project, area path, monorepo details, and Azure environment names
- [ ] `ANTHROPIC_API_KEY`, `ADO_PAT`, and `AZURE_CREDENTIALS` secrets set
- [ ] `forge-staging` and `forge-production` Container Apps environments created
- [ ] `forge-production` GitHub Environment configured with a required reviewer

---

## Part 2: Running a Pipeline

### Intake — Starting a Request

The BA's job is to complete the Excel intake spreadsheet and upload it to trigger the pipeline. There are two ways to do this:

**Option A — Issue attachment (recommended for build phase):**
The BA opens a new issue in the FORGE repo, attaches the completed spreadsheet to the issue body, and applies the label `intake-ready`. The Intake Agent is triggered by this label event.

**Option B — Repository path:**
The BA places the completed spreadsheet in `intake/` in the FORGE repo at a path matching the naming convention (`intake/<request-id>.xlsx`) and opens a PR. The Intake Agent runs as a PR check.

Both options work. Option A is simpler for BAs who are not comfortable with Git. Option B creates a cleaner audit trail. The choice is team layer — document it in your Orchestration Manager notes so BAs know what to do.

### The "Clarification Complete" Signal

After the Intake Agent posts its clarifying questions (as a comment on the tracking issue), the BA reads the questions and replies. When the BA has answered all questions, they signal completion by applying the label `clarification-complete` to the tracking issue.

Do not rely on a keyword reply. The label is unambiguous, cannot be accidentally triggered by a follow-up question, and maps directly to the GitHub Actions event filter that starts the Requirements Agent. Brief your BAs on this: when they are done answering the agent's questions, they apply the `clarification-complete` label. Nothing starts until they do.

If the agent asks a follow-up question (a second round of clarification), the BA removes the label, answers, and re-applies it when done. The workflow guard clause checks for the label's presence at the moment the job runs — it will not re-trigger on label re-application if the Requirements stage has already started.

### What Happens at Each Gate

Once the pipeline is running, your job at each gate is to read what the agent produced and decide whether to approve it.

**Gate 1 — Requirements approval:**
The Requirements Agent has produced `requirements.md` in the monorepo and a summary comment on the tracking issue. Read both. If the requirements look correct, apply the label `requirements-approved` to the tracking issue. ADO work items (Epics, Features, User Stories) are created only after this label is applied.

**Gate 2 — Design approval:**
The Design Agent has opened a PR against `design/<request-id>` containing `design.md`, `openapi.yaml`, and `tasks.md`. Review the PR. The Technical Approver reviews the architecture and API contracts. Merge the PR to approve.

**Gate 3 — Implementation review:**
The Implementation Coordinator (a Managed Agents session) has run the Backend, Frontend, and Test Writer subagents in parallel on a shared sandbox filesystem, synthesized their output, committed the complete implementation to `feature/<request-id>`, and opened a draft PR. Review the diff. The coordinator has flagged any issues encountered in the PR description, and a per-subagent audit trail is available in the Claude Console alongside the GitHub Actions log. Approve or request changes — the coordinator does not merge its own PR.

**Gate 4 — QA sign-off:**
The QA Agent has posted a test report as a PR comment. If all tests pass, apply `qa-approved`. If failures exist, the agent has already filed ADO bug tickets and the implementation loop restarts. You do not need to act on failures — the loop handles itself unless it exceeds the retry limit (see failure handling below).

**Gate 5 — Security sign-off:**
The Security Agent has posted severity-tagged findings as inline PR comments. A Critical finding has already set a failing check that blocks merge. If there are no Criticals, or after Criticals are resolved, the Technical Approver applies `security-approved`.

**Gate 6 — Production deployment:**
Staging deploys automatically once all prior gates pass. To approve production, open the GitHub Environment approval request and click **Approve**. The Deploy Agent runs the production deployment.

---

## Part 3: Customizing Your Instance

### What You Can Change (Team Layer)

Everything in `team/` is yours. Common customizations:

**Agent personas** — Edit `team/personas/` to adjust the tone and style of agent-generated content. Each file corresponds to one agent. Changing a persona affects how the agent communicates, not what it produces. Do not change the agent's instructions for what it produces — that's in `core/agents/` and is locked.

**Linting ruleset** — The requirement that linting runs is core and cannot be removed. Which rules apply is yours. Edit `team/.eslintrc` (frontend) and `team/.editorconfig` and relevant .NET analysis config files. The linting job reads from these files.

**Notification channels** — Set the Teams webhook or email in `team/config.yaml`. Leave blank to disable. Notifications fire on gate completions and failures.

**Azure Container Apps defaults** — Adjust vCPU, memory, and replica counts within the bounds defined in `core/container-apps.schema.yaml`. Changes apply to new pipeline runs; they do not retroactively change running containers.

**ADO configuration** — Change the default area path, iteration path, and any team-specific field defaults. The fields FORGE writes are fixed (core layer); the values some of them take are configurable here.

**Tech stack preferences** — Document your team's choices for CSS framework, component library, ORM, state management, and logging in `team/stack-preferences.yaml`. The Design Agent reads this file when producing `design.md`, so the agent's designs align with your team's conventions rather than making arbitrary choices.

### What You Cannot Change (Core Layer)

Files in `core/` are not to be modified in your instance. Modifying them will cause divergence from the upstream template and break your ability to apply core-layer updates cleanly.

Core layer is locked because these items affect security, compliance, interoperability, and the traceability chain that spans from spreadsheet to deployment:

- Security gate tools, their configuration, and the blocking behaviour on Critical findings
- ADO work item structure and the fields FORGE writes for traceability
- Branch naming and the branching strategy in the monorepo
- The Excel intake spreadsheet template field names and overview tab structure
- The `forge-pipeline` GitHub App permission set
- The no-self-merge rule (agents open PRs; agents never merge them)
- The agent prompts in `core/agents/`

If you have a legitimate reason to change something in `core/`, open an RFC in the FORGE template repo. See the Governance Model document for the RFC process.

---

## Part 4: Failure Handling

Most failures are recoverable. The key distinction is whether the failure is in the agent's work (recoverable by re-running or looping), the infrastructure (requires Orchestration Manager action), or the pipeline logic itself (requires escalation).

### Agent Failures

**The agent produced incorrect or incomplete output.**
This is the most common case. Read the tracking issue and PR comments — the agent usually flags its own uncertainty. If the output is salvageable, edit it directly (requirements.md, design.md, or code files) before approving the gate. If the output is substantially wrong, close the tracking issue, correct the intake spreadsheet (or clarify the requirements), and open a new request. Do not attempt to re-run an agent mid-stage; re-runs start from the beginning of the current stage.

**The QA loop has exceeded the retry limit.**
The QA Agent retries implementation failures up to three times before stopping and escalating. If this happens, the pipeline halts with a `qc-retry-limit-reached` label on the tracking issue. Review the QA report and the open bug tickets in ADO. Determine whether the bug is in the agent's code (common) or in the test assertions (less common but possible). Manually triage: either close incorrect test tickets or mark the code direction as incorrect and open a new request with corrected design guidance.

**The agent silently failed — no output, no error comment.**
This applies to all stages except Stage 3 (see the Managed Agents entry below for implementation-stage failures). Check the GitHub Actions job log for the failed run. Look for a non-zero exit code in the Claude Agent SDK call step. Common causes: API timeout (the Anthropic API call exceeded the job timeout), context overflow (the agent's input was too large), or a malformed tool call. The job log will distinguish these. For API timeouts and context overflow, reduce the scope of the request. For malformed tool calls, this is a bug — file an issue in the FORGE template repo.

**The Implementation Coordinator session failed (Stage 3).**
Stage 3 runs as a Managed Agents session rather than a standalone SDK call, so failures here look different. Start with the Claude Console — it provides a per-subagent audit trail (Backend, Frontend, Test Writer) in addition to the GitHub Actions log, and will usually show which subagent failed or where the coordinator's synthesis step broke down. Common causes: a session-level error (the coordinator agent session itself failed to start or was terminated — check for a beta-header or quota issue), a single subagent failure that the coordinator could not work around (check that subagent's portion of the Console trail), or a sandbox filesystem conflict during synthesis. For a session-level error, confirm the Managed Agents beta header and API access are still valid before retrying. For a subagent-specific failure, the coordinator's PR description (if one was opened) or the Console trail will usually identify which subagent and why. As with other agent failures, do not attempt to resume a failed session mid-stage — a re-run starts a fresh Stage 3 session from the approved design.

### Infrastructure Failures

**The GitHub App token failed to generate.**
The `FORGE_APP_ID` or `FORGE_APP_PRIVATE_KEY` secret is wrong, or the app's private key has been rotated. Verify the secrets match the current key shown in the GitHub App settings. If the key was rotated, generate a new one and update the secret.

**The Azure Container Apps deployment failed.**
Check the deployment logs in Azure. Common causes: the Docker image failed to build (check the build step in the Actions log), the image was pushed to a registry the Container Apps environment cannot reach (check managed identity or registry access), or the `team/config.yaml` environment names don't match the actual Container Apps environment names in Azure.

**The ADO work item creation failed.**
The `ADO_PAT` may be expired or may have insufficient scope. Regenerate the PAT with work items read/write scope and update the secret. Confirm the area path in `team/config.yaml` exists in the ADO project — a missing area path causes a silent 400 from the ADO API.

**The Managed Agents API rejected the request (beta access issue).**
Managed Agents is currently a public beta and requires a specific beta header on API calls. If Stage 3 fails immediately with an authorization or unrecognized-feature error, confirm the beta header is current — Anthropic may change it between beta versions. This is worth checking first if Stage 3 failures start appearing across multiple requests rather than one-off subagent issues, since it points to a platform-level change rather than a single session going wrong. Flag any such breaking change as a candidate for RFC per the open item tracked in the project context.

### Escalation

If a failure is not covered above and you cannot resolve it from the job logs, escalate to the Core Platform Owner with:

- The request ID (from the tracking issue title)
- The stage that failed
- The GitHub Actions run URL
- The full job log (download via the Actions UI)
- What you have already tried

Do not attempt to patch `core/` files locally. If the failure is caused by a bug in the core layer, the fix goes through the template repo and is applied as an update.

---

## Part 5: Moving to Production

This checklist is for when a FORGE instance is ready to move from build-phase workloads to production workloads. "Production" here means real projects, real ADO boards, real deployments to the organization's Azure subscription.

### Infrastructure

- [ ] FORGE repo transferred to the organization's GitHub account (if built under a personal account)
- [ ] `forge-pipeline` GitHub App re-created or transferred under the organization account
- [ ] Azure Container Apps environments provisioned in the organization's Azure subscription under the correct subscription and resource group naming conventions
- [ ] Azure Container Registry provisioned in the organization's Azure subscription; `AZURE_CREDENTIALS` secret updated to a service principal with the correct role assignments (AcrPush on the registry, Contributor on the Container Apps resource group)
- [ ] Staging and production environments connected to the organization's Azure Container Apps environments in `team/config.yaml`

### Credentials and Access

- [ ] `ANTHROPIC_API_KEY` updated to the organization's API key (not a personal developer account key)
- [ ] `ADO_PAT` evaluated for replacement with an ADO service principal; if keeping PAT, confirm it has an expiry date in the calendar and an owner who will rotate it
- [ ] `FORGE_APP_PRIVATE_KEY` rotation schedule established (rotate at least annually)
- [ ] All secrets stored at repo level (not environment level) unless environment-scoped access is required

### Process

- [ ] At least one BA has completed intake training and successfully submitted a test request through the pipeline
- [ ] At least one Technical Approver has been identified for each gate that requires technical review (Gate 2 — Design, Gate 5 — Security)
- [ ] The Release Approver for the `forge-production` GitHub Environment has been confirmed and has accepted the responsibility
- [ ] All six gates have been exercised at least once on a non-trivial request (the three-app demo plan satisfies this requirement)
- [ ] The QA retry limit has been tested at least once (trigger a deliberately failing test to confirm the loop-back and escalation behaviour)
- [ ] Orchestration Manager has read and understands the failure handling section of this guide; at least one escalation path has been tested end-to-end

### Governance

- [ ] Orchestration Manager account added to the FORGE template repo with read access (to receive RFC notifications and core-layer update announcements)
- [ ] Update cadence documented in team notes: 30-day window for non-security updates, 10-day window for security gate changes
- [ ] RFC process explained to the team; at least one team member knows how to open an RFC if needed

### Optional but Recommended Before Production

- [ ] Docker Desktop licensing confirmed for all developers who will run local builds (verify LAA non-profit eligibility, or standardize on Rancher Desktop to avoid licensing questions)
- [ ] GitHub Actions minutes consumption measured across at least two full pipeline runs; confirm within the organization's included minutes or budget for overages
- [ ] Anthropic API cost per pipeline run measured and recorded in the cost summary section of the Tool & Licensing Inventory (Document 3)
- [ ] Notification channels configured in `team/config.yaml` so gate completions and failures alert the right people without requiring anyone to watch the Actions tab

---

## Reference

### Label Reference

The following labels are used in the FORGE tracking issue to drive pipeline state. Do not apply these labels manually unless you understand what they trigger.

| Label | Applied by | Effect |
|---|---|---|
| `intake-ready` | BA | Triggers Intake Agent |
| `clarification-complete` | BA | Triggers Requirements Agent |
| `requirements-approved` | Technical Approver | Creates ADO work items; triggers Design Agent |
| `qa-approved` | QA Reviewer | Clears QA gate; combined with `security-approved` to enable production deploy |
| `security-approved` | Security Reviewer | Clears security gate; combined with `qa-approved` to enable production deploy |
| `qc-retry-limit-reached` | QA Agent | Halts pipeline; requires Orchestration Manager triage |

PR events (open, merge) and GitHub Environment approvals handle the remaining state transitions — these are not label-driven.

### File Reference

| Path (FORGE repo) | Purpose | Layer |
|---|---|---|
| `core/agents/` | Agent prompts and tool definitions | Core (locked) |
| `core/decisions/` | Architecture Decision Records | Core (locked) |
| `core/container-apps.schema.yaml` | Floor/ceiling values for container config | Core (locked) |
| `team/config.yaml` | ADO, Azure, monorepo connection settings | Team (yours) |
| `team/personas/` | Agent tone and communication style | Team (yours) |
| `team/stack-preferences.yaml` | CSS framework, ORM, library choices | Team (yours) |
| `.github/workflows/` | GitHub Actions workflow definitions | Core (locked) |

| Path (monorepo) | Purpose | Created by |
|---|---|---|
| `docs/<request-id>/requirements.md` | Approved requirements | Requirements Agent |
| `docs/<request-id>/design.md` | Architecture and API design | Design Agent |
| `docs/<request-id>/openapi.yaml` | API contract | Design Agent |
| `docs/<request-id>/tasks.md` | Implementation task breakdown | Design Agent |
| `services/<service-name>/` | Application source code | Backend/Frontend subagents (via Implementation Coordinator) |

### Getting Help

For questions about the core layer or the FORGE platform, open a GitHub Discussion in the FORGE template repo under the **Q&A** category.

For questions about this guide or the Orchestration Manager role, contact the Core Platform Owner.

For Anthropic API and Claude Agent SDK documentation, refer to the annotated resource list in the AI Foundations Guide (Document 5, Section 9).
