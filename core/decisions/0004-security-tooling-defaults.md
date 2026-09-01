# ADR-0004: Security Tooling Defaults

**Status:** Accepted
**Date:** 2026-07-23
**RFC:** _(seed ADR — predates RFC process)_
**Amended:** 2026-08-19 — dependency scanner swapped, see "Consequences" and
Document 3 §3.5 for the full record.

## Context

The Security stage (Stage 5) needs concrete tools to actually produce
findings, not just a policy that "security scanning happens." Three
distinct categories of finding needed coverage: static application security
testing (SAST) across the generated Backend/Frontend code, secrets
accidentally committed to the repo, and known vulnerabilities in
third-party dependencies. Each category needed a specific, working default
tool the Security Agent could invoke and parse output from — teams
shouldn't have to pick a toolchain from scratch before their first pipeline
run.

## Decision

FORGE ships with three default security scanners, one per finding category,
locked at the "a scanner in this category is required and blocks on
Critical findings" level but **flexible** on which specific tool a team
uses (see Document 7):

- **SAST:** Semgrep Community (pip-installable; runs in-job)
- **Secrets detection:** Gitleaks (standalone binary install)
- **Dependency vulnerabilities:** originally OWASP Dependency-Check
  (standalone binary install, syncs against the NVD)

All three tools' findings are normalized into a single severity schema
(Critical / High / Medium / Low) so the Security Agent's inline PR
comments and blocking-check logic don't need to branch on which specific
tool produced a finding. A Critical finding from any tool sets a failing
check that blocks merge automatically, enforced by branch protection, not
by agent judgment — this blocking behavior itself is core-layer locked
even though the specific tool underneath any one category is not.

## Consequences

**Positive:**
- Every team gets working security scanning on day one without needing to
  research and wire up a toolchain themselves.
- The Critical-blocks-merge enforcement lives in branch protection, not in
  agent judgment — a misbehaving or manipulated agent invocation cannot
  silently wave through a Critical finding.
- Teams can substitute any of the three defaults (e.g. GitHub Advanced
  Security/CodeQL for SAST, GitHub Advanced Security Secret Scanning for
  secrets) as long as the substitute runs in GitHub Actions (or, for
  dependency scanning, is API-based) and produces output the Security Agent
  can consume into the same severity schema.

**Negative / tradeoffs accepted, and one real amendment:**
- OWASP Dependency-Check's NVD sync made it the slowest of the three
  scanners by a wide margin, and it **timed out twice consecutively in
  real CI runs** — this was discovered in production use, not anticipated
  at design time. **Amended 2026-08-19:** the default dependency
  vulnerability scanner was swapped to **GitHub Dependabot alerts**, an
  API-based check rather than an Actions job, eliminating the timeout
  class of failure entirely. `security_agent.py`'s `_run_dependency_check()`
  was replaced with `_run_dependabot_check()`; `_TOOL_TIONEOUT_SECONDS` was
  reduced from 1800s to 600s once real Semgrep/Gitleaks run times (~4.6s
  and ~0.05s respectively) confirmed the long ceiling was never needed by
  either of them — it existed only for Dependency-Check's own sync step.
  OWASP Dependency-Check remains an available substitute for teams that
  prefer it, with the same timeout risk they'd need to manage themselves.
- Because Dependabot alerts are repo-wide rather than path-scoped (unlike
  Dependency-Check's `--scan services/<request-id>/`), the Security Agent
  must filter alerts to the relevant service path itself rather than
  relying on the scanner to have already scoped them.
