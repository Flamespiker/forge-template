"""
FORGE Managed Agents subagent definitions — Stage 3 (Implementation) only.

Shared tool configuration for the Backend, Frontend, and Test Writer specialist
subagents (ADR-0010). All three get the same scoped toolset: full filesystem +
shell access within their shared sandbox, no web access (offline, deterministic
code generation — no need to browse the internet, and no reason to give a
code-writing agent live network egress).
"""

from __future__ import annotations

# Coordinator writes design.md/openapi.yaml/tasks.md here before delegating; Backend
# and Frontend read them directly from this path rather than via relay.
SHARED_DOCS_DIR = "/mnt/session/shared-docs"

# On an Enhancement run only (Item #23), the coordinator seeds the existing
# service's files here read-only via session resources[] -- mounted files
# cannot be edited in place, so the coordinator copies what's relevant into
# the real (empty, writable) service_root during its own step 0 before
# delegating, mirroring the SHARED_DOCS_DIR pattern above. On a Greenfield
# run this path simply doesn't exist in the sandbox -- subagents check for
# its presence to tell the two cases apart.
EXISTING_SERVICE_MOUNT_DIR = "/mnt/session/existing-service"

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
