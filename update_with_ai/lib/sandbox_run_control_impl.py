from typing import List, Optional, Sequence, Set, Tuple
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
    def verification_checks(self) -> Sequence[sandbox_run_control.VerificationCheck]:
        cfg = get_singleton(node_config.NodeConfig)
        return cfg.verification_checks

    @property
    def blame_targets(self) -> Set[file_alias.BoundFile]:
        cfg = get_singleton(node_config.NodeConfig)
        return cfg.blame_targets

    def has_cached_failure(self) -> bool:
        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        return (
            self._cached_revision is not None
            and edit_mgr.file_update_revision == self._cached_revision
            and not self._cached_passed
        )

    def evaluate_verification(self) -> Tuple[bool, str]:
        # Requirement: Evaluation of verification checks is cached alongside the edit manager file update revision.
        # Requirement: Verification check execution is omitted and the cached result is reused whenever workspace files have not been updated since the previous evaluation as indicated by the file update revision.
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

        self._cached_passed = passed
        self._cached_diag = diag_out
        self._cached_revision = current_rev
        return passed, diag_out

class AdvanceTool(sandbox_run_control.AdvanceTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        pass

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

        is_cached_fail = rc.has_cached_failure()
        passed, diag = rc.evaluate_verification()
        if not passed:
            # Requirement: When the previous evaluation failed and workspace files have not been updated since, tool execution fails with the cached diagnostic output, reminding the agent that workspace files must be updated before proceeding.
            reminder = (
                "Calling advance without modifying workspace files will always fail with cached diagnostics and cannot advance the guide. Workspace files must be updated before proceeding."
                if is_cached_fail
                else None
            )
            if guide_del.has_steps_remaining:
                # Requirement: Failing verification halts progression and reports diagnostic feedback sanitized through the alias manager when guide steps remain.
                next_step = guide_del.advance_step(
                    verification_passed=False, failure_diagnostics=diag
                )
                if next_step is not None:
                    return tool_provider.Response(
                        is_failed=True,
                        is_terminated=False,
                        content=next_step.content,
                        reminder=reminder or next_step.reminder,
                        suppression_key="advance",
                    )
            # Requirement: Failing verification reports sanitized diagnostic feedback alongside any configured verification failure instructions when no steps remain.
            vf_block = ""
            guide_obj = getattr(guide_del, "guide", None)
            if guide_obj and getattr(guide_obj, "verification_failure", None):
                vf_block = f"\n\n## Verification failure\n{guide_obj.verification_failure}"
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Verification failed: {diag}{vf_block}".strip(),
                reminder=reminder,
                suppression_key="advance",
            )

        # Requirement: Passing verification advances guide delivery and delivers the next step section when guide steps remain.
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
            # Requirement: When no steps remain and workspace files were modified, passing verification fails tool execution with a reminder to call the finish tool with a change summary describing modifications.
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="All guide steps have been completed, but workspace files were modified.",
                reminder="Call the finish tool with a change summary describing modifications.",
                suppression_key="advance",
            )

        # Requirement: When no steps remain and no workspace files were modified, passing verification produces a response specifying a follow-up execution of the finish tool without a change summary.
        follow_up = tool_provider.FollowUpToolCall(
            tool_name="finish",
            wire_parameter_bindings=tool_provider.WireParameterBindings(bindings=set()),
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
            description="Summary of modifications made to workspace files.",
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

        # Requirement: Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.
        if cfg.feedback and not edit_mgr.has_modifications:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: Session feedback is present but no workspace files were modified.",
                reminder="Workspace files must be modified to address feedback or the fail tool must be used.",
                suppression_key="finish",
            )

        if cfg.is_step_mode and guide_del.has_steps_remaining:
            # Requirement: Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call.
            # Requirement: [FinishTool] Executing the finish tool while guide steps remain fails with a reminder to execute the advance tool, specifying the advance tool as a follow-up tool call.
            follow_up = tool_provider.FollowUpToolCall(
                tool_name="advance",
                wire_parameter_bindings=tool_provider.WireParameterBindings(bindings=set()),
            )
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: Cannot finish while guide steps remain.",
                reminder="The advance tool must be called while guide steps remain.",
                suppression_key="finish",
                follow_up_tool_call=follow_up,
            )

        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        # Requirement: Tool execution fails if workspace files were modified and the change summary is omitted, and reminds the agent that a change summary must be provided when completing the session after modifying workspace files.
        if edit_mgr.has_modifications and not summary_str:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: Workspace files were modified but change_summary was not provided.",
                reminder="A change summary must be provided when completing the session after modifying workspace files.",
                suppression_key="finish",
            )

        # Requirement: Tool execution fails if no workspace files were modified and the change summary is provided, and reminds the agent that a change summary can only be provided when workspace files were modified.
        if not edit_mgr.has_modifications and summary_str:
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Error: change_summary provided but no workspace files were modified.",
                reminder="A change summary can only be provided when workspace files were modified.",
                suppression_key="finish",
            )

        rc = get_singleton(RunController)
        is_cached_fail = rc.has_cached_failure()
        passed, diag = rc.evaluate_verification()
        if not passed:
            # Requirement: When the previous evaluation failed and workspace files have not been updated since, tool execution fails with the cached diagnostic output, reminding the agent that workspace files must be updated before proceeding.
            # Requirement: Tool execution evaluates verification checks, failing with diagnostic feedback sanitized through the alias manager when any verification check fails.
            reminder = "Workspace files must be updated before proceeding." if is_cached_fail else None
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=f"Verification failed: {diag}".strip(),
                reminder=reminder,
                suppression_key="finish",
            )

        # Requirement: Passing verification produces a terminating response indicating that the session completed successfully.
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
        pass

    @property
    def name(self) -> str:
        # Requirement: The run tests tool is named `run_tests` and accepts no parameters.
        return "run_tests"

    @property
    def description(self) -> str:
        return "Directs the agent to run tests through the advance tool or finish tool."

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        # Requirement: The run tests tool is named `run_tests` and accepts no parameters.
        return set()

    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        cfg = get_singleton(node_config.NodeConfig)
        guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)

        # Requirement: Executing the run tests tool always fails reminding the agent that tests can only be run by calling the advance tool when guide step mode is active and guide steps remain in guide delivery, specifying the advance tool as a follow-up tool call.
        if cfg.is_step_mode and guide_del.has_steps_remaining:
            follow_up = tool_provider.FollowUpToolCall(
                tool_name="advance",
                wire_parameter_bindings=tool_provider.WireParameterBindings(bindings=set()),
            )
            return tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content="Tests cannot be run directly with run_tests.",
                reminder="Tests can only be run by calling the advance tool.",
                follow_up_tool_call=follow_up,
            )

        # Requirement: Executing the run tests tool always fails reminding the agent that tests can only be run by calling the finish tool when guide step mode is inactive, or when guide step mode is active and no guide steps remain in guide delivery, specifying the finish tool without a change summary as a follow-up tool call.
        follow_up = tool_provider.FollowUpToolCall(
            tool_name="finish",
            wire_parameter_bindings=tool_provider.WireParameterBindings(bindings=set()),
        )
        return tool_provider.Response(
            is_failed=True,
            is_terminated=False,
            content="Tests cannot be run directly with run_tests.",
            reminder="Tests can only be run by calling the finish tool.",
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

