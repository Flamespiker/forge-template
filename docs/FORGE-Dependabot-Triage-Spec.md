# FORGE — Dependabot Alert Triage Pass: Spec for Claude Code

**Prepared:** 2026-08-20 (Claude.ai)
**For:** Claude Code CLI session against both `forge-template` and `forge-demo-apps` (read-only against GitHub's API — no code changes, no dismissals performed automatically)
**Context:** 102 total open Dependabot alerts repo-wide (per CLAUDE.md, confirmed 2026-08-19), ~28 scoped under `services/REQ-2026-03/`, 74 outside that scope. Never triaged. Carried forward v58–v63. This is a **data-gathering and classification pass**, not a fix — the output is a report Mike reviews before any dismissal or remediation action is taken.

**Standing conventions to follow (per `CLAUDE.md` / context doc):**
- Individual NVD-source verification required for any CPE fuzzy-matching false-positive candidate — no batch treatment, per existing root-cause discipline (confirmed principle: "Confirm whether bugs share a root cause before treating them as one — surface similarity doesn't imply shared fix").
- Dismissal is a manual human action (via `gh api` or the Security tab) — the Security Agent does not auto-dismiss, and neither should this session. This pass produces recommendations only.
- Use the GitHub App's actual granted permission (`vulnerability_alerts`) via the existing `github_helper.py` machinery where possible, rather than reinventing API calls — `get_dependabot_alerts(repo_full_name, state)` already exists and paginates correctly; reuse it.
- Item #11 is already a known, accepted, non-actionable finding: 8 HIGH-severity `next@14.2.35` CVEs with no 14.x backport, accepted ongoing risk from the deliberate decision to stay on the 14.x line. **Do not re-litigate this one** — just confirm it's still present in the pull and tag it as "known/accepted" in the report rather than spending verification effort on it.

---

## Task 1: Pull the full current data set

1. Call `get_dependabot_alerts(repo_full_name, state="open")` against both `Flamespiker/forge-template` and `Flamespiker/forge-demo-apps`. Confirm the total count matches or has drifted from the 102 figure recorded 2026-08-19 (alerts open/close over time — note any drift explicitly, don't assume the old number still holds).
2. For each alert, capture: repo, alert number, package name + ecosystem, severity (`security_advisory.severity`), CVE/GHSA identifier, `dependency.manifest_path`, whether it falls under `services/REQ-2026-03/` (existing filter logic from `_run_dependabot_check()` — reuse the same path-prefix check, don't reimplement it differently), and current state.
3. Separate into two working sets: **REQ-2026-03-scoped** (~28 expected) and **everything else** (~74 expected, spanning REQ-2026-01 and REQ-2026-02's retained code plus `forge-template` itself). Note which repo and which request each alert belongs to.

## Task 2: Classify by severity and disposition

For each alert, assign one of these dispositions — this is the actual triage judgment, and it's the part that needs care rather than a mechanical pass:

- **Known/accepted** — the 8 HIGH `next@14.2.35` findings (Item #11) and any other alert Mike has previously and explicitly accepted as ongoing risk (check CLAUDE.md/context docs for any other prior explicit acceptance before assuming none exist).
- **Real, actionable** — a genuine vulnerability in a package version actually in use, where a fixed version is available and upgrading is plausible without a known-conflicting dependency. Flag the fixed version and any obvious upgrade blockers (peer dependency conflicts, major-version bumps that would need their own testing pass).
- **Likely false positive (CPE fuzzy-match candidate)** — GitHub's advisory matched a package/version range that doesn't actually apply (e.g. a transitive dependency pinned to a patched version but the advisory's CPE range is broader than the real affected range, or a dev-only dependency flagged as if it were production). **Every alert placed in this bucket requires individual verification against the advisory's own NVD/GHSA source page** — read the actual advisory, confirm the affected version range against the actual resolved version in the lockfile, and record the specific reasoning (not just "looks like a false positive"). Do not batch multiple alerts under one blanket "these are all fuzzy-match noise" judgment even if they look similar on the surface.
- **Dev-only / no production exposure** — package only present in devDependencies, test tooling, or build-time-only paths, where the vulnerability class doesn't apply outside that context (e.g. a CLI tool's own dependency chain that never ships). Still needs the manifest path confirmed, not assumed from the package name alone.
- **Needs Mike's call** — anything ambiguous: correct exposure, no clean upgrade path, real risk but real cost to fix, or anything where reasonable people could disagree on disposition.

## Task 3: Produce the report

Write `docs/FORGE-Dependabot-Triage-Report-2026-08-20.md` (or similar dated filename) to `forge-template`, structured as:

1. **Summary table** — counts by repo × severity × disposition bucket (a simple grid, not prose).
2. **Known/accepted section** — the 8 `next@14.2.35` findings plus any others found, one line each, no further action needed.
3. **Real, actionable section** — one entry per alert: package, current vs. fixed version, upgrade blockers if any, recommended action. Ordered Critical → High → Medium → Low.
4. **Likely false positive section** — one entry per alert with the specific NVD/GHSA verification performed and the reasoning for the false-positive call, not a blanket dismissal. This is the section most likely to need Mike's spot-check given how much individual judgment goes into it.
5. **Dev-only / no exposure section** — one entry per alert, manifest path confirmed.
6. **Needs Mike's call section** — anything genuinely ambiguous, with the specific question to resolve stated plainly.
7. **Recommended dismissal list** — for the false-positive and dev-only buckets, a ready-to-run list of `gh api repos/{owner}/{repo}/dependabot/alerts/{n}` `PATCH` commands with `state: dismissed` and a `dismissed_reason` (`tolerable_risk` / `not_used` per GitHub's allowed enum values — confirm the exact enum from GitHub's REST API docs before writing these) and a `dismissed_comment` under the 280-character cap (confirmed live limit). **Do not execute any of these** — this list is for Mike to review and run (or authorize Claude Code to run) after reading the report.

## Explicitly out of scope for this pass

- No actual package upgrades. No `npm install`/`dotnet add package` changes. This is triage only.
- No dismissals executed automatically, even for alerts that look obviously safe to dismiss.
- No re-verification of Item #11 (already settled — just confirm presence and count).
- No changes to `_run_dependabot_check()` or any agent code.

## Acceptance criteria

- Every one of the ~102 (or current actual count, if drifted) open alerts appears in exactly one disposition bucket — no alert silently dropped.
- Every "likely false positive" entry cites the specific advisory source checked and the specific version-range reasoning, not a generic "probably fine."
- The recommended-dismissal list uses real, GitHub-API-valid `dismissed_reason` values and respects the 280-character `dismissed_comment` cap (confirm live via a dry construction, not just assumption).
- Report file committed to `forge-template` (docs are fair game for direct commit, not gated behind a PR — confirm this matches existing convention for docs-only changes; if docs normally go through a PR too, follow that instead).

---

## After the report is done

- Do not action anything from the recommended-dismissal list without Mike's explicit go-ahead.
- Update `CLAUDE.md` with a brief note that the pass was completed and where the report lives. Do **not** update the context doc from this session — that's Claude.ai's job at close.
- Next chat after this one (Claude.ai): review the report with Mike, decide which dismissals to authorize, and fold the outcome into the context doc.
