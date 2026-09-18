import difflib
import os
import subprocess
from typing import Optional, Set
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.agent.lib import agent_node_config
from . import sandbox_file_editor
from . import template_format
from . import tool_provider
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib.agent_session import agent_session


class EditManager(sandbox_file_editor.EditManager, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._initial_contents: dict[str, Optional[str]] = {}
        self._file_update_revision: int = 0
        self._locked_files: set[agent_file_alias.ReadWriteFile] = set()
        self._last_read_or_edited_file: Optional[agent_file_alias.FileAlias] = None

    @property
    def locked_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        # Requirement: The edit manager exposes read-write files locked against modification.
        # Requirement: [EditManager] The edit manager exposes read-write files locked against modification.
        return set(self._locked_files)

    def lock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        # Requirement: The edit manager supports locking individual read-write files against modification.
        # Requirement: [EditManager] The edit manager supports locking individual read-write files against modification.
        self._locked_files.add(file)

    def unlock_file(self, file: agent_file_alias.ReadWriteFile) -> None:
        # Requirement: The edit manager supports unlocking individual read-write files.
        # Requirement: [EditManager] The edit manager supports unlocking individual read-write files.
        self._locked_files.discard(file)

    def initialize(self) -> None:
        # Requirement: The edit manager unconditionally installs the replace file content tool into the tool manager.
        # Requirement: [EditManager] The edit manager installs the replace file content tool.
        tm = get_singleton(tool_provider.ToolManager)
        tm.install_tool(get_singleton(ReplaceFileContentTool))

    def record_initial_content(
        self, host_path: str, content: Optional[str] = None
    ) -> None:
        if host_path not in self._initial_contents:
            if content is not None:
                self._initial_contents[host_path] = content
            elif os.path.exists(host_path):
                try:
                    with open(host_path, "r", encoding="utf-8") as f:
                        self._initial_contents[host_path] = f.read()
                except OSError:
                    self._initial_contents[host_path] = None
            else:
                self._initial_contents[host_path] = None

    @property
    def has_modifications(self) -> bool:
        # Requirement: The edit manager exposes whether workspace file modifications occurred during the session by comparing current workspace file content against initial content before editing.
        for host_path, initial in self._initial_contents.items():
            if not os.path.exists(host_path):
                if initial is not None:
                    return True
            else:
                if initial is None:
                    return True
                try:
                    with open(host_path, "r", encoding="utf-8") as f:
                        current = f.read()
                    if current != initial:
                        return True
                except OSError:
                    return True
        return False

    @property
    def file_update_revision(self) -> int:
        # Requirement: The edit manager tracks a file update revision that increments whenever workspace files are updated.
        return self._file_update_revision

    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        # Requirement: The edit manager tracks the last read or edited file alias across the session, recording file reads from the file reader and file edits from editing tools.
        # Requirement: [EditManager] The edit manager tracks the last read or edited file across the session, recording file reads from file readers and file edits from editing tools.
        return self._last_read_or_edited_file

    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        self._last_read_or_edited_file = file

    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        self._last_read_or_edited_file = file

    def record_modification(self, host_path: Optional[str] = None) -> None:
        self._file_update_revision += 1
        if host_path is not None:
            self.record_initial_content(host_path)

    def materialize_templates(self) -> None:
        # Requirement: Materializing templates retrieves configured templates from the node config, formats initial template content using the template formatter with session template parameters, checks whether target files exist in the filesystem at the host path formed from the alias manager workspace root and the read-write file workspace path, and writes formatted template content for missing files while preserving existing files.
        # Requirement: [EditManager] Materializing templates populates missing read-write files with initial template content without overwriting existing files.
        cfg = get_singleton(agent_node_config.NodeConfig)
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        formatter = get_singleton(template_format.TemplateFormatter)

        materialized_paths: list[str] = []
        for bound_file, content in cfg.templates:
            host_path = os.path.join(
                alias_mgr.workspace_root.path, bound_file.workspace_path.path
            )
            if not os.path.exists(host_path):
                os.makedirs(os.path.dirname(host_path), exist_ok=True)
                formatted_content = formatter.format_template(
                    str(content), cfg.template_parameters
                )
                with open(host_path, "w", encoding="utf-8") as f:
                    f.write(formatted_content)
                materialized_paths.append(host_path)

        if materialized_paths:
            for check in getattr(cfg, "verification_checks", []):
                try:
                    check.verify()
                except (subprocess.SubprocessError, OSError, RuntimeError):
                    pass

        for host_path in materialized_paths:
            try:
                with open(host_path, "r", encoding="utf-8") as f:
                    actual_content = f.read()
            except OSError:
                actual_content = None
            self.record_initial_content(host_path, actual_content)


class _OrderedParameterSet(set[tool_provider.Parameter]):
    def __init__(self, items: tuple[tool_provider.Parameter, ...]) -> None:
        super().__init__(items)
        self._items = items

    def __iter__(self):
        return iter(self._items)


class ReplaceFileContentTool(sandbox_file_editor.ReplaceFileContentTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        # Requirement: The replace file content tool is named `replace_file_content`.
        return "replace_file_content"

    @property
    def description(self) -> str:
        return (
            "Replaces target content in a read-write file within an optional line range. "
            "Edits must be small and targeted (such as a single function, method, or class at a time); "
            "whole-file or monolithic replacements are prohibited."
        )

    @property
    def file_alias_parameter(self) -> tool_provider.Parameter:
        # Requirement: The replace file content tool path parameter uses the alias manager to convert a file alias.
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.Parameter(
            name="path",
            description="Target file alias (optional; defaults to the last file read or edited in the session)",
            parameter_converter=alias_mgr,
            is_required=False,
        )

    @property
    def target_content_parameter(self) -> tool_provider.Parameter:
        # Requirement: The replace file content tool target content parameter uses a string parameter converter to accept text.
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="target_content",
            description="Exact text to replace",
            parameter_converter=str_conv,
            is_required=True,
        )

    @property
    def replacement_content_parameter(self) -> tool_provider.Parameter:
        # Requirement: The replace file content tool replacement content parameter uses a string parameter converter to accept text.
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="replacement_content",
            description="Replacement text content",
            parameter_converter=str_conv,
            is_required=True,
        )

    @property
    def start_line_parameter(self) -> tool_provider.Parameter:
        # Requirement: The replace file content tool start line parameter uses an integer parameter converter to accept an integer.
        int_conv = get_singleton(tool_provider.IntegerParameterConverter)
        return tool_provider.Parameter(
            name="start_line",
            description="Optional 1-based starting line number (inclusive)",
            parameter_converter=int_conv,
            is_required=False,
        )

    @property
    def end_line_parameter(self) -> tool_provider.Parameter:
        # Requirement: The replace file content tool end line parameter uses an integer parameter converter to accept an integer.
        int_conv = get_singleton(tool_provider.IntegerParameterConverter)
        return tool_provider.Parameter(
            name="end_line",
            description="Optional 1-based ending line number (inclusive)",
            parameter_converter=int_conv,
            is_required=False,
        )

    @property
    def allow_multiple_parameter(self) -> tool_provider.Parameter:
        # Requirement: The replace file content tool allow multiple parameter uses a boolean parameter converter to accept a boolean.
        bool_conv = get_singleton(tool_provider.BooleanParameterConverter)
        return tool_provider.Parameter(
            name="allow_multiple",
            description="Whether to allow replacing multiple occurrences (defaults to false)",
            parameter_converter=bool_conv,
            is_required=False,
        )
    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return _OrderedParameterSet(
            (
                self.file_alias_parameter,
                self.start_line_parameter,
                self.end_line_parameter,
                self.allow_multiple_parameter,
                self.target_content_parameter,
                self.replacement_content_parameter,
            )
        )

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        target_file = bindings_map.get("path")
        target_content = str(bindings_map.get("target_content", ""))
        replacement_content = str(bindings_map.get("replacement_content", ""))
        start_line: Optional[int] = (
            int(bindings_map["start_line"]) if "start_line" in bindings_map else None
        )
        end_line: Optional[int] = (
            int(bindings_map["end_line"]) if "end_line" in bindings_map else None
        )
        allow_multiple: bool = (
            bool(bindings_map["allow_multiple"])
            if "allow_multiple" in bindings_map
            else False
        )

        edit_mgr = get_singleton(EditManager)
        is_implicit_path = False
        if target_file is None:
            last_file = edit_mgr.last_read_or_edited_file
            if last_file is None:
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content="Error: 'path' was not specified and no file has been read or edited yet in this session.",
                    suppression_key="replace_file_content",
                )
            if not isinstance(last_file, agent_file_alias.ReadWriteFile):
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: 'path' was not specified and the last accessed file '{last_file.relative_path}' is not a read-write file.",
                    reminder="Only declared read-write files can be modified.",
                    suppression_key="replace_file_content",
                )
            target_file = last_file
            is_implicit_path = True
        elif not isinstance(target_file, agent_file_alias.ReadWriteFile):
            # Requirement: Before modifying a file, editing tool execution fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.
            # Requirement: Editing tool responses share a constant suppression key replace_file_content.
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: {target_file} is not a read-write file.",
                reminder="Only declared read-write files can be modified.",
                suppression_key="replace_file_content",
            )

        # Requirement: Before modifying a file, editing tool execution fails if the file alias is locked against modification, reminding the agent that files that have been the target of a submit, fail, or blame cannot be modified.
        if target_file in edit_mgr.locked_files:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: `{target_file.relative_path}` has been locked against further modification.",
                reminder="Files that have been the target of a submit, fail, or blame cannot be modified.",
                suppression_key="replace_file_content",
            )

        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        host_path = os.path.join(
            alias_mgr.workspace_root.path, target_file.workspace_path.path
        )

        # Requirement: Replace file content tool execution reads the file content from the filesystem, treating missing files as empty.
        if not os.path.exists(host_path):
            content = ""
        else:
            with open(host_path, "r", encoding="utf-8") as f:
                content = f.read()

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        # Requirement: When a start line is provided, execution fails if the start line is less than one or exceeds the total line count plus one.
        if start_line is not None:
            if start_line < 1 or start_line > total_lines + 1:
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: start_line {start_line} out of bounds (1..{total_lines + 1}).",
                    suppression_key="replace_file_content",
                )

        # Requirement: When an end line is provided, execution fails if the end line is less than one or exceeds the total line count.
        if end_line is not None:
            if end_line < 1 or end_line > total_lines:
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: end_line {end_line} out of bounds (1..{total_lines}).",
                    suppression_key="replace_file_content",
                )

        # Requirement: When both start line and end line are provided, execution fails if the start line exceeds the end line.
        if start_line is not None and end_line is not None:
            if start_line > end_line:
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: start_line ({start_line}) cannot be greater than end_line ({end_line}).",
                    suppression_key="replace_file_content",
                )

        s_idx = (start_line - 1) if start_line is not None else 0
        e_idx = end_line if end_line is not None else total_lines

        prefix = "".join(lines[:s_idx])
        region = "".join(lines[s_idx:e_idx])
        suffix = "".join(lines[e_idx:])

        count = region.count(target_content)

        # Requirement: When allow multiple is not set or false, execution fails if the target content is not found within the designated line range or matches multiple locations within the designated line range, and on success replaces the single matching occurrence.
        # Requirement: When allow multiple is true, execution fails if the target content is not found within the designated line range, and replaces all occurrences of the target content within the designated line range.
        if count == 0:
            if start_line is not None or end_line is not None:
                full_count = content.count(target_content)
                if full_count > 0:
                    # Requirement: When target content is not found within the designated line range but exists elsewhere in the file, failure feedback indicates the line numbers where the target content was located.
                    first_idx = content.find(target_content)
                    actual_start_line = content[:first_idx].count("\n") + 1
                    actual_end_line = actual_start_line + target_content.count("\n")
                    line_desc = (
                        f"lines {actual_start_line}-{actual_end_line}"
                        if actual_end_line > actual_start_line
                        else f"line {actual_start_line}"
                    )
                    return tool_provider.Response(
                        is_failed=True,
                        is_terminated=False,
                        content=(
                            f"Error: target_content not found in specified line range [{s_idx + 1}, {e_idx}]. "
                            f"target_content exists at {line_desc} in '{target_file.relative_path}'. "
                            f"Update start_line/end_line to include {line_desc}, or omit start_line and end_line."
                        ),
                        suppression_key="replace_file_content",
                    )
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: target_content not found in specified line range [{s_idx + 1}, {e_idx}].",
                    suppression_key="replace_file_content",
                    follow_up_tool_call=tool_provider.FollowUpToolCall(
                        tool_name="view_file",
                        wire_parameter_bindings=tool_provider.WireParameterBindings(
                            bindings={("path", target_file.relative_path)}
                        ),
                        reasoning_text=f"Target content not found in '{target_file.relative_path}'. Let me view the current file content to see the exact lines to replace.",
                    ),
                )
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: target_content not found in file.",
                suppression_key="replace_file_content",
                follow_up_tool_call=tool_provider.FollowUpToolCall(
                    tool_name="view_file",
                    wire_parameter_bindings=tool_provider.WireParameterBindings(
                        bindings={("path", target_file.relative_path)}
                    ),
                    reasoning_text=f"Target content not found in '{target_file.relative_path}'. Let me view the current file content to see the exact lines to replace.",
                ),
            )

        if not allow_multiple and count > 1:
            if start_line is not None or end_line is not None:
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: target_content matches {count} locations in line range [{s_idx + 1}, {e_idx}]. Set allow_multiple=true or narrow the line range.",
                    suppression_key="replace_file_content",
                )
            # Requirement: When target content matches multiple locations in the file and allow multiple is false, failure feedback indicates the first two matching line numbers to assist in narrowing the replacement region and instructs the agent to include more surrounding lines in target_content or specify start_line and end_line.
            first_idx = region.find(target_content)
            second_idx = region.find(
                target_content, first_idx + len(target_content)
            )
            first_line = content[:first_idx].count("\n") + 1
            second_line = content[:second_idx].count("\n") + 1
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=(
                    f"Error: target_content matches {count} locations in file (first at line {first_line}, then at line {second_line}). "
                    "Include more surrounding lines in target_content to make it unique, or specify start_line and end_line."
                ),
                suppression_key="replace_file_content",
            )

        if allow_multiple:
            new_region = region.replace(target_content, replacement_content)
        else:
            new_region = region.replace(target_content, replacement_content, 1)

        new_content = prefix + new_region + suffix

        # Requirement: Before modifying a file, editing tool execution fails if the edit produces no change to file content, reminding the agent that the edit had no effect and such edits will fail.
        if new_content == content:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: replacement produced no change to file content.",
                reminder="The edit had no effect, and such edits will fail.",
                suppression_key="replace_file_content",
            )

        edit_mgr = get_singleton(EditManager)
        edit_mgr.record_initial_content(host_path, content)

        # Requirement: On successful execution, an editing tool writes the updated file content to the filesystem, records that workspace file modifications occurred, and reminds the agent to call the check file tool to verify syntax and type correctness before making further modifications.
        # Requirement: On success, the tool writes the updated file content to the filesystem, creating any missing parent directories, and records that workspace file modifications occurred.
        # Requirement: [EditManager] Modifying a file records that workspace file modifications occurred during the session.
        os.makedirs(os.path.dirname(host_path), exist_ok=True)
        with open(host_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        edit_mgr.record_modification(host_path)
        edit_mgr.record_file_edit(target_file)

        try:
            cfg = get_singleton(agent_config.AgentConfig)
            delta_output = cfg.edit_delta_output
        except (LookupError, KeyError, AttributeError):
            delta_output = True

        content_msg = "Successfully replaced content."
        if delta_output:
            # Requirement: When configured to produce delta output, successful editing tool execution includes a diff delta representation in the response content.
            diff_lines = list(
                difflib.unified_diff(
                    content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"a/{target_file.relative_path}",
                    tofile=f"b/{target_file.relative_path}",
                )
            )
            diff_text = "".join(diff_lines)
            content_msg = f"Successfully replaced content.\n\n```diff\n{diff_text}```"

        if is_implicit_path:
            content_msg = (
                f"Warning: 'path' was not specified; implicitly editing last accessed file '{target_file.relative_path}'.\n\n{content_msg}"
            )

        # Requirement: Editing tool responses share a constant suppression key replace_file_content.
        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content=content_msg,
            reminder=f"Call check_file(path='{target_file.relative_path}') to verify syntax and type correctness before making further modifications.",
            suppression_key="replace_file_content",
            follow_up_tool_call=None,
        )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        EditManager,
        keys=[EditManager, sandbox_file_editor.EditManager],
        tier=agent_session,
    )
    reg.register_singleton(
        ReplaceFileContentTool,
        keys=[
            ReplaceFileContentTool,
            sandbox_file_editor.ReplaceFileContentTool,
            sandbox_file_editor.EditingTool,
            tool_provider.Tool,
        ],
        tier=agent_session,
    )
