# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_harness interface library
# CODE_HASH: a90025d88c46
# --- END CLEANROOM METADATA ---

"""Interface specification for antigravity_harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol
from support.lib.lifecycle import InTier
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier
from update_with_ai.parts.subagent.lib import subagent_coordinator


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


class TranscriptTelemetryParser(Protocol):
    """Parses Antigravity transcript logs to extract token telemetry."""

    def parse_transcript_file(
        self,
        transcript_path: str,
        model_name: Optional[str] = None,
    ) -> TranscriptTokenMetrics:
        """Parses a transcript log file and returns token metrics."""
        ...


class AntigravityHarnessAdapter(subagent_coordinator.HarnessAdapter, Protocol):
    """Executes subagent turns within Antigravity role workspaces."""

    def dispatch_role(self, dispatch: subagent_coordinator.RoleDispatch) -> str:
        """Dispatches work directive to an Antigravity role workspace."""
        ...

    def await_role(self, task_handle: str) -> subagent_coordinator.RoleTurnResult:
        """Awaits subagent turn completion and returns outcome result."""
        ...

    def interrupt_role(self, task_handle: str) -> None:
        """Aborts active subagent task execution upon timeout or limit."""
        ...


class AntigravityHarnessManager(InTier[AgentSessionTier], Protocol):
    """Manages Antigravity harness execution adapters and transcript parsing services."""

    def create_harness_adapter(
        self,
        model_name: Optional[str] = None,
        timeout_seconds: float = 600.0,
        custom_cmd: Optional[str] = None,
    ) -> AntigravityHarnessAdapter:
        """Constructs an Antigravity harness adapter instance."""
        ...

    def get_transcript_parser(self) -> TranscriptTelemetryParser:
        """Returns the transcript telemetry parser service."""
        ...
