# FORGE — Phase 5 Close-Out

**Phase:** 5 — App 1 real greenfield build (first fully-automated, non-manual pipeline run)
**App:** Inactive User & License Auditor (`REQ-2026-02`) — read-only Dynamics 365 Dataverse admin tool
**Window:** 2026-08-10 (chat 40, planning) → 2026-08-12 (chat 43, D365 wiring + close-out)
**Status at close:** App fully working end-to-end in a real browser against real Dataverse data (license-status report, descoped per R-001 below). Azure/D365 resources for this app are being decommissioned immediately following this doc — see Decommission Note at the end.

---

## 1. Goal and Scope

Phase 4 wired the pipeline's automation (label-triggered GitHub Actions, real agent invocations). Phase 5's job was to prove the pipeline could run a **genuinely new request start-to-finish with zero manual stage invocation** — `REQ-2026-01` didn't count, since every one of its stages had been run by hand during Phase 3.

App 1 was deliberately chosen small and single-service (Dataverse Web API read query + a Next.js dashboard, no write-back) specifically to avoid exercising the already-known Deploy Agent cross-service wiring gap while still being a real, useful app for LAA.

## 2. What Actually Shipped

- Requirements, ADO Epic → Feature → User Story traceability, design doc, implementation (coordinator + Backend/Frontend/Test Writer subagents), QA, Security, and Deploy all ran for real through the label-triggered automation.
- Final feature set: a license-status report listing D365 accounts and their license assignment, sortable/filterable, with CSV export. **Inactivity detection (90+ day threshold) was formally descoped** — see R-001 below — so the shipped app is narrower than the original intake ask.
- Both backend and frontend deployed live to `forge-staging` and were confirmed working in a real browser (data loading, CSV export functioning) — the first time this project's frontend has gotten that far.

## 3. The R-001 Descope — A Real Precedent

Mid-build, metadata investigation against the live Dataverse environment confirmed `systemuser` has no login/logon/last-activity concept in this tenant at all — not a misnamed field, a genuinely absent one. Graph API `signInActivity`, a custom Dataverse field, or Dataverse audit history were named as real alternatives, but none were built; this needs a design decision outside Phase 5's scope.

Mike's call: descope R-001 (inactivity detection) for this phase, ship license-status only. Handled as an informal ADO description edit with a scope note rather than a formal change-request process — the first live instance of the standing "requirement changes after ADO approval" open question. The original intake spreadsheet was deliberately left unedited as the historical record of what was actually asked; the descope lives in the ADO item and the context doc instead. The fix was run through the full pipeline as a real feature PR (#18), not a manual bypass, specifically to set a real precedent for future requirement changes.

## 4. Real Gaps and Bugs Found (Confirmed, Not Fixed This Phase)

This run surfaced more structural gaps than any prior phase — worth reading as validation that a full, uninterrupted run finds problems dry-runs and manual invocation don't:

1. **Deploy Agent has no cross-service wiring mechanism — confirmed a 4th time, with two brand-new instances found live this phase:**
   - `_docker_build()` never passes `--build-arg`, so `NEXT_PUBLIC_API_BASE_URL` has silently baked in empty on every frontend deploy this pipeline has ever done — undetected because prior verification only checked `/` returns 200, never that the real data fetch succeeds.
   - The backend never gets `FRONTEND_ORIGIN` wired, defaulting to `localhost:3000` — would CORS-block any real browser even with the above fixed.
   - Both now have a **concrete, verified fix shape** (Container Apps FQDNs are predictable from the environment's `defaultDomain` before the target Container App exists, confirmed empirically), plus two related findings: batched build-then-deploy (one unit's build failure blocks an already-built unit's deploy) and `resolve_feature_pr()` anchoring to the original coordinator comment (can't find a newer follow-up PR for an already-implemented request).
   - **None implemented this phase** — Mike's explicit call to defer even the now-easy fixes to a dedicated pre-Phase-6 session rather than fold them into live-incident work.

2. **Stage 6 had silently never auto-triggered for any past request, until this phase.** Root cause: `qa_agent.py`/`security_agent.py` apply their own approval labels using the default `GITHUB_TOKEN`, and GitHub Actions' anti-recursion rule never lets a `GITHUB_TOKEN`'s own actions trigger a new workflow run. Every past "successful" deploy had actually been triggered by a human manually applying the label. **Fixed and verified this phase** (the GitHub-App-token fix).

3. **`04-qa.yml`/`05-security.yml`'s `request_id` derivation breaks on `feature/*` branches with a suffix** beyond the bare request ID — caused a real Security crash and a QA false positive on PR #18. Logged, not fixed.

4. **`06-deploy.yml`'s auto-trigger can't find a follow-up feature PR** for a request already through Implementation once — resolved to the stale original PR instead of the new one. Logged, not fixed. Possibly shares a root cause with the `resolve_feature_pr()` gap above.

5. **`DataverseUserRepository.cs` collapses network failure, timeout, and any non-2xx HTTP response into one identical generic exception**, discarding the real status/body — caused a red-herring `DATAVERSE_UNAVAILABLE` error that was actually a clean `400` with a useful message underneath. Logged, not fixed.

6. **`notify-forge.yml`'s `synchronize` trigger can't distinguish an app-code push from a non-app-code cleanup push** — cost a real QA retry attempt when deleting dead CI workflow files re-triggered QA/Security unnecessarily. Logged, not fixed.

## 5. Manual Intervention Required

An honest count, since this was meant to be a hands-off run:

- **D365 secret wiring** — always planned as a manual post-deploy step (Deploy Agent has no secrets-injection mechanism), not a deviation.
- **Metadata investigation detour** — required a throwaway local script run entirely on Mike's machine (never touching either chat) after `az containerapp exec` proved unreliable, plus working through a URL-encoding bug and a Dataverse API grammar limitation.
- **Four ad hoc admin-merges** (PRs #7, #8, #11, #16) for mechanical fix branches that hit the permanently-unsatisfiable `security-check` + no-review combination on non-`feature/*`/`design/*` branches. This phase alone accounted for one of the four (PR #16). **Still not resolved as a standing decision** — genuinely overdue.
- **Two manual one-off Azure patches** (frontend build-arg, backend `FRONTEND_ORIGIN`) applied directly to the running Container Apps, deliberately not folded into `deploy_agent.py` — will need reapplying on any future redeploy of this app, or of any other request's frontend unit, until the root fix lands.
- **ADR-0008 filled in** (was a stub since initial repo setup) — real content grounded in existing project reasoning rather than generic boilerplate.

## 6. Cost and Timing (Partial — Known Gap)

- Stage 1 (Requirements): $0.053832 confirmed.
- Stage 3 (Implementation, Managed Agents): ~37 min wall-clock (`active_seconds: 2218.4`), ~$6.63 — pulled directly from the session cost endpoint, confirming that field is reliable. Consistent with `REQ-2026-01`'s earlier 38.5–55.2 min range, not an outlier.
- Stage 4 (QA): $0.013425 partially captured.
- **`docs/FORGE-pipeline-cost-log.md` was not fully updated with these figures during the phase** — flagged then, still outstanding now. A dedicated pass is needed before Phase 6 to have a real cost baseline.

## 7. Go / No-Go Read for Phase 6 (App 2)

**Read: proceed, with pre-work.** The pipeline can run a real request end-to-end with zero manual stage invocation — that was Phase 5's actual goal, and it's now demonstrated. But this run needed substantial manual intervention (Section 5) to get to a genuinely working app, and several of the gaps found (Section 4) are structural, not one-off. Recommended before Phase 6 starts:

- Implement the now-verified Deploy Agent cross-service wiring fixes (build-arg, `FRONTEND_ORIGIN`, build-order) — App 2 is not guaranteed to be single-service, and this gap is now confirmed on its 4th occurrence.
- Decide the branch-naming convention for ad hoc fix PRs (4 admin-merges is a real recurring cost, not a one-off).
- Fix or at least scope the `request_id` derivation and `resolve_feature_pr()` bugs if App 2 is likely to need a post-implementation follow-up PR (R-001's descope pattern may recur).
- Update the cost log with real Phase 5 figures as an actual baseline.

## 8. Carried Forward, Not Resolved

- Deploy Agent cross-service wiring fixes (verified shape, not implemented).
- `request_id` derivation bug, `resolve_feature_pr()` staleness bug.
- `DataverseUserRepository.cs` exception-collapsing.
- `notify-forge.yml` synchronize-trigger over-firing.
- Branch-naming convention for ad hoc fix PRs.
- Cost log update.
- Document 6's stale "do not resume a failed session mid-stage" guidance, which contradicts the now-multiply-proven recover-and-reattach practice used during Stage 3 recovery.
- Security Agent's scanner-failure-still-approves gap (never triggered this phase — no scanner actually failed — but still open).

## 9. Decommission Note

Per Mike's decision, `REQ-2026-02`'s live Azure and D365 resources are being torn down immediately following this document, rather than kept pending further close-out material — this document is being written from what was already recorded in the context doc and `CLAUDE.md`, with no new screenshots or live data pulled first. The code in `forge-demo-apps` (`services/req-2026-02-...`) is retained; only the running cloud infrastructure and the D365 connection are removed. See the separate teardown checklist for the exact steps and their verification.
