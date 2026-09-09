from typing import Protocol, Set
from . import file_alias
from . import tool_provider

class Template(file_alias.FileContent):
    pass

class EditingTool(tool_provider.Tool, Protocol):
    pass

class EditManager(Protocol):
    @property
    def has_modifications(self) -> bool:
        ...

    def materialize_templates(self) -> None:
        ...

class TextReplacementTool(EditingTool, Protocol):
    @property
    def file_alias_parameter(self) -> tool_provider.Parameter:
        ...

    @property
    def target_text_parameter(self) -> tool_provider.Parameter:
        ...

    @property
    def replacement_text_parameter(self) -> tool_provider.Parameter:
        ...

class LineUpdateTool(EditingTool, Protocol):
    @property
    def file_alias_parameter(self) -> tool_provider.Parameter:
        ...

    @property
    def start_line_parameter(self) -> tool_provider.Parameter:
        ...

    @property
    def end_line_parameter(self) -> tool_provider.Parameter:
        ...

    @property
    def replacement_text_parameter(self) -> tool_provider.Parameter:
        ...
