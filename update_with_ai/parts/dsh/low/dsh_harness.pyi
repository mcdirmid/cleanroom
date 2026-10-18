# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_harness interface low-level specification
# CODE_HASH: 1ee94bbfc278
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for dsh_harness."""

from dataclasses import dataclass
from typing import Any, Optional, Protocol
from framework import data_type, operation, poly_type, singleton_type
from support.lib.lifecycle import InTier
from session import AgentSessionTier
import dsh_telemetry
import subagent_coordinator
import subagent_harness

DshSessionTokenMetrics = dsh_telemetry.DshSessionTokenMetrics
DshTelemetryParser = dsh_telemetry.DshTelemetryParser


@poly_type
class DshHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns within DeepSeek Harness role workspaces."""

    @operation
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a DeepSeek Harness role workspace.

        POSTCONDITIONS:
        - MUST initiate DeepSeek Harness subagent turn via RPC bridge or headless process in the designated workspace and return a task handle.
        """
        ...

    @operation
    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits DeepSeek Harness subagent turn completion and returns outcome result.

        POSTCONDITIONS:
        - MUST await turn completion without mandatory timeout unless configured, and return role turn result with telemetry.
        """
        ...

    @operation
    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls DeepSeek Harness subagent turn execution without blocking.

        POSTCONDITIONS:
        - WHEN subagent process has terminated, MUST return role turn result.
        - WHEN subagent process is still running, MUST return None without blocking or termination.
        """
        ...

    @operation
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active DeepSeek Harness subagent task execution upon timeout or limit.

        POSTCONDITIONS:
        - MUST terminate active DeepSeek Harness subagent process associated with task handle.
        """
        ...


@singleton_type("agent_session")
class DshHarnessManager(InTier[AgentSessionTier], Protocol):
    """Manages DeepSeek Harness execution adapters and telemetry parsing services."""

    @operation
    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
        sessions_dir: Optional[str] = None,
        **kwargs: Any,
    ) -> DshHarnessAdapter:
        """Constructs a DeepSeek Harness adapter instance.

        POSTCONDITIONS:
        - MUST construct and return configured DeepSeek Harness adapter instance.
        """
        ...

    @operation
    def initialize(self) -> None:
        """Initializes the manager and installs the adapter factory into the harness registry.

        POSTCONDITIONS:
        - MUST install DeepSeek Harness adapter factory into subagent harness registry.
        """
        ...

    @operation
    def get_telemetry_parser(self) -> dsh_telemetry.DshTelemetryParser:
        """Returns the DeepSeek Harness telemetry parser service.

        POSTCONDITIONS:
        - MUST return DeepSeek Harness telemetry parser instance.
        """
        ...
