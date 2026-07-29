"""
Smoke test — managed_agents_wrapper.py

Verifies the full Managed Agents MULTI-AGENT lifecycle against the real API:
    subagent create → coordinator create (with multiagent roster) →
    environment create → session create → send message → poll to idle →
    retrieve audit trail (2 threads) → verify specialist thread events → archive both agents

Run manually from the repo root:
    python -m core.agents.utils.smoke_tests.smoke_managed_agents

Requires a .env file with: ANTHROPIC_API_KEY (must have Managed Agents beta access).

Uses one coordinator + one throwaway "specialist" subagent — the minimum to exercise
the real multi-agent path (multiagent field, agent_toolset_20260401, 2-thread audit trail,
archive of both agent resources).

Cost: small token usage + ~$0.08/session-hour active runtime. Negligible for this test.
"""

from __future__ import annotations

import json
import sys
import traceback

from dotenv import load_dotenv

load_dotenv()

import core.agents.utils.managed_agents_wrapper as maw  # noqa: E402

PASS = "[PASS]"
FAIL = "[FAIL]"
results: list[tuple[str, bool]] = []

# IDs are tracked here so cleanup runs even if a mid-test step fails
_coordinator_id: str | None = None
_subagent_ids: list[str] = []
_environment_id: str | None = None
_session_id: str | None = None

# One throwaway specialist subagent — trivial system prompt, no tools.
_SUBAGENT_CONFIGS = [
    {
        "name": "smoke-specialist",
        "system_prompt": "You are a specialist agent. When asked anything, reply with only the word DONE.",
        "scoped_tools": [],
    }
]


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
    global _coordinator_id, _subagent_ids, _environment_id, _session_id

    print("=== Managed Agents Wrapper Smoke Test (multi-agent path) ===\n")
    print("  Note: uses the real Managed Agents API (managed-agents-2026-04-01 beta header).")
    print("  Subagent: smoke-specialist (system_prompt: reply DONE, no tools)")
    print("  Coordinator: forge-coordinator with multiagent roster + agent_toolset_20260401\n")

    # 1. Create session — 1 subagent so coordinator is created with the multiagent field.
    ids = run(
        "create_agent_session(coordinator_prompt, subagents=[smoke-specialist])",
        lambda: maw.create_agent_session(
            coordinator_system_prompt=(
                "You are a test coordinator. You have one specialist subagent named "
                "'smoke-specialist'. When you receive a task, delegate it to the specialist "
                "and report back its reply."
            ),
            subagent_configs=_SUBAGENT_CONFIGS,
            coordinator_model="claude-sonnet-4-6",  # Sonnet for both to save cost
            subagent_model="claude-sonnet-4-6",
        ),
    )

    if ids:
        _coordinator_id = ids["coordinator_id"]
        _subagent_ids = ids["subagent_ids"]
        _environment_id = ids["environment_id"]
        _session_id = ids["session_id"]
        print(f"       coordinator_id:  {_coordinator_id}  (v{ids['coordinator_version']})")
        print(f"       subagent_ids:    {_subagent_ids}")
        print(f"       environment_id:  {_environment_id}")
        print(f"       session_id:      {_session_id}")
    else:
        print("\nCannot proceed — session creation failed.")
        sys.exit(1)

    # 2. Send message — instruct coordinator to delegate to the specialist
    run(
        "send_message(session_id, delegate-to-specialist task)",
        lambda: maw.send_message(
            _session_id,
            "Please delegate the following task to your specialist subagent: 'What is your reply?' "
            "Then tell me exactly what the specialist said.",
        ),
    )

    # 3. Poll to idle — error scan runs inside poll_until_idle after idle is confirmed
    status = run(
        "poll_until_idle(session_id, timeout=180) + session.error scan",
        lambda: maw.poll_until_idle(_session_id, timeout_seconds=180, poll_interval=5),
    )
    if status:
        print(f"       Final status: {status.get('status')}")

    # 4. Audit trail — must show 2 threads: coordinator (parent_thread_id=null) + specialist
    audit = run(
        "get_subagent_audit_trail(session_id) returns 2 threads",
        lambda: maw.get_subagent_audit_trail(_session_id),
    )
    if audit:
        thread_count = audit.get("thread_count", 0)
        print(f"       thread_count: {thread_count}")
        coordinator_thread = None
        specialist_thread = None
        for t in audit.get("threads", []):
            role = "coordinator" if t["parent_thread_id"] is None else "subagent"
            print(f"         [{role}] agent_name={t['agent_name']}  thread_id={t['thread_id']}")
            print(f"                  parent_thread_id={t['parent_thread_id']}  status={t['status']}  events={len(t['events'])}")
            if t["parent_thread_id"] is None:
                coordinator_thread = t
            else:
                specialist_thread = t

        # Print a few events from the specialist thread so they are visible in output
        if specialist_thread:
            print(f"\n       Specialist thread events ({len(specialist_thread['events'])} total):")
            for ev in specialist_thread["events"][:5]:
                print(f"         {json.dumps(ev, indent=None)[:200]}")

        # Inline assertions — these fail the step if the multi-agent assertions don't hold
        def assert_two_threads():
            if thread_count != 2:
                raise AssertionError(
                    f"Expected 2 threads (coordinator + specialist), got {thread_count}"
                )
            if coordinator_thread is None:
                raise AssertionError("No coordinator thread found (parent_thread_id=null)")
            if specialist_thread is None:
                raise AssertionError("No specialist thread found (parent_thread_id set)")
            if specialist_thread["agent_name"] != "smoke-specialist":
                raise AssertionError(
                    f"Expected specialist agent_name='smoke-specialist', "
                    f"got '{specialist_thread['agent_name']}'"
                )
            if not specialist_thread["events"]:
                raise AssertionError("Specialist thread has no events — delegation did not occur")

        run(
            "assert: 2 threads, coordinator parent_thread_id=null, specialist has events",
            assert_two_threads,
        )

    # 5. Archive — must archive BOTH coordinator and specialist agent resources
    run(
        "archive_session(coordinator_id, environment_id, session_id, subagent_ids=[specialist])",
        lambda: maw.archive_session(_coordinator_id, _environment_id, _session_id, _subagent_ids),
    )

    print("\n=== Results ===")
    passed = sum(1 for _, ok in results if ok)
    for label, ok in results:
        print(f"  {'OK' if ok else 'XX'} {label}")
    print(f"\n{passed}/{len(results)} checks passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
