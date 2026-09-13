from typing import Optional, Sequence, Set, Tuple
from . import file_alias
from . import node_config
from . import sandbox_file_editor
from . import sandbox_guide_delivery
from . import sandbox_run_control
from . import tool_provider
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class RunController(sandbox_run_control.RunController, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._cached_passed: Optional[bool] = None
        self._cached_diag: str = ""
        self._cached_revision: Optional[int] = None

    def initialize(self) -> None:
        # Requirement: The run controller unconditionally installs the finish tool, fail tool, and run tests tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured.
        # Requirement: Verification checks exposed by the run controller include the session verification checks from node config.
        tm = get_singleton(tool_provider.ToolManager)
        cfg = get_singleton(node_config.NodeConfig)
        if cfg.is_step_mode:
            tm.install_tool(get_singleton(AdvanceTool))
        tm.install_tool(get_singleton(FinishTool))
        tm.install_tool(get_singleton(FailTool))
        tm.install_tool(get_singleton(RunTestsTool))
        if self.blame_targets:
            tm.install_tool(get_singleton(BlameTool))

    @property
    def verification_checks(self) -> Sequence[node_config.VerificationCheck]:
        cfg = get_singleton(node_config.NodeConfig)
        return cfg.verification_checks

    @property
    def blame_targets(self) -> Set[file_alias.BoundFile]:
        cfg = get_singleton(node_config.NodeConfig)
        return cfg.blame_targets

    def evaluate_verification(self) -> Tuple[bool, str]:
        # Requirement: Evaluation of verification checks is cached alongside the edit manager file update revision.
        # Requirement: Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when workspace files have been updated since the previous evaluation.
        # Requirement: When workspace files have not been updated since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        current_rev = edit_mgr.file_update_revision
        if self._cached_revision is not None and current_rev == self._cached_revision:
            return self._cached_passed or False, self._cached_diag

        alias_mgr = get_singleton(file_alias.AliasManager)
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

    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
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
            # Requirement: Tool execution fails when verification is failing, reminding the agent that the run tests tool should be called first and specifying a follow-up execution of the run tests tool with reasoning text indicating that verification results must be inspected before advancing.
            follow_up = tool_provider.FollowUpToolCall(
                tool_name="run_tests",
                wire_parameter_bindings=tool_provider.WireParameterBindings(bindings=set()),
                reasoning_text="Verification results must be inspected before advancing.",
            )
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Verification is failing. The run tests tool should be called first.",
                reminder="The run tests tool should be called first to inspect verification results.",
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
            # Requirement: Tool execution fails with a reminder to call the finish tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="All guide steps have been completed, but workspace files were modified.",
                reminder="Call the finish tool with a change summary describing modifications.",
                suppression_key="advance",
            )

        # Requirement: Tool execution produces a response specifying a follow-up execution of the finish tool without a change summary and with reasoning text indicating that all guide steps are complete when verification is passing, no steps remain, and no workspace files were modified.
        follow_up = tool_provider.FollowUpToolCall(
            tool_name="finish",
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

class FinishTool(sandbox_run_control.FinishTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        # Requirement: The finish tool is named `finish`, accepting a text change summary parameter, and shares a constant suppression key `finish`.
        return "finish"

    @property
    def description(self) -> str:
        return "Concludes the session and enforces change documentation."

    @property
    def change_summary(self) -> tool_provider.Parameter:
        # Requirement: The finish tool change summary parameter uses a string parameter converter to accept text.
        # Requirement: The finish tool is named `finish`, accepting a text change summary parameter, and shares a constant suppression key `finish`.
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="change_summary",
            description="Summary of modifications made to workspace files. May be omitted when no workspace files were modified.",
            parameter_converter=str_conv,
            is_required=False,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {self.change_summary}

    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        summary_str = str(bindings_map.get("change_summary", "") or "").strip()

        guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)
        cfg = get_singleton(node_config.NodeConfig)
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        rc = get_singleton(RunController)

        # Requirement: Executing the finish tool updates verification results if outdated.
        passed, _ = rc.evaluate_verification()

        # Requirement: Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call with reasoning text indicating that remaining guide steps must be completed before finishing.
        if cfg.is_step_mode and guide_del.has_steps_remaining:
            follow_up = tool_provider.FollowUpToolCall(
                tool_name="advance",
                wire_parameter_bindings=tool_provider.WireParameterBindings(bindings=set()),
                reasoning_text="Remaining guide steps must be completed before finishing.",
            )
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: Cannot finish while guide steps remain.",
                reminder="The advance tool must be called while guide steps remain.",
                suppression_key="finish",
                follow_up_tool_call=follow_up,
            )

        # Requirement: Tool execution fails when verification is failing, reminding the agent that the run tests tool should be called first and specifying a follow-up execution of the run tests tool with reasoning text indicating that verification results must be inspected before finishing.
        if not passed:
            follow_up = tool_provider.FollowUpToolCall(
                tool_name="run_tests",
                wire_parameter_bindings=tool_provider.WireParameterBindings(bindings=set()),
                reasoning_text="Verification results must be inspected before finishing.",
            )
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Verification is failing. The run tests tool should be called first.",
                reminder="The run tests tool should be called first to inspect verification results.",
                suppression_key="finish",
                follow_up_tool_call=follow_up,
            )

        # Requirement: Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.
        if cfg.feedback and not edit_mgr.has_modifications:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: Session feedback is present but no workspace files were modified.",
                reminder="Workspace files must be modified to address feedback or the fail tool must be used.",
                suppression_key="finish",
            )

        # Requirement: Tool execution fails if workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files.
        if edit_mgr.has_modifications and not summary_str:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: Workspace files were modified but change_summary was not provided.",
                reminder="A change summary must be provided when completing the session after modifying workspace files.",
                suppression_key="finish",
            )

        # Requirement: Tool execution produces a terminating response indicating that the session completed successfully when verification is passing and all completion criteria are met.
        msg = f"Session completed successfully: {summary_str}".strip() if summary_str else "Session completed successfully."
        return tool_provider.Response(
            is_failed=False,
            is_terminated=True,
            content=msg,
            suppression_key="finish",
        )

class FailTool(sandbox_run_control.FailTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "fail"

    @property
    def description(self) -> str:
        return "Terminates the run in failure."

    @property
    def explanation(self) -> tool_provider.Parameter:
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="explanation",
            description="Explanation of why the run failed",
            parameter_converter=str_conv,
            is_required=True,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {self.explanation}

    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        # Requirement: Executing the fail tool produces a terminating response carrying the explanation.
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        exp = str(bindings_map.get("explanation", "Failed"))
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
        return "blame"

    @property
    def description(self) -> str:
        return "Attributes failure to a dependency node via a blame target."

    @property
    def blame_target(self) -> tool_provider.Parameter:
        alias_mgr = get_singleton(file_alias.AliasManager)
        return tool_provider.Parameter(
            name="target",
            description="Target bound file to blame",
            parameter_converter=alias_mgr,
            is_required=True,
        )

    @property
    def explanation(self) -> tool_provider.Parameter:
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="explanation",
            description="Explanation of the defect",
            parameter_converter=str_conv,
            is_required=True,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {self.blame_target, self.explanation}

    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        target = bindings_map.get("target")
        exp = str(bindings_map.get("explanation", ""))

        # Requirement: Executing the blame tool fails if the target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.
        rc = get_singleton(RunController)
        if target not in rc.blame_targets:
            avail = ", ".join(t.short_name for t in rc.blame_targets)
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Error: Target '{target}' is not a valid blame target. Available: {avail}",
                reminder="Only upstream files configured as blame targets can be blamed.",
            )

        # Requirement: On successful blame tool execution, the response indicates termination attributing feedback to the blame target owning node.
        target_name = target.short_name if hasattr(target, "short_name") else str(target)
        return tool_provider.Response(
            is_failed=False,
            is_terminated=True,
            content=f"Blamed {target_name}: {exp}",
        )

class RunTestsTool(sandbox_run_control.RunTestsTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._last_tested_revision: Optional[int] = None

    @property
    def name(self) -> str:
        # Requirement: The run tests tool is named `run_tests`, accepts no parameters, and shares a constant suppression key `run_tests`.
        return "run_tests"

    @property
    def description(self) -> str:
        return "Evaluates verification checks and presents results."

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        # Requirement: The run tests tool is named `run_tests`, accepts no parameters, and shares a constant suppression key `run_tests`.
        return set()

    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        rc = get_singleton(RunController)
        guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        cfg = get_singleton(node_config.NodeConfig)

        # Requirement: [RunController] The run controller installs a run tests tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
        passed, diag = rc.evaluate_verification()

        current_rev = edit_mgr.file_update_revision
        is_repeated = (self._last_tested_revision is not None and self._last_tested_revision == current_rev)
        self._last_tested_revision = current_rev

        reminder: Optional[str] = None
        follow_up: Optional[tool_provider.FollowUpToolCall] = None

        if is_repeated:
            rw_file = next(iter(sorted(cfg.read_write_files, key=lambda f: f.short_name)), None) if cfg.read_write_files else None
            src_name = rw_file.short_name if rw_file else "session read-write files"
            status_word = "passes" if passed else "failed"
            action_word = "advance" if cfg.is_step_mode else "finish"
            # Requirement: Reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when workspace files have not been updated since the previous run tests tool execution.
            reminder = f"Verification {status_word}, no new information will be revealed by this tool call until {src_name} is updated."
            if rw_file is not None:
                if passed:
                    reasoning_text = (
                        f"Oh, verification passes and I'm not allowed to run anymore tests. "
                        f"Let me read {rw_file.short_name} again and see if I can figure out a different course of action. "
                        f"If it is already correct, I need to {action_word} the agent session rather than run more tests."
                    )
                else:
                    reasoning_text = (
                        f"Oh, verification failed and I'm not allowed to run anymore tests until I update the files. "
                        f"Let me read {rw_file.short_name} again and see if I can figure out a different course of action."
                    )
                # Requirement: Specifies a follow-up execution of the read tool on the session source file with line numbers requested and reasoning text noting that verification passed without permission to run more tests and to advance or finish the session if correct, or noting that verification failed without permission to run more tests until files are updated, when workspace files have not been updated since the previous run tests tool execution.
                follow_up = tool_provider.FollowUpToolCall(
                    tool_name="read_file",
                    wire_parameter_bindings=tool_provider.WireParameterBindings(
                        bindings={("file", rw_file.short_name), ("line_numbers", True)}
                    ),
                    reasoning_text=reasoning_text,
                )

        if not passed:
            # Requirement: Fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.
            vf_block = ""
            guide_obj = getattr(guide_del, "guide", None)
            if guide_obj and getattr(guide_obj, "verification_failure", None):
                vf_block = f"\n\n## Verification failure\n{guide_obj.verification_failure}"
            content = f"Verification failed: {diag}{vf_block}".strip()
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=content,
                reminder=reminder,
                suppression_key="run_tests",
                follow_up_tool_call=follow_up,
            )

        # Requirement: Produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.
        base_msg = cfg.verification_success_message or "Verification passed: All checks succeeded."
        content = base_msg
        if diag:
            content = f"{content}\n\n{diag}".strip()
        return tool_provider.Response(
            is_failed=False,
            is_terminated=False,
            content=content,
            reminder=reminder,
            suppression_key="run_tests",
            follow_up_tool_call=follow_up,
        )

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
        FinishTool,
        keys=[FinishTool, sandbox_run_control.FinishTool, tool_provider.Tool],
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
        RunTestsTool,
        keys=[RunTestsTool, sandbox_run_control.RunTestsTool, tool_provider.Tool],
        tier="agent_session",
    )

