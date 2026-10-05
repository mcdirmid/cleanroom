# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: bbe5810e67ab
# GROUNDING_QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

"""Sandbox run control implementation grounding specification module."""

from __future__ import annotations
from typing import Any, Mapping, Optional, Sequence, Set, cast
from support.lib.grounding_support import (
    InTier,
    AgentSessionTier,
    key,
    value,
    only_elem,
)
from parts.agent.grounding import agent_file_alias, agent_node_config
from parts.dag.grounding import dag_config, dag_storage, dag_subgraph
from parts.sandbox.grounding import sandbox_file_editor
from parts.sandbox.grounding import sandbox_guide_delivery
from parts.sandbox.grounding import sandbox_run_control
from parts.sandbox.grounding import tool_provider


class RunController(sandbox_run_control.RunController, InTier[AgentSessionTier]):
    """Coordinates session termination tools and verification caching."""

    def __init__(self) -> None:
        self._cached_passed: bool = False
        self._cached_feedback: str = ""
        self._cached_hashes: Mapping[
            agent_file_alias.FileAlias, sandbox_file_editor.FileHash
        ] = {}

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """
        COVERED:
        - MUST expose configured verification checks from node configuration.
        """
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)
        _checks: Sequence[agent_node_config.VerificationCheck] = (
            node_cfg.verification_checks
        )
        raise NotImplementedError

    def update_verification(self) -> None:
        """
        COVERED:
        - MUST cache verification evaluations alongside target file hashes, evaluating sequentially when outdated.
          - Condition knowledge: resolve NodeConfig, EditManager; query file hashes.
          - Consequent knowledge: evaluate checks sequentially and update self._cached_passed, self._cached_feedback, and self._cached_hashes.
        - WHEN target file hashes have not changed since previous evaluation, MUST omit check execution and reuse cached outcome.
          - Condition knowledge: compare current hashes to self._cached_hashes.
          - Consequent knowledge: reuse cached outcome."""
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)
        edit_mgr = self.get_singleton(sandbox_file_editor.EditManager)

        sample_rw = only_elem(node_cfg.read_write_files)
        curr_hash = edit_mgr.file_hash(sample_rw)
        _hashes_unchanged: bool = self._cached_hashes.get(sample_rw) == curr_hash

        checks = self.verification_checks
        sample_check = only_elem(checks)
        passed, diag = sample_check.verify()

        self._cached_passed = passed
        self._cached_feedback = str(diag)
        self._cached_hashes = {sample_rw: curr_hash}
        raise NotImplementedError


class CheckFilesTool(sandbox_run_control.CheckFilesTool, InTier[AgentSessionTier]):
    """Realizes verification check execution and diagnostic aggregation."""

    @property
    def name(self) -> tool_provider.ToolName:
        """
        COVERED:
        - Returns tool name.
        """
        _name = tool_provider.ToolName("check_files")
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        COVERED:
        - Returns tool description.
        """
        _desc = tool_provider.ToolDescription(
            "Inspect verification checks across session files."
        )
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        COVERED:
        - Returns tool parameters mapping.
        """
        _params: Mapping[
            tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]
        ] = {}
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - WHEN target file hashes have not changed since previous check, MUST remind agent that verification status is unchanged.
          - Condition knowledge: test whether hashes changed since last check.
          - Consequent knowledge: return ToolResponse with reminder "Verification status is unchanged.".
        - WHEN verification fails, MUST present sanitized diagnostic feedback alongside verification failure instructions.
          - Condition knowledge: evaluate not controller._cached_passed.
          - Consequent knowledge: resolve AliasManager, sanitize diagnostic text, append guide verification failure instructions.
        - WHEN verification passes, MUST produce response presenting passing results.
          - Condition knowledge: evaluate controller._cached_passed.
          - Consequent knowledge: construct passing ToolResponse with verification success message."""
        controller = self.get_singleton(RunController)
        alias_mgr = self.get_singleton(agent_file_alias.AliasManager)
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)

        controller.update_verification()

        # Unchanged hashes reminder knowledge
        _unchanged_resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content="Verification status is unchanged from previous check.",
            reminder=tool_provider.ToolReminder("Verification status is unchanged."),
        )

        # Failing verification knowledge
        sanitized_diag = alias_mgr.sanitize_text(
            agent_file_alias.UnsanitizedText(controller._cached_feedback)
        )
        guide_vf = agent_node_config.VerificationFailureInstructions(
            "Failure instructions."
        )
        _fail_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Verification failed:\n{sanitized_diag}\n\nInstructions:\n{guide_vf}",
        )

        # Passing verification knowledge
        success_msg = (
            node_cfg.verification_success_message or "All verification checks passed."
        )
        _pass_resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=str(success_msg),
        )
        raise NotImplementedError


class AdvanceTool(sandbox_run_control.AdvanceTool, InTier[AgentSessionTier]):
    """Realizes guide milestone advancement gated by verification checks."""

    @property
    def name(self) -> tool_provider.ToolName:
        """
        COVERED:
        - Returns tool name.
        """
        _name = tool_provider.ToolName("advance")
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        COVERED:
        - Returns tool description.
        """
        _desc = tool_provider.ToolDescription(
            "Advance guide milestone upon passing verification."
        )
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        COVERED:
        - Returns tool parameters mapping.
        """
        _params: Mapping[
            tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]
        ] = {}
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - WHEN verification is failing on first step, MUST repeat primer and summary content through guide delivery.
          - Condition knowledge: test not controller._cached_passed and delivery._step_index == 0.
          - Consequent knowledge: deliver primer and summary via GuideDelivery.
        - WHEN verification is failing, MUST remind agent to call check files first and specify follow-up execution of check files.
          - Condition knowledge: test not controller._cached_passed.
          - Consequent knowledge: return failed ToolResponse with reminder and FollowUpToolCall for check_files.
        - WHEN verification passes and guide steps remain, MUST deliver next step section.
          - Condition knowledge: test controller._cached_passed and delivery.has_steps_remaining.
          - Consequent knowledge: invoke delivery.advance_step and deliver section content.
        - WHEN verification passes, no steps remain, and files were modified, MUST fail reminding agent to call submit with change summary.
          - Condition knowledge: test controller._cached_passed, not delivery.has_steps_remaining, edit_mgr.has_modifications.
          - Consequent knowledge: return failed ToolResponse reminding to call submit with change_summary.
        - WHEN verification passes, no steps remain, and no files were modified, MUST specify follow-up execution of submit without change summary.
          - Condition knowledge: test controller._cached_passed, not delivery.has_steps_remaining, not edit_mgr.has_modifications.
          - Consequent knowledge: return ToolResponse with FollowUpToolCall for submit without change_summary."""
        controller = self.get_singleton(RunController)
        delivery = self.get_singleton(sandbox_guide_delivery.GuideDelivery)
        edit_mgr = self.get_singleton(sandbox_file_editor.EditManager)

        # 1. Failing verification on first step vs later step knowledge
        _check_followup = tool_provider.FollowUpToolCall(
            tool_name=tool_provider.ToolName("check_files"),
            wire_parameter_bindings={},
        )
        _fail_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Verification failing. Please run check_files first.",
            reminder=tool_provider.ToolReminder("Call check_files before advancing."),
            follow_up_tool_call=_check_followup,
        )

        # 2. Passing with remaining steps knowledge
        step_resp = delivery.advance_step(
            True, agent_node_config.VerificationDiagnostic("")
        )

        # 3. Passing with no steps remaining and files modified knowledge
        _submit_needed_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="All guide steps complete. Please call submit with a change_summary.",
            reminder=tool_provider.ToolReminder("Call submit with change_summary."),
        )

        # 4. Passing with no steps remaining and no files modified knowledge
        _submit_followup = tool_provider.FollowUpToolCall(
            tool_name=tool_provider.ToolName("submit"),
            wire_parameter_bindings={},
        )
        _auto_submit_resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content="All guide steps complete without file modifications. Submitting task.",
            follow_up_tool_call=_submit_followup,
        )

        _final_resp: Optional[tool_provider.ToolResponse] = step_resp
        raise NotImplementedError


class SubmitTool(sandbox_run_control.SubmitTool, InTier[AgentSessionTier]):
    """Realizes node completion verification and clean submission."""

    def __init__(self) -> None:
        self._target_param = tool_provider.ToolParameter[
            agent_file_alias.FileAlias, str
        ](
            name=tool_provider.ParameterName("target"),
            description="Target file to submit",
            parameter_type=tool_provider.SimpleParameterType[
                agent_file_alias.FileAlias, str
            ](),
            is_required=False,
            default_value=None,
            missing_message=None,
        )
        self._summary_param = tool_provider.ToolParameter[
            Optional[sandbox_run_control.ChangeSummary], str
        ](
            name=tool_provider.ParameterName("change_summary"),
            description="Summary of changes made",
            parameter_type=tool_provider.SimpleParameterType[
                Optional[sandbox_run_control.ChangeSummary], str
            ](),
            is_required=False,
            default_value=None,
            missing_message=None,
        )

    @property
    def name(self) -> tool_provider.ToolName:
        """
        COVERED:
        - Returns tool name.
        """
        _name = tool_provider.ToolName("submit")
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        COVERED:
        - Returns tool description.
        """
        _desc = tool_provider.ToolDescription("Submit node work as cleanly completed.")
        raise NotImplementedError

    @property
    def target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """
        COVERED:
        - Exposes target parameter.
        """
        _param = self._target_param
        raise NotImplementedError

    @property
    def change_summary_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[sandbox_run_control.ChangeSummary], str]:
        """
        COVERED:
        - Exposes change summary parameter.
        """
        _param = self._summary_param
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        COVERED:
        - Returns tool parameters mapping.
        """
        _params = {
            self._target_param.name: self._target_param,
            self._summary_param.name: self._summary_param,
        }
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - WHEN guide step mode is active and guide steps remain, MUST fail specifying advance as follow-up tool call.
          - Condition knowledge: test node_cfg.is_step_mode and delivery.has_steps_remaining.
          - Consequent knowledge: return failed ToolResponse with FollowUpToolCall for advance.
        - WHEN verification is failing, MUST fail specifying follow-up execution of check files.
          - Condition knowledge: test not controller._cached_passed.
          - Consequent knowledge: return failed ToolResponse with FollowUpToolCall for check_files.
        - WHEN an initial implementation change is assigned and no files were modified, MUST fail.
          - Condition knowledge: test initial implementation task and not edit_mgr.has_modifications.
          - Consequent knowledge: return failed ToolResponse.
        - WHEN session feedback is present and no files were modified, MUST fail.
          - Condition knowledge: test bool(node_cfg.feedback) and not edit_mgr.has_modifications.
          - Consequent knowledge: return failed ToolResponse citing feedback without modifications.
        - WHEN target is an auditor node and change summary is provided, MUST fail reminding agent that change summary is prohibited for audit nodes.
          - Condition knowledge: test role is auditor and change_summary is not None.
          - Consequent knowledge: return failed ToolResponse reminding that change summary is prohibited for audit nodes.
        - WHEN files were modified and change summary is omitted, MUST fail.
          - Condition knowledge: test edit_mgr.has_modifications and change_summary is None.
          - Consequent knowledge: return failed ToolResponse reminding that change_summary is required.
        - WHEN workspace files were not modified and change summary is provided, MUST fail reminding agent that change summaries are not permitted when submitting without workspace file modifications.
          - Condition knowledge: test not edit_mgr.has_modifications and change_summary is not None.
          - Consequent knowledge: return failed ToolResponse reminding that change summaries are not permitted without modifications.
        - MUST mark the resolve target clean in storage via dag_storage with the provided change summary so that the node is no longer dirty.
          - Condition knowledge: obtain DagStorage singleton.
          - Consequent knowledge: invoke storage.mark_node_clean and assert not storage.is_dirty.
        - MUST mark resolve target clean in current turn.
          - Consequent knowledge: return terminating ToolResponse.
        """
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)
        delivery = self.get_singleton(sandbox_guide_delivery.GuideDelivery)
        controller = self.get_singleton(RunController)
        edit_mgr = self.get_singleton(sandbox_file_editor.EditManager)
        storage = self.get_singleton(dag_storage.DagStorage)

        # 1. Unfinished guide steps failure knowledge
        _advance_followup = tool_provider.FollowUpToolCall(
            tool_name=tool_provider.ToolName("advance"),
            wire_parameter_bindings={},
        )
        _steps_remain_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Guide steps remain to be completed.",
            follow_up_tool_call=_advance_followup,
        )

        # 2. Failing verification failure knowledge
        _check_followup = tool_provider.FollowUpToolCall(
            tool_name=tool_provider.ToolName("check_files"),
            wire_parameter_bindings={},
        )
        _vf_fail_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Verification checks are currently failing.",
            follow_up_tool_call=_check_followup,
        )

        # 3. Unmodified with feedback failure knowledge
        _has_feedback: bool = len(node_cfg.feedback) > 0
        _feedback_unmodified_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Node feedback was delivered but no file modifications were made.",
        )

        # 4. Auditor with change summary failure knowledge
        sample_node = key(node_cfg.blame_targets_by_node)
        _is_auditor: bool = "qa" in str(sample_node.role_address) or "coverage" in str(
            sample_node.role_address
        )
        _auditor_summary_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Change summary is prohibited for audit nodes.",
            reminder=tool_provider.ToolReminder(
                "Do not provide change_summary for audit nodes."
            ),
        )

        # 5. Modified without change summary failure knowledge
        _missing_summary_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Files were modified but change_summary parameter was omitted.",
            reminder=tool_provider.ToolReminder(
                "Supply change_summary when files were modified."
            ),
        )

        # 5b. Unmodified with change summary failure knowledge
        _unmodified_summary_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Workspace files were not modified, but change_summary was provided.",
            reminder=tool_provider.ToolReminder(
                "Omit change_summary when submitting without workspace file modifications."
            ),
        )

        # 6. Clean submission knowledge via dag_storage
        storage.mark_node_clean(
            sample_node, dag_storage.ChangeDescription("Summary of changes")
        )
        _is_dirty: bool = storage.is_dirty(sample_node)

        _submit_resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=True,
            content="Task completed and cleanly submitted.",
        )
        raise NotImplementedError


class FailTool(sandbox_run_control.FailTool, InTier[AgentSessionTier]):
    """Realizes task failure termination."""

    def __init__(self) -> None:
        self._target_param = tool_provider.ToolParameter[
            agent_file_alias.FileAlias, str
        ](
            name=tool_provider.ParameterName("target"),
            description="Target file that failed",
            parameter_type=tool_provider.SimpleParameterType[
                agent_file_alias.FileAlias, str
            ](),
            is_required=False,
            default_value=None,
            missing_message=None,
        )
        self._exp_param = tool_provider.ToolParameter[
            sandbox_run_control.FailureExplanation, str
        ](
            name=tool_provider.ParameterName("explanation"),
            description="Failure explanation",
            parameter_type=tool_provider.SimpleParameterType[
                sandbox_run_control.FailureExplanation, str
            ](),
            is_required=True,
            default_value=None,
            missing_message=None,
        )

    @property
    def name(self) -> tool_provider.ToolName:
        """
        COVERED:
        - Returns tool name.
        """
        _name = tool_provider.ToolName("fail")
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        COVERED:
        - Returns tool description.
        """
        _desc = tool_provider.ToolDescription(
            "Terminate active node execution in failure."
        )
        raise NotImplementedError

    @property
    def target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """
        COVERED:
        - Exposes target parameter.
        """
        _param = self._target_param
        raise NotImplementedError

    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[sandbox_run_control.FailureExplanation, str]:
        """
        COVERED:
        - Exposes explanation parameter.
        """
        _param = self._exp_param
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        COVERED:
        - Returns tool parameters mapping.
        """
        _params = {
            self._target_param.name: self._target_param,
            self._exp_param.name: self._exp_param,
        }
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - MUST mark active node as failed.
          - Consequent knowledge: return terminating failed ToolResponse carrying failure explanation.
        """
        _fail_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=True,
            content="Task marked as failed.",
        )
        raise NotImplementedError


class BlameTool(sandbox_run_control.BlameTool, InTier[AgentSessionTier]):
    """Realizes defect attribution to upstream prerequisites."""

    def __init__(self) -> None:
        self._target_param = tool_provider.ToolParameter[
            agent_file_alias.FileAlias, str
        ](
            name=tool_provider.ParameterName("target"),
            description="Target file",
            parameter_type=tool_provider.SimpleParameterType[
                agent_file_alias.FileAlias, str
            ](),
            is_required=False,
            default_value=None,
            missing_message=None,
        )
        self._blame_target_param = tool_provider.ToolParameter[
            agent_file_alias.FileAlias, str
        ](
            name=tool_provider.ParameterName("blame_target"),
            description="Blamed prerequisite",
            parameter_type=tool_provider.SimpleParameterType[
                agent_file_alias.FileAlias, str
            ](),
            is_required=True,
            default_value=None,
            missing_message=None,
        )
        self._exp_param = tool_provider.ToolParameter[
            sandbox_run_control.BlameExplanation, str
        ](
            name=tool_provider.ParameterName("explanation"),
            description="Blame explanation",
            parameter_type=tool_provider.SimpleParameterType[
                sandbox_run_control.BlameExplanation, str
            ](),
            is_required=True,
            default_value=None,
            missing_message=None,
        )

    @property
    def name(self) -> tool_provider.ToolName:
        """
        COVERED:
        - Returns tool name.
        """
        _name = tool_provider.ToolName("blame")
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        COVERED:
        - Returns tool description.
        """
        _desc = tool_provider.ToolDescription(
            "Attribute defect to an upstream prerequisite."
        )
        raise NotImplementedError

    @property
    def target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """
        COVERED:
        - Exposes target parameter.
        """
        _param = self._target_param
        raise NotImplementedError

    @property
    def blame_target_parameter(
        self,
    ) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        """
        COVERED:
        - Exposes blame target parameter.
        """
        _param = self._blame_target_param
        raise NotImplementedError

    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[sandbox_run_control.BlameExplanation, str]:
        """
        COVERED:
        - Exposes explanation parameter.
        """
        _param = self._exp_param
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        COVERED:
        - Returns tool parameters mapping.
        """
        _params = {
            self._target_param.name: self._target_param,
            self._blame_target_param.name: self._blame_target_param,
            self._exp_param.name: self._exp_param,
        }
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - MUST identify active node attributing blame from specified blame target.
          - Condition knowledge: test blame target matching across blame targets of active nodes.
          - Consequent knowledge: identify active node attributing blame.
        - WHEN blame target is omitted in single-target context, MUST default to single configured blame target of active node.
          - Condition knowledge: test blame target omitted, single configured blame target available.
          - Consequent knowledge: default blame target to single configured blame target.
        - WHEN blame target does not match any configured blame target, MUST fail listing available blame targets.
          - Condition knowledge: test blame_target not in blame_targets.
          - Consequent knowledge: return failed ToolResponse listing configured blame targets.
        - WHEN explanation contains newline characters, MUST fail reminding agent that explanation must be a single paragraph.
          - Condition knowledge: test newline character in explanation.
          - Consequent knowledge: return failed ToolResponse with single-paragraph reminder.
        - MUST record defect feedback for the blamed target via dag_storage so that the blamed node receives the feedback message.
          - Condition knowledge: obtain DagStorage singleton and construct FeedbackMessage.
          - Consequent knowledge: invoke storage.add_message with blamed node.
        - MUST mark blame target as attributed.
          - Consequent knowledge: return terminating ToolResponse citing blamed prerequisite.
        """
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)
        storage = self.get_singleton(dag_storage.DagStorage)

        sample_node = key(node_cfg.blame_targets_by_node)
        blame_targets = node_cfg.blame_targets_by_node[sample_node]
        sample_target = only_elem(blame_targets)

        # 1. Identify active node attributing blame and default single target
        _identified_node = sample_node
        _default_target = sample_target

        # 2. Invalid blame target failure knowledge
        _invalid_blame_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content=f"Error: Unknown blame target. Available blame targets: {sample_target.relative_path}",
        )

        # 3. Multi-line explanation failure knowledge
        explanation_str = "Explanation line 1\nExplanation line 2"
        _has_newline: bool = "\n" in explanation_str
        _newline_fail_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Error: Explanation must be a single paragraph without newline characters.",
            reminder=tool_provider.ToolReminder(
                "Explanation must be a single paragraph."
            ),
        )

        # 4. Attribution and defect feedback recording knowledge via dag_storage
        blamed_node = getattr(sample_target, "owning_node", sample_node)
        storage.add_message(
            dag_storage.FeedbackMessage(
                content=dag_storage.MessageContent(explanation_str),
                target=blamed_node,
            ),
            to=blamed_node,
        )
        _blame_attributed_str = (
            f"Blamed {sample_target.relative_path}: defect detected."
        )

        _blame_resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=True,
            content=_blame_attributed_str,
        )
        raise NotImplementedError


class GetWorkTool(sandbox_run_control.GetWorkTool, InTier[AgentSessionTier]):
    """Realizes batch acquisition and session task prompt delivery."""

    def __init__(self) -> None:
        self._batch_param = tool_provider.ToolParameter[
            Optional[dag_config.BatchSize], int
        ](
            name=tool_provider.ParameterName("max_batch_size"),
            description="Maximum batch size",
            parameter_type=tool_provider.SimpleParameterType[
                Optional[dag_config.BatchSize], int
            ](),
            is_required=False,
            default_value=None,
            missing_message=None,
        )

    @property
    def name(self) -> tool_provider.ToolName:
        """
        COVERED:
        - Returns tool name.
        """
        _name = tool_provider.ToolName("get_work")
        raise NotImplementedError

    @property
    def description(self) -> tool_provider.ToolDescription:
        """
        COVERED:
        - Returns tool description.
        """
        _desc = tool_provider.ToolDescription("Acquire dirty nodes for execution.")
        raise NotImplementedError

    @property
    def max_batch_size_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[dag_config.BatchSize], int]:
        """
        COVERED:
        - Exposes max batch size parameter.
        """
        _param = self._batch_param
        raise NotImplementedError

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        """
        COVERED:
        - Returns tool parameters mapping.
        """
        _params = {self._batch_param.name: self._batch_param}
        raise NotImplementedError

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        """
        COVERED:
        - WHEN open active nodes remain, MUST fail reminding agent to resolve open nodes.
          - Condition knowledge: test open active nodes count > 0.
          - Consequent knowledge: return failed ToolResponse.
        - WHEN no dirty nodes are ready, MUST produce an idle response.
          - Condition knowledge: test subgraph.next_ready_batch() is empty.
          - Consequent knowledge: return idle ToolResponse.
        - WHEN ready dirty nodes are obtained and guide step mode is inactive, MUST return task primer with guide file attribution.
          - Condition knowledge: test ready nodes obtained and not node_cfg.is_step_mode.
          - Consequent knowledge: return ToolResponse with task primer referencing guide file.
        - WHEN ready dirty nodes are obtained and guide step mode is active, MUST return task primer prompting advance.
          - Condition knowledge: test ready nodes obtained and node_cfg.is_step_mode.
          - Consequent knowledge: return ToolResponse prompting advance."""
        subgraph = self.get_singleton(dag_subgraph.DagSubgraph)
        storage = self.get_singleton(dag_storage.DagStorage)
        node_cfg = self.get_singleton(agent_node_config.NodeConfig)

        # 1. Open nodes failure knowledge
        _open_nodes_resp = tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=False,
            content="Error: Open active nodes remain. Resolve open nodes before requesting more work.",
        )

        # 2. Idle response knowledge
        batch = subgraph.next_ready_batch()
        _is_empty_batch: bool = len(batch) == 0
        _idle_resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content="No ready dirty nodes found in graph.",
        )

        # 3. Materialize templates and build task primer knowledge
        sample_node = only_elem(batch)
        storage.materialize_template(sample_node)

        _step_mode: bool = node_cfg.is_step_mode
        primer_text = "Task primer: follow guide step mode by calling advance."

        _work_resp = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=primer_text,
        )
        raise NotImplementedError


def __initialize__() -> None:
    """Initializes run control singletons in the agent session tier."""
    _controller: RunController = cast(RunController, None)
    _check: CheckFilesTool = cast(CheckFilesTool, None)
    _advance: AdvanceTool = cast(AdvanceTool, None)
    _submit: SubmitTool = cast(SubmitTool, None)
    _fail: FailTool = cast(FailTool, None)
    _blame: BlameTool = cast(BlameTool, None)
    _get_work: GetWorkTool = cast(GetWorkTool, None)
