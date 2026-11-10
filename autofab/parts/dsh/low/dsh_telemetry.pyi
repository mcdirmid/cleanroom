"""Low-level interface specification for dsh_telemetry."""

from dataclasses import dataclass
from typing import Optional, Protocol
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier


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


@data_type
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


DshRpcTurnStatus = DshRpcRoundStatus


@singleton_type("agent_session")
class DshTelemetryParser(Singleton[AgentSessionTier], Protocol):
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
    def is_server_available(
        self,
        sessions_dir: Optional[str] = None,
    ) -> bool:
        """Evaluates whether an active DeepSeek Harness Web loopback bridge is reachable.

        POSTCONDITIONS:
        - MUST check active Web loopback bridge configuration and verify reachability over the bridge.
        """
        ...

    @operation
    def dispatch_round_rpc(
        self,
        workspace_dir: str,
        role_name: str,
        prompt_text: str,
        session_id: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Optional[str]:
        """Dispatches a role round over the local JSON-RPC bridge to the central DeepSeek Harness server.

        POSTCONDITIONS:
        - MUST create or resume session on the server directly within the role workspace directory.
        - MUST set session title to capture scope and role.
        - MUST enqueue the prompt task and return a task handle, or None if unreachable.
        """
        ...

    @operation
    def dispatch_turn_rpc(
        self,
        workspace_dir: str,
        role_name: str,
        prompt_text: str,
        session_id: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> Optional[str]:
        """Dispatches a role round over the local JSON-RPC bridge (backwards-compatible alias for dispatch_round_rpc)."""
        ...

    @operation
    def poll_round_rpc(
        self,
        task_handle: str,
        sessions_dir: Optional[str] = None,
    ) -> DshRpcRoundStatus:
        """Polls active round status over the local JSON-RPC bridge.

        POSTCONDITIONS:
        - MUST query round execution status from the central server and return DshRpcRoundStatus.
        """
        ...

    @operation
    def poll_turn_rpc(
        self,
        task_handle: str,
        sessions_dir: Optional[str] = None,
    ) -> DshRpcTurnStatus:
        """Polls active round status over the local JSON-RPC bridge (backwards-compatible alias for poll_round_rpc)."""
        ...

    @operation
    def rename_session(
        self,
        session_id: str,
        title: str,
        sessions_dir: Optional[str] = None,
    ) -> bool:
        """Renames a session on DeepSeek Harness Web bridge.

        POSTCONDITIONS:
        - MUST update the session title to title and return True if successful, or False if unreachable.
        """
        ...

    @operation
    def delete_session(
        self,
        session_id: str,
        sessions_dir: Optional[str] = None,
    ) -> bool:
        """Deletes a session from DeepSeek Harness Web bridge.

        POSTCONDITIONS:
        - MUST delete the session from the server and return True if successful, or False if unreachable.
        """
        ...

    @operation
    def cleanup_scope_sessions(
        self,
        dir_scope: str,
        sessions_dir: Optional[str] = None,
    ) -> int:
        """Discovers and deletes all existing sessions whose title contains [<dir_scope>].

        POSTCONDITIONS:
        - MUST find all sessions with [<dir_scope>] in their title and delete them.
        - MUST return the count of deleted sessions.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-11-09T23:32:00Z
# CHANGE: Add session renaming, deletion, and scope conversation cleanup operations
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
