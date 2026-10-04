"""Sandbox run control grounding specification module."""

from __future__ import annotations
from typing import Any, Mapping, NewType, Optional, Protocol, Sequence
from support.lib.grounding_support import InTier, AgentSessionTier, key, value
from parts.agent.grounding import agent_file_alias, agent_node_config
from parts.dag.grounding import dag_config
from parts.sandbox.grounding import tool_provider

ChangeSummary = NewType("ChangeSummary", str)
FailureExplanation = NewType("FailureExplanation", str)
BlameExplanation = NewType("BlameExplanation", str)


class ResolveTool(tool_provider.Tool, Protocol):
    """Polymorphic tool that resolves an active node."""

    @property
    def target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """
        DEFERRED:
        - Target parameter specification.
        """
        raise NotImplementedError

    @property
    def name(self) -> tool_provider.ToolName:
        """
        DEFERRED:
        - Tool name specification.
        """
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        DEFERRED:
        - Tool description specification.
        """
        raise NotImplementedError

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        DEFERRED:
        - Tool parameters mapping.
        """
        raise NotImplementedError

    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """
        DEFERRED:
        - Tool execution dispatch.
        """
        raise NotImplementedError


class CheckFilesTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Tool that inspects verification checks across active files."""

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - MUST evaluate verification checks across open targets and modified workspace files.
          - Consequent knowledge: return ToolResponse.
        - MUST present aggregated verification outcomes.
          - Consequent knowledge: return ToolResponse presenting aggregated verification results.
        - WHEN verification fails, MUST fail.
          - Condition knowledge: evaluate verification failure.
          - Consequent knowledge: return failed ToolResponse.

        DEFERRED:
        - MUST update verification results when results are outdated.
        - Deferred to sandbox_run_control_impl.py.
        """
        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content="Verification passed.",
        )
        raise NotImplementedError


class AdvanceTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Tool that advances progressive guide steps upon passing verification."""

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - MUST coordinate step progression through guide delivery upon passing verification.
          - Consequent knowledge: return ToolResponse.
        """
        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content="Advanced to next step.",
        )
        raise NotImplementedError


class SubmitTool(ResolveTool, InTier[AgentSessionTier], Protocol):
    """Tool that marks an active node complete upon passing verification."""

    @property
    def change_summary_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[ChangeSummary], str]:
        """
        DEFERRED:
        - Change summary parameter specification.
        """
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - WHEN verification passes, MUST conclude active node.
          - Consequent knowledge: return terminated ToolResponse.

        DEFERRED:
        - MUST mark the resolve target clean in the current turn.
        - Deferred to sandbox_run_control_impl.py.
        - MUST enforce change documentation when files were modified.
        - Deferred to sandbox_run_control_impl.py.
        """
        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=True,
            content="Submitted successfully.",
        )
        raise NotImplementedError


class FailTool(ResolveTool, InTier[AgentSessionTier], Protocol):
    """Tool that terminates session execution in failure."""

    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[FailureExplanation, str]:
        """
        DEFERRED:
        - Explanation parameter specification.
        """
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - MUST terminate the run in failure.
          - Consequent knowledge: return terminated failed ToolResponse.
        """
        _resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=True,
            content="Task failed.",
        )
        raise NotImplementedError


class BlameTool(ResolveTool, InTier[AgentSessionTier], Protocol):
    """Tool that attributes failure to an upstream prerequisite."""

    @property
    def blame_target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """
        DEFERRED:
        - Blame target parameter specification.
        """
        raise NotImplementedError

    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[BlameExplanation, str]:
        """
        DEFERRED:
        - Explanation parameter specification.
        """
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - MUST attribute task failure to an upstream dependency node.
          - Consequent knowledge: return terminated ToolResponse with Blamed prefix.
        """
        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=True,
            content="Blamed prerequisite: defect detected.",
        )
        raise NotImplementedError


class GetWorkTool(tool_provider.Tool, InTier[AgentSessionTier], Protocol):
    """Tool that retrieves active dirty nodes for processing."""

    @property
    def max_batch_size_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[dag_config.BatchSize], int]:
        """
        DEFERRED:
        - Maximum batch size parameter specification.
        """
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - MUST retrieve active dirty nodes.
          - Consequent knowledge: retrieve active dirty nodes.
        - MUST deliver the session task prompt.
          - Consequent knowledge: return non-terminated ToolResponse with prompt.
        - WHEN in guide step mode, MUST specify follow-up execution of advance tool.
          - Condition knowledge: test guide step mode.
          - Consequent knowledge: return ToolResponse specifying follow-up execution of advance tool.

        DEFERRED:
        - MUST materialize startup templates.
        - Deferred to sandbox_run_control_impl.py.
        """
        _resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content="Task prompt instructions.",
        )
        raise NotImplementedError


class RunController(InTier[AgentSessionTier], Protocol):
    """Coordinates session termination tools and verification caching."""

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """
        DEFERRED:
        - MUST return verification checks that validate session criteria.
        """
        raise NotImplementedError

    def update_verification(self) -> None:
        """
        DEFERRED:
        - MUST cache verification evaluation results alongside target node file hashes.
        - Deferred to sandbox_run_control_impl.py.
        - WHEN no workspace files have been updated, MUST reuse cached verification outcome.
        - Deferred to sandbox_run_control_impl.py.
        """
        raise NotImplementedError
