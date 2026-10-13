# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T09:50:00Z
# CHANGE: author goose_harness interface library
# CODE_HASH: 4b6e6c2b24c8
# --- END CLEANROOM METADATA ---

"""Interface specification for goose_harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol
from update_with_ai.parts.subagent.lib import subagent_coordinator


@dataclass(frozen=True)
class GooseSessionTokenMetrics:
    """Normalized token metrics parsed from Goose session storage or execution logs.

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


class GooseTelemetryParser(Protocol):
    """Parses Goose SQLite session databases and execution logs for token metrics."""

    def parse_session_db(
        self,
        sessions_db_path: str,
        session_name: str,
        model_name: Optional[str] = None,
    ) -> GooseSessionTokenMetrics:
        """Queries the SQLite sessions database and returns token metrics."""
        ...

    def parse_log_text(
        self,
        log_text: str,
        model_name: Optional[str] = None,
    ) -> GooseSessionTokenMetrics:
        """Parses stdout log text for token metrics when database records are unavailable."""
        ...


class GooseHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns within Goose role workspaces."""

    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a Goose role workspace."""
        ...

    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits Goose subagent turn completion and returns outcome result."""
        ...

    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls Goose subagent turn execution without blocking."""
        ...

    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active Goose subagent task execution upon timeout or limit."""
        ...


class GooseHarnessManager(Protocol):
    """Manages Goose harness execution adapters and telemetry parsing services."""

    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        sessions_db_path: Optional[str] = None,
    ) -> GooseHarnessAdapter:
        """Constructs a Goose harness adapter instance."""
        ...

    def get_telemetry_parser(self) -> GooseTelemetryParser:
        """Returns the Goose telemetry parser service."""
        ...
