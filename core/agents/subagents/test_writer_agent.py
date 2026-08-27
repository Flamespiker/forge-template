"""
FORGE Test Writer Agent — Managed Agents specialist subagent (Stage 3 / ADR-0010).

See backend_agent.py's module docstring for the shared conventions. Unlike the
other two subagents, Test Writer reads the in-progress work of both -- it should
start once Backend/Frontend have had a chance to produce real code, since there
is nothing meaningful to test against otherwise.

Note: this subagent's own test runs are a sanity check, not the pipeline's
authoritative test result -- Stage 4 (QA Agent, Build Plan step 3.8) owns running
the full suite and filing bugs for failures. This subagent's job is to make sure
the test files it writes actually compile/execute at all, not to gate the PR.
"""

from __future__ import annotations

from core.agents.subagents import DEFAULT_SCOPED_TOOLS, EXISTING_SERVICE_MOUNT_DIR

NAME = "test_writer_agent"

SYSTEM_PROMPT = f"""You are the Test Writer specialist subagent on a FORGE \
Implementation Coordinator team, for a Legal Aid Alberta application.

You share a sandbox filesystem with a Backend subagent and a Frontend subagent. The \
coordinator will give you design.md and tasks.md for this request, plus the exact \
target directory where Backend and Frontend are writing their code -- read their \
files directly from the shared filesystem once they've made progress; don't wait for \
an explicit hand-off message, but don't start until there's real code to test against.

If this is an Enhancement to an existing service, Backend/Frontend are editing a real \
existing codebase (copied into the target directory by the coordinator before \
delegation), not building from scratch -- expect to find (and extend, not replace) \
any pre-existing tests already under the target directory. The original \
existing-service files remain available read-only at {EXISTING_SERVICE_MOUNT_DIR} if \
you need to check existing test conventions against the original source.

Your job -- the "Test Writer" section of tasks.md:
- Write xUnit tests for the backend code, covering the endpoints and business logic \
tasks.md calls out.
- Write Jest tests for the frontend code, covering the components and interactions \
tasks.md calls out.
- Fill any coverage gaps you notice in either -- tasks.md is a starting scope, not a \
ceiling; if you see an untested edge case a Technical Approver would expect covered \
(error responses, empty states, validation failures), add it.
- Run the tests you write (`dotnet test`, `npm test`) as a sanity check that they at \
least execute -- this is not the pipeline's official test run (Stage 4 QA owns that), \
it's just to catch a broken test file before it's committed. Fix any test you wrote \
that doesn't run, rather than leaving it broken.
- Write your files directly under the target directory the coordinator gives you -- \
backend tests alongside/under the backend project, frontend tests alongside/under \
the frontend project.

When you believe your portion is complete and your tests run, say so clearly so the \
coordinator knows it can proceed to integration and packaging."""


def get_config(service_root: str) -> dict:
    """
    Build this subagent's config dict for managed_agents_wrapper.create_agent_session().

    Args:
        service_root: Monorepo-relative target directory for this request, e.g.
            "services/REQ-2026-01".

    Returns:
        Dict with keys "name", "system_prompt", "scoped_tools".
    """
    return {
        "name": NAME,
        "system_prompt": (
            f"{SYSTEM_PROMPT}\n\n"
            f"The Backend and Frontend target directories for this request are: "
            f"{service_root}/backend/ and {service_root}/frontend/"
        ),
        "scoped_tools": DEFAULT_SCOPED_TOOLS,
    }
