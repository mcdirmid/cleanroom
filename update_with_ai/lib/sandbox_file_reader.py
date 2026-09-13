from typing import Optional, Protocol, Set
from . import agent_file_alias
from . import tool_provider

class ReadManager(Protocol):
    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        ...

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        ...

    def requires_line_numbers(self, file: agent_file_alias.FileAlias) -> bool:
        ...

class ReadTool(tool_provider.Tool, Protocol):
    @property
    def file_alias_parameter(self) -> tool_provider.Parameter:
        ...

    @property
    def line_numbers_parameter(self) -> tool_provider.Parameter:
        ...

class SearchTool(tool_provider.Tool, Protocol):
    @property
    def regex_pattern_parameter(self) -> tool_provider.Parameter:
        ...
