"""
FORGE Claude Agent SDK wrapper — stateless-per-stage invocation for all pipeline stages
except Stage 3 (Implementation), which uses managed_agents_wrapper.py instead.

Why claude-agent-sdk (not the base anthropic client):
    The claude-agent-sdk package drives the full Claude Code agent loop — multi-turn,
    tool use, extended thinking — via a single async query() call. This matches FORGE's
    stateless-per-stage model: each invocation receives its inputs, runs the agent loop
    to completion, produces output artifacts, and exits. No persistent session is kept.

    The base anthropic client (pip install anthropic) only provides the raw Messages API.
    Using query() instead means FORGE agents can use tools (Read, Write, Bash, etc.)
    natively within the loop rather than requiring manual tool-call/result plumbing.

Why managed_agents_wrapper.py uses raw requests instead:
    The beta Managed Agents endpoints (agents, environments, sessions) are not exposed
    through claude-agent-sdk. That module uses raw HTTP calls with the beta header.
    See managed_agents_wrapper.py for full rationale.

Tool scoping — IMPORTANT:
    By default, claude-agent-sdk gives Claude the full Claude Code toolset (Read, Write,
    Edit, Bash, etc.). FORGE agents must NOT receive unrestricted tool access. Each call
    to invoke_agent() must pass an allowed_tools list scoped to what that specific stage
    legitimately needs. Examples:
        Intake Agent:       ["Read"]
        Requirements Agent: ["Read"]
        Design Agent:       ["Read", "Write"]
        QA Agent:           ["Read", "Bash"]
        Security Agent:     ["Read", "Bash"]
        Deploy Agent:       ["Read", "Bash"]
    Callers are responsible for this list — invoke_agent() enforces nothing by default.

Usage data:
    ResultMessage (the final message yielded by query()) carries:
        total_cost_usd  — direct USD cost for this invocation
        usage           — dict with input_tokens, output_tokens, and cache keys
        num_turns       — number of agent loop turns
    These are surfaced in AgentResult and emitted in the structured log line so that
    per-stage cost data can be captured during App 1 / App 2 runs and used to fill in
    Document 3's cost summary table.

Required environment variables (see .env.example):
    ANTHROPIC_API_KEY — read automatically by claude-agent-sdk from the environment.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class AgentResult:
    """
    Structured result returned by invoke_agent().

    Attributes:
        output_text:    The final text produced by the agent (ResultMessage.result).
                        This is the stage artifact content — e.g. the body of
                        requirements.md, design.md, etc.
        all_messages:   Every message yielded during the agent loop, in order.
                        Useful for debugging tool-use sequences or multi-turn reasoning.

        COST TRACKING NOTE — use total_cost_usd as ground truth, not token counts:
        The SDK wraps the Claude Code CLI subprocess. On every invocation the CLI sends
        its full system prompt + all built-in tool definitions to the API (~25k tokens),
        regardless of the allowed_tools list. allowed_tools becomes --allowedTools on the
        CLI — a runtime execution permission filter, not an API token filter. The full
        tool payload is prompt-cached after the first call:
          - First call:  cache_creation_tokens ~25k → expensive (~$0.096 at Sonnet rates)
          - Later calls: cache_read_tokens ~25k → cheap (~$0.008 at Sonnet rates)
        input_tokens reflects only the user message (typically 3–50 tokens). It does NOT
        include cache_read_tokens or cache_creation_tokens, so it is useless as a cost
        proxy. total_cost_usd is the SDK-computed ground truth and is the only field
        Document 3's per-stage cost tables should key off.

        The CLI also makes an internal Haiku call (~500 tokens, ~$0.0005) for background
        processing; this is included in total_cost_usd automatically.

        input_tokens:            User message tokens only (NOT the full billed count).
        output_tokens:           Output tokens from the main model call.
        cache_creation_tokens:   Tokens written to prompt cache this call (expensive).
                                 High on first call; zero on subsequent calls.
        cache_read_tokens:       Tokens read from prompt cache this call (cheap).
                                 ~25k on every call after the first.
        total_cost_usd:          SDK-computed total cost — USE THIS for Document 3.
                                 None if the SDK did not report a figure.
        num_turns:      Number of agent loop turns (from ResultMessage.num_turns).
        is_error:       True if the SDK reported a terminal error.
        stop_reason:    Why the loop stopped (from ResultMessage.terminal_reason / stop_reason).
        latency_seconds: Wall-clock time from query start to completion.
        stage_name:     Pipeline stage name, echoed from the invoke_agent() call.
        request_id:     FORGE request ID, echoed for log correlation.
    """

    output_text: str
    all_messages: list[Any] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    total_cost_usd: float | None = None
    num_turns: int = 0
    is_error: bool = False
    stop_reason: str | None = None
    latency_seconds: float = 0.0
    stage_name: str = "unknown"
    request_id: str = "unknown"


async def _run_query(
    system_prompt: str,
    user_prompt: str,
    allowed_tools: list[str],
    model: str,
    stage_name: str,
    request_id: str,
) -> AgentResult:
    """Internal async implementation; called via asyncio.run() from invoke_agent()."""
    options = ClaudeAgentOptions(
        allowed_tools=allowed_tools,
        model=model,
        system_prompt=system_prompt,
    )

    start = time.monotonic()
    messages: list[Any] = []
    result_msg: ResultMessage | None = None

    async for message in query(prompt=user_prompt, options=options):
        messages.append(message)
        if isinstance(message, ResultMessage):
            result_msg = message

    elapsed = time.monotonic() - start

    # Extract output text and usage from ResultMessage.
    # ResultMessage.result is the final agent output text — cleaner than parsing
    # AssistantMessage content blocks because it's already synthesised by the SDK.
    output_text = ""
    input_tokens = 0
    output_tokens = 0
    cache_creation_tokens = 0
    cache_read_tokens = 0
    total_cost_usd: float | None = None
    num_turns = 0
    is_error = False
    stop_reason: str | None = None

    if result_msg is not None:
        output_text = result_msg.result or ""
        num_turns = result_msg.num_turns
        is_error = result_msg.is_error
        total_cost_usd = result_msg.total_cost_usd
        stop_reason = result_msg.terminal_reason or result_msg.stop_reason

        usage = result_msg.usage or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        # Cache tokens are the dominant cost driver — see AgentResult docstring.
        # cache_read_tokens is ~25k on every call after the first (cheap per token).
        # cache_creation_tokens is ~25k on the first call only (expensive per token).
        cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)
        cache_read_tokens = usage.get("cache_read_input_tokens", 0)

    # Structured log line — one JSON object per invocation, greppable in Actions logs.
    # grep '"forge_event": "agent_invocation"' to find all FORGE agent runs in a job log.
    # Use total_cost_usd for Document 3 cost tracking — NOT input_tokens (see docstring).
    log_entry: dict[str, Any] = {
        "forge_event": "agent_invocation",
        "stage": stage_name,
        "request_id": request_id,
        "model": model,
        "allowed_tools": allowed_tools,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "cache_read_tokens": cache_read_tokens,
        "total_cost_usd": total_cost_usd,
        "num_turns": num_turns,
        "stop_reason": stop_reason,
        "is_error": is_error,
        "latency_seconds": round(elapsed, 3),
    }
    print(json.dumps(log_entry), flush=True)
    logger.info(
        "Stage '%s' [%s]: %d in / %d out / %d cache_read / %d cache_create tokens, "
        "cost=$%s, %d turn(s), %.2fs",
        stage_name,
        request_id,
        input_tokens,
        output_tokens,
        cache_read_tokens,
        cache_creation_tokens,
        f"{total_cost_usd:.6f}" if total_cost_usd is not None else "N/A",
        num_turns,
        elapsed,
    )

    if is_error:
        errors = getattr(result_msg, "errors", None) or []
        logger.error("Stage '%s' [%s] agent loop reported error: %s", stage_name, request_id, errors)

    return AgentResult(
        output_text=output_text,
        all_messages=messages,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
        total_cost_usd=total_cost_usd,
        num_turns=num_turns,
        is_error=is_error,
        stop_reason=stop_reason,
        latency_seconds=elapsed,
        stage_name=stage_name,
        request_id=request_id,
    )


def invoke_agent(
    system_prompt: str,
    user_prompt: str,
    allowed_tools: list[str] | None = None,
    model: str = _DEFAULT_MODEL,
    stage_name: str = "unknown",
    request_id: str = "unknown",
) -> AgentResult:
    """
    Invoke a Claude agent via the claude-agent-sdk query() call.

    This is the standard entry point for all FORGE pipeline stages except Stage 3.
    Each call is fully stateless — the agent loop runs to completion and exits.
    Context for the next stage is carried forward as committed files in the monorepo,
    not as retained agent memory (ADR-0002).

    Args:
        system_prompt:  The agent's system prompt — persona, role, output format
                        instructions. This defines what kind of agent this invocation is.
        user_prompt:    The user-turn input for this stage — assembled by the calling
                        agent script from the stage's input artifacts (spreadsheet content,
                        markdown files, previous stage outputs, etc.).
        allowed_tools:  List of Claude Code tool names this agent is permitted to use.
                        MUST be scoped to the minimum needed for the stage. Passing None
                        or [] produces a text-only agent with no tool access (suitable for
                        stages where the Python script handles all file I/O itself).
                        See module docstring for per-stage recommendations.
        model:          Claude model ID. Defaults to Sonnet tier (claude-sonnet-4-6).
        stage_name:     Pipeline stage name for structured log output (e.g. "requirements").
        request_id:     FORGE request ID for log correlation (e.g. "req-0042").

    Returns:
        AgentResult with:
            output_text     — the agent's final artifact text (ResultMessage.result)
            input_tokens    — input token count (for Document 3 cost tracking)
            output_tokens   — output token count
            total_cost_usd  — USD cost for this invocation (may be None)
            num_turns       — number of agent loop turns
            is_error        — True if the SDK reported a terminal error
            all_messages    — full loop transcript for debugging

    Raises:
        Exception: Propagates any exception raised by claude-agent-sdk (API errors,
            auth failures, tool permission errors, etc.).
    """
    return asyncio.run(
        _run_query(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            allowed_tools=allowed_tools or [],
            model=model,
            stage_name=stage_name,
            request_id=request_id,
        )
    )
