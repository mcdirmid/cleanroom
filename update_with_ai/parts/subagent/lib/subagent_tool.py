"""Interface specification for subagent_tool."""

from __future__ import annotations

from typing import Optional, Protocol, Sequence
from support.lib.lifecycle import Singleton
from update_with_ai.parts.agent.lib.session import AgentSessionTier


# Contract: SubagentToolRunner dispatches commands and executes subagent orchestration.
class SubagentToolRunner(Singleton[AgentSessionTier], Protocol):
    """Command dispatch and execution runner for subagent orchestration."""

    # Contract: SubagentToolRunner.execute_command - parses CLI argument sequence and executes selected action.
    def execute_command(self, argv: Sequence[str]) -> int:
        """Dispatches and executes subagent commands matching an argument sequence."""
        ...

    # Contract: SubagentToolRunner.run_orchestrate - orchestrates multi-agent execution across topological waves until convergence.
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
        target_node: Optional[str] = None,
        max_unproductive_rounds: Optional[int] = None,
    ) -> int:
        """Orchestrates multi-agent execution across topological waves until convergence."""
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_tool interface library
# --- END CLEANROOM METADATA ---
