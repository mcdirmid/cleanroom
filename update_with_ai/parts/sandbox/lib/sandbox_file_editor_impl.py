import os
from typing import Optional, Set
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


class EditManager(sandbox_file_editor.EditManager, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._initial_contents: dict[str, Optional[str]] = {}
        self._file_update_revision: int = 0

    def initialize(self) -> None:
        # Requirement: The edit manager unconditionally installs the text replacement tool and line update tool into the tool manager.
        # Requirement: [EditManager] The edit manager installs the text replacement tool and line update tool.
        tm = get_singleton(tool_provider.ToolManager)
        tm.install_tool(get_singleton(TextReplacementTool))
        tm.install_tool(get_singleton(LineUpdateTool))

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
                self.record_initial_content(host_path, formatted_content)


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
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
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

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        target_file = bindings_map.get("file")
        target_text = str(bindings_map.get("target_text", ""))
        replacement_text = str(bindings_map.get("replacement_text", ""))

        # Requirement: Before modifying a file, editing tool execution fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.
        if not isinstance(target_file, agent_file_alias.ReadWriteFile):
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: {target_file} is not a read-write file.",
                reminder="Only declared read-write files can be modified.",
            )

        # Requirement: Executing the text replacement tool fails if the target text exceeds 100,000 characters, and reminds the agent that target text for replacement must not exceed 100,000 characters.
        if len(target_text) > 100000:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: target_text exceeds 100,000 characters limit.",
                reminder="Target text for replacement must not exceed 100,000 characters.",
            )

        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        host_path = os.path.join(
            alias_mgr.workspace_root.path, target_file.workspace_path.path
        )

        # Requirement: Executing the text replacement tool reads file content using the filesystem, treating missing files as empty.
        # Requirement: Executing the text replacement tool fails if the target text is not found in the file content.
        if not os.path.exists(host_path):
            content = ""
        else:
            with open(host_path, "r", encoding="utf-8") as f:
                content = f.read()

        count = content.count(target_text)
        if count == 0:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: target_text not found in file.",
            )
        # Requirement: Executing the text replacement tool fails if the target text matches multiple locations in the file.
        if count > 1:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: target_text matches {count} locations in file. It must be unique.",
            )

        edit_mgr = get_singleton(EditManager)
        edit_mgr.record_initial_content(host_path, content)

        # Requirement: On successful text replacement tool execution, the unique occurrence of the target text is replaced with the replacement text, written using the filesystem, and file modifications are recorded.
        # Requirement: [EditManager] Modifying a file records that workspace file modifications occurred during the session.
        new_content = content.replace(target_text, replacement_text, 1)
        # Requirement: Before modifying a file, editing tool execution fails if the edit produces no change to file content, reminding the agent that the edit had no effect and such edits will fail.
        if new_content == content:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: replacement produced no change to file content.",
                reminder="The edit had no effect, and such edits will fail.",
            )

        os.makedirs(os.path.dirname(host_path), exist_ok=True)
        with open(host_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        edit_mgr.record_modification(host_path)

        follow_up = tool_provider.FollowUpToolCall(
            tool_name="read_file",
            wire_parameter_bindings=tool_provider.WireParameterBindings(
                bindings={
                    ("file", target_file.short_name),
                    ("line_numbers", True),
                }
            ),
        )
        # Requirement: On successful execution, an editing tool writes the updated file content to the filesystem, records that workspace file modifications occurred, and produces a response specifying a follow-up execution of the read tool on the modified read-write file with line numbers requested, accompanied by a reminder justifying inspecting the updated file.
        # Requirement: Successful editing tool responses carry a suppression key matching the short name of the modified read-write file.
        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content="Successfully replaced text.",
            reminder="Inspect the updated file to verify changes.",
            suppression_key=target_file.short_name,
            follow_up_tool_call=follow_up,
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
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
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

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        target_file = bindings_map.get("file")
        start_line = int(bindings_map.get("start_line", 1))
        end_line = int(bindings_map.get("end_line", 1))
        replacement_text = str(bindings_map.get("replacement_text", ""))

        # Requirement: Before modifying a file, editing tool execution fails if the file alias is not a read-write file, reminding the agent that only declared read-write files can be modified.
        if not isinstance(target_file, agent_file_alias.ReadWriteFile):
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: {target_file} is not a read-write file.",
                reminder="Only declared read-write files can be modified.",
            )

        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        host_path = os.path.join(
            alias_mgr.workspace_root.path, target_file.workspace_path.path
        )

        # Requirement: Executing the line update tool reads file content using the filesystem, treating missing files as empty.
        # Requirement: Executing the line update tool fails if the start line is less than one or exceeds the total line count plus one.
        if not os.path.exists(host_path):
            lines = []
        else:
            with open(host_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        total_lines = len(lines)
        if start_line < 1 or start_line > total_lines + 1:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: start_line {start_line} out of bounds (1..{total_lines + 1}).",
            )

        # Requirement: Replacing or inserting lines treats each replacement line as a complete newline-terminated line, preserving subsequent line boundaries when replacement text lacks a trailing newline.
        rep_lines = [
            l + "\n" if not l.endswith("\n") else l
            for l in replacement_text.splitlines()
        ]

        if start_line <= end_line:
            # Requirement: When the start line is less than or equal to the end line, executing the line update tool fails if the end line exceeds the total line count.
            if end_line > total_lines:
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: end_line {end_line} exceeds total lines {total_lines}.",
                )
            # Requirement: When the start line is less than or equal to the end line, successful execution replaces lines within the range, writes using the filesystem, and records file modifications.
            # Requirement: [EditManager] Modifying a file records that workspace file modifications occurred during the session.
            new_lines = lines[: start_line - 1] + rep_lines + lines[end_line:]
        else:
            # Requirement: When the start line exceeds the end line, successful execution inserts the replacement lines before the start line, writes using the filesystem, and records file modifications.
            # Requirement: [EditManager] Modifying a file records that workspace file modifications occurred during the session.
            new_lines = lines[: start_line - 1] + rep_lines + lines[start_line - 1 :]

        # Requirement: Before modifying a file, editing tool execution fails if the edit produces no change to file content, reminding the agent that the edit had no effect and such edits will fail.
        if new_lines == lines:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: line update produced no change to file content.",
                reminder="The edit had no effect, and such edits will fail.",
            )

        edit_mgr = get_singleton(EditManager)
        edit_mgr.record_initial_content(host_path, "".join(lines))

        os.makedirs(os.path.dirname(host_path), exist_ok=True)
        with open(host_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        edit_mgr.record_modification(host_path)

        follow_up = tool_provider.FollowUpToolCall(
            tool_name="read_file",
            wire_parameter_bindings=tool_provider.WireParameterBindings(
                bindings={
                    ("file", target_file.short_name),
                    ("line_numbers", True),
                }
            ),
        )
        # Requirement: On successful execution, an editing tool writes the updated file content to the filesystem, records that workspace file modifications occurred, and produces a response specifying a follow-up execution of the read tool on the modified read-write file with line numbers requested, accompanied by a reminder justifying inspecting the updated file.
        # Requirement: Successful editing tool responses carry a suppression key matching the short name of the modified read-write file.
        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content="Successfully updated lines.",
            reminder="Inspect the updated file to verify changes.",
            suppression_key=target_file.short_name,
            follow_up_tool_call=follow_up,
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
