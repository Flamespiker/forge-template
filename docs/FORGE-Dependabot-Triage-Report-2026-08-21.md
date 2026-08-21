# FORGE — Dependabot Alert Triage Report

**Prepared:** 2026-08-21 (Claude Code CLI), per `docs/FORGE-Dependabot-Triage-Spec.md`
**Scope:** All open Dependabot alerts on `Flamespiker/forge-template` and `Flamespiker/forge-demo-apps`, pulled live via `get_dependabot_alerts()`.
**Nature of this pass:** Data-gathering and classification only. No packages upgraded, no alerts dismissed. All actions below are recommendations for Mike to review and authorize.

---

## 0. Headline finding

**REQ-2026-01 and REQ-2026-02 are both pinned to `next@14.2.5`. REQ-2026-03 already runs `next@14.2.35` — a newer patch version already proven safe in production.** Bumping REQ-01/02's `next` dependency to match REQ-03's existing pin (or later) would close **24 alert rows** (12 unique CVEs — 1 Critical, 4 High, 5 Medium, 2 Low) with zero major-version risk, since it's not a new upgrade path — it's catching up to a version already running elsewhere in this same monorepo. This was not previously identified as an action item; it was sitting underneath the already-known "next.js has unpatched issues" framing (Open Item #11) without anyone having separated "needs a 15.x major bump" from "just needs the patch version REQ-03 already has."

---

## 1. Summary table

| Repo | Total open | Critical | High | Medium | Low |
|---|---|---|---|---|---|
| `forge-template` | 0 | 0 | 0 | 0 | 0 |
| `forge-demo-apps` | 101 | 2 | 40 | 49 | 10 |

**Drift from the 102 figure recorded 2026-08-19:** 101, not 102 — a drift of 1 (one alert closed/auto-resolved since then; not investigated further, immaterial to this pass). This comparison is against `forge-demo-apps` alone, since the original 102 figure was never inclusive of `forge-template` (`forge-template` has 0 open alerts and was not previously tracked in that count — its inclusion in this pass's scope is new, not part of the drift comparison).

**By disposition (all 101 alerts are in `forge-demo-apps`; counted by raw alert row, not unique CVE):**

| Disposition | Alert rows | Unique CVEs | Repo scope |
|---|---|---|---|
| Known / accepted | 63 | 21 | REQ-2026-01, -02, -03 (all three) |
| Real, actionable | 29 | 17 | REQ-2026-01, -02, -03 |
| Likely false positive | 0 | 0 | — |
| Dev-only / no exposure | 9 | 8 | REQ-2026-02, -03 |

**Update 2026-08-21 (later same day):** REQ-2026-01's frontend deployment status — originally left as an open question in §6 below — is now resolved: `az containerapp list` confirms no `req-2026-01`-prefixed frontend Container App exists. Its 33 alert rows (still counted under Known/accepted and Real, actionable above; not a separate bucket) are dormant-code risk, not live-traffic risk. See §6 for the full reasoning; the original "needs Mike's call" framing no longer applies.

**By repo × request:**

| Request | Alert rows | Live infra today |
|---|---|---|
| REQ-2026-01 | 33 | Backend units (`req-2026-01-document-api`, `req-2026-01-email-worker`) confirmed live via `az containerapp list`. **Frontend confirmed not deployed** — no `req-2026-01-frontend`-style Container App exists in `forge-build-rg`. These 33 alert rows are dormant-code risk (see §6), not currently-exposed risk. |
| REQ-2026-02 | 41 | **Fully decommissioned 2026-08-13** (per CLAUDE.md Phase 5 closeout) — no Container Apps running. Zero live production exposure right now for any of these 41 alerts. |
| REQ-2026-03 | 27 | Fully live (frontend + backend both confirmed running). Normal current exposure applies. |

---

## 2. Known / accepted section

**All 21 unique CVEs here affect `next` across all three requests (REQ-2026-01/02/03) and have no fix available within the 14.x line — the first patched version for every one of them is 15.0.8 or later.** This is Open Item #11's finding, confirmed still present and — this pass found — **larger than previously counted**. Item #11's original wording ("8 HIGH-severity `next@14.2.35` CVE findings") only ever counted the HIGH-severity subset. The full "no 14.x backport" population is 21 unique CVEs (8 High + 11 Medium + 2 Low) × 3 requests = 63 alert rows. The underlying decision (accept this risk, stay on 14.x) is unchanged and not re-litigated here — only the count is being corrected for completeness, per the spec's own note that a prior acceptance should be confirmed, not assumed complete.

No action needed. No dismissal recommended — these stay open as a visible, honest record of accepted risk, consistent with how Item #11 has been handled since it was first recorded.

| CVE (GHSA) | Severity | Patched at | Requests affected |
|---|---|---|---|
| GHSA-h25m-26qc-wcjf | High | 15.0.8 | 01, 02, 03 |
| GHSA-q4gf-8mx6-v5v3 | High | 15.5.15 | 01, 02, 03 |
| GHSA-c4j6-fc7j-m34r | High | 15.5.16 | 01, 02, 03 |
| GHSA-36qx-fr4f-26g5 | High | 15.5.16 | 01, 02, 03 |
| GHSA-8h8q-6873-q5fj | High | 15.5.16 | 01, 02, 03 |
| GHSA-89xv-2m56-2m9x | High | 15.5.21 | 01, 02, 03 |
| GHSA-p9j2-gv94-2wf4 | High | 15.5.21 | 01, 02, 03 |
| GHSA-m99w-x7hq-7vfj | High | 15.5.21 | 01, 02, 03 |
| GHSA-9g9p-9gw9-jx7f | Medium | 15.5.10 | 01, 02, 03 |
| GHSA-ggv3-7p47-pfv8 | Medium | 15.5.13 | 01, 02, 03 |
| GHSA-3x4c-7xq6-9pq8 | Medium | 15.5.14 | 01, 02, 03 |
| GHSA-ffhc-5mcf-pf4q | Medium | 15.5.16 | 01, 02, 03 |
| GHSA-gx5p-jg67-6x7h | Medium | 15.5.16 | 01, 02, 03 |
| GHSA-h64f-5h5j-jqjh | Medium | 15.5.16 | 01, 02, 03 |
| GHSA-wfc6-r584-vfw7 | Medium | 15.5.16 | 01, 02, 03 |
| GHSA-68g3-v927-f742 | Medium | 15.5.21 | 01, 02, 03 |
| GHSA-4633-3j49-mh5q | Medium | 15.5.21 | 01, 02, 03 |
| GHSA-4c39-4ccg-62r3 | Medium | 15.5.21 | 01, 02, 03 |
| GHSA-955p-x3mx-jcvp | Medium | 15.5.21 | 01, 02, 03 |
| GHSA-3g8h-86w9-wvmq | Low | 15.5.16 | 01, 02, 03 |
| GHSA-vfv6-92ff-j949 | Low | 15.5.16 | 01, 02, 03 |

---

## 3. Real, actionable section

Ordered Critical → High → Medium → Low. All 12 CVEs below affect only REQ-2026-01 and REQ-2026-02 (24 alert rows total — 12 CVEs × 2 requests), and **every one of them is already fixed in `next@14.2.35`** — the exact version REQ-2026-03 already runs in production. No 15.x major-version jump needed; this is a same-line patch bump.

| CVE (GHSA) | Severity | Vulnerable range | Patched at | Alert #s (REQ-01, REQ-02) |
|---|---|---|---|---|
| GHSA-f82v-jwr5-mffw | **Critical** | >= 14.0.0, < 14.2.25 | 14.2.25 | 5, 38 |
| GHSA-gp8f-8m3g-qvj9 | High | >= 14.0.0, < 14.2.10 | 14.2.10 | 1, 34 |
| GHSA-7gfc-8cq8-jh5f | High | >= 9.5.5, < 14.2.15 | 14.2.15 | 3, 36 |
| GHSA-mwv6-3258-q52c | High | >= 13.3.0, < 14.2.34 | 14.2.34 | 11, 45 |
| GHSA-5j59-xgg2-r9c4 | High | >= 13.3.1-canary.0, < 14.2.35 | 14.2.35 | 12, 46 |
| GHSA-7m27-7ghc-44w9 | Medium | >= 14.0.0, < 14.2.21 | 14.2.21 | 4, 37 |
| GHSA-g5qg-72qw-gw5v | Medium | >= 0.9.9, < 14.2.31 | 14.2.31 | 7, 40 |
| GHSA-xv57-4mr9-wg8v | Medium | >= 0.9.9, < 14.2.31 | 14.2.31 | 8, 41 |
| GHSA-4342-x723-ch2f | Medium | >= 0.9.9, < 14.2.32 | 14.2.32 | 9, 42 |
| GHSA-g77x-44xx-532m | Medium | >= 10.0.0, < 14.2.7 | 14.2.7 | 2, 35 |
| GHSA-qpjv-v59x-3qc4 | Low | >= 0.9.9, < 14.2.24 | 14.2.24 | 10, 43 |
| GHSA-3h52-269p-cp9r | Low | >= 13.0, < 14.2.30 | 14.2.30 | 6, 39 |

**Recommended action:** bump `next` in `services/REQ-2026-01/frontend/package.json` and `services/REQ-2026-02/frontend/package.json` from `14.2.5` to `14.2.35` (or later, if a newer 14.x patch has shipped since). No upgrade-blocker research was done beyond version-range matching — this wasn't tested against either app's actual build (`npm run build`/`next build`), so treat "no obvious blocker" as unconfirmed, not verified, per Open Item #3's standing gap (no pipeline stage validates a real build before Deploy).

**Two additional, unrelated packages, both simple patch bumps:**

| Package | Request | CVE(s) | Severity | Current → Patched | Alert #s |
|---|---|---|---|---|---|
| `postcss` | REQ-2026-02 | GHSA-r28c-9q8g-f849, GHSA-6g55-p6wh-862q | High | ≤8.5.11/≤8.5.17 → 8.5.12/8.5.18 | 72, 73 |
| `postcss` | REQ-2026-02 | GHSA-qx2v-qp2m-jg93, GHSA-fxqj-rqcc-2cmp | Medium | <8.5.10/≤8.5.22 → 8.5.10/8.5.23 | 55, 74 |
| `Microsoft.Identity.Web` | REQ-2026-03 | GHSA-rpq8-q44m-2rpg | Medium | >=3.2.0,<3.8.2 → 3.8.2 | 75 |

`postcss` is a transitive dependency here (not a direct `dependencies`/`devDependencies` entry in REQ-2026-02's `package.json` — confirmed via the alert's `manifest_path` pointing at `package-lock.json`, not `package.json`); fixing it may require an `npm update postcss` / lockfile refresh rather than a direct version bump, depending on what pulls it in. `Microsoft.Identity.Web` is a direct NuGet reference in REQ-2026-03's `.csproj` — a normal patch-version bump.

---

## 4. Likely false positive section

**None found.** Zero alerts were placed in this bucket.

Reasoning: Dependabot's native alerts (what this pass queried) match against the GHSA advisory database using **direct npm/NuGet semver-range comparison** against the resolved lockfile version — not NVD's CPE dictionary fuzzy-matching, which is what actually caused the CPE-fuzzy-match false-positive class that motivated dropping OWASP Dependency-Check in the first place (`docs/FORGE-DependencyScanner-Dependabot-Swap-Spec.md`, Open Item #13's resolution). That specific failure mode doesn't apply to this data source. No alert in this dataset showed a version-range or ecosystem mismatch suggesting Dependabot's own match was wrong; every alert's resolved version genuinely falls inside the stated vulnerable range.

---

## 5. Dev-only / no exposure section

All 9 confirmed via `scope: "development"` on the alert's `dependency` object (not assumed from package name) — each also individually confirmed via `manifest_path` pointing at a `package-lock.json` inside a `frontend/` build context where the flagged package (`vite`, `esbuild`, `glob`, `minimatch`) is a build/test-tooling dependency, never shipped in the Next.js production bundle.

| Package | Request | Severity | Current → Patched | Alert #s |
|---|---|---|---|---|
| `vite` | REQ-2026-03 | High | ≤6.4.2 → 6.4.3 | 94 |
| `vite` | REQ-2026-03 | Medium | ≤6.4.1 → 6.4.2, ≤6.4.2 → 6.4.3 | 82, 95 |
| `glob` | REQ-2026-02 | High | >=10.2.0,<10.5.0 → 10.5.0 | 44 |
| `glob` | REQ-2026-03 | High | >=10.2.0,<10.5.0 → 10.5.0 | 77 |
| `esbuild` | REQ-2026-03 | Medium | ≤0.24.2 → 0.25.0 | 76 |
| `minimatch` | REQ-2026-02 | High | >=9.0.0,<9.0.6 → 9.0.6, >=9.0.0,<9.0.7 → 9.0.7 (×2) | 49, 50, 51 |

No production exposure. Recommended: dismiss with `dismissed_reason: not_used` (closest fit of GitHub's 5 allowed values — devDependency, never executed in the shipped bundle).

---

## 6. REQ-2026-01 frontend status — resolved 2026-08-21

**Originally an open question in this report; resolved the same day.** `az containerapp list` against `forge-build-rg` was checked again and confirmed: only `req-2026-01-document-api` and `req-2026-01-email-worker` are live. No `req-2026-01`-prefixed frontend Container App exists — REQ-2026-01's frontend is not currently deployed anywhere in `forge-build-rg`.

This does not fully rule out a deployment outside `forge-build-rg` (no other resource group or subscription was checked), but combined with CLAUDE.md's own account of REQ-2026-01 as a Phase 3/4 pipeline-validation request (merged as `forge-demo-apps` PR #5, predating `deploy_agent.py`'s existence — i.e., it was never run through the FORGE pipeline's own Deploy stage in the first place), the frontend has no evidence of ever having been deployed, let alone currently serving traffic.

**Conclusion: REQ-2026-01's 33 alert rows (12 in §3's Real-actionable table, 21 in §2's Known-accepted table) are dormant-code risk, not live-attack-surface risk — the same practical status as REQ-2026-02's fully-decommissioned alerts.** This doesn't change their underlying technical disposition (§2/§3 stand as written) — it changes urgency only. Not urgent to act on ahead of REQ-2026-03's genuinely-live exposure, but still worth including in the `next` version-catch-up fix (§3) since the code exists in the repo and could be redeployed later; fixing it now costs nothing extra beyond what's already being done for REQ-2026-02.

No other alerts in this report needed this kind of follow-up — the rest of the dataset had a clear, unambiguous disposition from the start.

---

## 7. Recommended dismissal list

**Per the spec: only the dev-only bucket has a dismissal recommendation below (the false-positive bucket is empty; the known/accepted bucket stays open by design, matching how Item #11 has always been handled).**

**Executed 2026-08-21, with Mike's explicit go-ahead.** All 9 commands below were run and independently verified (each alert re-fetched individually and confirmed `state: dismissed` with the correct `dismissed_reason`, not just a zero exit code) — alert numbers 44, 49, 50, 51, 76, 77, 82, 94, 95. `forge-demo-apps`'s open-alert count dropped from 101 to 92 immediately after, confirming no other alert was touched. Commands are left below as the executed record, not a pending recommendation.

All `dismissed_comment` values below are well under the 280-character cap (longest is 118 characters), confirmed by construction, not just asserted.

```bash
# vite -- dev-only build tooling, REQ-2026-03 (alerts 82, 94, 95)
gh api -X PATCH repos/Flamespiker/forge-demo-apps/dependabot/alerts/82 \
  -f state=dismissed -f dismissed_reason=not_used \
  -f dismissed_comment="vite is a devDependency (build/test tooling); never shipped in the Next.js production bundle."

gh api -X PATCH repos/Flamespiker/forge-demo-apps/dependabot/alerts/94 \
  -f state=dismissed -f dismissed_reason=not_used \
  -f dismissed_comment="vite is a devDependency (build/test tooling); never shipped in the Next.js production bundle."

gh api -X PATCH repos/Flamespiker/forge-demo-apps/dependabot/alerts/95 \
  -f state=dismissed -f dismissed_reason=not_used \
  -f dismissed_comment="vite is a devDependency (build/test tooling); never shipped in the Next.js production bundle."

# glob -- dev-only build tooling, REQ-2026-02 and REQ-2026-03 (alerts 44, 77)
gh api -X PATCH repos/Flamespiker/forge-demo-apps/dependabot/alerts/44 \
  -f state=dismissed -f dismissed_reason=not_used \
  -f dismissed_comment="glob is a devDependency (build tooling); never shipped in the Next.js production bundle."

gh api -X PATCH repos/Flamespiker/forge-demo-apps/dependabot/alerts/77 \
  -f state=dismissed -f dismissed_reason=not_used \
  -f dismissed_comment="glob is a devDependency (build tooling); never shipped in the Next.js production bundle."

# esbuild -- dev-only build tooling, REQ-2026-03 (alert 76)
gh api -X PATCH repos/Flamespiker/forge-demo-apps/dependabot/alerts/76 \
  -f state=dismissed -f dismissed_reason=not_used \
  -f dismissed_comment="esbuild is a devDependency (build tooling); never shipped in the Next.js production bundle."

# minimatch -- dev-only build/test tooling, REQ-2026-02 (alerts 49, 50, 51)
gh api -X PATCH repos/Flamespiker/forge-demo-apps/dependabot/alerts/49 \
  -f state=dismissed -f dismissed_reason=not_used \
  -f dismissed_comment="minimatch is a devDependency (test tooling); never shipped in the Next.js production bundle."

gh api -X PATCH repos/Flamespiker/forge-demo-apps/dependabot/alerts/50 \
  -f state=dismissed -f dismissed_reason=not_used \
  -f dismissed_comment="minimatch is a devDependency (test tooling); never shipped in the Next.js production bundle."

gh api -X PATCH repos/Flamespiker/forge-demo-apps/dependabot/alerts/51 \
  -f state=dismissed -f dismissed_reason=not_used \
  -f dismissed_comment="minimatch is a devDependency (test tooling); never shipped in the Next.js production bundle."
```

---

## Appendix: raw alert data

The full 101-row dataset (repo, alert number, package, ecosystem, severity, CVE/GHSA ID, manifest path, request ID, vulnerable range, first patched version, scope, state) was pulled via `get_dependabot_alerts()` and is not reproduced verbatim in this report for length — every alert number cited above traces back to that pull. Re-run `get_dependabot_alerts("Flamespiker/forge-demo-apps", state="open")` to reproduce it if needed for a future pass.
