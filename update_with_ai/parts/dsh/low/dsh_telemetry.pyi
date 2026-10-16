# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T18:55:00Z
# CHANGE: Author dsh_telemetry interface low-level specification
# CODE_HASH: 024b1259a460
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for dsh_telemetry."""

from dataclasses import dataclass
from typing import Optional, Protocol
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


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


@singleton_type("agent_session")
class DshTelemetryParser(InTier[AgentSessionTier], Protocol):
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

    @operation
    def sync_desktop_session(
        self,
        sessions_dir: Optional[str],
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        start_time: float,
    ) -> None:
        """Synchronizes active session records with the DeepSeek Harness Desktop application.

        POSTCONDITIONS:
        - MUST update desktop storage files and send RPC notifications when sessions_dir is valid.
        """
        ...
