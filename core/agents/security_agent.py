"""
FORGE Security Agent — Stage 5 (Security).

Runs five security scanners (via shell, or the GitHub API for Dependabot)
against a checked-out copy of the feature branch — Semgrep (SAST), Gitleaks
(secrets detection), GitHub Dependabot alerts (repo-wide, default-branch
dependency vulnerability scanning, via API), and npm audit / dotnet list
package --vulnerable (per-PR dependency vulnerability scanning, against the
real manifests on THIS checkout — added 2026-09-05, Item #52, see the
dedicated section below for why Dependabot alone isn't sufficient here) —
parses their output,
maps every finding to FORGE's locked Critical/High/Medium/Low schema
(Document 7) using a fixed, deterministic table per tool (never an LLM
judgment call), and:

  - Posts every finding as a severity-tagged inline PR review comment on the
    feature PR in the monorepo (forge-demo-apps) — Document 2 §4.7. Comment
    bodies are built deterministically; Claude is not asked to interpret or
    reword individual findings.
  - Creates a completed GitHub check run named "security-check" on the PR's
    head commit: conclusion "failure" if any Critical finding exists (this is
    what actually blocks merge, via the required-status-check branch
    protection rule — Build Plan 4.8), "success" otherwise. The check run
    exists independent of any label — Document 2 §3 notes branch protection
    waits on this named check resolving, not on a label being applied.
  - If there are no Critical findings: applies `security-approved` to the
    FORGE tracking issue directly (following the same agent-applies-the-label
    precedent as qa_agent.py's qa-approved; Document 6's Label Reference table
    says "Applied by: Security Reviewer" for this label, same pre-existing
    table/reality mismatch already flagged for qa-approved in the QA Agent's
    own session notes — not re-litigated here).
  - Claude is used only once per run, to write a short human-facing overview
    comment given the already-computed deterministic finding counts/severities
    — it does not re-judge severity and does not write the individual inline
    comment bodies.

Unlike QA, there is no retry-loop/attempt-counting here: Document 6 has no
`security-loop-back` or retry-limit label for this stage. Security re-scans
on every PR update; the failing check run is what blocks merge until findings
are resolved, not a retry budget.

KNOWN LIMITATION (flagged, not fixed here): re-running this agent after a fix
re-posts the full current finding set as new inline comments rather than
diffing against a prior run's comments — no de-duplication against previously
posted findings exists yet. Flagged as an open item for whoever wires Phase 4,
same pattern as other gaps already tracked in FORGE-context.

Severity mapping (fixed, per tool — Document 7: "Locked... used consistently
across SAST, secrets, and dependency scanning outputs"):
  - Gitleaks: every finding -> Critical. Gitleaks has no lesser-severity
    output category of its own; a hardcoded secret is always treated as
    Critical under this fixed table. Test/fixture project paths are excluded
    from scanning entirely via team/gitleaks-allowlist.toml (team-configurable
    per Document 7's Flexible/Locked model for the secrets detection tool) --
    a hardcoded fake key in a WebApplicationFactory or __tests__ mock never
    reaches this classifier in the first place.
  - Dependabot: security_advisory.severity arrives pre-computed as
    critical/high/medium/low -- mapped 1:1 (no CVSS-threshold math needed;
    that was Dependency-Check-specific). If a future alert somehow lacks a
    severity field, defaults to Medium (logged) rather than silently
    under-reporting as Low, matching the same-spirit default Dependency-Check
    used for scoreless findings.
  - Semgrep: ERROR -> High, WARNING -> Medium, INFO -> Low. NOTE: under this
    fixed table, Semgrep findings can never be classified Critical — same
    kind of documented best-effort limitation as QA's assertion-vs-crash
    heuristic (Semgrep community rules don't expose a clean CVSS-equivalent
    score to threshold against).
  - npm audit / dotnet list package --vulnerable: same critical/high/medium/
    low vocabulary as Dependabot, mapped 1:1 (npm's lowercase "moderate" ->
    Medium, its "info" tier -> Low, no equivalent in this fixed schema
    otherwise). See the dedicated section below for the full rationale.

Like qa_agent.py, this script needs the actual repository contents on disk —
it assumes a local checkout of the monorepo at the feature branch already
exists (passed via --repo-path), populated by the invoking GitHub Actions
job's own actions/checkout step (Phase 4, step 4.6, not yet wired). This
script does not clone anything itself.

PREREQUISITE: semgrep and gitleaks must be on PATH wherever this script
runs. Unlike QA's dotnet/npm (already required for local app development),
these are tooling dependencies specific to the Security stage. See
CLAUDE.md for install notes. npm audit / dotnet list package --vulnerable
(added 2026-09-05) reuse the same dotnet/npm CLIs QA already requires --
no new tooling dependency, but this script's own CI job must have them on
PATH too (previously only needed for QA's job).

DEPENDENCY SCANNING (swapped from OWASP Dependency-Check to GitHub
Dependabot alerts, 2026-08-19 -- see docs/FORGE-DependencyScanner-Dependabot-
Swap-Spec.md): Dependency-Check had timed out twice consecutively in CI at
its 1800s ceiling, root-caused to NVD database sync being much slower over
GitHub Actions' network path than locally, and separately required a
suppression file to handle CPE-matching false positives. Dependabot alerts
are precomputed by GitHub in the background -- this stage now just queries
an API (seconds, not a 30-60 min scan) via get_dependabot_alerts() /
_run_dependabot_check() below. NVD_API_KEY is no longer used by this script
(left as a still-configured Actions secret for now, in case of rollback --
see the spec's Rollback section). Requires the forge-pipeline GitHub App
installation to have the "Dependabot alerts: Read-only" permission
(GitHub's actual permission key is `vulnerability_alerts`) and both repos
to have Dependabot alerts + dependency graph enabled (Settings → Code
security and analysis) -- confirmed live prerequisites for this repo as of
the swap date, not assumed.

Usage:
    python -m core.agents.security_agent --issue-number 2 --request-id REQ-2026-01 \\
        --pr-number 5 --repo-path /path/to/forge-demo-apps-checkout
    python -m core.agents.security_agent --issue-number 2 --request-id REQ-2026-01 \\
        --pr-number 5 --repo-path /path/to/forge-demo-apps-checkout --dry-run

CLI arguments:
    --issue-number   FORGE tracking issue number in forge-template, used to
                     post a failure comment (best-effort) and apply
                     `security-approved` when clean (required).
    --request-id     FORGE request ID. Used to locate services/<request-id>/
                     within --repo-path (required).
    --pr-number      The feature PR number in forge-demo-apps, used to resolve
                     the head SHA, post inline review comments, and create the
                     check run. Required for a real run; optional for
                     --dry-run.
    --repo-path      Local path to an existing checkout of forge-demo-apps at
                     the feature branch (required — see module docstring;
                     this script does not clone anything itself).
    --existing-service  Item #25 §2.1: the "If Enhancement -- Existing Service
                     Name" value from the intake spreadsheet, resolved by
                     05-security.yml's own "Determine Enhancement status" step
                     (mirrors 03-implementation.yml's Item #24 step). When
                     set, Security scans the real existing
                     services/<existing_service>/ folder instead of
                     services/<request_id>/, which doesn't exist for an
                     Enhancement request. Optional -- omitted or blank means
                     Greenfield (unchanged behavior).
    --dry-run        Run all scans, parse results, compute severities,
                     and call Claude for the overview write-up, but print
                     everything to stdout instead of posting review comments,
                     creating a check run, or applying the label.

Per ADR-0011 / Document 6: the invoke_agent() call is wrapped in try/except at
the call site. On failure, a failure comment is posted to the tracking issue
(best-effort, real run only) before the exception is re-raised.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.agents.utils.claude_agent_wrapper import invoke_agent
from core.agents.utils.enhancement_target import resolve_service_root
from core.agents.utils.github_helper import (
    add_label,
    create_check_run,
    create_review_with_comments,
    create_single_review_comment,
    get_dependabot_alerts,
    get_dependency_graph_package_count,
    get_pr,
    post_comment,
)

logger = logging.getLogger(__name__)

_STAGE_NAME = "security"
_MAX_TOKENS = 2000
# Real observed run times (2026-08-19, live CI run): Semgrep ~4.6s,
# Gitleaks ~0.05s -- neither remotely approaches the old 1800s ceiling,
# which existed only to accommodate Dependency-Check's NVD sync (now
# removed, see the Dependabot swap note above). 600s leaves >100x headroom
# over both observed times while still failing fast on a genuine hang,
# rather than carrying forward a 30-minute allowance neither tool needs.
_TOOL_TIMEOUT_SECONDS = 600
_CHECK_RUN_NAME = "security-check"  # must match Build Plan 4.8's branch-protection required check

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GITLEAKS_ALLOWLIST_CONFIG = _REPO_ROOT / "team" / "gitleaks-allowlist.toml"

_SEV_CRITICAL = "Critical"
_SEV_HIGH = "High"
_SEV_MEDIUM = "Medium"
_SEV_LOW = "Low"


@dataclass
class Finding:
    tool: str            # "semgrep" | "gitleaks" | "dependabot" | "npm-audit" | "dotnet-audit"
    severity: str         # Critical | High | Medium | Low
    path: str | None      # repo-relative file path, if applicable
    line: int | None      # 1-indexed line, if applicable
    rule_id: str
    message: str


@dataclass
class ScanResult:
    tool: str
    ran: bool
    findings: list[Finding]
    run_failure_message: str | None = None  # set when ran=False


def _run_shell(command: list[str], cwd: str) -> subprocess.CompletedProcess:
    logger.info("Running: %s (cwd=%s)", " ".join(command), cwd)
    resolved = shutil.which(command[0]) or command[0]
    return subprocess.run(
        [resolved, *command[1:]],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TOOL_TIMEOUT_SECONDS,
    )


# ---------------------------------------------------------------------------
# Semgrep (SAST)
# ---------------------------------------------------------------------------

def _run_semgrep(service_dir: str) -> ScanResult:
    with tempfile.TemporaryDirectory() as results_dir:
        json_path = Path(results_dir) / "semgrep-results.json"
        try:
            result = _run_shell(
                ["semgrep", "--config=auto", "--json", f"--output={json_path}", "."],
                cwd=service_dir,
            )
        except subprocess.TimeoutExpired:
            return ScanResult(tool="semgrep", ran=False, findings=[],
                               run_failure_message=f"semgrep timed out after {_TOOL_TIMEOUT_SECONDS}s.")

        if not json_path.exists():
            tail = (result.stdout or "")[-3000:] + (result.stderr or "")[-1000:]
            return ScanResult(
                tool="semgrep", ran=False, findings=[],
                run_failure_message=f"semgrep failed to produce a JSON report. Tail of output:\n\n{tail}",
            )
        return _parse_semgrep(json_path)


def _classify_semgrep_severity(raw_severity: str) -> str:
    """Fixed mapping (module docstring) — Semgrep can never map to Critical here."""
    mapping = {"ERROR": _SEV_HIGH, "WARNING": _SEV_MEDIUM, "INFO": _SEV_LOW}
    return mapping.get((raw_severity or "").upper(), _SEV_MEDIUM)


def _parse_semgrep(json_path: Path) -> ScanResult:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    findings: list[Finding] = []
    for r in data.get("results", []):
        extra = r.get("extra", {})
        findings.append(Finding(
            tool="semgrep",
            severity=_classify_semgrep_severity(extra.get("severity", "")),
            path=r.get("path"),
            line=(r.get("start") or {}).get("line"),
            rule_id=r.get("check_id", "unknown-rule"),
            message=(extra.get("message") or "")[:1000],
        ))
    return ScanResult(tool="semgrep", ran=True, findings=findings)


# ---------------------------------------------------------------------------
# Gitleaks (secrets detection)
# ---------------------------------------------------------------------------

def _run_gitleaks(service_dir: str) -> ScanResult:
    """
    --no-git: treat service_dir as a plain filesystem tree, not a git
    repository, so this is a directory-scoped scan of current file contents
    (what we want here), not a full commit-history scan of the whole monorepo.
    --exit-code 0: don't let gitleaks' nonzero-on-findings exit code matter —
    we determine "ran" from report-file presence, same principle as QA's
    TRX/Jest presence check, not from process exit code.
    """
    with tempfile.TemporaryDirectory() as results_dir:
        json_path = Path(results_dir) / "gitleaks-results.json"
        command = ["gitleaks", "detect", "--source", ".", "--no-git",
                   "--report-format", "json", "--report-path", str(json_path),
                   "--exit-code", "0"]
        if _GITLEAKS_ALLOWLIST_CONFIG.exists():
            command.extend(["--config", str(_GITLEAKS_ALLOWLIST_CONFIG)])
        else:
            logger.warning(
                "Gitleaks allowlist config not found at %s -- running with "
                "Gitleaks' default ruleset only (no test-path exclusions). "
                "Team-configurable per Document 7; see team/gitleaks-allowlist.toml.",
                _GITLEAKS_ALLOWLIST_CONFIG,
            )
        try:
            result = _run_shell(command, cwd=service_dir)
        except subprocess.TimeoutExpired:
            return ScanResult(tool="gitleaks", ran=False, findings=[],
                               run_failure_message=f"gitleaks timed out after {_TOOL_TIMEOUT_SECONDS}s.")

        if not json_path.exists():
            # Gitleaks omits the report file entirely when there are zero
            # findings in some versions — treat that as "ran, clean", not a
            # run failure, distinguishing it from a genuine execution error
            # via the process's own exit code (nonzero + no file = real error).
            if result.returncode == 0:
                return ScanResult(tool="gitleaks", ran=True, findings=[])
            tail = (result.stdout or "")[-3000:] + (result.stderr or "")[-1000:]
            return ScanResult(
                tool="gitleaks", ran=False, findings=[],
                run_failure_message=f"gitleaks failed to produce a report. Tail of output:\n\n{tail}",
            )
        return _parse_gitleaks(json_path)


def _parse_gitleaks(json_path: Path) -> ScanResult:
    raw = json_path.read_text(encoding="utf-8").strip()
    data = json.loads(raw) if raw else []
    findings: list[Finding] = []
    for entry in data:
        findings.append(Finding(
            tool="gitleaks",
            severity=_SEV_CRITICAL,  # fixed mapping — every gitleaks finding is Critical
            path=entry.get("File"),
            line=entry.get("StartLine"),
            rule_id=entry.get("RuleID", "unknown-rule"),
            message=(entry.get("Description") or "Potential secret detected")[:1000],
        ))
    return ScanResult(tool="gitleaks", ran=True, findings=findings)


# ---------------------------------------------------------------------------
# GitHub Dependabot alerts (dependency vulnerability scanning)
#
# Replaced OWASP Dependency-Check 2026-08-19 -- see docs/
# FORGE-DependencyScanner-Dependabot-Swap-Spec.md for the full root-cause
# writeup (CI timeout class + CPE false-positive class, not just a tool
# swap for its own sake).
# ---------------------------------------------------------------------------

def _classify_dependabot_severity(raw_severity: str | None) -> str:
    """
    Fixed mapping (module docstring): Dependabot's security_advisory.severity
    arrives pre-computed as critical/high/medium/low -- no CVSS-threshold
    math needed. Defaults to Medium (logged) if a future alert somehow lacks
    this field, same defensive spirit as Dependency-Check's old
    no-CVSS-score default.
    """
    mapping = {
        "critical": _SEV_CRITICAL,
        "high": _SEV_HIGH,
        "medium": _SEV_MEDIUM,
        "low": _SEV_LOW,
    }
    severity = mapping.get((raw_severity or "").lower())
    if severity is None:
        logger.warning(
            "Dependabot alert has an unrecognized/missing severity %r -- defaulting to Medium.",
            raw_severity,
        )
        return _SEV_MEDIUM
    return severity


def _dependabot_alert_to_finding(alert: dict) -> Finding:
    advisory = alert.get("security_advisory") or {}
    dependency = alert.get("dependency") or {}
    vulnerability = alert.get("security_vulnerability") or {}
    package_name = (dependency.get("package") or {}).get("name", "unknown-package")

    ghsa_id = advisory.get("ghsa_id") or "unknown-advisory"
    cve_id = advisory.get("cve_id")
    rule_id = f"{ghsa_id} ({cve_id})" if cve_id else ghsa_id

    patched = vulnerability.get("first_patched_version") or {}
    patched_identifier = patched.get("identifier") if isinstance(patched, dict) else None
    message = advisory.get("summary") or ""
    if patched_identifier:
        message = f"{message} First patched version: {patched_identifier}."

    return Finding(
        tool="dependabot",
        severity=_classify_dependabot_severity(advisory.get("severity")),
        path=dependency.get("manifest_path"),
        line=None,  # dependency findings are manifest-level, not line-anchored
        rule_id=rule_id,
        message=(f"{package_name}: {message}")[:1000],
    )


def _run_dependabot_check(repo_full_name: str, service_root: str) -> ScanResult:
    """
    ran=False on any of: API auth/permission failure (see
    get_dependabot_alerts()'s own docstring on the 403/404 ambiguity),
    dependency graph not populated -- never on "zero alerts returned for a
    legitimately clean repo."

    Filters the repo-wide alert list down to this request's manifests under
    service_root (the resolved target from resolve_service_root() -- Item #25
    §2.1/§2.3: services/<existing_service>/ for an Enhancement request, else
    services/<request_id>/) -- Dependabot alerts are repo-wide, unlike
    Dependency-Check's old --scan services/<request-id>/ path scoping, so
    without this filter a PR touching REQ-2026-03 would surface findings
    from every other request's manifests too (confirmed live: 102 open
    alerts repo-wide across REQ-2026-01/02/03 combined, only ~28 actually
    under REQ-2026-03). Real latent bug fixed here: this used to build its
    own prefix from raw request_id independently of service_dir/service_root
    -- for an Enhancement request that would have silently filtered against
    the wrong (nonexistent) request_id path even once Semgrep/Gitleaks were
    correctly scanning the real existing-service directory, returning zero
    findings for the actual changed manifests rather than a genuine failure.
    """
    try:
        alerts = get_dependabot_alerts(repo_full_name, state="open")
    except Exception as exc:
        return ScanResult(tool="dependabot", ran=False, findings=[], run_failure_message=str(exc))

    if not alerts:
        # Empty could mean "genuinely clean repo" or "dependency graph isn't
        # populated yet" -- GitHub gives no other documented signal to tell
        # these apart (see get_dependabot_alerts()'s docstring), so fall
        # back to checking the SBOM package count as a real, checkable
        # secondary signal.
        try:
            package_count = get_dependency_graph_package_count(repo_full_name)
        except Exception as exc:
            return ScanResult(tool="dependabot", ran=False, findings=[], run_failure_message=str(exc))
        if package_count == 0:
            return ScanResult(
                tool="dependabot", ran=False, findings=[],
                run_failure_message=(
                    f"Dependabot returned zero alerts for {repo_full_name}, and the repo's "
                    "dependency-graph SBOM shows zero packages -- this looks like the "
                    "dependency graph is not populated, not a genuinely clean repo. "
                    "Treating as a scan failure rather than risk a false clean."
                ),
            )

    prefix = f"{service_root}/"
    relevant = [a for a in alerts if (a.get("dependency", {}).get("manifest_path") or "").startswith(prefix)]
    findings = [_dependabot_alert_to_finding(a) for a in relevant]
    return ScanResult(tool="dependabot", ran=True, findings=findings)


# ---------------------------------------------------------------------------
# npm audit / dotnet list package --vulnerable (dependency scanning, per-PR)
#
# Added 2026-09-05 (Item #52): Dependabot alerts (above) are computed from
# GitHub's dependency graph, which is anchored to the repo's DEFAULT branch --
# confirmed live via a real SBOM showing only 2 entries (no app packages) on
# a Greenfield request's first-ever Implementation PR, whose real manifests
# exist only on the unmerged feature branch. GitHub's actual per-PR answer to
# this (Dependency Review, dependency-graph/compare/{basehead}) returns 403
# for private repos without paid GitHub Advanced Security -- confirmed live
# against mike-digital-platform. npm audit / dotnet list package --vulnerable
# are the free alternative: both read the real manifests on THIS checkout
# directly (no dependence on any other branch's state), the same way
# Semgrep/Gitleaks already do. Kept alongside Dependabot, not replacing it --
# Dependabot is still the right tool for continuous post-merge monitoring
# across the whole repo; these two are what actually gate a fresh PR.
#
# Confirmed live (a real historical checkout with next@14.2.5, since patched):
# npm audit needs only package.json/package-lock.json -- works with
# node_modules absent, so no `npm install` step is required first (verified
# by removing node_modules and re-running: identical result). dotnet list
# package --vulnerable, by contrast, requires `dotnet restore` to have run
# first (errors with "No assets file was found... run restore" otherwise) --
# confirmed live the same way.
#
# FUTURE NOTE: if this FORGE instance ever moves to a GitHub plan/tier with
# GitHub Advanced Security included, prefer switching to the Dependency
# Review API (dependency-graph/compare/{basehead}) instead of (or as well
# as) these two -- it's GitHub's own first-party per-PR dependency diff, with
# richer data than a bare CLI audit (e.g. "was this vulnerability newly
# introduced by this PR" rather than "does this vulnerability exist at all").
# npm audit / dotnet list package --vulnerable are the free-tier substitute,
# not assumed to be the permanent answer.
# ---------------------------------------------------------------------------

def _classify_dependency_audit_severity(raw_severity: str | None) -> str:
    """
    Shared by both npm audit and dotnet list package --vulnerable. npm's
    severities are lowercase (info/low/moderate/high/critical, confirmed live
    via a real `npm audit --json` run); dotnet's are capitalized
    (Low/Moderate/High/Critical, confirmed live via a real `dotnet list
    package --vulnerable --format json` run). npm's "info" tier has no
    equivalent in FORGE's fixed four-level schema -- mapped to Low, the same
    spirit as Dependabot's missing-severity default one tier below unknown.
    """
    mapping = {
        "critical": _SEV_CRITICAL,
        "high": _SEV_HIGH,
        "moderate": _SEV_MEDIUM,
        "medium": _SEV_MEDIUM,
        "low": _SEV_LOW,
        "info": _SEV_LOW,
    }
    severity = mapping.get((raw_severity or "").lower())
    if severity is None:
        logger.warning(
            "Dependency audit finding has an unrecognized/missing severity %r -- "
            "defaulting to Medium.",
            raw_severity,
        )
        return _SEV_MEDIUM
    return severity


def _run_npm_audit(service_dir: str) -> ScanResult:
    """
    ran=True with zero findings when there's no frontend/package.json at all --
    "not applicable" (no frontend unit in this request), same principle as
    QA's own not_applicable outcome for a missing test suite, not a scan
    failure. ran=False only on a genuine execution problem (npm missing,
    malformed output, or npm's own top-level "error" response) -- never on
    "zero vulnerabilities for a real, present package.json", which is a
    legitimate clean result here (unlike Dependabot's ambiguous empty-alerts
    case, since this reads the manifest directly with no default-branch
    dependency).

    npm audit REQUIRES an existing package-lock.json -- confirmed live (Item
    #54): without one it exits 1 with a top-level {"error": {"code":
    "ENOLOCK", ...}} JSON body, which has no "vulnerabilities" key. The
    original version of this function only ever checked for that key's
    presence, so a missing lockfile silently produced "ran=True, 0 findings"
    -- a real false-clean, caught only because Mike asked "how did zero
    findings come up" and pushed for a from-scratch verification rather than
    accepting the reported result. Generate one on the fly with
    `npm install --package-lock-only` (confirmed live: ~37s for a real
    Next.js app, well under the timeout ceiling) when missing, matching
    npm's own suggested remedy in the ENOLOCK error text -- this makes scans
    genuinely possible for requests that never got a lockfile committed
    (e.g. a Managed Agents subagent that ran `npm install` rather than
    `npm ci`+commit), rather than perpetually reporting "incomplete."
    """
    frontend_dir = Path(service_dir) / "frontend"
    if not (frontend_dir / "package.json").is_file():
        return ScanResult(tool="npm-audit", ran=True, findings=[])

    if not (frontend_dir / "package-lock.json").is_file():
        try:
            lock_result = _run_shell(["npm", "install", "--package-lock-only"], cwd=str(frontend_dir))
        except subprocess.TimeoutExpired:
            return ScanResult(tool="npm-audit", ran=False, findings=[],
                               run_failure_message=f"npm install --package-lock-only timed out after {_TOOL_TIMEOUT_SECONDS}s.")
        except FileNotFoundError:
            return ScanResult(tool="npm-audit", ran=False, findings=[],
                               run_failure_message="npm is not on PATH.")
        if lock_result.returncode != 0:
            tail = (lock_result.stdout or "")[-2000:] + (lock_result.stderr or "")[-1000:]
            return ScanResult(
                tool="npm-audit", ran=False, findings=[],
                run_failure_message=f"npm install --package-lock-only failed (no committed lockfile). Tail:\n\n{tail}",
            )

    try:
        result = _run_shell(["npm", "audit", "--json"], cwd=str(frontend_dir))
    except subprocess.TimeoutExpired:
        return ScanResult(tool="npm-audit", ran=False, findings=[],
                           run_failure_message=f"npm audit timed out after {_TOOL_TIMEOUT_SECONDS}s.")
    except FileNotFoundError:
        return ScanResult(tool="npm-audit", ran=False, findings=[],
                           run_failure_message="npm is not on PATH.")

    # npm audit exits 1 (not 0) the moment it finds any vulnerability -- same
    # non-zero-on-findings behavior as gitleaks/dotnet below. Parse stdout
    # regardless of exit code; only a genuinely unparseable body is a failure.
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        tail = (result.stdout or "")[-3000:] + (result.stderr or "")[-1000:]
        return ScanResult(
            tool="npm-audit", ran=False, findings=[],
            run_failure_message=f"npm audit did not produce parseable JSON. Tail of output:\n\n{tail}",
        )

    # Defense in depth: npm audit can return a top-level {"error": {...}}
    # JSON body (ENOLOCK and other cases) that parses cleanly but has no
    # "vulnerabilities" key -- must be checked explicitly, or it silently
    # reads as "ran cleanly, found nothing" (the exact bug this function
    # just had). Never treat an error response as a clean scan.
    if "error" in data:
        err = data["error"]
        detail = err.get("summary") or err.get("detail") or json.dumps(err)
        return ScanResult(
            tool="npm-audit", ran=False, findings=[],
            run_failure_message=f"npm audit returned an error: {detail}",
        )

    findings: list[Finding] = []
    for pkg_name, vuln in (data.get("vulnerabilities") or {}).items():
        severity = _classify_dependency_audit_severity(vuln.get("severity"))
        via = vuln.get("via") or []
        titles = [v.get("title") for v in via if isinstance(v, dict) and v.get("title")]
        urls = [v.get("url") for v in via if isinstance(v, dict) and v.get("url")]
        message = "; ".join(titles) if titles else f"Vulnerable range: {vuln.get('range', 'unknown')}"
        if urls:
            message = f"{message} ({urls[0]})"
        findings.append(Finding(
            tool="npm-audit",
            severity=severity,
            path="frontend/package.json",
            line=None,
            rule_id=pkg_name,
            message=message[:1000],
        ))
    return ScanResult(tool="npm-audit", ran=True, findings=findings)


def _run_dotnet_audit(service_dir: str) -> ScanResult:
    """
    Iterates every non-test backend unit under service_dir/backend/, using the
    exact same discovery convention as deploy_agent.py's own unit detection
    (rglob for *.csproj, skip any path segment containing "test" case-
    insensitively) -- so this scans the same real units Deploy will later
    build, not an independently-guessed set.

    ran=True with zero findings when there's no backend/ at all or it has no
    matching .csproj (not applicable, mirroring _run_npm_audit() above).
    ran=False if restore or list fails for any *one* unit -- a partial
    dependency scan is treated the same as a failed one (Document 7's
    established "unknown status blocks" precedent), not silently reported as
    clean for the units that did succeed.
    """
    backend_dir = Path(service_dir) / "backend"
    if not backend_dir.is_dir():
        return ScanResult(tool="dotnet-audit", ran=True, findings=[])

    csproj_paths = [
        p for p in sorted(backend_dir.rglob("*.csproj"))
        if not any("test" in part.lower() for part in p.relative_to(backend_dir).parts)
    ]
    if not csproj_paths:
        return ScanResult(tool="dotnet-audit", ran=True, findings=[])

    findings: list[Finding] = []
    for csproj_path in csproj_paths:
        try:
            restore_result = _run_shell(["dotnet", "restore", str(csproj_path)], cwd=service_dir)
        except subprocess.TimeoutExpired:
            return ScanResult(tool="dotnet-audit", ran=False, findings=[],
                               run_failure_message=f"dotnet restore timed out for {csproj_path.name}.")
        except FileNotFoundError:
            return ScanResult(tool="dotnet-audit", ran=False, findings=[],
                               run_failure_message="dotnet is not on PATH.")
        if restore_result.returncode != 0:
            tail = (restore_result.stdout or "")[-2000:] + (restore_result.stderr or "")[-1000:]
            return ScanResult(
                tool="dotnet-audit", ran=False, findings=[],
                run_failure_message=f"dotnet restore failed for {csproj_path.name}. Tail:\n\n{tail}",
            )

        try:
            list_result = _run_shell(
                ["dotnet", "list", str(csproj_path), "package", "--vulnerable",
                 "--include-transitive", "--format", "json"],
                cwd=service_dir,
            )
        except subprocess.TimeoutExpired:
            return ScanResult(tool="dotnet-audit", ran=False, findings=[],
                               run_failure_message=f"dotnet list package timed out for {csproj_path.name}.")

        try:
            data = json.loads(list_result.stdout or "{}")
        except json.JSONDecodeError:
            tail = (list_result.stdout or "")[-3000:] + (list_result.stderr or "")[-1000:]
            return ScanResult(
                tool="dotnet-audit", ran=False, findings=[],
                run_failure_message=f"dotnet list package did not produce parseable JSON for {csproj_path.name}. Tail:\n\n{tail}",
            )
        if data.get("problems"):
            problem_text = "; ".join(p.get("text", "") for p in data["problems"])
            return ScanResult(
                tool="dotnet-audit", ran=False, findings=[],
                run_failure_message=f"dotnet list package reported problems for {csproj_path.name}: {problem_text}",
            )

        rel_csproj = csproj_path.relative_to(service_dir)
        for project in data.get("projects", []):
            for framework in project.get("frameworks", []):
                for key in ("topLevelPackages", "transitivePackages"):
                    for pkg in framework.get(key) or []:
                        for vuln in pkg.get("vulnerabilities") or []:
                            findings.append(Finding(
                                tool="dotnet-audit",
                                severity=_classify_dependency_audit_severity(vuln.get("severity")),
                                path=str(rel_csproj).replace("\\", "/"),
                                line=None,
                                rule_id=f"{pkg['id']} {pkg.get('resolvedVersion', '')}".strip(),
                                message=f"Advisory: {vuln.get('advisoryurl', 'unknown')}"[:1000],
                            ))
    return ScanResult(tool="dotnet-audit", ran=True, findings=findings)


# ---------------------------------------------------------------------------
# Shared: comment building, posting, orchestration
# ---------------------------------------------------------------------------

def _build_finding_comment(finding: Finding) -> str:
    return (
        f"**[{finding.severity}] {finding.tool}** — `{finding.rule_id}`\n\n"
        f"{finding.message}"
    )


def post_findings(pr_number: int, commit_sha: str, findings: list[Finding]) -> dict:
    """
    Post every line-anchored finding as one batched inline review. Findings
    with no path/line (dependabot -- manifest-level, not line-anchored) or
    that the batch review rejects as outside the diff fall back to
    per-finding attempts, then to a single aggregated plain PR comment for
    whatever still couldn't be attached.
    """
    line_anchored = [f for f in findings if f.path and f.line]
    unanchored = [f for f in findings if not (f.path and f.line)]

    posted = 0
    fallback_failures: list[Finding] = []

    if line_anchored:
        comments = [
            {"path": f.path, "line": f.line, "body": _build_finding_comment(f)}
            for f in line_anchored
        ]
        try:
            create_review_with_comments(pr_number, commit_sha, comments)
            posted = len(comments)
        except Exception:
            logger.warning(
                "Batch review failed (likely a line outside the diff) — "
                "retrying %d finding(s) individually.",
                len(line_anchored),
            )
            for f in line_anchored:
                try:
                    create_single_review_comment(
                        pr_number, commit_sha, f.path, f.line, _build_finding_comment(f)
                    )
                    posted += 1
                except Exception:
                    fallback_failures.append(f)

    to_summarize = unanchored + fallback_failures
    if to_summarize:
        body = "**Additional security findings (couldn't attach inline — see details below):**\n\n" + "\n\n---\n\n".join(
            f"`{f.path or 'N/A'}` — {_build_finding_comment(f)}" for f in to_summarize
        )
        from core.agents.utils.github_helper import post_pr_comment
        post_pr_comment(pr_number, body)

    return {"posted_inline": posted, "posted_as_summary": len(to_summarize)}


_TOOL_DISPLAY_NAMES = {
    "semgrep": "Semgrep",
    "gitleaks": "Gitleaks",
    "dependabot": "GitHub Dependabot",
    "npm-audit": "npm audit",
    "dotnet-audit": "dotnet list package --vulnerable",
}


def _build_finding_summary_table(counts_by_severity: dict[str, int]) -> str:
    """
    Built in Python, not by the model — same "deterministic code decides
    facts" principle already used for individual finding bodies
    (_build_finding_comment()). Added 2026-09-05 after confirming live,
    twice, that asking the model to transcribe a variable-length tool list
    into a table is unreliable: invoke_agent() never enables thinking, so a
    forced single-turn tool call gives the model no room to actually count
    before answering, and it kept writing a fixed "three tools" table even
    when five real entries were passed to it, before and after two
    increasingly explicit prompt rewrites.
    """
    total = sum(counts_by_severity.values())
    lines = ["| Severity | Count |", "|----------|-------|"]
    for sev, emoji in ((_SEV_CRITICAL, "🔴"), (_SEV_HIGH, "🟠"), (_SEV_MEDIUM, "🟡"), (_SEV_LOW, "🔵")):
        lines.append(f"| {emoji} {sev} | {counts_by_severity.get(sev, 0)} |")
    lines.append(f"| **Total** | **{total}** |")
    return "\n".join(lines)


def _build_results_by_tool_table(all_results: list[ScanResult]) -> str:
    """Same rationale as _build_finding_summary_table() above."""
    lines = ["| Tool | Findings | Status |", "|------|----------|--------|"]
    for r in all_results:
        display_name = _TOOL_DISPLAY_NAMES.get(r.tool, r.tool)
        status = "✅ Ran successfully" if r.ran else f"❌ Failed — {r.run_failure_message or 'no report produced'}"
        lines.append(f"| {display_name} | {len(r.findings)} | {status} |")
    return "\n".join(lines)


_SYSTEM_PROMPT = """You are the FORGE Security Agent for Legal Aid Alberta's software delivery \
pipeline, writing two short pieces of text for a feature PR's security check comment.

The Finding Summary table (by severity) and the Results by Tool table are built separately \
by deterministic code and inserted verbatim — you never see or write them, so there is no \
tool list or count for you to get wrong. You are given only: whether any Critical finding \
exists (has_critical), whether any_tool_failed is true (one or more scanners failed to \
execute at all — crashed, timed out, or never produced a report — a distinct case from \
"ran cleanly and found nothing"), and the check run conclusion.

Write exactly two things:
1. verdict_line — one short sentence: "blocked" (has_critical), "incomplete" \
(any_tool_failed and not has_critical), or "clear" (neither). Do not mention specific tools \
or counts here — those are in the tables above your text.
2. notes_markdown — one to three short bullet points of human-facing commentary:
   - If has_critical: state plainly that security-check is failing and blocks merge until \
resolved — do not imply anything else will unblock it.
   - If any_tool_failed and not has_critical: state plainly that the scan is INCOMPLETE and \
the true security status is not yet known — do not imply a vulnerability was found. Do not \
say `security-approved` was applied.
   - If neither: note that security-check passed and (if applicable) `security-approved` was \
applied — but that a Security Reviewer's explicit PR approval is still required regardless \
of severity (Document 6 Gate 5: even an all-clear scan needs human sign-off).

Do not re-judge severity, do not re-interpret individual findings (posted separately as \
inline PR comments), and do not attempt to reproduce either table yourself.

Submit via the submit_structured_output tool — do not respond with plain text."""

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict_line": {
            "type": "string",
            "description": "One short sentence stating the overall verdict (blocked / incomplete / clear).",
        },
        "notes_markdown": {
            "type": "string",
            "description": "One to three short Markdown bullet points of human-facing commentary — no tables, no tool names/counts.",
        },
    },
    "required": ["verdict_line", "notes_markdown"],
    "additionalProperties": False,
}


def run_security_agent(
    issue_number: int,
    request_id: str,
    repo_path: str,
    pr_number: int | None = None,
    dry_run: bool = False,
    existing_service: str | None = None,
) -> dict:
    """
    Core entry point. Returns a dict summarizing the run (findings by tool,
    check run conclusion, label applied, overview text).
    """
    if not dry_run and not pr_number:
        raise ValueError(
            "--pr-number is required for a real (non-dry-run) run — it determines "
            "where inline comments and the check run are posted. Refusing to "
            "proceed without it."
        )

    resolved_target = resolve_service_root(request_id, existing_service)
    service_dir = str(Path(repo_path) / resolved_target)
    repo_full_name = f"{os.environ['FORGE_GITHUB_OWNER']}/{os.environ['FORGE_TARGET_REPO']}"

    # Item #25 §2.3: same directory-existence check as QA's §2.2 fix, before
    # any scanner runs. Previously a missing target directory crashed
    # _run_semgrep() with an unhandled FileNotFoundError (subprocess.run()
    # raising on a nonexistent cwd) -- caught by the generic ADR-0011 except
    # block below, which did post a real failure comment and correctly
    # withhold security-approved (confirmed live -- this was never as silent
    # as it first looked), but named the raw Python exception rather than
    # the real Enhancement-target problem, and Gitleaks/Dependabot never got
    # a chance to run at all. Handled here as its own branch, not raised --
    # same non-raising shape as the existing any_tool_failed path below (the
    # check run, not the Actions job's exit code, is what blocks merge) --
    # and deliberately distinct from any_tool_failed: a scanner that never
    # got the chance to run because its target doesn't exist is a different
    # fact than one that ran and crashed.
    if not Path(service_dir).is_dir():
        if existing_service:
            context = (
                f"This is an Enhancement request targeting existing service "
                f"`{existing_service}` -- confirm the 'Existing Service Name' value "
                "on the intake spreadsheet matches a real `services/` folder in "
                "forge-demo-apps."
            )
        else:
            context = (
                f"Expected `services/{request_id}/` to exist for this Greenfield "
                "request -- has Implementation (Stage 3) run and committed a "
                "feature PR yet?"
            )
        message = (
            "⚠️ **FORGE Security Agent could not run.**\n\n"
            f"Expected service directory `{resolved_target}/` does not exist in this "
            "checkout. This is a distinct condition from a scanner crash or a clean "
            "scan -- no scanner ran against any real code.\n\n"
            f"{context}\n\n"
            "No `security-approved` applied. An Orchestration Manager needs to "
            "investigate."
        )
        logger.error(
            "Security Agent: resolved service directory '%s' does not exist under "
            "repo_path '%s' (request_id=%s, existing_service=%s)",
            resolved_target, repo_path, request_id, existing_service,
        )
        check_run_title = "Security scan: blocked — target directory not found"
        run_summary = {
            "counts_by_severity": {sev: 0 for sev in (_SEV_CRITICAL, _SEV_HIGH, _SEV_MEDIUM, _SEV_LOW)},
            "counts_by_tool": {},
            "check_conclusion": "failure",
            "label_to_apply": None,
            "overview_markdown": message,
            "target_missing": True,
        }

        if dry_run:
            print("=" * 20, "would post failure comment -- resolved target directory missing", "=" * 20)
            print(message)
            print("=" * 20, "check run (not created)", "=" * 20)
            print(f"name={_CHECK_RUN_NAME} conclusion=failure title={check_run_title!r}")
            print("=" * 20, "label (not applied)", "=" * 20)
            print("(none — resolved target directory does not exist)")
            return run_summary

        try:
            post_comment(issue_number, message)
        except Exception:
            logger.exception("Also failed to post missing-target comment to issue #%s", issue_number)

        pr = get_pr(pr_number)
        create_check_run(
            head_sha=pr["head"]["sha"],
            name=_CHECK_RUN_NAME,
            conclusion="failure",
            title=check_run_title,
            summary=message,
        )
        logger.info(
            "Security Agent: resolved target directory missing for request %s -- "
            "check run created with conclusion=failure, no label applied.",
            request_id,
        )
        return run_summary

    try:
        semgrep_result = _run_semgrep(service_dir)
        gitleaks_result = _run_gitleaks(service_dir)
        dependabot_result = _run_dependabot_check(repo_full_name, resolved_target)
        npm_audit_result = _run_npm_audit(service_dir)
        dotnet_audit_result = _run_dotnet_audit(service_dir)

        all_results = [
            semgrep_result, gitleaks_result, dependabot_result,
            npm_audit_result, dotnet_audit_result,
        ]
        any_tool_failed = any(not r.ran for r in all_results)
        all_findings = [f for r in all_results for f in r.findings]

        counts_by_severity = {sev: 0 for sev in (_SEV_CRITICAL, _SEV_HIGH, _SEV_MEDIUM, _SEV_LOW)}
        for f in all_findings:
            counts_by_severity[f.severity] += 1
        has_critical = counts_by_severity[_SEV_CRITICAL] > 0

        check_conclusion = "failure" if (has_critical or any_tool_failed) else "success"
        label_to_apply = None if (has_critical or any_tool_failed) else "security-approved"

        commit_sha = None
        if not dry_run:
            pr = get_pr(pr_number)
            commit_sha = pr["head"]["sha"]

        summary_for_model = {
            "tools_ran": {r.tool: r.ran for r in all_results},
            "tool_run_failures": {r.tool: r.run_failure_message for r in all_results if not r.ran},
            "counts_by_severity": counts_by_severity,
            "counts_by_tool": {
                r.tool: len(r.findings) for r in all_results
            },
            "has_critical": has_critical,
            "any_tool_failed": any_tool_failed,
            "check_conclusion": check_conclusion,
            "label_to_apply": label_to_apply,
        }
        user_prompt = (
            "## Deterministic Security Scan Results (already computed — report exactly as given)\n\n"
            f"```json\n{json.dumps(summary_for_model, indent=2)}\n```\n"
            "---\nProduce your structured output now."
        )

        result = invoke_agent(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=_MAX_TOKENS,
            stage_name=_STAGE_NAME,
            request_id=request_id,
            output_schema=_OUTPUT_SCHEMA,
        )
        if result.stop_reason == "max_tokens":
            raise ValueError(
                f"Model response was truncated at max_tokens={_MAX_TOKENS} — "
                "increase _MAX_TOKENS in security_agent.py and retry."
            )
        parsed_output = result.structured_output
        verdict_emoji = "🔴" if has_critical else ("🔶" if any_tool_failed else "🔒")
        verdict_title = "Blocked" if has_critical else ("Incomplete" if any_tool_failed else "All Clear")
        overview_markdown = (
            f"## {verdict_emoji} FORGE Security Scan — {verdict_title}\n\n"
            f"**Overall verdict:** {parsed_output['verdict_line']}\n\n"
            "---\n\n"
            "### Finding Summary\n\n"
            f"{_build_finding_summary_table(counts_by_severity)}\n\n"
            "---\n\n"
            "### Results by Tool\n\n"
            f"{_build_results_by_tool_table(all_results)}\n\n"
            "---\n\n"
            "### Notes\n\n"
            f"{parsed_output['notes_markdown']}"
        )

    except Exception as exc:
        logger.exception("Security Agent failed for request %s", request_id)
        if not dry_run:
            failure_body = (
                "⚠️ **FORGE Security Agent failed to complete.**\n\n"
                f"Error: `{exc}`\n\n"
                "An Orchestration Manager needs to investigate before this request "
                "can proceed. Do not apply `security-approved` yet."
            )
            try:
                post_comment(issue_number, failure_body)
            except Exception:
                logger.exception("Also failed to post failure comment to issue #%s", issue_number)
        raise

    run_summary = {
        "counts_by_severity": counts_by_severity,
        "counts_by_tool": {r.tool: len(r.findings) for r in all_results},
        "check_conclusion": check_conclusion,
        "label_to_apply": label_to_apply,
        "overview_markdown": overview_markdown,
    }

    if dry_run:
        print("=" * 20, "scan summary", "=" * 20)
        print(json.dumps(summary_for_model, indent=2))
        print("=" * 20, "overview comment (not posted)", "=" * 20)
        print(overview_markdown)
        print("=" * 20, "check run (not created)", "=" * 20)
        print(f"name={_CHECK_RUN_NAME} conclusion={check_conclusion}")
        print("=" * 20, "label (not applied)", "=" * 20)
        if label_to_apply:
            reason = label_to_apply
        elif has_critical:
            reason = "(none — Critical findings present)"
        else:
            reason = "(none — one or more scanners failed to run; see tool_run_failures)"
        print(reason)
        logger.info(
            "Dry run complete for request %s -- nothing posted, nothing labeled.",
            request_id,
        )
        return run_summary

    post_findings(pr_number, commit_sha, all_findings)

    from core.agents.utils.github_helper import post_pr_comment
    post_pr_comment(pr_number, overview_markdown)

    if has_critical:
        check_run_title = "Security scan: blocked"
    elif any_tool_failed:
        check_run_title = "Security scan: incomplete — scanner failure"
    else:
        check_run_title = "Security scan: passed"

    create_check_run(
        head_sha=commit_sha,
        name=_CHECK_RUN_NAME,
        conclusion=check_conclusion,
        title=check_run_title,
        summary=overview_markdown,
    )

    if label_to_apply:
        add_label(issue_number, label_to_apply)

    logger.info(
        "Security Agent complete for request %s -- check_conclusion=%s, %d finding(s) "
        "(%d Critical), label=%s.",
        request_id, check_conclusion, len(all_findings),
        counts_by_severity[_SEV_CRITICAL], label_to_apply,
    )
    return run_summary


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE Security Agent")
    parser.add_argument("--issue-number", required=True, type=int, help="FORGE tracking issue number in forge-template")
    parser.add_argument("--request-id", required=True, help="FORGE request ID")
    parser.add_argument("--pr-number", default=None, type=int, help="Feature PR number in forge-demo-apps (required for a real run)")
    parser.add_argument("--repo-path", required=True, help="Local path to an existing checkout of forge-demo-apps at the feature branch")
    parser.add_argument("--existing-service", default=None, help="Item #25: resolved 'Existing Service Name' for an Enhancement request; omitted/blank means Greenfield")
    parser.add_argument("--dry-run", action="store_true", help="Run scans and compute results but don't post, check, or label")
    args = parser.parse_args()

    try:
        run_security_agent(
            issue_number=args.issue_number,
            request_id=args.request_id,
            repo_path=args.repo_path,
            pr_number=args.pr_number,
            dry_run=args.dry_run,
            existing_service=args.existing_service,
        )
    except Exception:
        logger.exception("Security Agent failed for request %s", args.request_id)
        sys.exit(1)


if __name__ == "__main__":
    main()
