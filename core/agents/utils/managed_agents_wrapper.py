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

Key implementation notes (from Phase 2.9 hands-on verification — do not change without
re-testing against the live API):

  1. The beta header "managed-agents-2026-04-01" is required on every request.
     Without it, the API returns a 404 or behaves as the standard messages API.

  2. Event body shape — the events endpoint requires a NESTED structure:
         {"events": [{"type": "user.message", "content": [{"type": "text", "text": "..."}]}]}
     DO NOT flatten this to a top-level "content" field — the API rejects that with
     a 400 ("unknown field 'content'"). The nesting is intentional and non-obvious.

  3. Archive order — always archive in this sequence: session → agent → environment.
     Reversing the order causes 400 errors because environments cannot be destroyed
     while sessions still reference them.

  4. Archive race condition — a session can flip from "idle" back to "running" briefly
     (trailing extended-thinking wrap-up) immediately after the poller sees it idle.
     The archive_session() function wraps the session archive call in a retry loop.
     Do NOT treat a transient "cannot be archived while status is running" as fatal.

  5. Model split per ADR-0010:
     - Coordinator: Opus tier (higher reasoning for synthesis and integration)
     - Subagents: Sonnet tier (sufficient for bounded specialist tasks)
     Both are configurable via the COORDINATOR_MODEL / SUBAGENT_MODEL env vars
     (or passed as arguments) because exact model strings may shift during the beta.

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
_ANTHROPIC_VERSION = "2023-06-01"

_DEFAULT_COORDINATOR_MODEL = "claude-opus-4-6"
_DEFAULT_SUBAGENT_MODEL = "claude-sonnet-4-6"

_DEFAULT_POLL_INTERVAL = 10       # seconds between status polls
_DEFAULT_TIMEOUT = 14400          # 4 hours — generous for a full implementation run
_ARCHIVE_RETRY_ATTEMPTS = 3
_ARCHIVE_RETRY_BASE_DELAY = 2.0   # seconds; doubles on each retry (exponential backoff)


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
) -> dict[str, str]:
    """
    Create a Managed Agents coordinator session with the given subagents.

    Lifecycle created here: agent → environment → session.
    Call archive_session() when the session has run to completion.

    Args:
        coordinator_system_prompt: System prompt for the coordinator agent.
        subagent_configs: List of subagent definition dicts, each with keys:
            {
                "name": str,              # e.g. "backend_agent"
                "system_prompt": str,     # specialist agent instructions
                "scoped_tools": list,     # tool definitions available to this subagent
            }
        coordinator_model: Model ID for the coordinator. Defaults to FORGE_COORDINATOR_MODEL
            env var, or claude-opus-4-6.
        subagent_model: Model ID for all subagents. Defaults to FORGE_SUBAGENT_MODEL
            env var, or claude-sonnet-4-6.

    Returns:
        Dict with keys: "agent_id", "environment_id", "session_id".
    """
    c_model = coordinator_model or os.environ.get("FORGE_COORDINATOR_MODEL", _DEFAULT_COORDINATOR_MODEL)
    s_model = subagent_model or os.environ.get("FORGE_SUBAGENT_MODEL", _DEFAULT_SUBAGENT_MODEL)

    # 1. Create the coordinator agent
    agent_body: dict[str, Any] = {
        "model": c_model,
        "system": coordinator_system_prompt,
        "subagents": [
            {
                "name": cfg["name"],
                "model": s_model,
                "system": cfg["system_prompt"],
                "tools": cfg.get("scoped_tools", []),
            }
            for cfg in subagent_configs
        ],
    }
    agent = _post("agents", agent_body)
    agent_id: str = agent["id"]
    logger.info("Created coordinator agent: %s (model: %s)", agent_id, c_model)

    # 2. Create an execution environment
    env = _post(f"agents/{agent_id}/environments", {})
    environment_id: str = env["id"]
    logger.info("Created environment: %s", environment_id)

    # 3. Create the session
    session = _post(f"agents/{agent_id}/environments/{environment_id}/sessions", {})
    session_id: str = session["id"]
    logger.info("Created session: %s", session_id)

    return {
        "agent_id": agent_id,
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
    Poll the session status until it reaches "idle" (or raises on timeout/error).

    Args:
        session_id: The session ID to poll.
        timeout_seconds: Maximum time to wait before raising TimeoutError. Default 4 hours.
        poll_interval: Seconds between polls. Default 10.

    Returns:
        The final session status dict from the API.

    Raises:
        TimeoutError: If the session has not become idle within timeout_seconds.
        RuntimeError: If the session reaches a terminal error state.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = _get(f"sessions/{session_id}")
        state = status.get("status", "unknown")
        logger.debug("Session %s status: %s", session_id, state)

        if state == "idle":
            logger.info("Session %s reached idle", session_id)
            return status
        if state in {"failed", "cancelled", "archived"}:
            raise RuntimeError(f"Session {session_id} reached terminal state: {state}")

        time.sleep(poll_interval)

    raise TimeoutError(
        f"Session {session_id} did not reach idle within {timeout_seconds}s"
    )


def get_subagent_audit_trail(session_id: str) -> dict:
    """
    Retrieve the per-subagent transcript and events for the Claude Console audit trail.

    Per ADR-0010, the coordinator session provides a full audit trail in Claude Console
    showing what each subagent (Backend, Frontend, Test Writer) produced. This function
    surfaces the raw API response so callers can log or link to it.

    Args:
        session_id: The session ID to retrieve the audit trail for.

    Returns:
        The session events/transcript dict from the API.
    """
    audit = _get(f"sessions/{session_id}/events")
    logger.info("Retrieved audit trail for session %s (%d event(s))", session_id, len(audit.get("events", [])))
    return audit


def archive_session(agent_id: str, environment_id: str, session_id: str) -> None:
    """
    Archive a completed Managed Agents session, then its environment, then its agent.

    Archive order MUST be: session → environment → agent. Reversing causes 400 errors.

    The session archive call is wrapped in a retry-with-backoff because a session can
    transiently flip from "idle" back to "running" immediately after the poller sees it
    idle (trailing extended-thinking wrap-up). This is a known API behaviour observed
    during Phase 2.9 verification — it is retryable, not a hard failure.

    Args:
        agent_id: Agent ID from create_agent_session().
        environment_id: Environment ID from create_agent_session().
        session_id: Session ID from create_agent_session().

    Raises:
        RuntimeError: If the session archive fails after all retries.
    """
    # Archive session with retry-with-backoff
    last_error: Exception | None = None
    for attempt in range(1, _ARCHIVE_RETRY_ATTEMPTS + 1):
        try:
            _archive(f"sessions/{session_id}/archive", f"session {session_id}")
            break  # success
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 400:
                delay = _ARCHIVE_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Session archive attempt %d/%d failed (status 400 — likely transient "
                    "'running' state). Retrying in %.1fs...",
                    attempt,
                    _ARCHIVE_RETRY_ATTEMPTS,
                    delay,
                )
                last_error = exc
                time.sleep(delay)
            else:
                raise  # non-400 errors are not retryable
    else:
        raise RuntimeError(
            f"Failed to archive session {session_id} after {_ARCHIVE_RETRY_ATTEMPTS} attempts"
        ) from last_error

    # Archive environment, then agent
    _archive(f"environments/{environment_id}/archive", f"environment {environment_id}")
    _archive(f"agents/{agent_id}/archive", f"agent {agent_id}")
    logger.info(
        "Full cleanup complete: session %s, environment %s, agent %s",
        session_id,
        environment_id,
        agent_id,
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

    agent_id = ids["agent_id"]
    environment_id = ids["environment_id"]
    session_id = ids["session_id"]

    log_entry = {
        "forge_event": "managed_agents_session_start",
        "stage": "implementation",
        "agent_id": agent_id,
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
            archive_session(agent_id, environment_id, session_id)
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
