"""
Smoke test — managed_agents_wrapper.py

Verifies the full Managed Agents lifecycle against the real API:
    agent create → environment create → session create →
    send message → poll to idle → retrieve audit trail → archive

Run manually from the repo root:
    python -m core.agents.utils.smoke_tests.smoke_managed_agents

Requires a .env file with: ANTHROPIC_API_KEY (must have Managed Agents beta access).

This test uses a single coordinator with zero subagents — just enough to confirm
the full lifecycle works. It mirrors the Phase 2.9 verification but is structured
as a reusable smoke test rather than a throwaway script.

Cost: small token usage (~200 tokens) + ~$0.08/session-hour active runtime.
The session completes in seconds for this minimal test, so actual cost is negligible.
"""

from __future__ import annotations

import sys
import traceback

from dotenv import load_dotenv

load_dotenv()

import core.agents.utils.managed_agents_wrapper as maw  # noqa: E402

PASS = "[PASS]"
FAIL = "[FAIL]"
results: list[tuple[str, bool]] = []

# IDs are tracked here so cleanup runs even if a mid-test step fails
_agent_id: str | None = None
_environment_id: str | None = None
_session_id: str | None = None


def run(label: str, fn):
    try:
        result = fn()
        print(f"{PASS} {label}")
        results.append((label, True))
        return result
    except Exception as exc:
        print(f"{FAIL} {label}: {exc}")
        traceback.print_exc()
        results.append((label, False))
        return None


def main():
    global _agent_id, _environment_id, _session_id

    print("=== Managed Agents Wrapper Smoke Test ===\n")
    print("  Note: uses the real Managed Agents API (managed-agents-2026-04-01 beta header).\n")

    # 1. Create session (zero subagents — connectivity test only)
    ids = run(
        "create_agent_session(coordinator_prompt, subagents=[])",
        lambda: maw.create_agent_session(
            coordinator_system_prompt="You are a test agent. Reply concisely.",
            subagent_configs=[],
            coordinator_model="claude-sonnet-4-6",  # use Sonnet for this smoke test to save cost
        ),
    )

    if ids:
        _agent_id = ids["agent_id"]
        _environment_id = ids["environment_id"]
        _session_id = ids["session_id"]
        print(f"       agent_id:       {_agent_id}")
        print(f"       environment_id: {_environment_id}")
        print(f"       session_id:     {_session_id}")
    else:
        print("\nCannot proceed — session creation failed.")
        sys.exit(1)

    # 2. Send message
    run(
        "send_message(session_id, 'Say: FORGE smoke test OK')",
        lambda: maw.send_message(_session_id, "Say exactly: 'FORGE smoke test OK'"),
    )

    # 3. Poll to idle
    status = run(
        "poll_until_idle(session_id, timeout=120)",
        lambda: maw.poll_until_idle(_session_id, timeout_seconds=120, poll_interval=5),
    )
    if status:
        print(f"       Final status: {status.get('status')}")

    # 4. Audit trail
    audit = run(
        "get_subagent_audit_trail(session_id)",
        lambda: maw.get_subagent_audit_trail(_session_id),
    )
    if audit:
        print(f"       Audit events: {len(audit.get('events', []))}")

    # 5. Archive (with retry — exercises the retry path)
    run(
        "archive_session(agent_id, environment_id, session_id)",
        lambda: maw.archive_session(_agent_id, _environment_id, _session_id),
    )

    print("\n=== Results ===")
    passed = sum(1 for _, ok in results if ok)
    for label, ok in results:
        print(f"  {'OK' if ok else 'XX'} {label}")
    print(f"\n{passed}/{len(results)} checks passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
