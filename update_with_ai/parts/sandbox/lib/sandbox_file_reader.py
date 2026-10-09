# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:19:24Z
# CHANGE: Fix sibling and cross-part imports
# CODE_HASH: 60263e25770a
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Mapping, Optional, Protocol, Set, Union
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier
import update_with_ai.parts.agent.lib.agent_file_alias as agent_file_alias
from . import tool_provider

# Requirements specified in sandbox_file_reader.pyi

class ReadManager(Protocol):
    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        # TODO_read_only_files_body
        ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        # TODO_read_write_files_body
        ...

    def can_read(self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]) -> tool_provider.ToolResponse:
        # TODO_can_read_body
        ...


class ViewFileTool(tool_provider.Tool, Protocol):
    @property
    def path_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        # TODO_path_parameter_body
        ...

    @property
    def name(self) -> tool_provider.ToolName:
        # TODO_name_body
        ...

    @property
    def description(self) -> tool_provider.ToolDescription:
        # TODO_description_body
        ...

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        # TODO_parameters_body
        ...

    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        # TODO_execute_tool_body
        ...


class SearchTool(tool_provider.Tool, Protocol):
    @property
    def regex_pattern_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.RegexPattern, str]:
        # TODO_regex_pattern_parameter_body
        ...

    @property
    def name(self) -> tool_provider.ToolName:
        # TODO_name_body
        ...

    @property
    def description(self) -> tool_provider.ToolDescription:
        # TODO_description_body
        ...

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        # TODO_parameters_body
        ...

    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        # TODO_execute_tool_body
        ...
