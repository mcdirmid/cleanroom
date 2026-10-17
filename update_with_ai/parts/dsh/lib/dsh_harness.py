# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_harness interface library
# CODE_HASH: 067fe5b26aea
# --- END CLEANROOM METADATA ---

"""Interface specification for dsh_harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol
from update_with_ai.parts.subagent.lib import subagent_coordinator


from .dsh_telemetry import DshSessionTokenMetrics, DshTelemetryParser


# Contract: DshHarnessAdapter protocol for executing subagent turns within DeepSeek Harness workspaces.
class DshHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns within DeepSeek Harness role workspaces."""

    # Contract: MUST initiate DeepSeek Harness subagent turn in the designated workspace and return a task handle.
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a DeepSeek Harness role workspace."""
        ...

    # Contract: MUST await turn completion without mandatory timeout unless configured, and return role turn result with telemetry.
    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits DeepSeek Harness subagent turn completion and returns outcome result."""
        ...

    # Contract: MUST return None when running, or role turn result when terminated.
    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls DeepSeek Harness subagent turn execution without blocking."""
        ...

    # Contract: MUST terminate active DeepSeek Harness subagent process associated with task handle.
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active DeepSeek Harness subagent task execution upon timeout or limit."""
        ...


# Contract: DshHarnessManager protocol managing DeepSeek Harness execution adapters and telemetry parsing.
class DshHarnessManager(Protocol):
    """Manages DeepSeek Harness execution adapters and telemetry parsing services."""

    # Contract: MUST construct and return configured DeepSeek Harness adapter instance.
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
        """Constructs a DeepSeek Harness adapter instance."""
        ...

    # Contract: MUST install DeepSeek Harness adapter factory into subagent harness registry.
    def initialize(self) -> None:
        """Initializes the manager and installs the adapter factory into the harness registry."""
        ...

    # Contract: MUST return DeepSeek Harness telemetry parser instance.
    def get_telemetry_parser(self) -> DshTelemetryParser:
        """Returns the DeepSeek Harness telemetry parser service."""
        ...
