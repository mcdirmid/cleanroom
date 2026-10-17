# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_tool_impl implementation low-level specification
# CODE_HASH: 93e66ab0c6d1
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for subagent_tool_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
import agent_session
import subagent_coordinator
import subagent_harness
import subagent_tool


@singleton_type("agent_session")
class SubagentToolRunner(
    subagent_tool.SubagentToolRunner,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes command dispatch and execution runner for subagent orchestration.

    GROUNDING:
    - Realizes CLI orchestration by resolving harness adapter via subagent_harness.HarnessResolver,
      coordinating execution waves via subagent_coordinator.SubagentCoordinator,
      and rendering summary telemetry.
    """

    @operation
    @override
    def execute_command(self, argv: Sequence[str]) -> int:
        """Dispatches and executes subagent commands matching an argument sequence.

        GROUNDING:
        - Parses argv using argparse for the orchestrate subcommand, prepending default orchestrate when omitted, and executes run_orchestrate.
        """
        ...

    @operation
    @override
    def run_orchestrate(
        self,
        dir_scope: str,
        target_role: Optional[str] = None,
        harness: Optional[str] = None,
        model: Optional[str] = None,
        max_waves: int = 50,
        batch_size: Optional[int] = None,
        timeout: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        repo_root: Optional[str] = None,
        max_unproductive_turns: Optional[int] = None,
    ) -> int:
        """Orchestrates multi-agent execution across topological waves until convergence.

        GROUNDING:
        - Resolves harness adapter via subagent_harness.HarnessResolver.resolve_harness,
          delegates multi-agent orchestration with optional unproductive turn limits to subagent_coordinator.SubagentCoordinator.orchestrate,
          and renders summary telemetry.
        """
        ...
