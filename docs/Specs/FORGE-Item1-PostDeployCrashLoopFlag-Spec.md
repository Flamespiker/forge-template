# FORGE — Post-Deploy Crash-Loop Flag (Item #1, Option 3): Spec for Claude Code

**Prepared:** 2026-08-30 (Claude.ai)
**For:** Claude Code CLI session against `forge-template` (new workflow file,
tentatively `.github/workflows/07-post-deploy-health.yml`, plus a small new
module or function reusing existing `deploy_agent.py` unit-resolution logic),
live read access to Container Apps in `forge-build-rg`.
**Context:** Item #1 in CLAUDE.md — `_wire_keyvault_secret()` (2026-08-19) is a
solid *wiring* primitive, but nothing in the pipeline *discovers* that an app
needs a given secret in the first place. Confirmed zero machine-readable
declaration exists anywhere (`.env.example`, `design.md`, `tasks.md`,
`package.json`, agent code). Two directions were on the table this session:
(1) a machine-readable declaration convention Deploy Agent enforces at Stage 6,
or (3) a lightweight, non-blocking post-deploy flag. **Mike chose Option 3.**
This spec does not attempt discovery or prevention — it detects a
secret/config-shaped failure shortly *after* a deploy and surfaces it,
without blocking the pipeline. Item #1's underlying discovery gap remains
open by design; this closes the "silent forever" part of it, not the gap
itself.

**Investigation already done this session (Claude Code CLI, 2026-08-30,
read-only against `req-2026-01-email-worker`) — do not re-investigate, build
on it:**

- **Signal exists and is reliable, one layer down from where you'd first
  look.** Top-level `containerapp` fields (`provisioningState`,
  `runningStatus`) stay healthy-looking. The real signal is at the
  **revision** level: `healthState: "Unhealthy"`, `provisioningState:
  "Failed"`, `provisioningError: "Container crashing: <name>"`. Confirmed
  live against `req-2026-01-email-worker--0000001`.
- **Timing is genuinely unverified for the first-crash case.** The
  investigation's 300s/restart figure is a 4+ day steady-state average
  (consistent with Container Apps' backoff cap, but not independently
  confirmed against Azure's own docs, and not a measurement of *first*-crash
  latency — `logs show` only retains one crash's worth of output, no history
  to measure against). Treat any wait-time number below as a starting
  assumption to validate empirically, not a verified spec.
- **No hook point exists today.** `06-deploy.yml`'s last real step is
  Deploy Agent itself; nothing runs after it; no `workflow_run` trigger on
  Stage 6 exists anywhere in `.github/workflows/`. `run_summary` (which has
  every unit's name post-deploy) is computed but **discarded** on real runs —
  only printed on `--dry-run`. QA/Security Agents structurally can't help;
  they trigger pre-merge, before Deploy ever runs.
- **No persisted, structured report-file mechanism exists anywhere in the
  pipeline** — the cost log is a hand-maintained Markdown ledger, not
  automated. Deploy Agent makes zero Claude/Messages API calls and doesn't
  participate in the `forge_event` JSON-line pattern used elsewhere.
- **Verbatim crash text (for reference, not for pattern-matching in v1 — see
  §3 fork resolution below):**
  ```
  System.FormatException: The connection string could not be parsed; either
  it was malformed or contains no well-known tokens.
  ```

---

## 1. Design forks — resolved this session (Mike delegated the call; decisions and reasoning below, not defaulted silently)

### 1.1 Where does the delayed check live?

**Decision: a new, separate `workflow_run`-triggered workflow — not inline in
Deploy Agent's synchronous path.**

Reasoning: Deploy Agent's own hook point (end of `run_deploy_agent()`, before
`post_pr_comment()`) is real, but checking health inline means Deploy Agent's
own job has to sit and wait for a crash-loop to manifest — adding real wall-
clock time to *every* deploy, including healthy ones, and conflating "did the
CLI call succeed" with "did the app come up healthy," which are genuinely
different concerns today (confirmed: `executed` only reflects the CLI
return code). A separate workflow keeps Deploy Agent's own runtime and
success/failure semantics untouched, and matches this project's existing
pattern of one workflow per pipeline stage rather than folding new concerns
into an existing job.

### 1.2 Polling approach

**Decision: poll at checkpoints (~30s / 60s / 120s / 240s after the new
workflow starts), not a single fixed wait.**

Reasoning: the investigation explicitly flagged the only available timing
data as an average, not a first-crash measurement — a single fixed sleep is a
guess dressed up as a number. Checking at increasing intervals (roughly
matching typical early-backoff behavior) catches a fast-failing app (this
project's actual failure mode so far — a startup-time exception) within the
first checkpoint or two, while still giving a slower-to-manifest failure a
few minutes to show up, without either guessing wrong on a single number or
waiting the full worst case every time. Total ceiling ~4–5 minutes, then
exit cleanly with no flag if nothing unhealthy showed up.

### 1.3 Enhancement "already broken" baseline

**Decision: simple dedupe (skip re-flagging if an open flag already exists
for this unit), not real revision-history comparison.**

Reasoning: `req-2026-01-email-worker` has only ever had one revision — there
is no real precedent in this environment for comparing a new revision's
health against a previous one, and building that comparison is real,
untested work that cuts against the "lightweight" framing Mike chose Option
3 for in the first place. Dedup-by-existing-flag is cruder (it can't tell
"newly broken by this deploy" from "still broken from before"), but it
directly solves the concrete problem raised earlier this session — it stops
a chronically-broken app from generating a fresh noisy comment on every
future deploy. If Mike later wants true causal attribution (new-vs-
pre-existing), that's a real follow-on item, not something to half-build
here.

### 1.4 What signal, and log-content matching — carried over from earlier this session, now settled by the investigation

**Decision: revision `healthState`/`provisioningState` only for v1. No
log-content/exception-string matching in this pass.**

The investigation confirmed the health-state signal is reliable and cheap
(one `az containerapp revision list` call). Log-content matching would add a
second API call, and `logs show` was confirmed to return only the latest
crash's ~30 lines with no history — useful for a human reading the flag, not
essential for detecting it. Recommend including the raw log tail in the
flag's comment body when available (nice-to-have, best-effort, don't fail
the check if the log fetch itself errors), but the trigger condition itself
should be health state alone.

---

## 2. Scope

### 2.1 New workflow: `.github/workflows/07-post-deploy-health.yml`

- Trigger: `workflow_run`, keyed to `06-deploy.yml`'s completion,
  `conclusion == 'success'`. Also add `workflow_dispatch` with a manual
  `request_id`/`unit_name` input, purely so this can be tested against
  `req-2026-01-email-worker` without waiting for or forcing a real deploy
  cycle (see §5).
- Resolve which units belong to this run's `request_id` by **reusing the
  existing `_detect_units()`/`_finalize_unit_name()` logic** already built
  and live-verified under Item #28 — do not re-derive this independently or
  invent new resolution logic. This also avoids needing Deploy Agent to pass
  anything forward, since `run_summary` being discarded (confirmed above) is
  a non-issue if this workflow can re-derive the same unit list on its own.
- For each resolved unit: poll its Container App's latest revision at the
  §1.2 checkpoints. If `healthState == "Unhealthy"` and `provisioningState ==
  "Failed"` at any checkpoint, proceed to §2.2. If no unhealthy state seen by
  the final checkpoint, exit cleanly, no comment posted.

### 2.2 Flag mechanism

- Reuse Deploy Agent's existing `post_pr_comment()`-style comment call (same
  tracking-issue-comment mechanism already proven, not new report-file
  infrastructure) to post a **non-blocking** comment: unit name, Container
  App name, detected health/provisioning state, best-effort raw log tail if
  fetchable, and explicit "flagging for investigation — did not fail the
  pipeline" framing so it can't be misread as a gate.
- **Dedupe per §1.3:** before posting, check the tracking issue's existing
  comments for a marker (e.g. `<!-- forge:crash-loop-flag:<unit_name> -->`)
  already present for this unit; skip posting if found.

### 2.3 Azure auth for the new workflow — investigate before implementing

Confirm whether the same Azure credentials/OIDC federation already used by
`06-deploy.yml` can be reused as-is for a separate workflow, or whether new
federated-credential setup is needed for a `workflow_run`-triggered job
(different trigger context can affect OIDC claims). Report back before
writing any Azure-facing code — this is a real open question, not an
assumption to skip.

---

## 3. Out of scope

- The underlying discovery/prevention gap (Option 1, the declaration
  convention) — explicitly not being built; Item #1 stays partially open
  by design until/unless Mike revisits that direction later.
- Items #7, #9, #10, #11, #12, #15 — untouched, unrelated.
- Log-content/exception-string pattern matching as a trigger condition
  (§1.4) — deferred, not this pass.
- True revision-history "newly broken vs. pre-existing" comparison (§1.3) —
  deferred, not this pass.
- Production deploy path — doesn't exist yet.

---

## 4. Live verification

1. **§2.3 Azure-auth investigation first** — report back before writing the
   workflow.
2. Build `07-post-deploy-health.yml` per §2.1/§2.2.
3. **Test via `workflow_dispatch` against `req-2026-01-email-worker`
   directly** — it's already live and crash-looping, no need to force a real
   deploy to validate detection. Confirm: the workflow correctly detects its
   `Unhealthy`/`Failed` revision state, posts a comment with the right
   content, and — run it a second time — confirms the dedupe marker
   correctly suppresses a second comment.
4. Confirm via the actual posted GitHub comment (not just green workflow
   run) that the flag is genuinely non-blocking — nothing in `06-deploy.yml`
   or downstream stages reads or reacts to this comment/marker.
5. Once validated against the known-broken case, confirm with a real
   Enhancement deploy of a healthy unit that the workflow runs, checks
   cleanly, and posts nothing — no false positives.

---

## 5. Sequencing

1. §2.3 investigation, reported back.
2. §2.1/§2.2 implemented.
3. §4 verification, starting with the known-broken `req-2026-01-email-worker`
   case before any real deploy is used to test the clean/healthy path.
4. `CLAUDE.md` updated: Item #1 marked partially addressed — reactive flag
   shipped and live-verified; proactive discovery (Option 1) explicitly
   still open, not resolved, so a future reader doesn't mistake this for
   the full fix.

---

## Next chat after this one (Claude.ai)

Once Claude Code CLI reports back on §2.3 and completes §4's verification,
fold the outcome into a fresh context doc, updating both CLAUDE.md's Item #1
entry and the Open Items Backlog to reflect the partial-resolution framing
in §5.4 — explicit that discovery/prevention remains a live, open decision
for Mike, not quietly closed alongside the reactive flag.
