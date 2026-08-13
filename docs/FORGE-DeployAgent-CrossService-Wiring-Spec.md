# FORGE — Deploy Agent Cross-Service Wiring Fixes: Spec for Claude Code

**Prepared:** 2026-08-13 (Claude.ai, chat 45)
**For:** Claude Code CLI session against `forge-template` (local clone:
`C:\Users\mikef\projects\forge-template`)
**Context:** Confirmed a 4th time across DRYRUN-2026-01 and REQ-2026-01/REQ-2026-02 —
`deploy_agent.py` has no cross-service wiring mechanism. Two concrete bugs
(missing `NEXT_PUBLIC_API_BASE_URL` build-arg, missing `FRONTEND_ORIGIN`) plus
one related robustness gap (batched build-then-deploy) were found and given a
**verified fix shape** during REQ-2026-02 clean-up, but deliberately not
implemented then (Mike's call, to avoid folding a structural fix into live-
incident work). This spec is that dedicated pre-Phase-6 session.

**Explicitly out of scope for this session:** `resolve_feature_pr()`'s
staleness bug (`workflow_glue.py`, used by `06-deploy.yml`) — different
file/mechanism, no verified fix shape yet, logged separately in the context
doc and Phase 5 close-out doc. Do not touch `workflow_glue.py` in this
session.

**Standing conventions to follow (per `CLAUDE.md` / context doc):**
- Verify against live reality, not this doc — `curl` (or `gh api`) the actual
  current `deploy_agent.py` from `raw.githubusercontent.com` (or read the
  local clone directly, since you have it checked out) before editing. Line
  numbers below are from the last confirmed read (REQ-2026-02 session) and
  may have drifted.
- Windows environment: `shutil.which()` for subprocess calls,
  `encoding="utf-8"` on subprocess readers, no bash heredocs (save scripts as
  files). Git commands in fenced code blocks with the copy button. State
  commit/push steps explicitly — don't just do them silently.
- Commit messages must be verified against actual `git diff HEAD`, not
  intent.
- Fix root causes narrowly; don't silently widen shared logic beyond what's
  specified here.
- Smoke-test each fix individually before moving to the next; commit each
  fix separately (not one combined commit) so history stays legible.
- Report any design fork back to Mike rather than resolving it silently —
  especially anything that changes billing-relevant behavior or touches
  branch protection (neither should be needed here, but flag if you hit
  one).
- Do **not** update the context doc (`FORGE-context_v48.md`) — that's
  Claude.ai's job at the close of this mini-cycle. Do update `CLAUDE.md`
  with what this session actually did/observed, scoped narrowly, per the
  existing convention.

---

## Background: the verified fix shape

`az containerapp env list --resource-group forge-build-rg --query
"[].{name:name, defaultDomain:properties.defaultDomain}"` confirmed
`defaultDomain` is available at the **environment** level (e.g.
`forge-staging` → `yellowmeadow-894377a9.canadacentral.azurecontainerapps.io`),
and every real unit's FQDN observed so far has matched
`f"{unit.name}.{env_domain}"` exactly. This means **a unit's FQDN is fully
predictable before that unit's Container App exists** — there is no
chicken-and-egg ordering problem. This is the shared mechanism all three
fixes below build on.

---

## Fix 1: Missing `NEXT_PUBLIC_API_BASE_URL` build-arg

**File:** `core/agents/utils/deploy_agent.py`, `_docker_build()` (observed at
`deploy_agent.py:345-352` as of the last read — re-verify).

**Problem:** The frontend Dockerfile declares `ARG
NEXT_PUBLIC_API_BASE_URL=""` with an empty default. `_docker_build()` runs a
bare `docker build -f ... -t ... <context>` with no `--build-arg` anywhere.
Next.js bakes `NEXT_PUBLIC_*` vars in at build time, so every deployed
frontend has shipped with an empty base URL — the client's `fetch()` calls
resolve to a same-origin relative path against the frontend container
itself (which has no such route), so Next.js's own 404 HTML page comes back
instead of JSON, and `apiClient.ts`'s JSON-parse fallback surfaces a generic
"An unexpected error occurred." This was a 100%-of-the-time silent failure —
never caught before REQ-2026-02 because prior verification only checked `/`
returns 200, never that the real data fetch succeeds.

**Fix design:**
1. Before building any frontend unit, compute that request's backend unit's
   expected FQDN: one `az containerapp env show --resource-group
   forge-build-rg --name <env-name> --query properties.defaultDomain` call
   (cache the result — do this once per pipeline run, not once per unit),
   combined with the backend unit's already-deterministic name
   (`{request_id}-<backend-unit-suffix>` — confirm exact naming convention
   against `_build_containerapp_command()` or wherever unit names are
   currently generated).
2. Pass the computed FQDN via `--build-arg
   NEXT_PUBLIC_API_BASE_URL=https://{backend_fqdn}` in `_docker_build()`
   when building a frontend unit. Non-frontend units are unaffected.
3. Handle the single-service (backend-only, no frontend) case cleanly — no
   build-arg needed, no error, just skip this logic entirely when there's no
   frontend unit in the request.
4. Handle the case where a request has a frontend but the *environment name*
   lookup fails (e.g. wrong resource group, environment doesn't exist yet)
   — fail loudly with a clear error rather than silently building with an
   empty/wrong base URL again. This bug's whole cost was silence; don't
   reintroduce a quieter version of it.

**Acceptance criteria:**
- Deploy a request with both backend and frontend units to `forge-staging`
  → inspect the built frontend image (`docker run --rm <image> printenv` or
  by pulling the built JS bundle) and confirm the real backend FQDN is baked
  in, not empty.
- Confirm a backend-only request (no frontend unit) still deploys cleanly
  with no behavior change.
- Confirm the computed FQDN matches the backend Container App's actual FQDN
  once it exists (`az containerapp show --query
  properties.configuration.ingress.fqdn`) — this is the empirical check that
  the prediction was right, not just that a build-arg was passed.

---

## Fix 2: Missing `FRONTEND_ORIGIN` on the backend Container App

**File:** `core/agents/utils/deploy_agent.py`,
`_build_containerapp_command()` (observed at `deploy_agent.py:403-438` as of
the last read — re-verify).

**Problem:** No unit, on any request, has ever had `FRONTEND_ORIGIN` set as
an env var on its backend Container App (confirmed via `az containerapp show
... properties.template.containers[0].env` on the live
`req-2026-02-auditor-api` — no such entry). `Program.cs` defaults it to
`http://localhost:3000` when unset, so CORS only ever allows `localhost` — a
real deployed frontend origin gets no `Access-Control-Allow-Origin` header
back at all (confirmed empirically by curling the backend with `-H "Origin:
<real frontend URL>"` and finding the header absent). Even with Fix 1 in
place, a real browser's cross-origin fetch would still be CORS-blocked.

**Fix design:**
1. Using the same predictable-FQDN mechanism as Fix 1 but in reverse: before
   creating/updating a backend unit's Container App, compute that request's
   frontend unit's expected FQDN the same way (env `defaultDomain` +
   frontend unit's deterministic name).
2. Add `--set-env-vars FRONTEND_ORIGIN=https://{frontend_fqdn}` to the
   backend unit's create/update command in
   `_build_containerapp_command()`.
3. Same single-service handling as Fix 1: if there's no frontend unit in the
   request, don't set `FRONTEND_ORIGIN` at all (let `Program.cs`'s
   `localhost` default stand — it's harmless with no frontend to talk to
   it).
4. Confirm this doesn't clobber any other `--set-env-vars` already being
   passed for the backend unit — read the full current
   `_build_containerapp_command()` body before editing, since multiple env
   vars may need to be merged into one command rather than passed as
   competing flags.

**Acceptance criteria:**
- Deploy a request with both units → curl the backend with `-H "Origin:
  https://<real frontend FQDN>"` and confirm
  `Access-Control-Allow-Origin` echoes that exact origin back.
- Confirm a backend-only request still deploys with no `FRONTEND_ORIGIN` set
  and no error.
- Re-verify via `az containerapp show ...
  properties.template.containers[0].env` that the env var is actually
  present on the live resource, not just passed on the command line.

---

## Fix 3: Batched build-then-deploy ordering

**File:** `core/agents/utils/deploy_agent.py`, `run_deploy_agent()`
(observed at `deploy_agent.py:590-626` as of the last read — re-verify).

**Problem:** `run_deploy_agent()` builds+pushes *every* unit in one loop
before running `az containerapp create/update` for *any* unit in a second
loop. One unit's build failure blocks even an already-successfully-built
unit's deploy — this happened for real to REQ-2026-02's backend. Not
strictly required to fix Fixes 1/2 now that FQDNs are predictable without
needing creation order, but a separate, real robustness gap.

**Fix design:**
1. Restructure `run_deploy_agent()` to interleave build+push+deploy **per
   unit**, in one loop, rather than two batched passes (build-all, then
   deploy-all).
2. A failure on one unit's build/push/deploy should not block a different
   unit that already succeeded — each unit's outcome (success/failure)
   should be tracked and reported independently in the final PR
   comment/summary, matching whatever reporting shape already exists for
   partial failures elsewhere in the agent.
3. Confirm this doesn't change the *order in which units are attempted*
   relative to Fix 1/2's FQDN dependencies — e.g. if backend must exist (or
   at least be name-computable) before frontend's build-arg is set, make
   sure the per-unit loop still computes the needed FQDN correctly
   regardless of which unit is processed first (this should already be true
   since FQDNs are name-derived, not existence-derived, but confirm it
   explicitly rather than assuming).

**Acceptance criteria:**
- Simulate or reproduce one unit's build failure (e.g. temporarily break a
  Dockerfile path) in a multi-unit request → confirm the other unit still
  builds, pushes, and deploys successfully, and the failure is reported
  against only the broken unit.
- Re-run a normal two-unit (backend+frontend) request end-to-end → confirm
  no regression versus current behavior when both units succeed.

---

## After all three are done

- Smoke-test each fix independently (per fix, not just once at the end).
- Commit each fix separately: three commits minimum, in fix order (1, 2,
  3), each committed only after that fix's acceptance criteria are
  confirmed against live Azure resources — not just local/unit-test logic.
- Update `CLAUDE.md` with what this session actually did/observed, scoped
  narrowly per the existing convention. Include: exact line numbers touched
  (post-drift-check), the actual `az` commands used to verify each fix
  empirically, and any design forks surfaced to Mike along the way even if
  resolved during the session.
- Do **not** touch `workflow_glue.py` / `resolve_feature_pr()` — separate,
  not-yet-scoped follow-up.
- Do **not** update `FORGE-context_v48.md` — that's this Claude.ai chat's
  job at close, per the standing two-tool convention.
- Next chat after this one (Claude.ai, fresh chat, per one-document-per-chat
  convention): either the branch-naming decision for ad hoc fix PRs, or the
  `request_id` derivation bug — both still open, whichever Mike wants to
  tackle first.
