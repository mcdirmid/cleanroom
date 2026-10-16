# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T18:30:00Z
# CHANGE: Define sandbox_submission low-level interface specification
# CODE_HASH: 24bf2712dcd8
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Sandbox submission low-level interface specification."""

from typing import Any, Mapping, NewType, Optional, Protocol, Sequence, Set
from framework import operation, override, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import dag_storage
import tool_provider

ChangeSummary = NewType("ChangeSummary", str)
FailureExplanation = NewType("FailureExplanation", str)
BlameExplanation = NewType("BlameExplanation", str)


@poly_type
class ResolveTool(tool_provider.Tool, Protocol):
    """Polymorphic tool that resolves an active node."""

    @property
    def target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """Parameter identifying the active node being resolved."""
        ...

    @property
    @override
    def name(self) -> tool_provider.ToolName:
        ...

    @property
    @override
    def description(self) -> tool_provider.ToolDescription:
        ...

    @property
    @override
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """Executes the resolve tool action.

        POSTCONDITIONS:
        - WHEN all active nodes are resolved, MUST produce a terminating response.
        - WHEN other active nodes remain, MUST produce a non-terminating response.
        """
        ...


@singleton_type("agent_session")
class SubmitTool(ResolveTool, InTier[AgentSessionTier], Protocol):
    """Tool that marks an active node complete upon passing verification."""

    @property
    def change_summary_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[ChangeSummary], str]:
        """Parameter describing modifications made during the task."""
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """Submits an active node as cleanly finished.

        Args:
            actual_parameter_bindings: Tool parameter bindings.

        Returns:
            Response confirming task submission.

        POSTCONDITIONS:
        - WHEN verification passes, MUST conclude active node.
        - MUST mark the resolve target clean in the current turn.
        - WHEN workspace files were modified, MUST enforce change documentation.
        """
        ...


@singleton_type("agent_session")
class FailTool(ResolveTool, InTier[AgentSessionTier], Protocol):
    """Tool that terminates session execution in failure."""

    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[FailureExplanation, str]:
        """Parameter explaining the reason for failure."""
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """Fails the active node.

        Args:
            actual_parameter_bindings: Tool parameter bindings.

        Returns:
            Response terminating the run in failure.

        POSTCONDITIONS:
        - MUST terminate the run in failure.
        """
        ...


@singleton_type("agent_session")
class BlameTool(ResolveTool, InTier[AgentSessionTier], Protocol):
    """Tool that attributes failure to an upstream prerequisite."""

    @property
    def blame_target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """Parameter identifying the blamed upstream dependency."""
        ...

    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[BlameExplanation, str]:
        """Parameter explaining the defect in the upstream dependency."""
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """Attributes failure to an upstream dependency node.

        Args:
            actual_parameter_bindings: Tool parameter bindings.

        Returns:
            Response recording blame feedback.

        POSTCONDITIONS:
        - MUST attribute task failure to an upstream dependency node.
        """
        ...
