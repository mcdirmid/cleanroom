from typing import Any, Mapping, Protocol, Sequence
from framework import operation, singleton_type
import mcp_session


@singleton_type('system')
class McpServer(Protocol):
    """System service that coordinates tool exposure, session turn scope activation, and hook IPC hosting.

    REQUIREMENTS:
    - Exposes a register role agent tool that accepts a role address, a unit root, and a conversation identifier, registering the subagent session.
    - Exposes a deregister role agent tool that accepts a conversation identifier, deregistering the subagent session.
    - Exposes a shutdown tool that terminates the server and removes the workspace sentinel.
    - Exposes domain tools accepting a conversation identifier, executing incoming tool calls within the active session scope for the caller conversation identifier.
    - Hosts hook validation and directory filter endpoints, producing access decisions and sanitized directory listings.
    - Server startup begins the transport loop and writes the workspace sentinel, updating registered subagents on registration and deregistration, and server termination cleanly closes active sessions, shuts down endpoints, and removes the sentinel.
    """

    @operation
    def register_role_agent(self, conversation_id: mcp_session.ConversationId, role_address: str, unit_root: str) -> str:
        """Registers a role agent session, binding the conversation to the specified role and unit root.

        GROUNDING_PROVISIONS:
        - action("register_subagent_session", str): Registers subagent session binding role and unit.
        """
        ...

    @operation
    def deregister_role_agent(self, conversation_id: mcp_session.ConversationId) -> str:
        """Deregisters a role agent session and releases its held resources.

        GROUNDING_PROVISIONS:
        - action("deregister_subagent_session", str): Deregisters subagent session and releases held resources.
        """
        ...

    @operation
    def next_batch(self, unit_address: str, role_address: str) -> str:
        """Returns the next ready batch of dirty nodes for the given target as a JSON string.

        GROUNDING_PROVISIONS:
        - action("query_ready_batch", str): Queries next ready batch of dirty nodes.
        """
        ...

    @operation
    def execute_domain_tool(self, conversation_id: mcp_session.ConversationId, tool_name: str, arguments: Mapping[str, Any]) -> str:
        """Executes a domain tool within the activated session scope for the caller conversation.

        GROUNDING_PROVISIONS:
        - action("dispatch_domain_tool", str): Executes domain tool within active session scope.
        """
        ...

    @operation
    def handle_validate_access(self, conversation_id: mcp_session.ConversationId, tool_name: str, file_path: str) -> Mapping[str, Any]:
        """Handles hook access validation requests, producing JSON-compatible decision mappings.

        GROUNDING_PROVISIONS:
        - action("validate_hook_access", Mapping[str, Any]): Validates hook access and produces decision mapping.
        """
        ...

    @operation
    def handle_filter_dir(self, conversation_id: mcp_session.ConversationId, directory_path: str, entries: Sequence[str]) -> Sequence[str]:
        """Handles hook directory filter requests, producing sanitized child entries.

        GROUNDING_PROVISIONS:
        - action("filter_hook_directory", Sequence[str]): Filters hook directory listing to preserve role blindness.
        """
        ...

    @operation
    def start(self, transport: str) -> None:
        """Starts the FastMCP server and hook endpoints on the specified transport.

        GROUNDING_PROVISIONS:
        - action("start_server", None): Starts server, writes sentinel, and begins transport loop.
        """
        ...

    @operation
    def stop(self) -> None:
        """Stops the server, canceling background tasks and closing active sessions.

        GROUNDING_PROVISIONS:
        - action("stop_server", None): Stops server, cancels tasks, and removes sentinel.
        """
        ...
