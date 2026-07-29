# ADR-0011: Base Anthropic Client for Non-Stage-3 Agent Invocation

**Status:** Accepted
**Date:** 2026-07-29
**RFC:** N/A — decided organically during Phase 3.1 build and live smoke-testing;
no GitHub Discussion was opened. Recorded as a full ADR (not a documentation-only
fix) because it reverses architecture stated in Documents 2, 3, and 9.

## Context

Documents 2, 3, and 9 originally mandated the Claude Agent SDK (`claude-agent-sdk`)
as the invocation mechanism for every FORGE stage except Stage 3 (Intake,
Requirements, Design, QA, Security, Deploy) — six of the pipeline's seven stages.
This assumed the Agent SDK's autonomous tool-use loop (Read/Write/Edit/Bash,
bundled Claude Code CLI) was the appropriate runtime for agentic work generally.

Phase 3.1 build and live smoke testing surfaced two facts that weren't known when
that decision was made:

1. The Agent SDK bundles the full Claude Code CLI as a subprocess. Every
   invocation — even a trivial, tool-free text exchange — pays a fixed overhead:
   ~25,700 tokens of Claude Code's system prompt and built-in tool definitions
   written to cache on a cold call (~$0.10 at $3.75/MTok cache-write rates), plus
   a subprocess-launch latency floor measured at ~10 seconds in testing,
   regardless of how small the actual task is.
2. None of the six non-Stage-3 stages use the Agent SDK's autonomous
   tool-execution capability. FORGE's deterministic Python layer performs all
   file I/O (reading spreadsheets, writing markdown/YAML, committing to Git) for
   these stages; Claude is only ever asked to generate text from content already
   placed in the prompt. This was confirmed empirically — every Phase 3.1
   invocation across these stages already passed `allowed_tools=[]`, meaning the
   tool-use capability was provisioned but never exercised.

## Decision

The six non-Stage-3 stages switch from the Claude Agent SDK to the base
`anthropic` Python client, calling the Messages API directly with a per-stage
system prompt. Stage 3 is unaffected — it uses Anthropic Managed Agents
(ADR-0010), a separate mechanism entirely, not the Agent SDK.

The `invoke_agent()` function signature and `AgentResult` return contract in
`core/agents/utils/claude_agent_wrapper.py` are preserved as closely as possible,
so the six stage-agent scripts that call it require no architectural changes —
only the wrapper's internal transport changes. `allowed_tools` is removed from
the interface, since there is no tool-use loop left to scope; any future stage
that genuinely needs autonomous tool-calling should use the Messages API's own
`tools` parameter (scoped, per-call function definitions) rather than
reintroducing the Agent SDK for that one stage, or should adopt the Agent SDK
explicitly with a documented rationale, following this same ADR process.

## Consequences

+ Eliminates the ~$0.10 cold-call cost floor and ~25.7k-token cache-creation tax
  on cold calls for five-sixths of the pipeline's agent invocations
+ Eliminates the ~10-second subprocess-launch latency floor per invocation
+ Removes the bundled Claude Code CLI dependency for these six stages — GitHub
  Actions runners no longer need it for anything but Stage 3's own tooling (if any)
+ Drops a dependency on `claude-agent-sdk`, an Alpha-classified package with a
  near-daily release cadence and at least one prior breaking rename
  (`ClaudeCodeOptions` → `ClaudeAgentOptions`) in its short history — less
  beta-instability exposure for the five-sixths of the pipeline that never needed
  its agentic capabilities in the first place
- Loses the Agent SDK's automatic per-invocation cost computation
  (`total_cost_usd` from `ResultMessage`). FORGE must maintain its own per-model
  token-rate table in the wrapper to keep cost logging accurate; this table needs
  manual updates if Anthropic's published pricing changes
- Loses latent tool-use capability for these six stages. If a future requirement
  genuinely needs Claude to autonomously read/write files or run commands within
  one of these stages, that stage would need either a scoped Messages API
  `tools` definition or a documented, stage-specific reintroduction of the Agent
  SDK — not a silent revert
- Reverses part of the architecture documented in Documents 2, 3, and 9, which
  mandated the Agent SDK for all non-Stage-3 stages. Those documents have since
  been corrected to reflect this decision (Documents 2 v3, 3 v7, 9 v6).
