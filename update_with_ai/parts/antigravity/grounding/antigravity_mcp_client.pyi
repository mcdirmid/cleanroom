from framework import operation, singleton_type
from typing import Any, Mapping

@singleton_type('system')
class AntigravityMcpClient:
    """
PURPOSE:
System service that executes operations against an active Model Context Protocol server.
"""

    @operation
    def call_tool(self, name: str, arguments: Mapping[str, Any], port: int=8765) -> str:
        """
PURPOSE:
Dispatches a tool name with an arguments mapping to a server port.

FRESH_REQUIREMENTS:
- The antigravity mcp client dispatches a tool name with an arguments mapping to a server port.
"""
        ...

    @operation
    def register_session(self, identifier: str, role: str, unit: str, port: int=8765) -> str:
        """
PURPOSE:
Establishes a session identifier with an assigned role and unit root.

FRESH_REQUIREMENTS:
- The antigravity mcp client establishes a session identifier with an assigned role and unit root.
"""
        ...

    @operation
    def deregister_session(self, identifier: str, port: int=8765) -> str:
        """
PURPOSE:
Terminates a session identifier on the server.

FRESH_REQUIREMENTS:
- The antigravity mcp client terminates a session identifier on the server.
"""
        ...

    @operation
    def get_work(self, identifier: str, port: int=8765) -> str:
        """
PURPOSE:
Retrieves task instructions and incoming changes for a session identifier.

FRESH_REQUIREMENTS:
- The antigravity mcp client retrieves task instructions and incoming changes for a session identifier.
"""
        ...

    @operation
    def check_files(self, identifier: str, port: int=8765) -> str:
        """
PURPOSE:
Runs batch verification tests for a session identifier.

FRESH_REQUIREMENTS:
- The antigravity mcp client runs batch verification tests for a session identifier.
"""
        ...

    @operation
    def submit(self, identifier: str, target: str, summary: str, port: int=8765) -> str:
        """
PURPOSE:
Commits changes for an open target with a change summary.

FRESH_REQUIREMENTS:
- The antigravity mcp client commits changes for an open target with a change summary.
"""
        ...

    @operation
    def blame(self, identifier: str, target: str, blame_target: str, explanation: str, port: int=8765) -> str:
        """
PURPOSE:
Reports contract defects to a blame target with an explanation.

FRESH_REQUIREMENTS:
- The antigravity mcp client reports contract defects to a blame target with an explanation.
"""
        ...

    @operation
    def shutdown(self, port: int=8765) -> str:
        """
PURPOSE:
Stops the server on the server port.

FRESH_REQUIREMENTS:
- The antigravity mcp client stops the server on the server port.
"""
        ...

    @operation
    def next_batch(self, unit: str, port: int=8765) -> str:
        """
PURPOSE:
Queries the next ready wave for a target unit.

FRESH_REQUIREMENTS:
- The antigravity mcp client queries the next ready wave for a target unit.
"""
        ...
