# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T06:00:32Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 39d19ccff5fc
# COVERAGE_AUDIT: 2026-10-05T04:28:01Z
# QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

# Requirements specified in sandbox_file_editor_impl.pyi
import difflib
import hashlib
import os
from typing import Any, Mapping, Optional, Set, Union, cast
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.agent.lib import agent_node_config
from . import sandbox_file_editor
from . import tool_provider
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from support.lib import src_metadata
from update_with_ai.parts.agent.lib.agent_session import agent_session


def _make_tool_response(
    is_failed: bool,
    is_terminated: bool,
    content: str,
    reminder: Optional[str] = None,
    suppression_key: Optional[str] = None,
    follow_up_tool_call: Optional[tool_provider.FollowUpToolCall] = None,
) -> tool_provider.ToolResponse:
    return tool_provider.ToolResponse(
        is_failed=is_failed,
        is_terminated=is_terminated,
        content=tool_provider.ToolResponseContent(content),
        reminder=tool_provider.ToolReminder(reminder) if reminder is not None else None,
        suppression_key=tool_provider.SuppressionKey(suppression_key)
        if suppression_key is not None
        else None,
        follow_up_tool_call=follow_up_tool_call,
    )


class EditManager(sandbox_file_editor.EditManager, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._file_update_revision: int = 0
        self._last_read_or_edited_file: Optional[agent_file_alias.FileAlias] = None

    def initialize(self) -> None:
        tm = get_singleton(tool_provider.ToolManager)
        try:
            cfg = get_singleton(agent_config.AgentConfig)
            is_mcp = cfg.is_mcp_mode
        except (
            LookupError,
            KeyError,
        ):  # pragma: no cover (assumption: standard non-mcp session)
            is_mcp = False
        if not is_mcp:
            tm.install_tool(get_singleton(ReplaceFileContentTool))

    def can_write(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        target_file = (
            path
            if isinstance(path, agent_file_alias.FileAlias)
            else alias_mgr.convert(path)
        )

        if not isinstance(target_file, agent_file_alias.ReadWriteFile):
            file_name = (
                target_file.relative_path
                if isinstance(target_file, agent_file_alias.FileAlias)
                else str(target_file)
            )
            return _make_tool_response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: File '{file_name}' is not a declared read-write file.",
                reminder="Only declared read-write files can be modified.",
            )

        self.record_file_edit(target_file)
        return _make_tool_response(
            is_failed=False,
            is_terminated=False,
            content=f"Modification permitted for '{target_file.relative_path}'.",
        )

    @property
    def has_modifications(self) -> bool:
        # Requirement: The edit manager exposes whether workspace file writes occurred during the session by comparing current workspace file content against their in-band code hash.
        # Requirement: [EditManager] The edit manager exposes whether workspace file writes occurred during the session, determined by whether workspace file contents differ from their in-band code hash.
        try:
            n_cfg = get_singleton(agent_node_config.NodeConfig)
            alias_mgr = get_singleton(agent_file_alias.AliasManager)
            for rw_file in getattr(n_cfg, "read_write_files", []):
                host_path = os.path.join(
                    alias_mgr.workspace_root.path, rw_file.workspace_path.path
                )
                if not os.path.exists(host_path):
                    continue
                if src_metadata.is_code_modified(host_path):
                    return True
        except (
            LookupError,
            KeyError,
            OSError,
        ):  # pragma: no cover (assumption: session singletons present)
            pass
        return False

    def file_hash(
        self, file: agent_file_alias.FileAlias
    ) -> sandbox_file_editor.FileHash:
        try:
            alias_mgr = get_singleton(agent_file_alias.AliasManager)
            target_file = (
                file
                if isinstance(file, agent_file_alias.FileAlias)
                else alias_mgr.convert(file)
            )
            if not isinstance(target_file, agent_file_alias.BoundFile):
                return sandbox_file_editor.FileHash(hashlib.md5(b"").hexdigest())
            host_path = os.path.join(
                alias_mgr.workspace_root.path, target_file.workspace_path.path
            )
            if not os.path.exists(host_path):
                return sandbox_file_editor.FileHash(hashlib.md5(b"").hexdigest())
            with open(host_path, "rb") as f:
                return sandbox_file_editor.FileHash(hashlib.md5(f.read()).hexdigest())
        except (LookupError, KeyError, OSError):
            return sandbox_file_editor.FileHash(hashlib.md5(b"").hexdigest())

    @property
    def file_update_revision(self) -> sandbox_file_editor.FileUpdateRevision:
        return sandbox_file_editor.FileUpdateRevision(self._file_update_revision)

    @property
    def last_read_or_edited_file(self) -> Optional[agent_file_alias.FileAlias]:
        return self._last_read_or_edited_file

    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        self._last_read_or_edited_file = file

    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        self._last_read_or_edited_file = file

    def record_modification(self, host_path: Optional[str] = None) -> None:
        self._file_update_revision += 1


def _target_content_missing_message(
    supplied_parameters: Set[tool_provider.ParameterName],
) -> tool_provider.MissingMessage:
    if (
        tool_provider.ParameterName("start_line") in supplied_parameters
        or tool_provider.ParameterName("end_line") in supplied_parameters
    ):
        return tool_provider.MissingMessage(
            "start_line and end_line only restrict the search window; target_content is mandatory."
        )
    return tool_provider.MissingMessage(
        "replace_file_content requires existing target_content to match against. "
        "To append or insert text, provide the existing surrounding text in target_content "
        "and include both the existing text and new content in replacement_content."
    )


class ReplaceFileContentTool(sandbox_file_editor.ReplaceFileContentTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> tool_provider.ToolName:
        return tool_provider.ToolName("replace_file_content")

    @property
    def description(self) -> tool_provider.ToolDescription:
        return tool_provider.ToolDescription(
            "Replaces target content in a read-write file within an optional line range "
            "(start_line and end_line restrict the search window). "
            "Edits must be small and targeted (such as a single function, method, or class at a time); "
            "whole-file or monolithic replacements are prohibited."
        )

    @property
    def path_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.ToolParameter(
            name=tool_provider.ParameterName("path"),
            description=tool_provider.ParameterDescription(
                "Target file alias (optional; defaults to the last file read or edited in the session)"
            ),
            parameter_type=alias_mgr,
            is_required=False,
        )

    @property
    def target_content_parameter(
        self,
    ) -> tool_provider.ToolParameter[sandbox_file_editor.TargetContent, str]:
        return tool_provider.ToolParameter(
            name=tool_provider.ParameterName("target_content"),
            description=tool_provider.ParameterDescription(
                "Exact text to replace within the file (or within start_line and end_line search window if provided). This parameter is always required."
            ),
            parameter_type=cast(
                tool_provider.ParameterType[sandbox_file_editor.TargetContent, str],
                tool_provider.STRING_PARAMETER_TYPE,
            ),
            is_required=True,
            missing_message=_target_content_missing_message,
        )

    @property
    def replacement_content_parameter(
        self,
    ) -> tool_provider.ToolParameter[sandbox_file_editor.ReplacementContent, str]:
        return tool_provider.ToolParameter(
            name=tool_provider.ParameterName("replacement_content"),
            description=tool_provider.ParameterDescription("Replacement text content"),
            parameter_type=cast(
                tool_provider.ParameterType[
                    sandbox_file_editor.ReplacementContent, str
                ],
                tool_provider.STRING_PARAMETER_TYPE,
            ),
            is_required=True,
        )

    @property
    def start_line_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[sandbox_file_editor.LineNumber], int]:
        return tool_provider.ToolParameter(
            name=tool_provider.ParameterName("start_line"),
            description=tool_provider.ParameterDescription(
                "Optional 1-based starting line number of the search window (inclusive). Note: target_content is still required and searched for within this range."
            ),
            parameter_type=cast(
                tool_provider.ParameterType[
                    Optional[sandbox_file_editor.LineNumber], int
                ],
                tool_provider.INTEGER_PARAMETER_TYPE,
            ),
            is_required=False,
        )

    @property
    def end_line_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[sandbox_file_editor.LineNumber], int]:
        return tool_provider.ToolParameter(
            name=tool_provider.ParameterName("end_line"),
            description=tool_provider.ParameterDescription(
                "Optional 1-based ending line number of the search window (inclusive). Note: target_content is still required and searched for within this range."
            ),
            parameter_type=cast(
                tool_provider.ParameterType[
                    Optional[sandbox_file_editor.LineNumber], int
                ],
                tool_provider.INTEGER_PARAMETER_TYPE,
            ),
            is_required=False,
        )

    @property
    def allow_multiple_parameter(
        self,
    ) -> tool_provider.ToolParameter[sandbox_file_editor.AllowMultiple, bool]:
        return tool_provider.ToolParameter(
            name=tool_provider.ParameterName("allow_multiple"),
            description=tool_provider.ParameterDescription(
                "Whether to allow replacing multiple occurrences (defaults to false)"
            ),
            parameter_type=cast(
                tool_provider.ParameterType[sandbox_file_editor.AllowMultiple, bool],
                tool_provider.BOOLEAN_PARAMETER_TYPE,
            ),
            is_required=False,
        )

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return {
            self.path_parameter.name: self.path_parameter,
            self.start_line_parameter.name: self.start_line_parameter,
            self.end_line_parameter.name: self.end_line_parameter,
            self.allow_multiple_parameter.name: self.allow_multiple_parameter,
            self.target_content_parameter.name: self.target_content_parameter,
            self.replacement_content_parameter.name: self.replacement_content_parameter,
        }

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        target_file = actual_parameter_bindings.get(self.path_parameter)
        target_content = str(
            actual_parameter_bindings.get(self.target_content_parameter) or ""
        )
        replacement_content = str(
            actual_parameter_bindings.get(self.replacement_content_parameter) or ""
        )
        start_line_val = actual_parameter_bindings.get(self.start_line_parameter)
        start_line: Optional[int] = (
            int(cast(Any, start_line_val)) if start_line_val is not None else None
        )
        end_line_val = actual_parameter_bindings.get(self.end_line_parameter)
        end_line: Optional[int] = (
            int(cast(Any, end_line_val)) if end_line_val is not None else None
        )
        allow_multiple_val = actual_parameter_bindings.get(
            self.allow_multiple_parameter
        )
        allow_multiple: bool = (
            bool(allow_multiple_val) if allow_multiple_val is not None else False
        )

        edit_mgr = get_singleton(EditManager)
        is_implicit_path = False
        # Requirement: Tool execution implicitly binds the target file to the last file read or edited in the edit manager if that file is a read-write file, informs the agent with a warning in the response content that the path was implicitly bound while allowing the tool execution to proceed, or fails if no file has been read or edited or if the last read or edited file is not a read-write file, when the path parameter is omitted.
        if target_file is None:
            last_file = edit_mgr.last_read_or_edited_file
            if last_file is None:
                return _make_tool_response(
                    is_failed=True,
                    is_terminated=False,
                    content="Error: 'path' was not specified and no file has been read or edited yet in this session.",
                    suppression_key="replace_file_content",
                )
            if not isinstance(last_file, agent_file_alias.ReadWriteFile):
                return _make_tool_response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: 'path' was not specified and the last accessed file '{last_file.relative_path}' is not a read-write file.",
                    reminder="Only declared read-write files can be modified.",
                    suppression_key="replace_file_content",
                )
            target_file = last_file
            is_implicit_path = True
        elif not isinstance(target_file, agent_file_alias.ReadWriteFile):
            return _make_tool_response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: {target_file} is not a read-write file.",
                reminder="Only declared read-write files can be modified.",
                suppression_key="replace_file_content",
            )
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        host_path = os.path.join(
            alias_mgr.workspace_root.path, target_file.workspace_path.path
        )

        if not os.path.exists(host_path):
            content = ""
        else:
            with open(host_path, "r", encoding="utf-8") as f:
                content = f.read()

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        if start_line is not None:
            if start_line < 1 or start_line > total_lines + 1:
                return _make_tool_response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: start_line {start_line} out of bounds (1..{total_lines + 1}).",
                    suppression_key="replace_file_content",
                )

        if end_line is not None:
            if end_line < 1 or end_line > total_lines:
                return _make_tool_response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: end_line {end_line} out of bounds (1..{total_lines}).",
                    suppression_key="replace_file_content",
                )

        if start_line is not None and end_line is not None:
            if start_line > end_line:
                return _make_tool_response(
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

        fuzzy_matched = False
        new_region = ""
        if count == 0 and not allow_multiple:
            region_lines = lines[s_idx:e_idx]
            target_lines = [l.strip() for l in target_content.splitlines()]
            if target_lines and len(region_lines) >= len(target_lines):
                matches = []
                for i in range(len(region_lines) - len(target_lines) + 1):
                    cand_lines = [
                        l.strip() for l in region_lines[i : i + len(target_lines)]
                    ]
                    if cand_lines == target_lines:
                        matches.append(i)
                if len(matches) == 1:
                    match_idx = matches[0]
                    matched_start_char = sum(
                        len(line) for line in region_lines[:match_idx]
                    )
                    matched_end_char = sum(
                        len(line)
                        for line in region_lines[: match_idx + len(target_lines)]
                    )
                    new_region = (
                        region[:matched_start_char]
                        + replacement_content
                        + region[matched_end_char:]
                    )
                    fuzzy_matched = True

        if count == 0 and not fuzzy_matched:
            if start_line is not None or end_line is not None:
                full_count = content.count(target_content)
                if full_count > 0:
                    first_idx = content.find(target_content)
                    actual_start_line = content[:first_idx].count("\n") + 1
                    actual_end_line = actual_start_line + target_content.count("\n")
                    line_desc = (
                        f"lines {actual_start_line}-{actual_end_line}"
                        if actual_end_line > actual_start_line
                        else f"line {actual_start_line}"
                    )
                    return _make_tool_response(
                        is_failed=True,
                        is_terminated=False,
                        content=(
                            f"Error: target_content not found in specified line range [{s_idx + 1}, {e_idx}]. "
                            f"target_content exists at {line_desc} in '{target_file.relative_path}'. "
                            f"Update start_line/end_line to include {line_desc}, or omit start_line and end_line."
                        ),
                        suppression_key="replace_file_content",
                    )
                return _make_tool_response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: target_content not found in specified line range [{s_idx + 1}, {e_idx}].",
                    suppression_key="replace_file_content",
                )
            return _make_tool_response(
                is_failed=True,
                is_terminated=False,
                content="Error: target_content not found in file.",
                suppression_key="replace_file_content",
            )

        if not allow_multiple and count > 1:
            if start_line is not None or end_line is not None:
                return _make_tool_response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: target_content matches {count} locations in line range [{s_idx + 1}, {e_idx}]. Set allow_multiple=true or narrow the line range.",
                    suppression_key="replace_file_content",
                )
            first_idx = region.find(target_content)
            second_idx = region.find(target_content, first_idx + len(target_content))
            first_line = content[:first_idx].count("\n") + 1
            second_line = content[:second_idx].count("\n") + 1
            return _make_tool_response(
                is_failed=True,
                is_terminated=False,
                content=(
                    f"Error: target_content matches {count} locations in file (first at line {first_line}, then at line {second_line}). "
                    "Include more surrounding lines in target_content to make it unique, or specify start_line and end_line."
                ),
                suppression_key="replace_file_content",
            )

        if fuzzy_matched:
            pass
        elif allow_multiple:
            new_region = region.replace(target_content, replacement_content)
        else:
            new_region = region.replace(target_content, replacement_content, 1)

        new_content = prefix + new_region + suffix

        if new_content == content:
            return _make_tool_response(
                is_failed=True,
                is_terminated=False,
                content="Error: replacement produced no change to file content.",
                reminder="The edit had no effect, and such edits will fail.",
                suppression_key="replace_file_content",
            )

        edit_mgr = get_singleton(EditManager)

        os.makedirs(os.path.dirname(host_path), exist_ok=True)
        with open(host_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        edit_mgr.record_modification(host_path)
        edit_mgr.record_file_edit(target_file)

        try:
            cfg = get_singleton(agent_config.AgentConfig)
            delta_output = cfg.edit_delta_output
        except (
            LookupError,
            KeyError,
            AttributeError,
        ):  # pragma: no cover (assumption: standard non-mcp session)
            delta_output = True

        content_msg = "Successfully replaced content."
        if delta_output:
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
            content_msg = f"Warning: 'path' was not specified; implicitly editing last accessed file '{target_file.relative_path}'.\n\n{content_msg}"

        return _make_tool_response(
            is_failed=False,
            is_terminated=False,
            content=content_msg,
            reminder="Call check_files() to verify syntax and type correctness after completing edits.",
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
