# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:30:00Z
# CHANGE: Define sandbox_submission interface
# CODE_HASH: 4fa76fb7a570
# --- END CLEANROOM METADATA ---

from __future__ import annotations

from typing import Any, Mapping, NewType, Optional, Protocol

import update_with_ai.parts.agent.lib.agent_file_alias as agent_file_alias
from . import tool_provider

ChangeSummary = NewType("ChangeSummary", str)
FailureExplanation = NewType("FailureExplanation", str)
BlameExplanation = NewType("BlameExplanation", str)


class ResolveTool(tool_provider.Tool, Protocol):
    @property
    def target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        ...

    @property
    def name(self) -> tool_provider.ToolName:
        ...

    @property
    def description(self) -> tool_provider.ToolDescription:
        ...

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


class SubmitTool(ResolveTool, Protocol):
    @property
    def change_summary_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[ChangeSummary], str]:
        ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


class FailTool(ResolveTool, Protocol):
    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[FailureExplanation, str]:
        ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


class BlameTool(ResolveTool, Protocol):
    @property
    def blame_target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        ...

    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[BlameExplanation, str]:
        ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...
