# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T23:15:12Z
# CHANGE: Reject editing tool replacements that alter the cleanroom metadata header
# CODE_HASH: e7c5aa5add5b
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

import difflib
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence, Set, Union, cast
from support.lib.lifecycle import InTier, LifecycleRegistry, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib.session import AgentSessionTier, agent_session
import update_with_ai.parts.agent.lib.agent_config as agent_config
import update_with_ai.parts.agent.lib.file_alias as file_alias
import update_with_ai.parts.agent.lib.node_config as node_config
import update_with_ai.parts.metadata.lib.src_metadata as src_metadata
from . import file_editor
from . import tool_provider

# Requirements specified in file_editor_impl.pyi

_REPLACE_FILE_CONTENT_SUPPRESSION_KEY = tool_provider.SuppressionKey("replace_file_content")


def _failure_response(
    content: str,
    reminder: Optional[str] = None,
    suppression_key: Optional[tool_provider.SuppressionKey] = None,
) -> tool_provider.ToolResponse:
    return tool_provider.ToolResponse(
        is_failed=True,
        is_terminated=False,
        content=tool_provider.ToolResponseContent(content),
        reminder=tool_provider.ToolReminder(reminder) if reminder is not None else None,
        suppression_key=suppression_key,
    )


def _target_content_missing_message(
    parameter_names: Set[tool_provider.ParameterName],
) -> tool_provider.MissingMessage:
    line_range_supplied = (
        tool_provider.ParameterName("start_line") in parameter_names
        or tool_provider.ParameterName("end_line") in parameter_names
    )
    if line_range_supplied:
        return tool_provider.MissingMessage(
            "start_line and end_line only restrict the search window; they do not identify the text to replace. "
            "target_content must match existing text in the file."
        )
    return tool_provider.MissingMessage(
        "target_content must match existing text in the file so content can be appended or inserted."
    )


# Fallback whitespace-stripped line matching heuristic when exact string match fails.
def _stripped_match_offsets(
    window_lines: Sequence[str], target_lines: Sequence[str]
) -> List[int]:
    if not target_lines or len(target_lines) > len(window_lines):
        return []
    stripped_target = [line.strip() for line in target_lines]
    offsets: List[int] = []
    for offset in range(0, len(window_lines) - len(target_lines) + 1):
        candidate = [line.strip() for line in window_lines[offset : offset + len(target_lines)]]
        if candidate == stripped_target:
            offsets.append(offset)
    return offsets


# Generation of unified diff for edit response display.
def _diff_delta(original: str, updated: str) -> str:
    delta = list(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )
    return "\n".join(delta)


# Verification that cleanroom metadata block remains unaltered by replacements.
def _is_cleanroom_metadata_altered(
    original_content: str,
    new_content: str,
    filename: str,
) -> bool:
    is_html = src_metadata._is_html_comment_format(filename)
    orig_lines = original_content.splitlines()
    orig_bounds = src_metadata._extract_block_boundaries(orig_lines, is_html)
    new_lines = new_content.splitlines()
    new_bounds = src_metadata._extract_block_boundaries(new_lines, is_html)

    if orig_bounds is not None:
        if new_bounds is None:
            return True
        orig_meta = orig_lines[orig_bounds[0] : orig_bounds[1] + 1]
        new_meta = new_lines[new_bounds[0] : new_bounds[1] + 1]
        if orig_meta != new_meta:
            return True
        if orig_lines[: orig_bounds[0]] != new_lines[: new_bounds[0]]:
            return True
    else:
        if new_bounds is not None:
            return True
        for line in new_lines:
            stripped = line.strip()
            if (
                stripped == "# --- CLEANROOM METADATA ---"
                or stripped == "# --- END CLEANROOM METADATA ---"
                or (stripped.startswith("<!--") and "CLEANROOM METADATA" in stripped)
            ):
                return True
    return False


class EditManager(file_editor.EditManager, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._file_update_revision = file_editor.FileUpdateRevision(0)
        self._last_read_or_edited_file: Optional[file_alias.FileAlias] = None
        self._writes_occurred = False

    # Contract: EditManager.has_modifications - exposes whether workspace file contents differ from their in-band code hash.
    @property
    def has_modifications(self) -> bool:
        meta_mgr = get_singleton(src_metadata.SourceMetadataCoordinator)
        node_cfg = get_singleton(node_config.NodeConfig)
        alias_mgr = get_singleton(file_alias.AliasManager)
        ws_root = str(alias_mgr.workspace_root.path)
        for rw_file in node_cfg.read_write_files:
            disk_path = str(Path(ws_root) / str(rw_file.workspace_path.path))
            if meta_mgr.is_code_modified(disk_path):
                return True
        return False

    # Contract: EditManager.file_update_revision - tracks sequential updates made to workspace files.
    @property
    def file_update_revision(self) -> file_editor.FileUpdateRevision:
        return self._file_update_revision

    # Contract: EditManager.last_read_or_edited_file - returns the most recently read or edited file alias across the session.
    @property
    def last_read_or_edited_file(self) -> Optional[file_alias.FileAlias]:
        return self._last_read_or_edited_file

    # Contract: EditManager.record_file_read - records that a file was read, updating last_read_or_edited_file.
    def record_file_read(self, file: file_alias.FileAlias) -> None:
        self._last_read_or_edited_file = file

    # Contract: EditManager.record_file_edit - records that a file was edited, updating last_read_or_edited_file and incrementing revision.
    def record_file_edit(self, file: file_alias.ReadWriteFile) -> None:
        self._last_read_or_edited_file = file
        self._writes_occurred = True
        self._file_update_revision = file_editor.FileUpdateRevision(
            int(self._file_update_revision) + 1
        )

    # Contract: EditManager.file_hash - computes an MD5 file hash from read-write file content.
    def file_hash(self, file: file_alias.FileAlias) -> file_editor.FileHash:
        alias_mgr = get_singleton(file_alias.AliasManager)
        node_cfg = get_singleton(node_config.NodeConfig)
        ws_root = str(alias_mgr.workspace_root.path)
        if isinstance(file, file_alias.BoundFile):
            relative = str(file.workspace_path.path)
        else:
            relative = str(file.relative_path)
            for declared in node_cfg.read_write_files | node_cfg.read_only_files:
                if (
                    str(declared.relative_path) == relative
                    or str(declared.workspace_path.path) == relative
                ):
                    relative = str(declared.workspace_path.path)
                    break
        disk_path = Path(ws_root) / relative
        content = disk_path.read_text(encoding="utf-8") if disk_path.is_file() else ""
        return file_editor.FileHash(hashlib.md5(content.encode("utf-8")).hexdigest())

    # Contract: EditManager.can_write - validates modification access for a read-write file against declared read-write files.
    def can_write(
        self, path: Union[file_alias.RelativePath, file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        node_cfg = get_singleton(node_config.NodeConfig)
        relative = (
            str(path.relative_path)
            if isinstance(path, file_alias.FileAlias)
            else str(path)
        )
        matching_rw: Optional[file_alias.ReadWriteFile] = None
        for rw_file in node_cfg.read_write_files:
            if (
                str(rw_file.relative_path) == relative
                or str(rw_file.workspace_path.path) == relative
                or (isinstance(path, file_alias.BoundFile) and rw_file.workspace_path == path.workspace_path)
            ):
                matching_rw = rw_file
                break
        if matching_rw is None:
            return _failure_response(
                f"Error: File '{relative}' is not a declared read-write file.",
                "Only declared read-write files can be written.",
            )
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(
                f"Write access confirmed for '{relative}'."
            ),
        )


@dataclass(frozen=True)
class _TargetContentParamType(tool_provider.ParameterType[file_editor.TargetContent, str]):
    @property
    def actual_type(self) -> type[file_editor.TargetContent]:
        return cast(type[file_editor.TargetContent], file_editor.TargetContent)

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> file_editor.TargetContent:
        if not isinstance(wire_value, str):
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(
                    f"Expected str for target_content, got {type(wire_value).__name__}"
                )
            )
        return file_editor.TargetContent(wire_value)


@dataclass(frozen=True)
class _ReplacementContentParamType(tool_provider.ParameterType[file_editor.ReplacementContent, str]):
    @property
    def actual_type(self) -> type[file_editor.ReplacementContent]:
        return cast(type[file_editor.ReplacementContent], file_editor.ReplacementContent)

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> file_editor.ReplacementContent:
        if not isinstance(wire_value, str):
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(
                    f"Expected str for replacement_content, got {type(wire_value).__name__}"
                )
            )
        return file_editor.ReplacementContent(wire_value)


@dataclass(frozen=True)
class _LineNumberParamType(tool_provider.ParameterType[Optional[file_editor.LineNumber], int]):
    @property
    def actual_type(self) -> type[Optional[file_editor.LineNumber]]:
        return cast(type[Optional[file_editor.LineNumber]], int)

    @property
    def wire_type(self) -> type[int]:
        return int

    def convert(self, wire_value: int) -> Optional[file_editor.LineNumber]:
        if wire_value is None:
            return None
        if not isinstance(wire_value, int) or isinstance(wire_value, bool):
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(
                    f"Expected int for line number, got {type(wire_value).__name__}"
                )
            )
        return file_editor.LineNumber(wire_value)


@dataclass(frozen=True)
class _AllowMultipleParamType(tool_provider.ParameterType[file_editor.AllowMultiple, bool]):
    @property
    def actual_type(self) -> type[file_editor.AllowMultiple]:
        return cast(type[file_editor.AllowMultiple], file_editor.AllowMultiple)

    @property
    def wire_type(self) -> type[bool]:
        return bool

    def convert(self, wire_value: bool) -> file_editor.AllowMultiple:
        if not isinstance(wire_value, bool):
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(
                    f"Expected bool for allow_multiple, got {type(wire_value).__name__}"
                )
            )
        return file_editor.AllowMultiple(wire_value)


class ReplaceFileContentTool(file_editor.ReplaceFileContentTool, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    # Contract: ReplaceFileContentTool.initialize - installs tool into session environment via ToolManager.
    def initialize(self) -> None:
        tool_mgr = get_singleton(tool_provider.ToolManager)
        tool_mgr.install_tool(self)

    # Contract: ReplaceFileContentTool.path_parameter - parameter identifying the target read-write file.
    @property
    def path_parameter(self) -> tool_provider.ToolParameter[file_alias.FileAlias, str]:
        alias_type = get_singleton(tool_provider.AliasManagerType)
        return tool_provider.ToolParameter[file_alias.FileAlias, str](
            name=tool_provider.ParameterName("path"),
            description=tool_provider.ParameterDescription("Target read-write file."),
            parameter_type=alias_type,
            is_required=False,
            default_value=None,
        )

    # Contract: ReplaceFileContentTool.target_content_parameter - parameter specifying target content to replace.
    @property
    def target_content_parameter(self) -> tool_provider.ToolParameter[file_editor.TargetContent, str]:
        return tool_provider.ToolParameter[file_editor.TargetContent, str](
            name=tool_provider.ParameterName("target_content"),
            description=tool_provider.ParameterDescription("The exact string to be replaced."),
            parameter_type=_TargetContentParamType(),
            is_required=True,
            default_value=None,
            missing_message=_target_content_missing_message,
        )

    # Contract: ReplaceFileContentTool.replacement_content_parameter - parameter specifying replacement content.
    @property
    def replacement_content_parameter(self) -> tool_provider.ToolParameter[file_editor.ReplacementContent, str]:
        return tool_provider.ToolParameter[file_editor.ReplacementContent, str](
            name=tool_provider.ParameterName("replacement_content"),
            description=tool_provider.ParameterDescription("The content to replace the target content with."),
            parameter_type=_ReplacementContentParamType(),
            is_required=True,
            default_value=None,
        )

    # Contract: ReplaceFileContentTool.start_line_parameter - parameter specifying start line of search window.
    @property
    def start_line_parameter(self) -> tool_provider.ToolParameter[Optional[file_editor.LineNumber], int]:
        return tool_provider.ToolParameter[Optional[file_editor.LineNumber], int](
            name=tool_provider.ParameterName("start_line"),
            description=tool_provider.ParameterDescription("Starting line number of search window."),
            parameter_type=_LineNumberParamType(),
            is_required=False,
            default_value=None,
        )

    # Contract: ReplaceFileContentTool.end_line_parameter - parameter specifying end line of search window.
    @property
    def end_line_parameter(self) -> tool_provider.ToolParameter[Optional[file_editor.LineNumber], int]:
        return tool_provider.ToolParameter[Optional[file_editor.LineNumber], int](
            name=tool_provider.ParameterName("end_line"),
            description=tool_provider.ParameterDescription("Ending line number of search window."),
            parameter_type=_LineNumberParamType(),
            is_required=False,
            default_value=None,
        )

    # Contract: ReplaceFileContentTool.allow_multiple_parameter - parameter specifying whether to replace multiple occurrences.
    @property
    def allow_multiple_parameter(self) -> tool_provider.ToolParameter[file_editor.AllowMultiple, bool]:
        return tool_provider.ToolParameter[file_editor.AllowMultiple, bool](
            name=tool_provider.ParameterName("allow_multiple"),
            description=tool_provider.ParameterDescription("Whether to replace multiple occurrences."),
            parameter_type=_AllowMultipleParamType(),
            is_required=False,
            default_value=file_editor.AllowMultiple(False),
        )

    # Contract: Tool.name - returns tool identifier "replace_file_content".
    @property
    def name(self) -> tool_provider.ToolName:
        return tool_provider.ToolName("replace_file_content")

    # Contract: Tool.description - returns tool description.
    @property
    def description(self) -> tool_provider.ToolDescription:
        return tool_provider.ToolDescription("Replaces target content in a read-write file.")

    # Contract: Tool.parameters - returns tool parameter mapping.
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return {
            self.path_parameter.name: self.path_parameter,
            self.target_content_parameter.name: self.target_content_parameter,
            self.replacement_content_parameter.name: self.replacement_content_parameter,
            self.start_line_parameter.name: self.start_line_parameter,
            self.end_line_parameter.name: self.end_line_parameter,
            self.allow_multiple_parameter.name: self.allow_multiple_parameter,
        }

    # Contract: ReplaceFileContentTool.execute_tool - replaces target content with replacement content in bounded line range.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        edit_mgr = get_singleton(file_editor.EditManager)
        node_cfg = get_singleton(node_config.NodeConfig)
        alias_mgr = get_singleton(file_alias.AliasManager)
        ws_root = str(alias_mgr.workspace_root.path)

        warning = ""
        target_file = cast(Any, actual_parameter_bindings.get(self.path_parameter))

        def fail(message: str, reminder: Optional[str] = None) -> tool_provider.ToolResponse:
            return _failure_response(
                f"{warning}{message}",
                reminder,
                _REPLACE_FILE_CONTENT_SUPPRESSION_KEY,
            )

        if target_file is None:
            last = edit_mgr.last_read_or_edited_file
            if last is None:
                return fail(
                    "Error: Path parameter omitted and no file has been read or edited in this session."
                )
            declared_rw = [
                f for f in node_cfg.read_write_files if (
                    str(f.relative_path) == str(last.relative_path)
                    or str(f.workspace_path.path) == str(last.relative_path)
                    or (isinstance(last, file_alias.BoundFile) and f.workspace_path == last.workspace_path)
                )
            ]
            if not declared_rw:
                return fail(
                    f"Error: Path parameter omitted and last read or edited file "
                    f"'{last.relative_path}' is not a declared read-write file."
                )
            target_file = last
            warning = (
                f"Warning: Path omitted, defaulted to last read or edited file "
                f"'{target_file.relative_path}'.\n"
            )

        matching_rw_files = [
            f for f in node_cfg.read_write_files if (
                str(f.relative_path) == str(target_file.relative_path)
                or str(f.workspace_path.path) == str(target_file.relative_path)
                or (isinstance(target_file, file_alias.BoundFile) and f.workspace_path == target_file.workspace_path)
            )
        ]
        if not matching_rw_files:
            return fail(
                f"Error: File '{target_file.relative_path}' is not a declared read-write file."
            )
        target_rw_file = matching_rw_files[0]

        disk_path = Path(ws_root) / str(target_rw_file.workspace_path.path)
        content = disk_path.read_text(encoding="utf-8") if disk_path.is_file() else ""

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        start_line = actual_parameter_bindings.get(self.start_line_parameter)
        end_line = actual_parameter_bindings.get(self.end_line_parameter)

        if start_line is not None:
            s_line = int(cast(Any, start_line))
            if s_line < 1:
                return fail(
                    f"Error: start_line {s_line} is out of bounds; it must not be less than one."
                )
            if s_line > total_lines + 1:
                return fail(
                    f"Error: start_line {s_line} exceeds the total line count plus one "
                    f"({total_lines + 1})."
                )

        if end_line is not None:
            e_line = int(cast(Any, end_line))
            if e_line < 1:
                return fail(
                    f"Error: end_line {e_line} is out of bounds; it must not be less than one."
                )
            if e_line > total_lines:
                return fail(
                    f"Error: end_line {e_line} exceeds the total line count ({total_lines})."
                )

        if start_line is not None and end_line is not None:
            if int(cast(Any, start_line)) > int(cast(Any, end_line)):
                return fail(
                    f"Error: start_line {int(cast(Any, start_line))} exceeds end_line "
                    f"{int(cast(Any, end_line))}."
                )

        target_content = str(actual_parameter_bindings.get(self.target_content_parameter))
        replacement_content = str(actual_parameter_bindings.get(self.replacement_content_parameter))
        allow_multiple = bool(actual_parameter_bindings.get(self.allow_multiple_parameter, False))

        s_idx = (int(cast(Any, start_line)) - 1) if start_line is not None else 0
        e_idx = int(cast(Any, end_line)) if end_line is not None else total_lines

        window_lines = lines[s_idx:e_idx]
        window_text = "".join(window_lines)
        target_lines = target_content.splitlines()

        exact_count = window_text.count(target_content)
        stripped_offsets: List[int] = []
        # Fallback whitespace-stripped line matching heuristic when exact string match fails.
        if exact_count == 0 and not allow_multiple:
            stripped_offsets = _stripped_match_offsets(window_lines, target_lines)
            if len(stripped_offsets) > 1:
                return fail(
                    f"Error: Target content matches multiple locations "
                    f"(lines {s_idx + stripped_offsets[0] + 1} and "
                    f"{s_idx + stripped_offsets[1] + 1}). Include more surrounding lines in the "
                    f"target content to identify a unique location, or specify start_line and "
                    f"end_line to narrow the replacement region."
                )

        if exact_count == 0 and not stripped_offsets:
            global_text = "".join(lines)
            if target_content in global_text:
                locations: List[int] = []
                pos = global_text.find(target_content)
                step = max(1, len(target_content))
                while pos != -1:
                    locations.append(global_text[:pos].count("\n") + 1)
                    pos = global_text.find(target_content, pos + step)
                unique_locations = list(dict.fromkeys(locations))
                located = ", ".join(str(line_number) for line_number in unique_locations)
                return fail(
                    f"Error: Target content was not found within the search window "
                    f"(lines {s_idx + 1}-{e_idx}) but was located at line(s): {located}."
                )
            return fail(
                f"Error: Target content was not found within the search window "
                f"(lines {s_idx + 1}-{e_idx})."
            )

        if exact_count > 1 and not allow_multiple:
            first_pos = window_text.find(target_content)
            step = max(1, len(target_content))
            second_pos = window_text.find(target_content, first_pos + step)
            first_line = s_idx + 1 + window_text[:first_pos].count("\n")
            second_line = s_idx + 1 + window_text[:second_pos].count("\n")
            return fail(
                f"Error: Target content matches multiple locations "
                f"(lines {first_line} and {second_line}). Include more surrounding "
                f"lines in the target content to identify a unique location, or specify start_line "
                f"and end_line to narrow the replacement region."
            )

        if stripped_offsets:
            offset = stripped_offsets[0]
            matched_count = len(target_lines)
            replacement_lines = replacement_content.splitlines(keepends=True)
            if (
                replacement_lines
                and window_lines[offset + matched_count - 1].endswith("\n")
                and not replacement_lines[-1].endswith("\n")
            ):
                replacement_lines[-1] = f"{replacement_lines[-1]}\n"
            new_window_text = "".join(
                window_lines[:offset]
                + replacement_lines
                + window_lines[offset + matched_count :]
            )
        elif allow_multiple:
            new_window_text = window_text.replace(target_content, replacement_content)
        else:
            new_window_text = window_text.replace(target_content, replacement_content, 1)

        new_content = "".join(lines[:s_idx]) + new_window_text + "".join(lines[e_idx:])
        if new_content == content:
            return fail(
                "Error: No-op edit; the replacement produces no change to the file content.",
                "The edit had no effect.",
            )

        # Rejecting replacements that alter the cleanroom metadata header.
        if _is_cleanroom_metadata_altered(content, new_content, disk_path.name):
            return fail(
                "Error: CLEANROOM METADATA is managed automatically by submit; do not edit it directly.",
                "Cleanroom metadata is managed automatically by submit.",
            )

        disk_path.parent.mkdir(parents=True, exist_ok=True)
        disk_path.write_text(new_content, encoding="utf-8")

        edit_mgr.record_file_edit(target_rw_file)

        body = f"Successfully updated {target_file.relative_path}."
        # Appending unified diff output based on AgentConfig.edit_delta_output.
        if get_singleton(agent_config.AgentConfig).edit_delta_output:
            body = f"{body}\n\n{_diff_delta(content, new_content)}"
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(f"{warning}{body}"),
            reminder=tool_provider.ToolReminder(
                "Verify syntax and type correctness before making further writes."
            ),
            suppression_key=_REPLACE_FILE_CONTENT_SUPPRESSION_KEY,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        EditManager,
        keys=[EditManager, file_editor.EditManager, InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        ReplaceFileContentTool,
        keys=[ReplaceFileContentTool, file_editor.ReplaceFileContentTool, InTier[AgentSessionTier]],
        tier=agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
