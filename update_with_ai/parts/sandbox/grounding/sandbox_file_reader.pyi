from typing import Optional, Protocol, Set, Union
from framework import operation, override, singleton_type
import agent_file_alias
import tool_provider

@singleton_type('agent_session')
class ReadManager(Protocol):
    """
PURPOSE:
Defined as an agent session service that installs tools for inspecting workspace files

FRESH_REQUIREMENTS:
- The read manager installs the view file tool and search tool.
- The read manager exposes the session's set of read-only files.
- The read manager exposes the session's set of read-write files.
- When step-mode is active, the read manager is configured with a guide file that is an unbound file.
"""

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """
PURPOSE:
Exposes the agent session's set of read-only files to support session startup context injection
"""
        ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
PURPOSE:
Exposes the agent session's set of read-write files to support session inspection
"""
        ...

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """
PURPOSE:
Configured with a guide file as an unbound file when step-mode is active
"""
        ...

    @operation
    def can_read(self, path: Union[str, agent_file_alias.FileAlias]) -> tool_provider.Response:
        """
PURPOSE:
Validates inspection access for a file path under role blindness and file boundaries

FRESH_REQUIREMENTS:
- The read manager provides a can read operation validating inspection access for a file path.
"""
        ...

@singleton_type('agent_session')
class ViewFileTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as a tool that inspects file content

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    def path_parameter(self) -> tool_provider.Parameter[agent_file_alias.FileAlias, str]:
        """
PURPOSE:
Establishes that the view file tool takes a path parameter
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Provides that executing the view file tool inspects file content

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
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
    def regex_pattern_parameter(self) -> tool_provider.Parameter[agent_file_alias.RegexPattern, str]:
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
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
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
