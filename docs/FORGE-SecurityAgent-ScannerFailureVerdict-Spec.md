# FORGE Security Agent — Scanner-Failure Verdict Fix Spec

**Status:** Spec authored (Claude.ai), not yet implemented. Hand off to Claude Code CLI for implementation and verification, per the standing two-tool convention.

---

## Problem

`security_agent.py` can auto-apply `security-approved` and set a passing `security-check` even when one or more of its three scanners (Semgrep, Gitleaks, OWASP Dependency-Check) failed to execute at all — as opposed to running cleanly and finding nothing.

**First observed live, `DRYRUN-2026-01` (chat 39):** OWASP Dependency-Check failed to produce `dependency-check-report.json`. The overall verdict still returned "Clear" and `security-approved` auto-applied — indistinguishable in the PR from a run where all three tools executed cleanly and found nothing. Accepted for that dry run given trivial, well-known dependencies, but flagged as a real gap and never fixed.

## Root Cause (confirmed against the live file)

Fetched directly from `raw.githubusercontent.com/Flamespiker/forge-template/main/core/agents/security_agent.py` (public repo) rather than trusting the doc or context-log description alone.

`run_security_agent()`:

```python
all_results = [semgrep_result, gitleaks_result, depcheck_result]
all_findings = [f for r in all_results for f in r.findings]

counts_by_severity = {sev: 0 for sev in (_SEV_CRITICAL, _SEV_HIGH, _SEV_MEDIUM, _SEV_LOW)}
for f in all_findings:
    counts_by_severity[f.severity] += 1
has_critical = counts_by_severity[_SEV_CRITICAL] > 0

check_conclusion = "failure" if has_critical else "success"
label_to_apply = None if has_critical else "security-approved"
```

Each `ScanResult` already carries a `ran: bool` field — `False` when a tool times out or fails to produce its output file (`_run_semgrep`, `_run_gitleaks`, `_run_dependency_check` all set this correctly today, along with a `run_failure_message`). But the verdict computation above only ever looks at `all_findings`, which is empty for a tool that never ran — `r.ran` is never consulted. `tool_run_failures` is built a few lines later and passed into the Claude prompt purely for narrative color in the human-facing overview comment; it has zero effect on `has_critical`, `check_conclusion`, or `label_to_apply`. A tool that silently failed and a tool that ran clean with zero findings are, today, computationally identical outcomes.

## Fix

Minimal and fully deterministic — no new label, no new retry mechanism, consistent with this stage's existing "not AI judgment" design and with Security's existing no-retry-loop model.

**1. Compute the failure flag**, immediately after `all_results` is built:
```python
any_tool_failed = any(not r.ran for r in all_results)
```

**2. Fold it into the verdict** (replaces the two lines quoted above):
```python
check_conclusion = "failure" if (has_critical or any_tool_failed) else "success"
label_to_apply = None if (has_critical or any_tool_failed) else "security-approved"
```
A scanner that failed to run is treated the same as a Critical finding for gating purposes: it blocks merge via the existing `security-check` required-status-check, and `security-approved` is withheld. No new pipeline state introduced.

**3. Pass the flag to the model** — add to `summary_for_model`:
```python
"any_tool_failed": any_tool_failed,
```
so the overview comment can distinguish *why* the check failed.

**4. Extend `_SYSTEM_PROMPT`** with a third case: when `has_critical` is `False` but `any_tool_failed` is `True`, instruct the model to state plainly that the **scan is incomplete** — not that vulnerabilities were found — and that `security-check` is failing because a scanner didn't run, not because of a finding. Distinct wording matters here: a reviewer skimming a red X should not conclude "vulnerabilities present" when the real story is "we don't actually know yet."

**5. Update the check-run title logic:**
```python
if has_critical:
    title = "Security scan: blocked"
elif any_tool_failed:
    title = "Security scan: incomplete — scanner failure"
else:
    title = "Security scan: passed"
```

**6. Fix the `--dry-run` printed reason**, which currently hardcodes `"(none — Critical findings present)"` regardless of actual cause:
```python
if label_to_apply:
    reason = label_to_apply
elif has_critical:
    reason = "(none — Critical findings present)"
else:
    reason = "(none — one or more scanners failed to run; see tool_run_failures)"
```

## Recovery Path

No new mechanism needed. Security already has no retry-loop by design (Document 6 has no `security-loop-back` label) — a scanner failure is almost always transient or environmental (timeout, missing binary, NVD rate-limit), so pushing any new commit re-triggers a fresh Security run under existing behavior. If a reviewer judges a specific scanner failure safe to proceed past (e.g. a known, temporary NVD outage against an already-reviewed dependency set), the project's existing documented human-override authority — the same manual-triage precedent already exercised for `qc-retry-limit-reached` — covers manually applying `security-approved`. No new override path needs to be built.

## Verification Plan

Mirror the existing synthetic-data verification discipline (the 23-check pattern from chat 31) — pure unit-level checks against `run_security_agent`'s internals, no live API/GitHub calls needed to validate the logic itself:

| Case | `ran` per tool | Findings | Expected `check_conclusion` | Expected `label_to_apply` |
|---|---|---|---|---|
| Baseline clean pass (unchanged) | all `True` | none | `success` | `security-approved` |
| **The fixed case** — one tool silently failed, no findings elsewhere | one `False`, rest `True` | none | `failure` | `None` |
| Tool failed *and* a genuine Critical exists elsewhere | one `False`, rest `True` | Critical present | `failure` | `None` (already correct pre-fix — confirm it still holds) |
| Total scanner collapse | all `False` | none (none ran) | `failure` | `None` |

Also re-verify the `--dry-run` printed reason text against each row above.

Once the unit-level fix is committed, a live confirmation (real PR, real check run) can follow using a deliberately broken scanner invocation — e.g. a temporarily invalid Dependency-Check argument — mirroring how the Deploy Agent wiring spec's Fix 3 was proven both locally and against live infrastructure.

## Files Touched

- `core/agents/security_agent.py` — `run_security_agent()` (verdict computation, dry-run print), `_SYSTEM_PROMPT` (new branch), check-run title logic.
- No workflow YAML changes needed — `05-security.yml` only invokes the script and reacts to its exit code / side effects; the fix is entirely internal to the script.

## Cross-reference

Document 3's Security Tooling section (§3.5, this cleanup pass) now names this spec directly as the open item — once implemented and verified, remove that inline pointer and note the fix as closed there too.
