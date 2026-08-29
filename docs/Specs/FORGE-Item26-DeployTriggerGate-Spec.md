# FORGE — Require Feature-PR Merge Before Deploy Fires (Item #26): Spec for Claude Code

**Prepared:** 2026-08-29 (Claude.ai)
**For:** Claude Code CLI session against `forge-template`
(`.github/workflows/06-deploy.yml`, `core/agents/workflow_glue.py`) and
`forge-demo-apps` (`.github/workflows/notify-forge.yml`, branch protection
settings on `main`), live.
**Context:** Item #26 in CLAUDE.md's Open Items list — confirmed live 2026-08-28
during Item #25's session: no human gate exists between a feature PR opening and
Deploy firing. `notify-forge.yml` dispatches on `pull_request: [opened,
synchronize]`; `04-qa.yml`/`05-security.yml` trigger on that `repository_dispatch`
automatically; `06-deploy.yml` fires the instant `qa-approved` **and**
`security-approved` both land on the tracking issue, gated only by its own
guard-clause step re-confirming both labels are present — nothing in the chain
requires the feature PR itself to have been merged to `main` first. Decision made
(this session, Claude.ai): fix the trigger so Deploy requires the feature PR to be
merged to `main` before firing, aligning behavior with the original intent rather
than deploying an unmerged PR's HEAD commit to staging.

**What this session's live read of `06-deploy.yml` and `workflow_glue.py`
confirms, ahead of Claude Code CLI's own investigation:**
- `06-deploy.yml` triggers on `issues: [labeled]` against the **tracking issue**
  in `forge-template`, gated by `qa-approved`/`security-approved` — it does not
  listen to any `forge-demo-apps` PR event at all.
- It resolves the feature PR's number/head SHA via
  `workflow_glue.py resolve-feature-pr`, which explicitly finds the **currently
  open** PR on `feature/<request_id>` (`list_open_prs_by_head`, per its own
  docstring) — deliberately not anchored to history, but also, as written today,
  never checks whether that PR has been merged. An unmerged, still-open PR
  resolves exactly as successfully as a merged one.
- This means the real fix is not a one-line trigger-condition edit — Deploy's
  trigger lives on the *tracking issue* (`forge-template`), while "merged" is a
  fact about the *feature PR* (`forge-demo-apps`). The fork in §3.1 below is
  about where that fact gets checked, not just how.

**Standing conventions to follow (per CLAUDE.md / context doc):**
- Verify against the live files, not this spec — this spec's reads of
  `06-deploy.yml` and `workflow_glue.py` are current as of this session, but
  `notify-forge.yml` (in `forge-demo-apps`) and branch protection settings were
  **not** independently confirmed here (no authenticated access from this
  session) — §1.3/§1.4 below are genuinely open, not just formality.
- Windows environment: `shutil.which()` for subprocess calls, `encoding="utf-8"`
  on subprocess readers, no bash heredocs.
- Any new failure path follows the ADR-0011 comment-then-reraise contract.
- Report every design fork back to Mike rather than resolving silently — see §3.
- Commit each piece in §2 separately, verified against real `git diff HEAD`.
- Confirm via GitHub API (not local git, not verbal confirmation) that any
  commit is actually on `origin/main` before dispatching anything label-driven.
- Do not touch Items #1, #7, #9, #10, #11, #15, #27, #28 — out of scope here.
- Do not touch Items #24/#25/#28's already-closed Enhancement-target resolution
  logic in `implementation_coordinator.py`, `qa_agent.py`, `security_agent.py`,
  `deploy_agent.py` — this spec only touches the *trigger/gate*, not what Deploy
  does once it runs.

---

## 1. Investigate first — COMPLETE, confirmed live by Claude Code CLI 2026-08-29

1. **`06-deploy.yml`** (HEAD `origin/main` = `7ac6815`, confirmed clean) —
   matches this spec's original read exactly: `issues: [labeled]` trigger,
   guard clause re-fetches the issue and checks both labels before proceeding,
   resolves `request_id` and Item #28's `existing_service`, calls
   `resolve-feature-pr`, checks out `forge-demo-apps` at that SHA, runs
   `deploy_agent.py`. No merge-state check anywhere in the path.
2. **`resolve_feature_pr()` / `list_open_prs_by_head()` / `list_open_prs()` /
   `get_pr()`** — **important finding beyond what this spec anticipated:**
   `list_open_prs_by_head()` and `list_open_prs()` both hardcode
   `state=open` against GitHub's list-PRs endpoint, and a merged PR is always
   `state=closed`. So `resolve_feature_pr()` as written today is **structurally
   incapable of resolving an already-merged PR** — not just untested for merge
   state, but blind to it by construction, since its Step 1/Step 2 fallback
   both only ever see open PRs. By contrast, `get_pr(pr_number)` (single-PR
   fetch, already used by `resolve_tracking_issue()`) works regardless of state
   and its response carries `merged`/`merged_at` directly — confirmed live on
   PR #32 (`"merged": false, "merged_at": null`), no extra API call needed.
   **Design implication for §3.1:** Option A's re-fire step must consume the
   `pull_request: closed` dispatch payload's own `pull_request.number`/
   `pull_request.head.sha` directly, not call `resolve_feature_pr()` — that
   function would find nothing once the PR is closed/merged. Folded into
   §2.1/§2.2 below.
3. **`notify-forge.yml`** (`forge-demo-apps`, fetched live via API) — confirmed:
   trigger is exactly `pull_request: types: [opened, synchronize]`, nothing
   else. No `closed` handling exists today, not even unused — adding a
   `closed`-filtered-on-`merged == true` branch is a clean addition, not a
   modification of existing behavior.
4. **Branch protection on `forge-demo-apps` `main`** (fetched live via API) —
   `required_pull_request_reviews.required_approving_review_count: 1`,
   `required_status_checks.contexts: ["security-check"]` (app_id `4388813`,
   `strict: false`), `enforce_admins.enabled: true` (Item #10's fix still in
   effect), `allow_force_pushes`/`allow_deletions: false`. **This changes
   §3.3's answer:** merge is already a real, enforced human gate — a PR
   cannot merge to `main` without at least one human approval and a passing
   `security-check`, and admins aren't exempt. Requiring merge-before-Deploy
   does introduce a genuine human checkpoint, not merely close the literal
   gap — this spec's original hedge ("may not add the human checkpoint the
   item's framing implies") is resolved: it does.
5. **`forge-demo-apps#32`** (`feature/REQ-2026-04`) — confirmed empirically via
   the same list-PRs-by-head query `resolve_feature_pr()` makes: `state: open`,
   `merged: false`, head SHA `2febc2a3...`, resolves cleanly via Step 1 with no
   merge-state check anywhere in the path. Matches the code-reading inference
   exactly.
6. **`forge-template#10` / `forge-demo-apps#32`** — issue #10 open, labels
   `["qa-approved", "security-approved"]`, both gates present. PR #32 still
   open/unmerged. Confirmed as the live reproduction case: both labels landed,
   nothing merged, today's code would let Deploy fire again right now if
   re-triggered.

§1.3/§1.4 are now both confirmed, unblocking §3.1/§3.3 for Mike's decision below.

---

## 2. Scope (drafted pending §3 forks — do not implement until Mike decides)

### 2.1 Gate Deploy on real merge state

Whichever mechanism §3.1 selects, the end behavior: Deploy no longer proceeds
past its guard clause unless the feature PR's `merged` field is `true` as of
that check. If both labels are present but the PR is still open, Deploy should
**skip cleanly** (same "waiting for the other gate" no-op pattern the guard
clause already uses for the single-label case — not a failure, not a posted
comment, just a quiet skip with a log line) rather than deploy an unmerged
commit.

### 2.2 Re-triggering Deploy once merge happens after both labels already landed

Because QA/Security gate **before** merge (per `04-qa.yml`/`05-security.yml`'s
own header comments, already true today), the realistic sequence is: PR opens →
QA/Security pass and label the tracking issue → human reviews and merges the PR
→ Deploy should now fire. Today's `issues: [labeled]` trigger has nothing to
re-fire on at merge time if both labels already landed before the merge. This is
the crux of §3.1 — the fix needs *some* event tied to the merge itself to
re-enter Deploy's job, not just a stricter check inside a job that only ever
runs on a label event.

**Confirmed by §1.2:** the `pull_request: closed` dispatch payload must supply
the merged PR's number/head SHA directly to `06-deploy.yml` (via whatever
`repository_dispatch` client-payload shape `04-qa.yml`/`05-security.yml`
already use for their own dispatches). `06-deploy.yml` must **not** call
`resolve-feature-pr` when triggered this way — that function only ever sees
open PRs and would find nothing for an already-merged one. It should instead
resolve the tracking issue number from the dispatched PR (via the existing
`resolve-tracking-issue`, which reads the PR body regardless of state) and use
the dispatch payload's own PR number/SHA for the checkout step.

**Additional plumbing gap, request-type-agnostic (applies identically to
Greenfield and Enhancement, since it's mechanism-level, not app-level):**
`06-deploy.yml` currently sets `ISSUE_NUMBER: ${{ github.event.issue.number }}`
at the job level, which only resolves on the `issues: [labeled]` trigger.
`github.event.issue` does not exist on a `repository_dispatch` event —
`06-deploy.yml` needs an early step, run only on the `pr-merged` trigger
path, that calls `resolve-tracking-issue` against the dispatch payload's PR
number and writes the result to `$GITHUB_OUTPUT`, with every subsequent step
(`resolve-request-id`, the guard clause's re-fetch, the Item #28 Enhancement-
status step) referencing that resolved value instead of the job-level
`ISSUE_NUMBER` env var when running on this trigger. Without this, the
`pr-merged` path cannot resolve anything downstream of the guard clause for
either request type — this is not specific to Enhancement requests.

---

## 3. Design forks (Mike decides — do not resolve silently)

### 3.1 Trigger mechanism — RESOLVED by Mike: Option A

**Option A — `forge-demo-apps` dispatches a new event on merge, mirroring the
existing `repository_dispatch` pattern.** Add `pull_request: [closed]` to
`notify-forge.yml`, filtered on `github.event.pull_request.merged == true`,
dispatching a new event type (e.g. `pr-merged`) to `forge-template`.
`06-deploy.yml` gains a second trigger (`repository_dispatch: [types:
pr-merged]`) alongside its existing `issues: [labeled]` trigger, and its guard
clause checks both conditions regardless of which trigger fired this run
(both labels present AND merged) — so whichever of "both labels land" or "PR
merges" happens *last* is what actually fires a real Deploy. Pro: reuses the
exact dispatch mechanism already proven for `04-qa.yml`/`05-security.yml`, no
polling. Con: touches `notify-forge.yml` in the second repo, and `06-deploy.yml`
needs to resolve the tracking issue number from a PR-triggered event the same
way `04-qa.yml`/`05-security.yml` already do via `resolve-tracking-issue`
(existing, proven code path — not new).

**Option B — Deploy's existing guard clause queries merge state directly via
the GitHub API, no new trigger.** Keep `issues: [labeled]` as the only trigger;
the guard clause (or a new step right after it) calls `get_pr()` on the
already-resolved feature PR and checks `merged`. Problem: if both labels land
*before* the human merges, nothing re-fires this workflow once the merge
finally happens later — Deploy would sit permanently skipped with no future
trigger, unless something else re-invokes it. This only works cleanly if merge
is expected to happen *before* both labels land in practice, which is not
guaranteed and arguably backwards from Document 6's designed QA-before-merge
flow. **Not recommended as a complete fix on its own** — flagged because it's
the simplest code change, but likely needs pairing with Option A's re-trigger
regardless, unless Mike's actual intended flow is "merge first, then QA/Security,
then Deploy," which would be a bigger process change than this item currently
scopes.

**Decided:** Option A — it's the only one that guarantees Deploy re-fires at
the moment the missing condition (merge) becomes true, symmetric with how it
already re-fires at the moment each label lands. Implement per §2.1/§2.2,
including §1.2/§2.2's plumbing correction (dispatch payload's own PR
number/head SHA, resolved via `resolve-tracking-issue`, not `resolve-feature-pr`).

### 3.2 Staging-only or does this reasoning extend to production?

No production deploy path exists yet (per CLAUDE.md — Phase 5's app never went
past staging), so this is not an active fork today. Flagging only so Mike can
confirm the fix shouldn't be written with a staging-only assumption that would
need revisiting the moment a production path is added — §2's proposed changes
don't need to branch on environment either way, based on this session's read of
`06-deploy.yml`.

### 3.3 Does branch protection need to change too? — RESOLVED: no, leave as-is

`main` already requires 1 approving review, a passing `security-check` status,
and applies to admins (`enforce_admins: true`) — a real, enforced human
checkpoint exists today independent of this fix. Requiring merge-before-Deploy
therefore genuinely gates Deploy behind that existing human review, not just
behind a formality. Mike's decision: leave branch protection exactly as
configured today — Item #26's fix alone is sufficient, no additional required
status checks on `main`.

### 3.4 Re-verification path

Given `forge-template#10`/`forge-demo-apps#32` is already sitting with both
labels present and PR #32 unmerged (§1.6), it's a ready-made reproduction case
for confirming the *old* behavior (Deploy fires today) versus the *new* behavior
(Deploy skips cleanly until merge) without needing to construct a new scenario.
Mike should confirm whether merging PR #32 for real (to observe Deploy correctly
fire after the fact) is acceptable, given it would be a real, first-ever merge to
`main` in `forge-demo-apps` and a real staging deploy — a live, non-trivial
action, not a reversible test. See §5.

---

## 4. Out of scope

- **Items #1, #7, #9, #10, #11, #15** — untouched, unrelated.
- **Item #27** — untouched; separate, already resolved.
- **Item #28** — untouched; already resolved, this spec doesn't revisit
  Enhancement-target resolution or unit naming.
- Anything about what Deploy *does* once it fires (unit detection, naming,
  Container App identity) — Item #28's closed scope, not reopened here.
- Production deploy path — doesn't exist yet (§3.2).

---

## 5. Live verification

1. Confirm `forge-template#10`/`forge-demo-apps#32`'s exact current label and
   merge state (§1.6) as the baseline.
2. **Before merging PR #32 for real: explicitly confirm with Mike** that doing so
   is acceptable, given it's a real first merge to `forge-demo-apps`'s `main` and
   will trigger a real staging Deploy once the fix is live — same live-consequence
   bar as every other item touching a real resource. Do not proceed without that
   confirmation.
3. With the old (pre-fix) behavior: confirm Deploy does **not** currently
   re-fire or need to — it already fired once when both labels landed (this is
   the documented problem, not something to re-demonstrate destructively).
4. After the fix lands: confirm a fresh guard-clause run (real label event or
   real merge event, per whichever combination §3.1 lands on) correctly skips
   when merge is outstanding, and correctly fires the moment merge completes —
   using either PR #32 itself (if Mike approves merging it) or a fresh
   Greenfield/Enhancement request if a cleaner test case is preferred.
5. Confirm via the GitHub Actions run log and `az containerapp show` (not
   verbal/job-log-only confirmation) that a real Deploy actually ran and
   updated the real live Container App, same evidence bar as Items #24/#25/#28.
6. Confirm no regression to the existing single-label no-op skip behavior
   (only one of `qa-approved`/`security-approved` present) — unaffected by this
   fix, should behave exactly as before.
7. Confirm the `ISSUE_NUMBER` resolution fix (§3.1's plumbing addition) works
   identically for a Greenfield request and an Enhancement request — since the
   gate itself doesn't branch on request type, one real end-to-end run (either
   type) that reaches Item #28's Enhancement-status step successfully via the
   `pr-merged` trigger is sufficient evidence for both; no need to construct a
   second, separate reproduction case purely to prove type-independence.

---

## 6. Sequencing

1. §1 investigation — **complete**, all six points confirmed live 2026-08-29.
2. §3.1 — **decided: Option A.**
3. §3.3 — **decided: leave branch protection as-is.**
4. §2.1/§2.2 — implement per Option A, including §1.2/§2.2's plumbing
   correction (dispatch payload's own PR number/head SHA via
   `resolve-tracking-issue`, not `resolve-feature-pr`, on the `pr-merged` path).
5. §5 live verification — **gated on Mike's explicit go-ahead per §5 step 2**,
   given the real first-merge/real-Deploy consequence. Do not merge PR #32
   without that separate confirmation, even though §3.1/§3.3 are now decided.
6. `CLAUDE.md` close-out: mark Item #26 resolved with the real fix narrative and
   live evidence, same format as Items #24/#25/#27/#28's entries.

---

## Next chat after this one (Claude.ai)

Once Claude Code CLI reports back with §1's investigation findings and Mike's
fork decisions, fold the outcome into a fresh context doc. If implementation and
verification happen in the same Claude Code CLI session (Mike's call, same
one-time-suspension option used for Item #28), close Item #26 in CLAUDE.md and
update `FORGE-Open-Items-Backlog-v1.md` accordingly. Item #27 is already
resolved; no further action needed there.
