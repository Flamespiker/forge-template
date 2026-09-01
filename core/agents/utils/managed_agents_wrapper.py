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

  8. Completion detection vs. archive retry — these are two DIFFERENT problems,
     deliberately handled by two different mechanisms (post-REQ-2026-02 fix;
     superseded the Phase 5 pre-flight Fix 1 design below):
       - "Is the coordinator + every subagent actually done?" is answered by
         wait_for_all_threads_idle() polling GET /sessions/{id}/threads on a
         real, data-informed ceiling (see _COMPLETION_POLL_TIMEOUT) until every
         thread reports idle. This is the ONLY real waiting mechanism for
         completion. If the ceiling is exceeded, it raises
         SessionStillRunningError rather than proceeding — the session is left
         alive (not archived), because a 400 from the archive call in that state
         isn't new information, it's an expected consequence of asking too
         early. Confirmed on REQ-2026-02 (2026-08-11): the coordinator's own
         session-level status went idle in <1s of sending the initial message,
         but real completion (all subagent threads idle, implementation.tar.gz
         produced) took ~37 minutes. REQ-2026-01 took 38.5 min (dry run) / 55.2
         min (real) per docs/FORGE-pipeline-cost-log.md — all consistent with
         each other, none of which the old ~246s total budget (120s pre-check +
         6-attempt/~126s archive backoff) ever had a chance of covering.
       - "The archive API call itself intermittently 400s even on an
         already-idle session" (the separate idle->running flip race documented
         in the Phase 2.9 build notes) is a genuinely transient API hiccup, not
         a completion-detection problem. archive_session() retries this with a
         SMALL backoff (_ARCHIVE_RETRY_ATTEMPTS, now 3 — reduced from 6, since
         it no longer needs to double as the real wait mechanism) only after
         wait_for_all_threads_idle() has already confirmed every thread idle.

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

# Small and purely for absorbing the known idle->running archive-call race
# (Phase 2.9 build notes) on a session already CONFIRMED idle by
# wait_for_all_threads_idle() below. This is no longer doing the real waiting —
# that used to be true (6 attempts/~126s, widened from 3/~14s after the
# DRYRUN-2026-01 incident) and was the root cause of the REQ-2026-02 incident:
# retrying an archive call that keeps 400ing while a thread is genuinely still
# running isn't new information every time, it's the same premature request
# repeated. Reduced back down now that real completion detection lives
# elsewhere.
_ARCHIVE_RETRY_ATTEMPTS = 3
_ARCHIVE_RETRY_BASE_DELAY = 2.0   # seconds; doubles on each retry (2s/4s/8s, ~14s total)

# The real completion-wait ceiling for wait_for_all_threads_idle() — the ONE
# mechanism that decides whether the whole multi-agent stage is actually done.
# Chosen with headroom over real observed durations (docs/FORGE-pipeline-cost-log.md):
# REQ-2026-01 38.5 min (dry run) / 55.2 min (real); REQ-2026-02 ~37 min (real).
# 90 minutes gives ~1.6x headroom over the largest observed run so far.
# Overridable via env for when more data comes in without a code change.
_COMPLETION_POLL_INTERVAL = 15.0
_COMPLETION_POLL_TIMEOUT = float(
    os.environ.get("FORGE_IMPLEMENTATION_COMPLETION_TIMEOUT", 90 * 60)
)

# CONFIRMED live (Phase 5 pre-flight Fix 1's smoke test, and again directly via
# a manual read-only poll during the REQ-2026-02 incident): GET
# /sessions/{id}/threads DOES expose a real per-thread "status" field using the
# same {idle, running, rescheduling, terminated} vocabulary as session-level
# status. The "field might not exist" branch in wait_for_all_threads_idle()
# below is retained as a defensive fallback only — it is not expected to
# trigger on the current API.
_THREAD_IDLE_STATUSES = {"idle"}
_THREAD_BUSY_STATUSES = {"running", "rescheduling"}
_THREAD_FATAL_STATUSES = {"terminated"}


class SessionStillRunningError(RuntimeError):
    """
    Raised by wait_for_all_threads_idle() when a session's subagent threads have
    not all reported idle within the completion-wait ceiling.

    This is NOT a failure — see the module docstring note 8. The session is left
    alive (not archived) so it can be resumed by session ID later (via the
    recovery tool) instead of being force-archived mid-work or silently
    re-run as a duplicate, separately-billed session.

    Carries session_id and the last-observed per-thread status dict so a caller
    can report exactly what's still running without a second API round-trip.
    run_implementation_stage() additionally attaches coordinator_id,
    environment_id, and subagent_ids before re-raising, since
    wait_for_all_threads_idle() itself only knows the session_id.
    """

    def __init__(self, session_id: str, thread_statuses: dict[str, str]):
        self.session_id = session_id
        self.thread_statuses = thread_statuses
        self.coordinator_id: str | None = None
        self.environment_id: str | None = None
        self.subagent_ids: list[str] | None = None
        super().__init__(
            f"Session {session_id} has not reached full completion (all threads "
            f"idle) within the {_COMPLETION_POLL_TIMEOUT:.0f}s wait ceiling. "
            f"Current thread statuses: {thread_statuses}. The session was left "
            "alive, not archived — resume by session ID (recovery tool) rather "
            "than re-invoking the coordinator."
        )


class SessionBudgetExhaustedError(RuntimeError):
    """
    Raised when a thread's stop_reason is "budget_reached" — the thread is idle,
    but only because it ran out of its token/turn budget mid-work, not because it
    finished. This is a genuine failure, NOT a "still running, check back later"
    case: a budget-exhausted thread is never coming back on its own, so it must
    NOT be raised/handled as SessionStillRunningError (which means the opposite —
    "leave it alone, it'll finish"). Deliberately a plain RuntimeError subclass,
    not a SessionStillRunningError subclass, so run_implementation_stage()'s
    generic `except Exception` cleanup (best-effort archive) handles it, the same
    as any other genuine failure — see the module docstring note 8.
    """

    def __init__(self, session_id: str, detail: str):
        self.session_id = session_id
        self.detail = detail
        super().__init__(
            f"Session {session_id} has a thread that stopped with "
            f"stop_reason=budget_reached — it is idle because it ran out of "
            f"budget mid-work, not because it finished. Not recoverable by "
            f"waiting longer. Detail: {detail}"
        )


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
    resources: list[dict] | None = None,
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
        resources: Optional list of session resource dicts (e.g.
            {"type": "file", "file_id": ..., "mount_path": ...}), resolved
            before the coordinator's first turn (Item #23). Files mount
            READ-ONLY — see EXISTING_SERVICE_MOUNT_DIR in
            core/agents/subagents/__init__.py for how FORGE handles that.
            Omit or pass None/[] for a session with no pre-seeded files (the
            existing behavior for every non-Enhancement run).

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
    session_body: dict[str, Any] = {
        "agent": {"type": "agent", "id": coordinator_id, "version": coordinator_version},
        "environment_id": environment_id,
    }
    if resources:
        session_body["resources"] = resources
    session = _post("sessions", session_body)
    session_id: str = session["id"]
    logger.info(
        "Created session: %s (%d pre-seeded resource(s))", session_id, len(resources or [])
    )

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
    - "budget_reached"  → the coordinator's own session ran out of its token/turn
                          budget mid-work. Idle here does NOT mean done — raises
                          SessionBudgetExhaustedError rather than reporting success.
                          This only covers the coordinator's own session-level idle
                          event; a per-thread (subagent) budget exhaustion is a
                          separate case handled by wait_for_all_threads_idle().

    Args:
        session_id: The session ID to poll.
        timeout_seconds: Maximum time to wait before raising TimeoutError. Default 4 hours.
        poll_interval: Seconds between polls. Default 10.

    Returns:
        The final session status dict from the API.

    Raises:
        TimeoutError:                 If the session has not become idle within timeout_seconds.
        RuntimeError:                 If session.error events are found, stop_reason is
                                      requires_action, or the session reaches "terminated" status.
        SessionBudgetExhaustedError:  If stop_reason is budget_reached.
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
                if stop_reason.get("type") == "budget_reached":
                    # The coordinator's own session-level budget exhaustion — a
                    # distinct, simpler case from a per-thread subagent budget
                    # exhaustion (see wait_for_all_threads_idle(), which covers
                    # that case via the event stream since /threads has no
                    # stop_reason field of its own).
                    raise SessionBudgetExhaustedError(
                        session_id, "coordinator session's own status_idle event"
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


def upload_input_file(content: str, filename: str) -> str:
    """
    Upload a text file via the Files API, for use as a session `resources[]`
    entry (Item #23 -- the mirror-image, input-side counterpart to
    download_file_content()'s output-side download).

    Uses the same combined Files-API + Managed-Agents beta headers as
    _files_headers() -- the uploaded file needs to be referenceable as a
    session resource, not just a bare Files API object.

    Args:
        content: UTF-8 text content to upload.
        filename: Filename to attach to the Files API object (metadata only --
            does not need to be unique; the caller controls the real sandbox
            path via the session resource's own "mount_path").

    Returns:
        The uploaded file's "id", for use as a resources[] entry's "file_id".
    """
    url = f"{_ANTHROPIC_BASE}/files"
    response = requests.post(
        url,
        headers=_files_headers(),
        files={"file": (filename, content.encode("utf-8"), "text/plain")},
        timeout=60,
    )
    response.raise_for_status()
    file_id: str = response.json()["id"]
    logger.debug("Uploaded input file '%s' as %s (%d bytes)", filename, file_id, len(content))
    return file_id


def get_session_resource_ids(session_id: str) -> dict[str, Any]:
    """
    Derive coordinator_id, environment_id, and subagent_ids directly from
    GET /sessions/{id} -- confirmed live (2026-08-11) to carry
    agent.id (coordinator), agent.multiagent.agents[].id (subagents), and
    environment_id. Lets a recovery tool work from a session_id alone rather
    than requiring someone to dig the managed_agents_session_start log line
    out of a (possibly long-gone) GitHub Actions run.

    Also returns the raw "status" (session-level, NOT a reliable completion
    signal for a multi-agent coordinator — see wait_for_all_threads_idle())
    and "usage" (token/cost data — confirmed live to be present here, closing
    an open question in docs/FORGE-pipeline-cost-log.md about whether this
    endpoint exposes cost without a Console visit).
    """
    session = _get(f"sessions/{session_id}")
    agent = session.get("agent", {})
    subagent_ids = [a["id"] for a in agent.get("multiagent", {}).get("agents", [])]
    return {
        "coordinator_id": agent.get("id"),
        "environment_id": session.get("environment_id"),
        "subagent_ids": subagent_ids,
        "status": session.get("status"),
        "usage": session.get("usage"),
    }


def get_thread_statuses(session_id: str) -> list[dict]:
    """
    Lightweight per-thread status listing: GET /v1/sessions/{sid}/threads only,
    with no per-thread event fetch. get_subagent_audit_trail() is too expensive
    to call in a tight completion-polling loop — it fetches every event for
    every thread on every call. Public (not prefixed) because the recovery
    tool needs a direct, on-demand status check independent of the polling
    loop below.
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


def _raise_if_any_thread_budget_exhausted(session_id: str) -> None:
    """
    One-shot check (NOT part of the polling loop — see call site) for a
    stop_reason=budget_reached "session.thread_status_idle" event on any
    thread. The /threads status endpoint has no stop_reason field of its own;
    this is the only place that distinction is exposed, per the module
    docstring note 8/get_subagent_audit_trail()'s existing event-fetch.
    """
    audit_trail = get_subagent_audit_trail(session_id)
    for thread in audit_trail["threads"]:
        idle_events = [
            e for e in thread["events"] if e.get("type") == "session.thread_status_idle"
        ]
        if not idle_events:
            continue
        stop_reason = idle_events[-1].get("stop_reason", {})
        if stop_reason.get("type") == "budget_reached":
            raise SessionBudgetExhaustedError(
                session_id,
                f"thread {thread['thread_id']} (agent={thread['agent_name']})",
            )


def wait_for_all_threads_idle(
    session_id: str,
    timeout_seconds: float = _COMPLETION_POLL_TIMEOUT,
    poll_interval: float = _COMPLETION_POLL_INTERVAL,
) -> None:
    """
    The one real completion signal for a multi-agent Stage 3 session: block
    until every thread (coordinator + all subagents) reports idle.

    Fix for the DRYRUN-2026-01 / REQ-2026-02 Stage 3 incidents — coordinator-
    level session status can go idle in under a second (just the coordinator's
    first turn ending after kicking off delegation), long before the actual
    multi-agent work is done. Real completion has been observed at 37-55
    minutes for a real two-service build (docs/FORGE-pipeline-cost-log.md) —
    this polls on a real ceiling informed by that data, not a guess.

    Raises SessionStillRunningError (not a failure — see its docstring) if the
    ceiling is reached with threads still busy. Callers must NOT proceed to
    archive the session in that case.

    Once every thread reports idle (the normal /threads status field), makes
    ONE additional get_subagent_audit_trail() call to check each thread's event
    stream for a stop_reason=budget_reached — the /threads endpoint's bare
    "status" field cannot distinguish a thread that finished from one that went
    idle only because it ran out of budget mid-work; that distinction only
    exists in the per-thread event stream. This is deliberately done ONCE, only
    at the point of declaring success — not on every poll iteration, which is
    exactly the expensive-per-thread-event-fetch cost this function's polling
    loop is designed to avoid (see get_thread_statuses()'s docstring). Raises
    SessionBudgetExhaustedError if found, instead of returning success.

    If the threads endpoint doesn't expose a usable status field at all, this
    checks once, logs a warning, and returns immediately — there is nothing to
    gate on. Not expected to trigger on the current API (see the
    _THREAD_IDLE_STATUSES comment above), retained as a defensive fallback.

    Raises:
        SessionStillRunningError:    Threads still busy at the wait ceiling — NOT
                                     a failure, see that exception's docstring.
        SessionBudgetExhaustedError: A thread's stop_reason was budget_reached —
                                     it is idle but did not genuinely finish.
    """
    deadline = time.monotonic() + timeout_seconds
    checked_status_field = False
    last_logged_statuses: dict[str, str] | None = None

    while time.monotonic() < deadline:
        threads = get_thread_statuses(session_id)
        if not threads:
            return  # nothing to gate on

        statuses = {t["agent_name"]: t["status"] for t in threads}

        if not checked_status_field:
            checked_status_field = True
            if all(s is None for s in statuses.values()):
                logger.warning(
                    "Thread status field not present on GET /sessions/%s/threads "
                    "response (statuses: %s) -- cannot gate completion on real "
                    "subagent state. Treating as unknown/idle rather than "
                    "blocking forever. Raw threads: %s",
                    session_id, statuses, threads,
                )
                return

        fatal = {name: s for name, s in statuses.items() if s in _THREAD_FATAL_STATUSES}
        if fatal:
            logger.warning(
                "Thread(s) reached 'terminated' status: %s -- not waiting on "
                "these, they will never become idle.",
                fatal,
            )

        busy = {name: s for name, s in statuses.items() if s in _THREAD_BUSY_STATUSES}
        if not busy:
            logger.info(
                "All thread(s) report idle for session %s: %s", session_id, statuses,
            )
            _raise_if_any_thread_budget_exhausted(session_id)
            return

        if statuses != last_logged_statuses:
            remaining = deadline - time.monotonic()
            logger.info(
                "Completion poll for session %s: %d thread(s) still busy, "
                "waiting up to %.0fs more: %s",
                session_id, len(busy), max(remaining, 0), busy,
            )
            last_logged_statuses = statuses
        time.sleep(poll_interval)

    final_threads = get_thread_statuses(session_id)
    final_statuses = {t["agent_name"]: t["status"] for t in final_threads}
    raise SessionStillRunningError(session_id, final_statuses)


def archive_session(
    coordinator_id: str,
    environment_id: str,
    session_id: str,
    subagent_ids: list[str] | None = None,
) -> None:
    """
    Archive a completed session and all associated agent resources.

    Archive order: session → environment → coordinator agent → each subagent agent.

    Before attempting the archive call, confirms real completion via
    wait_for_all_threads_idle() — this is a hard precondition, not a nicety:
    if it raises SessionStillRunningError, this function does NOT catch it and
    does NOT attempt to archive anything. Only once every thread is confirmed
    idle does the small archive-retry loop run, purely to absorb the separate,
    genuinely transient idle->running API race documented in the Phase 2.9
    build notes (module docstring note 8).

    Args:
        coordinator_id:  Coordinator agent ID from create_agent_session().
        environment_id:  Environment ID from create_agent_session().
        session_id:      Session ID from create_agent_session().
        subagent_ids:    List of subagent agent IDs from create_agent_session()["subagent_ids"].
                         Each is archived after the coordinator. Pass None or [] if there
                         are no subagents (e.g. smoke test with subagent_configs=[]).

    Raises:
        SessionStillRunningError: If threads are not all idle within the
            completion-wait ceiling — the session is left alive, untouched.
        RuntimeError: If the session archive call itself fails after all retries
            despite every thread being confirmed idle.
    """
    # 0. Confirm real completion. Not caught here — a still-running session
    #    must never reach the archive call below.
    wait_for_all_threads_idle(session_id)

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
                    observed_statuses = get_thread_statuses(session_id)
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
    expected_output_filename: str | None = None,
    resources: list[dict] | None = None,
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
        resources: Optional session resources (Item #23) — see
            create_agent_session()'s own "resources" arg. Passed straight
            through; this function does no seeding logic of its own.
        expected_output_filename: If given, the session must have written a file
            of exactly this name to /mnt/session/outputs/ before this function
            will archive it — mirrors recover_implementation_session()'s existing
            pre-archive output check (see Item #6 Bug 6b: previously this
            function archived unconditionally, and the caller's own "did we get
            real output" check ran only AFTER archiving had already destroyed the
            session's evidence trail). Default None skips the check entirely,
            preserving today's behavior for any other caller that doesn't
            produce a single named output archive.

    Returns:
        Dict with keys:
            "session_id"      — for logging/linking to Claude Console
            "coordinator_id", "environment_id", "subagent_ids" — echoed from
                                 create_agent_session(), useful to a caller that
                                 needs to report or recover this session later
            "audit_trail"     — raw per-subagent events from the API
            "final_status"    — the session status dict at completion
            "output_files"    — list_session_output_files() result, fetched once
                                 here (needed for the expected_output_filename
                                 check when given) and handed back so a caller
                                 that needs to locate a specific file (e.g. to
                                 download it) doesn't have to pay for the same
                                 API call a second time.

    Raises:
        SessionStillRunningError: The coordinator's own turn ended normally but
            not every subagent thread reached idle within the completion-wait
            ceiling (see wait_for_all_threads_idle()). NOT a failure — the
            session is left alive, not archived. Re-raised with
            coordinator_id/environment_id/subagent_ids attached (the exception
            as raised by wait_for_all_threads_idle() only knows session_id).
            Callers must treat this distinctly from a real failure.
        RuntimeError: expected_output_filename was given but the session, though
            genuinely idle, produced no file of that name. Raised BEFORE
            archiving — the session is left alive so the evidence trail (the
            actual sandbox state) isn't destroyed. This is a plain RuntimeError,
            not a new exception subclass, and is raised from outside the
            try/except above — it never touches the best-effort-archive cleanup
            path that a genuine mid-run failure goes through, by construction
            (it can only be reached once wait_for_all_threads_idle() has already
            returned successfully).
    """
    ids = create_agent_session(
        coordinator_system_prompt=coordinator_system_prompt,
        subagent_configs=subagent_configs,
        coordinator_model=coordinator_model,
        subagent_model=subagent_model,
        resources=resources,
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
        # poll_until_idle() only confirms the coordinator's OWN turn ended
        # without a session-level error — for a multi-agent coordinator this
        # can return in under a second, long before delegated subagent work is
        # actually done (see wait_for_all_threads_idle()'s docstring).
        poll_until_idle(session_id, timeout_seconds=timeout_seconds)
        # This is the real completion signal for the whole stage.
        wait_for_all_threads_idle(session_id)
    except SessionStillRunningError as exc:
        exc.coordinator_id = coordinator_id
        exc.environment_id = environment_id
        exc.subagent_ids = subagent_ids
        raise
    except Exception:
        # A genuine failure (session.error, terminated, requires_action, etc).
        # Best-effort archive so we don't leak billed resources indefinitely,
        # but don't let a cleanup failure mask the original error.
        try:
            archive_session(coordinator_id, environment_id, session_id, subagent_ids)
        except SessionStillRunningError:
            logger.warning(
                "Session %s still has active threads after a failure elsewhere "
                "in the run -- leaving it alive rather than force-archiving.",
                session_id,
            )
        except Exception as cleanup_err:
            logger.error("Cleanup failed for session %s: %s", session_id, cleanup_err)
        raise

    # Fetch the audit trail before archiving -- an archived session's threads
    # may not remain queryable (unconfirmed either way; safer to fetch first,
    # matching the original working order).
    audit_trail = get_subagent_audit_trail(session_id)
    final_status = _get(f"sessions/{session_id}")

    # Item #34 §2.4: closes the cost-log automation gap flagged in
    # docs/FORGE-pipeline-cost-log.md §4.2 ("no automatic equivalent yet...
    # queued but not yet built") -- same grep-a-JSON-line pattern as every
    # Messages-API stage's "agent_invocation" line (claude_agent_wrapper.py),
    # so future cost-log updates no longer require a manual Claude Console
    # visit to find this session's usage data. Does not itself update the
    # cost log file -- that stays a separate, periodic bookkeeping pass.
    log_entry_cost = {
        "forge_event": "managed_agents_cost",
        "stage": "implementation",
        "session_id": session_id,
        "usage": final_status.get("usage"),
    }
    print(json.dumps(log_entry_cost), flush=True)

    output_files = list_session_output_files(session_id)

    # Item #6 Bug 6b: validate real output BEFORE archiving, not after -- an
    # archived session's evidence trail is gone. Deliberately outside the
    # try/except above (can only be reached once wait_for_all_threads_idle()
    # has already returned successfully), so this plain RuntimeError bypasses
    # that block's best-effort-archive cleanup entirely rather than needing a
    # new exception type/except clause to opt out of it -- see recover_
    # implementation_session()'s identical check for the equivalent recovery-
    # path pattern.
    if expected_output_filename is not None:
        found = any(f.get("filename") == expected_output_filename for f in output_files)
        if not found:
            raise RuntimeError(
                f"Session {session_id} is idle but produced no "
                f"'{expected_output_filename}' in /mnt/session/outputs/. Files "
                f"present: {[f.get('filename') for f in output_files]}. This "
                "session genuinely failed -- leaving it alive (not archived) so "
                "it remains inspectable."
            )

    archive_session(coordinator_id, environment_id, session_id, subagent_ids)

    log_entry_done = {
        "forge_event": "managed_agents_session_complete",
        "stage": "implementation",
        "session_id": session_id,
        "final_state": final_status.get("status"),
    }
    print(json.dumps(log_entry_done), flush=True)

    return {
        "session_id": session_id,
        "coordinator_id": coordinator_id,
        "environment_id": environment_id,
        "subagent_ids": subagent_ids,
        "audit_trail": audit_trail,
        "final_status": final_status,
        "output_files": output_files,
    }
