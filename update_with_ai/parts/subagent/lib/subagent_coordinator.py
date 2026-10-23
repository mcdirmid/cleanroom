"""Interface specification for subagent_coordinator."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional, Protocol, Sequence
from support.lib.lifecycle import Singleton
from update_with_ai.parts.agent.lib.session import AgentSessionTier


# Contract: normalized token telemetry for an execution turn or cumulative session
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


# Contract: directive dispatching work to an isolated role workspace
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


# Contract: outcome of an autonomous subagent execution round
@dataclass(frozen=True)
class RoleRoundResult:
    """Outcome of an autonomous subagent execution round.

    Args:
        role: Target role identifier.
        status: Round outcome status.
        submitted_targets: Sequence of submitted target paths.
        blamed_targets: Sequence of blamed target paths.
        failure_reason: Optional diagnostic failure message.
        telemetry: Optional token telemetry recorded during the round.
        wall_clock_seconds: Elapsed duration in seconds.
    """

    role: str
    status: str
    submitted_targets: Sequence[str] = ()
    blamed_targets: Sequence[str] = ()
    failure_reason: Optional[str] = None
    telemetry: Optional[TokenUsage] = None
    wall_clock_seconds: float = 0.0


# Deprecated backward-compatible alias
RoleTurnResult = RoleRoundResult


# Contract: outcome of iterative workspace orchestration across execution waves
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

    # Contract: dispatch work directive to a subagent bound to role workspace
    def dispatch_role(self, dispatch: RoleDispatch) -> str:
        """Dispatches work directive to a subagent bound to the role workspace."""
        ...

    # Contract: await subagent round completion and return outcome result
    def await_role(self, task_handle: str) -> RoleRoundResult:
        """Awaits subagent round completion and returns outcome result."""
        ...

    # Contract: poll subagent round execution without blocking
    def poll_role(self, task_handle: str) -> Optional[RoleRoundResult]:
        """Polls subagent round execution without blocking."""
        ...

    # Contract: abort active subagent task execution upon timeout or loop limit
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or loop limit."""
        ...


class SubagentCoordinator(Singleton[AgentSessionTier], Protocol):
    """Zero-execution coordinator scheduling subagents across role workspaces."""

    # Contract: evaluate DAG queues and group unblocked ready roles into execution waves
    def compute_execution_waves(
        self,
        dir_scope: str,
        target_role: Optional[str] = None,
        repo_root: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> Sequence[Sequence[RoleDispatch]]:
        """Evaluates DAG queues and groups unblocked ready roles into execution waves."""
        ...

    # Contract: dispatch all roles in an execution wave through harness and await results
    def run_wave(
        self,
        wave: Sequence[RoleDispatch],
        harness: HarnessAdapter,
    ) -> Sequence[RoleRoundResult]:
        """Dispatches all roles in an execution wave through the harness and awaits results."""
        ...

    # Contract: orchestrate iterative multi-agent execution until DAG convergence or failure
    def orchestrate(
        self,
        dir_scope: str,
        harness: HarnessAdapter,
        target_role: Optional[str] = None,
        max_waves: int = 50,
        batch_size: Optional[int] = None,
        repo_root: Optional[str] = None,
        model_name: Optional[str] = None,
        poll_interval: Optional[float] = None,
        max_unproductive_turns: Optional[int] = None,
        target_node: Optional[str] = None,
        max_unproductive_rounds: Optional[int] = None,
    ) -> OrchestrationSummary:
        """Orchestrates iterative multi-agent execution until DAG convergence or failure."""
        ...


# Contract: __orphan__ - resolves the canonical repository logs directory for a role workspace
def resolve_cleanroom_log_dir(workspace_dir: str) -> str:
    """Resolves the canonical repository logs directory for a role workspace."""
    try:
        from support.lib.lifecycle import Singleton, get_singleton
        import importlib
        ws_reg_mod = importlib.import_module("role_registry")
        reg = get_singleton(ws_reg_mod.WorkspaceRegistry)  # type: ignore
        main_root = reg.discover_repository_root(workspace_dir)
        log_dir = os.path.join(main_root, "logs")
    except Exception:
        parent = os.path.dirname(os.path.realpath(workspace_dir))
        if os.path.basename(parent) == "role_workspaces":
            p_root = os.path.dirname(parent)
            ws_base = os.path.basename(workspace_dir)
            main_cand = None
            for entry in sorted(os.listdir(p_root), key=len, reverse=True):
                if entry != "role_workspaces" and ws_base.startswith(f"{entry}_"):
                    cand = os.path.join(p_root, entry)
                    if os.path.isdir(cand):
                        main_cand = cand
                        break
            if main_cand:
                log_dir = os.path.join(main_cand, "logs")
            else:
                log_dir = os.path.join(workspace_dir, ".cleanroom", "logs")
        else:
            log_dir = os.path.join(workspace_dir, ".cleanroom", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-20T10:00:00Z
# CHANGE: Standardize terminology on role rounds and role round results, deprecating turn terminology
# --- END CLEANROOM METADATA ---
