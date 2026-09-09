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
- When using step mode in the model config to communicate a guide progressively, startup tool executions include an initial advance tool execution with tool name `advance` and empty wire parameter bindings.
- When performing startup reads in the model config to inspect declared files at session start, startup tool executions include reads for all declared read-only files from the node config, positioned after any advance tool execution.
- When step mode is not used, startup tool executions contain no advance tool execution.
- When startup reads are not performed, startup tool executions contain no file read executions.
- Each file read execution specifies the tool name as `read_file`.
- Each file read execution constructs wire parameter bindings mapping `file` to the read-only file short name and omitting line numbers.
- Each file read execution captures the execution response from the read tool.

INHERITED_REQUIREMENTS:
- [Sandbox] The sandbox provides an ordered sequence of startup tool executions pairing tool requests and responses based on active configuration.

GROUNDING_ARGUMENT:
- Reads step mode and startup read flags from imported model_config.ModelConfig (system tier), retrieves declared read-only files from imported node_config.NodeConfig (session tier), executes imported sandbox_run_control.AdvanceTool and sandbox_file_reader.ReadTool (session tier), and pairs tool requests with responses into StartupToolExecution records.
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
