# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:43:05Z
# LAST_CHANGED: 2026-10-09T21:43:05Z
# CHANGE: Add initialize method to RunController protocol
# CODE_HASH: 155ed79c9e6e
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Mapping, NewType, Optional, Protocol, Sequence, Set
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier
import update_with_ai.parts.agent.lib.agent_file_alias as agent_file_alias
import update_with_ai.parts.agent.lib.agent_node_config as agent_node_config
import update_with_ai.parts.dag.lib.dag_config as dag_config
import update_with_ai.parts.dag.lib.dag_storage as dag_storage
from . import tool_provider

# Requirements specified in sandbox_run_control.pyi

ChangeSummary = NewType('ChangeSummary', str)

FailureExplanation = NewType('FailureExplanation', str)

BlameExplanation = NewType('BlameExplanation', str)

class ResolveTool(tool_provider.Tool, Protocol):
    @property
    def target_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        # TODO_target_parameter_body
        ...

    @property
    def name(self) -> tool_provider.ToolName:
        # TODO_name_body
        ...

    @property
    def description(self) -> tool_provider.ToolDescription:
        # TODO_description_body
        ...

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        # TODO_parameters_body
        ...

    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        # TODO_execute_tool_body
        ...


class CheckFilesTool(tool_provider.Tool, Protocol):
    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        # TODO_execute_tool_body
        ...


class AdvanceTool(tool_provider.Tool, Protocol):
    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        # TODO_execute_tool_body
        ...


class SubmitTool(ResolveTool, Protocol):
    @property
    def change_summary_parameter(self) -> tool_provider.ToolParameter[Optional[ChangeSummary], str]:
        # TODO_change_summary_parameter_body
        ...

    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        # TODO_execute_tool_body
        ...


class FailTool(ResolveTool, Protocol):
    @property
    def explanation_parameter(self) -> tool_provider.ToolParameter[FailureExplanation, str]:
        # TODO_explanation_parameter_body
        ...

    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        # TODO_execute_tool_body
        ...


class BlameTool(ResolveTool, Protocol):
    @property
    def blame_target_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        # TODO_blame_target_parameter_body
        ...

    @property
    def explanation_parameter(self) -> tool_provider.ToolParameter[BlameExplanation, str]:
        # TODO_explanation_parameter_body
        ...

    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        # TODO_execute_tool_body
        ...


class GetWorkTool(tool_provider.Tool, Protocol):
    @property
    def max_batch_size_parameter(self) -> tool_provider.ToolParameter[Optional[dag_config.BatchSize], int]:
        # TODO_max_batch_size_parameter_body
        ...

    def execute_tool(self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]) -> tool_provider.ToolResponse:
        # TODO_execute_tool_body
        ...


class RunController(Protocol):
    def initialize(self) -> None:
        # TODO_initialize_body
        ...

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        # TODO_verification_checks_body
        ...

    def update_verification(self) -> None:
        # TODO_update_verification_body
        ...
