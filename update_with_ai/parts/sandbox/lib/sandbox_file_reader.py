# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 1d88ab51c71a
# --- END CLEANROOM METADATA ---

# Requirements specified in sandbox_file_reader.pyi
from typing import Any, Mapping, Protocol, Set, Union
from update_with_ai.parts.agent.lib import agent_file_alias
from . import tool_provider


class ReadManager(Protocol):
    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]: ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]: ...

    def can_read(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse: ...


class ViewFileTool(tool_provider.Tool, Protocol):
    @property
    def path_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]: ...

    @property
    def name(self) -> tool_provider.ToolName: ...

    @property
    def description(self) -> tool_provider.ToolDescription: ...

    @property
    def parameters(
        self,
    ) -> Mapping[
        tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]
    ]: ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse: ...


class SearchTool(tool_provider.Tool, Protocol):
    @property
    def regex_pattern_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.RegexPattern, str]: ...

    @property
    def name(self) -> tool_provider.ToolName: ...

    @property
    def description(self) -> tool_provider.ToolDescription: ...

    @property
    def parameters(
        self,
    ) -> Mapping[
        tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]
    ]: ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse: ...
