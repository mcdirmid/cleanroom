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


class DshHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns within DeepSeek Harness role workspaces."""

    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a DeepSeek Harness role workspace."""
        ...

    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits DeepSeek Harness subagent turn completion and returns outcome result."""
        ...

    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls DeepSeek Harness subagent turn execution without blocking."""
        ...

    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active DeepSeek Harness subagent task execution upon timeout or limit."""
        ...


class DshHarnessManager(Protocol):
    """Manages DeepSeek Harness execution adapters and telemetry parsing services."""

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

    def initialize(self) -> None:
        """Initializes the manager and installs the adapter factory into the harness registry."""
        ...

    def get_telemetry_parser(self) -> DshTelemetryParser:
        """Returns the DeepSeek Harness telemetry parser service."""
        ...
