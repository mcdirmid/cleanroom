# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T20:00:00Z
# CHANGE: author dsh_harness interface low-level specification
# CODE_HASH: a92b80cdb1b1
# SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for dsh_harness."""

from dataclasses import dataclass
from typing import Optional, Protocol
from framework import data_type, operation, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import subagent_coordinator


@data_type
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


@poly_type
class DshTelemetryParser(Protocol):
    """Parses DeepSeek Harness session storage archives and event streams for token metrics."""

    @operation
    def parse_session_storage(
        self,
        sessions_dir: str,
        workspace_dir: str,
        model_name: Optional[str] = None,
    ) -> DshSessionTokenMetrics:
        """Queries session storage archives and returns token metrics.

        POSTCONDITIONS:
        - MUST locate session archives under sessions_dir matching workspace_dir and extract token usage.
        - MUST calculate cost_usd using rate card for model_name.
        """
        ...

    @operation
    def parse_stream_text(
        self,
        stream_text: str,
        model_name: Optional[str] = None,
    ) -> DshSessionTokenMetrics:
        """Parses stdout JSON event streams or log text for token metrics.

        POSTCONDITIONS:
        - MUST parse token counts from JSON stream events or log text and calculate cost_usd.
        """
        ...


@poly_type
class DshHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns within DeepSeek Harness role workspaces."""

    @operation
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to a DeepSeek Harness role workspace.

        POSTCONDITIONS:
        - MUST initiate DeepSeek Harness subagent turn in the designated workspace and return a task handle.
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
        sessions_dir: Optional[str] = None,
    ) -> DshHarnessAdapter:
        """Constructs a DeepSeek Harness adapter instance.

        POSTCONDITIONS:
        - MUST construct and return configured DeepSeek Harness adapter instance.
        """
        ...

    @operation
    def get_telemetry_parser(self) -> DshTelemetryParser:
        """Returns the DeepSeek Harness telemetry parser service.

        POSTCONDITIONS:
        - MUST return DeepSeek Harness telemetry parser instance.
        """
        ...
