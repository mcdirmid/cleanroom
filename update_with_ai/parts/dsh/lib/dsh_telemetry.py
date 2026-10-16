# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:55:00Z
# CHANGE: Author dsh_telemetry interface
# CODE_HASH: b9c8cc318dfe
# --- END CLEANROOM METADATA ---

"""Interface specification for dsh_telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


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
    ) -> DshSessionTokenMetrics: ...

    def parse_stream_text(
        self,
        stream_text: str,
        model_name: Optional[str] = None,
    ) -> DshSessionTokenMetrics: ...

    def sync_desktop_session(
        self,
        sessions_dir: Optional[str],
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        start_time: float,
    ) -> None: ...
