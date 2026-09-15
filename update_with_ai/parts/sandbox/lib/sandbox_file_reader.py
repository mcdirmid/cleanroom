from typing import Optional, Protocol, Set
from update_with_ai.parts.agent.lib import agent_file_alias
from . import tool_provider


class ReadManager(Protocol):
    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]: ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]: ...

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]: ...


class ViewFileTool(tool_provider.Tool, Protocol):
    @property
    def path_parameter(self) -> tool_provider.Parameter: ...


class SearchTool(tool_provider.Tool, Protocol):
    @property
    def regex_pattern_parameter(self) -> tool_provider.Parameter: ...
