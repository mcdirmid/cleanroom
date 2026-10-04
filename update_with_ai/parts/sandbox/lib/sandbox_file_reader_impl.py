# Requirements specified in sandbox_file_reader_impl.pyi
import os
import re
from typing import Any, Mapping, Optional, Set, Type, Union, cast
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.agent.lib import agent_node_config
from . import sandbox_file_editor
from . import sandbox_file_reader
from . import template_format
from . import tool_provider
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib.agent_session import agent_session


class ReadManager(sandbox_file_reader.ReadManager, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    def can_read(
        self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]
    ) -> tool_provider.ToolResponse:
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        target_file = (
            path
            if isinstance(path, agent_file_alias.FileAlias)
            else alias_mgr.convert(path)
        )

        read_mgr = self
        cfg = get_singleton(agent_node_config.NodeConfig)
        if isinstance(target_file, agent_file_alias.UnboundFile):
            if (
                cfg.guide_file
                and target_file.relative_path == cfg.guide_file.relative_path
            ):
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        "To read the task guide, call 'advance' instead."
                    ),
                )

            raw_name = target_file.relative_path
            base_cand = os.path.basename(raw_name)
            if "." in base_cand:
                parts = base_cand.split(".")
                if len(parts) > 2 and parts[-1] in ("py", "pyi"):
                    base_cand = f"{parts[-2]}.{parts[-1]}"
                elif len(parts) >= 2 and parts[-1] not in ("py", "pyi", "md", "txt"):
                    base_cand = parts[-1]

            all_bound_files = list(read_mgr.read_only_files) + list(
                read_mgr.read_write_files
            )
            matched_bound: Optional[agent_file_alias.BoundFile] = None

            stem = (
                base_cand[:-3]
                if base_cand.endswith(".py")
                else (base_cand[:-4] if base_cand.endswith(".pyi") else base_cand)
            )
            variations = [raw_name, base_cand]
            if raw_name.endswith(".py"):
                variations.append(raw_name[:-3] + ".pyi")
            if base_cand.endswith(".py"):
                variations.append(f"{stem}.pyi")
            elif not base_cand.endswith(".pyi"):
                variations.extend([f"{stem}.py", f"{stem}.pyi"])

            for var in variations:
                for bf in all_bound_files:
                    if (
                        bf.relative_path == var
                        or bf.relative_path.endswith("/" + var)
                        or os.path.basename(bf.relative_path) == var
                    ):
                        matched_bound = bf
                        break
                if matched_bound is not None:
                    break

            if matched_bound is not None:
                target_file = matched_bound
            else:
                readable = [f.relative_path for f in read_mgr.read_only_files] + [
                    f.relative_path for f in read_mgr.read_write_files
                ]
                if (
                    target_file.relative_path.endswith("_test.py")
                    or "_test" in target_file.relative_path
                ):
                    guidance = f"Error: Unknown file '{target_file.relative_path}'. Test files are not inspectable by design; only declared grounding specifications (.pyi) and target library files (.py) are accessible. Available files: {', '.join(readable)}"
                else:
                    guidance = f"Error: Unknown file '{target_file.relative_path}'. Available files: {', '.join(readable)}"
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(guidance),
                    reminder=tool_provider.ToolReminder(
                        "Only declared files can be inspected."
                    ),
                )

        assert isinstance(target_file, agent_file_alias.BoundFile)
        try:
            edit_mgr = get_singleton(sandbox_file_editor.EditManager)
            edit_mgr.record_file_read(target_file)
        except (LookupError, KeyError):  # pragma: no cover (assumption: standard reader configuration)
            pass

        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(
                f"Access permitted for '{target_file.relative_path}'."
            ),
        )

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        return {
            f
            for f in cfg.read_only_files
            if isinstance(f, agent_file_alias.ReadOnlyFile)
        }

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        return {
            f
            for f in cfg.read_write_files
            if isinstance(f, agent_file_alias.ReadWriteFile)
        }

    @property
    def guide_file(self) -> Optional[agent_file_alias.FileAlias]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        return cfg.guide_file


class ViewFileTool(sandbox_file_reader.ViewFileTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    def initialize(self) -> None:
        tm = get_singleton(tool_provider.ToolManager)
        try:
            cfg = get_singleton(agent_config.AgentConfig)
            is_mcp = cfg.is_mcp_mode
        except (LookupError, KeyError):  # pragma: no cover (assumption: standard reader configuration)
            is_mcp = False
        if not is_mcp:
            tm.install_tool(self)

    @property
    def name(self) -> tool_provider.ToolName:
        return tool_provider.ToolName("view_file")

    @property
    def description(self) -> tool_provider.ToolDescription:
        return tool_provider.ToolDescription(
            "Views file content from the workspace with line numbers. "
            "Accepts only the file alias short name (e.g., 'widget.pyi' or 'widget_impl.py') "
            "via parameter 'path'. Parameter 'path' is the only accepted parameter."
        )

    @property
    def path_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.ToolParameter(
            name=tool_provider.ParameterName("path"),
            description=tool_provider.ParameterDescription("Target file alias"),
            parameter_type=alias_mgr,
            is_required=True,
        )

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return {self.path_parameter.name: self.path_parameter}

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        target_file = cast(
            Optional[agent_file_alias.FileAlias],
            actual_parameter_bindings.get(self.path_parameter),
        )
        read_mgr = get_singleton(ReadManager)
        cfg = get_singleton(agent_node_config.NodeConfig)

        if isinstance(target_file, agent_file_alias.UnboundFile):
            if (
                cfg.guide_file
                and target_file.relative_path == cfg.guide_file.relative_path
            ):
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        "To read the task guide, call 'advance' instead."
                    ),
                )

            raw_name = target_file.relative_path
            base_cand = os.path.basename(raw_name)
            if "." in base_cand:
                parts = base_cand.split(".")
                if len(parts) > 2 and parts[-1] in ("py", "pyi"):
                    base_cand = f"{parts[-2]}.{parts[-1]}"
                elif len(parts) >= 2 and parts[-1] not in ("py", "pyi", "md", "txt"):
                    base_cand = parts[-1]

            all_bound_files = list(read_mgr.read_only_files) + list(
                read_mgr.read_write_files
            )
            matched_bound: Optional[agent_file_alias.BoundFile] = None

            stem = (
                base_cand[:-3]
                if base_cand.endswith(".py")
                else (base_cand[:-4] if base_cand.endswith(".pyi") else base_cand)
            )
            variations = [raw_name, base_cand]
            if raw_name.endswith(".py"):
                variations.append(raw_name[:-3] + ".pyi")
            if base_cand.endswith(".py"):
                variations.append(f"{stem}.pyi")
            elif not base_cand.endswith(".pyi"):
                variations.extend([f"{stem}.py", f"{stem}.pyi"])

            for var in variations:
                for bf in all_bound_files:
                    if (
                        bf.relative_path == var
                        or bf.relative_path.endswith("/" + var)
                        or os.path.basename(bf.relative_path) == var
                    ):
                        matched_bound = bf
                        break
                if matched_bound is not None:
                    break

            if matched_bound is not None:
                target_file = matched_bound
            else:
                readable = [f.relative_path for f in read_mgr.read_only_files] + [
                    f.relative_path for f in read_mgr.read_write_files
                ]
                if (
                    target_file.relative_path.endswith("_test.py")
                    or "_test" in target_file.relative_path
                ):
                    guidance = f"Error: Unknown file '{target_file.relative_path}'. Test files are not inspectable by design; only declared grounding specifications (.pyi) and target library files (.py) are accessible. Available files: {', '.join(readable)}"
                else:
                    guidance = f"Error: Unknown file '{target_file.relative_path}'. Available files: {', '.join(readable)}"
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(guidance),
                    reminder=tool_provider.ToolReminder(
                        "Only declared files can be inspected."
                    ),
                )

        assert isinstance(target_file, agent_file_alias.BoundFile)
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        host_path = os.path.join(
            alias_mgr.workspace_root.path, target_file.workspace_path.path
        )

        if not os.path.exists(host_path):
            if isinstance(target_file, agent_file_alias.ReadWriteFile):
                lines = []
            else:
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        f"Error: File '{target_file.relative_path}' does not exist on disk."
                    ),
                    reminder=tool_provider.ToolReminder(
                        "Only declared files can be inspected."
                    ),
                )
        else:
            with open(host_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        if target_file.relative_path.endswith(
            ".md"
        ) or target_file.workspace_path.path.endswith(".md"):
            paragraphs: list[list[str]] = []
            current_para: list[str] = []
            for line in lines:
                if line.strip() == "":
                    if current_para:
                        paragraphs.append(current_para)
                        current_para = []
                else:
                    current_para.append(line)
            if current_para:
                paragraphs.append(current_para)

            filtered_lines: list[str] = []
            for para in paragraphs:
                first_line = para[0].strip()
                if first_line.startswith("> META:"):
                    continue
                if filtered_lines:
                    if not filtered_lines[-1].endswith("\n"):
                        filtered_lines[-1] += "\n"  # pragma: no cover (assumption: posix newline terminated)
                    filtered_lines.append("\n")
                filtered_lines.extend(para)
            lines = filtered_lines

            if isinstance(target_file, agent_file_alias.ReadOnlyFile):
                raw_text = "".join(lines)
                cfg = get_singleton(agent_node_config.NodeConfig)
                formatter = get_singleton(template_format.TemplateFormatter)
                formatted_text = formatter.format_template(
                    template_format.TemplateText(raw_text),
                    {
                        template_format.TemplateKey(k): v
                        for k, v in cfg.template_parameters.items()
                    },
                )
                lines = formatted_text.splitlines(keepends=True)

        if lines:
            digits = max(len(str(len(lines))), 3)
            content = "".join(
                f"{i:>{digits}d}: {line}" for i, line in enumerate(lines, start=1)
            )
        else:
            content = ""

        if isinstance(target_file, agent_file_alias.ReadWriteFile):
            suppression_key = target_file.relative_path
            final_content = content
        else:
            suppression_key = None
            final_content = alias_mgr.sanitize_text(
                agent_file_alias.UnsanitizedText(content)
            )

        try:
            edit_mgr = get_singleton(sandbox_file_editor.EditManager)
            edit_mgr.record_file_read(target_file)
        except (LookupError, KeyError):  # pragma: no cover (assumption: standard reader configuration)
            pass

        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(final_content),
            suppression_key=tool_provider.SuppressionKey(suppression_key)
            if suppression_key is not None
            else None,
        )


class RegexPatternParameterType(
    tool_provider.ParameterType[agent_file_alias.RegexPattern, str], Singleton
):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def actual_type(self) -> Type[agent_file_alias.RegexPattern]:
        return cast(Type[agent_file_alias.RegexPattern], agent_file_alias.RegexPattern)

    @property
    def wire_type(self) -> Type[str]:
        return str

    def convert(self, wire_value: str) -> agent_file_alias.RegexPattern:
        try:
            re.compile(wire_value)
        except re.error as e:
            raise tool_provider.ParameterConversionError(
                tool_provider.ConversionErrorMessage(
                    f"Invalid regex pattern '{wire_value}': {e}"
                )
            )
        return agent_file_alias.RegexPattern(wire_value)


class SearchTool(sandbox_file_reader.SearchTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> tool_provider.ToolName:
        return tool_provider.ToolName("search_files")

    @property
    def description(self) -> tool_provider.ToolDescription:
        return tool_provider.ToolDescription("Searches for regex pattern matches across session files.")

    @property
    def regex_pattern_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.RegexPattern, str]:
        conv = get_singleton(RegexPatternParameterType)
        return tool_provider.ToolParameter(
            name=tool_provider.ParameterName("pattern"),
            description=tool_provider.ParameterDescription("Regex pattern to search"),
            parameter_type=conv,
            is_required=True,
        )

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return {self.regex_pattern_parameter.name: self.regex_pattern_parameter}

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        pat_obj = actual_parameter_bindings.get(self.regex_pattern_parameter)
        pattern_str = str(pat_obj or "")

        try:
            compiled = re.compile(pattern_str)
        except re.error as e:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: Invalid regex pattern '{pattern_str}': {e}"
                ),
            )

        read_mgr = get_singleton(ReadManager)
        alias_mgr = get_singleton(agent_file_alias.AliasManager)

        results = []
        for ro in read_mgr.read_only_files:
            host_path = os.path.join(
                alias_mgr.workspace_root.path, ro.workspace_path.path
            )
            if os.path.isfile(host_path):
                with open(host_path, "r", encoding="utf-8") as f:
                    for idx, line in enumerate(f, start=1):
                        if compiled.search(line):
                            results.append(f"{ro.relative_path}:{idx}: {line.rstrip()}")

        for rw in read_mgr.read_write_files:
            host_path = os.path.join(
                alias_mgr.workspace_root.path, rw.workspace_path.path
            )
            if os.path.isfile(host_path):
                with open(host_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if compiled.search(content):
                        results.append(
                            f"{rw.relative_path}: matches found (details hidden to prevent unanchored edits)"
                        )

        output = "\n".join(results) if results else "No matches found."
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(
                alias_mgr.sanitize_text(agent_file_alias.UnsanitizedText(output))
            ),
        )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        ReadManager,
        keys=[ReadManager, sandbox_file_reader.ReadManager],
        tier=agent_session,
    )
    reg.register_singleton(
        ViewFileTool,
        keys=[ViewFileTool, sandbox_file_reader.ViewFileTool, tool_provider.Tool],
        tier=agent_session,
    )
    reg.register_singleton(
        RegexPatternParameterType,
        keys=[
            RegexPatternParameterType,
            tool_provider.ParameterType,
        ],
        tier=agent_session,
    )
    reg.register_singleton(
        SearchTool,
        keys=[SearchTool, sandbox_file_reader.SearchTool, tool_provider.Tool],
        tier=agent_session,
    )
