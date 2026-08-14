# FORGE Documentation Cleanup — Changeset (2026-08-13)

**Scope:** Three pre-Phase-6 doc-drift items, batched per Mike's explicit call to do all cleanup in one chat. Targeted edits, not full overwrites, per standing convention. Verify each `old_str` against the live file before applying — this changeset is built from the project's reference copies (`06_Orchestration_v5.md`, `FORGE_Build_Plan_v8.md`, `03_FORGE_Tooling_v7.md`).

**Not included here:** the OWASP Dependency-Check scanner-failure-still-approves gap. That's a real code fix, not a doc edit — see the separate spec, `FORGE-SecurityAgent-ScannerFailureVerdict-Spec.md`.

**Also not included:** Document 6's "do not resume a failed session mid-stage" guidance, flagged back in chat 39/40. Checked the live v5 file directly — it's already been corrected (Part 4 now has the full reattach-and-recover guidance, including `--recover-session` and thread-status polling). No action needed; noting it here so it doesn't get re-flagged as still-open.

---

## 1. Document 6 (`06_Orchestration_v5.md` → `v6`)

### Edit A — Gate 4 narrative (currently implies the QA Reviewer applies the label)

**Old:**
```
**Gate 4 — QA sign-off:**
The QA Agent has posted a test report as a PR comment. If all tests pass, apply `qa-approved`. If failures exist, the agent has already filed ADO bug tickets and the implementation loop restarts. You do not need to act on failures — the loop handles itself unless it exceeds the retry limit (see failure handling below).
```

**New:**
```
**Gate 4 — QA sign-off:**
The QA Agent has posted a test report as a PR comment. If all tests pass, the agent applies `qa-approved` automatically — there is nothing for the QA Reviewer to apply manually. Review the report to confirm the pass is real. If failures exist, the agent has already filed ADO bug tickets and the implementation loop restarts. You do not need to act on failures — the loop handles itself unless it exceeds the retry limit (see failure handling below).
```

### Edit B — Gate 5 narrative (same issue for Security)

**Old:**
```
**Gate 5 — Security sign-off:**
The Security Agent has posted severity-tagged findings as inline PR comments. A Critical finding has already set a failing check that blocks merge. If there are no Criticals, or after Criticals are resolved, the Technical Approver applies `security-approved`.
```

**New:**
```
**Gate 5 — Security sign-off:**
The Security Agent has posted severity-tagged findings as inline PR comments. A Critical finding has already set a failing check that blocks merge. If there are no Criticals, the agent applies `security-approved` automatically — the Security Reviewer's role is to review the findings and confirm the pass, not to apply the label. After Criticals are resolved and a clean re-scan runs, the label is applied the same way.
```

### Edit C — Label Reference table rows

**Old:**
```
| `qa-approved` | QA Reviewer | Clears QA gate; combined with `security-approved` to enable production deploy |
| `security-approved` | Security Reviewer | Clears security gate; combined with `qa-approved` to enable production deploy |
```

**New:**
```
| `qa-approved` | QA Agent (applied automatically on a clean pass) | Clears QA gate; combined with `security-approved` to enable production deploy |
| `security-approved` | Security Agent (applied automatically on a clean pass, no Critical findings) | Clears security gate; combined with `qa-approved` to enable production deploy |
```

### Edit D — Remove the now-redundant footnote sentence

**Old:**
```
PR events (open, merge) and GitHub Environment approvals handle the remaining state transitions — these are not label-driven. Note that `qa-approved` and `security-approved` are shown above with their documented human-reviewer owners; in practice both are applied directly by the QA Agent and Security Agent respectively when their automated checks pass cleanly (see Part 2, Gates 4–5) — this discrepancy between documented and built behavior is a known, separately-tracked open item, not resolved by this pass.
```

**New:**
```
PR events (open, merge) and GitHub Environment approvals handle the remaining state transitions — these are not label-driven.
```
*(The table now states the true owner directly, so the disclaimer sentence describing the discrepancy is no longer needed — this edit is what resolves it.)*

---

## 2. Build Plan (`FORGE_Build_Plan_v8.md` → `v9`)

### Edit E — Step 5.7

**Old:**
```
- [x] 5.7 Stage 4 — review QA report, confirm bugs filed (or clean run), apply `qa-approved` *(passed on the 3rd of 3 automated attempts against real bugs, not a clean first pass)*
```

**New:**
```
- [x] 5.7 Stage 4 — review QA report, confirm bugs filed (or clean run); `qa-approved` applied automatically by the agent on the clean pass *(3rd of 3 automated attempts against real bugs, not a clean first pass)*
```

### Edit F — Step 5.8

**Old:**
```
- [x] 5.8 Stage 5 — review Security Agent findings, confirm no Critical blockers, apply `security-approved`
```

**New:**
```
- [x] 5.8 Stage 5 — review Security Agent findings, confirm no Critical blockers; `security-approved` applied automatically by the agent
```

---

## 3. Document 3 (`03_FORGE_Tooling_v7.md` → `v8`)

This is the substantive one, flagged back in chat 32 as "a real architecture mismatch, not just stale wording" and a candidate for its own ADR. **Decision made this chat: correct Document 3's prose to match the real, live-verified architecture rather than write a new ADR.** The deviation is a tooling/provisioning detail (how the three scanners are invoked), not a governance-layer decision like ADR-0010/0011 were — it doesn't change any locked core-layer behavior or team-layer boundary, so it doesn't meet the bar this project has otherwise used for a dedicated ADR. Flag to Mike if you disagree; easy to add ADR-0013 later if this becomes a recurring pattern-of-record need.

**Ground truth for this rewrite:** confirmed by reading the live `core/agents/security_agent.py` directly (`Flamespiker/forge-template`, public repo) rather than trusting the prior doc or the context log alone.

### Edit G — Section intro + full table + recommendation paragraph

**Old:**
```
### 3.5 Security Tooling

FORGE's Security Agent (Document 2 §3, §4.7) runs three categories of checks: SAST (static analysis), secrets detection, and OWASP/dependency vulnerability scanning. Each runs in a GitHub Actions job and posts results as PR check runs and inline comments. All recommended tools below are open source and run within GitHub Actions — no separate SaaS account is required for the defaults.

| Tool | Category | Role in FORGE | Required | Who Provisions | License Type | Build-Phase Cost | Production Cost |
|---|---|---|---|---|---|---|---|
| **Semgrep Community** | SAST | Static analysis of .NET and React/Next.js code — rule sets for common vulnerability classes (injection, XSS, insecure deserialization, etc.) | Required (one SAST tool must be chosen) | Orchestration Manager installs via GitHub Actions step (`returntocorp/semgrep-action`) | Open source (LGPL-2.1); Community rules free | Free | Free |
| **Gitleaks** | Secrets detection | Scans commit history and staged changes for API keys, tokens, connection strings, and credential patterns | Required (one secrets tool must be chosen) | Orchestration Manager adds `gitleaks/gitleaks-action` to the Security workflow | Open source (MIT) | Free | Free |
| **OWASP Dependency-Check** | Dependency vulnerability scanning | Scans .NET NuGet and Node npm dependencies against the NVD CVE database; flags known vulnerabilities by severity | Required (one dependency scanner must be chosen) | Orchestration Manager adds `dependency-check/Dependency-Check_Action` to the Security workflow | Open source (Apache 2.0) | Free | Free |
| **GitHub Advanced Security (CodeQL + Secret Scanning)** | SAST + secrets (alternative) | GitHub's native SAST and secret scanning — tighter GitHub integration, automatic PR annotations, broader language coverage | Optional (upgrade path) | Org admin enables on the monorepo; requires GitHub Advanced Security add-on | GitHub Advanced Security add-on (~$49 USD/active committer/month) | Not needed in build phase | If adopted: significant per-user cost; evaluate against open-source alternatives |
| **Snyk** | Dependency vulnerability scanning (alternative) | Freemium SaaS alternative to OWASP Dependency-Check; richer advisory database, auto-fix PR suggestions | Optional | Orchestration Manager creates Snyk account; integrates via `snyk/actions` | Freemium (free tier: limited scans/month; paid plans from ~$25/month) | Free tier sufficient for build phase | Evaluate based on scan volume |

**Default recommendation:** Semgrep Community + Gitleaks + OWASP Dependency-Check. All three run in GitHub Actions, cost nothing, and satisfy the Security Agent's three check categories without a SaaS dependency. GitHub Advanced Security and Snyk are the upgrade path if LAA decides to consolidate security tooling or if the free tools prove insufficient in production.

A Critical finding from any of the three tools sets a failing check run on the implementation PR (Document 2 §4.7), which blocks merge without manual override — this is enforced by the branch protection rule requiring the Security check to pass, not by the agent making a judgment call.
```

**New:**
```
### 3.5 Security Tooling

FORGE's Security Agent (`core/agents/security_agent.py`, Document 2 §3, §4.7) runs three categories of checks: SAST (static analysis), secrets detection, and dependency vulnerability scanning. **Correction from earlier versions of this document:** these are not three separate GitHub Actions marketplace steps each posting its own results. Security Agent invokes all three tools directly as CLI subprocesses inside a single GitHub Actions job (`05-security.yml`), parses each tool's own output itself, applies FORGE's fixed severity-mapping tables (Document 7), and is the sole poster of every inline PR comment, the `security-check` check run, and the `security-approved` label — no GitHub Actions marketplace step for any of the three tools is used anywhere in the pipeline. All three tools must be installed as CLI binaries wherever the job runs, discovered via `shutil.which()` at call time — not configured as workflow-level Actions steps.

| Tool | Category | Role in FORGE | Required | Who Provisions | License Type | Build-Phase Cost | Production Cost |
|---|---|---|---|---|---|---|---|
| **Semgrep Community** | SAST | Static analysis of .NET and React/Next.js code — rule sets for common vulnerability classes (injection, XSS, insecure deserialization, etc.), invoked by Security Agent as a CLI subprocess | Required (one SAST tool must be chosen) | Orchestration Manager: `pip install semgrep` (pinned `semgrep>=1.90.0` in `requirements.txt`, same Python environment the six Messages-API stages already run in) | Open source (LGPL-2.1); Community rules free | Free | Free |
| **Gitleaks** | Secrets detection | Scans the checked-out service directory for API keys, tokens, connection strings, and credential patterns, invoked by Security Agent as a CLI subprocess; test-fixture paths excluded via team-configurable `team/gitleaks-allowlist.toml` | Required (one secrets tool must be chosen) | Orchestration Manager: separate binary install on the runner (not pip-installable) — e.g. `winget install --id Gitleaks.Gitleaks` or the equivalent on the CI runner's OS; must resolve on PATH | Open source (MIT) | Free | Free |
| **OWASP Dependency-Check** | Dependency vulnerability scanning | Scans .NET NuGet and Node npm dependencies against the NVD CVE database, invoked by Security Agent as a CLI subprocess (`dependency-check.sh`/`.bat`); flags known vulnerabilities by CVSS-threshold severity | Required (one dependency scanner must be chosen) | Orchestration Manager: separate binary install (zip release from `dependency-check/DependencyCheck` GitHub releases — no package-manager install exists); **also requires a Java runtime (JDK 21 LTS confirmed working)**, not needed by any other FORGE tool; strongly recommends registering a free **NVD API key** (`NVD_API_KEY` env var) — without one, NVD database updates are rate-limited and can be extremely slow on every run | Open source (Apache 2.0) | Free (NVD API key is free to register) | Free |
| **GitHub Advanced Security (CodeQL + Secret Scanning)** | SAST + secrets (alternative) | GitHub's native SAST and secret scanning — tighter GitHub integration, automatic PR annotations, broader language coverage | Optional (upgrade path) | Org admin enables on the monorepo; requires GitHub Advanced Security add-on | GitHub Advanced Security add-on (~$49 USD/active committer/month) | Not needed in build phase | If adopted: significant per-user cost; evaluate against open-source alternatives |
| **Snyk** | Dependency vulnerability scanning (alternative) | Freemium SaaS alternative to OWASP Dependency-Check; richer advisory database, auto-fix PR suggestions | Optional | Orchestration Manager creates Snyk account; integrates via `snyk/actions` | Freemium (free tier: limited scans/month; paid plans from ~$25/month) | Free tier sufficient for build phase | Evaluate based on scan volume |

**Default recommendation:** Semgrep Community + Gitleaks + OWASP Dependency-Check. All three are free and open source; Security Agent runs and parses them itself inside one GitHub Actions job rather than depending on separate marketplace Actions or a SaaS dependency. GitHub Advanced Security and Snyk are the upgrade path if LAA decides to consolidate security tooling or if the free tools prove insufficient in production.

A Critical finding from any of the three tools sets a failing check run on the implementation PR (Document 2 §4.7), which blocks merge without manual override — this is enforced by the branch protection rule requiring the `security-check` check to pass, not by the agent making a judgment call. **Open item, not yet fixed in code:** if a scanner fails to execute at all (distinct from running clean with zero findings), the current verdict logic still treats this the same as a clean scan and can auto-apply `security-approved` — see the dedicated spec (`FORGE-SecurityAgent-ScannerFailureVerdict-Spec.md`) for the fix in progress.
```

### Edit H — Provisioning checklist, step 8

**Old:**
```
8. **Configure security tools** — Orchestration Manager adds Semgrep, Gitleaks, and OWASP Dependency-Check GitHub Actions steps to the Security workflow; no external accounts required for the defaults.
```

**New:**
```
8. **Configure security tools** — Orchestration Manager installs Semgrep (`pip install semgrep`), Gitleaks, and OWASP Dependency-Check (including its Java prerequisite) as CLI binaries on the runner Security Agent executes on, and registers a free NVD API key for Dependency-Check; no external accounts required beyond the NVD key.
```

---

## Summary of version bumps

| Document | Old | New |
|---|---|---|
| Orchestration Manager Guide | `06_Orchestration_v5.md` | `06_Orchestration_v6.md` |
| Build Plan | `FORGE_Build_Plan_v8.md` | `FORGE_Build_Plan_v9.md` |
| Tool & Licensing Inventory | `03_FORGE_Tooling_v7.md` | `03_FORGE_Tooling_v8.md` |

Per the document-supersession convention: remove the old-version files when committing the new ones; Git history is the version record.
