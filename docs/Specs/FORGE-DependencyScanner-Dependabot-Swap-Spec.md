# FORGE Spec: Swap Dependency Scanner from OWASP Dependency-Check to GitHub Dependabot Alerts

**Status:** Ready for implementation
**Author:** Claude.ai (spec) — Claude Code CLI (implementation)
**Date:** 2026-08-18
**Related:** Open Item #9/#13 (dev-only npm CVE suppression), PR #21 (`forge-demo-apps`), CI timeout incident (Dependency-Check hitting 1800s twice consecutively on REQ-2026-03's frontend scan)

---

## 1. Background / Why

`security_agent.py`'s Stage 5 currently runs three scanners unconditionally: Semgrep (SAST), Gitleaks (secrets), OWASP Dependency-Check (dependency vulnerabilities). Dependency-Check has now timed out twice consecutively in CI at exactly `_TOOL_TIMEOUT_SECONDS` (1800s), root-caused to NVD database sync being much slower over GitHub Actions' network path than locally (local cold-cache run: ~6-7 min; CI: times out at 30 min). This is a reproducible, structural CI bottleneck, not a one-off flake.

Separately, Dependency-Check's CPE-based dependency matching produces a real, already-documented false-positive class in this project (see CLAUDE.md's root-cause-discipline learning: "CPE fuzzy-matching false positives require individual NVD-source verification, not batch treatment"), and required a suppression file (Open Item #13) to handle a confirmed dev-only finding (GHSA-5xrq-8626-4rwp, vitest) blocking PR #21.

Given LAA is planning to adopt GitHub Advanced Security, and Dependabot alerts are free today regardless of that purchase (no GHAS license required for alerts specifically), this is a good point to swap the dependency-scanning leg of Security Agent from Dependency-Check to Dependabot:

- Eliminates the entire CI-timeout failure class (Dependabot alerts are precomputed by GitHub in the background; the workflow just queries an API — seconds, not a 30-60 min scan).
- Eliminates CPE-fuzzy-matching false positives (Dependabot maps directly to package+version, no CPE guessing).
- No new SaaS cost (Dependabot alerts are free on github.com for public and private repos).
- Positions the Security Agent to consolidate onto GitHub-native tooling as GHAS comes online (CodeQL/Secret Scanning as later, separate swaps for Semgrep/Gitleaks — explicitly NOT in scope here).

Per `07_Customization_Ref_v2.md`, "Default dependency vulnerability scanner (OWASP Dependency-Check)" is explicitly **Flexible** — team's call, not a Locked platform decision. This swap does not require an RFC.

**Explicitly out of scope for this spec:** swapping Semgrep→CodeQL or Gitleaks→Secret Scanning. Those aren't broken today and should be evaluated separately once GHAS is actually purchased.

---

## 2. Prerequisites (Mike, manual, before implementation)

1. Enable **Dependabot alerts** (Settings → Code security and analysis) on both `Flamespiker/forge-template` and `Flamespiker/forge-demo-apps`.
2. Confirm the `forge-pipeline` GitHub App (App ID `4388813`) has the **Dependabot alerts: Read-only** permission scope granted on its installation for both repos. This is a narrower, separate permission from the Administration scope it's already confirmed *not* to have — check it explicitly, don't assume it's bundled with existing scopes.
3. Confirm both repos actually have a populated **dependency graph** (Insights → Dependency graph) — this is what Dependabot alerts are computed against; a repo with an unpopulated/errored dependency graph will return zero alerts, which would look identical to "no vulnerabilities" and must not be silently treated as a clean pass.

---

## 3. Design

### 3.1 New helper: `github_helper.py`

Add a function to fetch Dependabot alerts for a repo via the REST API:

```
get_dependabot_alerts(repo_full_name: str, state: str = "open") -> list[dict]
```

- Calls `GET /repos/{owner}/{repo}/dependabot/alerts?state=open` (paginate if `Link` header indicates more pages — do not assume a single page covers all alerts).
- Returns the raw alert objects. Each alert includes (per GitHub's API): `security_advisory.severity` (`critical`/`high`/`medium`/`low`), `security_advisory.cve_id`, `security_advisory.ghsa_id`, `security_advisory.summary`, `dependency.package.name`, `dependency.package.ecosystem`, `dependency.manifest_path`, `security_vulnerability.vulnerable_version_range`, `security_vulnerability.first_patched_version`.
- Handle 403 explicitly and distinguish two real cases before treating either as "no alerts": (a) Dependabot alerts not enabled on the repo, (b) the App's permission scope missing. Both must produce a clear, distinguishable error/log line — a scanner that can't run must be treated as `ran=False` (see 3.3), never silently as zero findings.
- Handle the dependency-graph-empty case (empty list AND graph not populated) distinctly from a genuinely clean repo (empty list, graph populated, zero alerts) if the API response/headers allow that distinction — check GitHub's actual API docs/response shape for this rather than assuming; if no clean distinguishing signal exists, flag this as a real limitation to report back, not something to paper over.

### 3.2 Filtering to the relevant path

Unlike Dependency-Check (invoked with `--scan services/<request-id>/`), Dependabot alerts are repo-wide, not path-scoped. `security_agent.py` must filter returned alerts to only those whose `dependency.manifest_path` falls under `services/<request-id>/` — otherwise a PR touching REQ-2026-03 would surface findings from REQ-2026-01/02's manifests too. Confirm this filtering is applied before any severity counting/gating logic runs.

### 3.3 Replacing `_run_dependency_check()`

Replace the function (not just its internals — the calling convention changes from "run subprocess, parse report file" to "call API, get structured data") with `_run_dependabot_check(repo_full_name, request_id)`:

- Returns the same `ScanResult` shape used by the other two scanners (`ran: bool`, findings list, etc.) so downstream gating logic (`has_critical`, `any_tool_failed`) doesn't need to change its interface — only this one function's internals change.
- `ran = False` on any of: API auth/permission failure, dependency graph not populated, unexpected API error — never on "zero alerts returned for a legitimately clean repo."
- Severity mapping: Dependabot's `security_advisory.severity` already arrives as `critical`/`high`/`medium`/`low` — map 1:1 to FORGE's existing Critical/High/Medium/Low schema (Document 7: Locked schema, must not change). No CVSS-threshold math needed (that was Dependency-Check-specific); if a future alert somehow lacks a severity field, default to Medium (matches the existing "Medium default if neither score present" pattern from Dependency-Check for consistency, and errs toward blocking review rather than silently passing).

### 3.4 Suppression mechanism

Dependabot has **native per-alert dismissal** (via API: `PATCH /repos/{owner}/{repo}/dependabot/alerts/{alert_number}` with a `state: dismissed` and `dismissed_reason`) — this replaces the need for the `team/dependency-check-suppressions.xml` file entirely for future dev-only findings. Today's already-open GHSA-5xrq-8626-4rwp on `forge-demo-apps` (vitest) should be dismissed this way, with `dismissed_reason: "tolerable_risk"` and a comment matching the same justification as the original suppression-file work (dev-only, never in the deployed image).

Whether the Security Agent itself should auto-dismiss known-dev-only findings, or whether all dismissals stay a manual human action via the GitHub UI/API, is a **separate open design question** — do not build auto-dismissal logic in this pass. For now, dismissal is manual (Mike, via `gh api` or the Security tab), same trust boundary as today's manual suppression-file edits.

### 3.5 What gets removed

- `_run_dependency_check()` internals (NVD sync, CLI subprocess invocation, XML/JSON report parsing) — remove entirely, not just disable.
- `NVD_API_KEY` Actions secret — no longer needed; leave a note in CLAUDE.md rather than deleting the secret itself immediately (in case rollback is needed short-term).
- `team/dependency-check-suppressions.xml` (if it was created in the earlier session before this swap lands) — superseded by native Dependabot dismissal; keep the file's git history but stop referencing it from `security_agent.py`.
- The `--exclude "**/node_modules/**"` CLI flag handling and related Dependency-Check-specific timeout/report-missing logic.

### 3.6 Timeout logic

Since Dependabot is a simple API call (seconds, not tens of minutes), `_TOOL_TIMEOUT_SECONDS` should no longer need a scanner-specific long allowance for this leg. Confirm whether Semgrep/Gitleaks still need the existing 1800s ceiling on their own merits (they might, independent of this swap) — don't reduce the global timeout constant without checking both remaining scanners' real run times first.

---

## 4. Verification (do all of these for real)

1. Confirm `get_dependabot_alerts()` returns real data against `forge-demo-apps`'s actual current Dependabot alerts (there should be at least the vitest one, if not yet dismissed).
2. Run `security_agent.py` (non-dry-run) against PR #21's current commit — confirm real API-backed results, correct path-filtering (only REQ-2026-03 manifests), correct severity mapping, and total run time (expect seconds, not minutes — report the actual number).
3. Confirm the check-run conclusion and `security-approved` label logic behave identically in shape to before (still driven by `has_critical OR any_tool_failed`), just backed by different data.
4. Confirm dismissing the vitest alert via API actually removes it from subsequent `get_dependabot_alerts()` calls.
5. Confirm Semgrep and Gitleaks are unaffected — same invocation, same results, this swap only touches the dependency-scanning leg.
6. Real end state: PR #21 merges cleanly via the normal (non-admin) path once the vitest alert is dismissed and no other Critical exists.

---

## 5. Rollback

If Dependabot's data proves insufficient for some real reason discovered during verification (missing ecosystem coverage, permission issues that can't be resolved, etc.), `_run_dependency_check()`'s prior implementation is recoverable from git history (pre-swap commit) — flag any such issue back to Mike rather than half-implementing a hybrid.

---

## 6. Documentation to update after implementation (Claude.ai will draft, Mike/Claude Code apply)

- `03_FORGE_Tooling_v7.md` §3.5 — Security Tooling table
- `07_Customization_Ref_v2.md` — Security Tooling table, dependency scanner row
- `09-forge-readme_v6.md` — cost reference table
- `CLAUDE.md` — `security_agent.py` section (Claude Code's own update, per two-tool convention), plus Outstanding/Open Items list (remove #13 as resolved-via-different-mechanism, note `NVD_API_KEY` deprecation)
- `FORGE-context_v58.md` (next version) — session narrative
