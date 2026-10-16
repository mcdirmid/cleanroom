# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_coordinator interface low-level specification
# CODE_HASH: 6b25eb8873f8
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for subagent_coordinator."""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from framework import data_type, operation, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


@data_type
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


@data_type
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


@data_type
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


@data_type
@dataclass(frozen=True)
class OrchestrationSummary:
    """Outcome of iterative workspace orchestration across execution waves.

    Args:
        is_converged: True if all units across all roles in scope evaluate clean.
        total_waves: Number of execution waves dispatched.
        submitted_count: Total count of submitted unit targets.
        blamed_count: Total count of blamed unit targets.
        total_telemetry: Cumulative token usage and monetary cost.
        status_message: Informational diagnostic status summary.
    """

    is_converged: bool
    total_waves: int
    submitted_count: int
    blamed_count: int
    total_telemetry: TokenUsage
    status_message: str


@poly_type
class HarnessAdapter(Protocol):
    """Abstract interface implemented by external agent execution harnesses."""

    @operation
    def dispatch_role(self, dispatch: RoleDispatch) -> str:
        """Dispatches work directive to a subagent bound to the role workspace.

        POSTCONDITIONS:
        - MUST initiate subagent turn in the designated workspace and return a task handle.
        """
        ...

    @operation
    def await_role(self, task_handle: str) -> RoleTurnResult:
        """Awaits subagent turn completion and returns outcome result.

        POSTCONDITIONS:
        - MUST await turn completion and return role turn result with telemetry.
        """
        ...

    @operation
    def poll_role(self, task_handle: str) -> Optional[RoleTurnResult]:
        """Polls subagent turn execution without blocking.

        POSTCONDITIONS:
        - WHEN subagent process has terminated, MUST return role turn result.
        - WHEN subagent process is still running, MUST return None without blocking or termination.
        """
        ...

    @operation
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or loop limit.

        POSTCONDITIONS:
        - MUST terminate active subagent process or session associated with task handle.
        """
        ...


@singleton_type("agent_session")
class SubagentCoordinator(InTier[AgentSessionTier], Protocol):
    """Zero-execution coordinator scheduling subagents across role workspaces."""

    @operation
    def compute_execution_waves(
        self,
        dir_scope: str,
        target_role: Optional[str] = None,
        repo_root: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> Sequence[Sequence[RoleDispatch]]:
        """Evaluates DAG queues and groups unblocked ready roles into execution waves.

        POSTCONDITIONS:
        - MUST discover ready dirty roles unblocked by upstream prerequisites across directory scope.
        - WHEN a scheduled role's workspace directory is absent, MUST commission the workspace via WorkspaceProvisioner.
        - MUST separate sequential specification roles into single-role waves.
        - MUST combine independent unblocked implementation roles into parallel waves.
        - MUST return sequence of execution waves containing role dispatch directives.
        """
        ...

    @operation
    def run_wave(
        self,
        wave: Sequence[RoleDispatch],
        harness: HarnessAdapter,
    ) -> Sequence[RoleTurnResult]:
        """Dispatches all roles in an execution wave through the harness and awaits results.

        POSTCONDITIONS:
        - MUST dispatch each role directive through harness.dispatch_role.
        - MUST await completion of each dispatched role through harness.await_role.
        - MUST return sequence of role turn results.
        """
        ...

    @operation
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
    ) -> OrchestrationSummary:
        """Orchestrates iterative multi-agent execution until DAG convergence or failure.

        POSTCONDITIONS:
        - MUST reset preexisting role workspaces for declared roles upon initiating orchestration.
        - MUST iterate through execution waves until all units in scope evaluate clean, a role fails, or max_waves is reached.
        - MUST periodically poll active workers through harness.poll_role or harness.await_role at a configurable interval defaulting to 10.0 seconds.
        - WHEN a role turn reports status failed, MUST stop execution and return non-converged summary with failure details.
        - WHEN consecutive unproductive turns for a role on unresolved targets exceed the threshold (defaulting to 2), MUST stop execution and return non-converged summary with impasse details.
        - MUST emit real-time progress notifications detailing role dispatch, turn outcomes, token consumption, and work queue state.
        - WHEN all units evaluate clean across all roles, MUST automatically delete all provisioned role workspaces in scope and return converged summary.
        - MUST aggregate cumulative token usage and monetary expenditure in orchestration summary.
        """
        ...
