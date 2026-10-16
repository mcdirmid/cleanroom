# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:03:50Z
# CHANGE: Resolve and match both declared path members through the file path manager before reporting access, and use pathlib filesystem operations
# CODE_HASH: d6b9a4867f14
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

import re
from pathlib import Path
from typing import Any, List, Mapping, Optional, Set, Type, Union, cast
from support.lib.lifecycle import InTier, LifecycleRegistry, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier, agent_session
import update_with_ai.parts.agent.lib.agent_file_alias as agent_file_alias
import update_with_ai.parts.agent.lib.agent_node_config as agent_node_config
import update_with_ai.parts.core.lib.file_paths as file_paths
from . import sandbox_file_editor
from . import sandbox_file_reader
from . import template_format
from . import tool_provider

# Requirements specified in sandbox_file_reader_impl.pyi

class ReadManager(sandbox_file_reader.ReadManager, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        return set(cfg.read_only_files)

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        return set(cfg.read_write_files)

    def can_read(self, path: Union[agent_file_alias.RelativePath, agent_file_alias.FileAlias]) -> tool_provider.ToolResponse:
        rel_path = str(path.relative_path) if isinstance(path, agent_file_alias.FileAlias) else str(path)
        all_declared = self.read_only_files | self.read_write_files
        avail_paths = sorted(str(f.relative_path) for f in all_declared)
        fp_mgr = get_singleton(file_paths.FilePathManager)
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        for declared in all_declared:
            if (
                str(declared.relative_path) == rel_path
                or str(declared.workspace_path.path) == rel_path
            ):
                workspace_path = fp_mgr.create_workspace_path(
                    file_paths.PathString(str(declared.workspace_path.path))
                )
                fp_mgr.resolve_path(alias_mgr.workspace_root, workspace_path)
                return tool_provider.ToolResponse(
                    is_failed=False,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(f"Access permitted for '{rel_path}'."),
                )
        avail_str = ", ".join(f"'{p}'" for p in avail_paths)
        return tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(f"Error: Unknown file '{rel_path}'. Available files: {avail_str}"),
            reminder=tool_provider.ToolReminder("Only declared files can be inspected."),
        )


class ViewFileTool(sandbox_file_reader.ViewFileTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        pass

    def initialize(self) -> None:
        tool_mgr = get_singleton(tool_provider.ToolManager)
        tool_mgr.install_tool(self)

    @property
    def name(self) -> tool_provider.ToolName:
        return tool_provider.ToolName("view_file")

    @property
    def description(self) -> tool_provider.ToolDescription:
        return tool_provider.ToolDescription("Views workspace file content with line numbers using the file alias short name.")

    @property
    def path_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        alias_type = get_singleton(tool_provider.AliasManagerType)
        return tool_provider.ToolParameter[agent_file_alias.FileAlias, str](
            name=tool_provider.ParameterName("path"),
            description=tool_provider.ParameterDescription("File alias or relative path of the file to view."),
            parameter_type=alias_type,
            is_required=True,
            default_value=None,
        )

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        param = self.path_parameter
        return {param.name: param}

    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        read_mgr = get_singleton(sandbox_file_reader.ReadManager)
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        fp_mgr = get_singleton(file_paths.FilePathManager)
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)

        target = cast(Any, actual_parameter_bindings.get(self.path_parameter))
        all_declared = read_mgr.read_only_files | read_mgr.read_write_files
        avail_paths = sorted(str(f.relative_path) for f in all_declared)
        avail_str = ", ".join(f"'{p}'" for p in avail_paths)

        if target is None or isinstance(target, agent_file_alias.UnboundFile) or not any(f.relative_path == target.relative_path for f in all_declared):
            path_str = str(target.relative_path) if target is not None and hasattr(target, "relative_path") else str(target)
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: Unknown file '{path_str}'. Available files: {avail_str}"
                ),
                reminder=tool_provider.ToolReminder("Only declared files can be inspected."),
            )

        is_ro = any(f.relative_path == target.relative_path for f in read_mgr.read_only_files)
        is_rw = any(f.relative_path == target.relative_path for f in read_mgr.read_write_files)

        ws_root = alias_mgr.workspace_root
        ws_path = fp_mgr.create_workspace_path(file_paths.PathString(str(target.relative_path)))
        abs_path = fp_mgr.resolve_path(ws_root, ws_path)
        disk_path = Path(abs_path.path)

        if is_ro and not disk_path.is_file():
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: File '{target.relative_path}' does not exist on disk."
                ),
                reminder=tool_provider.ToolReminder("Only declared files can be inspected."),
            )

        if is_rw and not disk_path.is_file():
            raw_content = ""
        else:
            raw_content = disk_path.read_text(encoding="utf-8")

        if str(target.relative_path).endswith(".md"):
            paras = raw_content.split("\n\n")
            filtered = [p for p in paras if not p.strip().startswith("> META:")]
            raw_content = "\n\n".join(filtered)

        if is_ro and str(target.relative_path).endswith(".md"):
            node_cfg = get_singleton(agent_node_config.NodeConfig)
            formatter = get_singleton(template_format.TemplateFormatter)
            template_params = {
                template_format.TemplateKey(str(k)): v
                for k, v in node_cfg.template_parameters.items()
            }
            raw_content = str(
                formatter.format_template(
                    template_format.TemplateText(raw_content),
                    template_params,
                )
            )

        if is_ro:
            raw_content = str(alias_mgr.sanitize_text(agent_file_alias.UnsanitizedText(raw_content)))
            supp_key = None
        else:
            supp_key = tool_provider.SuppressionKey(str(target.relative_path))

        lines = raw_content.splitlines()
        if not lines:
            formatted_content = ""
        else:
            width = len(str(len(lines)))
            formatted_lines = [
                f"{str(idx + 1).rjust(width)}: {line}"
                for idx, line in enumerate(lines)
            ]
            formatted_content = "\n".join(formatted_lines)

        edit_mgr.record_file_read(target)
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(formatted_content),
            suppression_key=supp_key,
        )


class RegexPatternParameterType(tool_provider.ParameterType[agent_file_alias.RegexPattern, str], InTier[AgentSessionTier], Singleton):
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
                message=tool_provider.ConversionErrorMessage(
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
        return tool_provider.ToolDescription("Searches regex pattern matches across session files.")

    @property
    def regex_pattern_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.RegexPattern, str]:
        param_type = get_singleton(RegexPatternParameterType)
        return tool_provider.ToolParameter[agent_file_alias.RegexPattern, str](
            name=tool_provider.ParameterName("pattern"),
            description=tool_provider.ParameterDescription("Regular expression pattern to search for."),
            parameter_type=param_type,
            is_required=True,
            default_value=None,
        )

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        param = self.regex_pattern_parameter
        return {param.name: param}

    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        pat = actual_parameter_bindings.get(self.regex_pattern_parameter)
        try:
            regex = re.compile(str(pat))
        except re.error as e:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(f"Error: Invalid regex pattern '{pat}': {e}"),
            )

        read_mgr = get_singleton(sandbox_file_reader.ReadManager)
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        fp_mgr = get_singleton(file_paths.FilePathManager)
        ws_root = alias_mgr.workspace_root

        results: List[str] = []

        for ro_file in sorted(read_mgr.read_only_files, key=lambda f: str(f.relative_path)):
            ws_path = fp_mgr.create_workspace_path(file_paths.PathString(str(ro_file.relative_path)))
            abs_path = fp_mgr.resolve_path(ws_root, ws_path)
            ro_path = Path(abs_path.path)
            if ro_path.is_file():
                content = ro_path.read_text(encoding="utf-8")
                file_matches: List[str] = []
                for idx, line in enumerate(content.splitlines(), start=1):
                    if regex.search(line):
                        sanitized_line = str(alias_mgr.sanitize_text(agent_file_alias.UnsanitizedText(line)))
                        file_matches.append(f"{idx}: {sanitized_line}")
                if file_matches:
                    results.append(f"=== {ro_file.relative_path} ===")
                    results.extend(file_matches)

        for rw_file in sorted(read_mgr.read_write_files, key=lambda f: str(f.relative_path)):
            ws_path = fp_mgr.create_workspace_path(file_paths.PathString(str(rw_file.relative_path)))
            abs_path = fp_mgr.resolve_path(ws_root, ws_path)
            rw_path = Path(abs_path.path)
            if rw_path.is_file():
                content = rw_path.read_text(encoding="utf-8")
                if regex.search(content):
                    results.append(f"{rw_file.relative_path}: matches found (details hidden to prevent unanchored edits)")

        output_str = "\n".join(results) if results else "No matches found."
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(output_str),
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        ReadManager,
        keys=[ReadManager, sandbox_file_reader.ReadManager],
        tier=agent_session,
    )
    reg.register_singleton(
        ViewFileTool,
        keys=[ViewFileTool, sandbox_file_reader.ViewFileTool],
        tier=agent_session,
    )
    reg.register_singleton(
        RegexPatternParameterType,
        keys=[RegexPatternParameterType, tool_provider.ParameterType[agent_file_alias.RegexPattern, str], InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        SearchTool,
        keys=[SearchTool, sandbox_file_reader.SearchTool],
        tier=agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
