"""Interface specification for dsh_telemetry."""

from __future__ import annotations
from autofab.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton

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


# Contract: DshRpcRoundStatus data type representing RPC round execution status and metrics.
@dataclass(frozen=True)
class DshRpcRoundStatus:
    """Round execution status and metrics returned from the DeepSeek Harness JSON-RPC bridge.

    Args:
        is_active: Whether the round is actively executing.
        is_completed: Whether the round finished execution.
        error: Optional error message if execution failed.
        metrics: Accumulated token metrics.
    """

    is_active: bool = False
    is_completed: bool = False
    error: Optional[str] = None
    metrics: Optional[DshSessionTokenMetrics] = None


# Backward compatibility alias
DshRpcTurnStatus = DshRpcRoundStatus


# Contract: DshTelemetryParser protocol for parsing session storage, streams, and desktop synchronization.
class DshTelemetryParser(Singleton[AgentSessionTier], Protocol):
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

    # Contract: MUST check active Web loopback bridge configuration and verify reachability over the bridge.
    def is_server_available(
        self,
        sessions_dir: Optional[str] = None,
    ) -> bool: ...

    # Contract: MUST ensure workspace registration and create or resume session on the server.
    # MUST set workspace title to the scope and session title to the role name.
    # MUST enqueue the prompt task and return a task handle, or None if unreachable.
    def dispatch_round_rpc(
        self,
        workspace_dir: str,
        role_name: str,
        prompt_text: str,
        session_id: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Optional[str]: ...

    # Backward compatibility alias for dispatch_round_rpc
    def dispatch_turn_rpc(
        self,
        workspace_dir: str,
        role_name: str,
        prompt_text: str,
        session_id: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Optional[str]: ...

    # Contract: MUST query round execution status from the central server and return DshRpcRoundStatus.
    def poll_round_rpc(
        self,
        task_handle: str,
        sessions_dir: Optional[str] = None,
    ) -> DshRpcRoundStatus: ...

    # Backward compatibility alias for poll_round_rpc
    def poll_turn_rpc(
        self,
        task_handle: str,
        sessions_dir: Optional[str] = None,
    ) -> DshRpcTurnStatus: ...

    # Contract: MUST rename a session on DeepSeek Harness Web bridge or Desktop RPC.
    def rename_session(
        self,
        session_id: str,
        title: str,
        sessions_dir: Optional[str] = None,
    ) -> bool: ...

    # Contract: MUST delete a session from DeepSeek Harness Web bridge or Desktop RPC.
    def delete_session(
        self,
        session_id: str,
        sessions_dir: Optional[str] = None,
    ) -> bool: ...

    # Contract: MUST discover and delete all existing sessions whose title contains [<dir_scope>].
    def cleanup_scope_sessions(
        self,
        dir_scope: str,
        sessions_dir: Optional[str] = None,
    ) -> int: ...


# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-11-09T23:32:00Z
# CHANGE: Add session renaming, deletion, and scope conversation cleanup operations
# --- END CLEANROOM METADATA ---
