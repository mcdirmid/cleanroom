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


# Contract: DshSessionTokenMetrics data type representing normalized token counts and cost.
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


# Contract: DshRpcTurnStatus data type representing RPC turn execution status and metrics.
@dataclass(frozen=True)
class DshRpcTurnStatus:
    """Turn execution status and metrics returned from the DeepSeek Harness JSON-RPC bridge.

    Args:
        is_active: Whether the turn is actively executing.
        is_completed: Whether the turn finished execution.
        error: Optional error message if execution failed.
        metrics: Accumulated token metrics.
    """

    is_active: bool = False
    is_completed: bool = False
    error: Optional[str] = None
    metrics: Optional[DshSessionTokenMetrics] = None


# Contract: DshTelemetryParser protocol for parsing session storage, streams, and desktop synchronization.
class DshTelemetryParser(Protocol):
    """Parses DeepSeek Harness session storage archives and event streams for token metrics."""

    # Contract: MUST locate session archives under sessions_dir matching workspace_dir and extract token usage with rate card cost.
    def parse_session_storage(
        self,
        sessions_dir: str,
        workspace_dir: str,
        model_name: Optional[str] = None,
    ) -> DshSessionTokenMetrics: ...

    # Contract: MUST parse token counts from JSON stream events or log text and calculate cost_usd.
    def parse_stream_text(
        self,
        stream_text: str,
        model_name: Optional[str] = None,
    ) -> DshSessionTokenMetrics: ...

    # Contract: MUST update desktop storage files and send RPC notifications when sessions_dir is valid.
    def sync_desktop_session(
        self,
        sessions_dir: Optional[str],
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        start_time: float,
    ) -> None: ...

    # Contract: MUST probe application cookie storage and verify reachability over the local RPC bridge.
    def is_desktop_server_available(
        self,
        sessions_dir: Optional[str] = None,
    ) -> bool: ...

    # Contract: MUST ensure workspace registration and create or resume session on the server.
    # MUST enqueue the prompt task and return a task handle, or None if unreachable.
    def dispatch_turn_rpc(
        self,
        workspace_dir: str,
        role_name: str,
        prompt_text: str,
        session_id: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Optional[str]: ...

    # Contract: MUST query turn execution status from the central server and return DshRpcTurnStatus.
    def poll_turn_rpc(
        self,
        task_handle: str,
        sessions_dir: Optional[str] = None,
    ) -> DshRpcTurnStatus: ...
