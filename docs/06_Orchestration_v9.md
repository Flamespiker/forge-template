# FORGE Orchestration Manager Guide

**Full-SDLC Orchestration with Review Gates for Engineers**

**v9 changelog:** added new Step 5 (Wire Up Your Target Monorepo's Cross-Repo
Dispatch Workflows) — `notify-forge.yml`/`design-pr-security-noop.yml`/
`ops-pr-security-noop.yml` must be pushed to the target monorepo or QA,
Security, and Deploy silently never fire for any request, with nothing
pointing at why. Confirmed live 2026-09-04 on a platform swap whose target
repo shipped without these; reference copies now live in
`core/templates/target-repo-workflows/` in `forge-template` itself (they
previously existed only in the target repo, with no source to recover them
from if that repo is ever lost). Old Steps 5/6 renumbered to 6/7.

**v8 changelog:** added a note at Gate 2 (Design approval) warning that a
manual edit to `design.md` before merge isn't automatically checked against
`openapi.yaml`/`tasks.md` — a mismatch across the three surfaces becomes
Stage 3's problem silently, rather than being caught.

**v7 changelog (Phase 8, 8.1 review):** added the "Enhancement vs.
Greenfield Requests" section and Enhancement-specific notes at Gate 6 and
in the File Reference table (Stage 0a, `existing_service` targeting,
in-place Deploy, ADO Epic linkage — Items #24/#25/#28/#32); added Gate 2.5
(Cost Estimator / `cost-approved`, Item #34) and its Label Reference
entries; corrected Gate 6 and the Label Reference table to reflect that
Deploy requires a confirmed feature-PR merge, not just labels (Item #26);
added the post-deploy crash-loop health check to Failure Handling
(Item #1); corrected two stale "Claude Agent SDK" references — six of the
seven stages use the base `anthropic` client directly (ADR-0011), not the
Agent SDK. **Post-review fix:** Step 4's secrets table was missing
`AZURE_STAGING_CREDENTIALS` and still carried a stale "not finalized as of
this writing" caution about Container Apps deployment credentials — both
corrected to match README.md and the live Deploy Agent; the Step 6
checklist now lists this secret too.

**Post-review fix (Items #35/#36/#37):** Step 3's `team/config.yaml` example used a
schema that matched neither the real shipped file nor README's own example — replaced
with the exact schema the code actually reads (`ado.*` + `container_apps.staging`
only; no `monorepo`/`notifications` keys, no `container_apps.production` block, none
of which any code consumes). Step 2's variable table and Step 6's checklist now list
the new `FORGE_TARGET_REPO`/`FORGE_GITHUB_OWNER`/`FORGE_ADO_ORG_URL` repository
variables that replace what used to be hardcoded literals in every stage workflow.
The Intake section's "Option B — Repository path" was removed from the two-options
framing — a codebase check found no such logic implemented anywhere; only issue
attachment exists in code today.

**Post-review addition (Item #43, Configurable Pipeline Depth):** added the "Pipeline
Depth — Limiting How Far a Request Goes" section, the `pipeline-complete-at-depth`
Label Reference row, and the `pipeline-config.json` File Reference row.

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
5. Under **Webhook**, uncheck **Active** — FORGE's workflows call the GitHub and Anthropic APIs directly using a generated token; no inbound webhook is needed
6. Create the app, generate a private key, and download it
7. Install the app on the custom-apps monorepo (not org-wide)

Store the credentials as repo-level secrets in your FORGE repo:

| Secret name | Value |
|---|---|
| `FORGE_APP_ID` | The App ID shown on the app's settings page |
| `FORGE_APP_PRIVATE_KEY` | The contents of the `.pem` private key file |

Also store the App's **Client ID** (a separate value from the App ID, shown on the same settings page) as a repository **variable** — not a secret, since it isn't sensitive:

| Variable name | Value |
|---|---|
| `FORGE_APP_CLIENT_ID` | The Client ID shown on the app's settings page |
| `FORGE_TARGET_REPO` | The name of your target monorepo — read by every stage workflow and by `github_helper.py` |
| `FORGE_GITHUB_OWNER` | The owner (user or org) of both your FORGE repo and target monorepo |
| `FORGE_ADO_ORG_URL` | Your Azure DevOps organization URL — used only by `verify-setup.yml`'s connectivity check (the pipeline agents themselves read `team/config.yaml`'s `ado.org_url` instead) |

**Note on `actions/create-github-app-token`:** as of mid-2026, the current major version of this action is `@v3`, which uses the `client-id` input above rather than the older `app-id` input (older major versions relied on a Node.js runtime GitHub has since deprecated). Confirm any workflow using this action pins `@v3` or later and reads `client-id` from `vars.FORGE_APP_CLIENT_ID` — using an older version with only `app-id`/`FORGE_APP_ID` set will fail once GitHub fully retires the deprecated runtime.

These secrets/variables are used by every workflow job to generate a short-lived installation token. The token expires after one hour and is never stored.

### Step 3 — Configure the Team Layer

Open `team/config.yaml` in your FORGE repo. This file is yours to edit. This is the exact
schema the code reads — confirmed by a full codebase grep, not just a suggested shape —
so use these key names and this nesting exactly:

```yaml
ado:
  org_url: "https://dev.azure.com/your-org"
  project: "YourProjectName"
  area_path: "YourProjectName\\YourTeamArea"   # default area path for work items
  default_tags:
    - "forge-managed"

container_apps:
  staging:
    environment: "forge-staging"
    resource_group: "rg-forge-staging"
    min_replicas: 0
    max_replicas: 2
    cpu: 0.25
    memory: "0.5Gi"
```

The values above are the platform defaults for the fields that exist. Change them to
match your team's Azure setup. The floor and ceiling values for vCPU and memory are
defined in `core/` — stay within them.

There is no `container_apps.production` block — FORGE currently deploys to staging
only (see README's Production deploys note); a production block would be read by no
code and would silently do nothing. There is also no `monorepo`/target-repo section
here — the target monorepo's owner/name are read from the `FORGE_TARGET_REPO` /
`FORGE_GITHUB_OWNER` repository variables instead (Step 4), not from this file. And
there are no `notifications` keys — no code in `core/` reads a Teams webhook or email
address; if you want gate-completion notifications, wire them yourself (e.g. a
GitHub Actions step) rather than expecting this file to drive them.

### Step 4 — Set Remaining Secrets

In your FORGE repo's settings under **Secrets and variables → Actions**, add:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `ADO_PAT` | An Azure DevOps Personal Access Token with work item read/write scope |
| `ACR_LOGIN_SERVER` | Your Azure Container Registry's login server (e.g., `yourregistry.azurecr.io`) |
| `ACR_USERNAME` | Registry admin username (Azure Portal → your ACR → Settings → Access keys) |
| `ACR_PASSWORD` | Registry admin password (same location) |
| `AZURE_STAGING_CREDENTIALS` | One JSON blob — `{"clientId":"...","clientSecret":"...","subscriptionId":"...","tenantId":"..."}` — for a service principal with Contributor on the resource group containing your staging Container Apps environment. Used by the Deploy Agent to authenticate `az login --service-principal` before pushing revisions. |

For build phase, a PAT is acceptable for ADO, and ACR admin-user credentials are acceptable for registry push access. Before going to production, evaluate replacing the ADO PAT with a service principal, and the ACR admin user with a scoped service principal holding the `AcrPush` role — see the moving-to-production checklist.

**Note on Container Apps deployment credentials:** the secrets above cover both pushing images to the registry and authenticating the Deploy Agent to push new revisions into the Container Apps environments themselves (`AZURE_STAGING_CREDENTIALS`). This principal cannot register new Azure resource providers or create RBAC role assignments — any one-time bootstrap work of that kind (e.g. provisioning a Key Vault, granting a managed identity a role) needs a human with elevated access instead.

### Step 5 — Wire Up Your Target Monorepo's Cross-Repo Dispatch Workflows

GitHub Actions can only trigger a workflow off an event in the same repo where it's
defined. Three of FORGE's stages need to react to events that happen in your target
monorepo — a feature PR opening, or merging — so three small workflow files must be
pushed directly to the target monorepo's `.github/workflows/`, not `forge-template`'s.
**Skipping this step doesn't fail loudly**: QA, Security, and Deploy will simply never
fire for any request, with nothing anywhere pointing at why — confirmed the hard way
live 2026-09-04, when a platform swap's own target repo shipped without these and three
stages silently never ran until the gap was traced back to this exact missing step.

Copy these three files from `core/templates/target-repo-workflows/` in `forge-template`
to your target monorepo's `.github/workflows/`:

- **`notify-forge.yml`** — forwards a feature PR opening (and merging) to
  `forge-template` as a `repository_dispatch` event, which `04-qa.yml`/`05-security.yml`/
  `06-deploy.yml` listen for. Requires two edits: replace the
  `YOUR_FORGE_OWNER`/`YOUR_FORGE_REPO` placeholders with your actual `forge-template`
  instance's owner/repo name — the one part that can't be self-referential, since it
  points at a different, fixed repo.
- **`design-pr-security-noop.yml`** / **`ops-pr-security-noop.yml`** — your target
  repo's branch protection requires a `security-check` status on every PR, but
  design-stage and ops-stage PRs never touch application code, so the real Security
  Agent scan never runs against them. These create a clearly-labeled no-op pass so
  those PRs aren't stuck waiting forever for a status that will never arrive. Copy both
  as-is — fully self-referential via GitHub Actions' own context, no edits needed.

The GitHub App **cannot** push these itself (no `workflows` permission, per Step 2) —
push them with your own git credentials instead.

`notify-forge.yml` also needs its own copies of two values already set on your FORGE
repo in Step 4 — repo secrets/variables don't cross repos in GitHub Actions:

| On your **target monorepo** | Value |
|---|---|
| `FORGE_APP_CLIENT_ID` (variable) | Same value as your FORGE repo's copy |
| `FORGE_APP_PRIVATE_KEY` (secret) | Same value as your FORGE repo's copy |

And the GitHub App must be installed on `forge-template` too, not just the target
monorepo, for the token this workflow generates to have write access to fire the
dispatch there.

### Step 6 — Create the Azure Container Apps Environments

In your Azure subscription, create two Container Apps environments. Use the names you set in `team/config.yaml`:

- `forge-staging` — in its own resource group
- `forge-production` — in its own resource group

**Note on the Azure portal:** as of mid-2026, the portal only lets you create a Container Apps environment as a byproduct of creating an actual Container App — there's no standalone "create environment" option. A simple workaround: create a throwaway Container App using Azure's built-in "quickstart image," pick **Create new** under Container Apps Environment during that flow, then delete just the placeholder Container App afterward — the environment itself persists independently once created. **This is a Portal-specific limitation** — the Azure CLI (`az containerapp env create`) creates an environment directly with no placeholder needed, so prefer the CLI (or the repo's `scripts/bootstrap-azure.sh`, if it wraps the CLI) over the Portal when you have the option.

Also create two corresponding **GitHub Environments** in your FORGE repo under **Settings → Environments** — note these are named plainly (`staging` / `production`), distinct from the Azure Container Apps environment names above (`forge-staging` / `forge-production`) — don't conflate the two when naming things:

- **`staging`** — no required reviewers; this is what makes staging deploy automatically
- **`production`** — add yourself (or the designated Release Approver) as a required reviewer, and enable **Required reviewers** — this is the gate that makes the production deploy require explicit approval

Staging deploys automatically. Production deploys never do.

### Step 7 — Verify the Setup

Confirm everything is wired up before your first pipeline run:

- [ ] FORGE repo created from template, visibility set to private
- [ ] `forge-pipeline` GitHub App installed on the monorepo only
- [ ] `FORGE_APP_ID` and `FORGE_APP_PRIVATE_KEY` secrets, and `FORGE_APP_CLIENT_ID` / `FORGE_TARGET_REPO` / `FORGE_GITHUB_OWNER` / `FORGE_ADO_ORG_URL` variables, set in FORGE repo
- [ ] `team/config.yaml` updated with your ADO org, project, area path, and staging Azure environment/resource-group names
- [ ] `ANTHROPIC_API_KEY`, `ADO_PAT`, `ACR_LOGIN_SERVER`, `ACR_USERNAME`, `ACR_PASSWORD`, and `AZURE_STAGING_CREDENTIALS` secrets set
- [ ] `forge-staging` and `forge-production` Container Apps environments created in Azure
- [ ] `staging` and `production` GitHub Environments created in the FORGE repo, with `production` configured with a required reviewer

Consider also running the setup verification workflow described in Build Plan step 2.8 (a GitHub Actions workflow that pings the GitHub App token generation, ADO, and Anthropic API in one run) and the Managed Agents access check in step 2.9 before your first real pipeline request — catching a misconfigured secret this way is much faster than discovering it mid-pipeline.

---

## Part 2: Running a Pipeline

### Intake — Starting a Request

The BA's job is to complete the Excel intake spreadsheet and upload it to trigger the pipeline:

**Issue attachment:**
The BA opens a new issue in the FORGE repo, attaches the completed spreadsheet to the issue body, and applies the label `intake-ready`. The Intake Agent is triggered by this label event.

**Not yet implemented — repository path:** an earlier version of this guide described a
second option (dropping the spreadsheet at `intake/<request-id>.xlsx` and opening a PR,
with `intake_agent.py` running as a PR check). A codebase check (backlog Item #36) found
no such branching logic anywhere in `intake_agent.py` — only the issue-attachment path
exists in code today. Treat this as a possible future option, not a currently-real choice.

### The "Clarification Complete" Signal

After the Intake Agent posts its clarifying questions (as a comment on the tracking issue), it applies the label `clarification-pending` — a status marker, not a trigger; nothing listens for it. The BA reads the questions and replies. When the BA has answered all questions, they signal completion by applying the label `clarification-complete` to the tracking issue. `clarification-pending` does not need to be removed for this to work — the Requirements Agent's guard clause checks only for `clarification-complete`'s presence, not for `clarification-pending`'s absence.

Do not rely on a keyword reply. The label is unambiguous, cannot be accidentally triggered by a follow-up question, and maps directly to the GitHub Actions event filter that starts the Requirements Agent. Brief your BAs on this: when they are done answering the agent's questions, they apply the `clarification-complete` label. Nothing starts until they do.

If the agent asks a follow-up question (a second round of clarification), the BA removes the label, answers, and re-applies it when done. The workflow guard clause checks for the label's presence at the moment the job runs — it will not re-trigger on label re-application if the Requirements stage has already started.

### Enhancement vs. Greenfield Requests

The Excel intake spreadsheet's Overview tab has a Request Type field: **Greenfield** (a brand-new application) or **Enhancement** (a change to an existing FORGE-built service). This choice affects several stages, not just intake:

- **Stage 0a (Codebase Ingestion)** runs automatically, and only, for an Enhancement request — it reads the target service's existing code and produces an architecture summary (`docs/<request-id>/existing-architecture-summary.md`) that Requirements and Design read alongside the intake spreadsheet. It does not run, and cannot be manually triggered, for a Greenfield request.
- **Implementation, QA, Security, and Deploy** all resolve an Enhancement's real target folder (`services/<existing-service>/`) rather than assuming a brand-new `services/<request-id>/` — an Enhancement's changes land on the existing service, not a new parallel one.
- **Deploy** updates the existing live Container App for that service in place (see Gate 6) rather than standing up a new, parallel set of resources.
- **ADO work items** for an Enhancement are created as Features/User Stories under the *existing* service's real Epic, not a new disconnected one — keeping the backlog attached to the application actually being changed.

For a BA filling out the intake spreadsheet, the only difference is one field (Request Type, plus naming the existing service being enhanced). Everything downstream of that field is handled automatically — there is nothing extra for you to configure per-request, but it's worth knowing this distinction exists so an Enhancement's PRs landing under an existing `services/` folder (rather than a new one) doesn't look like a mistake when you're reviewing a gate.

### Pipeline Depth — Limiting How Far a Request Goes

By default a request runs all the way to Deploy once every gate label is applied. The Excel intake spreadsheet's Overview tab has a second Section B field, **Pipeline Depth**, that lets the BA declare a firm stopping point up front — "I just want the requirements written down," or "stop after Design, I'm not ready to build this yet." Four values, each a **prefix**, not a subset — choosing a tier always runs every stage before it too, in the existing locked order:

| Pipeline Depth value | Runs through | Stops before |
|---|---|---|
| `Just Requirements` | Stage 1 — Requirements (ADO items are still created — see Gate 1) | Design |
| `Up to Design` | Stage 2 — Design (+ the Gate 2.5 cost estimate) | Implementation |
| `Up to Implementation` | Stage 3 — Implementation, and Stage 4/5 — QA + Security (these three share one tier — QA/Security fire automatically off the implementation PR, not a gate you apply) | Deploy |
| `Up to Deployment` *(default — leave blank)* | Stage 6 — Deploy | — nothing, full run |

This is enforced by the pipeline itself, not by you remembering not to apply the next label. If a gate label is applied beyond the configured depth (a misclick, the wrong person, simple forgetfulness), the workflow refuses to invoke that stage: it posts a comment on the tracking issue naming the configured depth and applies `pipeline-complete-at-depth` (see Label Reference), and the job exits clean (no red X — this is expected behavior, not a failure).

The configured depth is captured as soon as the Requirements Agent runs (`docs/<request-id>/pipeline-config.json` on `pipeline-state`) — the earliest point with a durable, downstream-readable location — and every later stage's guard clause reads it before invoking its real agent. A blank or unrecognized value defaults to `Up to Deployment` (full pipeline), so older intake spreadsheets and requests submitted before this field existed behave exactly as before.

**Changing your mind mid-flight:** there is no override label. If you decide a request that stopped at `Up to Design` should actually continue, edit `pipeline-config.json` on the `pipeline-state` branch directly (bump `pipeline_depth` to the tier you want) and re-apply the relevant gate label.

### What Happens at Each Gate

Once the pipeline is running, your job at each gate is to read what the agent produced and decide whether to approve it.

**Gate 1 — Requirements approval:**
The Requirements Agent has produced `requirements.md` (and `ado-work-items.json`) on the monorepo's `pipeline-state` branch — a persistent, intentionally-unprotected branch that holds orchestration state outside of `main`'s branch protection, not a PR against `main` — plus a summary comment on the tracking issue. Read both. If the requirements look correct, apply the label `requirements-approved` to the tracking issue. ADO work items (Epics, Features, User Stories) are created only after this label is applied, reading `ado-work-items.json` from `pipeline-state`.

**Gate 2 — Design approval:**
The Design Agent reads `requirements.md` from `pipeline-state` and has opened a **draft** PR against `design/<request-id>` containing `design.md`, `openapi.yaml`, and `tasks.md`. Review the PR. The Technical Approver reviews the architecture and API contracts. Click **Ready for review** (draft PRs cannot be merged directly), then merge the PR. After merging, apply the label `design-approved` to the tracking issue — this is the actual trigger for Stage 3 (Implementation); merging the PR alone does not start it.

If you edit `design.md` directly on the branch before merging, check that `openapi.yaml` and `tasks.md` still agree with your changes — there's no automated consistency check across the three files. Stage 3 reads all three together; a mismatch (e.g., `tasks.md` describing stale work, or `openapi.yaml` missing a contract your edit now implies) becomes the Implementation Coordinator's problem silently, not a caught error.

**Gate 2.5 — Cost approval:**
Before the Implementation Coordinator's real Managed Agents session starts, a coarse, shape-bucketed cost estimate is posted as a tracking-issue comment (based on unit count from `tasks.md`, plus seed-file count for an Enhancement, scaled against historical baselines). There is no hard threshold — this is purely informative. Read the estimate, then apply `cost-approved` to the tracking issue. Stage 3 requires **both** `design-approved` and `cost-approved` before it starts, the same two-label AND-gate shape as the Deploy trigger in Gate 6. Once Stage 3 completes, the same comment is updated with the actual cost for comparison against the estimate.

**Gate 3 — Implementation review:**
The Implementation Coordinator (a Managed Agents session) has run the Backend, Frontend, and Test Writer subagents in parallel on a shared sandbox filesystem, synthesized their output, committed the complete implementation to `feature/<request-id>`, and opened a **draft** PR. Review the diff. The coordinator has flagged any issues encountered in the PR description, and a per-subagent audit trail is available in the Claude Console alongside the GitHub Actions log. Click **Ready for review** before GitHub will allow the PR to be approved and merged — the coordinator opens it as draft, the same as the Design Agent's PR in Gate 2. Approve or request changes — the coordinator does not merge its own PR, and does not click Ready for review on your behalf.

**Gate 4 — QA sign-off:**
The QA Agent has posted a test report as a PR comment. If all tests pass, the agent applies `qa-approved` automatically — there is nothing for the QA Reviewer to apply manually. Review the report to confirm the pass is real. If failures exist, the agent has already filed ADO bug tickets and the implementation loop restarts. You do not need to act on failures — the loop handles itself unless it exceeds the retry limit (see failure handling below).

**Gate 5 — Security sign-off:**
The Security Agent has posted severity-tagged findings as inline PR comments. A Critical finding has already set a failing check that blocks merge. If there are no Criticals, the agent applies `security-approved` automatically — the Security Reviewer's role is to review the findings and confirm the pass, not to apply the label. After Criticals are resolved and a clean re-scan runs, the label is applied the same way.

**Gate 6 — Production deployment:**
Staging deploys automatically once all prior gates pass **and the feature PR has actually been merged to `main`** — `qa-approved` + `security-approved` being present is necessary but not sufficient; a real merge event is what fires the deploy trigger (`notify-forge.yml` dispatches on merge, and `06-deploy.yml`'s guard clause checks for both the labels and a confirmed merge). Applying both labels before the PR is merged will not deploy anything by itself. To approve production, open the **`production`** GitHub Environment approval request and click **Approve**. The Deploy Agent runs the production deployment.

**For an Enhancement request** (see "Enhancement vs. Greenfield Requests" below), Deploy updates the existing live Container App for that service in place — you will not see a new, parallel set of Container Apps resources spin up.

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
This applies to all stages except Stage 3 (see the Managed Agents entry below for implementation-stage failures). Check the GitHub Actions job log for the failed run. Look for a non-zero exit code in the agent invocation step — six of the seven stages call the base `anthropic` Python client directly (ADR-0011), not the Claude Agent SDK; only Stage 3 uses Managed Agents. Common causes: API timeout (the Anthropic API call exceeded the job timeout), context overflow (the agent's input was too large), or a malformed structured-output response. The job log will distinguish these. For API timeouts and context overflow, reduce the scope of the request. For a malformed response, this is a bug — file an issue in the FORGE template repo.

**A deployed service is crash-looping after Deploy.**
A post-deploy health check runs automatically after every Deploy stage completes, detecting crash loops at the Container Apps revision level and posting a deduped comment on the tracking issue if one is found — you do not need to watch Azure directly to catch this. This mechanism currently only detects and flags a crash loop; it does not yet proactively discover *why* a service needed a secret it wasn't given (a related, still-open gap — see the FORGE template repo's open items list). If you see this comment, check the flagged Container App's revision logs in Azure directly; a common cause is a missing or invalid app secret the Deploy Agent didn't wire (e.g. a connection string), which needs manual correction in Key Vault or `team/config.yaml` followed by a re-deploy.

**The Implementation Coordinator session failed (Stage 3).**
Stage 3 runs as a Managed Agents session rather than a standalone SDK call, so failures here look different. Start with the Claude Console — it provides a per-subagent audit trail (Backend, Frontend, Test Writer) in addition to the GitHub Actions log, and will usually show which subagent failed or where the coordinator's synthesis step broke down. Common causes: a session-level error (the coordinator agent session itself failed to start or was terminated — check for a beta-header or quota issue), a single subagent failure that the coordinator could not work around (check that subagent's portion of the Console trail), a sandbox filesystem conflict during synthesis, or — confirmed as the most common real-world cause so far — the coordinator and its subagents were still genuinely working when the job's completion-detection window ran out (see the entry immediately below; this is not a session failure in the usual sense).

**Do not re-run the coordinator to "retry" a failed Stage 3 job — check whether the session is still alive first.** Confirmed twice against real runs (`DRYRUN-2026-01`, `REQ-2026-02`): a Stage 3 job can exit with a failure while the underlying Managed Agents session is still alive and legitimately working, sometimes for tens of minutes past whatever window the job was watching. Re-running the coordinator in this state starts a second, fully duplicate billed set of agents on top of one that may finish on its own — this has real cost consequences, not just a wasted step. Before considering a fresh invocation:
1. Query the session's current thread status directly (`GET /v1/sessions/{sid}/threads`) rather than trusting the job's own log — the job may have given up well before the session actually finished.
2. If any thread is still running: leave it alone. Do not archive, do not re-invoke. Check back later.
3. If all threads report idle: use `implementation_coordinator.py --recover-session <session-id>` (or the manually-dispatched `03b-recover-implementation.yml` workflow) to complete the normal commit → PR → tracking-comment → archive sequence against the already-finished work, rather than discarding it. This recovery path is real, committed, tested infrastructure as of the `REQ-2026-02` run — it is not a manual workaround to be improvised each time.
4. Only if the session is confirmed genuinely dead (not just slow) — e.g. it errored out rather than continuing to run — is a fresh coordinator invocation the right move.

**A Managed Agents session archive call failed with a "cannot be archived while running" error.**
As of the `REQ-2026-02` fix, `archive_session()` no longer treats this as something to retry through — it only calls `archive` once all threads have been directly confirmed idle via thread-status polling (up to a generous, cost-conscious ceiling; see `_COMPLETION_POLL_TIMEOUT` / `FORGE_IMPLEMENTATION_COMPLETION_TIMEOUT` in `managed_agents_wrapper.py`), with only a small number of short-backoff retries left for genuine transient API flakiness on an already-idle session. If you see this error from current code, it most likely means the ceiling was reached with threads still genuinely busy — see the entry above; this is the "still legitimately working" case, not a transient blip to retry past.

### Infrastructure Failures

**The GitHub App token failed to generate.**
The `FORGE_APP_ID`, `FORGE_APP_CLIENT_ID`, or `FORGE_APP_PRIVATE_KEY` value is wrong or missing, or the app's private key has been rotated. Verify these match the current values shown in the GitHub App settings — note that `FORGE_APP_ID`/`FORGE_APP_PRIVATE_KEY` are repo secrets while `FORGE_APP_CLIENT_ID` is a repo *variable*; a value saved in the wrong one of these two places will fail silently rather than error clearly. If the key was rotated, generate a new one and update the secret. Also confirm the workflow is pinned to `actions/create-github-app-token@v3` (or later) — older major versions expect `app-id` instead of `client-id` and will fail if only the newer variable is set.

**The Azure Container Apps deployment failed.**
Check the deployment logs in Azure. Common causes: the Docker image failed to build (check the build step in the Actions log), the image was pushed to a registry the Container Apps environment cannot reach (check the ACR credentials or managed identity), or the `team/config.yaml` environment names don't match the actual Container Apps environment names in Azure.

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
- [ ] Azure Container Registry provisioned in the organization's Azure subscription; `ACR_LOGIN_SERVER`/`ACR_USERNAME`/`ACR_PASSWORD` updated to the org registry, or replaced with a scoped service principal holding `AcrPush`
- [ ] Container Apps deployment credentials (whatever the Phase 3 Deploy Agent design settles on — likely a service principal or managed identity with Contributor on the Container Apps resource group) established for the organization's subscription
- [ ] Staging and production environments connected to the organization's Azure Container Apps environments in `team/config.yaml`

### Credentials and Access

- [ ] `ANTHROPIC_API_KEY` updated to the organization's API key (not a personal developer account key)
- [ ] `ADO_PAT` evaluated for replacement with an ADO service principal; if keeping PAT, confirm it has an expiry date in the calendar and an owner who will rotate it
- [ ] `FORGE_APP_PRIVATE_KEY` rotation schedule established (rotate at least annually)
- [ ] All secrets stored at repo level (not environment level) unless environment-scoped access is required

### Process

- [ ] At least one BA has completed intake training and successfully submitted a test request through the pipeline
- [ ] At least one Technical Approver has been identified for each gate that requires technical review (Gate 2 — Design, Gate 5 — Security)
- [ ] The Release Approver for the `production` GitHub Environment has been confirmed and has accepted the responsibility
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
| `clarification-pending` | Intake Agent | Status marker only, applied after clarifying questions are posted — nothing listens for it, and it does not need to be removed before `clarification-complete` is applied |
| `clarification-complete` | BA | Triggers Requirements Agent |
| `requirements-approved` | Technical Approver | Writes `requirements.md`/`ado-work-items.json` to the monorepo's `pipeline-state` branch; creates ADO work items; triggers Design Agent |
| `design-approved` | Technical Approver, after merging the design PR | Combined with `cost-approved` to trigger the Implementation Coordinator (Stage 3) — merging the design PR alone does not start Stage 3, and neither label alone is sufficient |
| `cost-approved` | Technical Approver, after reviewing the posted cost estimate | Combined with `design-approved` to trigger Stage 3 — same two-label AND-gate shape as the Deploy trigger below. No hard threshold; purely informative |
| `qa-approved` | QA Agent (applied automatically on a clean pass) | Clears QA gate; combined with `security-approved` **and a confirmed merge of the feature PR** to enable deploy |
| `security-approved` | Security Agent (applied automatically on a clean pass, no Critical findings) | Clears security gate; combined with `qa-approved` **and a confirmed merge of the feature PR** to enable deploy |
| `qc-retry-limit-reached` | QA Agent | Halts pipeline; requires Orchestration Manager triage |
| `pipeline-complete-at-depth` | Any stage-2-through-6 workflow's depth-check step | Marks that the request reached its configured Pipeline Depth and stopped there on purpose — see "Pipeline Depth" above. Not applied again if already present (avoids a duplicate stop comment on a repeat trigger). |

PR events (open, merge) and GitHub Environment approvals handle the remaining state transitions — these are not label-driven. Note that `qa-approved` and `security-approved` alone do not fire Deploy — a real merge of the feature PR to `main` is also required (see Gate 6).

**On `pipeline-state`:** several of the labels above interact with a branch, not just each other. `requirements-approved` causes writes to `pipeline-state`; `design-approved`'s Design Agent reads from it. This branch exists because `main` is protected (required reviewers) to gate real application-code merges, while Requirements-stage writes are orchestration state committed directly, without a PR — protecting `main` meant giving those direct commits a home outside it. See Document 2 §9 for the full traceability-chain diagram reflecting this.

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
| `docs/<request-id>/existing-architecture-summary.md` | Existing-service architecture summary (Enhancement requests only) | Codebase Ingestion Agent (Stage 0a) |
| `docs/<request-id>/requirements.md` | Approved requirements | Requirements Agent |
| `docs/<request-id>/pipeline-config.json` | Configured Pipeline Depth (`{"pipeline_depth": ...}`) — read by every later stage's depth-check guard clause | Requirements Agent |
| `docs/<request-id>/design.md` | Architecture and API design | Design Agent |
| `docs/<request-id>/openapi.yaml` | API contract | Design Agent |
| `docs/<request-id>/tasks.md` | Implementation task breakdown | Design Agent |
| `services/<service-name>/` | Application source code | Backend/Frontend subagents (via Implementation Coordinator) |

### Getting Help

For questions about the core layer or the FORGE platform, open a GitHub Discussion in the FORGE template repo under the **Q&A** category.

For questions about this guide or the Orchestration Manager role, contact the Core Platform Owner.

For Anthropic API, Managed Agents, and base client documentation, refer to the annotated resource list in the AI Foundations Guide (Document 5, Section 9).
