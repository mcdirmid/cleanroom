# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T18:30:00Z
# CHANGE: Define sandbox_submission_impl low-level realization specification
# CODE_HASH: 2ce5f708b3d4
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Sandbox submission realization low-level specification."""

from typing import Any, Mapping, Optional, Sequence, Set
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import control_coordinate
import sandbox_guide_delivery
import sandbox_run_control
import sandbox_submission
import src_metadata
import tool_provider


@singleton_type("agent_session")
class SubmitTool(
    sandbox_submission.SubmitTool, InTier[AgentSessionTier]
):
    """Realizes clean task submission gated by verification and documentation.

    GROUNDING:
    - Validates verification status and guide milestones, then dispatches target submission through
      control_coordinate.SessionCoordinator.dispatch_submit.
    - Inspects whether workspace files were modified during the session through
      src_metadata.SourceMetadataCoordinator.is_code_modified before passing modification status to dispatch_submit.
    """

    @property
    @override
    def change_summary_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[sandbox_submission.ChangeSummary], str]:
        """Parameter describing modifications made during the task.

        GROUNDING:
        - Declares an optional tool_provider.ToolParameter over the
          sandbox_submission.ChangeSummary change description that execute_tool reads from the
          actual parameter bindings and passes to
          control_coordinate.SessionCoordinator.dispatch_submit.
        """
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
        - WHEN guide step mode is active and guide steps remain, MUST fail specifying advance as follow-up tool call.
        - WHEN verification is failing, MUST fail specifying follow-up execution of check files.
        - WHEN submission gating rejects request, MUST fail relaying rejection feedback alongside change summary reminders when summary rules are violated, or feedback resolution reminders when unaddressed feedback blocks submission.
        - WHEN submission succeeds and all active nodes are resolved, MUST produce a terminating response.
        - WHEN submission succeeds and other active nodes remain, MUST produce a non-terminating response.

        GROUNDING:
        - Checks agent_node_config.NodeConfig.is_step_mode and sandbox_guide_delivery.GuideDelivery.has_steps_remaining,
          refreshes outdated verification results through sandbox_run_control.RunController.update_verification,
          inspects modification state via src_metadata.SourceMetadataCoordinator.is_code_modified, delegates submission gating
          and clean transition to control_coordinate.SessionCoordinator.dispatch_submit, and checks
          control_coordinate.SessionCoordinator.open_targets to set the termination state.
        """
        ...


@singleton_type("agent_session")
class FailTool(
    sandbox_submission.FailTool, InTier[AgentSessionTier]
):
    """Realizes task failure termination.

    GROUNDING:
    - Records the active target as failed through
      control_coordinate.SessionCoordinator.dispatch_fail.
    """

    @property
    @override
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[sandbox_submission.FailureExplanation, str]:
        """Parameter explaining the reason for failure.

        GROUNDING:
        - Declares a tool_provider.ToolParameter over the
          sandbox_submission.FailureExplanation reason that execute_tool reads from the actual
          parameter bindings and records through
          control_coordinate.SessionCoordinator.dispatch_fail.
        """
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
        - MUST mark active node as failed.

        GROUNDING:
        - Resolves the active node and updates its status to failed through
          control_coordinate.SessionCoordinator.dispatch_fail.
        """
        ...


@singleton_type("agent_session")
class BlameTool(
    sandbox_submission.BlameTool, InTier[AgentSessionTier]
):
    """Realizes defect attribution to upstream prerequisites.

    GROUNDING:
    - Attributes failure to the upstream dependency node and records the defect feedback through
      control_coordinate.SessionCoordinator.dispatch_blame.
    """

    @property
    @override
    def blame_target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """Parameter identifying the blamed upstream dependency.

        GROUNDING:
        - Declares a tool_provider.ToolParameter over the agent_file_alias.FileAlias blame target
          that execute_tool matches against the per-node blame targets exposed by
          sandbox_run_control.RunController.blame_targets_by_node.
        """
        ...

    @property
    @override
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[sandbox_submission.BlameExplanation, str]:
        """Parameter explaining the defect in the upstream dependency.

        GROUNDING:
        - Declares a tool_provider.ToolParameter over the
          sandbox_submission.BlameExplanation defect text that execute_tool validates as a single
          paragraph and records through control_coordinate.SessionCoordinator.dispatch_blame.
        """
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
        - MUST identify active node attributing blame from specified blame target.
        - WHEN resolve target matches configured blame target, MUST treat resolve target as blame target and default active node.
        - WHEN blame target is omitted in single-target context, MUST default to single configured blame target of active node.
        - WHEN blame target does not match any configured blame target, MUST fail listing available blame targets.
        - WHEN explanation contains newline characters, MUST fail reminding agent that explanation must be a single paragraph.
        - MUST record defect feedback for the blamed target via dag_storage so that the blamed node receives the feedback message.
        - MUST mark blame target as attributed.
        - WHEN all active nodes are resolved, MUST produce a terminating response.
        - WHEN other active nodes remain, MUST produce a non-terminating response.

        GROUNDING:
        - Resolves the active node for the supplied blame target through
          control_coordinate.SessionCoordinator.get_node_for_alias, treating the resolve target
          as the blame target when matching configured blame targets by relative path, suffix, or
          basename, verifies the single-paragraph explanation, adds the defect message and
          attributes blame through control_coordinate.SessionCoordinator.dispatch_blame, and checks
          control_coordinate.SessionCoordinator.open_targets to set the termination state.
        """
        ...
