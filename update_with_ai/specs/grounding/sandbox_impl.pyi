from typing import List
from framework import operation, override, singleton_type
import model_config
import node_config
import sandbox
import sandbox_file_editor
import sandbox_file_reader
import sandbox_run_control
import tool_provider

@singleton_type('agent_session')
class Sandbox(sandbox.Sandbox):
    """
PURPOSE:
Implements sandbox to coordinate startup context and file management

FRESH_REQUIREMENTS:
- Querying file modifications delegates to the edit manager.

INHERITED_REQUIREMENTS:
- [Sandbox] The sandbox exposes whether workspace file modifications occurred during the session.

GROUNDING_ARGUMENT:
- As an agent_session singleton, Sandbox coordinates startup tool execution sequences and template materialization, accessing collaborator singletons in the same session lifecycle tier (node_config.NodeConfig, sandbox_file_editor.EditManager, sandbox_file_reader.ReadTool, sandbox_run_control.AdvanceTool) and model_config.ModelConfig in the more general system lifecycle tier.
"""

    @property
    @override
    def has_modifications(self) -> bool:
        """
PURPOSE:
Queries the edit manager to determine if workspace files were modified

GROUNDING_ARGUMENT:
- Delegated directly to imported collaborator sandbox_file_editor.EditManager.has_modifications in the same session lifecycle tier.
"""
        ...

    @operation
    @override
    def get_startup_tool_executions(self) -> List[sandbox.StartupToolExecution]:
        """
PURPOSE:
Implements get_startup_tool_executions assembling an ordered sequence of executions based on configuration

FRESH_REQUIREMENTS:
- When using step mode to communicate a guide progressively, startup tool executions include an initial advance tool execution with the name of the advance tool, empty wire parameter bindings, and the response produced by executing the advance tool.
- When performing startup reads to inspect declared files at session start, startup tool executions include file read executions for all declared read-only files from node config ordered deterministically by file alias short name, positioned after any advance tool execution.
- Each file read execution uses the name of the read tool, specifies wire parameter bindings mapping the file alias parameter of the read tool to the read-only file alias short name while supplying line numbers as determined by the read manager for source code files, and captures the response produced by executing the read tool.
- When step mode is not used, startup tool executions contain no advance tool execution.
- When startup reads are not performed, startup tool executions contain no file read executions.

INHERITED_REQUIREMENTS:
- [Sandbox] The sandbox exposes startup tool executions as an ordered sequence of initial tool executions based on active configuration.

GROUNDING_ARGUMENT:
- Reads step mode and startup reads from imported model_config.ModelConfig (system tier), retrieves declared read-only files from imported node_config.NodeConfig (session tier) ordered deterministically by file alias short name, executes imported sandbox_run_control.AdvanceTool and sandbox_file_reader.ReadTool (session tier), and pairs tool requests with responses into StartupToolExecution records.
"""
        ...

    @operation
    @override
    def materialize_startup_templates(self) -> None:
        """
PURPOSE:
Implements materialize_startup_templates by delegating to the edit manager

FRESH_REQUIREMENTS:
- Materializing startup templates delegates to the edit manager to write template content to missing read-write files without overwriting existing files.

INHERITED_REQUIREMENTS:
- [Sandbox] Materializing startup templates populates missing read-write files without overwriting existing files.

GROUNDING_ARGUMENT:
- Delegates template materialization directly to imported sandbox_file_editor.EditManager in the same session lifecycle tier.
"""
        ...
