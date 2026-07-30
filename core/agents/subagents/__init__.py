"""
FORGE Managed Agents subagent definitions — Stage 3 (Implementation) only.

Shared tool configuration for the Backend, Frontend, and Test Writer specialist
subagents (ADR-0010). All three get the same scoped toolset: full filesystem +
shell access within their shared sandbox, no web access (offline, deterministic
code generation — no need to browse the internet, and no reason to give a
code-writing agent live network egress).
"""

from __future__ import annotations

DEFAULT_SCOPED_TOOLS: list[dict] = [
    {
        "type": "agent_toolset_20260401",
        "default_config": {
            "enabled": True,
            "permission_policy": {"type": "always_allow"},
        },
        "configs": [
            {"name": "web_search", "enabled": False},
            {"name": "web_fetch", "enabled": False},
        ],
    }
]
