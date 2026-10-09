# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 731dd8d41a16
# --- END CLEANROOM METADATA ---

from typing import Any, Mapping, NewType, Optional, Protocol, Sequence, Set
from . import tool_provider
from update_with_ai.parts.agent.lib import agent_file_alias, agent_node_config

ChangeSummary = NewType("ChangeSummary", str)
FailureExplanation = NewType("FailureExplanation", str)
BlameExplanation = NewType("BlameExplanation", str)


class ResolveTool(tool_provider.Tool, Protocol):
    @property
    def target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]: ...

    @property
    def name(self) -> tool_provider.ToolName: ...

    @property
    def description(self) -> tool_provider.ToolDescription: ...

    @property
    def parameters(
        self,
    ) -> Mapping[
        tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]
    ]: ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse: ...


class CheckFilesTool(tool_provider.Tool, Protocol):
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse: ...


class AdvanceTool(tool_provider.Tool, Protocol):
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse: ...


class SubmitTool(ResolveTool, Protocol):
    @property
    def change_summary_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[ChangeSummary], str]: ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse: ...


class FailTool(ResolveTool, Protocol):
    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[FailureExplanation, str]: ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse: ...


class BlameTool(ResolveTool, Protocol):
    @property
    def blame_target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]: ...

    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[BlameExplanation, str]: ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse: ...


class _Types:
    BatchSize = NewType("BatchSize", int)


dag_config = _Types


class GetWorkTool(tool_provider.Tool, Protocol):
    @property
    def max_batch_size_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[dag_config.BatchSize], int]: ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse: ...


class RunController(Protocol):
    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]: ...

    def update_verification(self) -> None: ...
