# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_coordinator interface library
# CODE_HASH: 4314fbb50955
# --- END CLEANROOM METADATA ---

"""Interface specification for subagent_coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from support.lib.lifecycle import InTier
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier


@dataclass(frozen=True)
class TokenUsage:
    """Normalized token telemetry for an execution turn or cumulative session.

    Args:
        input_tokens: Uncached prompt tokens.
        cached_tokens: Cached prompt tokens.
        output_tokens: Generated completion tokens.
        total_tokens: Sum of input, cached, and output tokens.
        cost_usd: Monetary expenditure in USD.
    """

    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class RoleDispatch:
    """Directive dispatching work to an isolated role workspace.

    Args:
        role_name: Target role name.
        workspace_dir: Absolute path to the role workspace directory.
        dir_scope: Target directory scope.
        ready_targets: Sequence of relative ready target paths.
        batch_size: Optional maximum batch size bounding presented work.
        task_prompt: Instruction prompt for the role subagent.
    """

    role_name: str
    workspace_dir: str
    dir_scope: str
    ready_targets: Sequence[str]
    batch_size: Optional[int] = None
    task_prompt: str = ""


@dataclass(frozen=True)
class RoleTurnResult:
    """Outcome of an autonomous subagent execution turn.

    Args:
        role: Target role identifier.
        status: Turn outcome status.
        submitted_targets: Sequence of submitted target paths.
        blamed_targets: Sequence of blamed target paths.
        failure_reason: Optional diagnostic failure message.
        telemetry: Optional token telemetry recorded during the turn.
        wall_clock_seconds: Elapsed duration in seconds.
    """

    role: str
    status: str
    submitted_targets: Sequence[str] = ()
    blamed_targets: Sequence[str] = ()
    failure_reason: Optional[str] = None
    telemetry: Optional[TokenUsage] = None
    wall_clock_seconds: float = 0.0


@dataclass(frozen=True)
class OrchestrationSummary:
    """Outcome of iterative workspace orchestration across execution waves.

    Args:
        is_converged: True if all units across all roles in scope evaluate clean.
        total_waves: Number of execution waves dispatched.
        submitted_count: Total count of submitted unit targets.
        blamed_count: Total count of blamed unit targets.
        total_telemetry: TokenUsage
        status_message: Informational diagnostic status summary.
    """

    is_converged: bool
    total_waves: int
    submitted_count: int
    blamed_count: int
    total_telemetry: TokenUsage
    status_message: str


class HarnessAdapter(Protocol):
    """Abstract interface implemented by external agent execution harnesses."""

    def dispatch_role(self, dispatch: RoleDispatch) -> str:
        """Dispatches work directive to a subagent bound to the role workspace."""
        ...

    def await_role(self, task_handle: str) -> RoleTurnResult:
        """Awaits subagent turn completion and returns outcome result."""
        ...

    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or loop limit."""
        ...


class SubagentCoordinator(InTier[AgentSessionTier], Protocol):
    """Zero-execution coordinator scheduling subagents across role workspaces."""

    def compute_execution_waves(
        self,
        dir_scope: str,
        repo_root: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> Sequence[Sequence[RoleDispatch]]:
        """Evaluates DAG queues and groups unblocked ready roles into execution waves."""
        ...

    def run_wave(
        self,
        wave: Sequence[RoleDispatch],
        harness: HarnessAdapter,
    ) -> Sequence[RoleTurnResult]:
        """Dispatches all roles in an execution wave through the harness and awaits results."""
        ...

    def orchestrate(
        self,
        dir_scope: str,
        harness: HarnessAdapter,
        max_waves: int = 50,
        batch_size: Optional[int] = None,
        repo_root: Optional[str] = None,
    ) -> OrchestrationSummary:
        """Orchestrates iterative multi-agent execution until DAG convergence or failure."""
        ...
