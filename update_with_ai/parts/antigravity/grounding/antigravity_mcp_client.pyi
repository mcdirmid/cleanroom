from framework import operation, singleton_type
from typing import Any, Mapping

@singleton_type('system')
class AntigravityMcpClient:
    """System service that executes operations against an active Model Context Protocol server.

    REQUIREMENTS:
    - The antigravity mcp client dispatches a tool name with an arguments mapping to a server port.
    - The antigravity mcp client establishes a session identifier with an assigned role and unit root.
    - The antigravity mcp client terminates a session identifier on the server.
    - The antigravity mcp client retrieves task instructions and incoming changes for a session identifier.
    - The antigravity mcp client runs batch verification tests for a session identifier.
    - The antigravity mcp client commits changes for an open target with a change summary.
    - The antigravity mcp client reports contract defects to a blame target with an explanation.
    - The antigravity mcp client stops the server on the server port.
    - The antigravity mcp client queries the next ready wave for a target unit.

    GROUNDING_PROVISIONS:
    - action("transmit_tool_call", str): Dispatches tool invocation request to server.
    - action("register_session", str): Establishes session with assigned role and unit.
    - action("terminate_session", str): Terminates active session on server.
    - action("retrieve_work_instructions", str): Retrieves task instructions and incoming changes.
    - action("run_batch_verification", str): Runs batch verification tests for session.
    - action("commit_target_changes", str): Commits target modifications with change summary.
    - action("report_contract_defect", str): Reports defect to blame target with explanation.
    - action("stop_server", str): Stops server on specified port.
    - action("query_next_ready_wave", str): Queries next ready wave for target unit.
    """

    @operation
    def call_tool(self, name: str, arguments: Mapping[str, Any], port: int=8765) -> str:
        ...

    @operation
    def register_session(self, identifier: str, role: str, unit: str, port: int=8765) -> str:
        ...

    @operation
    def deregister_session(self, identifier: str, port: int=8765) -> str:
        ...

    @operation
    def get_work(self, identifier: str, port: int=8765) -> str:
        ...

    @operation
    def check_files(self, identifier: str, port: int=8765) -> str:
        ...

    @operation
    def submit(self, identifier: str, target: str, summary: str, port: int=8765) -> str:
        ...

    @operation
    def blame(self, identifier: str, target: str, blame_target: str, explanation: str, port: int=8765) -> str:
        ...

    @operation
    def shutdown(self, port: int=8765) -> str:
        ...

    @operation
    def next_batch(self, unit: str, port: int=8765) -> str:
        ...
