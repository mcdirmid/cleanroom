"""Low-level interface specification for subagent_tool."""

from typing import Optional, Protocol, Sequence
from support.lib.framework import operation, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier


@singleton_type("agent_session")
class SubagentToolRunner(Singleton[AgentSessionTier], Protocol):
    """Command dispatch and execution runner for subagent orchestration."""

    @operation
    def execute_command(self, argv: Sequence[str]) -> int:
        """Dispatches and executes subagent commands matching an argument sequence.

        POSTCONDITIONS:
        - MUST parse CLI argument sequence and execute selected action.
        - WHEN a subcommand is omitted from argv, MUST prepend the default orchestrate subcommand.
        - MUST return integer exit status code.
        """
        ...

    @operation
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
        """Orchestrates multi-agent execution across topological waves until convergence.

        POSTCONDITIONS:
        - MUST resolve execution harness adapter with timeout and token limit options.
        - MUST coordinate dynamic supervision via subagent coordinator up to optional target role and optional target node with optional unproductive round limits.
        - MUST return 0 on convergence, 1 otherwise.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_tool interface low-level specification
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
