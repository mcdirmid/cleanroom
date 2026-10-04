"""Sandbox file reader grounding specification module."""

from __future__ import annotations
from typing import Any, Mapping, Protocol, Set, Union
from support.lib.grounding_support import InTier, AgentSessionTier, only_elem, key, value
from parts.agent.grounding import agent_file_alias
from parts.sandbox.grounding import tool_provider


class ReadManager(InTier[AgentSessionTier], Protocol):
    """Regulates workspace file reading."""

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """
        DEFERRED:
        - MUST expose declared read-only files from other objects.
        """
        raise NotImplementedError

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
        DEFERRED:
        - MUST expose declared read-write files from other objects.
        """
        raise NotImplementedError

    def can_read(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        """
        DEFERRED:
        - WHEN checking read access for a workspace path matching declared files, MUST confirm access.
        - WHEN checking read access for an undeclared workspace path, MUST fail with guidance listing readable file aliases.
        """
        raise NotImplementedError


class ViewFileTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Reads file content."""

    @property
    def path_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """
        DEFERRED:
        - MUST specify the file alias path parameter converted using a parameter converter.
        """
        raise NotImplementedError

    @property
    def name(self) -> tool_provider.ToolName:
        """
        COVERED:
        - MUST return 'view_file'.
        """
        _name = tool_provider.ToolName("view_file")
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        COVERED:
        - MUST describe viewing workspace file content with line numbers using the file alias short name.
        """
        _desc = tool_provider.ToolDescription("View file content with line numbers using the file alias short name.")
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        DEFERRED:
        - MUST return a set containing strictly the path parameter.
        """
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - MUST retrieve file content for the specified file alias path.
          - Condition knowledge: access path parameter binding.
          - Consequent knowledge: construct ToolResponse carrying file contents.

        DEFERRED:
        - Line slicing, line numbering, and window bounds deferred to sandbox_file_reader_impl.py.        """
        sample_param = key(actual_parameter_bindings)
        sample_val = value(actual_parameter_bindings)
        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=f"Content for {sample_val}",
        )
        raise NotImplementedError


class SearchTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Searches pattern matches across the session's read-only and read-write files."""

    @property
    def regex_pattern_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.RegexPattern, str]:
        """
        DEFERRED:
        - MUST specify the regex pattern parameter converted using a parameter converter.
        """
        raise NotImplementedError

    @property
    def name(self) -> tool_provider.ToolName:
        """
        COVERED:
        - MUST return 'search_files'.
        """
        _name = tool_provider.ToolName("search_files")
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        COVERED:
        - MUST describe searching for regex pattern matches across session files.
        """
        _desc = tool_provider.ToolDescription("Search files for regex matches across session files.")
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        DEFERRED:
        - MUST return a set containing strictly the regex pattern parameter.
        """
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - MUST discover pattern matches across read-only and read-write files.
          - Condition knowledge: access regex pattern parameter binding.
          - Consequent knowledge: construct ToolResponse with match results.

        DEFERRED:
        - Regex compilation, multi-file searching, and result truncation deferred to sandbox_file_reader_impl.py.        """
        sample_param = key(actual_parameter_bindings)
        sample_val = value(actual_parameter_bindings)
        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=f"Matches for pattern {sample_val}",
        )
        raise NotImplementedError
