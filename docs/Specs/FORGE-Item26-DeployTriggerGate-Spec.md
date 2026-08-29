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

## 1. Investigate first (do this before designing anything)

1. **Current `06-deploy.yml`** — re-confirm this session's read above directly
   (`git show`/`view` the live file), including the exact guard-clause step and
   the exact `resolve-feature-pr` call, since this spec's understanding is
   accurate as of a `raw.githubusercontent.com` fetch this session but may have
   drifted or been cached stale (per CLAUDE.md's standing CDN-staleness note —
   re-fetch by commit SHA or via the GitHub API, not a cached `main` ref).
2. **`workflow_glue.py`'s `resolve_feature_pr()` and `list_open_prs_by_head()`**
   — read in full. Confirm whether either function, or any caller, currently
   has access to the feature PR's `merged`/`merged_at` field from the GitHub API
   response (the PR object `get_pr()`/`list_open_prs*` return likely already
   carries this — confirm exactly what fields are available without an extra
   API call).
3. **`notify-forge.yml` in `forge-demo-apps`** — read in full. Confirm its
   current trigger (`pull_request: [opened, synchronize]`, per CLAUDE.md) and
   confirm whether it already listens to `closed` at all today (even if unused
   downstream), since adding `closed` filtered on `merged == true` as a new
   dispatch type is the most direct way to notify `forge-template` the moment a
   feature PR actually merges — the alternative to polling merge status from
   inside Deploy's own guard clause.
4. **Branch protection on `main` in `forge-demo-apps`** — confirm via the
   GitHub API (`GET /repos/Flamespiker/forge-demo-apps/branches/main/protection`)
   whether `main` currently enforces any status checks or required reviews
   before merge, and specifically whether `qa-approved`/`security-approved`
   (or any FORGE-applied state) are wired in as merge conditions today, or
   whether merging to `main` is currently unconstrained (a human can merge
   regardless of FORGE's labels). This determines whether "require merge before
   Deploy" actually adds a meaningful human checkpoint, or whether merge itself
   is already just as automatic/unconstrained as label application is today —
   if the latter, §3's fix still closes the literal gap Item #26 names, but
   Mike should know it doesn't by itself introduce a *human* gate unless branch
   protection also requires manual review.
5. **A currently open, real feature PR** (if one exists at investigation time,
   e.g. anything mid-flight from Item #28's closeout) — use it to confirm empirically
   whether `resolve_feature_pr()` today returns a PR regardless of its mergeable/
   merged state, matching this session's read of the code, not just a code-reading
   inference.
6. **`forge-template#10` / `forge-demo-apps#32`'s current live state** — confirm
   current labels post-Item-#28-closeout (last known: `qa-approved` +
   `security-approved`, PR #32 never merged) — relevant to §5's verification
   plan, since this PR is already sitting in exactly the state Item #26 describes
   as the risk (both gates passed, nothing merged, nothing stopping a Deploy
   re-fire today).

Report findings back before proceeding — in particular §1.3/§1.4, since they
determine which of §3.1's options is actually viable without new plumbing.

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

---

## 3. Design forks (Mike decides — do not resolve silently)

### 3.1 Trigger mechanism — where does "merged" get checked, and what re-fires Deploy at merge time?

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

**Recommendation:** Option A, because it's the only one that guarantees Deploy
re-fires at the moment the missing condition (merge) becomes true, symmetric
with how it already re-fires at the moment each label lands. Final call is
Mike's, pending §1.3's confirmation of `notify-forge.yml`'s current shape.

### 3.2 Staging-only or does this reasoning extend to production?

No production deploy path exists yet (per CLAUDE.md — Phase 5's app never went
past staging), so this is not an active fork today. Flagging only so Mike can
confirm the fix shouldn't be written with a staging-only assumption that would
need revisiting the moment a production path is added — §2's proposed changes
don't need to branch on environment either way, based on this session's read of
`06-deploy.yml`.

### 3.3 Does branch protection need to change too?

Depends entirely on §1.4's finding. If `main` currently allows an unreviewed
merge, requiring merge-before-Deploy closes Item #26's literal gap (Deploy no
longer races ahead of the PR record) but may not add the *human* checkpoint the
item's framing implies, since a merge could still happen without a person
looking at the diff. Mike should decide, once §1.4 reports back, whether
tightening branch protection (e.g. requiring a review approval on `main`) is
part of this item's scope or a separate future item.

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

---

## 6. Sequencing

1. §1 investigation — all six points, reported back before any design commitment.
   §1.3/§1.4 in particular gate §3.1's real options.
2. §3.1 resolved by Mike (with recommendation given, not defaulted silently).
3. §3.3 resolved by Mike once §1.4 reports back.
4. §2.1/§2.2 implemented per §3.1's choice.
5. §5 live verification — **gated on Mike's explicit go-ahead per §5 step 2**,
   given the real first-merge/real-Deploy consequence.
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
