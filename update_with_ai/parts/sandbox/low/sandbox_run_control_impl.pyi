# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T18:30:00Z
# CHANGE: Update sandbox_run_control_impl low-level realization specification
# CODE_HASH: 18c14d435487
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Sandbox run control implementation low-level specification."""

from typing import Any, Mapping, Optional, Sequence, Set
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import control_coordinate
import dag_storage
import dag_subgraph
import sandbox_file_editor
import sandbox_guide_delivery
import sandbox_run_control
import sandbox_submission
import template_format
import tool_provider


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
        - WHEN verification has not been evaluated or is failing on first step, MUST repeat primer and summary content through guide delivery.
        - WHEN verification is failing, MUST fail reminding agent that check files should be called first and specifying follow-up execution of check files.
        - WHEN verification passes and guide steps remain, MUST deliver next step section through guide delivery.
        - WHEN verification passes, no steps remain, and workspace files were modified, MUST fail reminding agent to call submit with change summary.
        - WHEN verification passes, no steps remain, and no workspace files were modified, MUST produce response specifying follow-up execution of submit without change summary.

        GROUNDING:
        - Verifies that verification passes via RunController, advances milestone steps through
          sandbox_guide_delivery.GuideDelivery.advance_step, inspects modification state via
          sandbox_file_editor.EditManager.has_modifications, and returns the formatted response.
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

    @property
    @override
    def name(self) -> tool_provider.ToolName:
        """Exposes the constant get work tool identity.

        GROUNDING:
        - Reports the constant tool name "get_work" under which this tool is registered and invoked
          through tool_provider.ToolManager.install_tool.
        """
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
        - WHEN open active nodes remain, MUST fail.
        - WHEN no open active nodes remain, MUST obtain dirty nodes from dag storage and dag subgraph.
        - WHEN no dirty nodes are ready, MUST produce idle response.
        - MUST materialize startup templates on disk through dag storage.
        - WHEN ready dirty nodes are obtained, MUST install blame tool if any active node has configured blame targets in node config.
        - WHEN ready dirty nodes are obtained and guide step mode is inactive, MUST return task primer with guide file attribution.
        - WHEN ready dirty nodes are obtained and guide step mode is active, MUST install advance tool and return task primer prompting advance.

        GROUNDING:
        - Queries open targets through control_coordinate.SessionCoordinator.open_targets, obtains
          next dirty batch via dag_subgraph.DagSubgraph.next_ready_batch, materializes startup
          templates through dag_storage.DagStorage.materialize_template, builds the task primer
          formatted by template_format.TemplateFormatter, optionally registers sandbox_submission.BlameTool into
          tool_provider.ToolManager when blame targets exist, and optionally registers AdvanceTool into
          tool_provider.ToolManager.
        """
        ...


@singleton_type("agent_session")
class RunController(
    sandbox_run_control.RunController, InTier[AgentSessionTier]
):
    """Realizes tool installation and verification check result caching.

    GROUNDING:
    - Installs the session outcome tools from sandbox_submission alongside check files and get work tools through
      tool_provider.ToolManager.install_tool during agent session entry and maintains cached verification results
      keyed by the target file hashes computed by sandbox_file_editor.EditManager.file_hash.
    - Exposes the per-node blame targets declared by
      agent_node_config.NodeConfig.blame_targets_by_node for defect attribution.
    """

    @operation
    @override
    def initialize(self) -> None:
        """Initializes session outcome tools upon agent session entry.

        GROUNDING:
        - Registers the submit and fail tools from sandbox_submission alongside check files and get work tools through
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
