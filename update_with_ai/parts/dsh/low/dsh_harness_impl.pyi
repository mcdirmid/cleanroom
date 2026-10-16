# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_harness_impl implementation low-level specification
# CODE_HASH: ab8496699564
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for dsh_harness_impl."""

from typing import Any, Optional
from framework import operation, override, poly_type, singleton_type
from support.lib.lifecycle import InTier
import agent_session
import dsh_ext
import dsh_harness
import dsh_telemetry
import subagent_coordinator
import subagent_harness
import workspace_work


@poly_type
class DshHarnessAdapter(dsh_harness.DshHarnessAdapter):
    """Realizes subagent execution in DeepSeek Harness role workspaces.

    GROUNDING:
    - Launches dsh headless CLI processes bound to dispatch.workspace_dir with Cordis overlay
      patches, tracks initial pending targets via workspace_work.WorkspaceWorkManager,
      awaits completion, extracts token telemetry via DshTelemetryParser, inspects blame buffers,
      and returns subagent_coordinator.RoleTurnResult objects.
    """

    @operation
    @override
    def dispatch_role(
        self,
        dispatch: subagent_coordinator.RoleDispatch,
    ) -> str:
        """Dispatches work directive to a DeepSeek Harness role workspace.

        GROUNDING:
        - Prepares role-tailored task prompts distinguishing auditor roles from authoring roles,
          executes dsh CLI process bound to dispatch.workspace_dir using headless profile and
          overlay patches conforming to dsh_ext, and returns task handle.
        """
        ...

    @operation
    @override
    def await_role(
        self,
        task_handle: str,
    ) -> subagent_coordinator.RoleTurnResult:
        """Awaits DeepSeek Harness subagent turn completion and returns outcome result.

        GROUNDING:
        - Awaits process completion without mandatory timeout unless configured, computes buffer
          differences via workspace_work, assigns unresolved status when zero targets are submitted or blamed,
          parses session telemetry via dsh_harness, and constructs subagent_coordinator.RoleTurnResult.
        """
        ...

    @operation
    @override
    def poll_role(
        self,
        task_handle: str,
    ) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls DeepSeek Harness subagent turn execution without blocking.

        GROUNDING:
        - Polls process status via poll(), returning None if still running,
          or processing blame records, buffer differences, and session telemetry upon completion.
        """
        ...

    @operation
    @override
    def interrupt_role(
        self,
        task_handle: str,
    ) -> None:
        """Aborts active DeepSeek Harness subagent task execution upon timeout or limit.

        GROUNDING:
        - Terminates the running subprocess associated with task_handle.
        """
        ...


@singleton_type("agent_session")
class DshHarnessManager(
    dsh_harness.DshHarnessManager,
    InTier[agent_session.AgentSessionTier],
):
    """Realizes management of DeepSeek Harness execution adapters and telemetry parsing.

    GROUNDING:
    - Instantiates DshHarnessAdapter and DshTelemetryParser services
      within agent_session.AgentSessionTier.
    """

    @operation
    @override
    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
        sessions_dir: Optional[str] = None,
        **kwargs: Any,
    ) -> dsh_harness.DshHarnessAdapter:
        """Constructs a DeepSeek Harness adapter instance.

        GROUNDING:
        - Instantiates DshHarnessAdapter with configured model, timeout, and session storage path.
        """
        ...

    @operation
    @override
    def initialize(self) -> None:
        """Initializes the manager and installs the adapter factory into the harness registry.

        GROUNDING:
        - Registers DeepSeek Harness adapter factory into subagent_harness.HarnessRegistry during agent session initialization.
        """
        ...

    @operation
    @override
    def get_telemetry_parser(self) -> dsh_harness.DshTelemetryParser:
        """Returns the DeepSeek Harness telemetry parser service.

        GROUNDING:
        - Returns a singleton or reusable instance of DshTelemetryParser.
        """
        ...
