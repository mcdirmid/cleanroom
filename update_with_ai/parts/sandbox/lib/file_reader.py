from __future__ import annotations
from support.lib.lifecycle import Singleton
from typing import Any, Mapping, Optional, Protocol, Set, Union
from update_with_ai.parts.agent.lib.session import AgentSessionTier
import update_with_ai.parts.agent.lib.file_alias as file_alias
from . import tool_provider

# Requirements specified in file_reader.pyi

class ReadManager(Singleton[AgentSessionTier], Protocol):
    # Contract: Exposes declared read-only files from session configuration.
    @property
    def read_only_files(self) -> Set[file_alias.ReadOnlyFile]:
        ...

    # Contract: Exposes declared read-write files from session configuration.
    @property
    def read_write_files(self) -> Set[file_alias.ReadWriteFile]:
        ...

    # Contract: Validates read access; confirms access for declared files, rejects undeclared files with listing.
    def can_read(self, path: Union[file_alias.RelativePath, file_alias.FileAlias]) -> tool_provider.ToolResponse:
        ...


class ViewFileTool(tool_provider.Tool, Singleton[AgentSessionTier], Protocol):
    # Contract: Path parameter identifying file alias to view.
    @property
    def path_parameter(self) -> tool_provider.ToolParameter[file_alias.FileAlias, str]:
        ...

    # Contract: Returns 'view_file'.
    @property
    def name(self) -> tool_provider.ToolName:
        ...

    # Contract: Describes viewing workspace file content with line numbers.
    @property
    def description(self) -> tool_provider.ToolDescription:
        ...

    # Contract: Parameters mapping containing strictly the path parameter.
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        ...

    # Contract: Retrieves and formats file content with line numbers for specified file alias.
    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        ...


class SearchTool(tool_provider.Tool, Singleton[AgentSessionTier], Protocol):
    # Contract: Parameter specifying regex pattern to search.
    @property
    def regex_pattern_parameter(self) -> tool_provider.ToolParameter[file_alias.RegexPattern, str]:
        ...

    # Contract: Returns 'search_files'.
    @property
    def name(self) -> tool_provider.ToolName:
        ...

    # Contract: Describes searching regex patterns across session files.
    @property
    def description(self) -> tool_provider.ToolDescription:
        ...

    # Contract: Parameters mapping containing strictly the regex pattern parameter.
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        ...

    # Contract: Discovers regex pattern matches across read-only and read-write files.
    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-09T02:19:24Z
# CHANGE: Fix sibling and cross-part imports
# --- END CLEANROOM METADATA ---
