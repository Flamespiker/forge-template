"""
FORGE Anthropic Messages API wrapper — stateless-per-stage invocation for all pipeline stages
except Stage 3 (Implementation), which uses managed_agents_wrapper.py instead.

Why the base anthropic client (not claude-agent-sdk):
    ADR-0011 documents the switch from the Claude Agent SDK to the base anthropic Python
    client for the six non-Stage-3 pipeline stages. The Agent SDK bundled the Claude Code
    CLI as a subprocess, which imposed a fixed overhead of ~25,700 tokens (written to
    prompt cache on the first call, ~$0.10 at Sonnet rates) and a ~10-second subprocess-
    launch latency floor on every invocation — even trivial, tool-free text exchanges.

    None of the six stages (Intake, Requirements, Design, QA, Security, Deploy) use the
    Agent SDK's autonomous tool-execution capability: FORGE's deterministic Python layer
    handles all file I/O, and the claude_agent_sdk calls were already passing
    allowed_tools=[] in every stage. Switching to the Messages API eliminates that overhead
    with no loss of capability for these stages.

    Stage 3 (Implementation) remains on Anthropic Managed Agents (ADR-0010) and is not
    affected by this change.

Tool use:
    This wrapper makes a single-turn Messages API call. There is no tool-use loop.
    The caller provides system and user prompts; Claude generates text and returns.
    If a future stage needs autonomous tool calling, use the Messages API's own `tools`
    parameter (scoped, per-call function definitions) or adopt the Agent SDK explicitly
    with a documented rationale (see ADR-0011).

Structured output (Item #31, added to fix free-text JSON parsing fragility):
    Pass `output_schema` to force a single-turn tool call whose `input` is guaranteed to
    match the given JSON Schema -- no `json.loads()`/fence-stripping at the call site.
    See `invoke_agent()`'s docstring and `AgentResult.structured_output`.

    IMPORTANT (per Anthropic's own "Incomplete tool use blocks" guidance): when
    `stop_reason == "max_tokens"`, a forced tool_use block may still be present in
    `response.content` but with truncated/invalid `.input` -- this wrapper never reads
    `.input` in that case. `structured_output` is left `None` and the existing per-stage
    `if result.stop_reason == "max_tokens": raise ValueError(...)` guard (already present
    in every stage that uses this parameter) fires at the call site before
    `structured_output` is ever touched. This wrapper does not duplicate that check.

Cost tracking:
    total_cost_usd is computed from the Messages API response's usage object and a
    per-model rate table maintained in this module (_MODEL_RATES). The rate table must be
    updated when Anthropic publishes new pricing. See the table below for the current
    rates and source citation.

Required environment variables (see .env.example):
    ANTHROPIC_API_KEY — read automatically by the anthropic package from the environment.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-6"

# Fixed tool name used to force structured output via tool_choice (Item #31).
# Not user-facing -- Claude never sees this as a "real" tool to choose among others,
# since tool_choice always forces it directly.
_STRUCTURED_OUTPUT_TOOL_NAME = "submit_structured_output"

# ---------------------------------------------------------------------------
# Per-model token rate table — USD per million tokens.
# Source: https://platform.claude.com/docs/en/about-claude/pricing
# Retrieved: 2026-07-29  ← update this date whenever rates are refreshed
#
# cache_write rate is the 5-minute TTL write (1.25x base input).
# If 1-hour TTL caching is in use (cache_control ttl: 3600), the actual
# cache-write cost is 2x base input — this table will undercount in that case.
# cache_read rate is 0.10x base input (same for both TTL durations).
# ---------------------------------------------------------------------------
_MODEL_RATES: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-opus-4-6": {
        "input": 5.00,
        "output": 25.00,
        "cache_write": 6.25,
        "cache_read": 0.50,
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.00,
        "output": 5.00,
        "cache_write": 1.25,
        "cache_read": 0.10,
    },
    # Alias — same rates as the dated snapshot above
    "claude-haiku-4-5": {
        "input": 1.00,
        "output": 5.00,
        "cache_write": 1.25,
        "cache_read": 0.10,
    },
}


def _compute_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
) -> float | None:
    """
    Compute USD cost from token counts using _MODEL_RATES.
    Returns None if the model is not in the table (caller should log a warning).
    """
    rates = _MODEL_RATES.get(model)
    if rates is None:
        return None
    return (
        input_tokens * rates["input"]
        + output_tokens * rates["output"]
        + cache_write_tokens * rates["cache_write"]
        + cache_read_tokens * rates["cache_read"]
    ) / 1_000_000


@dataclass
class AgentResult:
    """
    Structured result returned by invoke_agent().

    Attributes:
        output_text:    The final text produced by the model. Assembled from all text
                        content blocks in the Messages API response. Still populated
                        when `output_schema` was passed (the SDK exposes both text and
                        tool_use blocks on the same response) -- useful for logging.
        structured_output: The forced tool_use block's parsed `.input`, as a plain dict.
                        Only populated when `invoke_agent()` was called with
                        `output_schema` AND `stop_reason != "max_tokens"`. `None`
                        otherwise -- including on a `max_tokens` truncation, where this
                        wrapper deliberately never reads a possibly-truncated `.input`
                        (see the module docstring's "Structured output" section).
        all_messages:   List containing the raw Messages API response object.
                        Useful for inspecting content blocks, stop reason, and usage.

        COST TRACKING — use total_cost_usd, computed from the rate table:
        The Messages API returns raw token counts; it does not compute a USD figure.
        This wrapper computes total_cost_usd using _MODEL_RATES, a per-model rate table
        maintained in this module. If the model is not in the table, total_cost_usd is
        None and a warning is logged. Document 3 cost tables must key off total_cost_usd.

        input_tokens:            Base (uncached) input tokens.
        output_tokens:           Output tokens.
        cache_creation_tokens:   Tokens written to prompt cache this call.
                                 Zero for plain Messages API calls without cache_control.
        cache_read_tokens:       Tokens read from prompt cache this call.
                                 Zero for plain Messages API calls without cache_control.
        total_cost_usd:          Computed from _MODEL_RATES — USE THIS for Document 3.
                                 None if the model is not in the rate table.
        num_turns:      Always 1 — single Messages API call, no agent loop.
        is_error:       Always False — errors propagate as exceptions from invoke_agent().
        stop_reason:    From Messages API response.stop_reason (e.g. "end_turn",
                        "max_tokens").
        latency_seconds: Wall-clock time for the API call.
        stage_name:     Pipeline stage name, echoed from the invoke_agent() call.
        request_id:     FORGE request ID, echoed for log correlation.
    """

    output_text: str
    structured_output: dict[str, Any] | None = None
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


def _persist_raw_response_for_diagnosis(response: Any, stage_name: str, request_id: str) -> str:
    """
    Defensive diagnostics for a failed structured_output extraction (Item #31). Writes
    the full raw API response to a JSON file in the current working directory so a CI
    workflow can upload it as a GitHub Actions artifact -- same pattern as
    06-deploy.yml's deploy-context.json (write here, upload as a separate workflow
    step). Without this, an unexpected response shape is unrecoverable, exactly like
    the original incident that motivated this wrapper change (a $0.205 API call whose
    malformed output was never persisted anywhere).

    Returns the filename written, for inclusion in the raised exception's message.
    """
    filename = f"forge-structured-output-failure-{stage_name}-{request_id}.json"
    try:
        raw: Any = response.model_dump(mode="json")
    except Exception as exc:  # defensive: never let diagnostics-writing itself crash
        raw = {"error": f"response.model_dump() failed: {exc}", "repr": repr(response)}
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)
    return filename


def _extract_structured_output(response: Any, stage_name: str, request_id: str) -> dict[str, Any]:
    """
    Extract the forced tool_use block's `.input` from a structured-output response.
    Caller must have already confirmed `stop_reason != "max_tokens"` -- this function
    does not re-check it, and does not attempt to salvage a truncated block.

    Raises RuntimeError (with the raw response persisted for diagnosis) if the response
    doesn't have exactly one tool_use block, or if `.input` isn't a dict -- both would
    otherwise be silent KeyError/AttributeError-shaped failures downstream in the
    calling stage agent.
    """
    tool_use_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
    if len(tool_use_blocks) != 1:
        path = _persist_raw_response_for_diagnosis(response, stage_name, request_id)
        raise RuntimeError(
            f"Stage '{stage_name}' [{request_id}]: expected exactly one tool_use block "
            f"for forced structured output (name='{_STRUCTURED_OUTPUT_TOOL_NAME}'), "
            f"found {len(tool_use_blocks)}. Raw response persisted to '{path}' for "
            f"diagnosis."
        )
    block_input = tool_use_blocks[0].input
    if not isinstance(block_input, dict):
        path = _persist_raw_response_for_diagnosis(response, stage_name, request_id)
        raise RuntimeError(
            f"Stage '{stage_name}' [{request_id}]: forced tool_use block's .input was "
            f"not a dict (got {type(block_input).__name__}). Raw response persisted to "
            f"'{path}' for diagnosis."
        )
    return block_input


def invoke_agent(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    model: str = _DEFAULT_MODEL,
    stage_name: str = "unknown",
    request_id: str = "unknown",
    output_schema: dict[str, Any] | None = None,
) -> AgentResult:
    """
    Invoke Claude via the Anthropic Messages API (single-turn, text only).

    This is the standard entry point for all FORGE pipeline stages except Stage 3.
    Each call is fully stateless — the model processes the combined system + user prompt
    and returns a response. No persistent session or agent loop is maintained.
    Context for the next stage is carried forward as committed files in the monorepo,
    not as retained model memory (ADR-0002).

    Args:
        system_prompt:  The agent's system prompt — persona, role, output format
                        instructions.
        user_prompt:    The user-turn input for this stage — assembled by the calling
                        agent script from the stage's input artifacts (spreadsheet
                        content, markdown files, previous stage outputs, etc.).
        max_tokens:     Maximum output tokens. Required by the Messages API. Pass a
                        value appropriate for the stage's expected output length
                        (e.g. 4096 for a short summary, 16000 for a full requirements
                        or design document).
        model:          Claude model ID. Defaults to Sonnet tier (claude-sonnet-4-6).
        stage_name:     Pipeline stage name for structured log output (e.g. "requirements").
        request_id:     FORGE request ID for log correlation (e.g. "req-0042").
        output_schema:  Optional JSON Schema (a plain dict, `type: "object"` with
                        `properties`/`required`). When provided, forces a single tool
                        call (`tools=[...]`, `tool_choice={"type": "tool", ...}`) whose
                        `input` is guaranteed to validate against this schema, and
                        populates `AgentResult.structured_output` with that `input` as
                        a plain dict — no `json.loads()`/fence-stripping needed at the
                        call site. `output_text` is still populated (the SDK exposes
                        both on the same response). Omit for a stage that only needs
                        free-text output (e.g. intake_agent.py's tracking-issue comment).

    Returns:
        AgentResult with:
            output_text        — the model's response text
            structured_output  — parsed tool_use input dict (only when output_schema
                                  was passed and stop_reason != "max_tokens"; else None)
            input_tokens        — input token count
            output_tokens       — output token count
            total_cost_usd      — USD cost from rate table (None if model not in table)
            num_turns           — always 1
            is_error            — always False (errors raise exceptions)
            all_messages        — list containing the raw Messages API response object

    Raises:
        anthropic.APIError: On API-level errors (auth failure, rate limit, etc.).
        RuntimeError: If output_schema was passed, stop_reason != "max_tokens", and the
                      response doesn't contain exactly one well-formed tool_use block
                      for the forced tool (raw response persisted to disk for
                      diagnosis first — see _persist_raw_response_for_diagnosis()).
        Exception: Any other unexpected error from the anthropic client.
    """
    client = anthropic.Anthropic()

    create_kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if output_schema is not None:
        create_kwargs["tools"] = [
            {
                "name": _STRUCTURED_OUTPUT_TOOL_NAME,
                "description": "Submit the structured output for this stage, matching the given schema exactly.",
                "input_schema": output_schema,
            }
        ]
        create_kwargs["tool_choice"] = {"type": "tool", "name": _STRUCTURED_OUTPUT_TOOL_NAME}

    # Streaming unconditionally, not just above some max_tokens threshold -- the
    # Anthropic SDK proactively raises ValueError on a non-streaming call it estimates
    # will exceed ~10 minutes (confirmed live: design_agent.py's _MAX_TOKENS=32000 hit
    # this before the request even reached the API). get_final_message() returns the
    # same Message shape create() does, so nothing downstream of this needs to change.
    start = time.monotonic()
    with client.messages.stream(**create_kwargs) as stream:
        response = stream.get_final_message()
    elapsed = time.monotonic() - start

    # Extract text from all TextBlock content blocks in the response.
    output_text = "".join(
        block.text for block in response.content if hasattr(block, "text")
    )

    # Token usage from the Messages API response usage object.
    usage = response.usage
    input_tokens: int = usage.input_tokens
    output_tokens: int = usage.output_tokens
    # cache fields are present on recent SDK versions; guard with getattr for safety
    cache_creation_tokens: int = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read_tokens: int = getattr(usage, "cache_read_input_tokens", 0) or 0

    total_cost_usd = _compute_cost(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_write_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
    )
    if total_cost_usd is None:
        logger.warning(
            "Stage '%s' [%s]: model '%s' not in _MODEL_RATES — cost not computed. "
            "Add the model to the rate table in claude_agent_wrapper.py.",
            stage_name,
            request_id,
            model,
        )

    stop_reason: str | None = response.stop_reason

    # Structured log line — one JSON object per invocation, greppable in Actions logs.
    # grep '"forge_event": "agent_invocation"' to find all FORGE agent runs in a job log.
    # Use total_cost_usd for Document 3 cost tracking (computed from _MODEL_RATES table).
    log_entry: dict[str, Any] = {
        "forge_event": "agent_invocation",
        "stage": stage_name,
        "request_id": request_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "cache_read_tokens": cache_read_tokens,
        "total_cost_usd": total_cost_usd,
        "num_turns": 1,
        "stop_reason": stop_reason,
        "is_error": False,
        "latency_seconds": round(elapsed, 3),
    }
    print(json.dumps(log_entry), flush=True)
    logger.info(
        "Stage '%s' [%s]: %d in / %d out / %d cache_read / %d cache_create tokens, "
        "cost=$%s, 1 turn, %.2fs",
        stage_name,
        request_id,
        input_tokens,
        output_tokens,
        cache_read_tokens,
        cache_creation_tokens,
        f"{total_cost_usd:.6f}" if total_cost_usd is not None else "N/A",
        elapsed,
    )

    # Structured-output extraction happens last, after cost/token logging above is
    # already emitted -- so a $-costed call's spend is never lost to logs even if
    # extraction itself raises (the original Item #31 gap this wrapper change fixes).
    # Never read .input on a max_tokens truncation (see module docstring) -- leave
    # structured_output=None and let the caller's existing stop_reason guard raise.
    structured_output: dict[str, Any] | None = None
    if output_schema is not None and stop_reason != "max_tokens":
        structured_output = _extract_structured_output(response, stage_name, request_id)

    return AgentResult(
        output_text=output_text,
        structured_output=structured_output,
        all_messages=[response],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
        total_cost_usd=total_cost_usd,
        num_turns=1,
        is_error=False,
        stop_reason=stop_reason,
        latency_seconds=elapsed,
        stage_name=stage_name,
        request_id=request_id,
    )
