from typing import Any, Mapping, Protocol, Sequence
from framework import operation, singleton_type
import mcp_session

@singleton_type('system')
class McpServer(Protocol):
    """
PURPOSE:
System service that coordinates tool exposure, session turn scope activation, and hook IPC hosting

FRESH_REQUIREMENTS:
- Exposes a register role agent tool that accepts a role address, a unit root, and a conversation identifier, registering the subagent session.
- Exposes a deregister role agent tool that accepts a conversation identifier, deregistering the subagent session.
- Exposes a shutdown tool that terminates the server and removes the workspace sentinel.
- Exposes domain tools accepting a conversation identifier, executing incoming tool calls within the active session scope for the caller conversation identifier.
- Hosts hook validation and directory filter endpoints, producing access decisions and sanitized directory listings.
- Server startup begins the transport loop and writes the workspace sentinel, updating registered subagents on registration and deregistration, and server termination cleanly closes active sessions, shuts down endpoints, and removes the sentinel.
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
    def next_batch(self, unit_address: str, role_address: str) -> str:
        """
PURPOSE:
Returns the next ready batch of dirty nodes for the given target as a JSON string
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
