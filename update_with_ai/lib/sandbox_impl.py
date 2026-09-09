from typing import List, Optional
from . import model_config
from . import node_config
from . import sandbox
from . import sandbox_file_editor
from . import sandbox_file_reader
from . import sandbox_run_control
from . import tool_provider
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class Sandbox(sandbox.Sandbox, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def has_modifications(self) -> bool:
        # Requirement: Delegate querying file modifications to edit manager
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        return edit_mgr.has_modifications

    def get_startup_tool_executions(self) -> List[sandbox.StartupToolExecution]:
        executions: List[sandbox.StartupToolExecution] = []
        m_cfg = get_singleton(model_config.ModelConfig)

        # Requirement: When using step mode, include initial advance tool execution with tool name 'advance' and empty bindings
        if m_cfg.is_step_mode:
            adv_tool = get_singleton(sandbox_run_control.AdvanceTool)
            resp = adv_tool.execute_tool(tool_provider.ActualParameterBindings(bindings=set()))
            executions.append(
                sandbox.StartupToolExecution(
                    tool_name="advance",
                    wire_parameter_bindings=tool_provider.WireParameterBindings(bindings=set()),
                    response=resp,
                )
            )

        # Requirement: When performing startup reads, include read executions for all declared read-only files from node config, positioned after any advance execution
        if m_cfg.is_startup_reads:
            n_cfg = get_singleton(node_config.NodeConfig)
            read_tool = get_singleton(sandbox_file_reader.ReadTool)
            for ro in n_cfg.read_only_files:
                bindings = {(read_tool.file_alias_parameter, ro)}
                resp = read_tool.execute_tool(tool_provider.ActualParameterBindings(bindings=bindings))
                # Requirement: Specify tool name as 'read_file' with wire bindings mapping 'file' to short name and capture read tool response
                executions.append(
                    sandbox.StartupToolExecution(
                        tool_name="read_file",
                        wire_parameter_bindings=tool_provider.WireParameterBindings(
                            bindings={("file", ro.short_name)}
                        ),
                        response=resp,
                    )
                )

        return executions

    def materialize_startup_templates(self) -> None:
        # Requirement: Delegate template materialization to edit manager to write template content without overwriting existing files
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        edit_mgr.materialize_templates()

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Sandbox,
        keys=[Sandbox, sandbox.Sandbox],
        tier="agent_session",
    )
