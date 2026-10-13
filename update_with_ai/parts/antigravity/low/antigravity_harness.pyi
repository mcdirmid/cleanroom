# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_harness interface low-level specification
# CODE_HASH: d2a1356a0e55
# SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for antigravity_harness."""

from dataclasses import dataclass
from typing import Optional, Protocol
from framework import data_type, operation, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import subagent_coordinator


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
class AntigravityHarnessManager(InTier[AgentSessionTier], Protocol):
    """Manages Antigravity harness execution adapters and transcript parsing services."""

    @operation
    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: float = 600.0,
        custom_cmd: Optional[str] = None,
    ) -> AntigravityHarnessAdapter:
        """Constructs an Antigravity harness adapter instance.

        POSTCONDITIONS:
        - MUST construct and return configured Antigravity harness adapter instance.
        """
        ...

    @operation
    def get_transcript_parser(self) -> TranscriptTelemetryParser:
        """Returns the transcript telemetry parser service.

        POSTCONDITIONS:
        - MUST return transcript telemetry parser instance.
        """
        ...
