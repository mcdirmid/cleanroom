# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 28e7dd9892e2
# GROUNDING_QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""Sandbox file reader implementation grounding specification module."""

from __future__ import annotations
import re
from typing import Any, Mapping, Optional, Set, Type, Union, cast
from support.lib.grounding_support import (
    InTier,
    AgentSessionTier,
    key,
    value,
    only_elem,
)
from parts.agent.grounding import agent_config, agent_file_alias, agent_node_config
from parts.core.grounding import filesystem_ext, file_paths
from parts.dag.grounding import dag_storage
from parts.sandbox.grounding import (
    sandbox_file_editor,
    sandbox_file_reader,
    template_format,
    tool_provider,
)


class ReadManager(sandbox_file_reader.ReadManager, InTier[AgentSessionTier]):
    """Realizes workspace file reading regulation and access validation.

    DISCHARGED:
    - can_read: Discharges path normalization and access gating against session files.
    """

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """
        COVERED:
        - Obtains read-only files from NodeConfig.
        """
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)
        _files: Set[agent_file_alias.ReadOnlyFile] = node_cfg.read_only_files
        raise NotImplementedError

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
        COVERED:
        - Obtains read-write files from NodeConfig.
        """
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)
        _files: Set[agent_file_alias.ReadWriteFile] = node_cfg.read_write_files
        raise NotImplementedError

    def can_read(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - WHEN path does not match any declared file workspace path, MUST produce a ToolResponse with failed set to True, content starting with "Error: Unknown file '{path}'. Available files: ", and reminder "Only declared files can be inspected.".
          - Condition knowledge: evaluate path against read_only_files and read_write_files.
          - Consequent knowledge: construct failing ToolResponse citing available files.
        - WHEN path matches a declared file workspace path, MUST produce a successful ToolResponse indicating access is permitted with content "Access permitted for '{path}'.".
          - Condition knowledge: path matches declared file.
          - Consequent knowledge: construct successful ToolResponse."""
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)
        ro_files = node_cfg.read_only_files
        rw_files = node_cfg.read_write_files
        path_str = str(path)

        # Undeclared file failure path knowledge
        sample_ro = only_elem(ro_files)
        available_str = f"{sample_ro.relative_path}"
        _fail_response = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: Unknown file '{path_str}'. Available files: {available_str}",
            reminder=tool_provider.ToolReminder(
                "Only declared files can be inspected."
            ),
        )

        # Declared file success path knowledge
        _is_declared: bool = path_str == str(sample_ro.relative_path)
        _res: tool_provider.ToolResponse = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=f"Access permitted for '{path_str}'.",
        )
        raise NotImplementedError


class ViewFileTool(sandbox_file_reader.ViewFileTool, InTier[AgentSessionTier]):
    """Executes file read across declared session files."""

    def __init__(self) -> None:
        self._path_param = tool_provider.ToolParameter[agent_file_alias.FileAlias, str](
            name=tool_provider.ParameterName("path"),
            description="File alias to view",
            parameter_type=tool_provider.SimpleParameterType[
                agent_file_alias.FileAlias, str
            ](),
            is_required=True,
            default_value=None,
            missing_message=None,
        )

    @property
    def name(self) -> tool_provider.ToolName:
        """
        COVERED:
        - Returns view_file name.
        """
        _name = tool_provider.ToolName("view_file")
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        COVERED:
        - Returns tool description.
        """
        _desc = tool_provider.ToolDescription(
            "View workspace file content with line numbers."
        )
        raise NotImplementedError

    @property
    def path_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """
        COVERED:
        - Returns path parameter definition.
        """
        _param = self._path_param
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        COVERED:
        - Returns parameters mapping.
        """
        _params = {self._path_param.name: self._path_param}
        raise NotImplementedError

    def initialize(self) -> None:
        """
        COVERED:
        - WHEN mcp mode is inactive, MUST install the view file tool for the agent session.
          - Condition knowledge: resolve AgentConfig and check not agent_cfg.is_mcp_mode.
          - Consequent knowledge: resolve ToolManager and invoke tool_mgr.install_tool(self).
        - WHEN mcp mode is active, MUST install no read tools.
          - Condition knowledge: check agent_cfg.is_mcp_mode.
        - MUST omit the search tool."""
        agent_cfg = self.get_singleton(agent_config.AgentConfig)
        tool_mgr = self.get_singleton(tool_provider.ToolManager)

        _mcp_mode: bool = agent_cfg.is_mcp_mode
        tool_mgr.install_tool(self)
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - WHEN target_file is an undeclared unbound file, MUST produce a ToolResponse with failed set to True, content starting with "Error: Unknown file '{path}'. Available files: ", and reminder "Only declared files can be inspected.".
          - Condition knowledge: isinstance(target_file, agent_file_alias.UnboundFile).
          - Consequent knowledge: return failed ToolResponse.
        - WHEN reading a missing read-only file, MUST produce a ToolResponse with failed set to True, content "Error: File '{path}' does not exist on disk.", and reminder "Only declared files can be inspected.".
          - Condition knowledge: isinstance(target_file, agent_file_alias.ReadOnlyFile) and not exists.
          - Consequent knowledge: return failed ToolResponse.
        - WHEN reading an existing file, MUST format file content with one-indexed right-aligned line numbers followed by a colon and space.
          - Consequent knowledge: enumerate lines starting at 1 and format "{line_no}: {line}".
        - WHEN reading a markdown file ending with .md, MUST filter out paragraphs beginning with '> META:'.
          - Condition knowledge: path.endswith('.md') and line.startswith('> META:').
          - Consequent knowledge: exclude meta lines.
        - WHEN reading a read-only markdown file ending with .md, MUST format content with session template parameters.
          - Condition knowledge: resolve TemplateFormatter and invoke format_template.
        - WHEN reading a read-write file that does not exist on disk, MUST treat file content as empty.
          - Condition knowledge: isinstance(target_file, agent_file_alias.ReadWriteFile) and not exists.
          - Consequent knowledge: content = "".
        - WHEN reading a read-write file, MUST set suppression key matching the file relative path.
          - Consequent knowledge: suppression_key = SuppressionKey(target_file.relative_path).
        - WHEN reading a read-only file, MUST omit suppression key and sanitize host paths.
          - Condition knowledge: resolve AliasManager and invoke sanitize_text.
          - Consequent knowledge: suppression_key = None.
        - WHEN reading a file succeeds, MUST record the read file to establish the session's last read or written file.
          - Consequent knowledge: resolve EditManager and invoke record_file_read(target_file)."""
        read_mgr = self.get_singleton(sandbox_file_reader.ReadManager)
        alias_mgr = self.get_singleton(agent_file_alias.AliasManager)
        edit_mgr = self.get_singleton(sandbox_file_editor.EditManager)
        formatter = self.get_singleton(template_format.TemplateFormatter)
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)

        sample_bound = agent_file_alias.ReadOnlyFile(
            relative_path=agent_file_alias.RelativePath("guide.md"),
            workspace_path=file_paths.WorkspacePath(
                file_paths.PathString("docs/guide.md")
            ),
            owning_node=dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("u"),
                role_address=dag_storage.RoleAddress("r"),
            ),
        )
        sample_unbound = agent_file_alias.UnboundFile(
            relative_path=agent_file_alias.RelativePath("unknown.txt")
        )
        sample_rw = agent_file_alias.ReadWriteFile(
            relative_path=agent_file_alias.RelativePath("code.py"),
            workspace_path=file_paths.WorkspacePath(
                file_paths.PathString("src/code.py")
            ),
            owning_node=dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("u"),
                role_address=dag_storage.RoleAddress("r"),
            ),
        )

        # 1. Undeclared unbound file knowledge
        _is_unbound: bool = isinstance(sample_unbound, agent_file_alias.UnboundFile)
        _unbound_err_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: Unknown file '{sample_unbound.relative_path}'. Available files: guide.md, code.py",
            reminder=tool_provider.ToolReminder(
                "Only declared files can be inspected."
            ),
        )

        # 2. Missing read-only file knowledge
        _missing_ro_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: File '{sample_bound.relative_path}' does not exist on disk.",
            reminder=tool_provider.ToolReminder(
                "Only declared files can be inspected."
            ),
        )

        # 3. Read content from filesystem
        _exists, raw_content = filesystem_ext.read_text_file(
            str(sample_bound.relative_path)
        )

        # 4. Markdown META filtering knowledge
        _is_md: bool = str(sample_bound.relative_path).endswith(".md")
        _is_meta_line: bool = "> META:".startswith("> META:")
        _clean_md_content: str = raw_content

        # 5. Template parameter formatting knowledge for read-only markdown
        tmpl_params = {
            template_format.TemplateKey(str(key(node_cfg.template_parameters))): value(
                node_cfg.template_parameters
            )
        }
        formatted_md = formatter.format_template(
            template_format.TemplateText(_clean_md_content),
            tmpl_params,
        )

        # 6. One-indexed line formatting knowledge
        line_num = 1
        formatted_line = f"{line_num:4d}: {formatted_md}\n"

        # 7. Read-only sanitization and suppression key omission knowledge
        sanitized_content = alias_mgr.sanitize_text(
            agent_file_alias.UnsanitizedText(formatted_line)
        )
        _ro_suppression: Optional[tool_provider.SuppressionKey] = None

        # 8. Read-write empty content fallback and suppression key assignment knowledge
        _rw_content = ""
        _rw_suppression = tool_provider.SuppressionKey(str(sample_rw.relative_path))

        # 9. Record file read knowledge
        edit_mgr.record_file_read(sample_bound)

        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=str(sanitized_content),
            suppression_key=_ro_suppression,
        )
        raise NotImplementedError


class RegexPatternParameterType(
    tool_provider.ParameterType[agent_file_alias.RegexPattern, str]
):
    """Converts wire type string into regex pattern."""

    @property
    def actual_type(self) -> Type[agent_file_alias.RegexPattern]:
        """
        COVERED:
        - Actual type is RegexPattern.
        """
        _t = cast(Type[agent_file_alias.RegexPattern], str)
        raise NotImplementedError

    @property
    def wire_type(self) -> Type[str]:
        """
        COVERED:
        - Wire type is string.
        """
        _t = str
        raise NotImplementedError

    def convert(self, wire_value: str) -> agent_file_alias.RegexPattern:
        """
        COVERED:
        - WHEN wire_value is not a valid regular expression pattern, MUST raise tool_provider.ParameterConversionError with message formatted as "Invalid regex pattern '{wire_value}': {error}".
          - Condition knowledge: evaluate re.compile(wire_value).
          - Consequent knowledge: construct ParameterConversionError formatted as "Invalid regex pattern '{wire_value}': {error}".
        - WHEN wire_value is a valid regular expression pattern, MUST return the constructed RegexPattern.
          - Consequent knowledge: return RegexPattern(wire_value)."""
        _err: tool_provider.ParameterConversionError = (
            tool_provider.ParameterConversionError(
                message=f"Invalid regex pattern '{wire_value}': invalid syntax"
            )
        )
        _pat = agent_file_alias.RegexPattern(wire_value)
        raise NotImplementedError


class SearchTool(sandbox_file_reader.SearchTool, InTier[AgentSessionTier]):
    """Searches regex patterns across workspace files."""

    def __init__(self) -> None:
        self._regex_param = tool_provider.ToolParameter[
            agent_file_alias.RegexPattern, str
        ](
            name=tool_provider.ParameterName("regex_pattern"),
            description="Regex pattern to search",
            parameter_type=RegexPatternParameterType(),
            is_required=True,
            default_value=None,
            missing_message=None,
        )

    @property
    def name(self) -> tool_provider.ToolName:
        """
        COVERED:
        - Returns search_files name.
        """
        _name = tool_provider.ToolName("search_files")
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        COVERED:
        - Returns search tool description.
        """
        _desc = tool_provider.ToolDescription(
            "Search for regex pattern matches across session files."
        )
        raise NotImplementedError

    @property
    def regex_pattern_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.RegexPattern, str]:
        """
        COVERED:
        - Returns regex pattern parameter.
        """
        _param = self._regex_param
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        COVERED:
        - Returns parameters mapping.
        """
        _params = {self._regex_param.name: self._regex_param}
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - WHEN regex pattern is invalid, MUST return a ToolResponse with failed set to True and content starting with "Error: Invalid regex pattern ".
          - Condition knowledge: test regex validity.
          - Consequent knowledge: return failed ToolResponse.
        - WHEN matches are found for read-only files, MUST return matched line contents and line numbers sanitized to mask host paths.
          - Condition knowledge: resolve AliasManager and call sanitize_text on matched lines.
          - Consequent knowledge: include line numbers and sanitized contents in ToolResponse.
        - WHEN matches are found for read-write files, MUST state that matches were found with "{relative_path}: matches found (details hidden to prevent unanchored edits)".
          - Condition knowledge: evaluate match on read-write file.
          - Consequent knowledge: format placeholder summary string."""
        read_mgr = self.get_singleton(sandbox_file_reader.ReadManager)
        alias_mgr = self.get_singleton(agent_file_alias.AliasManager)

        # 1. Invalid regex failure response knowledge
        _invalid_regex_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Error: Invalid regex pattern '[invalid': unterminated character set",
        )

        # 2. Read-only search matches and sanitization knowledge
        sample_ro_match = "sample_ro.py:10: def foo():"
        sanitized_ro_match = alias_mgr.sanitize_text(
            agent_file_alias.UnsanitizedText(sample_ro_match)
        )

        # 3. Read-write search matches summary knowledge
        sample_rw_path = "sample_rw.py"
        rw_match_summary = f"{sample_rw_path}: matches found (details hidden to prevent unanchored edits)"

        _combined_content = f"{sanitized_ro_match}\n{rw_match_summary}"

        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=_combined_content,
        )
        raise NotImplementedError


def __initialize__() -> None:
    """Initializes reader singletons in the agent session tier."""
    _read_mgr: ReadManager = cast(ReadManager, None)
    _view_tool: ViewFileTool = cast(ViewFileTool, None)
    _search_tool: SearchTool = cast(SearchTool, None)
    _regex_pt: RegexPatternParameterType = cast(RegexPatternParameterType, None)
