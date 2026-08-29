# lib/agent_node_tool_executor_impl.py
"""
Implementation LLS: agent_node_tool_executor_impl
"""
from typing import Any, Dict, List
from .agent_node_tool_executor import AgentNodeToolExecutor
from .sandbox import Sandbox
from .tool_provider import (
    PresentedToolResult,
    ToolCallOutcome,
    ToolDefinition,
    ToolFailure,
)


class AgentNodeToolExecutorImpl(AgentNodeToolExecutor):
    """
    Adapts a Sandbox instance for AgentLoop ToolExecutor protocol.
    """

    def __init__(self, sandbox: Sandbox) -> None:
        self.sandbox = sandbox

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return self.sandbox.get_tool_definitions()

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        return self.sandbox.get_session_start_reads()

    def execute_tool(self, name: str, args: Dict[str, Any]) -> ToolCallOutcome:
        if name == "read_file":
            path = args.get("path", "")
            line_numbers = args.get("line_numbers", True)
            return self.sandbox.read_file(path, line_numbers=line_numbers)
        elif name == "read_symbol":
            path = args.get("path", "")
            symbol = args.get("symbol", "")
            return self.sandbox.read_symbol(path, symbol)
        elif name == "search_files":
            query = args.get("query", "")
            return self.sandbox.search_files(query)
        elif name == "replace":
            path = args.get("path", "")
            old = args.get("old", "")
            new = args.get("new", "")
            expect_multiple = args.get("expect_multiple", False)
            return self.sandbox.replace_lines(path, old, new, expect_multiple=expect_multiple)
        elif name == "update_lines":
            path = args.get("path", "")
            start = args.get("start", 1)
            end = args.get("end", 1)
            new = args.get("new", "")
            return self.sandbox.update_lines(path, start, end, new)
        elif name == "advance":
            changes = args.get("changes", [])
            return self.sandbox.advance(changes=changes)
        elif name == "fail":
            reason = args.get("reason", "")
            return self.sandbox.fail(reason=reason)
        elif name == "blame":
            targets = args.get("targets", [])
            return self.sandbox.blame(targets=targets)
        return ToolFailure[str](f"Unknown tool: {name}")
