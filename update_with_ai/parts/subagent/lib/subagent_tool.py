# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_tool interface library
# CODE_HASH: 840a39d560cf
# --- END CLEANROOM METADATA ---

"""Interface specification for subagent_tool."""

from __future__ import annotations

from typing import Optional, Protocol, Sequence
from support.lib.lifecycle import InTier
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier


class SubagentToolRunner(InTier[AgentSessionTier], Protocol):
    """Command dispatch and execution runner for subagent orchestration."""

    def execute_command(self, argv: Sequence[str]) -> int:
        """Dispatches and executes subagent commands matching an argument sequence."""
        ...

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
    ) -> int:
        """Orchestrates multi-agent execution across topological waves until convergence."""
        ...
