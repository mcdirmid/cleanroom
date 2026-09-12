from typing import Optional, Protocol, Set
from framework import operation, override, singleton_type
import file_alias
import tool_provider

@singleton_type('agent_session')
class ReadManager(Protocol):
    """
PURPOSE:
Defined as an agent session service that installs tools for inspecting workspace files

FRESH_REQUIREMENTS:
- The read manager installs the read tool and search tool.
- The read manager exposes the session's set of read-only files to support session startup context injection.
- The read manager exposes the session's set of read-write files.
- When step-mode is active, the read manager is configured with a guide file that is an unbound file.
"""

    @property
    def read_only_files(self) -> Set[file_alias.ReadOnlyFile]:
        """
PURPOSE:
Exposes the agent session's set of read-only files to support session startup context injection
"""
        ...

    @property
    def read_write_files(self) -> Set[file_alias.ReadWriteFile]:
        """
PURPOSE:
Exposes the agent session's set of read-write files to support session inspection
"""
        ...

    @property
    def guide_file(self) -> Optional[file_alias.UnboundFile]:
        """
PURPOSE:
Configured with a guide file as an unbound file when step-mode is active
"""
        ...

    @operation
    def requires_line_numbers(self, file: file_alias.FileAlias) -> bool:
        """
PURPOSE:
Identifies whether an inspected file requires line numbers to be requested when read
"""
        ...

@singleton_type('agent_session')
class ReadTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as a tool that reads file content

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    def file_alias_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Establishes that the read tool takes a file alias parameter
"""
        ...

    @property
    def line_numbers_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Establishes that the read tool takes a parameter specifying if the agent wants content formatted with line numbers or not
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Provides that executing the read tool reads file content and distinguishes reading attempts on the guide file

FRESH_REQUIREMENTS:
- Executing the read tool on the guide file provides progressive delivery feedback to the agent.
- When reading markdown files, paragraphs beginning with > META: are filtered out.

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
class SearchTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as a tool that searches pattern matches across the session's read-only and read-write files

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The search tool accepts a regex pattern parameter.
"""

    @property
    def regex_pattern_parameter(self) -> tool_provider.Parameter:
        """
PURPOSE:
Establishes that the search tool takes a regex pattern parameter
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Provides that executing the search tool searches pattern matches across the session's read-only and read-write files

FRESH_REQUIREMENTS:
- Executing the search tool searches pattern matches across the session's read-only and read-write files.

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
