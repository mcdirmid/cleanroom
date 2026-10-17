# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:30:00Z
# CHANGE: Delegate submission tools to submission
# CODE_HASH: 8219977c5078
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Mapping, Optional, Protocol, Sequence, Set
from update_with_ai.parts.agent.lib.session import AgentSessionTier
import update_with_ai.parts.agent.lib.file_alias as file_alias
import update_with_ai.parts.agent.lib.node_config as node_config
import update_with_ai.parts.dag.lib.dag_storage as dag_storage
from . import tool_provider
from .submission import (
    BlameExplanation,
    BlameTool,
    ChangeSummary,
    FailTool,
    FailureExplanation,
    ResolveTool,
    SubmitTool,
)

# Requirements specified in run_control.pyi


# Contract: CheckFilesTool protocol - inspects verification checks across active files.
class CheckFilesTool(tool_provider.Tool, Protocol):
    # Contract: Tool.name - returns 'check_files'.
    @property
    def name(self) -> tool_provider.ToolName:
        ...

    # Contract: CheckFilesTool.execute_tool - evaluates verification checks and presents aggregated outcomes.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


# Contract: AdvanceTool protocol - advances progressive guide steps upon passing verification.
class AdvanceTool(tool_provider.Tool, Protocol):
    # Contract: Tool.name - returns 'advance'.
    @property
    def name(self) -> tool_provider.ToolName:
        ...

    # Contract: AdvanceTool.execute_tool - executes guide milestone advancement.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


# Contract: GetWorkTool protocol - retrieves active dirty nodes for processing and materializes startup templates.
class GetWorkTool(tool_provider.Tool, Protocol):
    # Contract: GetWorkTool.execute_tool - acquires dirty nodes for execution, formats task primer, and installs relevant tools.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        ...


# Contract: RunController protocol - coordinates session termination tools and verification caching.
class RunController(Protocol):
    # Contract: RunController.initialize - initializes session outcome tools upon agent session entry.
    def initialize(self) -> None:
        ...

    # Contract: RunController.verification_checks - exposes verification checks validating session criteria.
    @property
    def verification_checks(self) -> Sequence[node_config.VerificationCheck]:
        ...

    # Contract: RunController.blame_targets_by_node - exposes per-node blame targets eligible for defect attribution.
    @property
    def blame_targets_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Set[file_alias.BoundFile]]:
        ...

    # Contract: RunController.update_verification - updates and caches verification results if outdated.
    def update_verification(self) -> None:
        ...
