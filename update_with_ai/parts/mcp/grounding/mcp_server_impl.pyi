from typing import Any, Mapping, Sequence
from framework import operation, override, singleton_type
import fastmcp_ext
import mcp_cache_arbiter
import mcp_gate
import mcp_server
import mcp_session
import tool_provider

@singleton_type('system')
class McpServer(mcp_server.McpServer):
    """
PURPOSE:
Implements FastMCP server to host tool registrations, session scope activation, and hook HTTP routes

INHERITED_REQUIREMENTS:
- [McpServer] Exposes register and deregister role agent tools that delegate session bounds to the role session manager.
- [McpServer] Exposes domain tools from the session tool manager, routing incoming tool calls to the active session scope.
- [McpServer] Hosts hook validation and directory filter endpoints, delegating access authorization to the access gate.
- [McpServer] Starting the server begins the transport loop, and stopping cleanly terminates sessions and endpoints.

GROUNDING_ARGUMENT:
- As a system singleton, McpServer hosts a FastMCP application instance via imported fastmcp_ext, delegates session management to imported mcp_session.RoleSessionManager, activates scopes to execute tools in imported tool_provider.ToolManager, delegates hook requests to imported mcp_gate.AccessGate, and evaluates sampling via imported mcp_cache_arbiter.CacheArbiter.
"""

    @operation
    @override
    def register_role_agent(self, conversation_id: mcp_session.ConversationId, role_address: str, unit_root: str) -> str:
        """
PURPOSE:
Registers a role agent session, binding the conversation to the specified role and unit root

GROUNDING_ARGUMENT:
- Delegates directly to imported mcp_session.RoleSessionManager.register_session with conversation_id, role_address, and unit_root, returning a confirmation message.
"""
        ...

    @operation
    @override
    def deregister_role_agent(self, conversation_id: mcp_session.ConversationId) -> str:
        """
PURPOSE:
Deregisters a role agent session and releases its held resources

GROUNDING_ARGUMENT:
- Delegates directly to imported mcp_session.RoleSessionManager.deregister_session with conversation_id, returning a confirmation message.
"""
        ...

    @operation
    @override
    def execute_domain_tool(self, conversation_id: mcp_session.ConversationId, tool_name: str, arguments: Mapping[str, Any]) -> str:
        """
PURPOSE:
Executes a domain tool within the activated session scope for the caller conversation

GROUNDING_ARGUMENT:
- Touches session in imported mcp_session.RoleSessionManager, resolves session scope, activates scope using scope.activate(), dispatches tool_name and arguments to imported tool_provider.ToolManager.execute_tool_with_arguments, updates session status to Idle if response is idle, and returns response content.
"""
        ...

    @operation
    @override
    def handle_validate_access(self, conversation_id: mcp_session.ConversationId, tool_name: str, file_path: str) -> Mapping[str, Any]:
        """
PURPOSE:
Handles hook access validation requests, producing JSON-compatible decision mappings

GROUNDING_ARGUMENT:
- Delegates directly to imported mcp_gate.AccessGate.validate_access, serializing the AccessDecision to a dictionary mapping.
"""
        ...

    @operation
    @override
    def handle_filter_dir(self, conversation_id: mcp_session.ConversationId, directory_path: str, entries: Sequence[str]) -> Sequence[str]:
        """
PURPOSE:
Handles hook directory filter requests, producing sanitized child entries

GROUNDING_ARGUMENT:
- Delegates directly to imported mcp_gate.AccessGate.filter_directory_listing with conversation_id, directory_path, and entries.
"""
        ...

    @operation
    @override
    def start(self, transport: str) -> None:
        """
PURPOSE:
Starts the FastMCP server and hook endpoints on the specified transport

GROUNDING_ARGUMENT:
- Initializes the FastMCP application, registers tools and HTTP endpoints via imported fastmcp_ext, spawns background cache arbiter evaluation task via imported mcp_cache_arbiter.CacheArbiter, and begins the transport loop.
"""
        ...

    @operation
    @override
    def stop(self) -> None:
        """
PURPOSE:
Stops the server, canceling background tasks and closing active sessions

GROUNDING_ARGUMENT:
- Cancels background evaluation tasks, shuts down the transport loop, and iterates over active sessions in imported mcp_session.RoleSessionManager to deregister and close each.
"""
        ...
