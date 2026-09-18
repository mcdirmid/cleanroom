from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.agent.lib import agent_node_config
from update_with_ai.parts.dag.lib import dag_storage
from . import sandbox_file_editor
from . import sandbox_guide_delivery
from . import sandbox_run_control
from . import template_format
from . import tool_provider
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)


class RunController(sandbox_run_control.RunController, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._cached_passed: Optional[bool] = None
        self._cached_diag: str = ""
        self._cached_revision: Optional[int] = None
        self._cached_node_passed: Dict[dag_storage.Node, bool] = {}
        self._cached_node_diag: Dict[dag_storage.Node, str] = {}
        self._cached_node_revision: Dict[dag_storage.Node, int] = {}
        self._nodes: List[dag_storage.Node] = []
        self._alias_to_node: Dict[str, dag_storage.Node] = {}
        self._node_to_alias: Dict[dag_storage.Node, str] = {}
        self._node_states: Dict[dag_storage.Node, str] = {}
        self._initialized_nodes = False

    def _ensure_nodes(self) -> None:
        if self._initialized_nodes:
            return
        self._initialized_nodes = True
        cfg = get_singleton(agent_node_config.NodeConfig)
        if cfg.src_file_alias_by_node:
            for node, alias in cfg.src_file_alias_by_node.items():
                self._nodes.append(node)
                self._alias_to_node[alias] = node
                self._node_to_alias[node] = alias
                self._node_states[node] = "OPEN"
        elif cfg.read_write_files:
            for f in sorted(cfg.read_write_files, key=lambda x: x.relative_path):
                if hasattr(f, "owning_node") and f.owning_node is not None:
                    node = f.owning_node
                    if node not in self._node_states:
                        self._nodes.append(node)
                        self._alias_to_node[f.relative_path] = node
                        self._node_to_alias[node] = f.relative_path
                        self._node_states[node] = "OPEN"
        if not self._nodes:
            dummy_node = dag_storage.Node(
                unit_address="//session:target", role_address=""
            )
            self._nodes.append(dummy_node)
            self._alias_to_node["target"] = dummy_node
            self._node_to_alias[dummy_node] = "target"
            self._node_states[dummy_node] = "OPEN"

    @property
    def nodes(self) -> Sequence[dag_storage.Node]:
        self._ensure_nodes()
        return self._nodes

    @property
    def is_multi_node(self) -> bool:
        self._ensure_nodes()
        return len(self._nodes) > 1

    def get_node_for_alias(self, alias_or_name: str) -> Optional[dag_storage.Node]:
        self._ensure_nodes()
        if alias_or_name in self._alias_to_node:
            return self._alias_to_node[alias_or_name]
        for node, alias in self._node_to_alias.items():
            if alias == alias_or_name or node.unit_address == alias_or_name:
                return node
        return None

    def get_alias_for_node(self, node: dag_storage.Node) -> str:
        self._ensure_nodes()
        return self._node_to_alias.get(node, node.unit_address)

    def get_node_state(self, node: dag_storage.Node) -> str:
        self._ensure_nodes()
        return self._node_states.get(node, "OPEN")

    def set_node_state(self, node: dag_storage.Node, state: str) -> None:
        self._ensure_nodes()
        self._node_states[node] = state

    def open_nodes(self) -> List[dag_storage.Node]:
        self._ensure_nodes()
        return [n for n in self._nodes if self._node_states.get(n) == "OPEN"]

    def get_in_session_dependencies(
        self, node: dag_storage.Node
    ) -> Set[dag_storage.Node]:
        self._ensure_nodes()
        deps: Set[dag_storage.Node] = set()
        storage = get_singleton(dag_storage.DagStorage)
        for d in storage.get_dependencies(node):
            if d.node in self._node_states and d.node != node:
                deps.add(d.node)
        return deps

    def block_dependents(self, node: dag_storage.Node) -> None:
        self._ensure_nodes()
        to_check = [node]
        while to_check:
            curr = to_check.pop(0)
            for n in self._nodes:
                if self._node_states.get(n) == "OPEN":
                    if curr in self.get_in_session_dependencies(n):
                        self._node_states[n] = "BLOCKED"
                        to_check.append(n)

    def lock_node_files(self, node: dag_storage.Node) -> None:
        self._ensure_nodes()
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        cfg = get_singleton(agent_node_config.NodeConfig)
        target_alias = self.get_alias_for_node(node)
        for f in cfg.read_write_files:
            if isinstance(f, agent_file_alias.ReadWriteFile):
                if f.relative_path == target_alias or (
                    hasattr(f, "owning_node") and f.owning_node == node
                ):
                    edit_mgr.lock_file(f)

    def initialize(self) -> None:
        # Requirement: The run controller unconditionally installs the submit tool, fail tool, and run tests tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured.
        # Requirement: Verification checks exposed by the run controller include the session verification checks from node config.
        self._ensure_nodes()
        tm = get_singleton(tool_provider.ToolManager)
        cfg = get_singleton(agent_node_config.NodeConfig)
        if cfg.is_step_mode:
            tm.install_tool(get_singleton(AdvanceTool))
        tm.install_tool(get_singleton(SubmitTool))
        tm.install_tool(get_singleton(FailTool))
        tm.install_tool(get_singleton(CheckFileTool))
        if self.blame_targets or any(cfg.blame_targets_by_node.values()):
            tm.install_tool(get_singleton(BlameTool))

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        return cfg.verification_checks

    @property
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        return cfg.blame_targets

    def get_blame_targets_for_node(
        self, node: dag_storage.Node
    ) -> Set[agent_file_alias.BoundFile]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        if node in cfg.blame_targets_by_node:
            return cfg.blame_targets_by_node[node]
        return self.blame_targets

    def evaluate_verification(self) -> Tuple[bool, str]:
        # Requirement: Evaluation of verification checks is cached alongside the edit manager file update revision.
        # Requirement: Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when workspace files have been updated since the previous evaluation.
        # Requirement: When workspace files have not been updated since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        current_rev = edit_mgr.file_update_revision
        if self._cached_revision is not None and current_rev == self._cached_revision:
            return self._cached_passed or False, self._cached_diag

        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        passed = True
        diag_out = ""
        for check in self.verification_checks:
            chk_passed, chk_diag = check.verify()
            if not chk_passed:
                passed = False
                diag_out = alias_mgr.sanitize_text(chk_diag)
                break
            elif chk_diag:
                diag_out = alias_mgr.sanitize_text(chk_diag)

        self._cached_passed = passed
        self._cached_diag = diag_out
        self._cached_revision = current_rev
        return passed, diag_out

    def evaluate_verification_for_node(
        self, node: dag_storage.Node
    ) -> Tuple[bool, str]:
        cfg = get_singleton(agent_node_config.NodeConfig)
        checks = (
            cfg.verification_checks_by_node.get(node)
            if cfg.verification_checks_by_node
            else None
        )
        if not checks:
            return self.evaluate_verification()

        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        current_rev = edit_mgr.file_update_revision
        if (
            node in self._cached_node_revision
            and self._cached_node_revision[node] == current_rev
        ):
            return self._cached_node_passed.get(
                node, False
            ), self._cached_node_diag.get(node, "")

        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        passed = True
        diag_out = ""
        for check in checks:
            chk_passed, chk_diag = check.verify()
            if not chk_passed:
                passed = False
                diag_out = alias_mgr.sanitize_text(chk_diag)
                break
            elif chk_diag:
                diag_out = alias_mgr.sanitize_text(chk_diag)

        self._cached_node_passed[node] = passed
        self._cached_node_diag[node] = diag_out
        self._cached_node_revision[node] = current_rev
        return passed, diag_out

    def format_open_targets_reminder(self) -> str:
        open_nodes = self.open_nodes()
        if not open_nodes:
            return ""
        tmpl_formatter = get_singleton(template_format.TemplateFormatter)
        template_str = (
            "Remaining open files:\n"
            "<!-- for: node in nodes -->\n"
            "- `<node.src_alias>`\n"
            "<!-- endfor -->"
        )
        node_items = [{"src_alias": self.get_alias_for_node(n)} for n in open_nodes]
        return tmpl_formatter.format_template(
            template_str, {"nodes": node_items}
        ).strip()


class AdvanceTool(sandbox_run_control.AdvanceTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._is_first_call = True

    @property
    def name(self) -> str:
        # Requirement: The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.
        return "advance"

    @property
    def description(self) -> str:
        return "Advances guide steps or completes the session."

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        # Requirement: The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.
        return set()

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.Response:
        guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        rc = get_singleton(RunController)

        # Requirement: On its first execution, the advance tool delivers the initial guide summary through guide delivery without updating verification results.
        if self._is_first_call:
            self._is_first_call = False
            next_step = guide_del.advance_step(
                verification_passed=True, failure_diagnostics=None
            )
            content = next_step.content if next_step is not None else ""
            reminder = next_step.reminder if next_step is not None else None
            follow_up = next_step.follow_up_tool_call if next_step is not None else None
            return tool_provider.Response(
                is_failed=False,
                is_terminated=False,
                content=content,
                reminder=reminder,
                suppression_key="advance",
                follow_up_tool_call=follow_up,
            )

        # Requirement: On subsequent executions, executing the advance tool updates verification results if outdated.
        passed, _ = rc.evaluate_verification()
        if not passed:
            # Requirement: Tool execution fails when verification is failing, reminding the agent that the check file tool should be called first and specifying a follow-up execution of the check file tool with reasoning text indicating that verification results must be inspected before advancing.
            follow_up = tool_provider.FollowUpToolCall(
                tool_name="check_file",
                wire_parameter_bindings=tool_provider.WireParameterBindings(
                    bindings=set()
                ),
                reasoning_text="Verification results must be inspected before advancing.",
            )
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Verification is failing. The check file tool should be called first.",
                reminder="The check file tool should be called first to inspect verification results.",
                suppression_key="advance",
                follow_up_tool_call=follow_up,
            )

        # Requirement: Tool execution advances guide delivery and delivers the next step section when verification is passing and guide steps remain.
        if guide_del.has_steps_remaining:
            next_step = guide_del.advance_step(
                verification_passed=True, failure_diagnostics=None
            )
            if next_step is not None:
                return tool_provider.Response(
                    is_failed=next_step.is_failed,
                    is_terminated=next_step.is_terminated,
                    content=next_step.content,
                    reminder=next_step.reminder,
                    suppression_key="advance",
                    follow_up_tool_call=next_step.follow_up_tool_call,
                )

        if edit_mgr.has_modifications:
            # Requirement: Tool execution fails with a reminder to call the submit tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="All guide steps have been completed, but workspace files were modified.",
                reminder="Call the submit tool with a change summary describing modifications.",
                suppression_key="advance",
            )

        # Requirement: Tool execution produces a response specifying a follow-up execution of the submit tool without a change summary and with reasoning text indicating that all guide steps are complete when verification is passing, no steps remain, and no workspace files were modified.
        follow_up = tool_provider.FollowUpToolCall(
            tool_name="submit",
            wire_parameter_bindings=tool_provider.WireParameterBindings(bindings=set()),
            reasoning_text="All guide steps are complete.",
        )
        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content="All guide steps have been completed.",
            suppression_key="advance",
            follow_up_tool_call=follow_up,
        )


class SubmitTool(sandbox_run_control.SubmitTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        # Requirement: The submit tool is named `submit`, accepting an optional target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
        return "submit"

    @property
    def description(self) -> str:
        return "Submits a completed target file and enforces change documentation."

    @property
    def target(self) -> tool_provider.Parameter:
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.Parameter(
            name="target",
            description="Target file alias being submitted. Required in multi-target sessions; may be omitted in single-target sessions.",
            parameter_converter=alias_mgr,
            is_required=False,
        )

    @property
    def change_summary(self) -> tool_provider.Parameter:
        # Requirement: The submit tool change summary parameter uses a string parameter converter to accept text.
        # Requirement: The submit tool is named `submit`, accepting an optional target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="change_summary",
            description="Summary of modifications made to workspace files. May be omitted when no workspace files were modified.",
            parameter_converter=str_conv,
            is_required=False,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {self.target, self.change_summary}

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        summary_str = str(bindings_map.get("change_summary", "") or "").strip()
        raw_target = bindings_map.get("target")

        guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)
        cfg = get_singleton(agent_node_config.NodeConfig)
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        rc = get_singleton(RunController)

        # Requirement: Executing the submit tool updates verification results if outdated.
        rc.evaluate_verification()

        # Requirement: Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call with reasoning text indicating that remaining guide steps must be completed before finishing.
        if cfg.is_step_mode and guide_del.has_steps_remaining:
            follow_up = tool_provider.FollowUpToolCall(
                tool_name="advance",
                wire_parameter_bindings=tool_provider.WireParameterBindings(
                    bindings=set()
                ),
                reasoning_text="Remaining guide steps must be completed before finishing.",
            )
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: Cannot finish while guide steps remain.",
                reminder="The advance tool must be called while guide steps remain.",
                suppression_key="submit",
                follow_up_tool_call=follow_up,
            )

        # Resolve target node
        target_str = ""
        if raw_target is not None:
            target_str = (
                getattr(raw_target, "relative_path", None)
                or getattr(raw_target, "short_name", None)
                or str(raw_target)
            ).strip()

        if not target_str:
            if rc.is_multi_node:
                # Requirement: In multi-target sessions, tool execution fails when the target parameter is omitted or does not match an open session target, reminding the agent to specify an open target.
                open_targets = ", ".join(
                    f"`{rc.get_alias_for_node(n)}`" for n in rc.open_nodes()
                )
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content="Error: Target parameter must be specified in a multi-target session.",
                    reminder=f"Specify an open target: {open_targets}",
                    suppression_key="submit",
                )
            target_node = rc.nodes[0]
        else:
            target_node = rc.get_node_for_alias(target_str)
            if target_node is None or rc.get_node_state(target_node) != "OPEN":
                # Requirement: In multi-target sessions, tool execution fails when the target parameter is omitted or does not match an open session target, reminding the agent to specify an open target.
                open_targets = ", ".join(
                    f"`{rc.get_alias_for_node(n)}`" for n in rc.open_nodes()
                )
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: Target '{target_str}' is not an open target.",
                    reminder=f"Specify an open target: {open_targets}",
                    suppression_key="submit",
                )

        target_alias = rc.get_alias_for_node(target_node)

        # Requirement: Tool execution fails when an in-session dependency of the target has not yet been submitted, reminding the agent that in-session dependencies must be submitted before dependent targets.
        in_session_deps = rc.get_in_session_dependencies(target_node)
        for dep in in_session_deps:
            if rc.get_node_state(dep) != "SUBMITTED":
                dep_alias = rc.get_alias_for_node(dep)
                return tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Error: In-session dependency `{dep_alias}` must be submitted before `{target_alias}`.",
                    reminder=f"In-session dependencies must be submitted before dependent targets. Submit `{dep_alias}` first.",
                    suppression_key="submit",
                )

        # Verification check for target
        passed, _ = rc.evaluate_verification_for_node(target_node)
        # Requirement: Tool execution fails when verification is failing, reminding the agent that the check file tool should be called first and specifying a follow-up execution of the check file tool with reasoning text indicating that verification results must be inspected before submitting.
        if not passed:
            follow_up = tool_provider.FollowUpToolCall(
                tool_name="check_file",
                wire_parameter_bindings=tool_provider.WireParameterBindings(
                    bindings=set()
                ),
                reasoning_text="Verification results must be inspected before submitting.",
            )
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Verification is failing. The check file tool should be called first.",
                reminder="The check file tool should be called first to inspect verification results.",
                suppression_key="submit",
                follow_up_tool_call=follow_up,
            )

        # Requirement: Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.
        if cfg.feedback and not edit_mgr.has_modifications:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: Session feedback is present but no workspace files were modified.",
                reminder="Workspace files must be modified to address feedback or the fail tool must be used.",
                suppression_key="submit",
            )

        # Requirement: Tool execution fails if workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files.
        if edit_mgr.has_modifications and not summary_str:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: Workspace files were modified but change_summary was not provided.",
                reminder="A change summary must be provided when completing the session after modifying workspace files.",
                suppression_key="submit",
            )

        # Requirement: Tool execution marks the target as submitted, locks the target read-write files in the edit manager against modification, and produces a terminating response indicating that the session completed successfully when all session targets are resolved, or produces a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
        rc.set_node_state(target_node, "SUBMITTED")
        rc.lock_node_files(target_node)
        open_nodes = rc.open_nodes()

        if open_nodes:
            open_reminder = rc.format_open_targets_reminder()
            content = f"Target `{target_alias}` submitted successfully.\n\n{open_reminder}".strip()
            return tool_provider.Response(
                is_failed=False,
                is_terminated=False,
                content=content,
                reminder=open_reminder,
                suppression_key="submit",
            )

        msg = (
            f"Session completed successfully: {summary_str}".strip()
            if summary_str
            else "Session completed successfully."
        )
        return tool_provider.Response(
            is_failed=False,
            is_terminated=True,
            content=msg,
            suppression_key="submit",
        )


class FailTool(sandbox_run_control.FailTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        # Requirement: The fail tool is named `fail`.
        return "fail"

    @property
    def description(self) -> str:
        return "Terminates the run or marks a target in failure."

    @property
    def target(self) -> tool_provider.Parameter:
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.Parameter(
            name="target",
            description="Target file alias being failed. Required in multi-target sessions; may be omitted in single-target sessions.",
            parameter_converter=alias_mgr,
            is_required=False,
        )

    @property
    def explanation(self) -> tool_provider.Parameter:
        # Requirement: The fail tool explanation parameter uses a string parameter converter to accept text.
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="explanation",
            description="Explanation of why the run failed",
            parameter_converter=str_conv,
            is_required=True,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {self.target, self.explanation}

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.Response:
        # Requirement: Executing the fail tool marks the target as failed and in-session dependent targets as blocked, producing a terminating response carrying the explanation when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        exp = str(bindings_map.get("explanation", "Failed"))
        raw_target = bindings_map.get("target")

        rc = get_singleton(RunController)
        target_str = ""
        if raw_target is not None:
            target_str = (
                getattr(raw_target, "relative_path", None)
                or getattr(raw_target, "short_name", None)
                or str(raw_target)
            ).strip()

        if not target_str:
            target_node = rc.nodes[0]
        else:
            target_node = rc.get_node_for_alias(target_str) or rc.nodes[0]

        target_alias = rc.get_alias_for_node(target_node)
        # Requirement: Executing the fail tool marks the target as failed, locks the target read-write files in the edit manager against modification, and marks in-session dependent targets as blocked, producing a terminating response carrying the explanation when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
        rc.set_node_state(target_node, "FAILED")
        rc.lock_node_files(target_node)
        rc.block_dependents(target_node)

        open_nodes = rc.open_nodes()
        if open_nodes:
            open_reminder = rc.format_open_targets_reminder()
            content = (
                f"Target `{target_alias}` failed: {exp}\n\n{open_reminder}".strip()
            )
            return tool_provider.Response(
                is_failed=False,
                is_terminated=False,
                content=content,
                reminder=open_reminder,
            )

        return tool_provider.Response(
            is_failed=True,
            is_terminated=True,
            content=f"Failed: {exp}",
        )


class BlameTool(sandbox_run_control.BlameTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        # Requirement: The blame tool is named `blame`.
        return "blame"

    @property
    def description(self) -> str:
        return "Attributes failure to a dependency node via a blame target."

    @property
    def target(self) -> tool_provider.Parameter:
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.Parameter(
            name="target",
            description="Session target file alias attributing the blame. Required in multi-target sessions; may be omitted in single-target sessions.",
            parameter_converter=alias_mgr,
            is_required=False,
        )

    @property
    def blame_target(self) -> tool_provider.Parameter:
        # Requirement: The blame tool blame target parameter uses the alias manager to convert a file alias.
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.Parameter(
            name="blame_target",
            description="Target bound file to blame",
            parameter_converter=alias_mgr,
            is_required=False,
        )

    @property
    def explanation(self) -> tool_provider.Parameter:
        # Requirement: The blame tool explanation parameter uses a string parameter converter to accept text.
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="explanation",
            description="Explanation of the defect",
            parameter_converter=str_conv,
            is_required=True,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {self.target, self.blame_target, self.explanation}

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        raw_target = bindings_map.get("target")
        raw_blame_target = bindings_map.get("blame_target")
        exp = str(bindings_map.get("explanation", ""))

        rc = get_singleton(RunController)

        # Backward compatibility for single-target sessions:
        # If blame_target omitted, but target provided in single-target session: blamee is target
        if not rc.is_multi_node and raw_blame_target is None and raw_target is not None:
            blamee = raw_target
            source_node = rc.nodes[0]
        else:
            blamee = raw_blame_target
            if raw_target is not None:
                target_str = (
                    getattr(raw_target, "relative_path", None)
                    or getattr(raw_target, "short_name", None)
                    or str(raw_target)
                ).strip()
                source_node = rc.get_node_for_alias(target_str) or rc.nodes[0]
            else:
                source_node = rc.nodes[0]

        # Requirement: Executing the blame tool fails if the target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.
        allowed_blame_targets = rc.get_blame_targets_for_node(source_node)
        matched_target: Optional[agent_file_alias.BoundFile] = None
        blamee_str = ""
        if blamee is not None:
            blamee_str = (
                getattr(blamee, "relative_path", None)
                or getattr(blamee, "short_name", None)
                or str(blamee)
            ).strip()
        for bt in allowed_blame_targets:
            bt_name = getattr(bt, "relative_path", getattr(bt, "short_name", ""))
            if bt == blamee or bt_name == blamee_str:
                matched_target = bt
                break

        if matched_target is None:
            avail = ", ".join(
                getattr(t, "relative_path", getattr(t, "short_name", ""))
                for t in allowed_blame_targets
            )
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: Target '{blamee_str}' is not a valid blame target. Available: {avail}",
                reminder="Only upstream files configured as blame targets can be blamed.",
            )

        # Requirement: On successful blame tool execution, the response marks the submitted target of the blame as resolved, locks the submitted target read-write files in the edit manager against modification, and marks in-session dependent targets as blocked, producing a terminating response attributing defect feedback to the blame target owning node when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
        target_name = getattr(
            matched_target, "relative_path", getattr(matched_target, "short_name", "")
        )
        source_alias = rc.get_alias_for_node(source_node)
        rc.set_node_state(source_node, "BLAME")
        rc.lock_node_files(source_node)
        rc.block_dependents(source_node)

        open_nodes = rc.open_nodes()
        if open_nodes:
            open_reminder = rc.format_open_targets_reminder()
            content = f"Target `{source_alias}` blamed `{target_name}`: {exp}\n\n{open_reminder}".strip()
            return tool_provider.Response(
                is_failed=False,
                is_terminated=False,
                content=content,
                reminder=open_reminder,
            )

        return tool_provider.Response(
            is_failed=False,
            is_terminated=True,
            content=f"Blamed {target_name}: {exp}",
        )


class CheckFileTool(sandbox_run_control.CheckFileTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._last_tested_revision: Optional[int] = None
        self._last_tested_node_revision: Dict[dag_storage.Node, int] = {}

    @property
    def name(self) -> str:
        # Requirement: The check file tool is named `check_file`, accepting an optional src parameter, and shares a constant suppression key `check_file`.
        return "check_file"

    @property
    def description(self) -> str:
        return (
            "Checks static type correctness and syntax for the specified source file alias or open targets. "
            "Call check_file often while developing to catch type and syntax errors early."
        )

    @property
    def src(self) -> tool_provider.Parameter:
        alias_mgr = get_singleton(agent_file_alias.AliasManager)
        return tool_provider.Parameter(
            name="src",
            description="Source file alias to check. May be omitted to check open targets.",
            parameter_converter=alias_mgr,
            is_required=False,
        )

    @property
    def target(self) -> tool_provider.Parameter:
        return self.src

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        # Requirement: The check file tool is named `check_file`, accepting an optional src parameter, and shares a constant suppression key `check_file`.
        return {self.src}

    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        raw_target = bindings_map.get("src") or bindings_map.get("target")

        rc = get_singleton(RunController)
        guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        cfg = get_singleton(agent_node_config.NodeConfig)

        # Requirement: Executing the check file tool updates verification results if outdated.
        # Requirement: When a src target is specified, executing the check file tool evaluates verification checks for that target.
        target_str = ""
        if raw_target is not None:
            target_str = (
                getattr(raw_target, "relative_path", None)
                or getattr(raw_target, "short_name", None)
                or str(raw_target)
            ).strip()

        target_node: Optional[dag_storage.Node] = None
        if target_str:
            target_node = rc.get_node_for_alias(target_str)

        if target_node is not None:
            passed, diag = rc.evaluate_verification_for_node(target_node)
        else:
            passed, diag = rc.evaluate_verification()

        current_rev = edit_mgr.file_update_revision
        is_repeated = (
            self._last_tested_revision is not None
            and self._last_tested_revision == current_rev
        )
        self._last_tested_revision = current_rev

        reminder: Optional[str] = None
        follow_up: Optional[tool_provider.FollowUpToolCall] = None

        if is_repeated:
            rw_file = (
                next(
                    iter(
                        sorted(
                            cfg.read_write_files,
                            key=lambda f: getattr(
                                f, "relative_path", getattr(f, "short_name", "")
                            ),
                        )
                    ),
                    None,
                )
                if cfg.read_write_files
                else None
            )
            src_name = (
                getattr(rw_file, "relative_path", getattr(rw_file, "short_name", ""))
                if rw_file
                else "session read-write files"
            )
            status_word = "passes" if passed else "failed"
            action_word = "advance" if cfg.is_step_mode else "submit"
            # Requirement: Reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when workspace files have not been updated since the previous check file tool execution.
            reminder = f"Verification {status_word}, no new information will be revealed by this tool call until {src_name} is updated."
            if rw_file is not None:
                rw_file_alias = getattr(
                    rw_file, "relative_path", getattr(rw_file, "short_name", "")
                )
                if passed:
                    reasoning_text = (
                        f"Oh, verification passes and no new information will be revealed by calling check_file again until files are updated. "
                        f"Let me read {rw_file_alias} again and see if I can figure out a different course of action. "
                        f"If it is already correct, I need to {action_word} the agent session rather than check files again."
                    )
                else:
                    reasoning_text = (
                        f"Oh, verification failed and no new information will be revealed by calling check_file again until files are updated. "
                        f"Let me read {rw_file_alias} again and see if I can figure out a different course of action."
                    )
                # Requirement: Specifies a follow-up execution of the view file tool on the session source file and reasoning text noting that verification passed and to advance or submit the session if correct, or noting that verification failed until files are updated, when workspace files have not been updated since the previous check file tool execution.
                follow_up = tool_provider.FollowUpToolCall(
                    tool_name="view_file",
                    wire_parameter_bindings=tool_provider.WireParameterBindings(
                        bindings={("path", rw_file_alias)}
                    ),
                    reasoning_text=reasoning_text,
                )

        if not passed:
            # Requirement: Fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.
            vf_block = ""
            guide_obj = getattr(guide_del, "guide", None)
            if guide_obj and getattr(guide_obj, "verification_failure", None):
                vf_block = (
                    f"\n\n## Verification failure\n{guide_obj.verification_failure}"
                )
            content = f"Verification failed: {diag}{vf_block}".strip()
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=content,
                reminder=reminder,
                suppression_key="check_file",
                follow_up_tool_call=follow_up,
            )

        # Requirement: Produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.
        base_msg = (
            cfg.verification_success_message
            or "Verification passed: All checks succeeded."
        )
        content = base_msg
        if diag:
            content = f"{content}\n\n{diag}".strip()
        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content=content,
            reminder=reminder,
            suppression_key="check_file",
            follow_up_tool_call=follow_up,
        )


RunTestsTool = CheckFileTool


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RunController,
        keys=[RunController, sandbox_run_control.RunController],
        tier="agent_session",
    )
    reg.register_singleton(
        AdvanceTool,
        keys=[AdvanceTool, sandbox_run_control.AdvanceTool, tool_provider.Tool],
        tier="agent_session",
    )
    reg.register_singleton(
        SubmitTool,
        keys=[
            SubmitTool,
            sandbox_run_control.SubmitTool,
            sandbox_run_control.FinishTool,
            tool_provider.Tool,
        ],
        tier="agent_session",
    )
    reg.register_singleton(
        FailTool,
        keys=[FailTool, sandbox_run_control.FailTool, tool_provider.Tool],
        tier="agent_session",
    )
    reg.register_singleton(
        BlameTool,
        keys=[BlameTool, sandbox_run_control.BlameTool, tool_provider.Tool],
        tier="agent_session",
    )
    reg.register_singleton(
        CheckFileTool,
        keys=[
            CheckFileTool,
            sandbox_run_control.CheckFileTool,
            sandbox_run_control.RunTestsTool,
            tool_provider.Tool,
        ],
        tier="agent_session",
    )
