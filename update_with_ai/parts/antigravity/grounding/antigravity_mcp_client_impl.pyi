from framework import operation, override, singleton_type
from typing import Any, Mapping, Self
import antigravity_mcp_client

@singleton_type('system')
class AntigravityMcpClient(antigravity_mcp_client.AntigravityMcpClient):
    """Realizes HTTP client communication with the Cleanroom Model Context Protocol server.

    GROUNDING_ARGUMENT:
    - System singleton dispatching JSON tool invocations over HTTP transport to FastMCP server ports.
    """

    @operation
    @override
    def call_tool(self, name: str, arguments: Mapping[str, Any], port: int=8765) -> str:
        """
        REQUIREMENTS:
        - Calling a tool connects to the server at the configured host and port, transmitting a JSON-encoded request specifying tool name and arguments.
        - When the server responds with a success status, the client extracts and returns the content text.
        - When communication fails or the server returns an error, the client returns an error diagnostic string.

        GROUNDING_IMPLEMENTS:
        - action("transmit_tool_call", str): Calls tool on server.
        """
        ...

    @operation
    @override
    def register_session(self, identifier: str, role: str, unit: str, port: int=8765) -> str:
        """
        REQUIREMENTS:
        - Registering a session dispatches the server registration tool binding session identifier, role, and unit.

        GROUNDING_PROVISIONS:
        - action("register_session", str): Registers session.

        GROUNDING_ARGUMENT:
        - action("register_session", Self) :- action("transmit_tool_call", Self).
        """
        ...

    @operation
    @override
    def deregister_session(self, identifier: str, port: int=8765) -> str:
        """
        REQUIREMENTS:
        - Deregistering a session notifies the server to release resources associated with the session.

        GROUNDING_PROVISIONS:
        - action("terminate_session", str): Deregisters session.

        GROUNDING_ARGUMENT:
        - action("terminate_session", Self) :- action("transmit_tool_call", Self).
        """
        ...

    @operation
    @override
    def get_work(self, identifier: str, port: int=8765) -> str:
        """
        REQUIREMENTS:
        - Retrieving work invokes the domain get work tool within the session scope, returning task descriptions and incoming change notifications.

        GROUNDING_PROVISIONS:
        - action("retrieve_work_instructions", str): Retrieves work instructions.

        GROUNDING_ARGUMENT:
        - action("retrieve_work_instructions", Self) :- action("transmit_tool_call", Self).
        """
        ...

    @operation
    @override
    def check_files(self, identifier: str, port: int=8765) -> str:
        """
        REQUIREMENTS:
        - Running check files executes batch verification across all files assigned to the session.

        GROUNDING_PROVISIONS:
        - action("run_batch_verification", str): Runs check files.

        GROUNDING_ARGUMENT:
        - action("run_batch_verification", Self) :- action("transmit_tool_call", Self).
        """
        ...

    @operation
    @override
    def submit(self, identifier: str, target: str, summary: str, port: int=8765) -> str:
        """
        REQUIREMENTS:
        - Submitting commits modifications for an open target with the provided change summary.

        GROUNDING_PROVISIONS:
        - action("commit_target_changes", str): Submits target modifications.

        GROUNDING_ARGUMENT:
        - action("commit_target_changes", Self) :- action("transmit_tool_call", Self).
        """
        ...

    @operation
    @override
    def blame(self, identifier: str, target: str, blame_target: str, explanation: str, port: int=8765) -> str:
        """
        REQUIREMENTS:
        - Recording blame flags an upstream defect with an explanation.

        GROUNDING_PROVISIONS:
        - action("report_contract_defect", str): Reports contract defects to blame target.

        GROUNDING_ARGUMENT:
        - action("report_contract_defect", Self) :- action("transmit_tool_call", Self).
        """
        ...

    @operation
    @override
    def shutdown(self, port: int=8765) -> str:
        """
        REQUIREMENTS:
        - Shutting down sends the server shutdown command.

        GROUNDING_PROVISIONS:
        - action("stop_server", str): Stops server.

        GROUNDING_ARGUMENT:
        - action("stop_server", Self) :- action("transmit_tool_call", Self).
        """
        ...

    @operation
    @override
    def next_batch(self, unit: str, port: int=8765) -> str:
        """
        REQUIREMENTS:
        - Querying the next batch executes the server wave resolution tool for the resolved target unit.

        GROUNDING_PROVISIONS:
        - action("query_next_ready_wave", str): Queries next ready wave.

        GROUNDING_ARGUMENT:
        - action("query_next_ready_wave", Self) :- action("transmit_tool_call", Self).
        """
        ...
