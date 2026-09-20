from typing import Any, Mapping, Protocol, Sequence
from framework import operation, singleton_type
import mcp_session

@singleton_type('system')
class McpServer(Protocol):
    """
PURPOSE:
System service that coordinates tool exposure, session turn scope activation, and hook IPC hosting

FRESH_REQUIREMENTS:
- Exposes register and deregister role agent tools that delegate session bounds to the role session manager.
- Exposes domain tools from the session tool manager, routing incoming tool calls to the active session scope.
- Hosts hook validation and directory filter endpoints, delegating access authorization to the access gate.
- Starting the server begins the transport loop, and stopping cleanly terminates sessions and endpoints.
"""

    @operation
    def register_role_agent(self, conversation_id: mcp_session.ConversationId, role_address: str, unit_root: str) -> str:
        """
PURPOSE:
Registers a role agent session, binding the conversation to the specified role and unit root
"""
        ...

    @operation
    def deregister_role_agent(self, conversation_id: mcp_session.ConversationId) -> str:
        """
PURPOSE:
Deregisters a role agent session and releases its held resources
"""
        ...

    @operation
    def execute_domain_tool(self, conversation_id: mcp_session.ConversationId, tool_name: str, arguments: Mapping[str, Any]) -> str:
        """
PURPOSE:
Executes a domain tool within the activated session scope for the caller conversation
"""
        ...

    @operation
    def handle_validate_access(self, conversation_id: mcp_session.ConversationId, tool_name: str, file_path: str) -> Mapping[str, Any]:
        """
PURPOSE:
Handles hook access validation requests, producing JSON-compatible decision mappings
"""
        ...

    @operation
    def handle_filter_dir(self, conversation_id: mcp_session.ConversationId, directory_path: str, entries: Sequence[str]) -> Sequence[str]:
        """
PURPOSE:
Handles hook directory filter requests, producing sanitized child entries
"""
        ...

    @operation
    def start(self, transport: str) -> None:
        """
PURPOSE:
Starts the FastMCP server and hook endpoints on the specified transport
"""
        ...

    @operation
    def stop(self) -> None:
        """
PURPOSE:
Stops the server, canceling background tasks and closing active sessions
"""
        ...
