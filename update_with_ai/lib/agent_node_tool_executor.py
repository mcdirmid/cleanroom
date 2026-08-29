# lib/agent_node_tool_executor.py
"""
Interface LLS: agent_node_tool_executor
"""
from typing import Any, Dict, List, Protocol
from .tool_provider import ToolCallOutcome, ToolDefinition, PresentedToolResult


class AgentNodeToolExecutor(Protocol):
    def get_tool_definitions(self) -> List[ToolDefinition]:
        ...

    def execute_tool(self, name: str, args: Dict[str, Any]) -> ToolCallOutcome:
        ...

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        ...
