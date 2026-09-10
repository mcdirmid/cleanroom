from typing import Protocol, Set
from framework import data_type, operation, override, poly_type, singleton_type
import file_alias
import tool_provider

@data_type
class Template(file_alias.FileContent):
    """
PURPOSE:
Introduces template as initial file content for a read-write file
"""
    ...

@poly_type
class EditingTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as a polymorphic agent session service that modifies a read-write file

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executing an editing tool with a file alias that is not a read-write file fails

FRESH_REQUIREMENTS:
- Executing an editing tool with a file alias that is not a read-write file fails.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.
"""
        ...

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Established that each tool has a name which the agent uses to execute the tool
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation
"""
        ...

@singleton_type('agent_session')
class EditManager(Protocol):
    """
PURPOSE:
Defined as an agent session service that installs editing tools and tracks session modifications

FRESH_REQUIREMENTS:
- The edit manager installs the text replacement tool and line update tool.
- Modifying a file records that workspace file modifications occurred during the session.
"""

    @property
    def has_modifications(self) -> bool:
        """
PURPOSE:
Exposes whether workspace file modifications occurred during the session

FRESH_REQUIREMENTS:
- The edit manager exposes whether workspace file modifications occurred during the session, determined by whether workspace file contents differ from their initial state prior to editing.
"""
        ...

    @property
    def file_update_revision(self) -> int:
        """
PURPOSE:
Exposes a file update revision that tracks sequential updates made to workspace files

FRESH_REQUIREMENTS:
- The edit manager exposes a file update revision that tracks sequential updates made to workspace files.
"""
        ...

    @operation
    def materialize_templates(self) -> None:
        """
PURPOSE:
Materializes templates into missing read-write files at session start without overwriting existing files

FRESH_REQUIREMENTS:
- Materializing templates populates missing read-write files with initial template content without overwriting existing files.
"""
        ...

@singleton_type('agent_session')
class TextReplacementTool(EditingTool, Protocol):
    """
PURPOSE:
Defined as an editing tool that replaces unique matching text in a read-write file

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    def file_alias_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the target read-write file
"""
        ...

    @property
    def target_text_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the exact text to replace
"""
        ...

    @property
    def replacement_text_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the replacement content
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executing an editing tool with a file alias that is not a read-write file fails

INHERITED_REQUIREMENTS:
- [EditingTool] Executing an editing tool with a file alias that is not a read-write file fails.
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.
"""
        ...

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Established that each tool has a name which the agent uses to execute the tool
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation
"""
        ...

@singleton_type('agent_session')
class LineUpdateTool(EditingTool, Protocol):
    """
PURPOSE:
Defined as an editing tool that updates or inserts lines within a line range in a read-write file

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    def file_alias_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the target read-write file
"""
        ...

    @property
    def start_line_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the starting line index
"""
        ...

    @property
    def end_line_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the ending line index
"""
        ...

    @property
    def replacement_text_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the replacement content
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executing an editing tool with a file alias that is not a read-write file fails

INHERITED_REQUIREMENTS:
- [EditingTool] Executing an editing tool with a file alias that is not a read-write file fails.
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.
"""
        ...

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Established that each tool has a name which the agent uses to execute the tool
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation
"""
        ...
