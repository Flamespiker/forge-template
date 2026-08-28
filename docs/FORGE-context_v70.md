# FORGE Context — v70

**Session date:** 2026-08-27/28
**Prior doc:** v69
**Prepared by:** Claude.ai, from this session's spec authorship + Claude Code CLI's live execution, incident handling, and root-causing (relayed back into this chat)

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

**This session's shape:** v69's flagged next target — **Item #23 (Stage 3 never extended for Enhancement requests)** — finally tackled. What started as a four-part mechanism fix turned into a genuinely eventful live-execution session: a real self-inflicted incident (Stage 3 triggered against unpushed code, cascading to a real deploy), a clean recovery, a second live surprise (an undocumented Managed Agents API path-rewrite behavior), a proper root-cause via an isolated probe, a six-point pre-flight before the retry, a clean successful run, and — on the very last step — a third, genuinely separate gap discovered downstream (QA/Security have no Enhancement-target awareness at all). This session is a strong example of the project's live-verification discipline actually catching real problems at every layer, not just validating a smooth path.

---

## Current state

**Item #23 is resolved and closed in CLAUDE.md** (recorded there as Item #24, see numbering note below). Full resolution:

- **§2.1 — Enhancement detection + `service_root` resolution.** `03-implementation.yml` gained a "Determine Enhancement status" step mirroring `00-intake.yml`'s existing one. `implementation_coordinator.py` now resolves `service_root` to the real `services/<existing-service>/` folder when `--existing-service` is set, and raises (Layer 2, no silent fallback) if that folder doesn't exist — with a failure comment posted before re-raising, matching the ADR-0011 contract (this comment-before-raise behavior was initially missing, caught, fixed, and given a persisted, re-runnable test).
- **§2.2 — Sandbox population with real existing code.** New `existing_service_files.py` selects and fetches existing-service files via the same noise-filtering used by Ingestion Agent; new `upload_input_file()` in `managed_agents_wrapper.py` plus `resources[]` plumbing seed them read-only into the session. **Deliberate spec deviation, documented in both the module docstring and CLAUDE.md:** file selection is count-based (fits the whole filtered tree when ≤900 files, falls back to manifests + largest-by-size near that ceiling) rather than reusing Ingestion Agent's ~60k-character budget — that budget exists because Ingestion Agent's output becomes LLM prompt tokens, whereas these files are mounted to disk for on-demand reading, so a character-based truncation would risk handing subagents an incomplete, unbuildable copy for no real savings. Real App1/2/3 file counts (99/70/89) confirmed the 999-resource ceiling is non-binding today.
- **§2.3 — "Related service" cross-reference line.** Added to the PR body and tracking-issue comment (and the recovery path) when `--existing-service` is set; omitted entirely on Greenfield runs. Confirmed present and correct on the real verification PR.
- **§2.4 — Intake-template dropdown safeguard.** `docs/Intake Template.xlsx` Overview!C13 now has Excel data validation listing `REQ-2026-01`/`02`/`03`; placeholder text and layout untouched.

**Live verification: PR #32** (`Flamespiker/forge-demo-apps`, `feature/REQ-2026-04`, commit `2febc2a`). Coordinator's own real first-turn actions (checked via actual session thread events, not message text) confirmed it found the seeded files, explicitly concluded "the existing service has both backend and frontend" (Enhancement, not Greenfield), copied 87 files into the writable `services/REQ-2026-03/`, then read the real existing code (`AuditRepository.cs`, `UsersController.cs`, `AuditTable.tsx`, etc.) before building. Resulting PR: 19 files touched, all under `services/REQ-2026-03/` — a mix of small surgical diffs to existing files and genuinely new files (`AuditFilterPanel.tsx`, `useUsers.ts`, new tests) implementing REQ-2026-04's actual ask (staff/date-range filtering on the existing audit log). Zero files under `services/REQ-2026-04/`. "Related service: services/REQ-2026-03/" present on the PR body as designed.

**Not resolved, deliberately, as newly-discovered downstream gaps (see On the horizon):**
- QA passed PR #32, but as a **false positive** — it looked for tests under the nonexistent `services/REQ-2026-04/` and its existing "not applicable" handling silently converted that into a pass.
- Security **crashed** (`FileNotFoundError`) on the same nonexistent-directory problem, with no graceful handling at all.
- Deploy correctly did **not** fire — its guard clause requires both `qa-approved` and `security-approved`, and only the (false-positive) `qa-approved` landed.

**Issue #10 and PR #32 are deliberately left in their current state** (`qa-approved` only, OPEN, unmerged, undeployed) as live evidence of the newly-discovered QA/Security gap — not cleaned up, per the same reasoning applied to PR #31 earlier in the session.

---

## This session's work, in order

### 1. Spec written: `FORGE-Item23-Stage3-Enhancement-Spec.md`

Investigation-first structure: six things to verify live before any design was finalized (current `03-implementation.yml`/`implementation_coordinator.py` behavior, coordinator vs. subagent tool scoping, whether Managed Agents supports seeding sandbox files, `workflow_glue.py`'s existing download/parse subcommands, and GitHub tracking issue #10's live state). Two design forks deliberately left open rather than guessed at: how Stage 3 learns the existing-service value (recommended: mirror `00-intake.yml`'s spreadsheet re-download, over embedding it in `design.md`), and the sandbox-population mechanism itself (genuinely unknown pending investigation).

### 2. Sandbox-population fork resolved via live investigation

Claude Code CLI confirmed `sessions.create()`'s `resources[]` mechanism (Files API upload → mount at an absolute `mount_path`, resolved before the agent's first turn) — but surfaced a real, unanticipated constraint: file resources mount **read-only**, so existing-service code cannot be mounted directly at the writable `service_root`. Resolved design, explicitly flagged back to Mike before building rather than assumed: reuse the existing `SHARED_DOCS_DIR` pattern — mount read-only at a separate reference path, have the coordinator's step 0 copy into the real writable `service_root` before subagents edit, with all four prompts updated accordingly. Mike confirmed; this became the built design.

### 3. Incident #1 — Stage 3 triggered against unpushed code, cascaded to a real deploy

Claude Code CLI applied `design-approved` on issue #10 before pushing its §2.1–§2.4 commits to `origin/main`. GitHub Actions runs off the remote, not local commits, so the run executed the **old, unfixed** coordinator — reproducing Item #23's exact bug live: a whole duplicate On-Call Roster Tracker built from scratch under `services/REQ-2026-04/` instead of editing `services/REQ-2026-03/` (PR #31). QA and Security both passed against this wrong build (the code itself compiled and had tests, even though it was the wrong artifact), and Deploy auto-fired — a real Azure Container App (`req-2026-04-on-call-rost-ef23ba`) ran live and billable until caught. Frontend deploy failed to build, so no frontend Container App existed.

**Recovery, explicitly sequenced rather than bundled:** push the real fix immediately; decommission the Container App immediately (the only piece with an active cost meter, independently re-verified via a fresh `ResourceNotFound` lookup); leave PR #31, the branch, and the `qa-approved`/`security-approved` labels for Mike to review and clear manually on his own schedule, rather than have Claude Code CLI clean up evidence of its own mistake unilaterally. Mike reviewed, closed PR #31 (not merged), deleted the branch, and cleared both labels via the GitHub UI before any retry was authorized.

### 4. Incident #2 — undocumented Managed Agents API mount-path rewrite

Re-triggered Stage 3 off the correctly-pushed fix. Per Mike's explicit ask, Claude Code CLI verified early via the session's **real attached resources** (not just prompt text) and found all 87 seeded files had landed at `/mnt/session/uploads/existing-service/...` — not `/mnt/session/existing-service/...` as every prompt specified. The Managed Agents API silently inserts an `uploads/` segment after `/mnt/session/` for `type: "file"` resources — undocumented behavior no mock harness could have caught, since mocks never touch the real API. Practical effect if unfixed: the coordinator would have found nothing at the path it was told to check, concluded Greenfield, and rebuilt from scratch again — this time writing directly into the real `services/REQ-2026-03/` folder, arguably worse than Incident #1.

**Handling:** killed the session immediately via the documented manual-kill procedure (interrupt → confirmed all 4 threads idle → confirmed no `implementation.tar.gz` existed yet, nothing lost → archived session/environment/coordinator/all 3 subagents, all 6 confirmed via real `archived_at` timestamps). Root-caused properly rather than patching on guesswork: ran a minimal, near-zero-cost isolated probe (one throwaway agent/environment/session, three file resources with different requested paths, no `initial_events` so no model turns billed) and confirmed the exact rule — `uploads/` is always inserted after `/mnt/session/` unless the path already starts with `/mnt/session/uploads/`. Fixed `EXISTING_SERVICE_MOUNT_DIR` to the corrected path as a single constant; re-ran the mock harness with corrected expectations; pushed (`45325be`); independently confirmed via GitHub's API that `origin/main` carried the fix.

### 5. Six-point pre-flight before the third trigger attempt

Given two live surprises already, Mike required a firm pre-flight before spending money a third time. All six confirmed, not assumed:
1. `SHARED_DOCS_DIR` unaffected by the same rewrite — confirmed via a real historical session's actual `resources: []` field and real tool-call history (different mechanism entirely; never uses `resources[]`).
2. Zero stray unprefixed path literals anywhere outside the constant's own definition (one explanatory comment, one pre-discovery planning doc — neither executable).
3. The Layer-2 comment-before-raise fix now has a real, persisted test exercising the actual entry point, not just a diff — confirmed passing (9/9 total assertions).
4. No stray branch or PR from the killed session — confirmed via a fresh search, not inferred from the earlier "no tarball existed" finding.
5. Issue #10's label state re-confirmed fresh via the API immediately before the label flip.
6. **No pause point exists anywhere between Stage 3 and Deploy** — confirmed by reading the live workflow files directly (`notify-forge.yml`, `04-qa.yml`, `05-security.yml`, `06-deploy.yml` all auto-dispatch on labels/PR events with no human-click gate). Given this, Claude Code CLI committed to reporting at each stage transition (seeded-files-confirmed, PR-opened) rather than waiting for full completion.

### 6. Third trigger — clean success

Re-applied `design-approved`. Confirmed via real session thread events (not prompt text) that the coordinator found the 87 files at the corrected path, explicitly reasoned "the existing service has both backend and frontend," copied them into the writable `service_root`, and read the real existing code before building. PR #32 opened: 19 files, all under `services/REQ-2026-03/`, a real scoped diff matching REQ-2026-04's actual functional ask. "Related service" line correct on the PR body.

### 7. Downstream discovery — QA/Security have no Enhancement-target awareness

While watching for further transitions per the pre-flight's own commitment, QA passed (false-positive — looked in the nonexistent `services/REQ-2026-04/`, its "not applicable" handling silently converted the missing directory into a pass) and Security crashed (`FileNotFoundError`, same missing-directory root cause, no graceful handling). Deploy correctly did not fire (guard clause requires both labels; only one landed). Explicitly logged as new backlog items rather than fixed in-session, per standing "new discoveries get surfaced and decided by Mike before anyone touches them" convention.

### 8. Committed and closed

`ca9ef7c` (§2.4), `bf647a4` (§2.1+§2.2), `4b4420c` (§2.3), a Layer-2-test-fix commit, `45325be` (mount-path fix) — all on `origin/main`. `5edd643` — CLAUDE.md updated: Item #23 marked resolved (recorded as **Item #24** due to a numbering collision — CLAUDE.md's own backlog already had an unrelated #23, "no on-demand way to verify a service's language build/Docker build outside the full pipeline," resolved 2026-08-26 via `verify-build.yml`, PRs #28/#29 — entirely unrelated, pure coincidence of numbering between the two independently-maintained backlogs), plus two new items: **#25** (QA/Security Enhancement-target gap, both halves documented separately with real evidence quoted) and **#26** (no human gate before Deploy — the architectural condition that let Incident #1 cascade as far as it did, logged as its own distinct finding).

---

## Key learnings & principles (new/updated this session)

- **A resolved spec's own design can still have a real, unanticipated constraint hiding in the actual API** — the read-only-mount behavior wasn't guessable from documentation alone and reshaped §2.2's design mid-session. Confirming a mechanism *exists* is not the same as confirming its *shape* matches what the design assumes.
- **The single most expensive mistake this session was procedural, not technical**: flipping a label before confirming a push landed on the remote. GitHub Actions always runs off `origin`, never local state — this is now a standing thing to explicitly double-check before any label-triggered stage, not just assume.
- **Mock harnesses that never touch the real API can pass cleanly on a wrong assumption about undocumented API behavior.** This isn't a knock on writing mocks — it's a reason to distinguish, in verification language, "mocked-clean" from "live-confirmed" for anything touching an external API's real, possibly-undocumented behavior. The mount-path rewrite is the concrete example: 8/8 mock assertions passed while the real path was wrong the whole time.
- **A cheap, isolated, near-zero-cost probe is the right tool for root-causing a live API surprise** — three throwaway resources, no billed model turns, immediately cleaned up — rather than guessing at a fix from the failure message alone, or burning a full paid session to observe the same thing.
- **A six-point pre-flight, each item independently verified rather than assumed from memory, is the right bar after two live surprises in one session** — every one of the six items came back as a real check against live state (a real historical session's resource field, a real grep, a real persisted test, a real branch/PR search, a fresh label check, a real read of the workflow files), not a restatement of earlier claims.
- **Cleanup of Claude Code CLI's own mistake was deliberately not self-directed** — pushing the fix and killing the cost-bearing resource happened immediately, but reviewing/closing the human-facing artifacts (PR, branch, labels) was left to Mike on his own schedule. The same asymmetry as always: fix what's actively costing money now, defer anything a human might want to look at first.
- **A fix landing correctly at its own stage doesn't mean the surrounding pipeline was updated to match** — Stage 3 now understands Enhancement targets; Stage 4/5 do not, and the gap manifested as two different failure shapes (a silent false-positive pass vs. a loud crash), which is itself informative: the crash is the ADR-0011 pattern working as intended, while the false-positive pass is the pattern's opposite, and needs closing specifically, not just extending awareness.

---

## On the horizon

- **Item #25 (QA/Security Enhancement-target gap) — next real spec target.** Needs Stage 4/5 to gain the same Enhancement-target-resolution concept Stage 3 now has, plus QA's missing-directory case specifically needs to fail loud rather than silently pass — that's a distinct fix from "add awareness," since the current pass-on-missing-directory behavior is a real hole in the fail-loud pattern everywhere else in the project. **Next action: fresh chat, per one-doc-per-chat convention.**
- **Item #26 (no human gate before Deploy) — a real Document 6 architecture question for Mike**, distinct from #25. Deploy fires the instant `qa-approved`+`security-approved` land, with no PR-merge requirement and no human-click gate anywhere in the chain — proven twice now to matter (Incident #1's real deploy of wrong code). Needs Mike's decision on whether/how to add a pause point, not a unilateral fix.
- **`FORGE-Open-Items-Backlog-v1.md` (the standalone Claude.ai-maintained doc) needs reconciling** with CLAUDE.md's numbering: the old "#23" there is what CLAUDE.md now calls #24 (Enhancement targeting), and #25/#26 need adding. **Next action: fresh chat.**
- **Issue #10 / PR #32 deliberately left as-is** (`qa-approved` only, OPEN, unmerged) — do not touch, merge, close, or clear labels until Item #25's fix is decided and built; it's the live evidence of the gap.
- **PR #31 / stale branch / Container App from Incident #1** — already fully cleaned up (PR closed not merged, branch deleted, Container App decommissioned and independently reconfirmed gone, labels cleared). Nothing further needed there.
- **Carried forward, unchanged:** items #1, #7, #11, #12; Item #22's third test case (scale-rule units, still untestable). CLAUDE.md's `user.interrupt` documentation task (carried since v68) — not addressed again this session; worth checking whether Incident #2's real kill sequence was itself recorded anywhere that would satisfy this.
- **New standing-cost-awareness note:** this session directly demonstrated that a wrong Stage 3 run can produce a real, billable Azure Container App within minutes of a label flip, with no human gate in between. Worth keeping in mind for how urgently any future "the run looks wrong" observation should be acted on.

---

## Tools & resources (unchanged from v69 except where noted)

- **Repos:** `Flamespiker/forge-template` (public), `Flamespiker/forge-demo-apps` (private)
- **Azure:** Container Apps (`forge-staging`/`forge-production` environments, `forge-build-rg`), Container Registry, Key Vault (`forge-build-kv`), PostgreSQL Flexible Server (`forge-req2026-03-pg`, stop after each session), Azure AD (`FORGE-DemoApps-SSO`, client ID `b59886c1-12ac-42c1-895f-5fafa8e57318`, tenant `af2dd50c-3bc0-4e26-9973-e3af4b64dbf9`)
- **New this session:** `FORGE-Item23-Stage3-Enhancement-Spec.md`; `existing_service_files.py`; `upload_input_file()` in `managed_agents_wrapper.py`; `EXISTING_SERVICE_MOUNT_DIR` constant (`/mnt/session/uploads/existing-service`); real, live PR #32 sitting open as evidence
- **Decommissioned this session (evidence of Incident #1, now fully cleaned up):** Container App `req-2026-04-on-call-rost-ef23ba`; PR #31; branch `feature/REQ-2026-04` (first instance — note the same branch name was reused for the successful PR #32 run)
- **ADO:** `dev.azure.com/spike99`, project `FORGE-Build`
- **GitHub App:** `forge-pipeline` (App ID `4388813`), installed on both repos
- **Mike's local paths:** `C:\Users\mikef\Projects\forge-template`, `C:\Users\mikef\Projects\forge-demo-apps`
