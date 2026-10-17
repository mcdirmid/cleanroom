# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T11:59:00Z
# CHANGE: Install advance tool and specify follow-up execution when guide step mode is active in get work tool
# CODE_HASH: e1ad87c4e3b7
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
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
from update_with_ai.parts.agent.lib.session import AgentSessionTier, agent_session
import update_with_ai.parts.agent.lib.file_alias as file_alias
import update_with_ai.parts.agent.lib.node_config as node_config
import update_with_ai.parts.control.lib.coordinate as coordinate
import update_with_ai.parts.dag.lib.dag_storage as dag_storage
import update_with_ai.parts.dag.lib.subgraph as dag_subgraph
from . import file_editor
from . import guide_delivery
from . import run_control
from . import submission
from . import template_format
from . import tool_provider

# Requirements specified in run_control_impl.pyi


class CheckFilesTool(run_control.CheckFilesTool, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("check_files")
        self._description = tool_provider.ToolDescription("Inspects verification checks across active files.")
        self._parameters: Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]] = {}

    # Contract: Tool.name - returns 'check_files'.
    @property
    def name(self) -> tool_provider.ToolName:
        return self._name

    # Contract: Tool.description - returns tool description.
    @property
    def description(self) -> tool_provider.ToolDescription:
        return self._description

    # Contract: Tool.parameters - returns tool parameter mapping.
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    # Contract: CheckFilesTool.execute_tool - evaluates verification checks across open targets and modified files, returning cached status, failure feedback, or passing result.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        run_ctrl = get_singleton(run_control.RunController)
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
            alias_mgr = get_singleton(file_alias.AliasManager)
            sanitized_diag = str(alias_mgr.sanitize_text(file_alias.UnsanitizedText(raw_diag)))
            node_cfg = get_singleton(node_config.NodeConfig)
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

        node_cfg = get_singleton(node_config.NodeConfig)
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


class AdvanceTool(run_control.AdvanceTool, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("advance")
        self._description = tool_provider.ToolDescription("Advances progressive guide steps upon passing verification.")
        self._parameters: Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]] = {}

    # Contract: Tool.name - returns 'advance'.
    @property
    def name(self) -> tool_provider.ToolName:
        return self._name

    # Contract: Tool.description - returns tool description.
    @property
    def description(self) -> tool_provider.ToolDescription:
        return self._description

    # Contract: Tool.parameters - returns tool parameter mapping.
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    # Contract: AdvanceTool.execute_tool - advances progressive guide steps upon passing verification, prompting check_files on failure or submit on completion.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        run_ctrl = get_singleton(run_control.RunController)
        run_ctrl.update_verification()

        guide_deliv = get_singleton(guide_delivery.GuideDelivery)
        if not getattr(run_ctrl, "_passed", True):
            raw_diag = getattr(run_ctrl, "_diagnostic_output", "")
            resp = guide_deliv.advance_step(
                verification_passed=False,
                failure_diagnostics=node_config.VerificationDiagnostic(raw_diag),
            )
            failure_content = (
                resp.content
                if resp is not None
                else tool_provider.ToolResponseContent(str(raw_diag) or "Verification failed.")
            )
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=failure_content,
                reminder=tool_provider.ToolReminder("Call check_files first to diagnose and resolve verification failures."),
                follow_up_tool_call=tool_provider.FollowUpToolCall(
                    tool_name=tool_provider.ToolName("check_files"),
                    wire_parameter_bindings={},
                    reasoning_text=tool_provider.ReasoningText(
                        "Verification is failing, so I must call check_files to see the diagnostics before advancing."
                    ),
                ),
            )

        if guide_deliv.has_steps_remaining:
            return cast(
                tool_provider.ToolResponse,
                guide_deliv.advance_step(
                    verification_passed=True,
                    failure_diagnostics=node_config.VerificationDiagnostic(""),
                ),
            )

        edit_mgr = get_singleton(file_editor.EditManager)
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
                reasoning_text=tool_provider.ReasoningText(
                    "All guide steps are complete and no files were modified, so I will submit without a change summary."
                ),
            ),
        )



class GetWorkTool(run_control.GetWorkTool, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._name = tool_provider.ToolName("get_work")
        self._description = tool_provider.ToolDescription("Retrieves active dirty nodes for processing.")
        self._parameters: Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]] = {}

    # Contract: Tool.name - returns 'get_work'.
    @property
    def name(self) -> tool_provider.ToolName:
        return self._name

    # Contract: Tool.description - returns tool description.
    @property
    def description(self) -> tool_provider.ToolDescription:
        return self._description

    # Contract: Tool.parameters - returns tool parameter mapping.
    @property
    def parameters(self) -> Mapping[tool_provider.ParameterName, tool_provider.ToolParameter[Any, Any]]:
        return self._parameters

    # Contract: GetWorkTool.execute_tool - acquires dirty nodes for execution, prepares session task prompt, materializes templates, and registers BlameTool/AdvanceTool as needed.
    def execute_tool(
        self,
        actual_parameter_bindings: Mapping[tool_provider.ToolParameter[Any, Any], tool_provider.SomeParameterActualType],
    ) -> tool_provider.ToolResponse:
        coord = get_singleton(coordinate.SessionCoordinator)
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

        subgraph = get_singleton(dag_subgraph.DagSubgraph)
        schedule = coord.dispatch_get_work(subgraph=subgraph)

        if not schedule.tasks:
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content=tool_provider.ToolResponseContent("No dirty nodes are ready. Workspace is clean."),
            )

        prompts = [t.task_prompt for t in schedule.tasks if getattr(t, "task_prompt", None)]
        task_prompt = "\n\n".join(prompts) if prompts else "Dirty nodes acquired for processing."

        node_cfg = get_singleton(node_config.NodeConfig)
        guide_deliv = get_singleton(guide_delivery.GuideDelivery)
        init_guide = getattr(guide_deliv, "initialize", None)
        if callable(init_guide):
            init_guide()
        formatter = get_singleton(template_format.TemplateFormatter)

        template_parameters = {
            template_format.TemplateKey(str(key)): value
            for key, value in node_cfg.template_parameters.items()
        }
        primer_text = str(
            formatter.format_template(
                template_format.TemplateText(task_prompt), template_parameters
            )
        ).strip() or task_prompt

        guide_file = node_cfg.guide_file
        guide_alias = str(guide_file.relative_path) if guide_file is not None else ""
        # Fallback scan over read_only_files for an .md file to infer guide_alias when guide_file is not set.
        if not guide_alias:
            for read_only_file in node_cfg.read_only_files:
                candidate_alias = str(getattr(read_only_file, "relative_path", read_only_file))
                if candidate_alias.endswith(".md"):
                    guide_alias = candidate_alias
                    break
        if guide_alias and guide_alias not in primer_text:
            primer_text = f"{primer_text}\n\nRead {guide_alias} for alignment guidance."
        if node_cfg.guide and getattr(node_cfg.guide, "summary", None):
            guide_summary = str(node_cfg.guide.summary).strip()
            if guide_summary and guide_summary not in primer_text:
                primer_text = f"{primer_text}\n\n{guide_summary}"

        if any(node_cfg.blame_targets_by_node.values()):
            tool_mgr = get_singleton(tool_provider.ToolManager)
            tool_mgr.install_tool(get_singleton(submission.BlameTool))

        if node_cfg.is_step_mode:
            tool_mgr = get_singleton(tool_provider.ToolManager)
            tool_mgr.install_tool(get_singleton(run_control.AdvanceTool))
            advance_prompt = "Call advance to continue."
            prompt_content = primer_text
            if "call advance" not in prompt_content.lower():
                prompt_content = f"{prompt_content}\n\n{advance_prompt}"
            guide_deliv.record_initial_primer(guide_delivery.InitialPrimer(prompt_content))
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(prompt_content),
                reminder=tool_provider.ToolReminder(advance_prompt),
                follow_up_tool_call=tool_provider.FollowUpToolCall(
                    tool_name=tool_provider.ToolName("advance"),
                    wire_parameter_bindings={},
                    reasoning_text=tool_provider.ReasoningText(
                        "Guide step mode is active, so I will advance to the next guide step once the primer work is done."
                    ),
                ),
            )

        guide_deliv.record_initial_primer(guide_delivery.InitialPrimer(primer_text))
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(primer_text),
        )


class RunController(run_control.RunController, InTier[AgentSessionTier], Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._cached_hashes: Optional[Mapping[file_alias.FileAlias, file_editor.FileHash]] = None
        self._is_unchanged: bool = False
        self._passed: bool = True
        self._diagnostic_output: str = ""

    # Contract: RunController.initialize - registers session outcome tools, check_files, get_work, and conditionally advance tool.
    def initialize(self) -> None:
        tool_mgr = get_singleton(tool_provider.ToolManager)
        tool_mgr.install_tool(get_singleton(submission.SubmitTool))
        tool_mgr.install_tool(get_singleton(submission.FailTool))
        tool_mgr.install_tool(get_singleton(run_control.CheckFilesTool))
        tool_mgr.install_tool(get_singleton(run_control.GetWorkTool))
        node_cfg = get_singleton(node_config.NodeConfig)
        if node_cfg.is_step_mode:
            tool_mgr.install_tool(get_singleton(run_control.AdvanceTool))

    # Contract: RunController.verification_checks - exposes session verification checks.
    @property
    def verification_checks(self) -> Sequence[node_config.VerificationCheck]:
        cfg = get_singleton(node_config.NodeConfig)
        return cfg.verification_checks

    # Contract: RunController.blame_targets_by_node - exposes per-node blame targets eligible for defect attribution.
    @property
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[file_alias.BoundFile]]:
        node_cfg = get_singleton(node_config.NodeConfig)
        return {
            node: set(bound_files)
            for node, bound_files in node_cfg.blame_targets_by_node.items()
        }

    # Contract: RunController.update_verification - updates and caches verification results alongside target file hashes sequentially when outdated.
    def update_verification(self) -> None:
        edit_mgr = get_singleton(file_editor.EditManager)
        node_cfg = get_singleton(node_config.NodeConfig)

        target_files: Set[file_alias.FileAlias] = set(node_cfg.read_write_files)
        if not target_files:
            target_files = set(node_cfg.read_only_files)

        current_hashes: dict[file_alias.FileAlias, file_editor.FileHash] = {}
        if target_files:
            for f in sorted(target_files, key=lambda x: str(x.relative_path)):
                current_hashes[f] = edit_mgr.file_hash(f)
        else:
            alias_mgr = get_singleton(file_alias.AliasManager)
            default_alias = alias_mgr.to_alias("")
            current_hashes[default_alias] = edit_mgr.file_hash(default_alias)

        if self._cached_hashes is not None and self._cached_hashes == current_hashes:
            self._is_unchanged = True
            return

        self._is_unchanged = False
        self._cached_hashes = dict(current_hashes)

        all_passed = True
        diag_parts: list[str] = []
        for check in self.verification_checks:
            check_passed, check_diag = check.verify()
            if not check_passed:
                all_passed = False
                if check_diag:
                    diag_parts.append(str(check_diag))

        self._passed = all_passed
        self._diagnostic_output = "\n".join(diag_parts).strip()


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        CheckFilesTool,
        keys=[CheckFilesTool, run_control.CheckFilesTool, InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        AdvanceTool,
        keys=[AdvanceTool, run_control.AdvanceTool, InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        GetWorkTool,
        keys=[GetWorkTool, run_control.GetWorkTool, InTier[AgentSessionTier]],
        tier=agent_session,
    )
    reg.register_singleton(
        RunController,
        keys=[RunController, run_control.RunController, InTier[AgentSessionTier]],
        tier=agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
