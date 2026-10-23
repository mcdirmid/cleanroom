"""Low-level interface specification for antigravity_harness."""

from dataclasses import dataclass
from typing import Any, Optional, Protocol
from support.lib.framework import data_type, operation, poly_type, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import subagent_coordinator
import subagent_harness


@data_type
@dataclass(frozen=True)
class TranscriptTokenMetrics:
    """Normalized token metrics parsed from an execution transcript log.

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
class TranscriptTelemetryParser(Protocol):
    """Parses Antigravity transcript logs to extract token telemetry."""

    @operation
    def parse_transcript_file(
        self,
        transcript_path: str,
        model_name: Optional[str] = None,
    ) -> TranscriptTokenMetrics:
        """Parses a transcript log file and returns token metrics.

        POSTCONDITIONS:
        - MUST parse transcript log and return transcript token metrics.
        - WHEN transcript lines are not valid JSON objects, MUST fall back to regular expression scraping for token metrics.
        - MUST calculate cost_usd using rate card for model_name.
        """
        ...


@poly_type
class AntigravityHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns within Antigravity role workspaces."""

    @operation
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to an Antigravity role workspace.

        POSTCONDITIONS:
        - MUST initiate subagent turn in the designated workspace and return a task handle.
        """
        ...

    @operation
    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits subagent turn completion and returns outcome result.

        POSTCONDITIONS:
        - MUST await turn completion and return role turn result with telemetry.
        - MUST extract submitted targets including completion tags parsed from standard output.
        """
        ...

    @operation
    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls subagent turn execution non-blockingly without waiting for completion.

        POSTCONDITIONS:
        - MUST return None if turn is still actively running.
        - MUST return RoleTurnResult if turn has completed or failed.
        """
        ...

    @operation
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or limit.

        POSTCONDITIONS:
        - MUST terminate active subagent process or session associated with task handle.
        """
        ...


@singleton_type("agent_session")
class AntigravityHarnessManager(Singleton[AgentSessionTier], Protocol):
    """Manages Antigravity harness execution adapters and transcript parsing services."""

    @operation
    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
        **kwargs: Any,
    ) -> AntigravityHarnessAdapter:
        """Constructs an Antigravity harness adapter instance.

        POSTCONDITIONS:
        - MUST construct and return configured Antigravity harness adapter instance.
        """
        ...

    @operation
    def initialize(self) -> None:
        """Initializes the manager and installs the adapter factory into the harness registry.

        POSTCONDITIONS:
        - MUST install antigravity harness adapter factory into subagent harness registry.
        """
        ...

    @operation
    def get_transcript_parser(self) -> TranscriptTelemetryParser:
        """Returns the transcript telemetry parser service.

        POSTCONDITIONS:
        - MUST return transcript telemetry parser instance.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_harness interface low-level specification
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
