# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T21:57:18Z
# LAST_CHANGED: 2026-10-12T11:59:00Z
# CHANGE: Install advance tool and specify follow-up execution when guide step mode is active in get work tool
# CODE_HASH: cf45569112e7
# SPEC_QA_AUDIT: 2026-10-12T21:57:18Z
# --- END CLEANROOM METADATA ---

"""Sandbox run control implementation low-level specification."""

from typing import Any, Mapping, Optional, Sequence, Set
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import control_coordinate
import sandbox_run_control
import tool_provider
import dag_storage
import dag_subgraph
import sandbox_file_editor
import sandbox_guide_delivery
import sandbox
import template_format


@singleton_type("agent_session")
class CheckFilesTool(
    sandbox_run_control.CheckFilesTool, InTier[AgentSessionTier]
):
    """Realizes verification check execution and diagnostic aggregation.

    GROUNDING:
    - Evaluates the session verification checks declared by
      agent_node_config.NodeConfig.verification_checks sequentially, caching outcomes against the
      target file hashes computed by sandbox_file_editor.EditManager.file_hash.
    """

    @property
    @override
    def name(self) -> tool_provider.ToolName:
        """Exposes the constant check files tool identity.

        GROUNDING:
        - Reports the constant tool name "check_files" under which this tool is registered and
          invoked through tool_provider.ToolManager.install_tool.
        """
        ...

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

        GROUNDING:
        - Invokes RunController.update_verification to execute outdated checks against the target
          file hashes reported by sandbox_file_editor.EditManager.file_hash, and aggregates the
          formatted outcomes into the returned tool_provider.ToolResponse.
        """
        ...


@singleton_type("agent_session")
class AdvanceTool(
    sandbox_run_control.AdvanceTool, InTier[AgentSessionTier]
):
    """Realizes guide milestone advancement gated by verification checks.

    GROUNDING:
    - Coordinates milestone advancement through
      sandbox_guide_delivery.GuideDelivery.advance_step, gating progression behind the verification
      status obtained from RunController.
    """

    @property
    @override
    def name(self) -> tool_provider.ToolName:
        """Exposes the constant advance tool identity.

        GROUNDING:
        - Reports the constant tool name "advance" under which this tool is registered and invoked
          through tool_provider.ToolManager.install_tool.
        """
        ...

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

        GROUNDING:
        - Checks verification status through RunController.update_verification and advances the
          milestone through sandbox_guide_delivery.GuideDelivery.advance_step, which repeats the
          recorded primer and reports the failure diagnostics when verification fails.
        """
        ...


@singleton_type("agent_session")
class SubmitTool(
    sandbox_run_control.SubmitTool, InTier[AgentSessionTier]
):
    """Realizes node completion verification and clean submission.

    GROUNDING:
    - Validates verification status, change summaries, and guide milestones, then marks the resolved
      target clean through dag_storage.DagStorage.mark_node_clean with the supplied change
      description.
    - Inspects whether workspace files were modified during the session through the
      sandbox.Sandbox.has_modifications property before enforcing the change summary requirement.
    """

    @property
    @override
    def change_summary_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[sandbox_run_control.ChangeSummary], str]:
        """Parameter describing modifications made during the task.

        GROUNDING:
        - Declares an optional tool_provider.ToolParameter over the
          sandbox_run_control.ChangeSummary change description that execute_tool reads from the
          actual parameter bindings and passes to dag_storage.DagStorage.mark_node_clean.
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
        - WHEN session feedback is present and no files were modified, MUST fail.
        - WHEN target is an auditor node and change summary is provided, MUST fail reminding agent that change summary is prohibited for audit nodes.
        - WHEN files were modified and change summary is omitted, MUST fail.
        - WHEN workspace files were not modified and change summary is provided, MUST fail reminding agent that change summaries are not permitted when submitting without workspace file modifications.
        - MUST mark the resolve target clean in storage via dag_storage with the provided change summary so that the node is no longer dirty.
        - MUST mark resolve target clean in current turn.
        - WHEN all active nodes are resolved, MUST produce a terminating response.
        - WHEN other active nodes remain, MUST produce a non-terminating response.

        GROUNDING:
        - Resolves the target node through
          control_coordinate.SessionCoordinator.resolve_default_target or the last path recorded by
          sandbox_file_editor.EditManager.last_read_or_edited_file, refreshes outdated verification
          results through RunController.update_verification, delegates the clean transition to
          dag_storage.DagStorage.mark_node_clean, and checks
          control_coordinate.SessionCoordinator.open_targets to set the termination state.
        """
        ...


@singleton_type("agent_session")
class FailTool(
    sandbox_run_control.FailTool, InTier[AgentSessionTier]
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
    ) -> tool_provider.ToolParameter[sandbox_run_control.FailureExplanation, str]:
        """Parameter explaining the reason for failure.

        GROUNDING:
        - Declares a tool_provider.ToolParameter over the
          sandbox_run_control.FailureExplanation reason that execute_tool reads from the actual
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
    sandbox_run_control.BlameTool, InTier[AgentSessionTier]
):
    """Realizes defect attribution to upstream prerequisites.

    GROUNDING:
    - Attributes failure to the upstream dependency node and records the defect feedback through
      dag_storage.DagStorage.add_feedback_message.
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
          RunController.blame_targets_by_node.
        """
        ...

    @property
    @override
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[sandbox_run_control.BlameExplanation, str]:
        """Parameter explaining the defect in the upstream dependency.

        GROUNDING:
        - Declares a tool_provider.ToolParameter over the
          sandbox_run_control.BlameExplanation defect text that execute_tool validates as a single
          paragraph and records through dag_storage.DagStorage.add_feedback_message.
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
        - WHEN blame target is omitted in single-target context, MUST default to single configured blame target of active node.
        - WHEN blame target does not match any configured blame target, MUST fail listing available blame targets.
        - WHEN explanation contains newline characters, MUST fail reminding agent that explanation must be a single paragraph.
        - MUST record defect feedback for the blamed target via dag_storage so that the blamed node receives the feedback message.
        - MUST mark blame target as attributed.
        - WHEN all active nodes are resolved, MUST produce a terminating response.
        - WHEN other active nodes remain, MUST produce a non-terminating response.

        GROUNDING:
        - Resolves the active node for the supplied blame target through
          control_coordinate.SessionCoordinator.get_node_for_alias, verifies the single-paragraph
          explanation, adds the defect message through
          dag_storage.DagStorage.add_feedback_message, and checks
          control_coordinate.SessionCoordinator.open_targets to set the termination state.
        """
        ...


@singleton_type("agent_session")
class GetWorkTool(
    sandbox_run_control.GetWorkTool, InTier[AgentSessionTier]
):
    """Realizes batch acquisition and session task prompt delivery.

    GROUNDING:
    - Acquires ready dirty nodes from dag_storage.DagStorage together with
      dag_subgraph.DagSubgraph.next_ready_batch, materializes startup templates through
      dag_storage.DagStorage.materialize_template, and prepares the session task primer.
    """

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

        GROUNDING:
        - Queries dag_storage.DagStorage for ready dirty nodes, writes starter templates through
          dag_storage.DagStorage.materialize_template, and prepares the session prompt with
          agent_node_config.NodeConfig.guide_file attribution.
        - Renders the task primer content through the template_format.TemplateFormatter.format_template
          operation, substituting the session template parameters into the primer template text.
        - Initializes guide delivery through sandbox_guide_delivery.GuideDelivery.initialize and registers
          the advance tool through tool_provider.ToolManager.install_tool when
          agent_node_config.NodeConfig.is_step_mode is active.
        """
        ...


@singleton_type("agent_session")
class RunController(
    sandbox_run_control.RunController, InTier[AgentSessionTier]
):
    """Realizes tool installation and verification check result caching.

    GROUNDING:
    - Installs the session outcome tools through tool_provider.ToolManager.install_tool during agent
      session entry and maintains cached verification results keyed by the target file hashes
      computed by sandbox_file_editor.EditManager.file_hash.
    - Exposes the per-node blame targets declared by
      agent_node_config.NodeConfig.blame_targets_by_node for defect attribution.
    """

    @operation
    @override
    def initialize(self) -> None:
        """Initializes session outcome tools upon agent session entry.

        GROUNDING:
        - Registers the submit, fail, check files, get work, and blame tools through
          tool_provider.ToolManager.install_tool, and conditionally registers the advance tool when
          agent_node_config.NodeConfig.is_step_mode is active.
        """
        ...

    @property
    @override
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """Exposes session verification checks validating session criteria.

        GROUNDING:
        - Exposes the verification checks declared by
          agent_node_config.NodeConfig.verification_checks.
        """
        ...

    @property
    @override
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        """Exposes per-node blame targets eligible for defect attribution.

        GROUNDING:
        - Exposes the per-node blame targets declared by
          agent_node_config.NodeConfig.blame_targets_by_node, mapping each session
          dag_storage.DagNode to the agent_file_alias.BoundFile entries eligible for blame, without
          mutating the configured mapping.
        """
        ...

    @operation
    @override
    def update_verification(self) -> None:
        """Updates and caches verification results sequentially when outdated.

        POSTCONDITIONS:
        - MUST cache verification evaluations alongside target file hashes, evaluating sequentially when outdated.
        - WHEN target file hashes have not changed since previous evaluation, MUST omit check execution and reuse cached outcome.

        GROUNDING:
        - Compares the current sandbox_file_editor.EditManager.file_hash values against the cached
          hashes and runs the outdated agent_node_config.VerificationCheck.verify evaluations
          sequentially, caching each outcome alongside the target file hash.
        """
        ...
