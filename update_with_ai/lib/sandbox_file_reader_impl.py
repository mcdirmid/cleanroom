import os
import re
from typing import Any, Optional, Set, Type, cast
from . import file_alias
from . import node_config
from . import sandbox_file_reader
from . import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class ReadManager(sandbox_file_reader.ReadManager, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    def initialize(self) -> None:
        # Requirement: The read manager unconditionally installs the read tool into the tool manager and never installs the search tool.
        tm = get_singleton(tool_provider.ToolManager)
        tm.install_tool(get_singleton(ReadTool))

    @property
    def read_only_files(self) -> Set[file_alias.ReadOnlyFile]:
        # Requirement: The read manager exposes declared read-only files, read-write files, and optional guide file obtained from the node config.
        cfg = get_singleton(node_config.NodeConfig)
        return {f for f in cfg.read_only_files if isinstance(f, file_alias.ReadOnlyFile)}

    @property
    def read_write_files(self) -> Set[file_alias.ReadWriteFile]:
        # Requirement: The read manager exposes declared read-only files, read-write files, and optional guide file obtained from the node config.
        cfg = get_singleton(node_config.NodeConfig)
        return {f for f in cfg.read_write_files if isinstance(f, file_alias.ReadWriteFile)}

    @property
    def guide_file(self) -> Optional[file_alias.UnboundFile]:
        # Requirement: The read manager exposes declared read-only files, read-write files, and optional guide file obtained from the node config.
        cfg = get_singleton(node_config.NodeConfig)
        return cfg.guide_file


class ReadTool(sandbox_file_reader.ReadTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Reads file content from the workspace."

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
    def line_numbers_parameter(self) -> tool_provider.Parameter:
        bool_conv = get_singleton(tool_provider.BooleanParameterConverter)
        return tool_provider.Parameter(
            name="line_numbers",
            description="Must be true when reading read-write files; must be false or omitted when reading read-only files.",
            parameter_converter=bool_conv,
            is_required=False,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {self.file_alias_parameter, self.line_numbers_parameter}

    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        target_file = cast(file_alias.FileAlias, bindings_map.get("file"))
        line_numbers = bool(bindings_map.get("line_numbers", False))

        read_mgr = get_singleton(ReadManager)
        # Requirement: When an unbound file equals the guide file configured for step-mode, the read tool failure response indicates that `advance` must be called to read the guide instead.
        if isinstance(target_file, file_alias.UnboundFile):
            if read_mgr.guide_file and target_file.short_name == read_mgr.guide_file.short_name:
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content="To read the task guide, call 'advance' instead.",
                )
            # Requirement: Executing the read tool with an unbound file fails with a response guiding agent recovery that lists available readable file aliases, and reminds the agent that only declared files can be inspected.
            readable = [f.short_name for f in read_mgr.read_only_files] + [f.short_name for f in read_mgr.read_write_files]
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: Unknown file '{target_file.short_name}'. Available files: {', '.join(readable)}",
                reminder="Only declared files can be inspected.",
            )

        # Requirement: Executing the read tool fails if line numbers are not requested when reading a read-write file, and reminds the agent that line numbers must be requested when reading read-write files and omitted when reading read-only files.
        if isinstance(target_file, file_alias.ReadWriteFile) and not line_numbers:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: line_numbers must be requested when reading read-write file '{target_file.short_name}'.",
                reminder="Line numbers must be requested when reading read-write files and omitted when reading read-only files.",
            )

        # Requirement: Executing the read tool fails if line numbers are requested when reading a read-only file, and reminds the agent that line numbers must be requested when reading read-write files and omitted when reading read-only files.
        if isinstance(target_file, file_alias.ReadOnlyFile) and line_numbers:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: line_numbers must not be requested when reading read-only file '{target_file.short_name}'.",
                reminder="Line numbers must be requested when reading read-write files and omitted when reading read-only files.",
            )

        # Requirement: Executing the read tool reads file content using the filesystem at the host path formed from the alias manager workspace root and bound file workspace path.
        assert isinstance(target_file, file_alias.BoundFile)
        alias_mgr = get_singleton(file_alias.AliasManager)
        host_path = os.path.join(alias_mgr.workspace_root.path, target_file.workspace_path.path)

        with open(host_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if line_numbers:
            content = "".join(f"{i + 1}: {line}" for i, line in enumerate(lines))
        else:
            content = "".join(lines)

        # Requirement: On successful read tool execution for a read-only file, the returned file content is sanitized by the alias manager to mask host paths.
        sanitized = alias_mgr.sanitize_text(content)
        # Requirement: On successful read tool execution, the response includes internal resource metadata identifying the read file alias.
        kind = "read_write" if isinstance(target_file, file_alias.ReadWriteFile) else "read_only"
        response_content = f"_resource: {target_file.short_name}\n_kind: {kind}\n{sanitized}"
        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content=response_content,
        )

class RegexPatternConverter(tool_provider.ParameterConverter, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def actual_type(self) -> Type:
        return file_alias.RegexPattern

    @property
    def wire_type(self) -> tool_provider.WireType:
        return tool_provider.String()

    def convert(self, wire_value: Any) -> file_alias.RegexPattern:
        # Requirement: The regex pattern converter converts a wire type string into a regex pattern.
        return file_alias.RegexPattern(str(wire_value))

class SearchTool(sandbox_file_reader.SearchTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return "Searches for regex pattern matches across session files."

    @property
    def regex_pattern_parameter(self) -> tool_provider.Parameter:
        conv = get_singleton(RegexPatternConverter)
        return tool_provider.Parameter(
            name="pattern",
            description="Regex pattern to search",
            parameter_converter=conv,
            is_required=True,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {self.regex_pattern_parameter}

    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
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
        alias_mgr = get_singleton(file_alias.AliasManager)

        results = []
        # Requirement: The search tool searches for regex pattern matches across read-only files and read-write files using the filesystem.
        for ro in read_mgr.read_only_files:
            host_path = os.path.join(alias_mgr.workspace_root.path, ro.workspace_path.path)
            if os.path.isfile(host_path):
                with open(host_path, "r", encoding="utf-8") as f:
                    for idx, line in enumerate(f, start=1):
                        if compiled.search(line):
                            # Requirement: On successful search tool execution, matches in read-only files provide matched line contents and line numbers sanitized by the alias manager to mask host paths.
                            results.append(f"{ro.short_name}:{idx}: {line.rstrip()}")

        for rw in read_mgr.read_write_files:
            host_path = os.path.join(alias_mgr.workspace_root.path, rw.workspace_path.path)
            if os.path.isfile(host_path):
                with open(host_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if compiled.search(content):
                        # Requirement: On successful search tool execution, matches in read-write files state that matches were found but cannot be displayed to prevent unanchored edits.
                        results.append(f"{rw.short_name}: matches found (details hidden to prevent unanchored edits)")

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
        tier="agent_session",
    )
    reg.register_singleton(
        ReadTool,
        keys=[ReadTool, sandbox_file_reader.ReadTool, tool_provider.Tool],
        tier="agent_session",
    )
    reg.register_singleton(
        RegexPatternConverter,
        keys=[RegexPatternConverter, tool_provider.ParameterConverter],
        tier="agent_session",
    )
    reg.register_singleton(
        SearchTool,
        keys=[SearchTool, sandbox_file_reader.SearchTool, tool_provider.Tool],
        tier="agent_session",
    )
