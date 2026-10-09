# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:46:30Z
# LAST_CHANGED: 2026-10-09T22:40:00Z
# CHANGE: Allow clean submit of unmodified implementation nodes
# CODE_HASH: e61b138311e9
# QA_AUDIT: 2026-10-09T21:46:30Z
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
from update_with_ai.parts.dag.lib import dag_config, dag_storage, dag_subgraph
from update_with_ai.parts.sandbox.lib import (
    sandbox,
    sandbox_file_editor,
    sandbox_guide_delivery,
    sandbox_run_control,
    template_format,
    tool_provider,
)
from update_with_ai.parts.sandbox.lib.sandbox_run_control_impl import (
    AdvanceTool,
    BlameTool,
    CheckFilesTool,
    FailTool,
    GetWorkTool,
    RunController,
    SubmitTool,
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
        self.role_definitions: Dict[str, Any] = {}



class MockGuideDelivery:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.guide: Optional[agent_node_config.NodeGuide] = None
        self.has_steps_remaining = False
        self.advance_step_response: Optional[tool_provider.ToolResponse] = None
        self.advance_step_calls: List[Tuple[bool, agent_node_config.VerificationDiagnostic]] = []
        self.recorded_primers: List[sandbox_guide_delivery.InitialPrimer] = []

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


class MockDagConfig:
    tier = system

    @property
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        return dag_config.NodeVisitLimit(10)

    @property
    def batch_size(self) -> dag_config.BatchSize:
        return dag_config.BatchSize(2)


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

    def convert(self, wire_value: str) -> agent_file_alias.FileAlias:
        if not isinstance(wire_value, str):
            raise tool_provider.ParameterConversionError(
                tool_provider.ConversionErrorMessage("Wire value must be a string")
            )
        return agent_file_alias.FileAlias(agent_file_alias.RelativePath(wire_value))

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


class MockSandbox:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.has_modifications = False


class SandboxRunControlImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
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
        self.mock_dag_config = MockDagConfig()
        self.registry.register_instance(
            self.mock_dag_config,
            keys=[dag_config.DagConfig],
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
        self.mock_sandbox = MockSandbox()
        self.registry.register_instance(
            self.mock_sandbox,
            keys=[sandbox.Sandbox],
            tier=agent_session.agent_session,
        )
        self.mock_alias_manager = MockAliasManager()
        self.registry.register_instance(
            self.mock_alias_manager,
            keys=[
                agent_file_alias.AliasManager,
                tool_provider.ParameterType[agent_file_alias.FileAlias, str],
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
                BlameTool,
                CheckFilesTool,
                FailTool,
                GetWorkTool,
                RunController,
                SubmitTool,
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
        self.mock_sandbox.has_modifications = True
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
        self.mock_sandbox.has_modifications = False
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
    # SubmitTool Tests
    # -------------------------------------------------------------------------

    def test_submit_tool_metadata(self) -> None:
        """Postcondition: Submit target changes and enforce change summary when modified."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            self.assertEqual(tool.name, tool_provider.ToolName("submit"))
            self.assertTrue(len(tool.description) > 0)
            self.assertIn(tool.target_parameter.name, tool.parameters)
            self.assertIn(tool.change_summary_parameter.name, tool.parameters)

    def test_submit_tool_fails_when_guide_steps_remain(self) -> None:
        """Postcondition: WHEN guide step mode is active and steps remain, MUST fail specifying advance."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_node_config.is_step_mode = True
        self.mock_guide_delivery.has_steps_remaining = True
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            response = tool.execute_tool({})
            self.assertTrue(response.is_failed)
            self.assertIsNotNone(response.follow_up_tool_call)
            assert response.follow_up_tool_call is not None
            self.assertEqual(
                response.follow_up_tool_call.tool_name,
                tool_provider.ToolName("advance"),
            )

    def test_submit_tool_fails_when_verification_failing(self) -> None:
        """Postcondition: WHEN verification is failing, MUST fail specifying follow-up check_files."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.verification_result = False
        self.mock_session_coordinator.verification_diagnostic = "Syntax error"
        self.mock_node_config.is_step_mode = False
        self.mock_node_config.verification_checks = [
            MockVerificationCheck(passed=False, diagnostic="Syntax error")
        ]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            response = tool.execute_tool({})
            self.assertTrue(response.is_failed)
            self.assertIsNotNone(response.follow_up_tool_call)
            assert response.follow_up_tool_call is not None
            self.assertEqual(
                response.follow_up_tool_call.tool_name,
                tool_provider.ToolName("check_files"),
            )

    def test_submit_tool_fails_when_modified_without_summary(self) -> None:
        """Postcondition: WHEN files were modified and change summary is omitted, MUST fail."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_sandbox.has_modifications = True
        self.mock_edit_manager.has_modifications = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            response = tool.execute_tool({})
            self.assertTrue(response.is_failed)

    def test_submit_tool_fails_when_unmodified_with_summary(self) -> None:
        """Postcondition: WHEN workspace files were not modified and change summary is provided, MUST fail reminding agent that change summaries are not permitted when submitting without workspace file modifications."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_sandbox.has_modifications = False
        self.mock_edit_manager.has_modifications = False
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Unneeded summary"),
            }
            response = tool.execute_tool(bindings)
            self.assertTrue(response.is_failed)
            combined = f"{response.content} {response.reminder or ''}".lower()
            self.assertTrue(
                "not permitted" in combined
                or "without" in combined
                or "modification" in combined
            )

    def test_submit_tool_fails_auditor_with_summary(self) -> None:
        """Postcondition: WHEN target is an auditor node and change summary is provided, MUST fail reminding agent that change summary is prohibited for audit nodes."""
        node = _make_node("unit1", role="auditor")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_role_config.role = agent_node_config.RoleName("auditor")
        self.mock_sandbox.has_modifications = True
        self.mock_edit_manager.has_modifications = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Summary for audit"),
            }
            response = tool.execute_tool(bindings)
            self.assertTrue(response.is_failed)
            combined = f"{response.content} {response.reminder or ''}".lower()
            self.assertTrue("prohibited" in combined or "audit" in combined)

    def test_submit_tool_fails_when_feedback_present_without_modifications(self) -> None:
        """Postcondition: WHEN session feedback is present and no files were modified, MUST fail."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_sandbox.has_modifications = False
        self.mock_edit_manager.has_modifications = False
        self.mock_node_config.feedback = [agent_node_config.NodeFeedback("Fix regression")]
        self.mock_storage.add_feedback_message(
            node,
            dag_storage.FeedbackMessage(
                content=dag_storage.MessageContent("Fix regression"), target=node
            ),
        )
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
            }
            response = tool.execute_tool(_bindings(bindings))
            self.assertTrue(response.is_failed)

    def test_submit_tool_failing_when_per_node_configuration_specifies_active_feedback_on_unmodified_target(self) -> None:
        """Postcondition: SubmitTool failing when per-node configuration specifies active feedback on an unmodified target."""
        node = _make_node("unit_per_node_feedback")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit_per_node_feedback.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_sandbox.has_modifications = False
        self.mock_edit_manager.has_modifications = False
        self.mock_node_config.feedback = []
        self.mock_storage.clear_messages(node)
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        self.mock_node_config.per_node_info_by_node = {
            node: agent_node_config.PerNodeInfo(
                read_only_files=set(),
                read_write_files=set(),
                templates={},
                template_parameters={},
                allows_step_mode=False,
                guide_file=None,
                guide=None,
                blame_targets=set(),
                verification_checks=[MockVerificationCheck(passed=True)],
                src_file_alias=None,
                verification_success_message=None,
                feedback=[agent_node_config.NodeFeedback("Resolve reviewer defect before submitting")],
            )
        }
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            response = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_per_node_feedback.py"),
            }))
            self.assertTrue(response.is_failed)
            self.assertFalse(response.is_terminated)
            self.assertTrue(len(str(response.content)) > 0)
            self.assertNotIn(node, self.mock_storage.clean_nodes)
            self.assertIsNone(self.mock_session_coordinator.dispatched_submit)

    def test_submit_tool_succeeds_when_initial_implementation_without_modifications(self) -> None:
        """Postcondition: WHEN an initial implementation change is assigned and no files were modified, MUST succeed without change summary."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_sandbox.has_modifications = False
        self.mock_edit_manager.has_modifications = False
        self.mock_storage.add_message(
            dag_storage.ChangeMessage(
                content=dag_storage.MessageContent("Initial implementation required")
            ),
            to=node,
        )
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
            }
            response = tool.execute_tool(_bindings(bindings))
            self.assertFalse(response.is_failed)
            self.assertIn(node, self.mock_storage.clean_nodes)

    def test_submit_tool_differentiating_message_variants_when_enforcing_initial_implementation_modification_constraints(self) -> None:
        """Postcondition: SubmitTool differentiating message variants (including non-change feedback, empty descriptions, and audit notifications) when enforcing modification constraints."""
        self.mock_sandbox.has_modifications = False
        self.mock_edit_manager.has_modifications = False
        self.mock_session_coordinator.verification_result = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)

            # 1. Initial implementation change message variant: MUST succeed when unmodified without change summary
            node_init = _make_node("unit_init")
            self.mock_storage.mark_node_dirty(node_init)
            self.mock_session_coordinator.register_node(node_init, "pkg/unit_init.py")
            self.mock_storage.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent("Initial implementation required")
                ),
                to=node_init,
            )
            resp_init = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit_init.py")}))
            self.assertFalse(resp_init.is_failed)
            self.assertIn(node_init, self.mock_storage.clean_nodes)

            # 2. Empty description change message variant: MUST succeed when unmodified without change summary
            node_empty = _make_node("unit_empty")
            self.mock_storage.mark_node_dirty(node_empty)
            self.mock_session_coordinator.register_node(node_empty, "pkg/unit_empty.py")
            self.mock_storage.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent("")
                ),
                to=node_empty,
            )
            resp_empty = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit_empty.py")}))
            self.assertFalse(resp_empty.is_failed)
            self.assertIn(node_empty, self.mock_storage.clean_nodes)

            # Whitespace-only description change message variant: MUST also succeed when unmodified without change summary
            node_ws = _make_node("unit_ws")
            self.mock_storage.mark_node_dirty(node_ws)
            self.mock_session_coordinator.register_node(node_ws, "pkg/unit_ws.py")
            self.mock_storage.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent("   \n\t  ")
                ),
                to=node_ws,
            )
            resp_ws = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit_ws.py")}))
            self.assertFalse(resp_ws.is_failed)
            self.assertIn(node_ws, self.mock_storage.clean_nodes)

            # 3. Non-change feedback variant (FeedbackMessage and session feedback): MUST fail when unmodified
            node_fb = _make_node("unit_fb")
            self.mock_storage.mark_node_dirty(node_fb)
            self.mock_session_coordinator.register_node(node_fb, "pkg/unit_fb.py")
            self.mock_storage.add_feedback_message(
                node_fb,
                dag_storage.FeedbackMessage(
                    content=dag_storage.MessageContent("Downstream defect: regression observed"),
                    target=node_fb,
                ),
            )
            self.mock_node_config.feedback = [agent_node_config.NodeFeedback("Fix regression")]
            resp_fb = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit_fb.py")}))
            self.assertTrue(resp_fb.is_failed)

            # 4. Audit notification variant: MUST succeed when unmodified without change summary
            node_audit = _make_node("unit_audit", role="auditor")
            self.mock_storage.mark_node_dirty(node_audit)
            self.mock_session_coordinator.register_node(node_audit, "pkg/unit_audit.py")
            self.mock_role_config.role = agent_node_config.RoleName("auditor")
            self.mock_storage.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent("Audit notification: verify implementation")
                ),
                to=node_audit,
            )
            resp_audit = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit_audit.py")}))
            self.assertFalse(resp_audit.is_failed)
            self.assertIn(node_audit, self.mock_storage.clean_nodes)

            # 5. Upstream dependency change variant: MUST succeed when unmodified without change summary
            self.mock_role_config.role = agent_node_config.RoleName("developer")
            self.mock_node_config.feedback = []
            node_dep = _make_node("unit_dep")
            self.mock_storage.mark_node_dirty(node_dep)
            self.mock_session_coordinator.register_node(node_dep, "pkg/unit_dep.py")
            self.mock_storage.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent("Upstream dependency changed")
                ),
                to=node_dep,
            )
            resp_dep = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit_dep.py")}))
            self.assertFalse(resp_dep.is_failed)
            self.assertIn(node_dep, self.mock_storage.clean_nodes)

    def test_submit_tool_differentiating_message_variants_in_graph_storage_for_non_auditor_targets_without_active_session_feedback(self) -> None:
        """Postcondition: SubmitTool differentiating message variants in graph storage (non-change defect feedback and audit messages) for non-auditor targets without active session feedback when evaluating initial implementation modification constraints."""
        self.mock_sandbox.has_modifications = False
        self.mock_edit_manager.has_modifications = False
        self.mock_session_coordinator.verification_result = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        self.mock_role_config.role = agent_node_config.RoleName("developer")
        self.mock_node_config.feedback = []

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)

            # 1. Non-change defect feedback in graph storage for non-auditor target without active session feedback: MUST fail when unmodified
            node_defect = _make_node("unit_non_auditor_defect", role="developer")
            self.mock_storage.mark_node_dirty(node_defect)
            self.mock_session_coordinator.register_node(node_defect, "pkg/unit_non_auditor_defect.py")
            self.mock_storage.add_feedback_message(
                node_defect,
                dag_storage.FeedbackMessage(
                    content=dag_storage.MessageContent("Downstream defect: regression observed"),
                    target=node_defect,
                ),
            )
            resp_defect = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit_non_auditor_defect.py")}))
            self.assertTrue(resp_defect.is_failed)

            # 2. Audit message in graph storage for non-auditor target without active session feedback: MUST succeed when unmodified without change summary
            node_audit = _make_node("unit_non_auditor_audit", role="developer")
            self.mock_storage.mark_node_dirty(node_audit)
            self.mock_session_coordinator.register_node(node_audit, "pkg/unit_non_auditor_audit.py")
            self.mock_storage.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent("Audit notification: verified implementation")
                ),
                to=node_audit,
            )
            resp_audit = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit_non_auditor_audit.py")}))
            self.assertFalse(resp_audit.is_failed)
            self.assertIn(node_audit, self.mock_storage.clean_nodes)

            # 3. Initial implementation change message in graph storage for non-auditor target without active session feedback: MUST succeed when unmodified without change summary
            node_init = _make_node("unit_non_auditor_init", role="developer")
            self.mock_storage.mark_node_dirty(node_init)
            self.mock_session_coordinator.register_node(node_init, "pkg/unit_non_auditor_init.py")
            self.mock_storage.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent("Initial implementation required")
                ),
                to=node_init,
            )
            resp_init = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit_non_auditor_init.py")}))
            self.assertFalse(resp_init.is_failed)
            self.assertIn(node_init, self.mock_storage.clean_nodes)

            # 4. Empty description change message in graph storage for non-auditor target without active session feedback: MUST succeed when unmodified without change summary
            node_empty = _make_node("unit_non_auditor_empty", role="developer")
            self.mock_storage.mark_node_dirty(node_empty)
            self.mock_session_coordinator.register_node(node_empty, "pkg/unit_non_auditor_empty.py")
            self.mock_storage.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent("")
                ),
                to=node_empty,
            )
            resp_empty = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit_non_auditor_empty.py")}))
            self.assertFalse(resp_empty.is_failed)
            self.assertIn(node_empty, self.mock_storage.clean_nodes)

            # 5. Upstream dependency change in graph storage for non-auditor target without active session feedback: MUST succeed when unmodified without change summary
            node_dep = _make_node("unit_non_auditor_dep", role="developer")
            self.mock_storage.mark_node_dirty(node_dep)
            self.mock_session_coordinator.register_node(node_dep, "pkg/unit_non_auditor_dep.py")
            self.mock_storage.add_message(
                dag_storage.ChangeMessage(
                    content=dag_storage.MessageContent("Upstream dependency changed")
                ),
                to=node_dep,
            )
            resp_dep = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit_non_auditor_dep.py")}))
            self.assertFalse(resp_dep.is_failed)
            self.assertIn(node_dep, self.mock_storage.clean_nodes)

    def test_submit_tool_succeeds_with_modifications_and_summary(self) -> None:
        """Postcondition: MUST mark resolve target clean in storage and current turn."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_sandbox.has_modifications = True
        self.mock_edit_manager.has_modifications = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Implemented feature"),
            }
            response = tool.execute_tool(bindings)
            self.assertFalse(response.is_failed)
            self.assertTrue(response.is_terminated)
            self.assertIn(node, self.mock_storage.clean_nodes)

    def test_submit_tool_succeeds_unmodified_without_summary(self) -> None:
        """Postcondition: WHEN unedited target passes verification, MUST submit without summary."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_sandbox.has_modifications = False
        self.mock_edit_manager.has_modifications = False
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
            }
            response = tool.execute_tool(_bindings(bindings))
            self.assertFalse(response.is_failed)
            self.assertTrue(response.is_terminated)
            self.assertIn(node, self.mock_storage.clean_nodes)

    def test_submit_tool_terminating_response_when_all_resolved_and_non_terminating_when_open_remain(self) -> None:
        """Postcondition: WHEN all active nodes resolved MUST terminate, WHEN other open remain MUST not terminate."""
        node1 = _make_node("unit1")
        node2 = _make_node("unit2")
        self.mock_storage.mark_node_dirty(node1)
        self.mock_storage.mark_node_dirty(node2)
        self.mock_session_coordinator.register_node(node1, "pkg/unit1.py")
        self.mock_session_coordinator.register_node(node2, "pkg/unit2.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_sandbox.has_modifications = False
        self.mock_edit_manager.has_modifications = False
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)

            # Submitting first node leaves node2 open -> non-terminating
            resp1 = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit1.py")}))
            self.assertFalse(resp1.is_failed)
            self.assertFalse(resp1.is_terminated)

            # Submitting second node resolves all nodes -> terminating
            resp2 = tool.execute_tool(_bindings({tool.target_parameter: _make_file_alias("pkg/unit2.py")}))
            self.assertFalse(resp2.is_failed)
            self.assertTrue(resp2.is_terminated)

    def test_submit_tool_validating_role_definitions_designating_auditor_nodes_across_auditor_flags_tags_or_restricted_writable_file_patterns(self) -> None:
        """Postcondition: SubmitTool validating role definitions designating auditor nodes across auditor flags, tags, or restricted writable file patterns against supplied change summaries."""
        self.mock_session_coordinator.verification_result = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        self.mock_sandbox.has_modifications = True
        self.mock_edit_manager.has_modifications = True

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)

            # 1. Auditor node designated via auditor flag (is_auditor=True or RoleName("auditor"))
            node_flag = _make_node("unit_flag", role="auditor_flag_role")
            self.mock_storage.mark_node_dirty(node_flag)
            self.mock_session_coordinator.register_node(node_flag, "pkg/unit_flag.py")
            self.mock_role_config.role = agent_node_config.RoleName("auditor_flag_role")
            self.mock_node_config.role_definitions["auditor_flag_role"] = MockRoleDef(
                is_auditor=True, audit_tag=None, src_pattern="{unit_dir}/lib/{unit_name}.py"
            )
            # Supplying change summary MUST fail with reminder that summary is prohibited for audit nodes
            resp_flag_with_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_flag.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Audit review summary"),
            }))
            self.assertTrue(resp_flag_with_sum.is_failed)
            self.assertIsNotNone(resp_flag_with_sum.reminder)
            assert resp_flag_with_sum.reminder is not None
            self.assertTrue(
                "prohibited" in resp_flag_with_sum.reminder.lower()
                or "audit" in resp_flag_with_sum.reminder.lower()
            )
            # Omitting change summary MUST succeed
            resp_flag_no_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_flag.py"),
            }))
            self.assertFalse(resp_flag_no_sum.is_failed)
            self.assertIn(node_flag, self.mock_storage.clean_nodes)

            # Also verify standard auditor role name flag
            node_auditor_name = _make_node("unit_auditor_name", role="auditor")
            self.mock_storage.mark_node_dirty(node_auditor_name)
            self.mock_session_coordinator.register_node(node_auditor_name, "pkg/unit_auditor_name.py")
            self.mock_role_config.role = agent_node_config.RoleName("auditor")
            resp_name_with_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_auditor_name.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Summary"),
            }))
            self.assertTrue(resp_name_with_sum.is_failed)
            self.assertIsNotNone(resp_name_with_sum.reminder)
            assert resp_name_with_sum.reminder is not None
            resp_name_no_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_auditor_name.py"),
            }))
            self.assertFalse(resp_name_no_sum.is_failed)
            self.assertIn(node_auditor_name, self.mock_storage.clean_nodes)

            # 2. Auditor node designated via audit tag (audit_tag="QA_AUDIT" or role address with audit tag)
            node_tag = _make_node("unit_tag", role="qa_audit")
            self.mock_storage.mark_node_dirty(node_tag)
            self.mock_session_coordinator.register_node(node_tag, "pkg/unit_tag.py")
            self.mock_role_config.role = agent_node_config.RoleName("qa_audit")
            self.mock_node_config.role_definitions["qa_audit"] = MockRoleDef(
                is_auditor=False, audit_tag="QA_AUDIT", src_pattern="{unit_dir}/lib/{unit_name}.py"
            )
            resp_tag_with_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_tag.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("QA Audit notes"),
            }))
            self.assertTrue(resp_tag_with_sum.is_failed)
            self.assertIsNotNone(resp_tag_with_sum.reminder)
            assert resp_tag_with_sum.reminder is not None
            self.assertTrue(
                "prohibited" in resp_tag_with_sum.reminder.lower()
                or "audit" in resp_tag_with_sum.reminder.lower()
            )
            resp_tag_no_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_tag.py"),
            }))
            self.assertFalse(resp_tag_no_sum.is_failed)
            self.assertIn(node_tag, self.mock_storage.clean_nodes)

            # 3. Auditor node designated via restricted writable file patterns (src_pattern="" or empty read_write_files)
            node_restricted = _make_node("unit_restricted", role="reviewer")
            self.mock_storage.mark_node_dirty(node_restricted)
            self.mock_session_coordinator.register_node(node_restricted, "pkg/unit_restricted.py")
            self.mock_role_config.role = agent_node_config.RoleName("reviewer")
            self.mock_node_config.role_definitions["reviewer"] = MockRoleDef(
                is_auditor=False, audit_tag=None, src_pattern=""
            )
            self.mock_node_config.read_write_files = set()
            resp_restr_with_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_restricted.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Reviewer summary"),
            }))
            self.assertTrue(resp_restr_with_sum.is_failed)
            self.assertIsNotNone(resp_restr_with_sum.reminder)
            resp_restr_no_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_restricted.py"),
            }))
            self.assertFalse(resp_restr_no_sum.is_failed)
            self.assertIn(node_restricted, self.mock_storage.clean_nodes)

            # 4. Non-auditor role with normal writable file pattern requires change summary when files modified
            node_dev = _make_node("unit_dev", role="developer")
            self.mock_storage.mark_node_dirty(node_dev)
            self.mock_session_coordinator.register_node(node_dev, "pkg/unit_dev.py")
            self.mock_role_config.role = agent_node_config.RoleName("developer")
            self.mock_node_config.role_definitions["developer"] = MockRoleDef(
                is_auditor=False, audit_tag=None, src_pattern="{unit_dir}/lib/{unit_name}.py"
            )
            self.mock_node_config.read_write_files = {
                _make_read_write_file("pkg/unit_dev.py")
            }
            # Omission fails
            resp_dev_no_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_dev.py"),
            }))
            self.assertTrue(resp_dev_no_sum.is_failed)
            # Providing summary succeeds
            resp_dev_with_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_dev.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Feature changes"),
            }))
            self.assertFalse(resp_dev_with_sum.is_failed)
            self.assertIn(node_dev, self.mock_storage.clean_nodes)

    def test_submit_tool_attaching_change_summary_reminders_when_submission_outcomes_fail_due_to_change_summary_requirements(self) -> None:
        """Postcondition: SubmitTool attaching change summary reminders when submission outcomes fail due to change summary requirements."""
        self.mock_session_coordinator.verification_result = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)

            # 1. Files modified + change summary omitted: MUST fail attaching change summary reminder
            node_mod = _make_node("unit_mod")
            self.mock_storage.mark_node_dirty(node_mod)
            self.mock_session_coordinator.register_node(node_mod, "pkg/unit_mod.py")
            self.mock_role_config.role = agent_node_config.RoleName("developer")
            self.mock_sandbox.has_modifications = True
            self.mock_edit_manager.has_modifications = True
            resp_no_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_mod.py"),
            }))
            self.assertTrue(resp_no_sum.is_failed)
            self.assertIsNotNone(resp_no_sum.reminder)
            assert resp_no_sum.reminder is not None
            rem_mod = resp_no_sum.reminder.lower()
            self.assertTrue(
                "change summary" in rem_mod or "change_summary" in rem_mod,
                f"Expected change summary reminder, got: {resp_no_sum.reminder}",
            )

            # 2. Workspace files NOT modified + change summary provided: MUST fail reminding agent that change summaries are not permitted without modifications
            node_unmod = _make_node("unit_unmod")
            self.mock_storage.mark_node_dirty(node_unmod)
            self.mock_session_coordinator.register_node(node_unmod, "pkg/unit_unmod.py")
            self.mock_role_config.role = agent_node_config.RoleName("developer")
            self.mock_sandbox.has_modifications = False
            self.mock_edit_manager.has_modifications = False
            resp_unmod_with_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_unmod.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Unnecessary summary"),
            }))
            self.assertTrue(resp_unmod_with_sum.is_failed)
            self.assertIsNotNone(resp_unmod_with_sum.reminder)
            assert resp_unmod_with_sum.reminder is not None
            rem_unmod = resp_unmod_with_sum.reminder.lower()
            self.assertTrue(
                "not permitted" in rem_unmod or "without" in rem_unmod or "workspace file modifications" in rem_unmod,
                f"Expected reminder that summaries are not permitted without modifications, got: {resp_unmod_with_sum.reminder}",
            )

            # 3. Auditor node + change summary provided: MUST fail reminding agent that change summary is prohibited for audit nodes
            node_audit = _make_node("unit_audit_node", role="auditor")
            self.mock_storage.mark_node_dirty(node_audit)
            self.mock_session_coordinator.register_node(node_audit, "pkg/unit_audit_node.py")
            self.mock_role_config.role = agent_node_config.RoleName("auditor")
            self.mock_sandbox.has_modifications = False
            self.mock_edit_manager.has_modifications = False
            resp_audit_with_sum = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_audit_node.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Audit change summary"),
            }))
            self.assertTrue(resp_audit_with_sum.is_failed)
            self.assertIsNotNone(resp_audit_with_sum.reminder)
            assert resp_audit_with_sum.reminder is not None
            rem_audit = resp_audit_with_sum.reminder.lower()
            self.assertTrue(
                "prohibited" in rem_audit or "audit" in rem_audit,
                f"Expected reminder that change summary is prohibited for audit nodes, got: {resp_audit_with_sum.reminder}",
            )

    def test_submit_tool_handling_rejected_coordinator_submission_outcomes_reporting_change_summary_requirements(self) -> None:
        """Postcondition: SubmitTool handling rejected coordinator submission outcomes on dispatched submissions that report change summary requirements, verifying failure responses."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        self.mock_sandbox.has_modifications = True
        self.mock_edit_manager.has_modifications = True

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)

            # 1. Dispatched submission with modifications and change summary: Coordinator rejects reporting change summary requirements
            self.mock_session_coordinator.submit_outcome = control_coordinate.ControlDispatchOutcome(
                success=False,
                message="Submission rejected by coordinator: change summary does not meet required specifications",
                remaining_open_targets=[node],
            )
            resp_disp_mod = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Implemented feature updates"),
            }))
            self.assertTrue(resp_disp_mod.is_failed)
            self.assertFalse(resp_disp_mod.is_terminated)
            self.assertTrue(len(str(resp_disp_mod.content)) > 0)
            self.assertIsNotNone(self.mock_session_coordinator.dispatched_submit)
            assert self.mock_session_coordinator.dispatched_submit is not None
            self.assertEqual(self.mock_session_coordinator.dispatched_submit[0], "pkg/unit1.py")
            self.assertNotIn(node, self.mock_storage.clean_nodes)

            # 2. Dispatched submission without modifications and without change summary: Coordinator rejects reporting change summary requirements
            self.mock_sandbox.has_modifications = False
            self.mock_edit_manager.has_modifications = False
            self.mock_session_coordinator.dispatched_submit = None
            self.mock_session_coordinator.submit_outcome = control_coordinate.ControlDispatchOutcome(
                success=False,
                message="Submission rejected by coordinator: change summary required by repository policy",
                remaining_open_targets=[node],
            )
            resp_disp_unmod = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
            }))
            self.assertTrue(resp_disp_unmod.is_failed)
            self.assertFalse(resp_disp_unmod.is_terminated)
            self.assertTrue(len(str(resp_disp_unmod.content)) > 0)
            self.assertIsNotNone(self.mock_session_coordinator.dispatched_submit)
            assert self.mock_session_coordinator.dispatched_submit is not None
            self.assertEqual(self.mock_session_coordinator.dispatched_submit[0], "pkg/unit1.py")
            self.assertNotIn(node, self.mock_storage.clean_nodes)

            # 3. Dispatched submission on auditor target without change summary: Coordinator rejects reporting change summary requirements
            node_audit = _make_node("unit_audit_node", role="auditor")
            self.mock_storage.mark_node_dirty(node_audit)
            self.mock_session_coordinator.register_node(node_audit, "pkg/unit_audit_node.py")
            self.mock_role_config.role = agent_node_config.RoleName("auditor")
            self.mock_session_coordinator.dispatched_submit = None
            self.mock_session_coordinator.submit_outcome = control_coordinate.ControlDispatchOutcome(
                success=False,
                message="Submission rejected by coordinator: change summary prohibited for audit nodes",
                remaining_open_targets=[node_audit],
            )
            resp_disp_audit = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_audit_node.py"),
            }))
            self.assertTrue(resp_disp_audit.is_failed)
            self.assertFalse(resp_disp_audit.is_terminated)
            self.assertTrue(len(str(resp_disp_audit.content)) > 0)
            self.assertIsNotNone(self.mock_session_coordinator.dispatched_submit)
            assert self.mock_session_coordinator.dispatched_submit is not None
            self.assertEqual(self.mock_session_coordinator.dispatched_submit[0], "pkg/unit_audit_node.py")
            self.assertNotIn(node_audit, self.mock_storage.clean_nodes)

    def test_submit_tool_attaching_change_summary_reminders_when_coordinator_rejection_outcomes_explicitly_report_change_summary_requirements(self) -> None:
        """Postcondition: SubmitTool attaching change summary reminders when coordinator rejection outcomes explicitly report change_summary requirements."""
        node = _make_node("unit_csr")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit_csr.py")
        self.mock_session_coordinator.verification_result = True
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        self.mock_sandbox.has_modifications = True
        self.mock_edit_manager.has_modifications = True

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)

            # 1. Outcome explicitly reports change_summary requirements -> MUST attach change summary reminder
            self.mock_session_coordinator.submit_outcome = control_coordinate.ControlDispatchOutcome(
                success=False,
                message="Submission rejected: change_summary is required when files are modified",
                remaining_open_targets=[node],
            )
            resp = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_csr.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Modified files"),
            }))
            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertTrue(len(str(resp.content)) > 0)
            self.assertIsNotNone(resp.reminder)
            assert resp.reminder is not None
            rem = resp.reminder.lower()
            self.assertTrue(
                "change summary" in rem or "change_summary" in rem,
                f"Expected change summary reminder when coordinator outcome explicitly reports change_summary, got: {resp.reminder}",
            )
            self.assertIsNotNone(self.mock_session_coordinator.dispatched_submit)
            self.assertNotIn(node, self.mock_storage.clean_nodes)

            # 2. Outcome does NOT report change_summary requirements -> does NOT attach reminder
            self.mock_session_coordinator.submit_outcome = control_coordinate.ControlDispatchOutcome(
                success=False,
                message="Submission rejected: internal coordinator error",
                remaining_open_targets=[node],
            )
            resp_no_rem = tool.execute_tool(_bindings({
                tool.target_parameter: _make_file_alias("pkg/unit_csr.py"),
                tool.change_summary_parameter: sandbox_run_control.ChangeSummary("Modified files"),
            }))
            self.assertTrue(resp_no_rem.is_failed)
            self.assertFalse(resp_no_rem.is_terminated)
            self.assertTrue(len(str(resp_no_rem.content)) > 0)
            self.assertIsNone(resp_no_rem.reminder)

    # -------------------------------------------------------------------------
    # FailTool Tests
    # -------------------------------------------------------------------------

    def test_fail_tool_metadata(self) -> None:
        """Postcondition: Record failure reason and terminate session."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(FailTool)
            self.assertEqual(tool.name, tool_provider.ToolName("fail"))
            self.assertTrue(len(tool.description) > 0)
            self.assertIn(tool.target_parameter.name, tool.parameters)
            self.assertIn(tool.explanation_parameter.name, tool.parameters)

    def test_fail_tool_execution(self) -> None:
        """Postcondition: MUST mark active node as failed and terminate run."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(FailTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.explanation_parameter: sandbox_run_control.FailureExplanation("Fatal error encountered"),
            }
            response = tool.execute_tool(bindings)
            self.assertTrue(response.is_failed)
            self.assertTrue(response.is_terminated)
            self.assertEqual(
                self.mock_session_coordinator.target_states[node],
                control_coordinate.TargetState.FAILED,
            )

    # -------------------------------------------------------------------------
    # BlameTool Tests
    # -------------------------------------------------------------------------

    def test_blame_tool_metadata(self) -> None:
        """Postcondition: Attribute defect to upstream contract."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            self.assertEqual(tool.name, tool_provider.ToolName("blame"))
            self.assertTrue(len(tool.description) > 0)
            self.assertIn(tool.target_parameter.name, tool.parameters)
            self.assertIn(tool.blame_target_parameter.name, tool.parameters)
            self.assertIn(tool.explanation_parameter.name, tool.parameters)

    def test_blame_tool_fails_invalid_blame_target(self) -> None:
        """Postcondition: WHEN blame target does not match configured target, MUST fail listing available targets."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_node_config.blame_targets_by_node = {
            node: {_make_bound_file("pkg/upstream.py")}
        }
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.blame_target_parameter: _make_file_alias("pkg/wrong.py"),
                tool.explanation_parameter: sandbox_run_control.BlameExplanation("Defect"),
            }
            response = tool.execute_tool(bindings)
            self.assertTrue(response.is_failed)
            self.assertIn("pkg/upstream.py", str(response.content))

    def test_blame_tool_fails_multiline_explanation(self) -> None:
        """Postcondition: WHEN explanation contains newlines, MUST fail reminding it must be single paragraph."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_node_config.blame_targets_by_node = {
            node: {_make_bound_file("pkg/upstream.py")}
        }
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.blame_target_parameter: _make_file_alias("pkg/upstream.py"),
                tool.explanation_parameter: sandbox_run_control.BlameExplanation("Line one\nLine two"),
            }
            response = tool.execute_tool(bindings)
            self.assertTrue(response.is_failed)

    def test_blame_tool_succeeds_and_records_defect(self) -> None:
        """Postcondition: MUST record defect feedback for blamed target via dag_storage and mark attributed."""
        node = _make_node("unit1")
        upstream_node = _make_node("upstream_unit")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.register_node(upstream_node, "pkg/upstream.py")
        bound = _make_bound_file("pkg/upstream.py", owning_node=upstream_node)
        self.mock_node_config.blame_targets_by_node = {
            node: {bound}
        }
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.blame_target_parameter: _make_file_alias("pkg/upstream.py"),
                tool.explanation_parameter: sandbox_run_control.BlameExplanation("Interface specification is defective"),
            }
            response = tool.execute_tool(bindings)
            self.assertFalse(response.is_failed)
            self.assertEqual(
                self.mock_session_coordinator.target_states[node],
                control_coordinate.TargetState.ATTRIBUTED,
            )

    def test_blame_tool_attributing_defect_feedback_when_blame_target_node_is_not_pre_registered(self) -> None:
        """Postcondition: BlameTool attributing defect feedback when the blame target node is not pre-registered."""
        node = _make_node("unit1")
        upstream_node = _make_node("upstream_unregistered")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        # upstream_node is NOT registered with mock_session_coordinator.register_node
        bound = _make_bound_file("pkg/upstream_unregistered.py", owning_node=upstream_node)
        self.mock_node_config.blame_targets_by_node = {
            node: {bound}
        }
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.blame_target_parameter: _make_file_alias("pkg/upstream_unregistered.py"),
                tool.explanation_parameter: sandbox_run_control.BlameExplanation("Interface specification is defective"),
            }
            response = tool.execute_tool(bindings)
            self.assertFalse(response.is_failed)
            self.assertEqual(
                self.mock_session_coordinator.target_states[node],
                control_coordinate.TargetState.ATTRIBUTED,
            )
            self.assertTrue(
                any(n == upstream_node for n, _ in self.mock_storage.messages),
                "Expected defect feedback recorded for unregistered upstream node",
            )

    def test_blame_tool_defaults_to_single_blame_target(self) -> None:
        """Postcondition: WHEN blame target is omitted in single-target context, MUST default to configured target."""
        node = _make_node("unit1")
        upstream_node = _make_node("upstream_unit")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.register_node(upstream_node, "pkg/upstream.py")
        bound = _make_bound_file("pkg/upstream.py", owning_node=upstream_node)
        self.mock_node_config.blame_targets_by_node = {
            node: {bound}
        }
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.explanation_parameter: sandbox_run_control.BlameExplanation("Interface specification is defective"),
            }
            response = tool.execute_tool(bindings)
            self.assertFalse(response.is_failed)
            self.assertEqual(
                self.mock_session_coordinator.target_states[node],
                control_coordinate.TargetState.ATTRIBUTED,
            )
            self.assertEqual(
                self.mock_session_coordinator.dispatched_blame,
                ("pkg/unit1.py", "pkg/upstream.py", "Interface specification is defective"),
            )
            self.assertIn(upstream_node, [m[0] for m in self.mock_storage.messages])

    def test_blame_tool_fails_omitted_target_in_multi_target_context(self) -> None:
        """Postcondition: WHEN blame target is omitted in multi-target context, MUST fail listing available blame targets."""
        node = _make_node("unit1")
        upstream1 = _make_node("upstream1")
        upstream2 = _make_node("upstream2")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.register_node(upstream1, "pkg/upstream1.py")
        self.mock_session_coordinator.register_node(upstream2, "pkg/upstream2.py")
        bound1 = _make_bound_file("pkg/upstream1.py", owning_node=upstream1)
        bound2 = _make_bound_file("pkg/upstream2.py", owning_node=upstream2)
        self.mock_node_config.blame_targets_by_node = {
            node: {bound1, bound2}
        }
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.explanation_parameter: sandbox_run_control.BlameExplanation("Defect"),
            }
            response = tool.execute_tool(bindings)
            self.assertTrue(response.is_failed)
            content = str(response.content)
            self.assertTrue("pkg/upstream1.py" in content or "pkg/upstream2.py" in content)

    def test_blame_tool_fails_when_no_active_node_exists(self) -> None:
        """Postcondition: BlameTool error handling when no active node exists."""
        self.mock_session_coordinator.open_targets = []
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            bindings = {
                tool.explanation_parameter: sandbox_run_control.BlameExplanation("Defect"),
            }
            response = tool.execute_tool(_bindings(bindings))
            self.assertTrue(response.is_failed)

    def test_blame_tool_fails_when_active_node_has_no_configured_blame_targets(self) -> None:
        """Postcondition: BlameTool error handling when an active node has no configured blame targets."""
        node = _make_node("unit1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_node_config.blame_targets_by_node = {node: set()}
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.explanation_parameter: sandbox_run_control.BlameExplanation("Defect"),
            }
            response = tool.execute_tool(bindings)
            self.assertTrue(response.is_failed)

    def test_blame_tool_fails_when_blame_dispatch_fails(self) -> None:
        """Postcondition: BlameTool error handling when blame dispatch fails."""
        node = _make_node("unit1")
        upstream = _make_node("upstream1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.register_node(upstream, "pkg/upstream1.py")
        bound = _make_bound_file("pkg/upstream1.py", owning_node=upstream)
        self.mock_node_config.blame_targets_by_node = {node: {bound}}
        self.mock_session_coordinator.blame_outcome = control_coordinate.ControlDispatchOutcome(
            success=False, message="Blame dispatch failed", remaining_open_targets=[node]
        )
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            bindings = {
                tool.target_parameter: _make_file_alias("pkg/unit1.py"),
                tool.blame_target_parameter: _make_file_alias("pkg/upstream1.py"),
                tool.explanation_parameter: sandbox_run_control.BlameExplanation("Defect"),
            }
            response = tool.execute_tool(bindings)
            self.assertTrue(response.is_failed)
            self.assertIn("Blame dispatch failed", str(response.content))

    # -------------------------------------------------------------------------
    # GetWorkTool Tests
    # -------------------------------------------------------------------------

    def test_get_work_tool_metadata(self) -> None:
        """Postcondition: Inspect and pull pending work."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            self.assertEqual(tool.name, tool_provider.ToolName("get_work"))
            self.assertTrue(len(tool.description) > 0)
            self.assertIn(tool.max_batch_size_parameter.name, tool.parameters)

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

    def test_run_controller_initialize_registers_session_tools_into_tool_manager(self) -> None:
        """Postcondition: RunController.initialize registers outcome tools into ToolManager, conditionally including advance."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            controller = scope.get_singleton(RunController)

            # Step mode inactive: submit, fail, check_files, get_work, blame installed; advance omitted
            self.mock_node_config.is_step_mode = False
            self.mock_node_config.allows_step_mode = False
            self.mock_tool_manager.installed_tools.clear()
            controller.initialize()

            self.assertIn(tool_provider.ToolName("submit"), self.mock_tool_manager.installed_tools)
            self.assertIn(tool_provider.ToolName("fail"), self.mock_tool_manager.installed_tools)
            self.assertIn(tool_provider.ToolName("check_files"), self.mock_tool_manager.installed_tools)
            self.assertIn(tool_provider.ToolName("get_work"), self.mock_tool_manager.installed_tools)
            self.assertIn(tool_provider.ToolName("blame"), self.mock_tool_manager.installed_tools)
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
            self.assertIn(tool_provider.ToolName("blame"), self.mock_tool_manager.installed_tools)
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

    def test_run_controller_incorporating_declared_source_file_aliases_and_per_node_target_file_sets_into_cached_verification_file_hash_evaluations(self) -> None:
        """Postcondition: RunController incorporating declared source file aliases and per-node target file sets into cached verification file hash evaluations."""
        node = _make_node("unit1")
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_role_config.set_nodes([node])
        src_alias = agent_file_alias.RelativePath("pkg/src_declared.py")
        self.mock_node_config.src_file_alias_by_node = {node: src_alias}
        src_file_alias = agent_file_alias.FileAlias(src_alias)
        self.mock_edit_manager.set_file_hash("hash_declared_v1", file=src_file_alias)

        # Per-node target file set
        target_file_a = _make_read_write_file("pkg/target_a.py")
        target_file_b = _make_read_write_file("pkg/target_b.py")
        target_alias_a = agent_file_alias.FileAlias(target_file_a.relative_path)
        target_alias_b = agent_file_alias.FileAlias(target_file_b.relative_path)
        self.mock_edit_manager.set_file_hash("hash_target_a_v1", file=target_alias_a)
        self.mock_edit_manager.set_file_hash("hash_target_b_v1", file=target_alias_b)

        last_accessed = _make_file_alias("pkg/last_accessed.py")
        self.mock_edit_manager.last_read_or_edited_file = last_accessed
        self.mock_edit_manager.set_file_hash("hash_accessed_v1", file=last_accessed)

        check = MockVerificationCheck(passed=True)
        self.mock_node_config.verification_checks = [check]

        self.mock_node_config.read_write_files = {target_file_a, target_file_b}
        self.mock_node_config.per_node_info_by_node = {
            node: agent_node_config.PerNodeInfo(
                read_only_files=set(),
                read_write_files={target_file_a, target_file_b},
                templates={},
                template_parameters={},
                allows_step_mode=False,
                guide_file=None,
                guide=None,
                blame_targets=set(),
                verification_checks=[check],
                src_file_alias=src_alias,
                verification_success_message=None,
                feedback=[],
            )
        }

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            controller = scope.get_singleton(RunController)
            controller.update_verification()
            self.assertEqual(check.call_count, 1)
            self.assertIn(src_file_alias, self.mock_edit_manager.hashed_files)

            # Unchanged declared source file alias and per-node target file sets reuses cache
            controller.update_verification()
            self.assertEqual(check.call_count, 1)

            # Modifying hash of a file in per-node target file set invalidates cache and triggers check execution
            self.mock_edit_manager.set_file_hash("hash_target_a_v2", file=target_alias_a)
            controller.update_verification()
            self.assertEqual(check.call_count, 2)

            # Modifying hash of another file in per-node target file set invalidates cache and triggers check execution
            self.mock_edit_manager.set_file_hash("hash_target_b_v2", file=target_alias_b)
            controller.update_verification()
            self.assertEqual(check.call_count, 3)

            # Modifying hash of declared source file alias invalidates cache and triggers check execution
            self.mock_edit_manager.set_file_hash("hash_declared_v2", file=src_file_alias)
            controller.update_verification()
            self.assertEqual(check.call_count, 4)

            # Modifying hash of last accessed file invalidates cache and triggers check execution
            self.mock_edit_manager.set_file_hash("hash_accessed_v2", file=last_accessed)
            controller.update_verification()
            self.assertEqual(check.call_count, 5)

            # Adding a second node with its own per-node target file set and declared source alias
            node2 = _make_node("unit2")
            self.mock_session_coordinator.register_node(node2, "pkg/unit2.py")
            self.mock_role_config.set_nodes([node, node2])
            src_alias2 = agent_file_alias.RelativePath("pkg/src_per_node.py")
            src_file_alias2 = agent_file_alias.FileAlias(src_alias2)
            target_file_2 = _make_read_write_file("pkg/unit2_target.py")
            target_alias_2 = agent_file_alias.FileAlias(target_file_2.relative_path)
            self.mock_edit_manager.set_file_hash("hash_per_node_v1", file=src_file_alias2)
            self.mock_edit_manager.set_file_hash("hash_node2_target_v1", file=target_alias_2)
            self.mock_node_config.per_node_info_by_node = {
                node: self.mock_node_config.per_node_info_by_node[node],
                node2: agent_node_config.PerNodeInfo(
                    read_only_files=set(),
                    read_write_files={target_file_2},
                    templates={},
                    template_parameters={},
                    allows_step_mode=False,
                    guide_file=None,
                    guide=None,
                    blame_targets=set(),
                    verification_checks=[check],
                    src_file_alias=src_alias2,
                    verification_success_message=None,
                    feedback=[],
                ),
            }
            controller.update_verification()
            self.assertEqual(check.call_count, 6)
            self.assertIn(src_file_alias2, self.mock_edit_manager.hashed_files)

            # Modifying target file in second node's per-node target file set invalidates cache
            self.mock_edit_manager.set_file_hash("hash_node2_target_v2", file=target_alias_2)
            controller.update_verification()
            self.assertEqual(check.call_count, 7)

    def test_run_controller_incorporating_declared_source_file_alias_attributes_on_node_configuration_into_cached_verification_file_hash_evaluations(self) -> None:
        """Postcondition: RunController incorporating declared source file alias attributes on node configuration into cached verification file hash evaluations."""
        node = _make_node("unit_src_alias")
        self.mock_session_coordinator.register_node(node, "pkg/unit_src_alias.py")
        self.mock_role_config.set_nodes([node])
        src_alias = agent_file_alias.RelativePath("pkg/src_declared_alias.py")
        src_file_alias = agent_file_alias.FileAlias(src_alias)
        self.mock_edit_manager.set_file_hash("hash_src_v1", file=src_file_alias)
        self.mock_edit_manager.set_file_hash("hash_node_v1", file=_make_file_alias("pkg/unit_src_alias.py"))

        check = MockVerificationCheck(passed=True)
        self.mock_node_config.verification_checks = [check]

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            controller = scope.get_singleton(RunController)

            # 1. Attribute src_file_alias on node configuration
            self.mock_node_config.src_file_alias = src_alias
            self.mock_node_config.src_file_alias_by_node = {}
            controller.update_verification()
            self.assertEqual(check.call_count, 1)
            self.assertIn(src_file_alias, self.mock_edit_manager.hashed_files)

            # Verification outcome is cached when declared source file alias hash is unchanged
            controller.update_verification()
            self.assertEqual(check.call_count, 1)

            # Modifying declared source file alias invalidates cache and triggers check re-evaluation
            self.mock_edit_manager.set_file_hash("hash_src_v2", file=src_file_alias)
            controller.update_verification()
            self.assertEqual(check.call_count, 2)

            # 2. Attribute src_file_alias_by_node on node configuration
            self.mock_node_config.src_file_alias = None
            self.mock_node_config.src_file_alias_by_node = {node: src_alias}
            self.mock_edit_manager.set_file_hash("hash_src_v3", file=src_file_alias)
            controller.update_verification()
            self.assertEqual(check.call_count, 3)

            # Cached when unchanged
            controller.update_verification()
            self.assertEqual(check.call_count, 3)

            # Invalidate when hash changes
            self.mock_edit_manager.set_file_hash("hash_src_v4", file=src_file_alias)
            controller.update_verification()
            self.assertEqual(check.call_count, 4)

    # -------------------------------------------------------------------------
    # Tool Parameter Wire Decoding Tests
    # -------------------------------------------------------------------------

    def test_submit_tool_wire_parameter_decoding(self) -> None:
        """Postcondition: SubmitTool parameter wire decoding converts target and change summary wire values."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            target_param = tool.target_parameter
            self.assertEqual(target_param.parameter_type.wire_type, str)
            self.assertEqual(target_param.parameter_type.actual_type, agent_file_alias.FileAlias)
            converted_target = target_param.parameter_type.convert("pkg/unit1.py")
            self.assertIsInstance(converted_target, agent_file_alias.FileAlias)
            self.assertEqual(str(converted_target.relative_path), "pkg/unit1.py")

            summary_param = tool.change_summary_parameter
            self.assertEqual(summary_param.parameter_type.wire_type, str)
            converted_summary = summary_param.parameter_type.convert("Added feature implementation")
            self.assertEqual(str(converted_summary), "Added feature implementation")

    def test_fail_tool_wire_parameter_decoding(self) -> None:
        """Postcondition: FailTool parameter wire decoding converts target and failure explanation wire values."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(FailTool)
            target_param = tool.target_parameter
            converted_target = target_param.parameter_type.convert("pkg/unit1.py")
            self.assertIsInstance(converted_target, agent_file_alias.FileAlias)
            self.assertEqual(str(converted_target.relative_path), "pkg/unit1.py")

            explanation_param = tool.explanation_parameter
            self.assertEqual(explanation_param.parameter_type.wire_type, str)
            converted_explanation = explanation_param.parameter_type.convert("Fatal test suite failure")
            self.assertEqual(str(converted_explanation), "Fatal test suite failure")

    def test_blame_tool_wire_parameter_decoding(self) -> None:
        """Postcondition: BlameTool parameter wire decoding converts target, blame target, and blame explanation wire values."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(BlameTool)
            target_param = tool.target_parameter
            converted_target = target_param.parameter_type.convert("pkg/unit1.py")
            self.assertIsInstance(converted_target, agent_file_alias.FileAlias)
            self.assertEqual(str(converted_target.relative_path), "pkg/unit1.py")

            blame_target_param = tool.blame_target_parameter
            self.assertEqual(blame_target_param.parameter_type.wire_type, str)
            converted_blame = blame_target_param.parameter_type.convert("pkg/upstream.py")
            self.assertIsInstance(converted_blame, agent_file_alias.FileAlias)
            self.assertEqual(str(converted_blame.relative_path), "pkg/upstream.py")

            explanation_param = tool.explanation_parameter
            self.assertEqual(explanation_param.parameter_type.wire_type, str)
            converted_explanation = explanation_param.parameter_type.convert("Defective contract specification")
            self.assertEqual(str(converted_explanation), "Defective contract specification")

    def test_get_work_tool_wire_parameter_decoding(self) -> None:
        """Postcondition: GetWorkTool parameter wire decoding converts max batch size wire value."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            batch_param = tool.max_batch_size_parameter
            self.assertEqual(batch_param.parameter_type.wire_type, int)
            converted_batch = batch_param.parameter_type.convert(5)
            assert converted_batch is not None
            self.assertEqual(int(converted_batch), 5)

    def test_optional_change_summary_wire_conversion_returning_empty_bindings_for_blank_wire_inputs(self) -> None:
        """Postcondition: optional change summary wire conversion returning empty bindings for blank wire inputs."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(SubmitTool)
            param_type = tool.change_summary_parameter.parameter_type

            # Empty string produces empty binding (None)
            self.assertIsNone(param_type.convert(""))

            # Whitespace strings produce empty binding (None)
            self.assertIsNone(param_type.convert("   "))
            self.assertIsNone(param_type.convert("\t\n  \r\n"))

            # None wire input produces empty binding (None)
            self.assertIsNone(param_type.convert(None))  # type: ignore[arg-type]

            # Non-blank wire inputs produce ChangeSummary instances
            converted = param_type.convert("Implemented new feature")
            self.assertEqual(converted, sandbox_run_control.ChangeSummary("Implemented new feature"))
            self.assertEqual(str(converted), "Implemented new feature")

    def test_tool_parameter_wire_decoding_conversion_error(self) -> None:
        """Postcondition: WHEN wire value cannot be converted, MUST handle ParameterConversionError."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            tool = scope.get_singleton(GetWorkTool)
            batch_param = tool.max_batch_size_parameter
            with self.assertRaises((tool_provider.ParameterConversionError, ValueError, TypeError)):
                batch_param.parameter_type.convert("not_an_int")  # type: ignore[arg-type]

    def test_tool_parameter_actual_type_properties_and_optional_wire_value_conversion_across_run_control_tools(self) -> None:
        """Postcondition: Tool parameter actual type properties and optional wire value conversion across run control tools."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            # SubmitTool: parameters actual_type properties + optional wire conversion
            submit_tool = scope.get_singleton(SubmitTool)
            self.assertIn(tool_provider.ParameterName("target"), submit_tool.parameters)
            self.assertIn(tool_provider.ParameterName("change_summary"), submit_tool.parameters)
            self.assertEqual(submit_tool.target_parameter.name, tool_provider.ParameterName("target"))
            self.assertTrue(len(str(submit_tool.target_parameter.description)) > 0)
            self.assertIsInstance(submit_tool.target_parameter.is_required, bool)
            self.assertEqual(submit_tool.target_parameter.parameter_type.actual_type, agent_file_alias.FileAlias)
            self.assertEqual(submit_tool.target_parameter.parameter_type.wire_type, str)

            self.assertEqual(submit_tool.change_summary_parameter.name, tool_provider.ParameterName("change_summary"))
            self.assertTrue(len(str(submit_tool.change_summary_parameter.description)) > 0)
            self.assertIsInstance(submit_tool.change_summary_parameter.is_required, bool)
            self.assertEqual(submit_tool.change_summary_parameter.parameter_type.actual_type, sandbox_run_control.ChangeSummary)
            self.assertEqual(submit_tool.change_summary_parameter.parameter_type.wire_type, str)

            t_alias = submit_tool.target_parameter.parameter_type.convert("pkg/mod.py")
            self.assertIsInstance(t_alias, agent_file_alias.FileAlias)
            self.assertEqual(str(t_alias.relative_path), "pkg/mod.py")
            s_val = submit_tool.change_summary_parameter.parameter_type.convert("Summary text")
            self.assertEqual(str(s_val), "Summary text")
            self.assertIsNone(submit_tool.change_summary_parameter.parameter_type.convert(""))
            self.assertIsNone(submit_tool.change_summary_parameter.parameter_type.convert("   "))
            self.assertIsNone(submit_tool.change_summary_parameter.parameter_type.convert(None))  # type: ignore[arg-type]
            with self.assertRaises((tool_provider.ParameterConversionError, ValueError, TypeError)):
                submit_tool.target_parameter.parameter_type.convert(12345)  # type: ignore[arg-type]
            with self.assertRaises((tool_provider.ParameterConversionError, ValueError, TypeError)):
                submit_tool.change_summary_parameter.parameter_type.convert(12345)  # type: ignore[arg-type]

            # FailTool: parameters actual_type properties + wire conversion
            fail_tool = scope.get_singleton(FailTool)
            self.assertIn(tool_provider.ParameterName("target"), fail_tool.parameters)
            self.assertIn(tool_provider.ParameterName("explanation"), fail_tool.parameters)
            self.assertEqual(fail_tool.target_parameter.parameter_type.actual_type, agent_file_alias.FileAlias)
            self.assertEqual(fail_tool.explanation_parameter.name, tool_provider.ParameterName("explanation"))
            self.assertTrue(len(str(fail_tool.explanation_parameter.description)) > 0)
            self.assertIsInstance(fail_tool.explanation_parameter.is_required, bool)
            self.assertEqual(fail_tool.explanation_parameter.parameter_type.actual_type, sandbox_run_control.FailureExplanation)
            self.assertEqual(fail_tool.explanation_parameter.parameter_type.wire_type, str)
            f_expl = fail_tool.explanation_parameter.parameter_type.convert("Fatal error")
            self.assertEqual(str(f_expl), "Fatal error")
            with self.assertRaises((tool_provider.ParameterConversionError, ValueError, TypeError)):
                fail_tool.explanation_parameter.parameter_type.convert(12345)  # type: ignore[arg-type]

            # BlameTool: parameters actual_type properties + optional wire conversion
            blame_tool = scope.get_singleton(BlameTool)
            self.assertIn(tool_provider.ParameterName("target"), blame_tool.parameters)
            self.assertIn(tool_provider.ParameterName("blame_target"), blame_tool.parameters)
            self.assertIn(tool_provider.ParameterName("explanation"), blame_tool.parameters)
            self.assertEqual(blame_tool.target_parameter.parameter_type.actual_type, agent_file_alias.FileAlias)
            self.assertEqual(blame_tool.blame_target_parameter.name, tool_provider.ParameterName("blame_target"))
            self.assertTrue(len(str(blame_tool.blame_target_parameter.description)) > 0)
            self.assertIsInstance(blame_tool.blame_target_parameter.is_required, bool)
            self.assertEqual(blame_tool.blame_target_parameter.parameter_type.actual_type, agent_file_alias.FileAlias)
            self.assertEqual(blame_tool.blame_target_parameter.parameter_type.wire_type, str)
            self.assertEqual(blame_tool.explanation_parameter.name, tool_provider.ParameterName("explanation"))
            self.assertTrue(len(str(blame_tool.explanation_parameter.description)) > 0)
            self.assertIsInstance(blame_tool.explanation_parameter.is_required, bool)
            self.assertEqual(blame_tool.explanation_parameter.parameter_type.actual_type, sandbox_run_control.BlameExplanation)
            self.assertEqual(blame_tool.explanation_parameter.parameter_type.wire_type, str)
            b_target = blame_tool.blame_target_parameter.parameter_type.convert("pkg/upstream.py")
            self.assertIsInstance(b_target, agent_file_alias.FileAlias)
            b_expl = blame_tool.explanation_parameter.parameter_type.convert("Spec bug")
            self.assertEqual(str(b_expl), "Spec bug")
            with self.assertRaises((tool_provider.ParameterConversionError, ValueError, TypeError)):
                blame_tool.blame_target_parameter.parameter_type.convert(999)  # type: ignore[arg-type]
            with self.assertRaises((tool_provider.ParameterConversionError, ValueError, TypeError)):
                blame_tool.explanation_parameter.parameter_type.convert(999)  # type: ignore[arg-type]

            # GetWorkTool: parameters actual_type properties + optional wire conversion
            gw_tool = scope.get_singleton(GetWorkTool)
            self.assertIn(tool_provider.ParameterName("max_batch_size"), gw_tool.parameters)
            self.assertEqual(gw_tool.max_batch_size_parameter.name, tool_provider.ParameterName("max_batch_size"))
            self.assertTrue(len(str(gw_tool.max_batch_size_parameter.description)) > 0)
            self.assertIsInstance(gw_tool.max_batch_size_parameter.is_required, bool)
            self.assertEqual(gw_tool.max_batch_size_parameter.parameter_type.actual_type, dag_config.BatchSize)
            self.assertEqual(gw_tool.max_batch_size_parameter.parameter_type.wire_type, int)
            batch = gw_tool.max_batch_size_parameter.parameter_type.convert(4)
            assert batch is not None
            self.assertEqual(int(batch), 4)
            try:
                b_none = gw_tool.max_batch_size_parameter.parameter_type.convert(None)  # type: ignore[arg-type]
                self.assertIsNone(b_none)
            except (tool_provider.ParameterConversionError, ValueError, TypeError):
                pass
            with self.assertRaises((tool_provider.ParameterConversionError, ValueError, TypeError)):
                gw_tool.max_batch_size_parameter.parameter_type.convert("not_an_int")  # type: ignore[arg-type]

            # CheckFilesTool and AdvanceTool parameter schema checks
            cf_tool = scope.get_singleton(CheckFilesTool)
            self.assertIsInstance(cf_tool.parameters, Mapping)
            adv_tool = scope.get_singleton(AdvanceTool)
            self.assertIsInstance(adv_tool.parameters, Mapping)

            # ToolManager execution with invalid parameter wire value fails gracefully
            self.mock_tool_manager.install_tool(gw_tool)
            err_resp = self.mock_tool_manager.execute_tool(
                tool_provider.ToolName("get_work"),
                {tool_provider.ParameterName("max_batch_size"): "invalid_int"},
            )
            self.assertTrue(err_resp.is_failed)
            self.assertIn("Invalid argument", str(err_resp.content))

    def test_tool_manager_wire_dispatch_across_run_control_tools(self) -> None:
        """Postcondition: Dispatch tool execution via wire parameter bindings across all run control tools."""
        node = _make_node("unit1")
        upstream = _make_node("upstream1")
        self.mock_storage.mark_node_dirty(node)
        self.mock_session_coordinator.register_node(node, "pkg/unit1.py")
        self.mock_session_coordinator.register_node(upstream, "pkg/upstream1.py")
        bound_upstream = _make_bound_file("pkg/upstream1.py", owning_node=upstream)
        self.mock_node_config.blame_targets_by_node = {node: {bound_upstream}}
        self.mock_node_config.verification_checks = [MockVerificationCheck(passed=True)]
        self.mock_session_coordinator.verification_result = True

        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            for cls in [CheckFilesTool, AdvanceTool, SubmitTool, FailTool, BlameTool, GetWorkTool]:
                tool = scope.get_singleton(cls)
                self.mock_tool_manager.install_tool(tool)

            resp = self.mock_tool_manager.execute_tool(tool_provider.ToolName("check_files"), {})
            self.assertFalse(resp.is_failed)

            self.mock_guide_delivery.has_steps_remaining = True
            resp = self.mock_tool_manager.execute_tool(tool_provider.ToolName("advance"), {})
            self.assertFalse(resp.is_failed)

            self.mock_sandbox.has_modifications = True
            self.mock_edit_manager.has_modifications = True
            self.mock_guide_delivery.has_steps_remaining = False
            resp = self.mock_tool_manager.execute_tool(
                tool_provider.ToolName("submit"),
                {
                    tool_provider.ParameterName("target"): "pkg/unit1.py",
                    tool_provider.ParameterName("change_summary"): "Wire dispatched submit",
                },
            )
            self.assertFalse(resp.is_failed)

            resp = self.mock_tool_manager.execute_tool(
                tool_provider.ToolName("fail"),
                {
                    tool_provider.ParameterName("target"): "pkg/unit1.py",
                    tool_provider.ParameterName("explanation"): "Wire dispatched failure",
                },
            )
            self.assertTrue(resp.is_failed)
            self.assertTrue(resp.is_terminated)

            resp = self.mock_tool_manager.execute_tool(
                tool_provider.ToolName("blame"),
                {
                    tool_provider.ParameterName("target"): "pkg/unit1.py",
                    tool_provider.ParameterName("blame_target"): "pkg/upstream1.py",
                    tool_provider.ParameterName("explanation"): "Wire dispatched blame",
                },
            )
            self.assertFalse(resp.is_failed)

            self.mock_session_coordinator.open_targets = []
            self.mock_subgraph.ready_batch = []
            resp = self.mock_tool_manager.execute_tool(
                tool_provider.ToolName("get_work"),
                {tool_provider.ParameterName("max_batch_size"): 2},
            )
            self.assertFalse(resp.is_failed)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
