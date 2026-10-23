"""Interface specification for antigravity_harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol
from support.lib.lifecycle import Singleton
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from update_with_ai.parts.subagent.lib import subagent_coordinator


# Contract: TranscriptTokenMetrics captures normalized token metrics parsed from an execution transcript log.
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


# Contract: TranscriptTelemetryParser parses Antigravity transcript logs to extract token telemetry.
class TranscriptTelemetryParser(Protocol):
    """Parses Antigravity transcript logs to extract token telemetry."""

    # Contract: TranscriptTelemetryParser.parse_transcript_file - parses transcript log and calculates cost_usd using rate card.
    def parse_transcript_file(
        self,
        transcript_path: str,
        model_name: Optional[str] = None,
    ) -> TranscriptTokenMetrics:
        """Parses a transcript log file and returns token metrics."""
        ...


# Contract: AntigravityHarnessAdapter executes subagent turns within Antigravity role workspaces.
class AntigravityHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns within Antigravity role workspaces."""

    # Contract: AntigravityHarnessAdapter.dispatch_role - initiates subagent turn in designated workspace and returns task handle.
    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to an Antigravity role workspace."""
        ...

    # Contract: AntigravityHarnessAdapter.await_role - awaits turn completion and returns role turn result with telemetry.
    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits subagent turn completion and returns outcome result."""
        ...

    # Contract: AntigravityHarnessAdapter.poll_role - polls subagent turn execution non-blockingly without waiting for completion.
    def poll_role(self, task_handle: str) -> Optional[subagent_coordinator.RoleTurnResult]:
        """Polls subagent turn execution non-blockingly without waiting for completion."""
        ...

    # Contract: AntigravityHarnessAdapter.interrupt_role - aborts active subagent task execution upon timeout or limit.
    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or limit."""
        ...


# Contract: AntigravityHarnessManager manages Antigravity harness execution adapters and transcript parsing services.
class AntigravityHarnessManager(Singleton[AgentSessionTier], Protocol):
    """Manages Antigravity harness execution adapters and transcript parsing services."""

    # Contract: AntigravityHarnessManager.create_harness_adapter - constructs and returns configured Antigravity harness adapter instance.
    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
        custom_cmd: Optional[str] = None,
        simulation_mode: bool = False,
        **kwargs: Any,
    ) -> AntigravityHarnessAdapter:
        """Constructs an Antigravity harness adapter instance."""
        ...

    # Contract: AntigravityHarnessManager.initialize - installs antigravity harness adapter factory into subagent harness registry.
    def initialize(self) -> None:
        """Initializes the manager and installs the adapter factory into the harness registry."""
        ...

    # Contract: AntigravityHarnessManager.get_transcript_parser - returns transcript telemetry parser instance.
    def get_transcript_parser(self) -> TranscriptTelemetryParser:
        """Returns the transcript telemetry parser service."""
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_harness interface library
# --- END CLEANROOM METADATA ---
