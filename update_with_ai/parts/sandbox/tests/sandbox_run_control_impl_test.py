# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-12T11:59:00Z
# CHANGE: Install advance tool and specify follow-up execution when guide step mode is active in get work tool
# CODE_HASH: b4b1e2912957
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Unit tests for sandbox_run_control_impl per its grounding specification."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib import (
    agent_file_alias,
    agent_node_config,
    agent_session,
)
from update_with_ai.parts.control.lib import control_coordinate
from update_with_ai.parts.dag.lib import dag_storage, dag_subgraph
from update_with_ai.parts.sandbox.lib import (
    sandbox_file_editor,
    sandbox_guide_delivery,
    sandbox_run_control,
    sandbox_submission,
    template_format,
    tool_provider,
)
from update_with_ai.parts.sandbox.lib.sandbox_run_control_impl import (
    AdvanceTool,
    CheckFilesTool,
    GetWorkTool,
    RunController,
    __initialize__,
)


def _make_node(unit: str = "unit_a", role: str = "dev") -> dag_storage.DagNode:
    return dag_storage.DagNode(
        unit_address=dag_storage.UnitAddress(unit),
        role_address=dag_storage.RoleAddress(role),
    )


def _make_file_alias(path: str) -> agent_file_alias.FileAlias:
    return agent_file_alias.FileAlias(agent_file_alias.RelativePath(path))


def _make_bound_file(
    path: str,
    owning_node: Optional[dag_storage.DagNode] = None,
) -> agent_file_alias.BoundFile:
    node = owning_node if owning_node is not None else _make_node(path.replace("/", "_").replace(".", "_"))
    return agent_file_alias.BoundFile(
        relative_path=agent_file_alias.RelativePath(path),
        workspace_path=agent_file_alias.file_paths.WorkspacePath(
            agent_file_alias.file_paths.PathString(f"/workspace/{path}")
        ),
        owning_node=node,
    )


def _bindings(d: Mapping[Any, Any]) -> Any:
    return d


def _make_read_write_file(
    path: str,
    owning_node: Optional[dag_storage.DagNode] = None,
) -> agent_file_alias.ReadWriteFile:
    node = owning_node if owning_node is not None else _make_node(path.replace("/", "_").replace(".", "_"))
    return agent_file_alias.ReadWriteFile(
        relative_path=agent_file_alias.RelativePath(path),
        workspace_path=agent_file_alias.file_paths.WorkspacePath(
            agent_file_alias.file_paths.PathString(f"/workspace/{path}")
        ),
        owning_node=node,
    )


@dataclass(frozen=True)
class MockVerificationResult:
    passed: bool
    diagnostic_output: str
    is_cached: bool = False


@dataclass(frozen=True)
class MockScheduledTask:
    node: dag_storage.DagNode
    task_prompt: str
    dependency_paths: Sequence[str]
    feedback_messages: Sequence[dag_storage.FeedbackMessage]


@dataclass(frozen=True)
class MockWorkSchedule:
    tasks: Sequence[MockScheduledTask]


class MockVerificationCheck:
    def __init__(self, passed: bool = True, diagnostic: str = "") -> None:
        self.passed = passed
        self.diagnostic = agent_node_config.VerificationDiagnostic(diagnostic)
        self.call_count = 0

    def verify(self) -> Tuple[bool, agent_node_config.VerificationDiagnostic]:
        self.call_count += 1
        return self.passed, self.diagnostic


class MockToolManager:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.installed_tools: Dict[tool_provider.ToolName, tool_provider.Tool] = {}

    def install_tool(self, tool: tool_provider.Tool) -> None:
        self.installed_tools[tool.name] = tool

    def execute_tool(
        self,
        name: tool_provider.ToolName,
        wire_parameter_bindings: Mapping[tool_provider.ParameterName, Any],
    ) -> tool_provider.ToolResponse:
        if name not in self.installed_tools:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Error: Unknown tool '{name}'."
                ),
            )
        tool = self.installed_tools[name]
        actual_bindings: Dict[tool_provider.ToolParameter[Any, Any], Any] = {}
        for param_name, wire_val in wire_parameter_bindings.items():
            if param_name not in tool.parameters:
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        f"Error: Unknown parameter '{param_name}'."
                    ),
                )
            param = tool.parameters[param_name]
            try:
                actual_bindings[param] = param.parameter_type.convert(wire_val)
            except (tool_provider.ParameterConversionError, ValueError, TypeError) as e:
                msg = getattr(e, "message", str(e))
                return tool_provider.ToolResponse(
                    is_failed=True,
                    is_terminated=False,
                    content=tool_provider.ToolResponseContent(
                        f"Error: Invalid argument for parameter '{param_name}': {msg}"
                    ),
                )
        return tool.execute_tool(actual_bindings)


class MockEditManager:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.has_modifications = False
        self.file_update_revision = sandbox_file_editor.FileUpdateRevision(0)
        self.last_read_or_edited_file: Optional[agent_file_alias.FileAlias] = None
        self._current_hash = sandbox_file_editor.FileHash("hash123")
        self.file_hashes: Dict[str, sandbox_file_editor.FileHash] = {}
        self.hashed_files: List[agent_file_alias.FileAlias] = []

    def set_file_hash(self, h: str, file: Optional[Any] = None) -> None:
        new_hash = sandbox_file_editor.FileHash(h)
        if file is not None:
            key = str(file.relative_path) if hasattr(file, "relative_path") else str(file)
            self.file_hashes[key] = new_hash
        else:
            self._current_hash = new_hash

    def record_file_read(self, file: agent_file_alias.FileAlias) -> None:
        self.last_read_or_edited_file = file

    def record_file_edit(self, file: agent_file_alias.ReadWriteFile) -> None:
        self.last_read_or_edited_file = file

    def file_hash(self, file: Any) -> sandbox_file_editor.FileHash:
        self.hashed_files.append(file)
        key = str(file.relative_path) if hasattr(file, "relative_path") else str(file)
        return self.file_hashes.get(key, self._current_hash)

    def can_write(self, path: Any) -> tool_provider.ToolResponse:
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent("OK"),
        )


class MockRoleDef:
    """Role configuration surface designating auditor roles."""

    def __init__(
        self,
        is_auditor: bool = False,
        audit_tag: Optional[str] = None,
        src_pattern: str = "",
    ) -> None:
        self.is_auditor = is_auditor
        self.audit_tag = audit_tag
        self.src_pattern = src_pattern


class MockRoleConfig:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.role = agent_node_config.RoleName("developer")
        self.nodes: List[dag_storage.DagNode] = []
        self.version = agent_node_config.ExecutionVersion(1)

    def set_role(self, role: agent_node_config.RoleName) -> None:
        self.role = role

    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        self.nodes = list(nodes)
        self.version = agent_node_config.ExecutionVersion(int(self.version) + 1)


class MockNodeConfig:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.read_only_files: Set[agent_file_alias.ReadOnlyFile] = set()
        self.read_write_files: Set[agent_file_alias.ReadWriteFile] = set()
        self.allows_step_mode = False
        self.is_step_mode = False
        self.guide_file: Optional[agent_file_alias.UnboundFile] = None
        self.templates: Mapping[agent_file_alias.BoundFile, agent_file_alias.FileContent] = {}
        self.template_parameters: Mapping[agent_node_config.TemplateParamKey, Any] = {}
        self.guide: Optional[agent_node_config.NodeGuide] = None
        self.blame_targets_by_node: Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]] = {}
        self.verification_checks: Sequence[agent_node_config.VerificationCheck] = []
        self.verification_checks_by_node: Mapping[dag_storage.DagNode, Sequence[agent_node_config.VerificationCheck]] = {}
        self.src_file_alias: Optional[agent_file_alias.RelativePath] = None
        self.src_file_alias_by_node: Mapping[dag_storage.DagNode, agent_file_alias.RelativePath] = {}
        self.verification_success_message: Optional[agent_node_config.VerificationSuccessMessage] = None
        self.feedback: Sequence[agent_node_config.NodeFeedback] = []
        self.per_node_info_by_node: Mapping[dag_storage.DagNode, agent_node_config.PerNodeInfo] = {}
        self.role_definitions: Dict[str, MockRoleDef] = {}



class MockGuideDelivery:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.guide: Optional[agent_node_config.NodeGuide] = None
        self.has_steps_remaining = False
        self.advance_step_response: Optional[tool_provider.ToolResponse] = None
        self.advance_step_calls: List[Tuple[bool, agent_node_config.VerificationDiagnostic]] = []
        self.recorded_primers: List[sandbox_guide_delivery.InitialPrimer] = []

    def initialize(self) -> None:
        pass

    def parse_guide(self, content: agent_file_alias.FileContent) -> agent_node_config.NodeGuide:
        return agent_node_config.NodeGuide(
            summary=agent_node_config.GuideSummary("Summary"),
            sections=[],
        )

    def record_initial_primer(self, primer: sandbox_guide_delivery.InitialPrimer) -> None:
        self.recorded_primers.append(primer)

    def advance_step(
        self, verification_passed: bool, failure_diagnostics: agent_node_config.VerificationDiagnostic
    ) -> Optional[tool_provider.ToolResponse]:
        self.advance_step_calls.append((verification_passed, failure_diagnostics))
        if self.advance_step_response is not None:
            return self.advance_step_response
        if not verification_passed:
            return tool_provider.ToolResponse(
                is_failed=True,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(f"Verification failure: {failure_diagnostics}"),
            )
        if self.guide and self.guide.sections:
            section = self.guide.sections[0]
            return tool_provider.ToolResponse(
                is_failed=False,
                is_terminated=False,
                content=tool_provider.ToolResponseContent(
                    f"Milestone Section {section.index}: {section.title}\n{section.content}"
                ),
            )
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent("Next milestone section delivered"),
        )


class MockDagStorage:
    tier = system

    def __init__(self) -> None:
        self.clean_nodes: Set[dag_storage.DagNode] = set()
        self.dirty_nodes: Set[dag_storage.DagNode] = set()
        self.messages: List[Tuple[dag_storage.DagNode, Any]] = []
        self.materialized_nodes: List[dag_storage.DagNode] = []

    def mark_node_clean(
        self, node: dag_storage.DagNode, change_description: Optional[Any] = None, *args: Any, **kwargs: Any
    ) -> None:
        self.clean_nodes.add(node)
        self.dirty_nodes.discard(node)

    def mark_node_dirty(self, node: dag_storage.DagNode, reason: Optional[str] = None) -> None:
        self.clean_nodes.discard(node)
        self.dirty_nodes.add(node)

    def mark_subgraph_clean(self, node: dag_storage.DagNode) -> None:
        self.clean_nodes.add(node)
        self.dirty_nodes.discard(node)

    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        return node in self.dirty_nodes or node not in self.clean_nodes

    def add_feedback_message(self, node: dag_storage.DagNode, message: Any) -> None:
        self.messages.append((node, message))
        self.clean_nodes.discard(node)
        self.dirty_nodes.add(node)

    def add_message(self, message: Any, to: dag_storage.DagNode) -> None:
        self.messages.append((to, message))
        self.clean_nodes.discard(to)
        self.dirty_nodes.add(to)

    def clear_messages(self, node: dag_storage.DagNode) -> None:
        self.messages = [m for m in self.messages if m[0] != node]

    def materialize_template(self, node: dag_storage.DagNode) -> None:
        self.materialized_nodes.append(node)

    def get_dependencies(self, node: dag_storage.DagNode) -> Set[Any]:
        return set()

    def get_messages(self, node: dag_storage.DagNode) -> Set[Any]:
        return {m[1] for m in self.messages if m[0] == node}


class MockSessionCoordinator:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.open_targets: List[dag_storage.DagNode] = []
        self.target_states: Dict[dag_storage.DagNode, control_coordinate.TargetState] = {}
        self.node_by_alias: Dict[Any, dag_storage.DagNode] = {}
        self.alias_by_node: Dict[dag_storage.DagNode, str] = {}
        self.dispatched_submit: Optional[Tuple[Any, ...]] = None
        self.dispatched_blame: Optional[Tuple[Any, ...]] = None
        self.dispatched_fail: Optional[Tuple[Any, ...]] = None
        self.verification_result: bool = True
        self.verification_diagnostic: str = ""
        self.is_cached: bool = False
        self.storage: Optional[MockDagStorage] = None
        self.role_config: Optional[MockRoleConfig] = None
        self.submit_outcome: Optional[control_coordinate.ControlDispatchOutcome] = None
        self.blame_outcome: Optional[control_coordinate.ControlDispatchOutcome] = None
        self.fail_outcome: Optional[control_coordinate.ControlDispatchOutcome] = None
        self.node_config: Optional[MockNodeConfig] = None

    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: Any,
        state: control_coordinate.TargetState = control_coordinate.TargetState.OPEN,
    ) -> None:
        alias_str = str(alias.relative_path) if hasattr(alias, "relative_path") else str(alias)
        if state == control_coordinate.TargetState.OPEN and node not in self.open_targets:
            self.open_targets.append(node)
        self.target_states[node] = state
        self.node_by_alias[alias_str] = node
        self.node_by_alias[alias] = node
        self.alias_by_node[node] = alias_str
        if self.role_config is not None and node not in self.role_config.nodes:
            self.role_config.set_nodes(list(self.role_config.nodes) + [node])

    def reset_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        self.open_targets = list(nodes)

    def resolve_default_target(self, last_accessed_file: Optional[Any] = None) -> Optional[dag_storage.DagNode]:
        return self.open_targets[0] if self.open_targets else None

    def get_node_for_alias(self, alias: Any) -> Optional[dag_storage.DagNode]:
        if hasattr(alias, "relative_path"):
            alias_str = str(alias.relative_path)
        else:
            alias_str = str(alias)
        return self.node_by_alias.get(alias_str) or self.node_by_alias.get(alias)

    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        return self.alias_by_node.get(node, "test_alias")

    def dispatch_get_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> Any:
        ready_nodes = []
        if subgraph is not None:
            ready_nodes = list(subgraph.next_ready_batch())
        tasks = []
        for n in ready_nodes:
            self.register_node(n, f"pkg/{n.unit_address}.py")
            if self.storage is not None:
                self.storage.materialize_template(n)
            tasks.append(
                MockScheduledTask(
                    node=n,
                    task_prompt="Work prompt",
                    dependency_paths=[],
                    feedback_messages=[],
                )
            )
        return MockWorkSchedule(tasks=tasks)

    def dispatch_check_files(self, target_alias: Optional[str] = None) -> Any:
        return MockVerificationResult(
            passed=self.verification_result,
            diagnostic_output=self.verification_diagnostic,
            is_cached=self.is_cached,
        )

    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> control_coordinate.ControlDispatchOutcome:
        self.dispatched_submit = (target_alias, change_summary, has_modifications)
        if self.submit_outcome is not None:
            return self.submit_outcome
        target = self.get_node_for_alias(target_alias) if target_alias else self.resolve_default_target()

        is_auditor = False
        if target is not None and self.node_config is not None:
            role_clean = str(target.role_address).split(":")[-1].strip().lower()
            role_def = self.node_config.role_definitions.get(role_clean)
            if role_def is not None:
                is_auditor = bool(
                    getattr(role_def, "is_auditor", False)
                    or getattr(role_def, "audit_tag", None)
                    or not getattr(role_def, "src_pattern", "")
                )

        summary_str = str(change_summary or "").strip()
        if is_auditor and summary_str:
            return control_coordinate.ControlDispatchOutcome(
                success=False,
                message="Error: Change summary is prohibited for audit nodes.",
                remaining_open_targets=list(self.open_targets),
            )
        if not is_auditor:
            if has_modifications and not summary_str:
                return control_coordinate.ControlDispatchOutcome(
                    success=False,
                    message="Error: Workspace files were modified, so change_summary must be provided.",
                    remaining_open_targets=list(self.open_targets),
                )
            if not has_modifications and summary_str:
                return control_coordinate.ControlDispatchOutcome(
                    success=False,
                    message="Error: Change summaries are not permitted when submitting without workspace file modifications.",
                    remaining_open_targets=list(self.open_targets),
                )
            if not has_modifications and self.node_config is not None:
                has_feedback = bool(getattr(self.node_config, "feedback", None))
                if target is not None and self.storage is not None:
                    node_msgs = self.storage.get_messages(target)
                    if any(isinstance(m, dag_storage.FeedbackMessage) for m in node_msgs):
                        has_feedback = True
                if (
                    not has_feedback
                    and target is not None
                    and hasattr(self.node_config, "per_node_info_by_node")
                    and self.node_config.per_node_info_by_node
                ):
                    info = self.node_config.per_node_info_by_node.get(target)
                    if info and getattr(info, "feedback", None):
                        has_feedback = True
                if has_feedback:
                    return control_coordinate.ControlDispatchOutcome(
                        success=False,
                        message="Error: Session feedback is present but no workspace files were modified.",
                        remaining_open_targets=list(self.open_targets),
                    )

        if target:
            self.target_states[target] = control_coordinate.TargetState.CLEAN
            if target in self.open_targets:
                self.open_targets.remove(target)
            if self.storage is not None:
                self.storage.mark_node_clean(target, change_summary)
        return control_coordinate.ControlDispatchOutcome(
            success=True, message="Submitted", remaining_open_targets=list(self.open_targets)
        )

    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        self.dispatched_blame = (source_alias, blame_target_alias, explanation)
        if self.blame_outcome is not None:
            return self.blame_outcome
        target = self.get_node_for_alias(source_alias) if source_alias else self.resolve_default_target()
        if target:
            self.target_states[target] = control_coordinate.TargetState.ATTRIBUTED
            if target in self.open_targets:
                self.open_targets.remove(target)
        if blame_target_alias and self.storage is not None:
            blamed_node = self.get_node_for_alias(blame_target_alias)
            if not blamed_node and hasattr(self, "node_config") and self.node_config:
                for targets in self.node_config.blame_targets_by_node.values():
                    for t in targets:
                        t_alias: Any = getattr(t, "alias", t)
                        if hasattr(t_alias, "relative_path") and str(t_alias.relative_path) == str(blame_target_alias):
                            blamed_node = getattr(t, "owning_node", None)
                            break
            if blamed_node:
                msg = dag_storage.FeedbackMessage(
                    content=dag_storage.MessageContent(explanation),
                    target=blamed_node,
                )
                self.storage.add_feedback_message(blamed_node, msg)
        return control_coordinate.ControlDispatchOutcome(
            success=True, message="Blamed", remaining_open_targets=list(self.open_targets)
        )

    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        self.dispatched_fail = (target_alias, explanation)
        target = self.get_node_for_alias(target_alias) if target_alias else self.resolve_default_target()
        if target:
            self.target_states[target] = control_coordinate.TargetState.FAILED
            if target in self.open_targets:
                self.open_targets.remove(target)
        return control_coordinate.ControlDispatchOutcome(
            success=True, message="Failed", remaining_open_targets=self.open_targets
        )


class MockDagSubgraph:
    tier = system

    def __init__(self) -> None:
        self.target: Optional[dag_storage.DagNode] = None
        self.complete = True
        self.ready_batch: List[dag_storage.DagNode] = []
        self.visited_batches: List[Sequence[dag_storage.DagNode]] = []

    def set_target(self, target: dag_storage.DagNode) -> None:
        self.target = target

    def is_complete(self) -> bool:
        return self.complete

    def next_ready_batch(self) -> Sequence[dag_storage.DagNode]:
        return self.ready_batch

    def record_visit(self, batch: Sequence[dag_storage.DagNode]) -> None:
        self.visited_batches.append(batch)




class MockAliasManager:
    tier = agent_session.agent_session

    @property
    def workspace_root(self) -> Any:
        return "/tmp/test_ws"

    @property
    def actual_type(self) -> type[agent_file_alias.FileAlias]:
        return agent_file_alias.FileAlias

    @property
    def wire_type(self) -> type[str]:
        return str

    def to_alias(self, path: str) -> agent_file_alias.FileAlias:
        return agent_file_alias.FileAlias(agent_file_alias.RelativePath(path))

    convert = to_alias

    def sanitize_text(
        self, text: agent_file_alias.UnsanitizedText
    ) -> agent_file_alias.SanitizedText:
        return agent_file_alias.SanitizedText(str(text))


class MockTemplateFormatter:
    tier = agent_session.agent_session

    def format_template(
        self,
        text: template_format.TemplateText,
        parameters: Mapping[template_format.TemplateKey, Any],
    ) -> template_format.FormattedText:
        return template_format.FormattedText(str(text))


class MockSubmissionTool:
    tier = agent_session.agent_session
    description = "Mock submission tool"
    parameters: Mapping[Any, Any] = {}

    def __init__(self, name: str) -> None:
        self.name = tool_provider.ToolName(name)

    def execute_tool(self, actual_parameter_bindings: Mapping[Any, Any]) -> tool_provider.ToolResponse:
        return tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent("Mock executed"),
        )


class SandboxRunControlImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        for name, key in (
            ("submit", sandbox_submission.SubmitTool),
            ("fail", sandbox_submission.FailTool),
            ("blame", sandbox_submission.BlameTool),
        ):
            self.registry.register_instance(
                MockSubmissionTool(name),
                keys=[key],
                tier=agent_session.agent_session,
            )
        self.mock_storage = MockDagStorage()
        self.registry.register_instance(
            self.mock_storage,
            keys=[dag_storage.DagStorage],
            tier=system,
        )
        self.mock_subgraph = MockDagSubgraph()
        self.registry.register_instance(
            self.mock_subgraph,
            keys=[dag_subgraph.DagSubgraph],
            tier=system,
        )
        self.mock_tool_manager = MockToolManager()
        self.registry.register_instance(
            self.mock_tool_manager,
            keys=[tool_provider.ToolManager],
            tier=agent_session.agent_session,
        )
        self.mock_edit_manager = MockEditManager()
        self.registry.register_instance(
            self.mock_edit_manager,
            keys=[sandbox_file_editor.EditManager],
            tier=agent_session.agent_session,
        )
        self.mock_node_config = MockNodeConfig()
        self.registry.register_instance(
            self.mock_node_config,
            keys=[agent_node_config.NodeConfig],
            tier=agent_session.agent_session,
        )
        self.mock_role_config = MockRoleConfig()
        self.registry.register_instance(
            self.mock_role_config,
            keys=[agent_node_config.RoleConfig],
            tier=agent_session.agent_session,
        )
        self.mock_guide_delivery = MockGuideDelivery()
        self.registry.register_instance(
            self.mock_guide_delivery,
            keys=[sandbox_guide_delivery.GuideDelivery],
            tier=agent_session.agent_session,
        )
        self.mock_session_coordinator = MockSessionCoordinator()
        self.mock_session_coordinator.storage = self.mock_storage
        self.mock_session_coordinator.node_config = self.mock_node_config
        self.mock_session_coordinator.role_config = self.mock_role_config
        self.registry.register_instance(
            self.mock_session_coordinator,
            keys=[control_coordinate.SessionCoordinator],
            tier=agent_session.agent_session,
        )
        self.mock_alias_manager = MockAliasManager()
        self.registry.register_instance(
            self.mock_alias_manager,
            keys=[
                agent_file_alias.AliasManager,
            ],
            tier=agent_session.agent_session,
        )
        self.mock_template_formatter = MockTemplateFormatter()
        self.registry.register_instance(
            self.mock_template_formatter,
            keys=[template_format.TemplateFormatter],
            tier=agent_session.agent_session,
        )

    def test_initialization(self) -> None:
        """CUJ: Verify initial component presence and singleton resolution."""
        self.assertIsNotNone(self.registry)
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            for cls in [
                AdvanceTool,
                CheckFilesTool,
                GetWorkTool,
                RunController,
            ]:
                instance = scope.get_singleton(cls)
                self.assertIsNotNone(instance)

    # -------------------------------------------------------------------------
    # CheckFilesTool Tests
    # -------------------------------------------------------------------------

    def test_check_files_tool_metadata(self) -> None:
        """Postcondition: Execute verification checks and present diagnostic outcomes."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(CheckFilesTool)
            self.assertEqual(tool.name, tool_provider.ToolName("check_files"))
            self.assertTrue(len(tool.description) > 0)

    def test_check_files_tool_passes_verification(self) -> None:
        """Postcondition: WHEN verification passes, MUST produce response presenting passing results."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        check = MockVerificationCheck(passed=True)
        self.mock_node_config.verification_checks = [check]
        self.mock_session_coordinator.verification_result = True
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(CheckFilesTool)
            response = tool.execute_tool({})
            self.assertFalse(response.is_failed)
            self.assertFalse(response.is_terminated)
            self.assertIsNotNone(response.content)

    def test_check_files_tool_fails_verification(self) -> None:
        """Postcondition: WHEN verification fails, MUST present sanitized diagnostic feedback alongside verification failure instructions."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        check = MockVerificationCheck(passed=False, diagnostic="SyntaxError: invalid syntax")
        self.mock_node_config.verification_checks = [check]
        self.mock_session_coordinator.verification_result = False
        self.mock_session_coordinator.verification_diagnostic = "SyntaxError: invalid syntax"
        self.mock_edit_manager.set_file_hash("hash_failing")
        failure_instructions = agent_node_config.VerificationFailureInstructions(
            "Review diagnostic output and fix the offending code."
        )
        self.mock_node_config.guide = agent_node_config.NodeGuide(
            summary=agent_node_config.GuideSummary("Overview"),
            sections=[],
            verification_failure=failure_instructions,
        )
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(CheckFilesTool)
            response = tool.execute_tool({})
            self.assertTrue(response.is_failed)
            self.assertIn("SyntaxError", str(response.content))
            self.assertIn(str(failure_instructions), str(response.content))

    def test_check_files_tool_unchanged_hashes(self) -> None:
        """Postcondition: WHEN target file hashes have not changed, MUST remind agent status is unchanged."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        check = MockVerificationCheck(passed=True)
        self.mock_node_config.verification_checks = [check]
        self.mock_session_coordinator.verification_result = True
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(CheckFilesTool)
            first_resp = tool.execute_tool({})
            self.assertFalse(first_resp.is_failed)
            self.mock_session_coordinator.is_cached = True
            second_resp = tool.execute_tool({})
            self.assertIsNotNone(second_resp.content)

    def test_check_files_tool_presents_configured_verification_success_message(self) -> None:
        """Postcondition: CheckFilesTool presenting configured verification success messages."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        check = MockVerificationCheck(passed=True)
        self.mock_node_config.verification_checks = [check]
        self.mock_session_coordinator.verification_result = True
        success_msg = agent_node_config.VerificationSuccessMessage("All checks passed successfully.")
        self.mock_node_config.verification_success_message = success_msg
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(CheckFilesTool)
            response = tool.execute_tool({})
            self.assertFalse(response.is_failed)
            self.assertFalse(response.is_terminated)
            self.assertIn("All checks passed successfully.", str(response.content))

    # -------------------------------------------------------------------------
    # AdvanceTool Tests
    # -------------------------------------------------------------------------

    def test_advance_tool_metadata(self) -> None:
        """Postcondition: Advance guide milestone gated by verification checks."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(AdvanceTool)
            self.assertEqual(tool.name, tool_provider.ToolName("advance"))
            self.assertTrue(len(tool.description) > 0)

    def test_advance_tool_failing_first_step_repeats_primer(self) -> None:
        """Postcondition: WHEN verification is failing on first step, MUST repeat primer and summary."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        guide = agent_node_config.NodeGuide(
            summary=agent_node_config.GuideSummary("Overview guide"),
            sections=[
                agent_node_config.StepSection(
                    index=agent_node_config.StepIndex(0),
                    title=agent_node_config.StepTitle("First Step"),
                    content=agent_node_config.StepContent("Do step 1"),
                )
            ],
        )
        self.mock_guide_delivery.guide = guide
        self.mock_guide_delivery.has_steps_remaining = True
        self.mock_node_config.is_step_mode = True
        self.mock_node_config.guide = guide
        self.mock_session_coordinator.verification_result = False
        self.mock_session_coordinator.verification_diagnostic = "First step failure"
        self.mock_node_config.verification_checks = [
            MockVerificationCheck(passed=False, diagnostic="First step failure")
        ]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(AdvanceTool)
            response = tool.execute_tool({})
            self.assertTrue(response.is_failed)

    def test_advance_tool_failing_specifies_check_files(self) -> None:
        """Postcondition: WHEN verification is failing, MUST remind agent to call check files and specify follow-up."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        guide = agent_node_config.NodeGuide(
            summary=agent_node_config.GuideSummary("Overview guide"),
            sections=[
                agent_node_config.StepSection(
                    index=agent_node_config.StepIndex(2),
                    title=agent_node_config.StepTitle("Later Step"),
                    content=agent_node_config.StepContent("Do later step"),
                )
            ],
        )
        self.mock_guide_delivery.guide = guide
        self.mock_guide_delivery.has_steps_remaining = True
        self.mock_node_config.is_step_mode = True
        self.mock_node_config.guide = guide
        self.mock_session_coordinator.verification_result = False
        self.mock_session_coordinator.verification_diagnostic = "Later failure"
        self.mock_node_config.verification_checks = [
            MockVerificationCheck(passed=False, diagnostic="Later failure")
        ]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(AdvanceTool)
            response = tool.execute_tool({})
            self.assertTrue(response.is_failed)
            self.assertIsNotNone(response.follow_up_tool_call)
            assert response.follow_up_tool_call is not None
            self.assertEqual(
                response.follow_up_tool_call.tool_name,
                tool_provider.ToolName("check_files"),
            )

    def test_advance_tool_delivering_next_milestone_section_when_verification_passes_and_guide_steps_remain(self) -> None:
        """Postcondition: AdvanceTool delivering the next milestone section when verification passes and guide steps remain."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        section = agent_node_config.StepSection(
            index=agent_node_config.StepIndex(1),
            title=agent_node_config.StepTitle("Step 1 Title"),
            content=agent_node_config.StepContent("Step 1 Content Instructions"),
        )
        guide = agent_node_config.NodeGuide(
            summary=agent_node_config.GuideSummary("Overview guide"),
            sections=[section],
        )
        self.mock_guide_delivery.guide = guide
        self.mock_guide_delivery.has_steps_remaining = True
        self.mock_node_config.is_step_mode = True
        self.mock_node_config.guide = guide
        self.mock_session_coordinator.verification_result = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        milestone_response = tool_provider.ToolResponse(
            is_failed=False,
            is_terminated=False,
            content=tool_provider.ToolResponseContent(
                "Milestone Section 1: Step 1 Title\nStep 1 Content Instructions"
            ),
        )
        self.mock_guide_delivery.advance_step_response = milestone_response
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(AdvanceTool)
            response = tool.execute_tool({})
            self.assertFalse(response.is_failed)
            self.assertFalse(response.is_terminated)
            self.assertEqual(response.content, milestone_response.content)
            self.assertIn("Step 1 Title", str(response.content))
            self.assertIn("Step 1 Content Instructions", str(response.content))
            self.assertEqual(len(self.mock_guide_delivery.advance_step_calls), 1)
            self.assertTrue(self.mock_guide_delivery.advance_step_calls[0][0])

    def test_advance_tool_passes_no_steps_modified(self) -> None:
        """Postcondition: WHEN verification passes, no steps remain, and files modified, MUST fail reminding to submit with summary."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_guide_delivery.has_steps_remaining = False
        self.mock_edit_manager.has_modifications = True
        self.mock_session_coordinator.verification_result = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(AdvanceTool)
            response = tool.execute_tool({})
            self.assertTrue(response.is_failed)
            combined = f"{response.content} {response.reminder or ''}".lower()
            self.assertIn("submit", combined)

    def test_advance_tool_passes_no_steps_unmodified(self) -> None:
        """Postcondition: WHEN verification passes, no steps remain, and no files modified, MUST specify follow-up submit."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_guide_delivery.has_steps_remaining = False
        self.mock_edit_manager.has_modifications = False
        self.mock_session_coordinator.verification_result = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(AdvanceTool)
            response = tool.execute_tool({})
            self.assertIsNotNone(response.follow_up_tool_call)
            assert response.follow_up_tool_call is not None
            self.assertEqual(
                response.follow_up_tool_call.tool_name,
                tool_provider.ToolName("submit"),
            )

    # -------------------------------------------------------------------------
    # GetWorkTool Tests
    # -------------------------------------------------------------------------

    def test_get_work_tool_metadata(self) -> None:
        """Postcondition: Inspect and pull pending work."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            self.assertEqual(tool.name, tool_provider.ToolName("get_work"))
            self.assertTrue(len(tool.description) > 0)
            self.assertEqual(len(tool.parameters), 0)

    def test_get_work_tool_fails_when_open_targets_remain(self) -> None:
        """Postcondition: WHEN open active nodes remain, MUST fail reminding to resolve open nodes."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            response = tool.execute_tool({})
            self.assertTrue(response.is_failed)

    def test_get_work_tool_idle_when_no_dirty_nodes(self) -> None:
        """Postcondition: WHEN no dirty nodes are ready, MUST produce an idle response."""
        self.mock_session_coordinator.open_targets = []
        self.mock_subgraph.ready_batch = []
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            response = tool.execute_tool({})
            self.assertFalse(response.is_failed)

    def test_get_work_tool_returns_primer_step_mode_inactive(self) -> None:
        """Postcondition: WHEN ready dirty nodes obtained and guide step inactive, MUST return task primer."""
        self.mock_session_coordinator.open_targets = []
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_subgraph.ready_batch = [node]
        self.mock_node_config.is_step_mode = False
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            response = tool.execute_tool({})
            self.assertFalse(response.is_failed)
            self.assertNotIn(tool_provider.ToolName("advance"), self.mock_tool_manager.installed_tools)

    def test_get_work_tool_returns_primer_step_mode_active(self) -> None:
        """Postcondition: WHEN ready dirty nodes obtained and guide step active, MUST return primer prompting advance and specify follow-up execution of advance tool."""
        self.mock_session_coordinator.open_targets = []
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_subgraph.ready_batch = [node]
        self.mock_node_config.is_step_mode = True
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            response = tool.execute_tool({})
            self.assertFalse(response.is_failed)
            self.assertIsNotNone(response.content)
            self.assertIn(tool_provider.ToolName("advance"), self.mock_tool_manager.installed_tools)
            self.assertIsNotNone(response.follow_up_tool_call)
            assert response.follow_up_tool_call is not None
            self.assertEqual(
                response.follow_up_tool_call.tool_name,
                tool_provider.ToolName("advance"),
            )
            combined = f"{response.content} {response.reminder or ''}".lower()
            self.assertIn("advance", combined)

    # -------------------------------------------------------------------------
    # RunController Tests
    # -------------------------------------------------------------------------

    def test_run_controller(self) -> None:
        """Postcondition: Track verification checks and update verification status."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            controller = scope.get_singleton(RunController)
            self.assertEqual(list(controller.verification_checks), [])
            controller.update_verification()

    def test_get_work_tool_installs_blame_when_blame_targets_exist(self) -> None:
        """Postcondition: WHEN ready dirty nodes obtained and blame targets exist, MUST install blame tool."""
        self.mock_session_coordinator.open_targets = []
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_subgraph.ready_batch = [node]
        self.mock_node_config.is_step_mode = False
        dep_node = _make_node("dep1", "lib")
        bound_target = _make_bound_file("dep1.py", owning_node=dep_node)
        self.mock_node_config.blame_targets_by_node = {node: {bound_target}}
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            response = tool.execute_tool({})
            self.assertFalse(response.is_failed)
            self.assertIn(tool_provider.ToolName("blame"), self.mock_tool_manager.installed_tools)

    def test_run_controller_initialize_registers_session_tools_into_tool_manager(self) -> None:
        """Postcondition: RunController.initialize registers outcome tools into ToolManager, conditionally including advance."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            controller = scope.get_singleton(RunController)

            # Step mode inactive: submit, fail, check_files, get_work installed; blame and advance omitted
            self.mock_node_config.is_step_mode = False
            self.mock_node_config.allows_step_mode = False
            self.mock_tool_manager.installed_tools.clear()
            controller.initialize()

            self.assertIn(tool_provider.ToolName("submit"), self.mock_tool_manager.installed_tools)
            self.assertIn(tool_provider.ToolName("fail"), self.mock_tool_manager.installed_tools)
            self.assertIn(tool_provider.ToolName("check_files"), self.mock_tool_manager.installed_tools)
            self.assertIn(tool_provider.ToolName("get_work"), self.mock_tool_manager.installed_tools)
            self.assertNotIn(tool_provider.ToolName("blame"), self.mock_tool_manager.installed_tools)
            self.assertNotIn(tool_provider.ToolName("advance"), self.mock_tool_manager.installed_tools)

            # Step mode active: advance is conditionally installed
            self.mock_node_config.is_step_mode = True
            self.mock_node_config.allows_step_mode = True
            self.mock_node_config.guide = agent_node_config.NodeGuide(
                summary=agent_node_config.GuideSummary("Guide"),
                sections=[],
            )
            self.mock_tool_manager.installed_tools.clear()
            controller.initialize()

            self.assertIn(tool_provider.ToolName("submit"), self.mock_tool_manager.installed_tools)
            self.assertIn(tool_provider.ToolName("fail"), self.mock_tool_manager.installed_tools)
            self.assertIn(tool_provider.ToolName("check_files"), self.mock_tool_manager.installed_tools)
            self.assertIn(tool_provider.ToolName("get_work"), self.mock_tool_manager.installed_tools)
            self.assertNotIn(tool_provider.ToolName("blame"), self.mock_tool_manager.installed_tools)
            self.assertIn(tool_provider.ToolName("advance"), self.mock_tool_manager.installed_tools)

    def test_run_controller_caching(self) -> None:
        """Postcondition: Caches verification evaluations and skips re-execution when file hashes unchanged."""
        check = MockVerificationCheck(passed=True)
        self.mock_node_config.verification_checks = [check]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            controller = scope.get_singleton(RunController)
            controller.update_verification()
            initial_count = check.call_count
            controller.update_verification()
            self.assertEqual(check.call_count, initial_count)
            self.mock_edit_manager.set_file_hash("hash999")
            controller.update_verification()
            self.assertGreater(check.call_count, initial_count)


    # -------------------------------------------------------------------------
    # Tool Parameter Wire Decoding Tests
    # -------------------------------------------------------------------------

    def test_get_work_tool_is_argument_free(self) -> None:
        """Postcondition: GetWorkTool is an argument-free tool."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            self.assertEqual(len(tool.parameters), 0)

    def test_tool_parameter_actual_type_properties_and_schema(self) -> None:
        """Postcondition: Tool parameters declare correct actual_type properties."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            gw_tool = scope.get_singleton(GetWorkTool)
            self.assertEqual(len(gw_tool.parameters), 0)
            cf_tool = scope.get_singleton(CheckFilesTool)
            self.assertIsInstance(cf_tool.parameters, Mapping)
            adv_tool = scope.get_singleton(AdvanceTool)
            self.assertIsInstance(adv_tool.parameters, Mapping)

    def test_tool_manager_wire_dispatch_across_run_control_tools(self) -> None:
        """Postcondition: Dispatch tool execution via wire parameter bindings across run control tools."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        self.mock_session_coordinator.verification_result = True

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            for cls in [CheckFilesTool, AdvanceTool, GetWorkTool]:
                tool = scope.get_singleton(cls)
                self.mock_tool_manager.install_tool(tool)

            resp = self.mock_tool_manager.execute_tool(tool_provider.ToolName("check_files"), {})
            self.assertFalse(resp.is_failed)

            self.mock_guide_delivery.has_steps_remaining = True
            resp = self.mock_tool_manager.execute_tool(tool_provider.ToolName("advance"), {})
            self.assertFalse(resp.is_failed)

            self.mock_session_coordinator.open_targets = []
            self.mock_subgraph.ready_batch = []
            resp = self.mock_tool_manager.execute_tool(
                tool_provider.ToolName("get_work"),
                {},
            )
            self.assertFalse(resp.is_failed)


if __name__ == "__main__":
    unittest.main()
