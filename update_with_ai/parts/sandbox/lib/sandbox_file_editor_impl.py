# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:46:23Z
# LAST_CHANGED: 2026-10-09T22:20:00Z
# CHANGE: Resolve string workspace root path from WorkspaceRoot dataclass
# CODE_HASH: 7a4c810bf7e5
# QA_AUDIT: 2026-10-09T21:46:23Z
# --- END CLEANROOM METADATA ---

import hashlib
import os
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Set, Union, cast
from support.lib.lifecycle import InTier, LifecycleRegistry, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier, agent_session
import update_with_ai.parts.agent.lib.agent_config as agent_config
import update_with_ai.parts.agent.lib.agent_file_alias as agent_file_alias
import update_with_ai.parts.agent.lib.agent_node_config as agent_node_config
import update_with_ai.parts.control.lib.src_metadata as src_metadata
from . import sandbox_file_editor
from . import tool_provider

# Requirements specified in sandbox_file_editor_impl.pyi

class EditManager(sandbox_file_editor.EditManager, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._file_update_revision = sandbox_file_editor.FileUpdateRevision(0)
        self._last_read_or_edited_file: Optional[agent_file_alias.FileAlias] = None

    @property
    def has_modifications(self) -> bool:
        meta_mgr = get_singleton(src_metadata.SourceMetadataCoordinator)
        node_cfg = get_singleton(agent_node_config.NodeConfig)
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        ws_root = str(getattr(alias_mgr.workspace_root, "path", alias_mgr.workspace_root))
        for rw_file in node_cfg.read_write_files:
            disk_path = os.path.join(ws_root, str(rw_file.relative_path))
            if meta_mgr.is_code_modified(disk_path):
                return True
        return False

    @property
    def file_update_revision(self) -> sandbox_file_editor.FileUpdateRevision:
        return self._file_update_revision

    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        return self._last_read_or_edited_file

    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        self._last_read_or_edited_file = file

    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        self._last_read_or_edited_file = file
        self._file_update_revision = sandbox_file_editor.FileUpdateRevision(int(self._file_update_revision) + 1)

    def file_hash(self, file: agent_file_alias.FileAlias) -> sandbox_file_editor.FileHash:
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        ws_root = str(getattr(alias_mgr.workspace_root, "path", alias_mgr.workspace_root))
        disk_path = os.path.join(ws_root, str(file.relative_path))
        if os.path.isfile(disk_path):
            with open(disk_path, "rb") as f:
                content = f.read()
        else:
            content = b""
        h = hashlib.md5(content).hexdigest()
        return sandbox_file_editor.FileHash(h)

    def can_write(self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]) -> tool_provider.ToolResponse:
        node_cfg = get_singleton(agent_node_config.NodeConfig)
        rel_path = str(path.relative_path) if isinstance(path, agent_file_alias.FileAlias) else str(path)
        matching_rw = [f for f in node_cfg.read_write_files if str(f.relative_path) == rel_path]
        if not matching_rw:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: File '{rel_path}' is not a declared read-write file."
                ),
                reminder=tool_provider.ToolReminder("Only declared read-write files can be written."),
            )
        self.record_file_edit(matching_rw[0])
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(f"Write access confirmed for '{rel_path}'."),
        )


@dataclass(frozen=True)
class _TargetContentParamType(tool_provider.ParameterType[sandbox_file_editor.TargetContent, str]):
    @property
    def actual_type(self) -> type[sandbox_file_editor.TargetContent]:
        return cast(type[sandbox_file_editor.TargetContent], sandbox_file_editor.TargetContent)

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> sandbox_file_editor.TargetContent:
        return sandbox_file_editor.TargetContent(str(wire_value))


@dataclass(frozen=True)
class _ReplacementContentParamType(tool_provider.ParameterType[sandbox_file_editor.ReplacementContent, str]):
    @property
    def actual_type(self) -> type[sandbox_file_editor.ReplacementContent]:
        return cast(type[sandbox_file_editor.ReplacementContent], sandbox_file_editor.ReplacementContent)

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> sandbox_file_editor.ReplacementContent:
        return sandbox_file_editor.ReplacementContent(str(wire_value))


@dataclass(frozen=True)
class _LineNumberParamType(tool_provider.ParameterType[Optional[sandbox_file_editor.LineNumber], int]):
    @property
    def actual_type(self) -> type[Optional[sandbox_file_editor.LineNumber]]:
        return cast(type[Optional[sandbox_file_editor.LineNumber]], int)

    @property
    def wire_type(self) -> type[int]:
        return int

    def convert(self, wire_value: int) -> Optional[sandbox_file_editor.LineNumber]:
        return sandbox_file_editor.LineNumber(int(wire_value))


@dataclass(frozen=True)
class _AllowMultipleParamType(tool_provider.ParameterType[sandbox_file_editor.AllowMultiple, bool]):
    @property
    def actual_type(self) -> type[sandbox_file_editor.AllowMultiple]:
        return cast(type[sandbox_file_editor.AllowMultiple], sandbox_file_editor.AllowMultiple)

    @property
    def wire_type(self) -> type[bool]:
        return bool

    def convert(self, wire_value: bool) -> sandbox_file_editor.AllowMultiple:
        return sandbox_file_editor.AllowMultiple(bool(wire_value))


class ReplaceFileContentTool(sandbox_file_editor.ReplaceFileContentTool, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    def initialize(self) -> None:
        tool_mgr = get_singleton(tool_provider.ToolManager)
        tool_mgr.install_tool(self)

    @property
    def path_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.ToolParameter[agent_file_alias.FileAlias, str](
            name=tool_provider.ParameterName("path"),
            description=tool_provider.ParameterDescription("Target read-write file."),
            parameter_type=alias_mgr,
            is_required=False,
            default_value=None,
        )

    @property
    def target_content_parameter(self) -> tool_provider.ToolParameter[sandbox_file_editor.TargetContent, str]:
        return tool_provider.ToolParameter[sandbox_file_editor.TargetContent, str](
            name=tool_provider.ParameterName("target_content"),
            description=tool_provider.ParameterDescription("The exact string to be replaced."),
            parameter_type=_TargetContentParamType(),
            is_required=True,
            default_value=None,
        )

    @property
    def replacement_content_parameter(self) -> tool_provider.ToolParameter[sandbox_file_editor.ReplacementContent, str]:
        return tool_provider.ToolParameter[sandbox_file_editor.ReplacementContent, str](
            name=tool_provider.ParameterName("replacement_content"),
            description=tool_provider.ParameterDescription("The content to replace the target content with."),
            parameter_type=_ReplacementContentParamType(),
            is_required=True,
            default_value=None,
        )

    @property
    def start_line_parameter(self) -> tool_provider.ToolParameter[Optional[sandbox_file_editor.LineNumber], int]:
        return tool_provider.ToolParameter[Optional[sandbox_file_editor.LineNumber], int](
            name=tool_provider.ParameterName("start_line"),
            description=tool_provider.ParameterDescription("Starting line number of search window."),
            parameter_type=_LineNumberParamType(),
            is_required=False,
            default_value=None,
        )

    @property
    def end_line_parameter(self) -> tool_provider.ToolParameter[Optional[sandbox_file_editor.LineNumber], int]:
        return tool_provider.ToolParameter[Optional[sandbox_file_editor.LineNumber], int](
            name=tool_provider.ParameterName("end_line"),
            description=tool_provider.ParameterDescription("Ending line number of search window."),
            parameter_type=_LineNumberParamType(),
            is_required=False,
            default_value=None,
        )

    @property
    def allow_multiple_parameter(self) -> tool_provider.ToolParameter[sandbox_file_editor.AllowMultiple, bool]:
        return tool_provider.ToolParameter[sandbox_file_editor.AllowMultiple, bool](
            name=tool_provider.ParameterName("allow_multiple"),
            description=tool_provider.ParameterDescription("Whether to replace multiple occurrences."),
            parameter_type=_AllowMultipleParamType(),
            is_required=False,
            default_value=sandbox_file_editor.AllowMultiple(False),
        )

    @property
    def name(self) -> tool_provider.ToolName:
        return tool_provider.ToolName("replace_file_content")

    @property
    def description(self) -> tool_provider.ToolDescription:
        return tool_provider.ToolDescription("Replaces target content in a read-write file.")

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

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        node_cfg = get_singleton(agent_node_config.NodeConfig)
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        ws_root = str(getattr(alias_mgr.workspace_root, "path", alias_mgr.workspace_root))

        target_file = cast(Any, actual_parameter_bindings.get(self.path_parameter))
        warning = ""

        if target_file is None:
            last = edit_mgr.last_read_or_edited_file
            if last is None or not any(f.relative_path == last.relative_path for f in node_cfg.read_write_files):
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        "Error: Path parameter omitted and no previous read-write file in session history."
                    ),
                )
            target_file = last
            warning = f"Warning: Path omitted, defaulted to last read/edited file '{target_file.relative_path}'.\n"

        matching_rw_files = [f for f in node_cfg.read_write_files if f.relative_path == target_file.relative_path]
        if not matching_rw_files:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: File '{target_file.relative_path}' is not a declared read-write file."
                ),
            )
        target_rw_file = matching_rw_files[0]

        disk_path = os.path.join(ws_root, str(target_file.relative_path))

        if os.path.isfile(disk_path):
            with open(disk_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = ""

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        start_line = actual_parameter_bindings.get(self.start_line_parameter)
        end_line = actual_parameter_bindings.get(self.end_line_parameter)

        if start_line is not None:
            s_line = int(cast(Any, start_line))
            if s_line < 1 or s_line > total_lines + 1:
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        f"Error: start_line {s_line} is out of bounds (1..{total_lines + 1})."
                    ),
                )

        if end_line is not None:
            e_line = int(cast(Any, end_line))
            if e_line < 1 or e_line > max(1, total_lines):
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        f"Error: end_line {e_line} is out of bounds (1..{total_lines})."
                    ),
                )

        if start_line is not None and end_line is not None:
            if int(cast(Any, start_line)) > int(cast(Any, end_line)):
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        f"Error: start_line {start_line} exceeds end_line {end_line}."
                    ),
                )

        target_content = str(actual_parameter_bindings.get(self.target_content_parameter))
        replacement_content = str(actual_parameter_bindings.get(self.replacement_content_parameter))
        allow_multiple = bool(actual_parameter_bindings.get(self.allow_multiple_parameter, False))

        s_idx = (int(cast(Any, start_line)) - 1) if start_line is not None else 0
        e_idx = int(cast(Any, end_line)) if end_line is not None else total_lines

        window_lines = lines[s_idx:e_idx]
        window_text = "".join(window_lines)

        exact_count = window_text.count(target_content)

        if exact_count == 0:
            global_text = "".join(lines)
            if target_content in global_text:
                locs: List[int] = []
                pos = 0
                while True:
                    pos = global_text.find(target_content, pos)
                    if pos == -1:
                        break
                    line_num = global_text[:pos].count("\n") + 1
                    locs.append(line_num)
                    pos += len(target_content)
                locs_str = ", ".join(str(l) for l in locs)
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        f"Error: Target content not found in line range [{s_idx + 1}..{e_idx}], but found at line(s): {locs_str}."
                    ),
                )

            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    "Error: Target content not found in specified range."
                ),
            )

        if not allow_multiple and exact_count > 1:
            pos1 = window_text.find(target_content)
            line1 = s_idx + 1 + window_text[:pos1].count("\n")
            pos2 = window_text.find(target_content, pos1 + len(target_content))
            line2 = s_idx + 1 + window_text[:pos2].count("\n")
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: Target content matches multiple locations (lines {line1}, {line2}). Set allow_multiple=True or narrow start_line/end_line."
                ),
            )

        if allow_multiple:
            new_window_text = window_text.replace(target_content, replacement_content)
        else:
            new_window_text = window_text.replace(target_content, replacement_content, 1)

        new_lines = lines[:s_idx] + [new_window_text] + lines[e_idx:]
        new_content = "".join(new_lines)

        if new_content == content:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    "Error: No-op edit; target content and replacement content produce identical file."
                ),
                reminder=tool_provider.ToolReminder("No-op edits will fail."),
            )

        os.makedirs(os.path.dirname(disk_path), exist_ok=True)
        with open(disk_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        edit_mgr.record_file_edit(target_rw_file)
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(f"{warning}Successfully updated {target_file.relative_path}."),
            reminder=tool_provider.ToolReminder("Call check files to verify syntax and types."),
            suppression_key=tool_provider.SuppressionKey(str(target_file.relative_path)),
        )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        EditManager,
        keys=[EditManager, sandbox_file_editor.EditManager, InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        ReplaceFileContentTool,
        keys=[ReplaceFileContentTool, sandbox_file_editor.ReplaceFileContentTool, InTier[AgentSessionTier]],
        tier=agent_session,
    )

_initialize_ = __initialize__
