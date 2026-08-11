"""
FORGE Managed Agents wrapper — Stage 3 (Implementation) ONLY.

All other pipeline stages use claude_agent_wrapper.py (claude-agent-sdk / query()).
This module is exclusively for the Implementation Coordinator and its
Backend, Frontend, and Test Writer subagents (ADR-0010).

Why this module uses raw requests instead of claude-agent-sdk:
    The beta Managed Agents endpoints (/v1/agents, /v1/environments, /v1/sessions
    and their sub-resources) are not exposed through the claude-agent-sdk package.
    That SDK drives the Claude Code agent loop for single-agent stateless use;
    the multi-agent coordinator/subagent pattern with shared sandbox filesystems is
    a separate beta surface accessed only via direct HTTP. This module therefore uses
    the requests library for all calls and sets the beta header manually on every
    request. The anthropic pip package is not used here either — requests is sufficient.

Key implementation notes (verified against Anthropic reference docs — do not change
without re-testing against the live API):

  1. The beta header "managed-agents-2026-04-01" is required on every request.

  2. Agent creation flow — subagents cannot be declared inline. The correct sequence:
       a. POST /v1/agents for each subagent (name + model + system + tools).
          "name" is required on every agent creation call.
       b. POST /v1/agents for the coordinator, declaring the subagent roster in:
              "multiagent": {"type": "coordinator", "agents": ["<subagent_id>", ...]}
          The coordinator also needs tools: [{"type": "agent_toolset_20260401"}] so it
          can delegate. Omit multiagent entirely when there are no subagents.
       c. POST /v1/environments  (top-level resource — NOT nested under an agent)
       d. POST /v1/sessions      (top-level resource)
              body: {"agent": {"type": "agent", "id": ..., "version": ...},
                     "environment_id": ...}
     The old shape — POST /v1/agents with "subagents": [...], then nested
     /agents/{id}/environments and /agents/{id}/environments/{eid}/sessions —
     is rejected with HTTP 400 ("unknown field subagents").

  3. Event body shape — the events endpoint requires a NESTED structure:
         {"events": [{"type": "user.message", "content": [{"type": "text", "text": "..."}]}]}
     DO NOT flatten to a top-level "content" field — the API rejects that with 400.

  4. Error detection — errors surface as session.error events in the event stream, NOT as
     a distinct session status value. poll_until_idle() scans GET /v1/sessions/{sid}/events
     after reaching idle status and raises if any session.error events are found.
     "idle" status alone does NOT mean the run succeeded.

  5. stop_reason on session.status_idle events:
     - "end_turn" → completed normally, safe to archive.
     - "requires_action" → session is blocked waiting for a tool confirmation. FORGE agents
       use agent_toolset_20260401 without always_ask permission policies, so this should
       never occur in normal operation. poll_until_idle() raises if it does, rather than
       hanging indefinitely.

  6. "terminated" status means an unrecoverable orchestration-layer error — it should not
     appear during a normal poll-for-idle loop and is treated as a fatal error.
     The old states (failed, cancelled) no longer exist in the API.

  7. Archive order: session → environment → coordinator agent → each subagent agent.
     archive_session() accepts a coordinator_id and an optional subagent_ids list.

  8. Archive race condition — a session can flip from "idle" back to "running" briefly.
     archive_session() wraps the session archive call in a retry-with-backoff loop
     (6 attempts, 2s/4s/8s/16s/32s/64s, ~126s total as of Phase 5 pre-flight Fix 1 —
     widened from the original 3 attempts/~14s after the DRYRUN-2026-01 incident
     where a subagent thread was still legitimately running under an idle
     coordinator). archive_session() also polls subagent thread status first
     (_wait_for_subagent_threads_idle()) as the primary gate, treating the backoff
     loop above as a secondary safety net for the separate idle->running race.

  9. Model split per ADR-0010:
     - Coordinator: Opus tier (higher reasoning for synthesis and integration)
     - Subagents: Sonnet tier (sufficient for bounded specialist tasks)
     Both are configurable via the COORDINATOR_MODEL / SUBAGENT_MODEL env vars.

Required environment variables (see .env.example):
    ANTHROPIC_API_KEY — must have Managed Agents beta access.

Optional environment variables:
    FORGE_COORDINATOR_MODEL — override default coordinator model (default: claude-opus-4-6)
    FORGE_SUBAGENT_MODEL    — override default subagent model (default: claude-sonnet-4-6)
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_ANTHROPIC_BASE = "https://api.anthropic.com/v1"
_BETA_HEADER = "managed-agents-2026-04-01"
_FILES_API_BETA = "files-api-2025-04-14"
_ANTHROPIC_VERSION = "2023-06-01"

_DEFAULT_COORDINATOR_MODEL = "claude-opus-4-6"
_DEFAULT_SUBAGENT_MODEL = "claude-sonnet-4-6"

_DEFAULT_POLL_INTERVAL = 10       # seconds between status polls
_DEFAULT_TIMEOUT = 14400          # 4 hours — generous for a full implementation run

# Widened from 3 attempts / 2s-4s-8s (~14s total) after the DRYRUN-2026-01 Stage 3
# incident: the coordinator reported idle/end_turn while the Test Writer subagent
# thread was still legitimately executing underneath, and the old budget was
# exhausted before the session actually finished. 6 attempts on the same doubling
# schedule (2s/4s/8s/16s/32s/64s, ~126s total) gives a slow-but-healthy session
# more room, on top of the thread-status pre-check below (Phase 5 pre-flight Fix 1).
_ARCHIVE_RETRY_ATTEMPTS = 6
_ARCHIVE_RETRY_BASE_DELAY = 2.0   # seconds; doubles on each retry (exponential backoff)

# Pre-archive gate: wait for subagent threads to report idle before even
# attempting the archive call, rather than relying solely on the backoff retry
# above to paper over the gap. See _wait_for_subagent_threads_idle().
_THREAD_POLL_INTERVAL = 5.0
_THREAD_POLL_TIMEOUT = 120.0

# NOT CONFIRMED against Anthropic reference docs whether GET /sessions/{id}/threads
# exposes a per-thread status field, or what vocabulary it uses if so. Assumed to
# reuse the same {idle, running, rescheduling, terminated} enum documented for
# session-level status (CLAUDE.md), since threads are sub-resources of a session.
# If a thread has no "status" key at all, _wait_for_subagent_threads_idle() treats
# the signal as unavailable and falls back to the retry-backoff above as the only
# safety net — flagged as an open design fork in the Phase 5 pre-flight fixes spec.
_THREAD_IDLE_STATUSES = {"idle"}
_THREAD_BUSY_STATUSES = {"running", "rescheduling"}
_THREAD_FATAL_STATUSES = {"terminated"}


def _headers() -> dict[str, str]:
    """Build the required headers for every Managed Agents API call."""
    return {
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": _ANTHROPIC_VERSION,
        "anthropic-beta": _BETA_HEADER,
        "Content-Type": "application/json",
    }


def _post(path: str, body: dict) -> dict:
    url = f"{_ANTHROPIC_BASE}/{path}"
    response = requests.post(url, headers=_headers(), json=body, timeout=60)
    response.raise_for_status()
    return response.json()


def _get(path: str) -> dict:
    url = f"{_ANTHROPIC_BASE}/{path}"
    response = requests.get(url, headers=_headers(), timeout=30)
    response.raise_for_status()
    return response.json()


def _archive(path: str, resource_label: str) -> None:
    """POST to an archive endpoint with no body."""
    url = f"{_ANTHROPIC_BASE}/{path}"
    response = requests.post(url, headers=_headers(), json={}, timeout=30)
    response.raise_for_status()
    logger.info("Archived %s", resource_label)


# ── Public API ────────────────────────────────────────────────────────────────

def create_agent_session(
    coordinator_system_prompt: str,
    subagent_configs: list[dict],
    coordinator_model: str | None = None,
    subagent_model: str | None = None,
) -> dict[str, Any]:
    """
    Create a Managed Agents coordinator session with the given subagents.

    Lifecycle created here: subagent agents → coordinator agent → environment → session.
    Each subagent must be created as a separate agent resource before the coordinator
    can reference it — inline subagent declarations do not exist in the current API.

    Call archive_session() when the session has run to completion.

    Args:
        coordinator_system_prompt: System prompt for the coordinator agent.
        subagent_configs: List of subagent definition dicts, each with keys:
            {
                "name": str,              # e.g. "backend_agent" — required by the API
                "system_prompt": str,     # specialist agent instructions
                "scoped_tools": list,     # tool definitions available to this subagent
            }
        coordinator_model: Model ID for the coordinator. Defaults to FORGE_COORDINATOR_MODEL
            env var, or claude-opus-4-6.
        subagent_model: Model ID for all subagents. Defaults to FORGE_SUBAGENT_MODEL
            env var, or claude-sonnet-4-6.

    Returns:
        Dict with keys: "coordinator_id", "coordinator_version", "subagent_ids",
        "environment_id", "session_id".
    """
    c_model = coordinator_model or os.environ.get("FORGE_COORDINATOR_MODEL", _DEFAULT_COORDINATOR_MODEL)
    s_model = subagent_model or os.environ.get("FORGE_SUBAGENT_MODEL", _DEFAULT_SUBAGENT_MODEL)

    # 1. Create each subagent as a separate agent resource.
    #    These must exist before the coordinator can reference them.
    subagent_ids: list[str] = []
    for cfg in subagent_configs:
        subagent = _post("agents", {
            "name": cfg["name"],
            "model": s_model,
            "system": cfg["system_prompt"],
            "tools": cfg.get("scoped_tools", []),
        })
        subagent_ids.append(subagent["id"])
        logger.info("Created subagent '%s': %s (model: %s)", cfg["name"], subagent["id"], s_model)

    # 2. Create the coordinator agent, referencing subagent IDs in the multiagent roster.
    #    agent_toolset_20260401 enables the coordinator to delegate to the roster agents.
    #    Omit multiagent and agent_toolset entirely when there are no subagents (e.g. smoke test).
    coordinator_body: dict[str, Any] = {
        "name": "forge-coordinator",
        "model": c_model,
        "system": coordinator_system_prompt,
    }
    if subagent_ids:
        coordinator_body["tools"] = [{"type": "agent_toolset_20260401"}]
        coordinator_body["multiagent"] = {
            "type": "coordinator",
            "agents": subagent_ids,
        }
    coordinator = _post("agents", coordinator_body)
    coordinator_id: str = coordinator["id"]
    coordinator_version: int = coordinator["version"]
    logger.info("Created coordinator agent: %s v%s (model: %s)", coordinator_id, coordinator_version, c_model)

    # 3. Create an execution environment (top-level resource, not nested under the agent).
    env = _post("environments", {
        "name": "forge-implementation-env",
        "config": {"type": "anthropic_cloud"},
    })
    environment_id: str = env["id"]
    logger.info("Created environment: %s", environment_id)

    # 4. Create the session, pinning the coordinator to its exact version.
    session = _post("sessions", {
        "agent": {"type": "agent", "id": coordinator_id, "version": coordinator_version},
        "environment_id": environment_id,
    })
    session_id: str = session["id"]
    logger.info("Created session: %s", session_id)

    return {
        "coordinator_id": coordinator_id,
        "coordinator_version": coordinator_version,
        "subagent_ids": subagent_ids,
        "environment_id": environment_id,
        "session_id": session_id,
    }


def send_message(session_id: str, text: str) -> dict:
    """
    Send a user message to an active Managed Agents session.

    IMPORTANT — body shape: the events endpoint requires a NESTED structure.
    Do NOT flatten "content" to the top level — the API rejects that with a 400.
    See module docstring note 2 for full context.

    Args:
        session_id: The session ID returned by create_agent_session().
        text: The message text to send.

    Returns:
        The API response body.
    """
    # NOTE: this nested structure is required. A flat {"content": [...]} at the top
    # level is rejected with HTTP 400 ("unknown field 'content'"). Do not simplify.
    body = {
        "events": [
            {
                "type": "user.message",
                "content": [{"type": "text", "text": text}],
            }
        ]
    }
    response = _post(f"sessions/{session_id}/events", body)
    logger.info("Sent message to session %s", session_id)
    return response


def poll_until_idle(
    session_id: str,
    timeout_seconds: int = _DEFAULT_TIMEOUT,
    poll_interval: int = _DEFAULT_POLL_INTERVAL,
) -> dict:
    """
    Poll the session status until it reaches "idle", then verify no errors occurred.

    IMPORTANT — "idle" status alone does NOT mean the run succeeded. Errors surface
    as session.error events in the event stream, not as a distinct status value. This
    function scans the event stream after reaching idle and raises if any session.error
    events are present.

    Also checks the session.status_idle event's stop_reason:
    - "end_turn"        → completed normally, returns the status dict.
    - "requires_action" → session is blocked waiting for a tool confirmation. FORGE
                          agents use agent_toolset_20260401 without always_ask policies,
                          so this should never occur in normal operation. Raises rather
                          than hanging indefinitely.

    Args:
        session_id: The session ID to poll.
        timeout_seconds: Maximum time to wait before raising TimeoutError. Default 4 hours.
        poll_interval: Seconds between polls. Default 10.

    Returns:
        The final session status dict from the API.

    Raises:
        TimeoutError:   If the session has not become idle within timeout_seconds.
        RuntimeError:   If session.error events are found, stop_reason is requires_action,
                        or the session reaches "terminated" status.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = _get(f"sessions/{session_id}")
        state = status.get("status", "unknown")
        logger.debug("Session %s status: %s", session_id, state)

        if state == "idle":
            # Scan event stream for errors before declaring success.
            events_resp = _get(f"sessions/{session_id}/events?limit=100")
            events = events_resp.get("data", [])

            # Check for session.error events — these carry the real error detail.
            error_events = [e for e in events if e.get("type") == "session.error"]
            if error_events:
                error_detail = "; ".join(
                    e.get("error", {}).get("message", "unknown error")
                    for e in error_events
                )
                raise RuntimeError(
                    f"Session {session_id} reported error(s) in event stream: {error_detail}"
                )

            # Check stop_reason on the most recent session.status_idle event.
            idle_events = [e for e in events if e.get("type") == "session.status_idle"]
            if idle_events:
                stop_reason = idle_events[-1].get("stop_reason", {})
                if stop_reason.get("type") == "requires_action":
                    blocking_ids = stop_reason.get("event_ids", [])
                    raise RuntimeError(
                        f"Session {session_id} is paused waiting for tool confirmation "
                        f"(stop_reason=requires_action). This is unexpected in FORGE's "
                        f"autonomous mode — check whether agent_toolset_20260401 has an "
                        f"always_ask permission policy set. Blocking event IDs: {blocking_ids}"
                    )

            logger.info("Session %s reached idle (end_turn)", session_id)
            return status

        if state == "terminated":
            raise RuntimeError(
                f"Session {session_id} reached 'terminated' status — "
                "this indicates an unrecoverable error in the orchestration layer."
            )

        time.sleep(poll_interval)

    raise TimeoutError(
        f"Session {session_id} did not reach idle within {timeout_seconds}s"
    )


def get_subagent_audit_trail(session_id: str) -> dict:
    """
    Retrieve the per-thread audit trail for a multiagent session.

    Lists all session threads via GET /v1/sessions/{sid}/threads. The primary thread
    (parent_thread_id=null) carries the coordinator's trace. Each subagent runs in its
    own child thread; thread.agent.name identifies which subagent it belongs to.
    Per-thread events are fetched from GET /v1/sessions/{sid}/threads/{tid}/events.

    Per ADR-0010, this provides the full audit trail in Claude Console showing what each
    of the Backend, Frontend, and Test Writer subagents produced independently.

    Args:
        session_id: The session ID to retrieve the audit trail for.

    Returns:
        Dict with keys:
            "session_id"   — echoed for log correlation
            "thread_count" — total number of threads (coordinator + subagents)
            "threads"      — list of {thread_id, agent_name, parent_thread_id,
                             status, events} dicts, one per thread
    """
    threads_resp = _get(f"sessions/{session_id}/threads?limit=100")
    threads = threads_resp.get("data", [])
    logger.info("Retrieved %d thread(s) for session %s", len(threads), session_id)

    thread_details = []
    for thread in threads:
        thread_id = thread["id"]
        agent_name = thread.get("agent", {}).get("name", "unknown")
        parent_id = thread.get("parent_thread_id")
        events_resp = _get(f"sessions/{session_id}/threads/{thread_id}/events?limit=100")
        thread_details.append({
            "thread_id": thread_id,
            "agent_name": agent_name,
            "parent_thread_id": parent_id,
            "status": thread.get("status"),
            "events": events_resp.get("data", []),
        })
        logger.debug(
            "  Thread %s (%s, parent=%s): %d event(s)",
            thread_id, agent_name, parent_id, len(events_resp.get("data", [])),
        )

    return {
        "session_id": session_id,
        "thread_count": len(threads),
        "threads": thread_details,
    }


def _files_headers() -> dict[str, str]:
    """
    Build headers for Files API calls scoped to a Managed Agents session.

    The Files API is a separate beta from Managed Agents. Retrieving files scoped
    to a session (scope_id=<session_id>) requires BOTH beta headers together,
    comma-separated — confirmed against Anthropic's own Managed Agents cookbook.
    Omitting either one either 400s (missing files-api beta) or silently ignores
    the scope_id filter (missing managed-agents beta).
    """
    return {
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": _ANTHROPIC_VERSION,
        "anthropic-beta": f"{_FILES_API_BETA},{_BETA_HEADER}",
    }


def list_session_output_files(session_id: str, limit: int = 100) -> list[dict]:
    """
    List files persisted from a Managed Agents session's sandbox filesystem.

    IMPORTANT: only files written to /mnt/session/outputs/ inside the sandbox are
    persisted and appear here. Anything written elsewhere in the container (scratch
    files, intermediate build output) is invisible to this call and is discarded
    when the session's environment is archived.

    Args:
        session_id: The session ID whose output files to list.
        limit: Max files to return in one page (API default 20, max 1000).

    Returns:
        List of file metadata dicts, each with at least "id", "filename",
        "size_bytes", "mime_type".
    """
    url = f"{_ANTHROPIC_BASE}/files"
    response = requests.get(
        url,
        headers=_files_headers(),
        params={"scope_id": session_id, "limit": limit},
        timeout=30,
    )
    response.raise_for_status()
    files = response.json().get("data", [])
    logger.info("Listed %d output file(s) for session %s", len(files), session_id)
    return files


def download_file_content(file_id: str) -> bytes:
    """
    Download the raw bytes of a file produced by a Managed Agents session.

    Args:
        file_id: The file ID from list_session_output_files().

    Returns:
        Raw file content as bytes — binary-safe. FORGE uses this to download the
        gzip-compressed implementation archive, not text.
    """
    url = f"{_ANTHROPIC_BASE}/files/{file_id}/content"
    response = requests.get(url, headers=_files_headers(), timeout=60)
    response.raise_for_status()
    logger.info("Downloaded file %s (%d bytes)", file_id, len(response.content))
    return response.content


def _get_thread_statuses(session_id: str) -> list[dict]:
    """
    Lightweight per-thread status listing: GET /v1/sessions/{sid}/threads only,
    with no per-thread event fetch. get_subagent_audit_trail() is too expensive
    to call in a tight pre-archive polling loop — it fetches every event for
    every thread on every call.
    """
    threads_resp = _get(f"sessions/{session_id}/threads?limit=100")
    threads = threads_resp.get("data", [])
    return [
        {
            "thread_id": t["id"],
            "agent_name": t.get("agent", {}).get("name", "unknown"),
            "status": t.get("status"),
        }
        for t in threads
    ]


def _wait_for_subagent_threads_idle(
    session_id: str,
    timeout_seconds: float = _THREAD_POLL_TIMEOUT,
    poll_interval: float = _THREAD_POLL_INTERVAL,
) -> None:
    """
    Pre-archive gate (Phase 5 pre-flight Fix 1): wait for every subagent thread
    to report an idle-like status before attempting to archive the session.

    Fix for the DRYRUN-2026-01 Stage 3 incident — coordinator-level idle does
    not imply subagent-level idle; a subagent can legitimately keep working
    after the coordinator's own turn ends. Polls short-interval / generous-total
    rather than trusting only the coordinator's idle signal.

    If the threads endpoint doesn't expose a usable status field, this checks
    once, logs a warning, and returns immediately — degrading to the
    exponential-backoff retry in archive_session() as the sole safety net.
    Never blocks forever: if threads stay busy past timeout_seconds, logs a
    warning and returns anyway (bounded wait), leaving the archive-call retry
    loop as the backstop for a genuinely stuck session.
    """
    deadline = time.monotonic() + timeout_seconds
    checked_status_field = False

    while time.monotonic() < deadline:
        threads = _get_thread_statuses(session_id)
        if not threads:
            return  # nothing to gate on

        statuses = {t["agent_name"]: t["status"] for t in threads}

        if not checked_status_field:
            checked_status_field = True
            if all(s is None for s in statuses.values()):
                logger.warning(
                    "Thread status field not present on GET /sessions/%s/threads "
                    "response (statuses: %s) -- cannot gate archive on real "
                    "subagent state. Falling back to the archive-call "
                    "retry-with-backoff as the only safety net. Raw threads: %s",
                    session_id, statuses, threads,
                )
                return

        fatal = {name: s for name, s in statuses.items() if s in _THREAD_FATAL_STATUSES}
        if fatal:
            logger.warning(
                "Thread(s) reached 'terminated' status before archive: %s -- "
                "not waiting on these, they will never become idle.",
                fatal,
            )

        busy = {name: s for name, s in statuses.items() if s in _THREAD_BUSY_STATUSES}
        if not busy:
            logger.info(
                "All subagent thread(s) report idle before archive attempt "
                "for session %s: %s", session_id, statuses,
            )
            return

        remaining = deadline - time.monotonic()
        logger.info(
            "Archive pre-check for session %s: %d thread(s) still busy, "
            "waiting up to %.0fs more: %s",
            session_id, len(busy), max(remaining, 0), busy,
        )
        time.sleep(poll_interval)

    logger.warning(
        "Subagent thread(s) for session %s did not report idle within %.0fs "
        "pre-archive poll window -- proceeding to the archive call anyway; "
        "the retry-with-backoff loop is the remaining safety net.",
        session_id, timeout_seconds,
    )


def archive_session(
    coordinator_id: str,
    environment_id: str,
    session_id: str,
    subagent_ids: list[str] | None = None,
) -> None:
    """
    Archive a completed session and all associated agent resources.

    Archive order: session → environment → coordinator agent → each subagent agent.

    Before the session archive call, waits for subagent threads to report idle
    (_wait_for_subagent_threads_idle() — Phase 5 pre-flight Fix 1) so a slow-but-
    healthy session isn't killed by an arbitrarily short timer. The session
    archive call itself is then still wrapped in retry-with-backoff, because a
    session can transiently flip from "idle" back to "running" briefly even
    after threads report idle (the known race condition, unrelated to Fix 1).
    This is retryable, not a hard failure.

    Args:
        coordinator_id:  Coordinator agent ID from create_agent_session().
        environment_id:  Environment ID from create_agent_session().
        session_id:      Session ID from create_agent_session().
        subagent_ids:    List of subagent agent IDs from create_agent_session()["subagent_ids"].
                         Each is archived after the coordinator. Pass None or [] if there
                         are no subagents (e.g. smoke test with subagent_configs=[]).

    Raises:
        RuntimeError: If the session archive fails after all retries.
    """
    # 0. Wait for subagent threads to catch up to the coordinator's own idle
    #    status before attempting to archive at all (Phase 5 pre-flight Fix 1).
    _wait_for_subagent_threads_idle(session_id)

    # 1. Archive session with retry-with-backoff (secondary safety net — the
    #    session can still transiently flip idle -> running even after step 0).
    last_error: Exception | None = None
    for attempt in range(1, _ARCHIVE_RETRY_ATTEMPTS + 1):
        try:
            _archive(f"sessions/{session_id}/archive", f"session {session_id}")
            break
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 400:
                delay = _ARCHIVE_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                try:
                    observed_statuses = _get_thread_statuses(session_id)
                except Exception as status_err:
                    observed_statuses = f"<unavailable: {status_err}>"
                logger.warning(
                    "Session archive attempt %d/%d failed (status 400 — likely transient "
                    "'running' state). Thread statuses at this attempt: %s. Retrying in "
                    "%.1fs...",
                    attempt, _ARCHIVE_RETRY_ATTEMPTS, observed_statuses, delay,
                )
                last_error = exc
                time.sleep(delay)
            else:
                raise
    else:
        raise RuntimeError(
            f"Failed to archive session {session_id} after {_ARCHIVE_RETRY_ATTEMPTS} attempts"
        ) from last_error

    # 2. Archive environment.
    _archive(f"environments/{environment_id}/archive", f"environment {environment_id}")

    # 3. Archive coordinator agent.
    _archive(f"agents/{coordinator_id}/archive", f"coordinator agent {coordinator_id}")

    # 4. Archive each subagent agent.
    for sid in (subagent_ids or []):
        _archive(f"agents/{sid}/archive", f"subagent agent {sid}")

    logger.info(
        "Full cleanup complete: session %s, environment %s, coordinator %s, %d subagent(s)",
        session_id, environment_id, coordinator_id, len(subagent_ids or []),
    )


def run_implementation_stage(
    coordinator_system_prompt: str,
    subagent_configs: list[dict],
    initial_message: str,
    coordinator_model: str | None = None,
    subagent_model: str | None = None,
    timeout_seconds: int = _DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    Convenience wrapper: create a session, send the initial message, wait for completion,
    retrieve the audit trail, and clean up — returning a summary dict.

    This is the entry point called by the Stage 3 GitHub Actions workflow via
    implementation_coordinator.py.

    Args:
        coordinator_system_prompt: System prompt for the coordinator agent.
        subagent_configs: Subagent definition list (see create_agent_session()).
        initial_message: The user message that kicks off the implementation run
            (typically contains design.md, openapi.yaml, and tasks.md content).
        coordinator_model: Optional coordinator model override.
        subagent_model: Optional subagent model override.
        timeout_seconds: Maximum wait time for the session to complete.

    Returns:
        Dict with keys:
            "session_id"    — for logging/linking to Claude Console
            "audit_trail"   — raw per-subagent events from the API
            "final_status"  — the session status dict at completion
    """
    ids = create_agent_session(
        coordinator_system_prompt=coordinator_system_prompt,
        subagent_configs=subagent_configs,
        coordinator_model=coordinator_model,
        subagent_model=subagent_model,
    )

    coordinator_id = ids["coordinator_id"]
    subagent_ids = ids["subagent_ids"]
    environment_id = ids["environment_id"]
    session_id = ids["session_id"]

    log_entry = {
        "forge_event": "managed_agents_session_start",
        "stage": "implementation",
        "coordinator_id": coordinator_id,
        "subagent_ids": subagent_ids,
        "environment_id": environment_id,
        "session_id": session_id,
    }
    print(json.dumps(log_entry), flush=True)

    try:
        send_message(session_id, initial_message)
        final_status = poll_until_idle(session_id, timeout_seconds=timeout_seconds)
        audit_trail = get_subagent_audit_trail(session_id)
    finally:
        # Always attempt cleanup, even if something above raised
        try:
            archive_session(coordinator_id, environment_id, session_id, subagent_ids)
        except Exception as cleanup_err:
            logger.error("Cleanup failed for session %s: %s", session_id, cleanup_err)

    log_entry_done = {
        "forge_event": "managed_agents_session_complete",
        "stage": "implementation",
        "session_id": session_id,
        "final_state": final_status.get("status"),
    }
    print(json.dumps(log_entry_done), flush=True)

    return {
        "session_id": session_id,
        "audit_trail": audit_trail,
        "final_status": final_status,
    }
