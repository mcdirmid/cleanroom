# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_coordinator_impl implementation low-level specification
# CODE_HASH: a6132ac91315
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for subagent_coordinator_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
import session as agent_session
import subagent_coordinator
import provision
import role_registry
import work


@singleton_type("agent_session")
class SubagentCoordinator(
    subagent_coordinator.SubagentCoordinator,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes zero-execution multi-agent workspace coordination across execution waves.

    GROUNDING:
    - Realizes workspace coordination by querying commissioned role workspaces via
      role_registry.WorkspaceRegistry, evaluating dirty role work queues via
      work.WorkspaceWorkManager, commissioning absent workspaces via
      provision.WorkspaceProvisioner, grouping roles into topological waves,
      dispatching role directives through subagent_coordinator.HarnessAdapter,
      and aggregating token usage telemetry into standardized monetary expenditures.
    """

    @operation
    @override
    def compute_execution_waves(
        self,
        dir_scope: str,
        target_role: Optional[str] = None,
        repo_root: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> Sequence[Sequence[subagent_coordinator.RoleDispatch]]:
        """Evaluates DAG queues and groups unblocked ready roles into execution waves.

        GROUNDING:
        - Inspects commissioned workspaces via role_registry.WorkspaceRegistry.list_roles,
          queries ready tasks via work.WorkspaceWorkManager.compute_role_work_queue,
          commissions absent workspaces via provision.WorkspaceProvisioner.commission,
          partitions sequential specification roles into single-role waves, combines unblocked
          implementation roles into parallel waves, and constructs RoleDispatch directives.
        """
        ...

    @operation
    @override
    def run_wave(
        self,
        wave: Sequence[subagent_coordinator.RoleDispatch],
        harness: subagent_coordinator.HarnessAdapter,
    ) -> Sequence[subagent_coordinator.RoleTurnResult]:
        """Dispatches all roles in an execution wave through the harness and awaits results.

        GROUNDING:
        - Dispatches each role directive via harness.dispatch_role, awaits each result via
          harness.await_role, and collects RoleTurnResult instances.
        """
        ...

    @operation
    @override
    def orchestrate(
        self,
        dir_scope: str,
        harness: subagent_coordinator.HarnessAdapter,
        target_role: Optional[str] = None,
        max_waves: int = 50,
        batch_size: Optional[int] = None,
        repo_root: Optional[str] = None,
        model_name: Optional[str] = None,
        poll_interval: Optional[float] = None,
        max_unproductive_turns: Optional[int] = None,
    ) -> subagent_coordinator.OrchestrationSummary:
        """Orchestrates iterative multi-agent execution until DAG convergence or failure.

        GROUNDING:
        - Resets preexisting role workspace directories for declared roles via role_registry
          and filesystem operations.
        - Resolves subagent batch size, token limits, and maximum unproductive turn thresholds from model configurations and persists
          effective batch sizes into role workspaces.
        - Iterates dynamic process supervision until work queues are clean, a turn fails,
          consecutive unproductive turns exceed the threshold, or max_waves is exceeded,
          emitting real-time telemetry and aggregating TokenUsage into OrchestrationSummary.
        - Upon clean convergence, deletes provisioned role workspace directories for declared roles in scope.
        """
        ...

    @operation
    @override
    def resolve_cleanroom_log_dir(self, workspace_dir: str) -> str:
        """Resolves the canonical repository logs directory for a role workspace.

        GROUNDING:
        - Queries role_registry.WorkspaceRegistry to discover repository root, falling
          back to traversing parent directory structure, and returns logs directory path.
        """
        ...
