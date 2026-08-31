"""
FORGE — Post-Deploy Crash-Loop Flag (Item #1, Option 3).

Spec: docs/Specs/FORGE-Item1-PostDeployCrashLoopFlag-Spec.md

Runs AFTER a successful Deploy Agent (Stage 6) run, from a separate
workflow (`.github/workflows/07-post-deploy-health.yml`) — never inline in
Deploy Agent's own synchronous path (spec §1.1). Polls each deployed unit's
Container App revision at increasing checkpoints for a crash-loop-shaped
unhealthy state and, if found, posts a single non-blocking flag comment to
the FORGE tracking issue. Never fails the pipeline, never blocks a gate,
never applies or removes a label — Document 6's Label Reference table gains
nothing from this stage, by design.

Deliberately NOT doing (spec §1.3/§1.4, both explicit v1 exclusions):
  - No log-content/exception-string pattern matching as a trigger condition.
    Health state alone (`healthState`/`provisioningState` on the latest
    revision) is the only detection signal. A best-effort raw log tail is
    included in the comment for a human to read, never used to decide
    whether to post.
  - No true "newly broken by this deploy" vs. "pre-existing" comparison.
    Dedup is by-existing-flag only (a `forge:crash-loop-flag:<unit_name>`
    marker already present on the tracking issue skips a re-post) — cruder
    than real revision-history comparison, but enough to stop a
    chronically-broken unit from generating a fresh comment on every future
    deploy, which is the concrete problem this pass exists to solve.

Reuses deploy_agent.py's existing _detect_units()/_finalize_unit_name()/
_az_login()/_load_staging_config() directly (imported, not re-derived) --
same naming_id/service_dir resolution Item #28 already built and
live-verified, so this script always agrees with Deploy Agent about which
Container App names it just created/updated.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass

from dotenv import load_dotenv

from core.agents.deploy_agent import (
    _REPO_ROOT,
    _az_login,
    _detect_units,
    _finalize_unit_name,
    _load_staging_config,
    _require_env,
    _run_shell,
)
from core.agents.utils.enhancement_target import resolve_service_root
from core.agents.utils.github_helper import get_issue_comments, post_comment

load_dotenv()

logger = logging.getLogger(__name__)

# Cumulative seconds from job start (spec §1.2) -- checked at increasing
# intervals rather than one fixed sleep, since the only timing data
# available (Claude Code CLI's 2026-08-30 investigation) is a long-run
# steady-state average, not a first-crash measurement. Catches this
# project's actual known failure mode (a startup-time exception) within the
# first checkpoint or two, while still giving a slower-to-manifest failure
# a few minutes to show up. ~4-5 minute ceiling total, then exit clean.
_CHECKPOINTS_SECONDS = [30, 60, 120, 240]

_MARKER_PREFIX = "forge:crash-loop-flag"


@dataclass
class HealthCheckResult:
    unit_name: str
    project_label: str
    unhealthy: bool
    health_state: str | None = None
    provisioning_state: str | None = None
    provisioning_error: str | None = None


def _get_latest_revision_health(name: str, resource_group: str) -> dict | None:
    """
    Returns the latest revision's health fields, or None if the call itself
    failed (Container App not found, transient CLI error, etc.) -- treated
    as "not observed as unhealthy this checkpoint", not as a crash-loop
    signal. Confirmed live (2026-08-30 investigation) that the crash-loop
    signal lives on the REVISION, not the top-level containerapp object --
    `provisioningState`/`runningStatus` on the containerapp itself stay
    healthy-looking even while the active revision is Unhealthy/Failed.
    """
    result = _run_shell(
        ["az", "containerapp", "revision", "list", "--name", name, "--resource-group", resource_group, "-o", "json"],
        cwd=str(_REPO_ROOT), timeout=120,
    )
    if result.returncode != 0:
        logger.warning("az containerapp revision list failed for %s -- treating as not-yet-observed this checkpoint:\n%s", name, (result.stderr or "")[-1000:])
        return None
    try:
        revisions = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        logger.warning("Could not parse revision list JSON for %s -- treating as not-yet-observed this checkpoint.", name)
        return None
    if not revisions:
        return None

    # Single active-revisions mode (this project's only mode) means at most
    # one revision should carry active=true; fall back to the first entry
    # if none is marked active rather than assuming the list is empty.
    active = next((r for r in revisions if r.get("properties", {}).get("active")), revisions[0])
    props = active.get("properties", {})
    return {
        "healthState": props.get("healthState"),
        "provisioningState": props.get("provisioningState"),
        "provisioningError": props.get("provisioningError"),
    }


def _fetch_log_tail(name: str, resource_group: str, tail: int = 50) -> str | None:
    """
    Best-effort only (spec §1.4/§2.2) -- a failure here must never fail the
    check itself. `az containerapp logs show --type console` returns
    newline-delimited JSON objects (one per log line), not a single JSON
    array despite `-o json` (confirmed live 2026-08-30) -- parsed line by
    line, skipping anything that doesn't parse.
    """
    try:
        result = _run_shell(
            ["az", "containerapp", "logs", "show", "--name", name, "--resource-group", resource_group,
             "--type", "console", "--tail", str(tail), "-o", "json"],
            cwd=str(_REPO_ROOT), timeout=60,
        )
        if result.returncode != 0:
            logger.warning("Best-effort log fetch failed for %s (non-fatal):\n%s", name, (result.stderr or "")[-500:])
            return None
        lines = []
        for raw_line in (result.stdout or "").splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                entry = json.loads(raw_line)
                lines.append(entry.get("Log", raw_line))
            except json.JSONDecodeError:
                lines.append(raw_line)
        if not lines:
            return None
        joined = "\n".join(lines)
        return joined[-3000:]  # keep the comment body a sane size
    except Exception:
        logger.exception("Best-effort log fetch raised for %s (non-fatal) -- omitting log tail from the flag comment.", name)
        return None


def _already_flagged(issue_number: int, unit_name: str) -> bool:
    marker = f"{_MARKER_PREFIX}:{unit_name}"
    for comment in get_issue_comments(issue_number):
        if marker in (comment.get("body") or ""):
            return True
    return False


def _build_flag_comment(result: HealthCheckResult, resource_group: str, log_tail: str | None) -> str:
    marker = f"<!-- {_MARKER_PREFIX}:{result.unit_name} -->"
    log_section = (
        f"<details>\n<summary>Recent console log tail (best-effort, may be empty/unavailable)</summary>\n\n```\n{log_tail}\n```\n\n</details>\n"
        if log_tail else
        "_Recent console log tail was not available (best-effort fetch failed or returned nothing)._\n"
    )
    return (
        f"{marker}\n"
        "⚠️ **FORGE Post-Deploy Health Check — possible crash-loop detected**\n\n"
        f"**Unit:** {result.project_label} (`{result.unit_name}`)\n"
        f"**Container App:** `{result.unit_name}` (resource group `{resource_group}`)\n"
        f"**Detected state:** `healthState={result.health_state}`, "
        f"`provisioningState={result.provisioning_state}`\n"
        f"**Provisioning error:** `{result.provisioning_error}`\n\n"
        f"{log_section}\n"
        "---\n"
        "This is a **non-blocking flag — it did not fail the pipeline, block any merge, "
        "or affect any label/gate.** An Orchestration Manager should investigate whether "
        "this is a real problem introduced by this deploy (e.g. a missing/invalid secret "
        "or config value) or a pre-existing condition unrelated to it. This flag will not "
        "be re-posted for this unit on future deploys once it's present on this issue."
    )


def run_post_deploy_health_check(
    issue_number: int,
    request_id: str,
    repo_path: str,
    existing_service: str | None = None,
    unit_name_filter: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Core entry point. Returns a dict summarizing what was checked/flagged."""
    azure_credentials = json.loads(_require_env("AZURE_STAGING_CREDENTIALS"))
    staging_cfg = _load_staging_config()
    resource_group = staging_cfg["resource_group"]

    # Same resolution Deploy Agent itself uses (Item #28) -- resolved_service_dir
    # is where the code lives (services/<existing_service>/ for an Enhancement),
    # naming_id is what unit names are built from (existing_service for an
    # Enhancement, so this agrees with the live Container App names Deploy
    # Agent actually created/updated, not a new never-deployed request_id set).
    resolved_service_dir = resolve_service_root(request_id, existing_service)
    naming_id = existing_service or request_id

    units = _detect_units(repo_path, resolved_service_dir, naming_id)
    if not units:
        raise ValueError(
            f"No deployable units detected under {resolved_service_dir}/ in {repo_path} -- "
            "nothing to health-check. Check --repo-path/--request-id/--existing-service."
        )

    finalized = []
    for unit in units:
        try:
            unit.name = _finalize_unit_name(naming_id.lower(), unit.slug)
        except ValueError:
            logger.exception("Could not compute a valid Container App name for unit %s -- skipping health check for it.", unit.project_label)
            continue
        finalized.append(unit)

    if unit_name_filter:
        finalized = [u for u in finalized if u.name == unit_name_filter]
        if not finalized:
            raise ValueError(
                f"--unit-name '{unit_name_filter}' did not match any unit detected under "
                f"{resolved_service_dir}/ (naming_id={naming_id}). Detected names: "
                f"{[u.name for u in units]}"
            )

    logger.info(
        "Post-deploy health check: %d unit(s) to watch for %s (naming_id=%s): %s",
        len(finalized), request_id, naming_id, ", ".join(u.name for u in finalized),
    )

    _az_login(azure_credentials)

    pending = list(finalized)
    flagged: list[HealthCheckResult] = []
    elapsed = 0
    for checkpoint in _CHECKPOINTS_SECONDS:
        if not pending:
            break
        time.sleep(max(0, checkpoint - elapsed))
        elapsed = checkpoint
        logger.info("Checkpoint t=%ds -- checking %d unit(s): %s", elapsed, len(pending), ", ".join(u.name for u in pending))
        still_pending = []
        for unit in pending:
            health = _get_latest_revision_health(unit.name, resource_group)
            if health and health.get("healthState") == "Unhealthy" and health.get("provisioningState") == "Failed":
                logger.info("Unit %s: unhealthy state detected at t=%ds -- %s", unit.name, elapsed, health)
                flagged.append(HealthCheckResult(
                    unit_name=unit.name, project_label=unit.project_label, unhealthy=True,
                    health_state=health.get("healthState"),
                    provisioning_state=health.get("provisioningState"),
                    provisioning_error=health.get("provisioningError"),
                ))
            else:
                still_pending.append(unit)
        pending = still_pending

    summary = {"request_id": request_id, "naming_id": naming_id, "checked": [u.name for u in finalized], "flagged": [], "skipped_already_flagged": []}

    for result in flagged:
        if _already_flagged(issue_number, result.unit_name):
            logger.info("Unit %s already has an open crash-loop flag on issue #%s -- skipping (dedup, spec §1.3).", result.unit_name, issue_number)
            summary["skipped_already_flagged"].append(result.unit_name)
            continue
        log_tail = _fetch_log_tail(result.unit_name, resource_group)
        comment_body = _build_flag_comment(result, resource_group, log_tail)
        if dry_run:
            print("=" * 20, f"would post to issue #{issue_number}", "=" * 20)
            print(comment_body)
        else:
            post_comment(issue_number, comment_body)
            logger.info("Posted crash-loop flag comment for %s to issue #%s.", result.unit_name, issue_number)
        summary["flagged"].append(result.unit_name)

    if not flagged:
        logger.info("Post-deploy health check complete for %s -- no unhealthy state observed by the final checkpoint. Nothing posted.", request_id)

    return summary


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="FORGE Post-Deploy Health Check (Item #1, Option 3)")
    parser.add_argument("--issue-number", type=int, required=True, help="FORGE tracking issue number in forge-template")
    parser.add_argument("--request-id", required=True, help="FORGE request ID")
    parser.add_argument("--repo-path", required=True, help="Local checkout of forge-demo-apps to detect units from")
    parser.add_argument("--existing-service", default=None, help="Item #28-style: resolved 'Existing Service Name' for an Enhancement request; omitted/blank means Greenfield")
    parser.add_argument("--unit-name", default=None, help="Optional: check only this one already-finalized Container App name instead of every detected unit (manual testing)")
    parser.add_argument("--dry-run", action="store_true", help="Poll for real, but print (don't post) any flag comment")
    args = parser.parse_args()

    try:
        run_post_deploy_health_check(
            issue_number=args.issue_number,
            request_id=args.request_id,
            repo_path=args.repo_path,
            existing_service=args.existing_service,
            unit_name_filter=args.unit_name,
            dry_run=args.dry_run,
        )
    except Exception:
        # Deliberately no failure comment posted to the tracking issue here
        # (unlike every ADR-0011 stage agent) -- this stage is designed to be
        # silent unless it has a real crash-loop flag to raise, and a setup/
        # config failure in this script (bad --unit-name, zero units
        # detected, Azure auth failure) is not itself evidence of a problem
        # with the deployed app. The Actions run failing loudly is the
        # correct signal for an operator to notice, without a public
        # tracking-issue comment blurring this stage's own
        # "non-blocking, quiet unless something's genuinely wrong" framing.
        logger.exception("Post-deploy health check failed to complete.")
        sys.exit(1)


if __name__ == "__main__":
    main()
