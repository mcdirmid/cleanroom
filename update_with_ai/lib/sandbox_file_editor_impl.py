import os
from typing import Optional, Set
from . import file_alias
from . import node_config
from . import sandbox_file_editor
from . import tool_provider
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class EditManager(sandbox_file_editor.EditManager, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._has_modifications = False

    def initialize(self) -> None:
        # Requirement: Unconditionally install text replacement tool and line update tool into tool manager
        tm = get_singleton(tool_provider.ToolManager)
        tm.install_tool(get_singleton(TextReplacementTool))
        tm.install_tool(get_singleton(LineUpdateTool))

    @property
    def has_modifications(self) -> bool:
        # Requirement: Track whether workspace files were modified during the session
        return self._has_modifications

    def record_modification(self) -> None:
        self._has_modifications = True

    def materialize_templates(self) -> None:
        # Requirement: Retrieve configured templates from node config, check existence via filesystem, and write template content to missing target files while preserving existing files
        cfg = get_singleton(node_config.NodeConfig)
        alias_mgr = get_singleton(file_alias.AliasManager)

        for bound_file, content in cfg.templates:
            host_path = os.path.join(alias_mgr.workspace_root.path, bound_file.workspace_path.path)
            if not os.path.exists(host_path):
                os.makedirs(os.path.dirname(host_path), exist_ok=True)
                with open(host_path, "w", encoding="utf-8") as f:
                    f.write(str(content))


class TextReplacementTool(sandbox_file_editor.TextReplacementTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "replace"

    @property
    def description(self) -> str:
        return "Replaces unique matching text in a read-write file."

    @property
    def file_alias_parameter(self) -> tool_provider.Parameter:
        alias_mgr = get_singleton(file_alias.AliasManager)
        return tool_provider.Parameter(
            name="file",
            description="Target file alias",
            parameter_converter=alias_mgr,
            is_required=True,
        )

    @property
    def target_text_parameter(self) -> tool_provider.Parameter:
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="target_text",
            description="Exact text to replace",
            parameter_converter=str_conv,
            is_required=True,
        )

    @property
    def replacement_text_parameter(self) -> tool_provider.Parameter:
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="replacement_text",
            description="Replacement text content",
            parameter_converter=str_conv,
            is_required=True,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {
            self.file_alias_parameter,
            self.target_text_parameter,
            self.replacement_text_parameter,
        }

    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        target_file = bindings_map.get("file")
        target_text = str(bindings_map.get("target_text", ""))
        replacement_text = str(bindings_map.get("replacement_text", ""))

        # Requirement: Executing editing tool with file alias that is not a read-write file fails
        if not isinstance(target_file, file_alias.ReadWriteFile):
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: {target_file} is not a read-write file.",
            )

        # Requirement: Fail if target text exceeds 100,000 characters
        if len(target_text) > 100000:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: target_text exceeds 100,000 characters limit.",
            )

        alias_mgr = get_singleton(file_alias.AliasManager)
        host_path = os.path.join(alias_mgr.workspace_root.path, target_file.workspace_path.path)

        # Requirement: Read file content using filesystem and fail if target text is not found
        with open(host_path, "r", encoding="utf-8") as f:
            content = f.read()

        count = content.count(target_text)
        if count == 0:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: target_text not found in file.",
            )
        # Requirement: Fail if target text matches multiple locations in file
        if count > 1:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: target_text matches {count} locations in file. It must be unique.",
            )

        # Requirement: Replace unique occurrence of target text, write using filesystem, and record file modifications
        new_content = content.replace(target_text, replacement_text, 1)
        with open(host_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        edit_mgr = get_singleton(EditManager)
        edit_mgr.record_modification()

        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content="Successfully replaced text.",
        )

class LineUpdateTool(sandbox_file_editor.LineUpdateTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "update_lines"

    @property
    def description(self) -> str:
        return "Updates or inserts lines in a read-write file."

    @property
    def file_alias_parameter(self) -> tool_provider.Parameter:
        alias_mgr = get_singleton(file_alias.AliasManager)
        return tool_provider.Parameter(
            name="file",
            description="Target file alias",
            parameter_converter=alias_mgr,
            is_required=True,
        )

    @property
    def start_line_parameter(self) -> tool_provider.Parameter:
        int_conv = get_singleton(tool_provider.IntegerParameterConverter)
        return tool_provider.Parameter(
            name="start_line",
            description="1-based starting line number",
            parameter_converter=int_conv,
            is_required=True,
        )

    @property
    def end_line_parameter(self) -> tool_provider.Parameter:
        int_conv = get_singleton(tool_provider.IntegerParameterConverter)
        return tool_provider.Parameter(
            name="end_line",
            description="1-based ending line number",
            parameter_converter=int_conv,
            is_required=True,
        )

    @property
    def replacement_text_parameter(self) -> tool_provider.Parameter:
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="replacement_text",
            description="Replacement text lines",
            parameter_converter=str_conv,
            is_required=True,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {
            self.file_alias_parameter,
            self.start_line_parameter,
            self.end_line_parameter,
            self.replacement_text_parameter,
        }

    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        target_file = bindings_map.get("file")
        start_line = int(bindings_map.get("start_line", 1))
        end_line = int(bindings_map.get("end_line", 1))
        replacement_text = str(bindings_map.get("replacement_text", ""))

        # Requirement: Executing editing tool with file alias that is not a read-write file fails
        if not isinstance(target_file, file_alias.ReadWriteFile):
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: {target_file} is not a read-write file.",
            )

        alias_mgr = get_singleton(file_alias.AliasManager)
        host_path = os.path.join(alias_mgr.workspace_root.path, target_file.workspace_path.path)

        # Requirement: Read file content using filesystem and fail if start line is less than 1 or exceeds total line count plus 1
        with open(host_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
        if start_line < 1 or start_line > total_lines + 1:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: start_line {start_line} out of bounds (1..{total_lines + 1}).",
            )

        rep_lines = [l + "\n" if not l.endswith("\n") else l for l in replacement_text.splitlines()]
        if not replacement_text.endswith("\n") and rep_lines:
            rep_lines[-1] = rep_lines[-1].rstrip("\n")

        if start_line <= end_line:
            # Requirement: When start line is less than or equal to end line, fail if end line exceeds total line count
            if end_line > total_lines:
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: end_line {end_line} exceeds total lines {total_lines}.",
                )
            # Requirement: When start line is less than or equal to end line, replace lines within range, write using filesystem, and record file modifications
            new_lines = lines[: start_line - 1] + rep_lines + lines[end_line:]
        else:
            # Requirement: When start line exceeds end line, insert replacement lines before start line, write using filesystem, and record file modifications
            new_lines = lines[: start_line - 1] + rep_lines + lines[start_line - 1 :]

        with open(host_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        edit_mgr = get_singleton(EditManager)
        edit_mgr.record_modification()

        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content="Successfully updated lines.",
        )

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        EditManager,
        keys=[EditManager, sandbox_file_editor.EditManager],
        tier="agent_session",
    )
    reg.register_singleton(
        TextReplacementTool,
        keys=[
            TextReplacementTool,
            sandbox_file_editor.TextReplacementTool,
            sandbox_file_editor.EditingTool,
            tool_provider.Tool,
        ],
        tier="agent_session",
    )
    reg.register_singleton(
        LineUpdateTool,
        keys=[
            LineUpdateTool,
            sandbox_file_editor.LineUpdateTool,
            sandbox_file_editor.EditingTool,
            tool_provider.Tool,
        ],
        tier="agent_session",
    )
