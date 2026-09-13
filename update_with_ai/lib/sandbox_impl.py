from typing import List, Optional, Set, Tuple, Union
from . import model_config
from . import node_config
from . import sandbox
from . import sandbox_file_editor
from . import sandbox_file_reader
from . import sandbox_run_control
from . import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class Sandbox(sandbox.Sandbox, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def has_modifications(self) -> bool:
        # Requirement: Querying file modifications delegates to the edit manager.
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        return edit_mgr.has_modifications

    def get_startup_tool_executions(self) -> List[sandbox.StartupToolExecution]:
        executions: List[sandbox.StartupToolExecution] = []
        m_cfg = get_singleton(model_config.ModelConfig)
        n_cfg = get_singleton(node_config.NodeConfig)

        # Requirement: When using step mode to communicate a guide progressively, startup tool executions include an initial advance tool execution with the name of the advance tool, empty wire parameter bindings, and the response produced by executing the advance tool.
        if n_cfg.is_step_mode:
            adv_tool = get_singleton(sandbox_run_control.AdvanceTool)
            resp = adv_tool.execute_tool(tool_provider.ActualParameterBindings(bindings=set()))
            executions.append(
                sandbox.StartupToolExecution(
                    tool_name=adv_tool.name,
                    wire_parameter_bindings=tool_provider.WireParameterBindings(bindings=set()),
                    response=resp,
                )
            )

        # Requirement: When performing startup reads to inspect declared files at session start, startup tool executions include file read executions for all declared read-only files from node config ordered deterministically by file alias short name, positioned after any advance tool execution.
        if m_cfg.is_startup_reads:
            read_tool = get_singleton(sandbox_file_reader.ReadTool)
            read_mgr = get_singleton(sandbox_file_reader.ReadManager)
            for ro in sorted(n_cfg.read_only_files, key=lambda x: x.short_name):
                needs_ln = read_mgr.requires_line_numbers(ro)
                # Requirement: Each file read execution uses the name of the read tool, specifies wire parameter bindings mapping the file alias parameter of the read tool to the read-only file alias short name while supplying line numbers as determined by the read manager for source code files, and captures the response produced by executing the read tool.
                wire_bindings: Set[Tuple[str, Union[str, int, bool]]]
                if needs_ln:
                    bindings = {
                        (read_tool.file_alias_parameter, ro),
                        (read_tool.line_numbers_parameter, True),
                    }
                    wire_bindings = {
                        (read_tool.file_alias_parameter.name, ro.short_name),
                        (read_tool.line_numbers_parameter.name, True),
                    }
                else:
                    bindings = {(read_tool.file_alias_parameter, ro)}
                    wire_bindings = {(read_tool.file_alias_parameter.name, ro.short_name)}
                resp = read_tool.execute_tool(tool_provider.ActualParameterBindings(bindings=bindings))
                executions.append(
                    sandbox.StartupToolExecution(
                        tool_name=read_tool.name,
                        wire_parameter_bindings=tool_provider.WireParameterBindings(
                            bindings=wire_bindings
                        ),
                        response=resp,
                    )
                )

        return executions

    def materialize_startup_templates(self) -> None:
        # Requirement: Materializing startup templates delegates to the edit manager to write template content to missing read-write files without overwriting existing files.
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        edit_mgr.materialize_templates()

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Sandbox,
        keys=[Sandbox, sandbox.Sandbox],
        tier="agent_session",
    )
