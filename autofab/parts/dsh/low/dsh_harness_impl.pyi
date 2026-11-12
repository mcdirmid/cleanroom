"""Low-level implementation specification for dsh_harness_impl."""

from typing import Any, Mapping, Optional, Sequence
from support.lib.framework import operation, override, poly_type, singleton_type
from support.lib.lifecycle import Singleton
import session as agent_session
import autofab_files_ext
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
        - Prepares concise two-step task prompts directing workers strictly to read AGENTS.md in the workspace root if not already in context and run bin/get_work,
          omitting role labels, workspace paths, and explanatory ceremony,
          incorporates coordinator reminder directives when provided in role dispatch directives,
          derives initial pending targets in task memory from assigned ready targets or disk pending work without writing pending buffers to disk prior to worker execution,
          tracks pre-dispatch file offsets of candidate event logs to isolate round-specific action records,
          evaluates server reachability via dsh_telemetry,
          dispatches over the local RPC bridge when reachable with retry backoff to stream progress to the desktop UI without file lock contention (failing cleanly without attempting incompatible headless CLI fallback resumption),
          renames previous conversation to put [<scope>] dead - <role> after a replacement conversation is issued for the role,
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
          differences seeded from ready targets or disk pending work via work, inspects autofab_files_ext.BLAME_BUFFER_FILE and
          candidate event logs across workspace root and scoped directories scanning only lines beyond pre-dispatch file offsets for attributed defects and action records matching change, clean, submitted, and audit records, extracts active session identifiers from RPC task handles (supporting dsh_rpc:: and dsh_rpc_web::) or scrapes from event logs and
          saves to the state directory session ID file (recycling after N rounds defaulting to 8 rounds with clean session reset, resetting session on failure), assigns unresolved status when zero targets are submitted or blamed or when interrupted without clean completion,
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
        - Polls process status via poll() or queries round RPC status, returning None if still running (unless marked interrupted),
          or processing autofab_files_ext.BLAME_BUFFER_FILE and candidate event logs across workspace root and scoped directories, buffer differences, and session telemetry upon completion or interruption.
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
        - Aborts the active RPC session via session/cancel or terminates the running subprocess associated with task_handle, and marks the task interrupted without marking the active conversation dead before a replacement exists.
        """
        ...

    @operation
    @override
    def update_orchestration_state(
        self,
        dir_scope: str,
        wave_count: int,
        active_workers: Mapping[str, str],
        assigned_targets: Mapping[str, Sequence[str]],
        all_scope_roles: Sequence[str],
        converged: bool = False,
        failed: bool = False,
    ) -> None:
        """Updates and publishes external orchestration state for the active scope.

        GROUNDING:
        - Resolves coordination storage location, matches active roles to recorded session identifiers, filters out uninvoked roles, tracks superseded sessions, and writes authoritative state snapshot JSON.
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
# LAST_CLEANED: 2026-10-30T19:50:00Z
# LAST_CHANGED: 2026-11-11T16:30:00Z
# CHANGE: Support Web RPC task handles (dsh_rpc_web::) for session ID extraction and round continuity
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
