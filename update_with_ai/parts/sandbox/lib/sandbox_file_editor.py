from typing import Protocol, Set
from update_with_ai.parts.agent.lib import agent_file_alias
from . import tool_provider


class Template(agent_file_alias.FileContent):
    pass


class EditingTool(tool_provider.Tool, Protocol):
    pass


class EditManager(Protocol):
    @property
    def has_modifications(self) -> bool: ...

    @property
    def file_update_revision(self) -> int: ...

    @property
    def locked_files(self) -> Set[agent_file_alias.ReadWriteFile]: ...

    def lock_file(self, file: agent_file_alias.ReadWriteFile) -> None: ...

    def unlock_file(self, file: agent_file_alias.ReadWriteFile) -> None: ...

    def materialize_templates(self) -> None: ...


class ReplaceFileContentTool(EditingTool, Protocol):
    @property
    def file_alias_parameter(self) -> tool_provider.Parameter: ...

    @property
    def target_content_parameter(self) -> tool_provider.Parameter: ...

    @property
    def replacement_content_parameter(self) -> tool_provider.Parameter: ...

    @property
    def start_line_parameter(self) -> tool_provider.Parameter: ...

    @property
    def end_line_parameter(self) -> tool_provider.Parameter: ...

    @property
    def allow_multiple_parameter(self) -> tool_provider.Parameter: ...

