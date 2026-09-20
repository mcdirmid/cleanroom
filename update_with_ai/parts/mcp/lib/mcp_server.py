from __future__ import annotations
from typing import Any, Mapping, Protocol, Sequence
from . import mcp_session

# Requirements specified in mcp_server.pyi

class McpServer(Protocol):
    def register_role_agent(
        self,
        conversation_id: mcp_session.ConversationId,
        role_address: str,
        unit_root: str,
    ) -> str:
        ...

    def deregister_role_agent(
        self, conversation_id: mcp_session.ConversationId
    ) -> str:
        ...

    def execute_domain_tool(
        self,
        conversation_id: mcp_session.ConversationId,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> str:
        ...

    def handle_validate_access(
        self,
        conversation_id: mcp_session.ConversationId,
        tool_name: str,
        file_path: str,
    ) -> Mapping[str, Any]:
        ...

    def handle_filter_dir(
        self,
        conversation_id: mcp_session.ConversationId,
        directory_path: str,
        entries: Sequence[str],
    ) -> Sequence[str]:
        ...

    def start(self, transport: str) -> None:
        ...

    def stop(self) -> None:
        ...
