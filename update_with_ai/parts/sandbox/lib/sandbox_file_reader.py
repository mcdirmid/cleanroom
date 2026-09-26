# Requirements specified in sandbox_file_reader.pyi
from typing import Optional, Protocol, Set, Union
from update_with_ai.parts.agent.lib import agent_file_alias
from . import tool_provider


class ReadManager(Protocol):
    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]: ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]: ...

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]: ...

    def can_read(
        self, path: Union[str, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse: ...


class ViewFileTool(tool_provider.Tool, Protocol):
    @property
    def path_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]: ...


class SearchTool(tool_provider.Tool, Protocol):
    @property
    def regex_pattern_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.RegexPattern, tool_provider.WireString]: ...
