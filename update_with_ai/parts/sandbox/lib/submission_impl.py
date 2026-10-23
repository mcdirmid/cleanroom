"""Low-level implementation for submission."""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence, Set, cast

from support.lib.lifecycle import (

    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import file_alias, node_config
from update_with_ai.parts.agent.lib.session import AgentSessionTier, agent_session
from update_with_ai.parts.control.lib import coordinate
from update_with_ai.parts.metadata.lib import src_metadata
from . import (
    guide_delivery,
    run_control,
    submission,
    tool_provider,
)


@dataclass(frozen=True)
class _ChangeSummaryParamType(
    tool_provider.ParameterType[Optional[submission.ChangeSummary], str]
):
    @property
    def actual_type(self) -> type[Optional[submission.ChangeSummary]]:
        return cast(
            type[Optional[submission.ChangeSummary]],
            submission.ChangeSummary,
        )

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> Optional[submission.ChangeSummary]:
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
        return submission.ChangeSummary(stripped)


@dataclass(frozen=True)
class _FailureExplanationParamType(
    tool_provider.ParameterType[submission.FailureExplanation, str]
):
    @property
    def actual_type(self) -> type[submission.FailureExplanation]:
        return cast(
            type[submission.FailureExplanation],
            submission.FailureExplanation,
        )

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> submission.FailureExplanation:
        if not isinstance(wire_value, str):
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(
                    f"Expected str for explanation, got {type(wire_value).__name__}"
                )
            )
        return submission.FailureExplanation(wire_value)


@dataclass(frozen=True)
class _BlameExplanationParamType(
    tool_provider.ParameterType[submission.BlameExplanation, str]
):
    @property
    def actual_type(self) -> type[submission.BlameExplanation]:
        return cast(
            type[submission.BlameExplanation],
            submission.BlameExplanation,
        )

    @property
    def wire_type(self) -> type[str]:
        return str

    def convert(self, wire_value: str) -> submission.BlameExplanation:
        if not isinstance(wire_value, str):
            raise tool_provider.ParameterConversionError(
                message=tool_provider.ConversionErrorMessage(
                    f"Expected str for explanation, got {type(wire_value).__name__}"
                )
            )
        return submission.BlameExplanation(wire_value)


class SubmitTool(submission.SubmitTool):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("submit")
        self._description = tool_provider.ToolDescription(
            "Marks an active node complete upon passing verification."
        )
        alias_type = get_singleton(tool_provider.AliasManagerType)
        self._target_parameter = tool_provider.ToolParameter[
            file_alias.FileAlias, str
        ](
            name=tool_provider.ParameterName("target"),
            description=tool_provider.ParameterDescription(
                "Target file alias to submit."
            ),
            parameter_type=alias_type,
            is_required=False,
            default_value=None,
        )
        self._change_summary_parameter = tool_provider.ToolParameter[
            Optional[submission.ChangeSummary], str
        ](
            name=tool_provider.ParameterName("change_summary"),
            description=tool_provider.ParameterDescription(
                "Description of changes made during the task."
            ),
            parameter_type=_ChangeSummaryParamType(),
            is_required=False,
            default_value=None,
        )
        self._parameters: Mapping[
            tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]
        ] = {
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
    def target_parameter(
        self,
    ) -> tool_provider.ToolParameter[file_alias.FileAlias, str]:
        return self._target_parameter

    # Contract: SubmitTool.change_summary_parameter - parameter describing modifications made during the task.
    @property
    def change_summary_parameter(
        self,
    ) -> tool_provider.ToolParameter[Optional[submission.ChangeSummary], str]:
        return self._change_summary_parameter

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    # Contract: SubmitTool.execute_tool - validates verification status and guide milestones, then dispatches target submission.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        node_cfg = get_singleton(node_config.NodeConfig)
        guide_deliv = get_singleton(guide_delivery.GuideDelivery)
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
                    reasoning_text=tool_provider.ReasoningText(
                        "Guide steps remain, so I must advance through the remaining steps before submitting."
                    ),
                ),
            )

        run_ctrl = get_singleton(run_control.RunController)
        run_ctrl.update_verification()
        if not run_ctrl.is_passed:
            raw_diag = run_ctrl.diagnostic_output
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Verification is failing. Please fix errors before submitting.\n{raw_diag}"
                ),
                reminder=tool_provider.ToolReminder(
                    "Call check_files to view verification diagnostics."
                ),
                follow_up_tool_call=tool_provider.FollowUpToolCall(
                    tool_name=tool_provider.ToolName("check_files"),
                    wire_parameter_bindings={},
                    reasoning_text=tool_provider.ReasoningText(
                        "Verification is failing, so I must call check_files to view the diagnostics before submitting."
                    ),
                ),
            )

        raw_target = cast(
            Optional[file_alias.FileAlias],
            actual_parameter_bindings.get(self.target_parameter),
        )
        target_alias = (
            str(raw_target.relative_path) if raw_target is not None else None
        )
        meta_mgr = get_singleton(src_metadata.SourceMetadataCoordinator)
        alias_mgr = get_singleton(file_alias.AliasManager)
        ws_root = ""
        if hasattr(alias_mgr, "workspace_root") and hasattr(alias_mgr.workspace_root, "path"):
            ws_root = str(alias_mgr.workspace_root.path)
        node_cfg = get_singleton(node_config.NodeConfig)

        has_mods = False
        target_to_check = target_alias
        if not target_to_check:
            coord = get_singleton(coordinate.SessionCoordinator)
            def_node = coord.resolve_default_target()
            if def_node is not None:
                target_to_check = coord.get_alias_for_node(def_node)

        # File alias suffix matching and probing has_modifications attribute on SourceMetadataCoordinator.
        if target_to_check:
            matched = False
            for rw_file in (node_cfg.read_write_files or ()):
                rel = str(rw_file.relative_path)
                ws_path = str(rw_file.workspace_path.path)
                if (
                    target_to_check in (rel, ws_path)
                    or target_to_check.endswith("/" + rel)
                    or target_to_check.endswith("/" + ws_path)
                ):
                    disk_path = str(Path(ws_root) / ws_path) if ws_root else ws_path
                    meta_mgr_any: Any = meta_mgr
                    if bool(meta_mgr_any.has_modifications if hasattr(meta_mgr_any, "has_modifications") else False):
                        has_mods = True
                    else:
                        try:
                            has_mods = meta_mgr.is_code_modified(disk_path)
                        except Exception:
                            has_mods = False
                    matched = True
                    break
            if not matched:
                cand = (
                    target_to_check
                    if os.path.isabs(target_to_check)
                    else (str(Path(ws_root) / target_to_check) if ws_root else target_to_check)
                )
                meta_mgr_any = meta_mgr
                if bool(meta_mgr_any.has_modifications if hasattr(meta_mgr_any, "has_modifications") else False):
                    has_mods = True
                else:
                    try:
                        has_mods = meta_mgr.is_code_modified(cand)
                    except Exception:
                        has_mods = False
        else:
            for rw_file in (node_cfg.read_write_files or ()):
                ws_path = str(rw_file.workspace_path.path)
                disk_path = str(Path(ws_root) / ws_path) if ws_root else ws_path
                meta_mgr_any = meta_mgr
                if bool(meta_mgr_any.has_modifications if hasattr(meta_mgr_any, "has_modifications") else False):
                    has_mods = True
                    break
                try:
                    if meta_mgr.is_code_modified(disk_path):
                        has_mods = True
                        break
                except Exception:
                    pass
            meta_mgr_any = meta_mgr
            if not has_mods and bool(meta_mgr_any.has_modifications if hasattr(meta_mgr_any, "has_modifications") else False):
                has_mods = True
        raw_summary = actual_parameter_bindings.get(self.change_summary_parameter)
        change_summary_str = (
            str(raw_summary).strip()
            if (raw_summary is not None and str(raw_summary).strip())
            else None
        )

        coord = get_singleton(coordinate.SessionCoordinator)
        outcome = coord.dispatch_submit(
            target_alias=target_alias,
            change_summary=change_summary_str,
            has_modifications=has_mods,
        )

        if not outcome.success:
            msg_lower = outcome.message.lower()
            reminder = None
            if "session feedback is present" in msg_lower or "address feedback" in msg_lower:
                reminder = tool_provider.ToolReminder(
                    "You must modify workspace files to address feedback before submitting, or call fail if the feedback cannot be resolved."
                )
            elif "prohibited" in msg_lower or "audit" in msg_lower:
                reminder = tool_provider.ToolReminder(
                    "Change summary is prohibited for audit nodes. Call submit without change_summary."
                )
            elif "not permitted" in msg_lower or "without" in msg_lower:
                reminder = tool_provider.ToolReminder(
                    "Change summaries are not permitted when submitting without workspace file modifications."
                )
            elif (
                "change_summary" in msg_lower
                or "change summaries" in msg_lower
                or "modified" in msg_lower
            ):
                reminder = tool_provider.ToolReminder(
                    "Please provide a change_summary describing your modifications."
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


class FailTool(submission.FailTool):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("fail")
        self._description = tool_provider.ToolDescription(
            "Fails the active node and terminates session execution."
        )
        alias_type = get_singleton(tool_provider.AliasManagerType)
        self._target_parameter = tool_provider.ToolParameter[
            file_alias.FileAlias, str
        ](
            name=tool_provider.ParameterName("target"),
            description=tool_provider.ParameterDescription(
                "Target file alias to fail."
            ),
            parameter_type=alias_type,
            is_required=False,
            default_value=None,
        )
        self._explanation_parameter = tool_provider.ToolParameter[
            submission.FailureExplanation, str
        ](
            name=tool_provider.ParameterName("explanation"),
            description=tool_provider.ParameterDescription(
                "Explanation of failure reason."
            ),
            parameter_type=_FailureExplanationParamType(),
            is_required=True,
            default_value=None,
        )
        self._parameters: Mapping[
            tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]
        ] = {
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
    def target_parameter(
        self,
    ) -> tool_provider.ToolParameter[file_alias.FileAlias, str]:
        return self._target_parameter

    # Contract: FailTool.explanation_parameter - parameter explaining reason for failure.
    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[submission.FailureExplanation, str]:
        return self._explanation_parameter

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    # Contract: FailTool.execute_tool - marks active node as failed and terminates run in failure.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
    ) -> tool_provider.ToolResponse:
        raw_target = cast(
            Optional[file_alias.FileAlias],
            actual_parameter_bindings.get(self.target_parameter),
        )
        target_alias = (
            str(raw_target.relative_path) if raw_target is not None else None
        )
        raw_expl = actual_parameter_bindings.get(self.explanation_parameter)
        explanation = str(raw_expl) if raw_expl is not None else ""

        coord = get_singleton(coordinate.SessionCoordinator)
        outcome = coord.dispatch_fail(
            target_alias=target_alias, explanation=explanation
        )
        return tool_provider.ToolResponse(
            is_failed=True,
            is_terminated=True,
            content=tool_provider.ToolResponseContent(outcome.message),
        )


def _match_blame_target(
    cand: str, targets: Iterable[file_alias.BoundFile]
) -> Optional[file_alias.BoundFile]:
    """Matches a candidate blame target string against configured bound files."""
    norm_cand = cand.strip().lstrip("/")
    # 1. Exact match on relative_path
    for bt in targets:
        if str(bt.relative_path).strip().lstrip("/") == norm_cand:
            return bt
    # 2. Suffix match
    for bt in targets:
        bt_norm = str(bt.relative_path).strip().lstrip("/")
        if norm_cand.endswith("/" + bt_norm) or bt_norm.endswith("/" + norm_cand):
            return bt
    # 3. Basename match
    cand_base = os.path.basename(norm_cand)
    for bt in targets:
        if os.path.basename(str(bt.relative_path)) == cand_base:
            return bt
    return None


class BlameTool(submission.BlameTool):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("blame")
        self._description = tool_provider.ToolDescription(
            "Attributes failure to an upstream dependency node."
        )
        alias_type = get_singleton(tool_provider.AliasManagerType)
        self._target_parameter = tool_provider.ToolParameter[
            file_alias.FileAlias, str
        ](
            name=tool_provider.ParameterName("target"),
            description=tool_provider.ParameterDescription(
                "Active node file alias attributing blame."
            ),
            parameter_type=alias_type,
            is_required=False,
            default_value=None,
        )
        self._blame_target_parameter = tool_provider.ToolParameter[
            file_alias.FileAlias, str
        ](
            name=tool_provider.ParameterName("blame_target"),
            description=tool_provider.ParameterDescription(
                "Blamed upstream dependency file alias."
            ),
            parameter_type=alias_type,
            is_required=False,
            default_value=None,
        )
        self._explanation_parameter = tool_provider.ToolParameter[
            submission.BlameExplanation, str
        ](
            name=tool_provider.ParameterName("explanation"),
            description=tool_provider.ParameterDescription(
                "Explanation of defect in upstream dependency."
            ),
            parameter_type=_BlameExplanationParamType(),
            is_required=True,
            default_value=None,
        )
        self._parameters: Mapping[
            tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]
        ] = {
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
    def target_parameter(
        self,
    ) -> tool_provider.ToolParameter[file_alias.FileAlias, str]:
        return self._target_parameter

    # Contract: BlameTool.blame_target_parameter - parameter identifying blamed upstream dependency.
    @property
    def blame_target_parameter(
        self,
    ) -> tool_provider.ToolParameter[file_alias.FileAlias, str]:
        return self._blame_target_parameter

    # Contract: BlameTool.explanation_parameter - parameter explaining defect in upstream dependency.
    @property
    def explanation_parameter(
        self,
    ) -> tool_provider.ToolParameter[submission.BlameExplanation, str]:
        return self._explanation_parameter

    @property
    def parameters(
        self,
    ) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    # Contract: BlameTool.execute_tool - validates single paragraph explanation, resolves blame target, records defect feedback, and attributes failure.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[
            tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType
        ],
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

        coord = get_singleton(coordinate.SessionCoordinator)
        run_ctrl = get_singleton(run_control.RunController)

        raw_target_any: Any = actual_parameter_bindings.get(self.target_parameter)
        target_alias = (
            str(raw_target_any.relative_path if hasattr(raw_target_any, "relative_path") else raw_target_any)
            if raw_target_any is not None
            else None
        )
        raw_blame_any: Any = actual_parameter_bindings.get(self.blame_target_parameter)
        blame_alias = (
            str(raw_blame_any.relative_path if hasattr(raw_blame_any, "relative_path") else raw_blame_any)
            if raw_blame_any is not None
            else None
        )

        active_node = None
        open_nodes = list(coord.open_targets)

        # 1. If blame_alias is provided, identify active node owning that blame target
        if blame_alias:
            for n in open_nodes:
                if _match_blame_target(
                    blame_alias, run_ctrl.blame_targets_by_node.get(n, set())
                ):
                    active_node = n
                    break

        # 2. If blame_alias is omitted or mirrors target_alias, check if target_alias matches a configured blame target
        if (blame_alias is None or blame_alias == target_alias) and target_alias:
            for n in open_nodes:
                if _match_blame_target(
                    target_alias, run_ctrl.blame_targets_by_node.get(n, set())
                ):
                    active_node = n
                    blame_alias = target_alias
                    target_alias = None
                    break

        # 3. Fall back to standard target resolution if active_node not yet resolved
        if active_node is None:
            if target_alias:
                active_node = coord.get_node_for_alias(target_alias)
            else:
                active_node = coord.resolve_default_target()

        if active_node is None and len(open_nodes) == 1:
            active_node = open_nodes[0]

        if active_node is None:
            open_list = ", ".join(
                f"`{coord.get_alias_for_node(n)}`" for n in open_nodes
            )
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: No active node found for blame. Available: {open_list}"
                ),
            )

        configured_targets: Set[file_alias.BoundFile] = (
            run_ctrl.blame_targets_by_node.get(active_node, set())
        )
        configured_aliases = [str(bt.relative_path) for bt in configured_targets]

        if blame_alias is None:
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

        matched_bt = _match_blame_target(blame_alias, configured_targets)
        if matched_bt is None:
            avail_str = (
                ", ".join(f"`{a}`" for a in configured_aliases)
                if configured_aliases
                else "none"
            )
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: Blame target '{blame_alias}' is not valid for active node. Available: {avail_str}"
                ),
            )

        canon_alias = str(matched_bt.relative_path)
        coord.register_node(
            matched_bt.owning_node,
            alias=canon_alias,
            state=coordinate.TargetState.ATTRIBUTED,
        )
        if blame_alias != canon_alias:
            coord.register_node(
                matched_bt.owning_node,
                alias=blame_alias,
                state=coordinate.TargetState.ATTRIBUTED,
            )

        outcome = coord.dispatch_blame(
            source_alias=coord.get_alias_for_node(active_node),
            blame_target_alias=canon_alias,
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T18:30:00Z
# CHANGE: Define submission_impl realization
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        SubmitTool,
        keys=[SubmitTool, submission.SubmitTool, run_control.SubmitTool],
        tier=agent_session,
    )
    reg.register_singleton(
        FailTool,
        keys=[FailTool, submission.FailTool, run_control.FailTool],
        tier=agent_session,
    )
    reg.register_singleton(
        BlameTool,
        keys=[BlameTool, submission.BlameTool, run_control.BlameTool],
        tier=agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
