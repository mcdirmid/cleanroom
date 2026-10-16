# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:30:00Z
# CHANGE: Delegate submission tools to sandbox_submission
# CODE_HASH: 8219977c5078
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Mapping, Optional, Protocol, Sequence, Set
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier
import update_with_ai.parts.agent.lib.agent_file_alias as agent_file_alias
import update_with_ai.parts.agent.lib.agent_node_config as agent_node_config
import update_with_ai.parts.dag.lib.dag_storage as dag_storage
from . import tool_provider
from .sandbox_submission import (
    BlameExplanation,
    BlameTool,
    ChangeSummary,
    FailTool,
    FailureExplanation,
    ResolveTool,
    SubmitTool,
)

# Requirements specified in sandbox_run_control.pyi


class CheckFilesTool(tool_provider.Tool, Protocol):
    @property
    def name(self) -> tool_provider.ToolName:
        ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


class AdvanceTool(tool_provider.Tool, Protocol):
    @property
    def name(self) -> tool_provider.ToolName:
        ...

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


class GetWorkTool(tool_provider.Tool, Protocol):
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


class RunController(Protocol):
    def initialize(self) -> None:
        ...

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        ...

    @property
    def blame_targets_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        ...

    def update_verification(self) -> None:
        ...
