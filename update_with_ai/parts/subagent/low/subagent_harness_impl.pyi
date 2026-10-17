# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T11:00:00Z
# CHANGE: turn down support for goose, supporting only antigravity and dsh
# CODE_HASH: 4bba3c5eea8f
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for subagent_harness_impl."""

from typing import Mapping, Optional, Sequence
from framework import operation, override, poly_type, singleton_type
from support.lib.lifecycle import InTier
import session as agent_session
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
        - Awaits process completion without mandatory timeout unless configured, reads blame records,
          computes submitted targets via pending work buffer difference, parses token metrics from
          process logs via regex patterns and rate multipliers, inspects log tail on non-zero exit for
          failure diagnostics, and constructs RoleTurnResult.
        """
        ...

    @operation
    @override
    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls subagent turn execution without blocking.

        GROUNDING:
        - Checks subprocess status via poll(), returning None if still running,
          or processing blame records, buffer differences, and token metrics upon completion.
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
class HarnessRegistry(
    subagent_harness.HarnessRegistry,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes harness registry and resolution for external agent platforms.

    GROUNDING:
    - Maintains installed adapter factories by platform name, registers newly installed
      factories via install_harness, and resolves harness adapters via installed factories,
      custom command templates, or simulation mode.
    """

    @property
    def installed_harnesses(self) -> Mapping[str, subagent_harness.HarnessAdapterFactory]: ...

    @operation
    @override
    def install_harness(
        self,
        platform_name: str,
        adapter_factory: subagent_harness.HarnessAdapterFactory,
    ) -> None:
        """Installs a harness adapter factory for a designated platform name.

        GROUNDING:
        - Stores adapter factory in internal platform dictionary keyed by normalized platform name.
        """
        ...

    @operation
    @override
    def resolve_harness(
        self,
        platform_name: str,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
    ) -> subagent_coordinator.HarnessAdapter:
        """Resolves a harness adapter for a platform name or custom command template.

        GROUNDING:
        - Resolves platform via registered factory or creates CommandHarnessAdapter configured
          with custom_cmd or simulation mode.
        """
        ...


HarnessResolver = HarnessRegistry
