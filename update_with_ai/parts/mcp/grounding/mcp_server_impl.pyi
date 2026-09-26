from typing import Any, Mapping, Self, Sequence
from framework import operation, override, singleton_type
import dag_storage
import dag_subgraph
import fastmcp_ext
import mcp_cache_arbiter
import mcp_gate
import mcp_server
import mcp_session
import tool_provider


@singleton_type('system')
class McpServer(mcp_server.McpServer):
    """Implements FastMCP server to host tool registrations, session scope activation, and hook HTTP routes.

    GROUNDING_ARGUMENT:
    - As a system singleton, McpServer hosts a FastMCP application instance via imported fastmcp_ext, delegates session management to imported mcp_session.RoleSessionManager, activates scopes to execute tools in imported tool_provider.ToolManager, delegates hook requests to imported mcp_gate.AccessGate, and evaluates sampling via imported mcp_cache_arbiter.CacheArbiter.
    """

    @operation
    @override
    def register_role_agent(self, conversation_id: mcp_session.ConversationId, role_address: str, unit_root: str) -> str:
        """Registers a role agent session, binding the conversation to the specified role and unit root.

        GROUNDING_PROVISIONS:
        - action("register_subagent_session", str): Registers role agent session.

        GROUNDING_ARGUMENT:
        - action("register_subagent_session", Self) :- action("register_session", mcp_session.RoleSessionManager), knows("active_tools", tool_provider.ToolManager).
        """
        ...

    @operation
    @override
    def deregister_role_agent(self, conversation_id: mcp_session.ConversationId) -> str:
        """Deregisters a role agent session and releases its held resources.

        GROUNDING_PROVISIONS:
        - action("deregister_subagent_session", str): Deregisters role agent session.

        GROUNDING_ARGUMENT:
        - action("deregister_subagent_session", Self) :- action("deregister_session", mcp_session.RoleSessionManager).
        """
        ...

    @operation
    @override
    def next_batch(self, unit_address: str, role_address: str) -> str:
        """Returns the next ready batch of dirty nodes for the given target as a JSON string.

        REQUIREMENTS:
        - The next batch tool accepts a target unit address and a target role address, sets the target root node on the DAG subgraph using in-process system singletons without creating child registries, queries the DAG subgraph to determine the next ready batch of dirty nodes, and returns a JSON string with the unit, role, is_complete flag, ready_role, batch list, and dirty_nodes list.

        GROUNDING_PROVISIONS:
        - action("query_ready_batch", str): Determines next ready batch of dirty nodes.

        GROUNDING_ARGUMENT:
        - action("query_ready_batch", Self) :- action("set_target", dag_subgraph.DagSubgraph), action("next_ready_batch", dag_subgraph.DagSubgraph).
        """
        ...

    @operation
    @override
    def execute_domain_tool(self, conversation_id: mcp_session.ConversationId, tool_name: str, arguments: Mapping[str, Any]) -> str:
        """Executes a domain tool within the activated session scope for the caller conversation.

        GROUNDING_PROVISIONS:
        - action("dispatch_domain_tool", str): Executes domain tool in session scope.

        GROUNDING_ARGUMENT:
        - action("dispatch_domain_tool", Self) :- action("get_session_scope", mcp_session.RoleSessionManager), action("execute_tool_with_arguments", tool_provider.ToolManager), action("register_dependent", dag_storage.DagStorage), action("clear_messages", dag_storage.DagStorage), action("add_message", dag_storage.DagStorage), action("record_visit", dag_subgraph.DagSubgraph).
        """
        ...

    @operation
    @override
    def handle_validate_access(self, conversation_id: mcp_session.ConversationId, tool_name: str, file_path: str) -> Mapping[str, Any]:
        """Handles hook access validation requests, producing JSON-compatible decision mappings.

        GROUNDING_PROVISIONS:
        - action("validate_hook_access", Mapping[str, Any]): Validates hook access.

        GROUNDING_ARGUMENT:
        - action("validate_hook_access", Self) :- action("validate_file_access", mcp_gate.AccessGate).
        """
        ...

    @operation
    @override
    def handle_filter_dir(self, conversation_id: mcp_session.ConversationId, directory_path: str, entries: Sequence[str]) -> Sequence[str]:
        """Handles hook directory filter requests, producing sanitized child entries.

        GROUNDING_PROVISIONS:
        - action("filter_hook_directory", Sequence[str]): Filters directory child entries.

        GROUNDING_ARGUMENT:
        - action("filter_hook_directory", Self) :- action("sanitize_directory_entries", mcp_gate.AccessGate).
        """
        ...

    @operation
    @override
    def start(self, transport: str) -> None:
        """Starts the FastMCP server and hook endpoints on the specified transport.

        GROUNDING_PROVISIONS:
        - action("start_server", None): Starts server on transport.

        GROUNDING_ARGUMENT:
        - action("start_server", Self) :- action("write_sentinel", Self), action("register_http_routes", fastmcp_ext), action("evaluate_all_idle_sessions", mcp_cache_arbiter.CacheArbiter).
        """
        ...

    @operation
    @override
    def stop(self) -> None:
        """Stops the server, canceling background tasks and closing active sessions.

        GROUNDING_PROVISIONS:
        - action("stop_server", None): Stops server.

        GROUNDING_ARGUMENT:
        - action("stop_server", Self) :- action("remove_sentinel", Self), action("deregister_session", mcp_session.RoleSessionManager).
        """
        ...
