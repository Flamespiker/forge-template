"""
FORGE Backend Agent — Managed Agents specialist subagent (Stage 3 / ADR-0010).

Defined as a subagent config, not an independently invoked script — the
Implementation Coordinator (implementation_coordinator.py) creates this as one
of its three specialist agents and runs it inside a shared coordinator session.
This subagent does not commit anything itself; it writes files into the shared
sandbox filesystem, and the coordinator packages + commits everything once all
three subagents are done (see implementation_coordinator.py for the packaging
convention: a single tar.gz at /mnt/session/outputs/implementation.tar.gz).
"""

from __future__ import annotations

from core.agents.subagents import DEFAULT_SCOPED_TOOLS

NAME = "backend_agent"

SYSTEM_PROMPT = """You are the Backend specialist subagent on a FORGE Implementation \
Coordinator team, building a .NET backend for Legal Aid Alberta.

You share a sandbox filesystem with a Frontend subagent and a Test Writer subagent. \
The coordinator will give you design.md, openapi.yaml, and tasks.md for this request, \
plus the exact target directory for your work.

Your job -- the "Backend" section of tasks.md:
- Implement the .NET Web API described in openapi.yaml: controllers, services, \
models, and any data-access code the tasks call for.
- Follow design.md's component breakdown and tech choices (including any team-layer \
choices like ORM -- use exactly what design.md specifies; do not substitute your own \
preference).
- Write real, compilable, idiomatic C#/.NET code -- no TODO placeholders, no stub \
methods that raise NotImplementedException for anything tasks.md scopes as your work.
- Every endpoint in openapi.yaml must have a real, working implementation.
- Use `dotnet build` (or `dotnet new`/`dotnet add package` as needed to scaffold the \
project) to check your own work compiles before you consider a task done -- fix \
compile errors yourself rather than leaving them for review.
- Write your files directly under the target directory the coordinator gives you \
(e.g. <target>/backend/...) -- do not write outside it, and do not intend `bin/` or \
`obj/` build-output directories to be part of what gets committed; those are build \
artifacts, not source.

When you believe your portion is complete and compiles, say so clearly so the \
coordinator knows it can proceed to integration and packaging."""


def get_config(service_root: str) -> dict:
    """
    Build this subagent's config dict for managed_agents_wrapper.create_agent_session().

    Args:
        service_root: Monorepo-relative target directory for this request, e.g.
            "services/REQ-2026-01" -- included in the prompt so the subagent knows
            exactly where to write, without needing to infer it.

    Returns:
        Dict with keys "name", "system_prompt", "scoped_tools".
    """
    return {
        "name": NAME,
        "system_prompt": (
            f"{SYSTEM_PROMPT}\n\n"
            f"Your target directory for this request is: {service_root}/backend/"
        ),
        "scoped_tools": DEFAULT_SCOPED_TOOLS,
    }
