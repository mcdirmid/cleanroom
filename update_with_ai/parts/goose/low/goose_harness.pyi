# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T09:50:00Z
# CHANGE: author goose_harness interface low-level specification
# CODE_HASH: a22c1a37317f
# SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for goose_harness."""

from dataclasses import dataclass
from typing import Optional, Protocol
from framework import data_type, operation, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import subagent_coordinator


@data_type
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


@poly_type
class GooseTelemetryParser(Protocol):
    """Parses Goose SQLite session databases and execution logs for token metrics."""

    @operation
    def parse_session_db(
        self,
        sessions_db_path: str,
        session_name: str,
        model_name: Optional[str] = None,
    ) -> GooseSessionTokenMetrics:
        """Queries the SQLite sessions database and returns token metrics.

        POSTCONDITIONS:
        - MUST query sessions and usage_ledger tables for recorded tokens.
        - MUST calculate cost_usd using rate card for model_name.
        """
        ...

    @operation
    def parse_log_text(
        self,
        log_text: str,
        model_name: Optional[str] = None,
    ) -> GooseSessionTokenMetrics:
        """Parses stdout log text for token metrics when database records are unavailable.

        POSTCONDITIONS:
        - MUST parse token counts from log text and calculate cost_usd.
        """
        ...


@poly_type
class GooseHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns within Goose role workspaces."""

    @operation
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a Goose role workspace.

        POSTCONDITIONS:
        - MUST initiate Goose subagent turn in the designated workspace and return a task handle.
        """
        ...

    @operation
    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits Goose subagent turn completion and returns outcome result.

        POSTCONDITIONS:
        - MUST await turn completion without mandatory timeout unless configured, and return role turn result with telemetry.
        """
        ...

    @operation
    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls Goose subagent turn execution without blocking.

        POSTCONDITIONS:
        - WHEN subagent process has terminated, MUST return role turn result.
        - WHEN subagent process is still running, MUST return None without blocking or termination.
        """
        ...

    @operation
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active Goose subagent task execution upon timeout or limit.

        POSTCONDITIONS:
        - MUST terminate active Goose subagent process associated with task handle.
        """
        ...


@singleton_type("agent_session")
class GooseHarnessManager(InTier[AgentSessionTier], Protocol):
    """Manages Goose harness execution adapters and telemetry parsing services."""

    @operation
    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        sessions_db_path: Optional[str] = None,
    ) -> GooseHarnessAdapter:
        """Constructs a Goose harness adapter instance.

        POSTCONDITIONS:
        - MUST construct and return configured Goose harness adapter instance.
        """
        ...

    @operation
    def get_telemetry_parser(self) -> GooseTelemetryParser:
        """Returns the Goose telemetry parser service.

        POSTCONDITIONS:
        - MUST return Goose telemetry parser instance.
        """
        ...
