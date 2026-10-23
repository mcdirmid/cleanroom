"""Low-level implementation specification for dsh_harness_impl."""

from typing import Any, Optional
from support.lib.framework import operation, override, poly_type, singleton_type
from support.lib.lifecycle import Singleton
import session as agent_session
import cleanroom_files_ext
import dsh_ext
import dsh_harness
import dsh_telemetry
import subagent_coordinator
import subagent_harness
import work


@poly_type
class DshHarnessAdapter(dsh_harness.DshHarnessAdapter):
    """Realizes subagent execution in DeepSeek Harness role workspaces.

    GROUNDING:
    - Launches dsh headless CLI processes bound to dispatch.workspace_dir with Cordis overlay
      patches, tracks initial pending targets via work.WorkspaceWorkManager,
      awaits completion, extracts token telemetry via DshTelemetryParser, inspects blame buffers,
      and returns subagent_coordinator.RoleRoundResult objects.
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
          incorporates coordinator reminder directives when provided in role dispatch directives,
          directs workers to read AGENTS.md in the workspace root and discover work via get_work without inlining target lists or writing pending buffers to disk prior to worker execution,
          instructs authoring roles to edit only assigned target files, rely solely on check_files,
          and refrain from implementing scratch tests or auxiliary files,
          derives initial pending targets in task memory from assigned ready targets or disk pending work without writing pending buffers to disk prior to worker execution,
          evaluates server reachability via dsh_telemetry,
          dispatches over the local RPC bridge when reachable with retry backoff to stream progress to the desktop UI without file lock contention (failing cleanly without attempting incompatible headless CLI fallback resumption),
          or executes the dsh CLI process bound to dispatch.workspace_dir using headless profile and overlay patches conforming to dsh_ext when the server is absent,
          and returns task handle.
        """
        ...

    @operation
    @override
    def await_role(
        self,
        task_handle: str,
    ) -> subagent_coordinator.RoleRoundResult:
        """Awaits DeepSeek Harness subagent round completion and returns outcome result.

        GROUNDING:
        - Awaits RPC round completion or process termination without mandatory timeout unless configured, computes buffer
          differences seeded from ready targets or disk pending work via work, inspects cleanroom_files_ext.BLAME_BUFFER_FILE and
          candidate cleanroom logs across workspace root and scoped directories for attributed defects and action records matching change, clean, submitted, and audit records, scrapes active session identifiers from event logs and
          saves to .cleanroom/dsh_session_id.txt (resetting session on failure), assigns unresolved status when zero targets are submitted or blamed,
          tracks session token baselines across rounds, calculates incremental round deltas from cumulative session metrics across persistent session rounds to prevent double-counting (evicting baselines upon failed rounds or session reset),
          parses session telemetry via dsh_telemetry, and constructs subagent_coordinator.RoleRoundResult.
        """
        ...

    @operation
    @override
    def poll_role(
        self,
        task_handle: str,
    ) -> Optional[subagent_coordinator.RoleRoundResult]:
        """Polls DeepSeek Harness subagent round execution without blocking.

        GROUNDING:
        - Polls process status via poll(), returning None if still running,
          or processing cleanroom_files_ext.BLAME_BUFFER_FILE and candidate cleanroom logs across workspace root and scoped directories, buffer differences, and session telemetry upon completion.
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
class DshHarnessManager(dsh_harness.DshHarnessManager):
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
        - Instantiates DshHarnessAdapter with configured model, timeout, and session storage path discovered across environment overrides and platform conventions.
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-20T22:50:00Z
# LAST_CHANGED: 2026-10-20T23:45:00Z
# CHANGE: Derive pending_before from ready targets or disk, search scoped cleanroom logs, and match change and clean action records
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
