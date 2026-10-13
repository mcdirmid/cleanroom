# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_harness interface library
# CODE_HASH: 0b4425c932e8
# --- END CLEANROOM METADATA ---

"""Interface specification for dsh_harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol
from update_with_ai.parts.subagent.lib import subagent_coordinator


@dataclass(frozen=True)
class DshSessionTokenMetrics:
    """Normalized token metrics parsed from DeepSeek Harness session storage or event streams.

    Args:
        input_tokens: Uncached prompt tokens.
        cached_tokens: Cached prompt tokens.
        output_tokens: Generated completion tokens.
        total_tokens: Sum of input, cached, and output tokens.
        cost_usd: Monetary expenditure in USD.
        model_name: Resolved model identifier.
    """

    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model_name: str = ""


class DshTelemetryParser(Protocol):
    """Parses DeepSeek Harness session storage archives and event streams for token metrics."""

    def parse_session_storage(
        self,
        sessions_dir: str,
        workspace_dir: str,
        model_name: Optional[str] = None,
    ) -> DshSessionTokenMetrics:
        """Queries session storage archives and returns token metrics."""
        ...

    def parse_stream_text(
        self,
        stream_text: str,
        model_name: Optional[str] = None,
    ) -> DshSessionTokenMetrics:
        """Parses stdout JSON event streams or log text for token metrics."""
        ...


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
        sessions_dir: Optional[str] = None,
    ) -> DshHarnessAdapter:
        """Constructs a DeepSeek Harness adapter instance."""
        ...

    def get_telemetry_parser(self) -> DshTelemetryParser:
        """Returns the DeepSeek Harness telemetry parser service."""
        ...
