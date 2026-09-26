from typing import Any, Mapping, Optional, Protocol, Self, Set, Union
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import file_paths
import tool_provider


@singleton_type("agent_session")
class ReadManager(InTier[AgentSessionTier], Protocol):
    """Regulates workspace file reading."""

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """Exposes the session read-only files.

        GROUNDING_PROVISIONS:
        - knows("agent_session", Set[agent_file_alias.ReadOnlyFile]): Exposes session read-only files to satisfy requirement 4.
        """
        ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """Exposes the session read-write files.

        GROUNDING_PROVISIONS:
        - knows("agent_session", Set[agent_file_alias.ReadWriteFile]): Exposes session read-write files to satisfy requirement 4.
        """
        ...

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """Exposes the session guide file when configured."""
        ...

    @operation
    def can_read(
        self, path: Union[str, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        """Validates inspection access for a file path or alias.

        Args:
            path: The file path string or FileAlias to validate.

        Returns:
            Response indicating whether reading is permitted or providing recovery feedback.

        GROUNDING_PROVISIONS:
        - action("can_read", tool_provider.ToolResponse): Validates read access to satisfy requirement 5.
        """
        ...


@singleton_type("agent_session")
class ViewFileTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Reads file content."""

    @property
    def path_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        """Parameter identifying the file alias to read."""
        ...

    @property
    @override
    def name(self) -> str:
        ...

    @property
    @override
    def description(self) -> str:
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Executes the view file tool with actual parameter bindings.

        Args:
            actual_parameter_bindings: Bindings for tool invocation.

        Returns:
            Response providing output to the agent and indicating whether the conversation should terminate.

        GROUNDING_PROVISIONS:
        - action("execute_tool", tool_provider.ToolResponse): Reads file content to satisfy requirement 2.
        """
        ...


@singleton_type("agent_session")
class SearchTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Searches pattern matches across the session's read-only and read-write files."""

    @property
    def regex_pattern_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.RegexPattern, tool_provider.WireString]:
        """Parameter specifying the regex pattern to search for."""
        ...

    @property
    @override
    def name(self) -> str:
        ...

    @property
    @override
    def description(self) -> str:
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Executes the search tool with actual parameter bindings.

        Args:
            actual_parameter_bindings: Bindings for tool invocation.

        Returns:
            Response providing output to the agent and indicating whether the conversation should terminate.

        GROUNDING_PROVISIONS:
        - action("execute_tool", tool_provider.ToolResponse): Searches pattern matches across files to satisfy requirement 3.
        """
        ...
