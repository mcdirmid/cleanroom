from typing import List, Optional, Sequence, Set
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
        pass

    def initialize(self) -> None:
        # Requirement: The run controller installs the advance tool and fail tool unconditionally, and installs the blame tool only when blame targets are configured in the node config.
        tm = get_singleton(tool_provider.ToolManager)
        tm.install_tool(get_singleton(AdvanceTool))
        tm.install_tool(get_singleton(FailTool))
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

class AdvanceTool(sandbox_run_control.AdvanceTool, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._cached_failure_output: Optional[str] = None
        self._cached_failure_revision: Optional[int] = None

    @property
    def name(self) -> str:
        return "advance"

    @property
    def description(self) -> str:
        return "Advances guide steps or completes the session."

    @property
    def change_summary(self) -> tool_provider.Parameter:
        str_conv = get_singleton(tool_provider.StringParameterConverter)
        return tool_provider.Parameter(
            name="change_summary",
            description="Must be omitted while guide steps remain. Required only when concluding the session after modifying workspace files.",
            parameter_converter=str_conv,
            is_required=False,
        )

    @property
    def parameters(self) -> Set[tool_provider.Parameter]:
        return {self.change_summary}

    def _format_response(self, resp: tool_provider.Response) -> tool_provider.Response:
        node_cfg = get_singleton(node_config.NodeConfig)
        # Requirement: When guide step mode is on, tool execution always presents the guide summary from node config whether execution fails or succeeds.
        if node_cfg.guide is not None and not resp.content.startswith(node_cfg.guide.summary):
            return tool_provider.Response(
                is_failed=resp.is_failed,
                is_terminated=resp.is_terminated,
                content=f"{node_cfg.guide.summary}\n\n{resp.content}".strip(),
                reminder=resp.reminder,
            )
        return resp

    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        bindings_map = {p.name: v for p, v in actual_parameter_bindings.bindings}
        summary_str = str(bindings_map.get("change_summary", "") or "").strip()

        guide_del = get_singleton(sandbox_guide_delivery.GuideDelivery)
        if guide_del.has_steps_remaining:
            if summary_str:
                # Requirement: When guide step mode is on and steps remain in guide delivery, tool execution fails if a change summary is provided, and reminds the agent that a change summary can only be provided when completing the session after seeing all guide steps.
                return self._format_response(tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content="Error: change_summary is not allowed while guide steps remain. The change_summary parameter is only for describing workspace file modifications upon session completion.",
                    reminder="A change summary can only be provided when completing the session after seeing all guide steps.",
                ))
        else:
            edit_mgr = get_singleton(sandbox_file_editor.EditManager)
            if not edit_mgr.has_modifications and summary_str:
                # Requirement: When no file has changed, tool execution fails if a change summary is provided, and reminds the agent that a change summary can only be provided when workspace files were modified.
                return self._format_response(tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content="Error: change_summary is not allowed when no workspace files were modified. The change_summary parameter is only for describing workspace file modifications upon session completion.",
                    reminder="A change summary can only be provided when workspace files were modified.",
                ))

            # Requirement: If workspace files were modified and either guide step mode is not on or no steps remain in guide delivery, tool execution fails if the change summary is not provided, and reminds the agent that a change summary must be provided when completing the session after modifying workspace files.
            if edit_mgr.has_modifications and not summary_str:
                return self._format_response(tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content="Error: Workspace files were modified but change_summary was not provided.",
                    reminder="A change summary must be provided when completing the session after modifying workspace files.",
                ))

        edit_mgr = get_singleton(sandbox_file_editor.EditManager)
        current_rev = edit_mgr.file_update_revision
        if self._cached_failure_revision is not None and current_rev == self._cached_failure_revision:
            # Requirement: When the advance tool is called after a previous advance call that failed verification and no workspace files have been updated since that failure as indicated by the edit manager's file update revision, tool execution fails without re-executing verification checks, serving the cached output from the previous failed verification and reminding the agent that verification failed previously and workspace files must be updated before advancing again.
            return self._format_response(tool_provider.Response(
                is_failed=True,
                is_terminated=False,
                content=self._cached_failure_output or "",
                reminder="Verification failed previously and workspace files must be updated before advancing again.",
            ))

        # Requirement: Verification checks execute as long as the change summary is set correctly, unless the previous advance call failed verification and no workspace files have been updated since.
        rc = get_singleton(RunController)
        vchecks = list(rc.verification_checks)

        alias_mgr = get_singleton(file_alias.AliasManager)
        v_passed = True
        sanitized_diag: Optional[str] = None
        for check in vchecks:
            passed, diag = check.verify()
            if not passed:
                v_passed = False
                sanitized_diag = alias_mgr.sanitize_text(diag)
                break

        if not v_passed:
            # Requirement: When verification checks execute and any verification check fails, tool execution fails with diagnostic feedback sanitized through the alias manager, and the advance tool caches the failure output alongside the current file update revision from the edit manager.
            if guide_del.has_steps_remaining:
                next_step = guide_del.advance_step(
                    verification_passed=False, failure_diagnostics=sanitized_diag
                )
                if next_step is not None:
                    resp = self._format_response(next_step)
                else:
                    resp = self._format_response(tool_provider.Response(
                        is_failed=True,
                        is_terminated=False,
                        content=f"Verification failed: {sanitized_diag}",
                    ))
            else:
                resp = self._format_response(tool_provider.Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Verification failed: {sanitized_diag}",
                ))
            self._cached_failure_output = resp.content
            self._cached_failure_revision = current_rev
            return resp

        self._cached_failure_output = None
        self._cached_failure_revision = None

        if guide_del.has_steps_remaining:
            next_step = guide_del.advance_step(
                verification_passed=True, failure_diagnostics=None
            )
            if next_step is not None:
                return self._format_response(next_step)

        return self._format_response(tool_provider.Response(
            is_failed=False,
            is_terminated=True,
            content=f"Session completed successfully: {summary_str}".strip(),
        ))

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
        FailTool,
        keys=[FailTool, sandbox_run_control.FailTool, tool_provider.Tool],
        tier="agent_session",
    )
    reg.register_singleton(
        BlameTool,
        keys=[BlameTool, sandbox_run_control.BlameTool, tool_provider.Tool],
        tier="agent_session",
    )
