"""Low-level implementation specification for dsh_telemetry_impl."""

from typing import Optional
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import session as agent_session
import dsh_ext
import dsh_telemetry


@singleton_type("agent_session")
class DshTelemetryParser(dsh_telemetry.DshTelemetryParser):
    """Realizes session storage archive and event stream parsing for DeepSeek Harness.

    GROUNDING:
    - Realizes dsh_telemetry.DshTelemetryParser within agent_session.AgentSessionTier by
      querying session.v4.jsonl.zstd archives or parsing stdout stream events, aggregating
      uncached, cached, and completion tokens, falling back to text logs when structured
      records are absent, applying model pricing rate cards, and synchronizing desktop
      sessions (dsh_telemetry_mechanics).
    """

    @operation
    @override
    def parse_session_storage(
        self,
        sessions_dir: str,
        workspace_dir: str,
        model_name: Optional[str] = None,
    ) -> dsh_telemetry.DshSessionTokenMetrics:
        """Queries session storage archives and returns token metrics.

        GROUNDING:
        - Locates session directories under sessions_dir matching workspace_dir slug,
          decompresses session.v4.jsonl.zstd (or reads uncompressed session.v4.jsonl when present), aggregates token usage, and computes cost_usd
          (dsh_telemetry_mechanics).
        """
        ...

    @operation
    @override
    def parse_stream_text(
        self,
        stream_text: str,
        model_name: Optional[str] = None,
    ) -> dsh_telemetry.DshSessionTokenMetrics:
        """Parses stdout JSON event streams or log text for token metrics.

        GROUNDING:
        - Extracts token metrics from JSON run events or stdout strings and computes cost_usd
          (dsh_telemetry_mechanics).
        """
        ...

    @operation
    @override
    def sync_desktop_session(
        self,
        sessions_dir: Optional[str],
        workspace_dir: str,
        role_name: str,
        dir_scope: str,
        start_time: float,
    ) -> None:
        """Synchronizes active session records with the DeepSeek Harness Desktop application.

        GROUNDING:
        - Updates desktop workspace.json and session projcache records and dispatches RPC
          notifications to running Desktop processes (dsh_telemetry_mechanics).
        """
        ...

    @operation
    @override
    def is_desktop_server_available(
        self,
        sessions_dir: Optional[str] = None,
    ) -> bool:
        """Evaluates whether an active DeepSeek Harness Desktop application or background server is reachable.

        GROUNDING:
        - Probes application cookie storage and verifies reachability over the local RPC bridge
          (dsh_telemetry_mechanics).
        """
        ...

    @operation
    @override
    def dispatch_round_rpc(
        self,
        workspace_dir: str,
        role_name: str,
        prompt_text: str,
        session_id: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Optional[str]:
        """Dispatches a role round over the local JSON-RPC bridge to the central DeepSeek Harness server.

        GROUNDING:
        - Dispatches workspace/create, session/create, session/selectModel (resolving declared model profile names against model configuration definitions discovered in workspace ancestors, user configuration, or repository root and mapping local MLX providers to oMLX endpoints), and session/prompt over the local RPC bridge
          conforming to dsh_ext (dsh_telemetry_mechanics).
        """
        ...

    @operation
    @override
    def dispatch_turn_rpc(
        self,
        workspace_dir: str,
        role_name: str,
        prompt_text: str,
        session_id: Optional[str] = None,
        sessions_dir: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Optional[str]:
        """Dispatches a role round over the local JSON-RPC bridge (backwards-compatible alias for dispatch_round_rpc)."""
        ...

    @operation
    @override
    def poll_round_rpc(
        self,
        task_handle: str,
        sessions_dir: Optional[str] = None,
    ) -> dsh_telemetry.DshRpcRoundStatus:
        """Polls active round status over the local JSON-RPC bridge.

        GROUNDING:
        - Queries session status and event records over the JSON-RPC bridge
          (dsh_telemetry_mechanics).
        """
        ...

    @operation
    @override
    def poll_turn_rpc(
        self,
        task_handle: str,
        sessions_dir: Optional[str] = None,
    ) -> dsh_telemetry.DshRpcTurnStatus:
        """Polls active round status over the local JSON-RPC bridge (backwards-compatible alias for poll_round_rpc)."""
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-19T22:33:00Z
# CHANGE: specify model profile resolution and MLX to oMLX mapping in RPC turn dispatch
# SPEC_QA_AUDIT: 2026-10-19T22:33:00Z
# --- END CLEANROOM METADATA ---
