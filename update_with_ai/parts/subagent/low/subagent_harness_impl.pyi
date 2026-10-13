# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-12T21:00:00Z
# CHANGE: author subagent_harness_impl implementation low-level specification
# CODE_HASH: 5e52a87d032b
# SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for subagent_harness_impl."""

from typing import Optional, Sequence
from framework import operation, override, poly_type, singleton_type
from support.lib.lifecycle import InTier
import agent_session
import subagent_coordinator
import subagent_harness


@poly_type
class CommandHarnessAdapter(
    subagent_harness.CommandHarnessAdapter,
):
    """Realizes subagent turn execution through process command templates.

    GROUNDING:
    - Realizes subagent turn dispatch and result formulation by capturing initial pending targets
      from the pending work buffer, interpolating process command templates with workspace and prompt variables,
      monitoring subprocess lifecycle and enforcing timeouts, inspecting blame buffer records, computing submitted
      work targets from buffer diffs, parsing log token metrics, and computing financial costs
      as token usage telemetry via subagent_coordinator.
    """

    @operation
    @override
    def format_task_prompt(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Constructs instructional task prompt for the role subagent.

        GROUNDING:
        - Formulates task prompt with role, directory scope, assigned targets, guide instructions,
          check-files verification, and cleanroom_role_tool submit and blame commands.
        """
        ...

    @operation
    @override
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a subagent bound to the role workspace.

        GROUNDING:
        - Captures initial pending targets, generates log file path, launches subprocess
          matching command template, and records active task record.
        """
        ...

    @operation
    @override
    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits subagent turn completion and returns outcome result.

        GROUNDING:
        - Awaits process completion with timeout, reads blame records, computes submitted targets
          via pending work buffer difference, parses token metrics, and constructs RoleTurnResult.
        """
        ...

    @operation
    @override
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or loop limit.

        GROUNDING:
        - Sends termination signal to running subprocess associated with task handle.
        """
        ...


@singleton_type("agent_session")
class HarnessResolver(
    subagent_harness.HarnessResolver,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes harness resolution for external agent platforms.

    GROUNDING:
    - Maps platform names to canonical command templates or produces simulation adapters.
    """

    @operation
    @override
    def resolve_harness(
        self,
        platform_name: str,
        model_name: Optional[str] = None,
        timeout_seconds: float = 600.0,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
    ) -> subagent_coordinator.HarnessAdapter:
        """Resolves a harness adapter for a platform name or custom command template.

        GROUNDING:
        - Resolves platform names (antigravity, goose, dsh) to canonical templates
          or creates CommandHarnessAdapter configured with custom_cmd or simulation mode.
        """
        ...
