# FORGE Context — v72

**Session date:** 2026-08-29
**Prior doc:** v71
**Prepared by:** Claude.ai, from this session's scoping discussion (no code changes, no live investigation this session)

---

## Purpose & context

Mike Faulkner (Orchestration Manager, Legal Aid Alberta) is building **FORGE** (Full-SDLC Orchestration with Review Gates for Engineers) — an AI-orchestrated software delivery pipeline automating the full development lifecycle from BA intake through deployment.

**Two-repo model (unchanged):**
- `forge-template` (public, `Flamespiker/forge-template`) — orchestration/agent code
- `forge-demo-apps` (private) — target monorepo where generated app code lands

**Firm two-tool convention (unchanged):**
- Claude.ai: strategy, spec authorship, context documents
- Claude Code CLI: live execution, git operations, CLAUDE.md updates
- Mike shuttles between tools and holds all unilateral architecture/scope decisions

**This session's shape:** Short scoping-only session. Mike asked to add a cost estimator to an agent. Rather than write a spec blind, the session narrowed scope through a few clarifying questions before committing anything to a spec — consistent with "surface design forks back to Mike" rather than resolving silently. No live investigation, no code, no spec written yet. This doc captures the scoping decision so the next chat (dedicated to the spec, investigation-first) starts clean.

---

## Current state

Unchanged from v71 except for the addition below. See v71 for full detail on Items #25 (resolved), #26, #27, #28, and all carried-forward items.

---

## New this session — Cost Estimator scoping decision

**Target confirmed: Stage 3 Implementation Coordinator (Managed Agents session).** Mike's own framing — "estimate overall how much it will cost in the Claude session" — points specifically at Stage 3, since it's the only stage billed as an actual session (session-hour billing on top of token costs, per the existing cost table) and the only stage with genuinely unpredictable duration (~1–4 hours estimated, per `README.md`'s cost reference). Other agents (Stages 0–2, 4–6) are single-turn Messages API calls with comparatively predictable, already-logged token costs (`total_cost_usd` via `claude_agent_wrapper.py`'s `_MODEL_RATES` table) — not the intended target.

**Scope decided:**
- **Both** a pre-flight cost estimate (before the session is committed to) and improved post-run reporting of actual cost.
- **Gated with a configurable threshold** — mirroring the existing `qa-approved`/`security-approved` label-gate pattern, not purely informational.

**Open forks flagged for the dedicated spec session (not yet resolved):**
1. **Pre-flight estimate basis** — what grounds the prediction, given Stage 3 is agentic with unknown turn count going in: historical actuals from past runs (App1/2/3), a heuristic off input size (seeded file count, request complexity from intake), or some combination.
2. **Gate mechanism shape** — a new human-applied label mirroring `qa-approved`/`security-approved` (explicit approval step before Stage 3 dispatches), versus an automatic pause requiring a different kind of unblock.
3. **Mid-session behavior** — whether the gate is pre-flight only, or whether actual accumulating cost also gets checked against the threshold *during* a long-running session (and if so, what happens on breach — kill the session, alert only, something else).
4. **Threshold storage/ownership** — team-configurable (`team/config.yaml`, alongside `stack-preferences.yaml`) versus a core-locked default per the Customization Reference's Locked/Flexible/Fully Open split.
5. **Post-run reporting surface** — PR comment, tracking-issue comment, `docs/FORGE-pipeline-cost-log.md`, or some combination.

**Next action: fresh chat, dedicated to this spec, investigation-first** — same pattern as Items #24/#25/#26 (read live `managed_agents_wrapper.py`, the Stage 3 coordinator code, `04-qa.yml`'s label-gate implementation, and `team/config.yaml` before any design fork gets resolved). This is a real new gate mechanism, not a small add — do not fold it into an unrelated spec chat.

---

## On the horizon

- **Cost Estimator spec (Stage 3 Implementation Coordinator)** — newly scoped this session, not yet specced. Next action above.
- **Item #26 (no human gate before Deploy)** — has two live confirmations. Needs its own fresh chat, dedicated to the decision alone, not bundled with a spec. Still outstanding from v71.
- **Item #27, #28 specs** — sequencing TBD, carried from v71.
- **`FORGE-Open-Items-Backlog-v1.md` reconciliation** — still outstanding, now more stale. Needs #25 (resolved), #27, #28 folded in, plus the already-outstanding #24 renumbering note. Next action: fresh chat.
- **Phase 7 Enhancement Workflow validation** — continues; first real Stage 3–6 Enhancement cycle still pending clean Item #26 resolution.
- **Carried forward, unchanged:** Items #1, #7, #9, #10, #11, #12. Item #22's third test case (scale-rule units, still untestable). CLAUDE.md's `user.interrupt` documentation task (carried since v68, still not addressed). Worker Container Apps with no ingress / `rules: null` not auto-scaling to zero (`req-2026-01-email-worker`) — standing infra cost consideration.
- **Standing pre-dispatch discipline (unchanged, worth restating every session given the recurrence):** confirm via the GitHub API (not local git, not verbal confirmation) that any commit is actually present on `origin/main` before flipping any label-driven trigger.

---

## Key learnings & principles (unchanged from v71 — none added this session)

See v71 for the full list. Nothing new this session; this was scoping-only.

---

## Tools & resources (unchanged from v71)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **Azure:** Container Apps (`forge-staging`/`forge-production` environments, `forge-build-rg`), Container Registry, Key Vault (`forge-build-kv`), PostgreSQL Flexible Server (`forge-req2026-03-pg`, stop after each session), Azure AD (`FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`, `C:\Users\mikef\Projects\forge-demo-apps`
- **Cost reference (relevant to the new estimator work):** `claude_agent_wrapper.py`'s `_MODEL_RATES` table (current rates: sonnet-4-6 $3/$15 per MTok in/out, opus-4-6 $5/$25, haiku-4-5 $1/$5, all as of 2026-07-29 per `platform.claude.com/docs/en/about-claude/pricing`); `docs/FORGE-pipeline-cost-log.md`; Managed Agents session cost endpoint for per-request cost data; `README.md`'s cost table (~$0.08–0.32 USD Managed Agents runtime per Stage 3 session, 1–4 hours estimated).
