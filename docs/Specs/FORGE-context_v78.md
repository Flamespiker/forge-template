# FORGE — Session Context v78

**Session date:** 2026-08-30/31 (Claude.ai)
**Carries forward from:** v77, unchanged except where noted below.

---

## What changed this session

### 1. PR #32 stale-doc correction (closed)

CLAUDE.md's Item #28 write-up had drifted: it described the coverage-history
filter's visual sign-in confirmation as "pending a manual sign-in
confirmation from Mike," but Mike had already confirmed it directly in the
v75 session ("visual check is good. new view is there and works nicely").
This was a genuine staleness bug — resolved in one session, then
re-described as open in a later doc revision, the same failure mode already
logged as a standing risk in v77, just recurring one level downstream
(CLAUDE.md itself, not the Open Items Backlog).

**Fixed:** commit `8248e533` on `origin/main` — replaced the stale paragraph
with Mike's real v75 confirmation. No other content in Item #28's write-up
touched.

### 2. Item #1 — Option 3 built and live-verified end-to-end (partially resolves Item #1)

**Decision this session:** of the two directions considered for Item #1
(machine-readable secrets-declaration convention vs. a lightweight
non-blocking post-deploy flag), Mike chose the lightweight flag (Option 3).
Full spec: `FORGE-Item1-PostDeployCrashLoopFlag-Spec.md`.

**What this does and doesn't do — important framing:** this is a *reactive*
mechanism. It detects a secret/config-shaped crash-loop shortly after a
deploy and surfaces it via a non-blocking issue comment. It does **not**
solve Item #1's actual discovery gap — nothing in the pipeline yet knows,
*before* a deploy, that an app needs a given secret. That remains open by
deliberate choice, not oversight.

**Built (3 commits):**
- `4a451a5` — `core/agents/post_deploy_health_agent.py` (new module). Reuses
  `_detect_units()`/`_finalize_unit_name()`/`_az_login()`/`_load_staging_config()`
  from `deploy_agent.py` rather than re-deriving anything. Polls revision-level
  `healthState`/`provisioningState` at 30/60/120/240s checkpoints. Dedupes via
  a `<!-- forge:crash-loop-flag:<unit_name> -->` marker scan before posting.
  Log-tail fetch is best-effort, non-fatal. No log-content pattern matching,
  no revision-history "newly vs. pre-existing broken" comparison — health
  state and dedupe-by-marker only, per spec.
- `bfd98e1` — small addition to `06-deploy.yml` (existing, live workflow):
  two new steps after "Run Deploy Agent" (gated identically to other
  real-deploy-only steps) writing `deploy-context.json` (issue_number,
  request_id, existing_service, commit_sha, pr_number) and uploading it as a
  build artifact. **Deviation from the spec's original assumption** — the
  spec assumed the new workflow could re-derive its unit list independently,
  but a `workflow_run`-triggered job has no way to know which tracking
  issue/request a completed Stage 6 run was for (no request_id→issue_number
  reverse lookup exists anywhere in the codebase). Artifact-passing between a
  `workflow_run` pair is GitHub's own standard pattern for this gap.
- `250b8ae` — `.github/workflows/07-post-deploy-health.yml`. Triggers:
  `workflow_run` off `06-deploy.yml`'s completion (real path) +
  `workflow_dispatch` (manual test path, with `request_id`/`unit_name`/
  `issue_number` inputs).

**Live verification — two full passes, both real, both API-confirmed:**

1. **Manual `workflow_dispatch` against `req-2026-01-email-worker`**
   (known-broken, pre-existing crash-loop from an invalid Service Bus
   connection string — not something this session touched or fixed):
   - Run 1 (`33352062790`): detected `Unhealthy`/`Failed` at the very first
     checkpoint (t=30s). Posted a real comment on issue #2 with correct
     content and marker. Comment count 6→7 (comment ID `5473112169`),
     confirmed via direct API fetch, not log inference.
   - Run 2 (same inputs): correctly found the existing marker and skipped
     posting. Comment count 7→7, confirmed via a fresh API fetch after the
     run.

2. **Real `workflow_run` trigger, via a genuine event replay for PR #32**
   (chosen over a brand-new Enhancement cycle to avoid unnecessary Managed
   Agents cost — see "real-world footprint" reasoning in the spec-follow-up
   session). Confirmed first that re-adding labels to issue #10 would *not*
   produce a real run under the current (post-Item-#26) merge-gated guard
   clause — that technique only worked under the old, pre-merge-gate code.
   Used the same manual `repository_dispatch` replay technique already
   established for Items #15/#17 instead:
   ```
   gh api repos/Flamespiker/forge-template/dispatches -f event_type=pr-merged \
     -f 'client_payload[pr_number]=32' -f 'client_payload[head_sha]=2febc2a34771248c3ed3cffc02da2d1ad9de8aa0'
   ```
   - Run 1 — Deploy (`33352876943`, `repository_dispatch`, success): guard
     clause passed for real (`merged` came from the real event this time,
     not the old label-only check). Real docker build/push/`az containerapp
     update` against both `req-2026-03-on-call-rost-5bb949` and
     `req-2026-03-frontend`. `deploy-context.json` artifact confirmed via API
     (not just log), 278 bytes, downloaded and verified.
   - Run 2 — Health Check (`33353056085`, `workflow_run`, success, started
     8s after Run 1's artifact write): **first-ever real automatic firing**
     of `07-post-deploy-health.yml`'s intended trigger (not manual dispatch).
     Loaded the artifact, resolved both REQ-2026-03 units, polled the full
     4-checkpoint ceiling (nothing was ever unhealthy), posted nothing.
     Issue #10 comment count 17→17, confirmed via a fresh API fetch.
   - **Real finding, worth keeping:** the replay was a byte-identical
     redeploy (same commit, same env-vars) — Azure Container Apps recognized
     it as a genuine no-op and did **not** provision a new revision for
     either app (revision names/timestamps unchanged from 2026-08-29, before
     this replay). No restart/availability blip occurred, which is a safer
     outcome than originally predicted (a brief restart was expected) and a
     useful data point about Container Apps' update semantics for future
     no-op-risk planning.

**CLAUDE.md/backlog update:** dispatched to Claude Code CLI same session —
Item #1 marked PARTIALLY RESOLVED (not fully closed), explicitly stating the
discovery/prevention gap remains open by deliberate choice. Confirm on next
session open that this landed on `origin/main`.

---

## Open items — updated status

- **Item #1:** partially resolved this session (see above). Discovery/
  prevention (the rejected Option 1 direction) remains genuinely open —
  revisit only if Mike decides it's worth building later.
- **Item #12** (cost-log backfill): unchanged, still deferred.
- **Cost Estimator spec:** unchanged, not yet started.
- **`req-2026-01-email-worker` crash-loop:** unchanged, still pre-existing
  and unfixed — now has a working detection/flag mechanism sitting on top of
  it (this session's work), but the underlying invalid Service Bus
  connection string itself was not touched.
- **Phase 7 end-to-end Enhancement Workflow validation run:** arguably
  substantially satisfied as a side effect of this session's Option A replay
  (a real Enhancement-path deploy ran end-to-end, Stage 6 through the new
  Stage 7 health check) — but this was a *replay* of an already-existing
  PR/commit, not a fresh Requirements→Design→Implementation→...→Deploy cycle.
  Still worth a dedicated fresh-request pass if Mike wants the full pipeline
  exercised from intake.

## New this session

- **`.github/workflows/07-post-deploy-health.yml`** now exists as a live
  Stage 7 in the pipeline — real, automatic, non-blocking, running after
  every successful Stage 6 deploy going forward.
- **Event-replay technique for testing merge-gated triggers:** confirmed
  that re-labeling an issue does *not* produce a real Deploy run under the
  post-Item-#26 guard clause (only worked under old, pre-merge-gate code).
  The correct technique is replaying the actual `repository_dispatch` event
  via `gh api .../dispatches` with the right `event_type`/`client_payload`
  — same pattern already used for Items #15/#17. Worth remembering next time
  a merge-gated or event-gated trigger needs re-testing without a brand-new
  PR.
- **Container Apps no-op behavior confirmed:** an `az containerapp update`
  call with byte-identical image tag and env-vars does not provision a new
  revision — useful for predicting whether a given redeploy will cause a
  real restart/availability blip or not.

## Azure infrastructure

Nothing started this session that requires manual shutdown — all activity
was against already-live staging Container Apps (read-only health polling,
plus the one real-but-no-op `containerapp update` pair) and GitHub API
calls. Postgres (`forge-req2026-03-pg`) was not touched or started this
session.

---

## On the horizon (unchanged from v77 except Item #1's reframing above)

- Cost Estimator spec — five open design forks, not yet started
- Item #12 cost-log backfill
- A dedicated Phase 7 validation run from a genuinely fresh intake (if Mike
  wants the full pipeline exercised beyond this session's replay-based test)
- Ongoing Open Items Backlog discipline — this session is itself a reminder
  that CLAUDE.md's own prose, not just the backlog doc, can drift stale
