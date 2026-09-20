# Requirements specified in sandbox_file_reader_impl.pyi
import os
import re
from typing import Any, Optional, Set, Type, cast
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

    def initialize(self) -> None:
        # Requirement: The read manager unconditionally installs the view file tool into the tool manager and never installs the search tool.
        tm = get_singleton(tool_provider.ToolManager)
        tm.install_tool(get_singleton(ViewFileTool))

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        # Requirement: The read manager exposes declared read-only files, read-write files, and optional guide file obtained from the node config.
        cfg = get_singleton(agent_node_config.NodeConfig)
        return {
            f
            for f in cfg.read_only_files
            if isinstance(f, agent_file_alias.ReadOnlyFile)
        }

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        # Requirement: The read manager exposes declared read-only files, read-write files, and optional guide file obtained from the node config.
        cfg = get_singleton(agent_node_config.NodeConfig)
        return {
            f
            for f in cfg.read_write_files
            if isinstance(f, agent_file_alias.ReadWriteFile)
        }

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        # Requirement: The read manager exposes declared read-only files, read-write files, and optional guide file obtained from the node config.
        cfg = get_singleton(agent_node_config.NodeConfig)
        return cfg.guide_file


class ViewFileTool(sandbox_file_reader.ViewFileTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        # Requirement: The view file tool is named `view_file`.
        return "view_file"

    @property
    def description(self) -> str:
        return (
            "Views file content from the workspace with line numbers. "
            "Accepts only the file alias short name (e.g., 'widget.pyi' or 'widget_impl.py') "
            "via parameter 'path'. Parameter 'path' is the only accepted parameter."
        )

    @property
    def path_parameter(
        self,
    ) -> tool_provider.Parameter[agent_file_alias.FileAlias, str]:
        # Requirement: The view file tool path parameter uses the alias manager to convert a file alias.
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.Parameter(
            name="path",
            description="Target file alias",
            parameter_type=alias_mgr,
            is_required=True,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {self.path_parameter}

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        target_file = cast(agent_file_alias.FileAlias, bindings_map.get("path"))

        read_mgr = get_singleton(ReadManager)
        # Requirement: When an unbound file equals the guide file configured for step-mode, the view file tool failure response indicates that `advance` must be called to read the guide instead.
        if isinstance(target_file, agent_file_alias.UnboundFile):
            if (
                read_mgr.guide_file
                and target_file.relative_path == read_mgr.guide_file.relative_path
            ):
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content="To read the task guide, call 'advance' instead.",
                )

            # Check for transparent fallback resolution to a declared bound file:
            # Resolves foo.py -> foo.pyi, or module paths like testing.parts.pkg.foo.py -> foo.pyi
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

            # Requirement: When an unbound file is supplied, tool execution resolves to that grounding specification file alias if the relative path or qualified path addresses a module name or ends with `.py` and matches a declared read-only grounding specification ending with `.pyi`.
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
                    # Requirement: When an unbound file is supplied, tool execution fails with a response explaining that test files are not inspectable and grounding specifications serve as the contract if the unbound file addresses a test file ending with `_test.py`.
                    guidance = f"Error: Unknown file '{target_file.relative_path}'. Test files are not inspectable by design; only declared grounding specifications (.pyi) and target library files (.py) are accessible. Available files: {', '.join(readable)}"
                else:
                    # Requirement: When an unbound file is supplied, tool execution fails with a response guiding agent recovery, reminding the agent that only declared files can be inspected, listing available readable file aliases, and, if the unbound file matches the guide file configured for step-mode, that `advance` must be called to read the guide instead, otherwise.
                    guidance = f"Error: Unknown file '{target_file.relative_path}'. Available files: {', '.join(readable)}"
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=guidance,
                    reminder="Only declared files can be inspected.",
                )

        # Requirement: Tool execution reads file content from the filesystem at the host path formed from the alias manager workspace root and the bound file workspace path, returning the content formatted with one-indexed right-aligned line numbers followed by a colon and space, and formatting read-only markdown files ending with `.md` using the template formatter with session template parameters after filtering out paragraphs beginning with `> META:`.
        assert isinstance(target_file, agent_file_alias.BoundFile)
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        host_path = os.path.join(
            alias_mgr.workspace_root.path, target_file.workspace_path.path
        )

        # Requirement: Tool execution treats a read-write file as having empty content when the target file does not exist on disk, and fails with a response guiding agent recovery when inspecting a missing read-only file.
        if not os.path.exists(host_path):
            if isinstance(target_file, agent_file_alias.ReadWriteFile):
                lines = []
            else:
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: File '{target_file.relative_path}' does not exist on disk.",
                    reminder="Only declared files can be inspected.",
                )
        else:
            with open(host_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        # Requirement: When reading markdown files ending with .md, paragraphs beginning with > META: are filtered out from the returned content.
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
                        filtered_lines[-1] += (
                            "\n"  # pragma: no cover (assumption: readlines preserves newlines on non-terminal lines)
                        )
                    filtered_lines.append("\n")
                filtered_lines.extend(para)
            lines = filtered_lines

            # Requirement: When reading read-only markdown files ending with .md, content is formatted using the template formatter with session template parameters after filtering out paragraphs beginning with > META:.
            if isinstance(target_file, agent_file_alias.ReadOnlyFile):
                raw_text = "".join(lines)
                cfg = get_singleton(agent_node_config.NodeConfig)
                formatter = get_singleton(template_format.TemplateFormatter)
                formatted_text = formatter.format_template(
                    raw_text, cfg.template_parameters
                )
                lines = formatted_text.splitlines(keepends=True)

        if lines:
            digits = max(len(str(len(lines))), 3)
            content = "".join(
                f"{i:>{digits}d}: {line}" for i, line in enumerate(lines, start=1)
            )
        else:
            content = ""

        # Requirement: View file tool responses for read-write files carry a suppression key matching the file's relative path, while responses for read-only files omit suppression keys and sanitize host paths through the alias manager.
        if isinstance(target_file, agent_file_alias.ReadWriteFile):
            suppression_key = target_file.relative_path
            final_content = content
        else:
            suppression_key = None
            final_content = alias_mgr.sanitize_text(content)

        try:
            edit_mgr = get_singleton(sandbox_file_editor.EditManager)
            # Requirement: Tool execution records the read file in the edit manager on successful execution.
            edit_mgr.record_file_read(target_file)
        except (LookupError, KeyError):
            pass

        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content=final_content,
            suppression_key=suppression_key,
        )


class RegexPatternParameterType(
    tool_provider.ParameterType[agent_file_alias.RegexPattern, str], Singleton
):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def actual_type(self) -> Type[agent_file_alias.RegexPattern]:
        return agent_file_alias.RegexPattern

    @property
    def wire_type(self) -> Type[str]:
        return str

    def to_actual(self, value: str) -> agent_file_alias.RegexPattern:
        return agent_file_alias.RegexPattern(value)

    def to_wire(self, value: agent_file_alias.RegexPattern) -> str:
        return str(value)

    def convert(self, wire_value: str) -> agent_file_alias.RegexPattern:
        # Requirement: The regex pattern parameter type converts a wire type string into a regex pattern.
        return agent_file_alias.RegexPattern(wire_value)


class SearchTool(sandbox_file_reader.SearchTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return "Searches for regex pattern matches across session files."

    @property
    def regex_pattern_parameter(
        self,
    ) -> tool_provider.Parameter[agent_file_alias.RegexPattern, str]:
        # Requirement: The search tool regex pattern parameter uses the regex pattern parameter type.
        conv = get_singleton(RegexPatternParameterType)
        return tool_provider.Parameter(
            name="pattern",
            description="Regex pattern to search",
            parameter_type=conv,
            is_required=True,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {self.regex_pattern_parameter}

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        pat_obj = bindings_map.get("pattern")
        pattern_str = str(pat_obj or "")

        # Requirement: Executing the search tool fails when provided with an invalid regex pattern.
        try:
            compiled = re.compile(pattern_str)
        except re.error as e:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: Invalid regex pattern '{pattern_str}': {e}",
            )

        read_mgr = get_singleton(ReadManager)
        alias_mgr = get_singleton(agent_file_alias.AliasManager)

        results = []
        # Requirement: The search tool searches for regex pattern matches across read-only files and read-write files using the filesystem.
        for ro in read_mgr.read_only_files:
            host_path = os.path.join(
                alias_mgr.workspace_root.path, ro.workspace_path.path
            )
            if os.path.isfile(host_path):
                with open(host_path, "r", encoding="utf-8") as f:
                    for idx, line in enumerate(f, start=1):
                        if compiled.search(line):
                            # Requirement: On successful search tool execution, matches in read-only files provide matched line contents and line numbers sanitized by the alias manager to mask host paths.
                            results.append(f"{ro.relative_path}:{idx}: {line.rstrip()}")

        for rw in read_mgr.read_write_files:
            host_path = os.path.join(
                alias_mgr.workspace_root.path, rw.workspace_path.path
            )
            if os.path.isfile(host_path):
                with open(host_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if compiled.search(content):
                        # Requirement: On successful search tool execution, matches in read-write files state that matches were found but cannot be displayed to prevent unanchored edits.
                        results.append(
                            f"{rw.relative_path}: matches found (details hidden to prevent unanchored edits)"
                        )

        output = "\n".join(results) if results else "No matches found."
        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content=alias_mgr.sanitize_text(output),
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
