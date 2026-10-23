from __future__ import annotations
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton

from typing import Any, Mapping, NewType, Optional, Protocol

import update_with_ai.parts.agent.lib.file_alias as file_alias
from . import tool_provider

ChangeSummary = NewType("ChangeSummary", str)
FailureExplanation = NewType("FailureExplanation", str)
BlameExplanation = NewType("BlameExplanation", str)


# Contract: ResolveTool protocol - polymorphic tool that resolves an active node.
class ResolveTool(tool_provider.Tool, Protocol):
    # Contract: ResolveTool.target_parameter - parameter identifying the active node being resolved.
    @property
    def target_parameter(
        self,
    ) -> tool_provider.ToolParameter[file_alias.FileAlias, str]:
        ...

    # Contract: Tool.name
    @property
    def name(self) -> tool_provider.ToolName:
        ...

    # Contract: Tool.description
    @property
    def description(self) -> tool_provider.ToolDescription:
        ...

    # Contract: Tool.parameters
    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        ...

    # Contract: ResolveTool.execute_tool - executes node resolution action.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


# Contract: SubmitTool protocol - marks an active node complete upon passing verification and documenting changes.
class SubmitTool(ResolveTool, Singleton[AgentSessionTier], Protocol):
    # Contract: SubmitTool.change_summary_parameter - parameter describing modifications made during the task.
    @property
    def change_summary_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[ChangeSummary], str]:
        ...

    # Contract: SubmitTool.execute_tool - submits an active node as cleanly finished when verification passes and change documentation is valid.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


# Contract: FailTool protocol - terminates session execution in failure.
class FailTool(ResolveTool, Singleton[AgentSessionTier], Protocol):
    # Contract: FailTool.explanation_parameter - parameter explaining the reason for failure.
    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[FailureExplanation, str]:
        ...

    # Contract: FailTool.execute_tool - fails the active node and terminates run in failure.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


# Contract: BlameTool protocol - attributes failure to an upstream prerequisite.
class BlameTool(ResolveTool, Singleton[AgentSessionTier], Protocol):
    # Contract: BlameTool.blame_target_parameter - parameter identifying the blamed upstream dependency.
    @property
    def blame_target_parameter(
        self,
    ) -> tool_provider.ToolParameter[file_alias.FileAlias, str]:
        ...

    # Contract: BlameTool.explanation_parameter - parameter explaining the defect in the upstream dependency.
    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[BlameExplanation, str]:
        ...

    # Contract: BlameTool.execute_tool - attributes failure to an upstream dependency node.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:30:00Z
# CHANGE: Define submission interface
# --- END CLEANROOM METADATA ---
