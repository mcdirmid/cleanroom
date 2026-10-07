# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 3b97d0c929c3
# --- END CLEANROOM METADATA ---

"""Sandbox run control low-level interface specification."""

from typing import Any, Mapping, NewType, Optional, Protocol, Sequence, Set
from framework import operation, override, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import dag_config
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
        ...


@singleton_type("agent_session")
class CheckFilesTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Tool that inspects verification checks across active files."""

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """Executes verification inspection.

        Args:
            actual_parameter_bindings: Tool parameter bindings.

        Returns:
            Response containing verification outcomes.

        POSTCONDITIONS:
        - MUST update verification results when results are outdated.
        - MUST evaluate verification checks across open targets and modified workspace files.
        - MUST present aggregated verification outcomes.
        - WHEN verification fails, MUST fail.
        """
        ...


@singleton_type("agent_session")
class AdvanceTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Tool that advances progressive guide steps upon passing verification."""

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """Executes guide milestone advancement.

        Args:
            actual_parameter_bindings: Tool parameter bindings.

        Returns:
            Response delivering next milestone or failure feedback.

        POSTCONDITIONS:
        - MUST coordinate step progression through guide delivery upon passing verification.
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
        - MUST enforce change documentation when files were modified.
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


@singleton_type("agent_session")
class GetWorkTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Tool that retrieves active dirty nodes for processing."""

    @property
    def max_batch_size_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[dag_config.BatchSize], int]:
        """Parameter specifying the maximum number of nodes to acquire."""
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """Acquires dirty nodes for execution.

        Args:
            actual_parameter_bindings: Tool parameter bindings.

        Returns:
            Response delivering session task prompt or idle message.

        POSTCONDITIONS:
        - MUST retrieve active dirty nodes.
        - MUST materialize startup templates.
        - MUST deliver the session task prompt.
        - WHEN in guide step mode, MUST specify follow-up execution of advance tool.
        """
        ...


@singleton_type("agent_session")
class RunController(InTier[AgentSessionTier], Protocol):
    """Coordinates session termination tools and verification caching."""

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """Exposes verification checks validating session criteria.

        POSTCONDITIONS:
        - MUST return verification checks that validate session criteria.
        """
        ...

    @operation
    def update_verification(self) -> None:
        """Updates and caches verification results if outdated.

        POSTCONDITIONS:
        - MUST cache verification evaluation results alongside target node file hashes.
        - WHEN no workspace files have been updated, MUST reuse cached verification outcome.
        """
        ...
