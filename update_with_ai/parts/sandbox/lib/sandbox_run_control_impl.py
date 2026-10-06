# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-06T12:00:00Z
# LAST_CHANGED: 2026-10-06T12:55:00Z
# CHANGE: compact wire conversions and tool calling to ~400 lines
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast
from support.lib.lifecycle import LifecycleRegistry, LifecycleResolutionError, Singleton, get_default_registry, get_singleton
from update_with_ai.parts.agent.lib import agent_file_alias, agent_node_config, agent_session
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.control.lib import (
    control_asm, control_attribution_impl, control_coordinate_impl,
    control_submit_impl, control_verification_impl, control_work_scheduler_impl,
)
from update_with_ai.parts.dag.lib import dag_storage, dag_subgraph
from . import sandbox_file_editor, sandbox_guide_delivery, sandbox_run_control, tool_provider
dag_config = sandbox_run_control.dag_config


def _make_tool_response(
    is_failed: bool, content: str, reminder: Optional[str] = None, is_terminated: bool = False,
    suppression_key: Optional[str] = None, follow_up: Optional[tool_provider.FollowUpToolCall] = None,
) -> tool_provider.ToolResponse:
    return tool_provider.ToolResponse(
        is_failed=is_failed, is_terminated=is_terminated, content=tool_provider.ToolResponseContent(content),
        reminder=tool_provider.ToolReminder(reminder) if reminder is not None else None,
        suppression_key=tool_provider.SuppressionKey(suppression_key) if suppression_key is not None else None,
        follow_up_tool_call=follow_up,
    )


def _follow_up(tool: str, reasoning: str) -> tool_provider.FollowUpToolCall:
    return tool_provider.FollowUpToolCall(tool_name=tool_provider.ToolName(tool), wire_parameter_bindings={}, reasoning_text=tool_provider.ReasoningText(reasoning))


def _finish_target_or_session(
    rc: RunController, action_msg: str, term_msg: str, is_failed: bool = False, suppression_key: Optional[str] = None,
) -> tool_provider.ToolResponse:
    if rc.open_nodes():
        rem = rc.format_open_targets_reminder()
        return _make_tool_response(False, f"{action_msg}\n\n{rem}".strip(), reminder=rem, suppression_key=suppression_key)
    return _make_tool_response(is_failed, term_msg, is_terminated=True, suppression_key=suppression_key)


def _to_target_str(raw: Any) -> str:
    return (getattr(raw, "relative_path", None) or getattr(raw, "short_name", None) or str(raw)).strip() if raw is not None else ""


def _alias_param(name: str, desc: str) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
    return tool_provider.ToolParameter(name=tool_provider.ParameterName(name), description=tool_provider.ParameterDescription(desc), parameter_type=get_singleton(agent_file_alias.AliasManager), is_required=False)


def _string_param(name: str, desc: str, required: bool = True) -> tool_provider.ToolParameter[Any, str]:
    return tool_provider.ToolParameter(name=tool_provider.ParameterName(name), description=tool_provider.ParameterDescription(desc), parameter_type=tool_provider.STRING_PARAMETER_TYPE, is_required=required)


def _int_param(name: str, desc: str, required: bool = False) -> tool_provider.ToolParameter[Any, int]:
    return tool_provider.ToolParameter(name=tool_provider.ParameterName(name), description=tool_provider.ParameterDescription(desc), parameter_type=tool_provider.INTEGER_PARAMETER_TYPE, is_required=required)


def _resolve_target_node(
    rc: RunController, raw_target: Any, suppression_key: Optional[str] = None
) -> Tuple[Optional[dag_storage.DagNode], Optional[tool_provider.ToolResponse]]:
    target_str = _to_target_str(raw_target)
    target_node = rc.resolve_default_target() if not target_str else rc.get_node_for_alias(target_str)
    if target_node is None or (target_str and rc.get_node_state(target_node) != "OPEN"):
        open_t = ", ".join(f"`{rc.get_alias_for_node(n)}`" for n in rc.open_nodes())
        return None, _make_tool_response(True, f"Error: Target '{target_str}' is not an open target." if target_str else "Error: Target parameter must be specified when multiple unsubmitted targets exist.", reminder=f"Specify an open target: {open_t}", suppression_key=suppression_key)
    return target_node, None


def _resolve_blame(
    rc: RunController, raw_target: Any, raw_blame: Any
) -> Tuple[Optional[dag_storage.DagNode], Optional[agent_file_alias.BoundFile], str, str]:
    target_str, blame_str = _to_target_str(raw_target), _to_target_str(raw_blame)
    attrib, open_n = get_singleton(control_attribution_impl.AttributionCoordinator), rc.open_nodes()
    cands, src_node, matched, blamee = open_n or list(rc.nodes), None, None, ""
    for val, s in ((raw_blame, blame_str), (raw_target, target_str)):
        if (val is not None or s) and matched is None:
            matches = [n for n in cands if attrib.match_blame_target(n, val, s)]
            if matches:
                def_t = rc.resolve_default_target()
                src_node = def_t if (def_t is not None and def_t in matches) else matches[0]
                matched, blamee = attrib.match_blame_target(src_node, val, s), s
    if src_node is None:
        cand = rc.get_node_for_alias(target_str) if (raw_target is not None or target_str) else None
        src_node = cand if cand is not None and (rc.get_node_state(cand) == "OPEN" or not open_n) else (open_n[0] if len(open_n) == 1 else (rc.nodes[0] if not open_n and len(rc.nodes) == 1 else rc.resolve_default_target()))
    if src_node is not None and matched is None:
        if raw_blame is not None or blame_str: matched, blamee = attrib.match_blame_target(src_node, raw_blame, blame_str), blame_str
        else:
            targets = rc.get_blame_targets_for_node(src_node)
            matched = next(iter(targets)) if len(targets) == 1 else None
    return src_node, matched, blamee, target_str


def _compute_file_hash(cfg: agent_node_config.NodeConfig, edit_mgr: sandbox_file_editor.EditManager, target: Optional[dag_storage.DagNode] = None) -> str:
    rw = next((f for f in cfg.read_write_files if getattr(f, "owning_node", None) == target), None) if target else None
    if rw: return edit_mgr.file_hash(rw)
    if cfg.read_write_files:
        return ":".join(edit_mgr.file_hash(f) for f in sorted(cfg.read_write_files, key=lambda x: getattr(x, "relative_path", getattr(x, "short_name", ""))))
    return str(edit_mgr.file_update_revision)


def _check_submit_gating(
    target_node: dag_storage.DagNode, summary_str: str, edit_mgr: sandbox_file_editor.EditManager, cfg: agent_node_config.NodeConfig
) -> Optional[tool_provider.ToolResponse]:
    storage = get_singleton(dag_storage.DagStorage)
    msgs = storage.get_messages(target_node) if hasattr(storage, "get_messages") else []
    is_init, has_mod = any(isinstance(m, dag_storage.ChangeMessage) and str(m.content).strip().lower().startswith("implement ") for m in msgs), edit_mgr.has_modifications
    for cond, msg, rem in [
        (is_init and not has_mod, "Error: Initial implementation task requires workspace file modifications before submitting.", "Workspace files must be modified to implement the change before submitting."),
        (bool(cfg.feedback and not has_mod), "Error: Session feedback is present but no workspace files were modified.", "Workspace files must be modified to address feedback or the fail tool must be used."),
        (has_mod and not summary_str, "Error: Workspace files were modified but change_summary was not provided.", "A change summary must be provided when completing the session after modifying workspace files."),
        (control_submit_impl._is_auditor_node(target_node) and bool(summary_str), "Error: Change summary is prohibited for audit nodes.", "Do not provide a change summary when submitting audit nodes."),
        (not has_mod and bool(summary_str), "Error: Workspace files were not modified, but change_summary was provided.", "Omit change_summary when submitting without workspace file modifications."),
    ]:
        if cond: return _make_tool_response(True, msg, reminder=rem, suppression_key="submit")
    return None


def _install_tools() -> None:
    try:
        tm, cfg = get_singleton(tool_provider.ToolManager), get_singleton(agent_node_config.NodeConfig)
        for t in (SubmitTool, FailTool, CheckFilesTool, GetWorkTool, BlameTool): tm.install_tool(get_singleton(t))
        if cfg.is_step_mode: tm.install_tool(get_singleton(AdvanceTool))
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError): pass


class RunController(sandbox_run_control.RunController, Singleton):
    """Facade delegating session lifecycle and verification caching to parts/control."""

    tier = agent_session

    def __init__(self) -> None:
        self._cache: Dict[Optional[dag_storage.DagNode], Tuple[int, str, bool, str]] = {}
        _install_tools()

    @property
    def _coord(self) -> control_coordinate_impl.SessionCoordinator: return get_singleton(control_coordinate_impl.SessionCoordinator)
    @property
    def _nodes(self) -> List[dag_storage.DagNode]: return self._coord._nodes
    @_nodes.setter
    def _nodes(self, val: List[dag_storage.DagNode]) -> None: self._coord._nodes, self._coord._node_states = val, {n: "OPEN" for n in val}
    @property
    def _node_states(self) -> Dict[dag_storage.DagNode, str]: return self._coord._node_states
    @_node_states.setter
    def _node_states(self, val: Dict[dag_storage.DagNode, str]) -> None: self._coord._node_states = val
    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]: return get_singleton(agent_node_config.NodeConfig).verification_checks

    def __getattr__(self, name: str) -> Any:
        try: return getattr(self._coord, name)
        except Exception: raise AttributeError(name)

    def resolve_default_target(self) -> Optional[dag_storage.DagNode]:
        return self._coord.resolve_default_target(last_accessed_file=get_singleton(sandbox_file_editor.EditManager).last_read_or_edited_file)

    def get_blame_targets_for_node(self, node: dag_storage.DagNode) -> Set[agent_file_alias.BoundFile]:
        return (getattr(get_singleton(agent_node_config.NodeConfig), "blame_targets_by_node", None) or {}).get(node, set())

    def format_task_prompt(self, nodes: Sequence[dag_storage.DagNode]) -> str:
        return get_singleton(control_work_scheduler_impl.WorkScheduler).format_task_prompt(nodes)

    def check_in_batch_dependencies(self, node: dag_storage.DagNode, suppression_key: Optional[str] = None) -> Optional[tool_provider.ToolResponse]:
        for dep in self.get_in_batch_dependencies(node):
            if not self.is_clean_in_turn(dep):
                return _make_tool_response(True, f"Error: In-batch dependency `{self.get_alias_for_node(dep)}` must be submitted before `{self.get_alias_for_node(node)}`.", reminder=f"In-batch dependencies must be submitted before dependent targets. Submit `{self.get_alias_for_node(dep)}` first.", suppression_key=suppression_key)
        return None

    def reset_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        self._cache.clear()
        self._coord.reset_nodes(nodes)
        _install_tools()

    def evaluate_verification(self, target: Optional[dag_storage.DagNode] = None) -> Tuple[bool, str]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        by_node = getattr(cfg, "verification_checks_by_node", None)
        if target is not None and (not by_node or target not in by_node): return self.evaluate_verification(target=None)
        checks = (by_node.get(target) if target and by_node and target in by_node else cfg.verification_checks) or []
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        rev, h = edit_mgr.file_update_revision, _compute_file_hash(cfg, edit_mgr, target)
        cached = self._cache.get(target)
        if cached and cached[0] == rev and (not cached[1] or cached[1] == h): return cached[2], cached[3]
        alias_mgr, passed, diag_out = get_singleton(agent_file_alias.AliasManager), True, ""
        if target:
            for dep in sorted(self.get_in_batch_dependencies(target), key=self.get_alias_for_node):
                if self.get_node_state(dep) == "OPEN":
                    dep_passed, dep_diag = self.evaluate_verification(dep)
                    if not dep_passed:
                        passed, prefix = False, f"In-batch dependency `{self.get_alias_for_node(dep)}` verification failed:\n{dep_diag}"
                        diag_out = f"{prefix}\n\n{diag_out}" if diag_out else prefix
        for chk in checks:
            chk_passed, chk_diag = chk.verify()
            s = alias_mgr.sanitize_text(agent_file_alias.UnsanitizedText(chk_diag)) if chk_diag else ""
            if s: diag_out = f"{diag_out}\n\n{s}".strip() if diag_out else s
            if not chk_passed:
                passed = False; break
        self._cache[target] = (rev, h, passed, diag_out)
        return passed, diag_out

    evaluate_verification_for_node = evaluate_verification

    def evaluate_all_open_targets(self) -> Tuple[bool, str]:
        open_n = self.open_nodes()
        if not open_n: return self.evaluate_verification()
        results = [self.evaluate_verification(n) for n in open_n]
        passed, diag = all(p for p, _ in results), "\n".join(d for _, d in results if d).strip()
        self._cache[None] = (get_singleton(sandbox_file_editor.EditManager).file_update_revision, _compute_file_hash(get_singleton(agent_node_config.NodeConfig), get_singleton(sandbox_file_editor.EditManager), None), passed, diag)
        return passed, diag

    def update_verification(self) -> None: self.evaluate_verification()

    def is_verification_up_to_date_and_passing(self) -> Tuple[bool, bool]:
        cached = self._cache.get(None)
        if not cached: return False, False
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        cfg = get_singleton(agent_node_config.NodeConfig)
        if cached[0] != edit_mgr.file_update_revision or (cfg.read_write_files and cached[1] and _compute_file_hash(cfg, edit_mgr, None) != cached[1]):
            return False, False
        return True, cached[2]


class CheckFilesTool(sandbox_run_control.CheckFilesTool, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._last_tested_revision: Optional[int] = None
        self._last_tested_hashes: Dict[Any, str] = {}

    @property
    def name(self) -> tool_provider.ToolName: return tool_provider.ToolName("check_files")
    @property
    def description(self) -> tool_provider.ToolDescription:
        return tool_provider.ToolDescription("Checks static type correctness, syntax, and verification checks for all open targets and modified workspace files. Call check_files to verify syntax and type correctness after completing edits.")
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]: return {}

    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        rc, guide_del = get_singleton(RunController), get_singleton(sandbox_guide_delivery.GuideDelivery)
        edit_mgr, cfg = get_singleton(sandbox_file_editor.EditManager), get_singleton(agent_node_config.NodeConfig)
        passed, diag = rc.evaluate_all_open_targets()
        current_rev, current_hash = edit_mgr.file_update_revision, _compute_file_hash(cfg, edit_mgr, None)

        is_repeated = self._last_tested_hashes.get("all_files") == current_hash and self._last_tested_revision == current_rev
        self._last_tested_hashes["all_files"], self._last_tested_revision = current_hash, current_rev
        reminder = f"Verification {'passes' if passed else 'failed'}, no new information will be revealed by this tool call until session read-write files are updated." if is_repeated else None
        clean_diag = control_verification_impl.VerificationEvaluator().clean_diagnostic_noise(diag) or diag

        if not passed:
            guide_obj = getattr(guide_del, "guide", None)
            vf = f"\n\n## Verification failure\n{guide_obj.verification_failure}" if (guide_obj and getattr(guide_obj, "verification_failure", None)) else ""
            return _make_tool_response(True, f"Verification failed: {clean_diag}{vf}".strip(), reminder=reminder, suppression_key="check_files")

        base_msg = cfg.verification_success_message or "Verification passed: All checks succeeded."
        return _make_tool_response(False, f"{base_msg}\n\n{clean_diag}".strip() if clean_diag else base_msg, reminder=reminder, suppression_key="check_files")


class AdvanceTool(sandbox_run_control.AdvanceTool, Singleton):
    tier = agent_session

    @property
    def name(self) -> tool_provider.ToolName: return tool_provider.ToolName("advance")
    @property
    def description(self) -> tool_provider.ToolDescription: return tool_provider.ToolDescription("Advances guide steps or completes the session.")
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]: return {}

    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        guide_del, rc = get_singleton(sandbox_guide_delivery.GuideDelivery), get_singleton(RunController)
        is_up_to_date, is_passing = rc.is_verification_up_to_date_and_passing()
        if not is_up_to_date or not is_passing:
            passed, diag = rc.evaluate_verification()
            step_resp = guide_del.advance_step(verification_passed=False, failure_diagnostics=agent_node_config.VerificationDiagnostic(diag))
            return _make_tool_response(True, step_resp.content if step_resp is not None else "Verification is failing. The check files tool should be called first.", reminder="The check files tool should be called first to inspect verification results.", suppression_key="advance", follow_up=_follow_up("check_files", "Verification results must be inspected before advancing."))

        if guide_del.has_steps_remaining:
            next_step = guide_del.advance_step(verification_passed=True, failure_diagnostics=agent_node_config.VerificationDiagnostic(""))
            if next_step is not None: return next_step

        if get_singleton(sandbox_file_editor.EditManager).has_modifications:
            return _make_tool_response(True, "All guide steps have been completed, but workspace files were modified.", reminder="Call the submit tool with a change summary describing modifications.", suppression_key="advance")

        return _make_tool_response(False, "All guide steps have been completed.", suppression_key="advance", follow_up=_follow_up("submit", "All guide steps are complete."))


class _ResolveTool:
    @property
    def target_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        return _alias_param("target", "Target being resolved: source file alias (if any), unit_name (if unique among session units), or relative_path/unit_name (if ambiguous). May be omitted when only one unit is being processed.")
    target = target_parameter
    resolve_target = target_parameter
    resolve_target_parameter = target_parameter


class SubmitTool(_ResolveTool, sandbox_run_control.SubmitTool, Singleton):
    tier = agent_session

    @property
    def name(self) -> tool_provider.ToolName: return tool_provider.ToolName("submit")
    @property
    def description(self) -> tool_provider.ToolDescription: return tool_provider.ToolDescription("Submits a completed target file and enforces change documentation.")
    @property
    def change_summary_parameter(self) -> tool_provider.ToolParameter[Optional[sandbox_run_control.ChangeSummary], str]:
        return cast(Any, _string_param("change_summary", "Summary of modifications made during the task", required=False))
    change_summary = change_summary_parameter
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return {self.target.name: self.target, self.change_summary.name: self.change_summary}

    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        summary_str = str(actual_parameter_bindings.get(self.change_summary) or "").strip()
        guide_del, cfg = get_singleton(sandbox_guide_delivery.GuideDelivery), get_singleton(agent_node_config.NodeConfig)
        edit_mgr, rc = get_singleton(sandbox_file_editor.EditManager), get_singleton(RunController)
        rc.evaluate_verification()

        if cfg.is_step_mode and guide_del.has_steps_remaining:
            return _make_tool_response(True, "Error: Cannot finish while guide steps remain.", reminder="The advance tool must be called while guide steps remain.", suppression_key="submit", follow_up=_follow_up("advance", "Remaining guide steps must be completed before finishing."))

        target_node, err_resp = _resolve_target_node(rc, actual_parameter_bindings.get(self.target) or actual_parameter_bindings.get(self.resolve_target), suppression_key="submit")
        if err_resp or not target_node: return err_resp or _make_tool_response(True, "Target resolution error")
        dep_resp = rc.check_in_batch_dependencies(target_node, suppression_key="submit")
        if dep_resp: return dep_resp
        target_alias = rc.get_alias_for_node(target_node)

        passed, _ = rc.evaluate_verification_for_node(target_node)
        if not passed:
            return _make_tool_response(True, "Verification is failing. The check files tool should be called first.", reminder="The check files tool should be called first to inspect verification results.", suppression_key="submit", follow_up=_follow_up("check_files", "Verification results must be inspected before submitting."))

        gating_err = _check_submit_gating(target_node, summary_str, edit_mgr, cfg)
        if gating_err is not None: return gating_err

        is_auditor = control_submit_impl._is_auditor_node(target_node)
        get_singleton(dag_storage.DagStorage).mark_node_clean(target_node, dag_storage.ChangeDescription(summary_str) if (summary_str and not is_auditor) else None)
        rc.set_node_state(target_node, "SUBMITTED")
        rc.mark_clean_in_turn(target_node)
        return _finish_target_or_session(rc, f"Target `{target_alias}` submitted successfully.", f"Session completed successfully: {summary_str}".strip() if summary_str else "Session completed successfully.", suppression_key="submit")


class FailTool(_ResolveTool, sandbox_run_control.FailTool, Singleton):
    tier = agent_session

    @property
    def name(self) -> tool_provider.ToolName: return tool_provider.ToolName("fail")
    @property
    def description(self) -> tool_provider.ToolDescription: return tool_provider.ToolDescription("Terminates the run or marks a target in failure.")
    @property
    def explanation_parameter(self) -> tool_provider.ToolParameter[sandbox_run_control.FailureExplanation, str]:
        return cast(Any, _string_param("explanation", "Explanation of why the run failed", required=True))
    explanation = explanation_parameter
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return {self.target.name: self.target, self.explanation.name: self.explanation}

    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        exp = str(actual_parameter_bindings.get(self.explanation) or "Failed")
        rc = get_singleton(RunController)
        target_node, err_resp = _resolve_target_node(rc, actual_parameter_bindings.get(self.target) or actual_parameter_bindings.get(self.resolve_target))
        if err_resp or not target_node: return err_resp or _make_tool_response(True, "Target resolution error")
        dep_resp = rc.check_in_batch_dependencies(target_node)
        if dep_resp: return dep_resp
        target_alias = rc.get_alias_for_node(target_node)
        rc.set_node_state(target_node, "FAILED")
        rc.fail_dependents(target_node)
        return _finish_target_or_session(rc, f"Target `{target_alias}` failed: {exp}", f"Failed: {exp}", is_failed=True)


class BlameTool(_ResolveTool, sandbox_run_control.BlameTool, Singleton):
    tier = agent_session

    @property
    def name(self) -> tool_provider.ToolName: return tool_provider.ToolName("blame")
    @property
    def description(self) -> tool_provider.ToolDescription: return tool_provider.ToolDescription("Attributes failure to a dependency node via a blame target.")
    @property
    def blame_target_parameter(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, str]:
        return _alias_param("blame_target", "Target bound file to blame")
    blame_target = blame_target_parameter
    @property
    def explanation_parameter(self) -> tool_provider.ToolParameter[sandbox_run_control.BlameExplanation, str]:
        return cast(Any, _string_param("explanation", "Explanation of the defect", required=True))
    explanation = explanation_parameter
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return {self.target.name: self.target, self.blame_target.name: self.blame_target, self.explanation.name: self.explanation}

    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        raw_target = actual_parameter_bindings.get(self.target) or actual_parameter_bindings.get(self.resolve_target)
        raw_blame, exp = actual_parameter_bindings.get(self.blame_target), str(actual_parameter_bindings.get(self.explanation) or "")
        rc = get_singleton(RunController)
        src_node, matched, blamee, target_str = _resolve_blame(rc, raw_target, raw_blame)

        if src_node is None:
            open_t = ", ".join(f"`{rc.get_alias_for_node(n)}`" for n in rc.open_nodes())
            return _make_tool_response(True, "Error: No open target found for blame.", reminder=f"Specify an open target: {open_t}")
        if matched is None:
            avail = ", ".join(getattr(t, "relative_path", getattr(t, "short_name", "")) for t in rc.get_blame_targets_for_node(src_node))
            return _make_tool_response(True, f"Error: Target '{blamee or target_str}' is not a valid blame target. Available: {avail}", reminder="Only upstream files configured as blame targets can be blamed.")
        if "\n" in exp or "\r" in exp:
            return _make_tool_response(True, "Error: Blame explanation must be a single paragraph without newlines.", reminder="Provide the blame explanation as a single continuous paragraph without line breaks or bulleted lists.")

        dep_resp = rc.check_in_batch_dependencies(src_node)
        if dep_resp: return dep_resp

        storage, blamed_node = get_singleton(dag_storage.DagStorage), getattr(matched, "owning_node", None)
        if blamed_node is not None:
            storage.add_message(dag_storage.FeedbackMessage(content=dag_storage.MessageContent(exp), target=blamed_node), to=blamed_node)

        target_name = getattr(matched, "relative_path", getattr(matched, "short_name", ""))
        rc.set_node_state(src_node, "BLAME")
        rc.fail_dependents(src_node)
        return _finish_target_or_session(rc, f"Target `{rc.get_alias_for_node(src_node)}` blamed `{target_name}`: {exp}", f"Blamed {target_name}: {exp}")


class GetWorkTool(sandbox_run_control.GetWorkTool, Singleton):
    tier = agent_session

    @property
    def name(self) -> tool_provider.ToolName: return tool_provider.ToolName("get_work")
    @property
    def description(self) -> tool_provider.ToolDescription:
        return tool_provider.ToolDescription("Retrieves active dirty targets, materializes startup templates, and returns the session task prompt.")
    @property
    def max_batch_size_parameter(self) -> tool_provider.ToolParameter[Optional[dag_config.BatchSize], int]:
        return cast(Any, _int_param("max_batch_size", "Maximum number of dirty nodes to process together."))
    max_batch_size = max_batch_size_parameter
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return {self.max_batch_size_parameter.name: self.max_batch_size_parameter}

    def execute_tool(
        self, actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        rc = get_singleton(RunController)
        open_nodes = [n for n in rc.open_nodes() if n.unit_address != "//session:target"]
        if open_nodes:
            open_t = ", ".join(f"`{rc.get_alias_for_node(n)}`" for n in open_nodes)
            return _make_tool_response(True, f"Error: Open session targets remain: {open_t}.", reminder=f"Open session targets must be resolved before requesting new work: {open_t}.")

        subgraph, role_cfg = get_singleton(dag_subgraph.DagSubgraph), get_singleton(agent_node_config.RoleConfig)
        batch = list(subgraph.next_ready_batch())
        if role_cfg.role and any(n.role_address != role_cfg.role for n in batch): batch = []

        raw_max = actual_parameter_bindings.get(self.max_batch_size_parameter)
        if raw_max is not None:
            try:
                max_b = int(cast(Any, raw_max))
                if max_b > 0: batch = batch[:max_b]
            except (ValueError, TypeError): pass

        if not batch: return _make_tool_response(False, "No dirty nodes are ready for cleaning.", reminder="No dirty nodes are ready for cleaning.")

        role_cfg.set_nodes(batch)
        rc.reset_nodes(batch)
        for obj in (get_singleton(agent_file_alias.AliasManager), get_singleton(sandbox_guide_delivery.GuideDelivery)):
            try:
                if callable(getattr(obj, "initialize", None)): getattr(obj, "initialize")()
            except Exception: pass

        storage = get_singleton(dag_storage.DagStorage)
        for n in batch: storage.materialize_template(n)

        prompt = rc.format_task_prompt(batch)
        if get_singleton(agent_node_config.NodeConfig).is_step_mode:
            get_singleton(sandbox_guide_delivery.GuideDelivery).record_initial_primer(sandbox_guide_delivery.InitialPrimer(prompt))

        return _make_tool_response(False, prompt)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    control_asm.__initialize__(reg)
    for cls, keys in [
        (RunController, [RunController, sandbox_run_control.RunController]),
        (CheckFilesTool, [CheckFilesTool, sandbox_run_control.CheckFilesTool, tool_provider.Tool]),
        (AdvanceTool, [AdvanceTool, sandbox_run_control.AdvanceTool, tool_provider.Tool]),
        (SubmitTool, [SubmitTool, sandbox_run_control.SubmitTool, sandbox_run_control.ResolveTool, tool_provider.Tool]),
        (FailTool, [FailTool, sandbox_run_control.FailTool, sandbox_run_control.ResolveTool, tool_provider.Tool]),
        (BlameTool, [BlameTool, sandbox_run_control.BlameTool, sandbox_run_control.ResolveTool, tool_provider.Tool]),
        (GetWorkTool, [GetWorkTool, sandbox_run_control.GetWorkTool, tool_provider.Tool]),
    ]:
        reg.register_singleton(cls, keys=keys, tier=agent_session)
