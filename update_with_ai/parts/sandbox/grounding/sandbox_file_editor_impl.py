# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 0c3161e8191a
# GROUNDING_QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

"""Sandbox file editor implementation grounding specification module."""

from __future__ import annotations
import hashlib
from typing import Any, Mapping, Optional, Set, Union, cast
from support.lib.grounding_support import (
    InTier,
    AgentSessionTier,
    key,
    value,
    only_elem,
)
from parts.agent.grounding import agent_file_alias, agent_node_config
from parts.core.grounding import filesystem_ext, file_paths
from parts.dag.grounding import dag_storage
from parts.sandbox.grounding import (
    sandbox_file_editor,
    tool_provider,
)


class EditManager(sandbox_file_editor.EditManager, InTier[AgentSessionTier]):
    """Realizes workspace file modification tracking.

    DISCHARGED:
    - file_update_revision: Discharges revision increment tracking.
    - record_file_read / record_file_edit: Discharges last read or edited file tracking.
    - file_hash: Discharges MD5 digest computation.
    - can_write: Discharges write access validation.
    """

    def __init__(self) -> None:
        self._has_modifications: bool = False
        self._revision: int = 0
        self._last_file: Optional[agent_file_alias.FileAlias] = None

    @property
    def has_modifications(self) -> bool:
        """
        COVERED:
        - Reports whether file modifications have occurred.
        """
        _has = self._has_modifications
        raise NotImplementedError

    @property
    def file_update_revision(self) -> sandbox_file_editor.FileUpdateRevision:
        """
        COVERED:
        - MUST increment the file update revision whenever workspace files are updated.
          - Consequent knowledge: returns FileUpdateRevision wrapping self._revision.
        """
        _rev = sandbox_file_editor.FileUpdateRevision(self._revision)
        raise NotImplementedError

    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        """
        COVERED:
        - Returns last read or edited file alias.
        """
        _last = self._last_file
        raise NotImplementedError

    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        """
        COVERED:
        - MUST record that the file was read, updating the last read or edited file in the session.
          - Consequent knowledge: assign self._last_file = file.
        """
        self._last_file = file
        raise NotImplementedError

    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        """
        COVERED:
        - MUST record that the file was edited, updating the last read or edited file in the session.
          - Consequent knowledge: assign self._last_file = file, set _has_modifications = True, increment _revision.
        """
        self._last_file = file
        self._has_modifications = True
        self._revision += 1
        raise NotImplementedError

    def file_hash(
        self, file: agent_file_alias.FileAlias
    ) -> sandbox_file_editor.FileHash:
        """
        COVERED:
        - MUST return an MD5 hexadecimal digest of content read from the filesystem.
          - Condition knowledge: read file content via filesystem_ext.read_text_file.
          - Consequent knowledge: compute hashlib.md5(content.encode("utf-8")).hexdigest() and return FileHash.
        """
        _ok, content = filesystem_ext.read_text_file(str(file.relative_path))
        digest = hashlib.md5(content.encode("utf-8")).hexdigest()
        _h = sandbox_file_editor.FileHash(digest)
        raise NotImplementedError

    def can_write(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - WHEN the target file is not a declared read-write file, MUST fail reminding the agent that only declared read-write files can be written.
          - Condition knowledge: test target not in declared read-write files.
          - Consequent knowledge: return failed ToolResponse with reminder "Only declared read-write files can be written.".
        - WHEN a declared read-write file is supplied, MUST record the file edit and confirm write access.
          - Consequent knowledge: call self.record_file_edit(target) and return confirming ToolResponse.
        """
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)
        rw_files = node_cfg.read_write_files
        sample_rw = only_elem(rw_files)

        # Undeclared read-write file failure knowledge
        _not_rw_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: File '{path}' is not a declared read-write file.",
            reminder=tool_provider.ToolReminder(
                "Only declared read-write files can be written."
            ),
        )

        # Declared read-write file success knowledge
        self.record_file_edit(sample_rw)
        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=f"Write access confirmed for '{sample_rw.relative_path}'.",
        )
        raise NotImplementedError


class ReplaceFileContentTool(
    sandbox_file_editor.ReplaceFileContentTool, InTier[AgentSessionTier]
):
    """Realizes targeted text replacement within bounded line ranges."""

    def __init__(self) -> None:
        self._path_param = tool_provider.ToolParameter[agent_file_alias.FileAlias, str](
            name=tool_provider.ParameterName("path"),
            description="File path",
            parameter_type=tool_provider.SimpleParameterType[
                agent_file_alias.FileAlias, str
            ](),
            is_required=False,
            default_value=None,
            missing_message=None,
        )
        self._target_param = tool_provider.ToolParameter[
            sandbox_file_editor.TargetContent, str
        ](
            name=tool_provider.ParameterName("target_content"),
            description="Target text",
            parameter_type=tool_provider.SimpleParameterType[
                sandbox_file_editor.TargetContent, str
            ](),
            is_required=True,
            default_value=None,
            missing_message=None,
        )
        self._replacement_param = tool_provider.ToolParameter[
            sandbox_file_editor.ReplacementContent, str
        ](
            name=tool_provider.ParameterName("replacement_content"),
            description="Replacement text",
            parameter_type=tool_provider.SimpleParameterType[
                sandbox_file_editor.ReplacementContent, str
            ](),
            is_required=True,
            default_value=None,
            missing_message=None,
        )
        self._start_param = tool_provider.ToolParameter[
            Optional[sandbox_file_editor.LineNumber], int
        ](
            name=tool_provider.ParameterName("start_line"),
            description="Start line",
            parameter_type=tool_provider.SimpleParameterType[
                Optional[sandbox_file_editor.LineNumber], int
            ](),
            is_required=False,
            default_value=None,
            missing_message=None,
        )
        self._end_param = tool_provider.ToolParameter[
            Optional[sandbox_file_editor.LineNumber], int
        ](
            name=tool_provider.ParameterName("end_line"),
            description="End line",
            parameter_type=tool_provider.SimpleParameterType[
                Optional[sandbox_file_editor.LineNumber], int
            ](),
            is_required=False,
            default_value=None,
            missing_message=None,
        )
        self._allow_param = tool_provider.ToolParameter[
            sandbox_file_editor.AllowMultiple, bool
        ](
            name=tool_provider.ParameterName("allow_multiple"),
            description="Allow multiple occurrences",
            parameter_type=tool_provider.SimpleParameterType[
                sandbox_file_editor.AllowMultiple, bool
            ](),
            is_required=False,
            default_value=sandbox_file_editor.AllowMultiple(False),
            missing_message=None,
        )

    @property
    def name(self) -> tool_provider.ToolName:
        """
        COVERED:
        - Returns replace_file_content name.
        """
        _name = tool_provider.ToolName("replace_file_content")
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        COVERED:
        - Returns tool description.
        """
        _desc = tool_provider.ToolDescription("Replace target text in file.")
        raise NotImplementedError

    @property
    def path_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """
        COVERED:
        - Returns path parameter definition.
        """
        _p = self._path_param
        raise NotImplementedError

    @property
    def target_content_parameter(
        self,
    ) -> tool_provider.ToolParameter[sandbox_file_editor.TargetContent, str]:
        """
        COVERED:
        - Returns target content parameter definition.
        """
        _p = self._target_param
        raise NotImplementedError

    @property
    def replacement_content_parameter(
        self,
    ) -> tool_provider.ToolParameter[sandbox_file_editor.ReplacementContent, str]:
        """
        COVERED:
        - Returns replacement content parameter definition.
        """
        _p = self._replacement_param
        raise NotImplementedError

    @property
    def start_line_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[sandbox_file_editor.LineNumber], int]:
        """
        COVERED:
        - Returns start line parameter definition.
        """
        _p = self._start_param
        raise NotImplementedError

    @property
    def end_line_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[sandbox_file_editor.LineNumber], int]:
        """
        COVERED:
        - Returns end line parameter definition.
        """
        _p = self._end_param
        raise NotImplementedError

    @property
    def allow_multiple_parameter(
        self,
    ) -> tool_provider.ToolParameter[sandbox_file_editor.AllowMultiple, bool]:
        """
        COVERED:
        - Returns allow multiple parameter definition.
        """
        _p = self._allow_param
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        COVERED:
        - Returns parameters mapping.
        """
        _params = {
            self._path_param.name: self._path_param,
            self._target_param.name: self._target_param,
            self._replacement_param.name: self._replacement_param,
            self._start_param.name: self._start_param,
            self._end_param.name: self._end_param,
            self._allow_param.name: self._allow_param,
        }
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - WHEN the path parameter is omitted and the last read or edited file is a read-write file, MUST bind the target file to the last read or edited file and include a warning.
          - Condition knowledge: path param omitted, edit_mgr.last_read_or_edited_file is ReadWriteFile.
          - Consequent knowledge: bind target to last read or edited file and append warning.
        - WHEN the path parameter is omitted and no valid read-write file history exists, MUST fail.
          - Condition knowledge: path param omitted, edit_mgr.last_read_or_edited_file is None or not ReadWriteFile.
          - Consequent knowledge: return failed ToolResponse.
        - WHEN start_line is provided and is less than one or exceeds total line count plus one, MUST fail.
          - Condition knowledge: evaluate start_line < 1 or start_line > total_lines + 1.
          - Consequent knowledge: return failed ToolResponse.
        - WHEN end_line is provided and is less than one or exceeds total line count, MUST fail.
          - Condition knowledge: evaluate end_line < 1 or end_line > total_lines.
          - Consequent knowledge: return failed ToolResponse.
        - WHEN both start_line and end_line are provided and start_line exceeds end_line, MUST fail.
          - Condition knowledge: evaluate start_line > end_line.
          - Consequent knowledge: return failed ToolResponse citing start_line exceeds end_line.
        - WHEN exact matching finds zero occurrences and allow_multiple is false, MUST fall back to whitespace-stripped line matching.
          - Condition knowledge: exact_count == 0, allow_multiple is False.
          - Consequent knowledge: evaluate line.strip() matching.
        - WHEN allow_multiple is false and target content matches multiple locations, MUST fail indicating the first two matching line numbers.
          - Condition knowledge: allow_multiple is False, match_count > 1.
          - Consequent knowledge: return failed ToolResponse citing lines l1 and l2.
        - WHEN target content is not found in the search window but exists elsewhere, MUST fail indicating the line numbers where target content was located.
          - Condition knowledge: window_matches == 0, global_matches > 0.
          - Consequent knowledge: return failed ToolResponse citing global matching line numbers.
        - WHEN the edit produces no change to file content, MUST fail reminding the agent that no-op edits will fail.
          - Condition knowledge: evaluate new_content == old_content.
          - Consequent knowledge: return failed ToolResponse with reminder "No-op edits will fail.".
        - WHEN the replacement succeeds, MUST write updated content creating missing parent directories and record workspace file writes.
          - Condition knowledge: edit_mgr.can_write confirmed.
          - Consequent knowledge: filesystem_ext.write_text_file and edit_mgr.record_file_edit."""
        edit_mgr = self.get_singleton(sandbox_file_editor.EditManager)

        # 1. Path omission resolution knowledge
        sample_last = edit_mgr.last_read_or_edited_file
        _is_last_rw: bool = isinstance(sample_last, agent_file_alias.ReadWriteFile)
        _omitted_no_history_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Error: Path parameter omitted and no previous read-write file was accessed.",
        )

        # 2. Line bounds validation knowledge
        total_lines = 100
        start_line = 10
        end_line = 20
        _invalid_start: bool = start_line < 1 or start_line > total_lines + 1
        _invalid_end: bool = end_line < 1 or end_line > total_lines
        _start_exceeds_end: bool = start_line > end_line
        _bounds_err_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: Invalid line range: start_line {start_line} exceeds end_line {end_line}.",
        )

        # 3. Exact matching vs whitespace stripped fallback knowledge
        _exact_matches = 0
        _allow_multiple = False
        _fallback_needed: bool = _exact_matches == 0 and not _allow_multiple
        _stripped_match: bool = "line".strip() == " line ".strip()

        # 4. Multiple matches failure knowledge
        l1, l2 = 12, 45
        _multi_match_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: Target content matched multiple locations (lines {l1}, {l2}). Provide tighter line bounds or set allow_multiple=True.",
        )

        # 5. Outside window failure knowledge
        found_line = 55
        _outside_window_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: Target content not found in lines {start_line}-{end_line}, but found at line {found_line}.",
        )

        # 6. No-op edit failure knowledge
        old_content = "same content"
        new_content = "same content"
        _is_noop: bool = new_content == old_content
        _noop_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Error: Replacement produced no changes to file content.",
            reminder=tool_provider.ToolReminder("No-op edits will fail."),
        )

        # 7. Write access, parent directory creation, and recording edit knowledge
        sample_rw = agent_file_alias.ReadWriteFile(
            relative_path=agent_file_alias.RelativePath("foo.py"),
            workspace_path=file_paths.WorkspacePath(
                path=file_paths.PathString("src/foo.py")
            ),
            owning_node=dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress("sample_unit"),
                role_address=dag_storage.RoleAddress("sample_role"),
            ),
        )
        _write_ok = edit_mgr.can_write(sample_rw)
        filesystem_ext.write_text_file(str(sample_rw.relative_path), "updated content")
        edit_mgr.record_file_edit(sample_rw)

        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content="Replacement succeeded.",
        )
        raise NotImplementedError


def __initialize__() -> None:
    """Initializes file editor singletons in the agent session tier."""
    _edit_mgr: EditManager = cast(EditManager, None)
    _tool: ReplaceFileContentTool = cast(ReplaceFileContentTool, None)
