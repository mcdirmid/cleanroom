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
    def is_server_available(
        self,
        sessions_dir: Optional[str] = None,
    ) -> bool:
        """Evaluates whether an active DeepSeek Harness Web loopback bridge is reachable.

        GROUNDING:
        - Probes active Web loopback bridge configuration and verifies reachability
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
        dir_scope: Optional[str] = None,
    ) -> Optional[str]:
        """Dispatches a role round over the local JSON-RPC bridge to the central DeepSeek Harness server.

        GROUNDING:
        - Dispatches session/create (using role workspace directory directly without workspaceId), session/rename (setting conversation title to scope and role), session/selectModel (resolving declared model profile names against model configuration definitions discovered in workspace ancestors, user configuration, or repository root and mapping local MLX providers to oMLX endpoints), and session/prompt over the local RPC bridge
          conforming to dsh_ext without registering per-role workspace folders (dsh_telemetry_mechanics). In DeepSeek Harness Web mode, dispatches role rounds as independent top-level sessions with unique task names labeled `[<scope>] <role>` under Ungrouped without container attachment or workspace folder registration, providing direct conversation visibility and manual interactivity without subagent monitor dependencies.
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
        dir_scope: Optional[str] = None,
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
        - Queries session status and event records over the JSON-RPC bridge, marking missing workers completed with error when absent from registry beyond grace period
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

    @operation
    @override
    def rename_session(
        self,
        session_id: str,
        title: str,
        sessions_dir: Optional[str] = None,
    ) -> bool:
        """Renames a session on DeepSeek Harness Web bridge.

        GROUNDING:
        - Invokes dsh_rename_session on Web bridge (dsh_telemetry_mechanics).
        """
        ...

    @operation
    @override
    def delete_session(
        self,
        session_id: str,
        sessions_dir: Optional[str] = None,
    ) -> bool:
        """Deletes a session from DeepSeek Harness Web bridge.

        GROUNDING:
        - Invokes dsh_delete_session on Web bridge (dsh_telemetry_mechanics).
        """
        ...

    @operation
    @override
    def cleanup_scope_sessions(
        self,
        dir_scope: str,
        sessions_dir: Optional[str] = None,
    ) -> int:
        """Discovers and deletes all existing sessions whose title contains [<dir_scope>].

        GROUNDING:
        - Lists sessions via dsh_list_sessions, finds sessions with [<dir_scope>] in their title, and deletes them (dsh_telemetry_mechanics).
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-11-10T01:30:00Z
# CHANGE: Conclude missing RPC workers as errored completion when absent from registry beyond grace period
# SPEC_QA_AUDIT: 2026-10-19T22:33:00Z
# --- END CLEANROOM METADATA ---
