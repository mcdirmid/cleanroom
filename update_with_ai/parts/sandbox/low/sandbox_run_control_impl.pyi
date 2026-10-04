"""Sandbox run control implementation low-level specification."""

from typing import Any, Mapping, Optional, Sequence, Set
from framework import operation, override, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import sandbox_run_control
import tool_provider


@singleton_type("agent_session")
class CheckFilesTool(
    sandbox_run_control.CheckFilesTool, InTier[AgentSessionTier]
):
    """Realizes verification check execution and diagnostic aggregation."""

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType]
    ) -> tool_provider.ToolResponse:
        """Executes verification check evaluation across modified workspace files.

        Args:
            actual_parameter_bindings: Tool parameter bindings.

        Returns:
            Response containing verification outcomes or failure feedback.

        POSTCONDITIONS:
        - WHEN target file hashes have not changed since previous check, MUST remind agent that verification status is unchanged.
        - WHEN verification fails, MUST present sanitized diagnostic feedback alongside verification failure instructions.
        - WHEN verification passes, MUST produce response presenting passing results.
        """
        ...


@singleton_type("agent_session")
class AdvanceTool(
    sandbox_run_control.AdvanceTool, InTier[AgentSessionTier]
):
    """Realizes guide milestone advancement gated by verification checks."""

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
        - WHEN verification is failing on first step, MUST repeat primer and summary content through guide delivery.
        - WHEN verification is failing, MUST remind agent to call check files first and specify follow-up execution of check files.
        - WHEN verification passes and guide steps remain, MUST deliver next step section.
        - WHEN verification passes, no steps remain, and files were modified, MUST fail reminding agent to call submit with change summary.
        - WHEN verification passes, no steps remain, and no files were modified, MUST specify follow-up execution of submit without change summary.
        """
        ...


@singleton_type("agent_session")
class SubmitTool(
    sandbox_run_control.SubmitTool, InTier[AgentSessionTier]
):
    """Realizes node completion verification and clean submission."""

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
        - WHEN guide step mode is active and guide steps remain, MUST fail specifying advance as follow-up tool call.
        - WHEN verification is failing, MUST fail specifying follow-up execution of check files.
        - WHEN an initial implementation change is assigned and no files were modified, MUST fail.
        - WHEN session feedback is present and no files were modified, MUST fail.
        - WHEN target is an auditor node and change summary is provided, MUST fail reminding agent that change summary is prohibited for audit nodes.
        - WHEN files were modified and change summary is omitted, MUST fail.
        - MUST mark the resolve target clean in storage via dag_storage with the provided change summary so that the node is no longer dirty.
        - MUST mark resolve target clean in current turn.
        """
        ...


@singleton_type("agent_session")
class FailTool(
    sandbox_run_control.FailTool, InTier[AgentSessionTier]
):
    """Realizes task failure termination."""

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
        - MUST mark active node as failed.
        """
        ...


@singleton_type("agent_session")
class BlameTool(
    sandbox_run_control.BlameTool, InTier[AgentSessionTier]
):
    """Realizes defect attribution to upstream prerequisites."""

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
        - MUST identify active node attributing blame from specified blame target.
        - WHEN blame target is omitted in single-target context, MUST default to single configured blame target of active node.
        - WHEN blame target does not match any configured blame target, MUST fail listing available blame targets.
        - WHEN explanation contains newline characters, MUST fail reminding agent that explanation must be a single paragraph.
        - MUST record defect feedback for the blamed target via dag_storage so that the blamed node receives the feedback message.
        - MUST mark blame target as attributed.
        """
        ...


@singleton_type("agent_session")
class GetWorkTool(
    sandbox_run_control.GetWorkTool, InTier[AgentSessionTier]
):
    """Realizes batch acquisition and session task prompt delivery."""

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
        - WHEN open active nodes remain, MUST fail reminding agent to resolve open nodes.
        - WHEN no dirty nodes are ready, MUST produce an idle response.
        - WHEN ready dirty nodes are obtained and guide step mode is inactive, MUST return task primer with guide file attribution.
        - WHEN ready dirty nodes are obtained and guide step mode is active, MUST return task primer prompting advance.
        """
        ...


@singleton_type("agent_session")
class RunController(
    sandbox_run_control.RunController, InTier[AgentSessionTier]
):
    """Realizes tool installation and verification check result caching."""

    @property
    @override
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        ...

    @operation
    @override
    def update_verification(self) -> None:
        """Updates and caches verification results sequentially when outdated.

        POSTCONDITIONS:
        - MUST cache verification evaluations alongside target file hashes, evaluating sequentially when outdated.
        - WHEN target file hashes have not changed since previous evaluation, MUST omit check execution and reuse cached outcome.
        """
        ...
