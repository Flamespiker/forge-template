"""
Smoke test — claude_agent_wrapper.py

Makes a real call via claude-agent-sdk query() and verifies the result.
Run manually from the repo root:
    python -m core.agents.utils.smoke_tests.smoke_claude_agent

Requires a .env file with: ANTHROPIC_API_KEY.
Costs a small number of tokens.
"""

from __future__ import annotations

import sys
import traceback

from dotenv import load_dotenv

load_dotenv()

from core.agents.utils.claude_agent_wrapper import invoke_agent  # noqa: E402

PASS = "[PASS]"
FAIL = "[FAIL]"
results: list[tuple[str, bool]] = []


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
    print("=== Claude Agent Wrapper Smoke Test ===\n")
    print("  Uses claude-agent-sdk query() — makes a real Anthropic API call.\n")

    result = run(
        "invoke_agent(system, user, allowed_tools=[], stage_name='smoke-test')",
        lambda: invoke_agent(
            system_prompt="You are a helpful assistant. Reply concisely.",
            user_prompt="Say exactly: 'FORGE smoke test OK'",
            allowed_tools=[],  # text-only — no tools needed for this check
            stage_name="smoke-test",
            request_id="smoke-001",
        ),
    )

    if result:
        print(f"       output_text:            {result.output_text!r}")
        print(f"       latency:                {result.latency_seconds:.2f}s")
        print(f"       messages:               {len(result.all_messages)}")
        print(f"       input_tokens:           {result.input_tokens}")
        print(f"       output_tokens:          {result.output_tokens}")
        print(f"       cache_creation_tokens:  {result.cache_creation_tokens}")
        print(f"       cache_read_tokens:      {result.cache_read_tokens}")
        print(f"       total_cost_usd:         {result.total_cost_usd}")
        print(f"       num_turns:              {result.num_turns}")
        print(f"       stop_reason:            {result.stop_reason!r}")

        run(
            "output_text contains expected string",
            lambda: None if "FORGE smoke test OK" in result.output_text else (_ for _ in ()).throw(
                AssertionError(f"Expected 'FORGE smoke test OK' in: {result.output_text!r}")
            ),
        )
        run(
            "latency_seconds is positive",
            lambda: None if result.latency_seconds > 0 else (_ for _ in ()).throw(
                AssertionError("latency_seconds not recorded")
            ),
        )
        run(
            "cache_creation_tokens or cache_read_tokens is non-zero",
            lambda: None if (result.cache_creation_tokens > 0 or result.cache_read_tokens > 0) else (_ for _ in ()).throw(
                AssertionError(
                    f"Both cache fields are zero — cache_creation={result.cache_creation_tokens}, "
                    f"cache_read={result.cache_read_tokens}. SDK may not be returning usage."
                )
            ),
        )
        run(
            "total_cost_usd is not None and positive",
            lambda: None if (result.total_cost_usd is not None and result.total_cost_usd > 0) else (_ for _ in ()).throw(
                AssertionError(f"total_cost_usd not recorded: {result.total_cost_usd!r}")
            ),
        )

    print("\n=== Results ===")
    passed = sum(1 for _, ok in results if ok)
    for label, ok in results:
        print(f"  {'OK' if ok else 'XX'} {label}")
    print(f"\n{passed}/{len(results)} checks passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
