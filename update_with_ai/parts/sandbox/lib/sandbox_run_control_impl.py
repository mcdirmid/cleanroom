# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:46:30Z
# LAST_CHANGED: 2026-10-09T22:40:00Z
# CHANGE: Remove initial implementation modification constraint on submission
# CODE_HASH: a6af47232ea7
# QA_AUDIT: 2026-10-09T21:46:30Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Set, cast
from support.lib.lifecycle import (
    InTier,
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier, agent_session
import update_with_ai.parts.agent.lib.agent_file_alias as agent_file_alias
import update_with_ai.parts.agent.lib.agent_node_config as agent_node_config
import update_with_ai.parts.control.lib.control_coordinate as control_coordinate
import update_with_ai.parts.dag.lib.dag_config as dag_config
import update_with_ai.parts.dag.lib.dag_storage as dag_storage
import update_with_ai.parts.dag.lib.dag_subgraph as dag_subgraph
from . import sandbox
from . import sandbox_file_editor
from . import sandbox_guide_delivery
from . import sandbox_run_control
from . import template_format
from . import tool_provider

# Requirements specified in sandbox_run_control_impl.pyi


@dataclass(frozen=True)
class _ChangeSummaryParamType(tool_provider.ParameterType[Optional[sandbox_run_control.ChangeSummary], str]):
    @property
    def actual_type(self) -> type[Optional[sandbox_run_control.ChangeSummary]]:
        return cast(type[Optional[sandbox_run_control.ChangeSummary]], sandbox_run_control.ChangeSummary)

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> Optional[sandbox_run_control.ChangeSummary]:
        if wire_value is None:
            return None
        if not isinstance(wire_value, str):
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(
                    f"Expected str for change_summary, got {type(wire_value).__name__}"
                )
            )
        stripped = wire_value.strip()
        if not stripped:
            return None
        return sandbox_run_control.ChangeSummary(stripped)


@dataclass(frozen=True)
class _FailureExplanationParamType(tool_provider.ParameterType[sandbox_run_control.FailureExplanation, str]):
    @property
    def actual_type(self) -> type[sandbox_run_control.FailureExplanation]:
        return cast(type[sandbox_run_control.FailureExplanation], sandbox_run_control.FailureExplanation)

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> sandbox_run_control.FailureExplanation:
        if not isinstance(wire_value, str):
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(
                    f"Expected str for explanation, got {type(wire_value).__name__}"
                )
            )
        return sandbox_run_control.FailureExplanation(wire_value)


@dataclass(frozen=True)
class _BlameExplanationParamType(tool_provider.ParameterType[sandbox_run_control.BlameExplanation, str]):
    @property
    def actual_type(self) -> type[sandbox_run_control.BlameExplanation]:
        return cast(type[sandbox_run_control.BlameExplanation], sandbox_run_control.BlameExplanation)

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> sandbox_run_control.BlameExplanation:
        if not isinstance(wire_value, str):
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(
                    f"Expected str for explanation, got {type(wire_value).__name__}"
                )
            )
        return sandbox_run_control.BlameExplanation(wire_value)


@dataclass(frozen=True)
class _BatchSizeParamType(tool_provider.ParameterType[Optional[dag_config.BatchSize], int]):
    @property
    def actual_type(self) -> type[Optional[dag_config.BatchSize]]:
        return cast(type[Optional[dag_config.BatchSize]], dag_config.BatchSize)

    @property
    def wire_type(self) -> type[int]:
        return int

    def convert(self, wire_value: int) -> Optional[dag_config.BatchSize]:
        if wire_value is None:
            return None
        if isinstance(wire_value, bool) or not isinstance(wire_value, int):
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(
                    f"Expected int for max_batch_size, got {type(wire_value).__name__}"
                )
            )
        return dag_config.BatchSize(wire_value)


class CheckFilesTool(sandbox_run_control.CheckFilesTool, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("check_files")
        self._description = tool_provider.ToolDescription("Inspects verification checks across active files.")
        self._parameters: Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]] = {}

    @property
    def name(self) -> tool_provider.ToolName:
        return self._name

    @property
    def description(self) -> tool_provider.ToolDescription:
        return self._description

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        run_ctrl = get_singleton(sandbox_run_control.RunController)
        run_ctrl.update_verification()

        if getattr(run_ctrl, "_is_unchanged", False):
            return tool_provider.ToolResponse(
                is_failed=not getattr(run_ctrl, "_passed", True),
                is_terminated=False,
                content=tool_provider.ToolResponseContent("Verification status is unchanged."),
                reminder=tool_provider.ToolReminder(
                    "Verification status is unchanged because target files have not been modified since the previous check."
                ),
            )

        if not getattr(run_ctrl, "_passed", True):
            raw_diag = getattr(run_ctrl, "_diagnostic_output", "")
            alias_mgr = get_singleton(agent_file_alias.AliasManager)
            sanitized_diag = str(alias_mgr.sanitize_text(agent_file_alias.UnsanitizedText(raw_diag)))
            node_cfg = get_singleton(agent_node_config.NodeConfig)
            instructions = ""
            if node_cfg.guide and node_cfg.guide.verification_failure:
                instructions = str(node_cfg.guide.verification_failure)

            parts = []
            if sanitized_diag:
                parts.append(sanitized_diag)
            if instructions:
                parts.append(instructions)
            msg = "\n\n".join(parts) if parts else "Verification failed."

            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(msg),
                reminder=tool_provider.ToolReminder("Fix the verification failures before proceeding."),
            )

        node_cfg = get_singleton(agent_node_config.NodeConfig)
        success_msg = (
            str(node_cfg.verification_success_message)
            if getattr(node_cfg, "verification_success_message", None)
            else "All verification checks passed."
        )
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(success_msg),
        )


class AdvanceTool(sandbox_run_control.AdvanceTool, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("advance")
        self._description = tool_provider.ToolDescription("Advances progressive guide steps upon passing verification.")
        self._parameters: Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]] = {}

    @property
    def name(self) -> tool_provider.ToolName:
        return self._name

    @property
    def description(self) -> tool_provider.ToolDescription:
        return self._description

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        run_ctrl = get_singleton(sandbox_run_control.RunController)
        run_ctrl.update_verification()

        guide_deliv = get_singleton(sandbox_guide_delivery.GuideDelivery)
        if not getattr(run_ctrl, "_passed", True):
            raw_diag = getattr(run_ctrl, "_diagnostic_output", "")
            resp = cast(
                tool_provider.ToolResponse,
                guide_deliv.advance_step(
                    verification_passed=False,
                    failure_diagnostics=agent_node_config.VerificationDiagnostic(raw_diag),
                ),
            )
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=resp.content,
                reminder=tool_provider.ToolReminder("Call check_files first to diagnose and resolve verification failures."),
                follow_up_tool_call=tool_provider.FollowUpToolCall(
                    tool_name=tool_provider.ToolName("check_files"),
                    wire_parameter_bindings={},
                ),
            )

        if guide_deliv.has_steps_remaining:
            return cast(
                tool_provider.ToolResponse,
                guide_deliv.advance_step(
                    verification_passed=True,
                    failure_diagnostics=agent_node_config.VerificationDiagnostic(""),
                ),
            )

        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        if edit_mgr.has_modifications:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    "All guide milestone steps completed. Workspace files were modified; call submit with a change summary."
                ),
                reminder=tool_provider.ToolReminder("Call submit with change_summary."),
            )

        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(
                "All guide milestone steps completed. No files were modified."
            ),
            follow_up_tool_call=tool_provider.FollowUpToolCall(
                tool_name=tool_provider.ToolName("submit"),
                wire_parameter_bindings={},
            ),
        )


def _is_auditor_node(node: Optional[dag_storage.DagNode]) -> bool:
    candidate_roles: list[str] = []
    if node is not None:
        candidate_roles.append(str(node.role_address).split(":")[-1].strip().lower())
    role_service = get_singleton(agent_node_config.RoleConfig)
    if role_service and getattr(role_service, "role", None):
        candidate_roles.append(str(role_service.role).split(":")[-1].strip().lower())

    cfg = get_singleton(agent_node_config.NodeConfig)
    role_defs = getattr(cfg, "role_definitions", {})
    if isinstance(role_defs, dict):
        for r in candidate_roles:
            role_cfg = role_defs.get(r)
            if role_cfg is not None:
                if (
                    getattr(role_cfg, "is_auditor", False)
                    or getattr(role_cfg, "audit_tag", None)
                    or not getattr(role_cfg, "src_pattern", "")
                    or (hasattr(role_cfg, "writable_file_patterns") and not role_cfg.writable_file_patterns)
                ):
                    return True
                return False

    for r in candidate_roles:
        if (
            r.endswith(("_qa", "_audit", "_auditor", "_coverage"))
            or r.startswith(("qa_", "audit_"))
            or r in ("qa", "audit", "coverage")
            or "qa" in r
            or "audit" in r
            or "coverage" in r
        ):
            return True

    return False


class SubmitTool(sandbox_run_control.SubmitTool, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("submit")
        self._description = tool_provider.ToolDescription("Marks an active node complete upon passing verification.")
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        self._target_parameter = tool_provider.ToolParameter[agent_file_alias.FileAlias, str](
            name=tool_provider.ParameterName("target"),
            description=tool_provider.ParameterDescription("Target file alias to submit."),
            parameter_type=alias_mgr,
            is_required=False,
            default_value=None,
        )
        self._change_summary_parameter = tool_provider.ToolParameter[Optional[sandbox_run_control.ChangeSummary], str](
            name=tool_provider.ParameterName("change_summary"),
            description=tool_provider.ParameterDescription("Description of changes made during the task."),
            parameter_type=_ChangeSummaryParamType(),
            is_required=False,
            default_value=None,
        )
        self._parameters: Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]] = {
            self._target_parameter.name: self._target_parameter,
            self._change_summary_parameter.name: self._change_summary_parameter,
        }

    @property
    def name(self) -> tool_provider.ToolName:
        return self._name

    @property
    def description(self) -> tool_provider.ToolDescription:
        return self._description

    @property
    def target_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        return self._target_parameter

    @property
    def change_summary_parameter(self) -> tool_provider.ToolParameter[Optional[sandbox_run_control.ChangeSummary], str]:
        return self._change_summary_parameter

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        node_cfg = get_singleton(agent_node_config.NodeConfig)
        guide_deliv = get_singleton(sandbox_guide_delivery.GuideDelivery)
        if node_cfg.is_step_mode and guide_deliv.has_steps_remaining:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    "Guide step mode is active and guide steps remain. Advance through all steps before submitting."
                ),
                reminder=tool_provider.ToolReminder("Call advance to continue."),
                follow_up_tool_call=tool_provider.FollowUpToolCall(
                    tool_name=tool_provider.ToolName("advance"),
                    wire_parameter_bindings={},
                ),
            )

        run_ctrl = get_singleton(sandbox_run_control.RunController)
        run_ctrl.update_verification()
        if not getattr(run_ctrl, "_passed", True):
            raw_diag = getattr(run_ctrl, "_diagnostic_output", "")
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Verification is failing. Please fix errors before submitting.\n{raw_diag}"
                ),
                reminder=tool_provider.ToolReminder("Call check_files to view verification diagnostics."),
                follow_up_tool_call=tool_provider.FollowUpToolCall(
                    tool_name=tool_provider.ToolName("check_files"),
                    wire_parameter_bindings={},
                ),
            )

        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        has_mods = edit_mgr.has_modifications

        raw_target = cast(Optional[agent_file_alias.FileAlias], actual_parameter_bindings.get(self.target_parameter))
        target_alias = str(raw_target.relative_path) if raw_target is not None else None
        raw_summary = actual_parameter_bindings.get(self.change_summary_parameter)
        change_summary_str = str(raw_summary).strip() if (raw_summary is not None and str(raw_summary).strip()) else None

        coord = get_singleton(control_coordinate.SessionCoordinator)
        target_node = coord.get_node_for_alias(target_alias) if target_alias else coord.resolve_default_target()

        is_auditor = _is_auditor_node(target_node)
        if is_auditor and change_summary_str:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    "Error: Change summary is prohibited for audit nodes."
                ),
                reminder=tool_provider.ToolReminder(
                    "Change summary is prohibited for audit nodes. Call submit without change_summary."
                ),
            )

        if not is_auditor:
            if has_mods and not change_summary_str:
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        "Error: Workspace files were modified, so change_summary must be provided."
                    ),
                    reminder=tool_provider.ToolReminder(
                        "Please provide a change_summary describing your modifications."
                    ),
                )
            if not has_mods and change_summary_str:
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        "Error: Change summaries are not permitted when submitting without workspace file modifications."
                    ),
                    reminder=tool_provider.ToolReminder(
                        "Change summaries are not permitted when submitting without workspace file modifications."
                    ),
                )

        if not is_auditor and not has_mods:
            node_msgs: Set[dag_storage.DagMessage] = set()
            if target_node is not None:
                storage = get_singleton(dag_storage.DagStorage)
                node_msgs = storage.get_messages(target_node)

            has_feedback = bool(getattr(node_cfg, "feedback", None)) or any(
                isinstance(m, dag_storage.FeedbackMessage) for m in node_msgs
            )
            if not has_feedback and target_node is not None and hasattr(node_cfg, "per_node_info_by_node") and node_cfg.per_node_info_by_node:
                info = node_cfg.per_node_info_by_node.get(target_node)
                if info and getattr(info, "feedback", None):
                    has_feedback = True

            if has_feedback:
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        "Error: Session feedback is present but no workspace files were modified."
                    ),
                )

        outcome = coord.dispatch_submit(
            target_alias=target_alias,
            change_summary=change_summary_str,
            has_modifications=has_mods,
        )

        if not outcome.success:
            reminder = None
            if "change_summary" in outcome.message.lower() or "change summaries" in outcome.message.lower():
                reminder = tool_provider.ToolReminder(
                    "Please provide an appropriate change_summary or omit it as instructed."
                )
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(outcome.message),
                reminder=reminder,
            )

        is_term = not bool(coord.open_targets)
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=is_term,
            content=tool_provider.ToolResponseContent(outcome.message),
        )


class FailTool(sandbox_run_control.FailTool, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("fail")
        self._description = tool_provider.ToolDescription("Fails the active node and terminates session execution.")
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        self._target_parameter = tool_provider.ToolParameter[agent_file_alias.FileAlias, str](
            name=tool_provider.ParameterName("target"),
            description=tool_provider.ParameterDescription("Target file alias to fail."),
            parameter_type=alias_mgr,
            is_required=False,
            default_value=None,
        )
        self._explanation_parameter = tool_provider.ToolParameter[sandbox_run_control.FailureExplanation, str](
            name=tool_provider.ParameterName("explanation"),
            description=tool_provider.ParameterDescription("Explanation of failure reason."),
            parameter_type=_FailureExplanationParamType(),
            is_required=True,
            default_value=None,
        )
        self._parameters: Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]] = {
            self._target_parameter.name: self._target_parameter,
            self._explanation_parameter.name: self._explanation_parameter,
        }

    @property
    def name(self) -> tool_provider.ToolName:
        return self._name

    @property
    def description(self) -> tool_provider.ToolDescription:
        return self._description

    @property
    def target_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        return self._target_parameter

    @property
    def explanation_parameter(self) -> tool_provider.ToolParameter[sandbox_run_control.FailureExplanation, str]:
        return self._explanation_parameter

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        raw_target = cast(Optional[agent_file_alias.FileAlias], actual_parameter_bindings.get(self.target_parameter))
        target_alias = str(raw_target.relative_path) if raw_target is not None else None
        raw_expl = actual_parameter_bindings.get(self.explanation_parameter)
        explanation = str(raw_expl) if raw_expl is not None else ""

        coord = get_singleton(control_coordinate.SessionCoordinator)
        outcome = coord.dispatch_fail(target_alias=target_alias, explanation=explanation)
        return tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=True,
            content=tool_provider.ToolResponseContent(outcome.message),
        )


class BlameTool(sandbox_run_control.BlameTool, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("blame")
        self._description = tool_provider.ToolDescription("Attributes failure to an upstream dependency node.")
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        self._target_parameter = tool_provider.ToolParameter[agent_file_alias.FileAlias, str](
            name=tool_provider.ParameterName("target"),
            description=tool_provider.ParameterDescription("Active node file alias attributing blame."),
            parameter_type=alias_mgr,
            is_required=False,
            default_value=None,
        )
        self._blame_target_parameter = tool_provider.ToolParameter[agent_file_alias.FileAlias, str](
            name=tool_provider.ParameterName("blame_target"),
            description=tool_provider.ParameterDescription("Blamed upstream dependency file alias."),
            parameter_type=alias_mgr,
            is_required=False,
            default_value=None,
        )
        self._explanation_parameter = tool_provider.ToolParameter[sandbox_run_control.BlameExplanation, str](
            name=tool_provider.ParameterName("explanation"),
            description=tool_provider.ParameterDescription("Explanation of defect in upstream dependency."),
            parameter_type=_BlameExplanationParamType(),
            is_required=True,
            default_value=None,
        )
        self._parameters: Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]] = {
            self._target_parameter.name: self._target_parameter,
            self._blame_target_parameter.name: self._blame_target_parameter,
            self._explanation_parameter.name: self._explanation_parameter,
        }

    @property
    def name(self) -> tool_provider.ToolName:
        return self._name

    @property
    def description(self) -> tool_provider.ToolDescription:
        return self._description

    @property
    def target_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        return self._target_parameter

    @property
    def blame_target_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        return self._blame_target_parameter

    @property
    def explanation_parameter(self) -> tool_provider.ToolParameter[sandbox_run_control.BlameExplanation, str]:
        return self._explanation_parameter

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        raw_expl = actual_parameter_bindings.get(self.explanation_parameter)
        explanation = str(raw_expl).strip() if raw_expl is not None else ""
        if "\n" in explanation or "\r" in explanation:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    "Error: Explanation must be a single paragraph without newline characters."
                ),
                reminder=tool_provider.ToolReminder(
                    "Format blame explanation as a single paragraph without newlines."
                ),
            )

        coord = get_singleton(control_coordinate.SessionCoordinator)
        raw_target = cast(Optional[agent_file_alias.FileAlias], actual_parameter_bindings.get(self.target_parameter))
        target_alias = str(raw_target.relative_path) if raw_target is not None else None
        active_node = coord.get_node_for_alias(target_alias) if target_alias else coord.resolve_default_target()
        if active_node is None:
            open_list = ", ".join(f"`{coord.get_alias_for_node(n)}`" for n in coord.open_targets)
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: No active node found for blame. Available: {open_list}"
                ),
            )

        node_cfg = get_singleton(agent_node_config.NodeConfig)
        configured_targets = node_cfg.blame_targets_by_node.get(active_node, set())
        configured_aliases = [str(bt.relative_path) for bt in configured_targets]

        raw_blame = cast(Optional[agent_file_alias.FileAlias], actual_parameter_bindings.get(self.blame_target_parameter))
        blame_alias: Optional[str] = None
        if raw_blame is not None:
            blame_alias = str(raw_blame.relative_path)
        else:
            if len(configured_targets) == 1:
                blame_alias = str(list(configured_targets)[0].relative_path)
            elif len(configured_targets) == 0:
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        "Error: Active node has no configured blame targets."
                    ),
                )
            else:
                avail_str = ", ".join(f"`{a}`" for a in configured_aliases)
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        f"Error: Blame target omitted but multiple blame targets exist: {avail_str}"
                    ),
                )

        if configured_aliases and blame_alias not in configured_aliases:
            avail_str = ", ".join(f"`{a}`" for a in configured_aliases)
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: Blame target '{blame_alias}' is not valid for active node. Available: {avail_str}"
                ),
            )

        # Ensure blame target node is registered in coordinator
        matching_bts = [bt for bt in configured_targets if str(bt.relative_path) == blame_alias]
        if matching_bts and hasattr(matching_bts[0], "owning_node"):
            blame_node = matching_bts[0].owning_node
            if coord.get_node_for_alias(blame_alias) is None:
                coord.register_node(blame_node, alias=blame_alias, state=control_coordinate.TargetState.ATTRIBUTED)

        outcome = coord.dispatch_blame(
            source_alias=coord.get_alias_for_node(active_node),
            blame_target_alias=blame_alias,
            explanation=explanation,
        )
        if outcome.success:
            is_term = not bool(coord.open_targets)
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=is_term,
                content=tool_provider.ToolResponseContent(outcome.message),
            )
        else:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(outcome.message),
            )


class GetWorkTool(sandbox_run_control.GetWorkTool, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("get_work")
        self._description = tool_provider.ToolDescription("Retrieves active dirty nodes for processing.")
        self._max_batch_size_parameter = tool_provider.ToolParameter[Optional[dag_config.BatchSize], int](
            name=tool_provider.ParameterName("max_batch_size"),
            description=tool_provider.ParameterDescription("Maximum batch size of dirty nodes to acquire."),
            parameter_type=_BatchSizeParamType(),
            is_required=False,
            default_value=None,
        )
        self._parameters: Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]] = {
            self._max_batch_size_parameter.name: self._max_batch_size_parameter,
        }

    @property
    def name(self) -> tool_provider.ToolName:
        return self._name

    @property
    def description(self) -> tool_provider.ToolDescription:
        return self._description

    @property
    def max_batch_size_parameter(self) -> tool_provider.ToolParameter[Optional[dag_config.BatchSize], int]:
        return self._max_batch_size_parameter

    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        coord = get_singleton(control_coordinate.SessionCoordinator)
        if coord.open_targets:
            open_list = ", ".join(f"`{coord.get_alias_for_node(n)}`" for n in coord.open_targets)
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Open active nodes remain: {open_list}. Please resolve open nodes before getting new work."
                ),
                reminder=tool_provider.ToolReminder("Resolve all open targets before calling get_work."),
            )

        raw_batch = actual_parameter_bindings.get(self.max_batch_size_parameter)
        batch_val = int(cast(Any, raw_batch)) if raw_batch is not None else None
        subgraph = get_singleton(dag_subgraph.DagSubgraph)
        schedule = coord.dispatch_get_work(subgraph=subgraph, max_batch_size=batch_val)

        if not schedule.tasks:
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content=tool_provider.ToolResponseContent("No dirty nodes are ready. Workspace is clean."),
            )

        prompts = [t.task_prompt for t in schedule.tasks if getattr(t, "task_prompt", None)]
        task_prompt = "\n\n".join(prompts) if prompts else "Dirty nodes acquired for processing."

        node_cfg = get_singleton(agent_node_config.NodeConfig)
        guide_deliv = get_singleton(sandbox_guide_delivery.GuideDelivery)

        if node_cfg.is_step_mode:
            advance_prompt = "Call advance to continue."
            prompt_content = task_prompt
            if "call advance" not in prompt_content.lower():
                prompt_content = f"{prompt_content}\n\n{advance_prompt}"
            guide_deliv.record_initial_primer(sandbox_guide_delivery.InitialPrimer(prompt_content))
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(prompt_content),
                reminder=tool_provider.ToolReminder(advance_prompt),
                follow_up_tool_call=tool_provider.FollowUpToolCall(
                    tool_name=tool_provider.ToolName("advance"),
                    wire_parameter_bindings={},
                ),
            )

        guide_deliv.record_initial_primer(sandbox_guide_delivery.InitialPrimer(task_prompt))
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(task_prompt),
        )


class RunController(sandbox_run_control.RunController, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._cached_hashes: Optional[Mapping[agent_file_alias.FileAlias, sandbox_file_editor.FileHash]] = None
        self._is_unchanged: bool = False
        self._passed: bool = True
        self._diagnostic_output: str = ""

    def initialize(self) -> None:
        tool_mgr = get_singleton(tool_provider.ToolManager)
        tool_mgr.install_tool(get_singleton(sandbox_run_control.SubmitTool))
        tool_mgr.install_tool(get_singleton(sandbox_run_control.FailTool))
        tool_mgr.install_tool(get_singleton(sandbox_run_control.CheckFilesTool))
        tool_mgr.install_tool(get_singleton(sandbox_run_control.GetWorkTool))
        tool_mgr.install_tool(get_singleton(sandbox_run_control.BlameTool))
        node_cfg = get_singleton(agent_node_config.NodeConfig)
        if node_cfg.is_step_mode:
            tool_mgr.install_tool(get_singleton(sandbox_run_control.AdvanceTool))

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        return cfg.verification_checks

    def update_verification(self) -> None:
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        node_cfg = get_singleton(agent_node_config.NodeConfig)

        target_files: Set[agent_file_alias.FileAlias] = set(node_cfg.read_write_files)
        if not target_files:
            target_files = set(node_cfg.read_only_files)
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        src_file_alias = getattr(node_cfg, "src_file_alias", None)
        if src_file_alias:
            target_files.add(alias_mgr.convert(str(src_file_alias)))
        if hasattr(node_cfg, "src_file_alias_by_node"):
            for rel in node_cfg.src_file_alias_by_node.values():
                target_files.add(alias_mgr.convert(str(rel)))
        if hasattr(node_cfg, "per_node_info_by_node") and node_cfg.per_node_info_by_node:
            for info in node_cfg.per_node_info_by_node.values():
                if getattr(info, "src_file_alias", None):
                    target_files.add(alias_mgr.convert(str(info.src_file_alias)))
                if getattr(info, "read_write_files", None):
                    target_files.update(info.read_write_files)
        if edit_mgr.last_read_or_edited_file is not None:
            target_files.add(edit_mgr.last_read_or_edited_file)

        current_hashes: dict[agent_file_alias.FileAlias, sandbox_file_editor.FileHash] = {}
        if target_files:
            for f in sorted(target_files, key=lambda x: str(x.relative_path)):
                current_hashes[f] = edit_mgr.file_hash(f)
        else:
            alias_mgr = get_singleton(agent_file_alias.AliasManager)
            default_alias = alias_mgr.convert("")
            current_hashes[default_alias] = edit_mgr.file_hash(default_alias)

        if self._cached_hashes is not None and self._cached_hashes == current_hashes:
            self._is_unchanged = True
            return

        self._is_unchanged = False
        self._cached_hashes = dict(current_hashes)

        all_passed = True
        diag_parts: list[str] = []
        for check in self.verification_checks:
            passed, diag = check.verify()
            if not passed:
                all_passed = False
                if diag:
                    diag_parts.append(str(diag))
                break

        self._passed = all_passed
        self._diagnostic_output = "\n".join(diag_parts).strip()


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        CheckFilesTool,
        keys=[CheckFilesTool, sandbox_run_control.CheckFilesTool, InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        AdvanceTool,
        keys=[AdvanceTool, sandbox_run_control.AdvanceTool, InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        SubmitTool,
        keys=[SubmitTool, sandbox_run_control.SubmitTool, InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        FailTool,
        keys=[FailTool, sandbox_run_control.FailTool, InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        BlameTool,
        keys=[BlameTool, sandbox_run_control.BlameTool, InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        GetWorkTool,
        keys=[GetWorkTool, sandbox_run_control.GetWorkTool, InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        RunController,
        keys=[RunController, sandbox_run_control.RunController, InTier[AgentSessionTier]],
        tier=agent_session,
    )

_initialize_ = __initialize__
