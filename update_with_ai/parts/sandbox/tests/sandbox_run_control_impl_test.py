"""Unit tests for sandbox_run_control_impl aligned with grounding specifications."""

import unittest
from typing import Any, List, Mapping, Optional, Sequence, Set, Tuple

from update_with_ai.parts.dag.lib.dag_storage import Dependency, Node
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.agent.lib.agent_file_alias import (
    AliasManager,
    BoundFile,
    DirectoryPath,
    FileAlias,
    FileContent,
    ReadOnlyFile,
    ReadWriteFile,
    UnboundFile,
    WorkspacePath,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.agent.lib.agent_node_config import (
    Guide,
    NodeConfig,
    RoleConfig,
    VerificationCheck,
)
from update_with_ai.parts.dag.lib.dag_subgraph import DagSubgraph
from update_with_ai.parts.sandbox.lib.sandbox import Sandbox
from update_with_ai.parts.sandbox.lib.sandbox_file_editor import EditManager
from update_with_ai.parts.sandbox.lib.sandbox_guide_delivery import GuideDelivery
from update_with_ai.parts.sandbox.lib.sandbox_run_control import (
    AdvanceTool,
    BlameTool,
    CheckFileTool,
    FailTool,
    GetWorkTool,
    RunController,
    RunTestsTool,
    SubmitTool,
)
from update_with_ai.parts.sandbox.lib.sandbox_run_control_impl import (
    AdvanceTool as AdvanceToolImpl,
    BlameTool as BlameToolImpl,
    CheckFileTool as CheckFileToolImpl,
    FailTool as FailToolImpl,
    GetWorkTool as GetWorkToolImpl,
    RunController as RunControllerImpl,
    RunTestsTool as RunTestsToolImpl,
    SubmitTool as SubmitToolImpl,
    __initialize__,
)

agent_session = RunControllerImpl.tier
from update_with_ai.parts.sandbox.lib import template_format
from update_with_ai.parts.sandbox.lib.tool_provider import (
    ActualParameterBindings,
    Integer,
    IntegerParameterConverter,
    Response,
    String,
    StringParameterConverter,
    Tool,
    ToolManager,
    WireParameterBindings,
)


class MockToolManager:
    tier = agent_session

    def __init__(self) -> None:
        self.installed_tools: Set[Tool] = set()

    def install_tool(self, tool: Tool) -> None:
        self.installed_tools.add(tool)

    def execute_tool(
        self, name: str, wire_parameter_bindings: WireParameterBindings
    ) -> Response:
        return Response(is_failed=False, is_terminated=False, content="")


class MockStringConverter:
    tier = agent_session
    actual_type = str
    wire_type = String()

    def convert(self, wire_value: Any) -> str:
        return str(wire_value)


class MockIntegerConverter:
    tier = agent_session
    actual_type = int
    wire_type = Integer()

    def convert(self, wire_value: Any) -> int:
        return int(wire_value)


def _make_directory_path(path: str) -> DirectoryPath:
    obj = object.__new__(DirectoryPath)
    object.__setattr__(obj, "path", path)
    return obj


def _make_workspace_path(path: str) -> WorkspacePath:
    obj = object.__new__(WorkspacePath)
    object.__setattr__(obj, "path", path)
    return obj


class MockAliasManager:
    tier = agent_session

    def __init__(self) -> None:
        self.workspace_root = _make_directory_path("/workspace")
        self.actual_type = FileAlias
        self.wire_type = String()

    def convert(self, wire_value: Any) -> Any:
        return wire_value

    def sanitize_text(self, text: str) -> str:
        return text.replace("/workspace/pkg/", "")

    def initialize(self) -> None:
        pass


class MockNodeConfig:
    tier = agent_session

    def __init__(
        self,
        blame_targets: Optional[Set[BoundFile]] = None,
        blame_targets_by_node: Optional[Mapping[Node, Set[BoundFile]]] = None,
        verification_checks: Optional[Sequence[VerificationCheck]] = None,
        verification_checks_by_node: Optional[
            Mapping[Node, Sequence[VerificationCheck]]
        ] = None,
        guide: Optional[Guide] = None,
        is_step_mode: bool = True,
        feedback: Optional[Sequence[str]] = None,
        read_write_files: Optional[Set[BoundFile]] = None,
        verification_success_message: Optional[str] = None,
        src_file_alias_by_node: Optional[Mapping[Node, str]] = None,
    ) -> None:
        self._blame_targets = blame_targets or set()
        self.blame_targets_by_node: Mapping[Node, Set[BoundFile]] = (
            blame_targets_by_node or {}
        )
        self._verification_checks: Sequence[VerificationCheck] = (
            verification_checks or []
        )
        self.verification_checks_by_node: Mapping[Node, Sequence[VerificationCheck]] = (
            verification_checks_by_node or {}
        )
        self._guide = guide
        self.is_step_mode = is_step_mode
        self._feedback: Sequence[str] = feedback or ()
        self._read_write_files: Set[BoundFile] = read_write_files or set()
        self._verification_success_message = verification_success_message
        self.src_file_alias_by_node: Mapping[Node, str] = src_file_alias_by_node or {}

    @property
    def read_only_files(self) -> Set[BoundFile]:
        return set()

    @property
    def read_write_files(self) -> Set[BoundFile]:
        return set(self._read_write_files)

    @property
    def guide_file(self) -> Optional[UnboundFile]:
        return None

    @property
    def templates(self) -> Set[Tuple[BoundFile, FileContent]]:
        return set()

    @property
    def guide(self) -> Optional[Guide]:
        return self._guide

    @property
    def blame_targets(self) -> Set[BoundFile]:
        return self._blame_targets

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        return self._verification_checks

    @property
    def verification_success_message(self) -> Optional[str]:
        return self._verification_success_message

    @property
    def feedback(self) -> Sequence[str]:
        return self._feedback


class MockGuideDelivery:
    tier = agent_session

    def __init__(
        self,
        has_steps: bool = False,
        next_step_content: Optional[str] = None,
        guide: Optional[Guide] = None,
    ) -> None:
        self.has_steps_remaining = has_steps
        self.next_step_content = next_step_content
        self.advance_step_called = False
        self.last_verification_passed: Optional[bool] = None
        self.last_failure_diagnostics: Optional[str] = None
        self._guide: Optional[Guide] = guide
        self.initial_delivered = False

    @property
    def guide(self) -> Optional[Guide]:
        return self._guide

    def advance_step(
        self, verification_passed: bool, failure_diagnostics: Optional[str] = None
    ) -> Optional[Response]:
        self.advance_step_called = True
        self.last_verification_passed = verification_passed
        self.last_failure_diagnostics = failure_diagnostics
        if not self.initial_delivered:
            self.initial_delivered = True
            summary = self._guide.summary if self._guide else "Guide Summary"
            return Response(is_failed=False, is_terminated=False, content=summary)
        if self.has_steps_remaining:
            if not verification_passed:
                return Response(
                    is_failed=True,
                    is_terminated=False,
                    content=f"Step failed with: {failure_diagnostics}",
                )
            if self.next_step_content:
                return Response(
                    is_failed=False, is_terminated=False, content=self.next_step_content
                )
        return None

    def parse_guide(self, content: FileContent) -> Guide:
        return Guide(summary="", sections=[])


class MockEditManager:
    tier = agent_session

    def __init__(
        self, has_modifications: bool = False, file_update_revision: int = 0
    ) -> None:
        self.has_modifications = has_modifications
        self.file_update_revision = file_update_revision
        self._locked_files: Set[Any] = set()
        self._last_read_or_edited_file: Optional[Any] = None

    @property
    def last_read_or_edited_file(self) -> Optional[Any]:
        return self._last_read_or_edited_file

    @last_read_or_edited_file.setter
    def last_read_or_edited_file(self, value: Optional[Any]) -> None:
        self._last_read_or_edited_file = value

    @property
    def locked_files(self) -> Set[Any]:
        return set(self._locked_files)

    def lock_file(self, file: Any) -> None:
        self._locked_files.add(file)

    def unlock_file(self, file: Any) -> None:
        self._locked_files.discard(file)

    def materialize_templates(self) -> None:
        pass


class TargetFileObj:
    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        self.short_name = relative_path


class MockVerificationCheck(VerificationCheck):
    def __init__(self, passes: bool = True, diagnostic: str = "") -> None:
        self.passes = passes
        self.diagnostic = diagnostic
        self.called = False
        self.call_count = 0

    def verify(self) -> Tuple[bool, str]:
        self.called = True
        self.call_count += 1
        return self.passes, self.diagnostic


class MockNodeDefinition:
    def __init__(self, task_prompt: str = "") -> None:
        self.task_prompt = task_prompt


class MockDagStorage:
    tier = system

    def __init__(self) -> None:
        self.dependencies: dict[Node, Set[Dependency]] = {}
        self.messages: dict[Node, Sequence[Any]] = {}
        self.node_definitions: dict[Node, Any] = {}
        self.dirty_nodes: Set[Node] = set()

    def get_dependencies(self, node: Node) -> Set[Dependency]:
        return self.dependencies.get(node, set())

    def get_messages(self, node: Node) -> Sequence[Any]:
        return self.messages.get(node, [])

    def get_node_definition(self, node: Node) -> Any:
        return self.node_definitions.get(node)

    def is_dirty(self, node: Node) -> bool:
        return node in self.dirty_nodes


class MockDagSubgraph:
    tier = system

    def __init__(self, ready_batches: Optional[List[Sequence[Node]]] = None) -> None:
        self.ready_batches: List[Sequence[Node]] = ready_batches or []
        self.batch_index: int = 0

    def next_ready_batch(self) -> Sequence[Node]:
        if self.batch_index < len(self.ready_batches):
            batch = self.ready_batches[self.batch_index]
            self.batch_index += 1
            return batch
        return []


class MockRoleConfig:
    tier = agent_session

    def __init__(self, node_cfg: Optional["MockNodeConfig"] = None) -> None:
        self.node_cfg = node_cfg
        self._role: str = ""
        self.active_nodes: Sequence[Node] = []
        self.execution_version: int = 1

    @property
    def role(self) -> str:
        return self._role

    @property
    def nodes(self) -> Sequence[Node]:
        return self.active_nodes

    @property
    def version(self) -> int:
        return self.execution_version

    def set_role(self, role: str) -> None:
        self._role = role

    def set_nodes(self, nodes: Sequence[Node]) -> None:
        self.active_nodes = list(nodes)
        if nodes:
            self._role = nodes[0].role_address
        self.execution_version += 1
        if self.node_cfg is not None:
            self.node_cfg.src_file_alias_by_node = {
                n: f"{n.unit_address.split(':')[-1]}.py" for n in nodes
            }


class MockSandbox:
    tier = agent_session

    def __init__(self) -> None:
        self.materialize_startup_templates_called = False

    def materialize_startup_templates(self) -> None:
        self.materialize_startup_templates_called = True


class MockAgentConfig:
    tier = agent_session

    def __init__(self, is_mcp_mode: bool = False) -> None:
        self.is_mcp_mode = is_mcp_mode


class MockTemplateFormatter:
    tier = agent_session

    def format_template(self, text: str, parameters: Any) -> str:
        nodes = parameters.get("nodes", [])
        if "Remaining open files" in text or "Remaining submit targets" in text:
            lines = ["Remaining submit targets to handle:"]
            for n in nodes:
                lines.append(f"- `{n.get('src_alias', '')}`")
            return "\n".join(lines)
        if parameters.get("is_multi_node"):
            lines = ["Process the following files:"]
            for n in nodes:
                lines.append(f"- `{n['src_alias']}`: {n['task_prompt']}")
            lines.append("\nCall submit(target='<file_name>') to submit each file individually.")
            if parameters.get("has_guide"):
                lines.append(f"\n{parameters.get('guide_instruction')}")
            return "\n".join(lines)
        if "task_prompt" in parameters:
            res = parameters.get("task_prompt", "")
            if parameters.get("has_guide"):
                res = f"{res}\n\n{parameters.get('guide_instruction')}"
            return res
        return text


class SandboxRunControlImplTest(unittest.TestCase):
    def setUp(self) -> None:
        node = Node(unit_address="//pkg:upstream", role_address="lib")
        self.blame_target_file = ReadOnlyFile(
            relative_path="dep.py",
            workspace_path=_make_workspace_path("pkg/dep.py"),
            owning_node=node,
        )

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.storage = MockDagStorage()
        self.registry.register_instance(
            self.storage, keys=[dag_storage.DagStorage], tier=system
        )
        self.subgraph = MockDagSubgraph()
        self.registry.register_instance(
            self.subgraph, keys=[DagSubgraph], tier=system
        )

        self.tool_mgr = MockToolManager()
        self.str_conv = MockStringConverter()
        self.int_conv = MockIntegerConverter()
        self.alias_mgr = MockAliasManager()
        self.tmpl_formatter = MockTemplateFormatter()
        self.node_cfg = MockNodeConfig(
            blame_targets={self.blame_target_file},
            is_step_mode=True,
            guide=Guide(summary="Guide Summary", sections=[]),
        )
        self.guide_del = MockGuideDelivery(
            guide=Guide(summary="Guide Summary", sections=[])
        )
        self.edit_mgr = MockEditManager()
        self.role_cfg = MockRoleConfig(node_cfg=self.node_cfg)
        self.sb = MockSandbox()
        self.agent_cfg = MockAgentConfig(is_mcp_mode=False)

        self.registry.register_instance(
            self.tool_mgr, keys=[ToolManager], tier=agent_session
        )
        self.registry.register_instance(
            self.str_conv, keys=[StringParameterConverter], tier=agent_session
        )
        self.registry.register_instance(
            self.int_conv, keys=[IntegerParameterConverter], tier=agent_session
        )
        self.registry.register_instance(
            self.alias_mgr, keys=[AliasManager], tier=agent_session
        )
        self.registry.register_instance(
            self.tmpl_formatter,
            keys=[template_format.TemplateFormatter],
            tier=agent_session,
        )
        self.registry.register_instance(
            self.node_cfg, keys=[NodeConfig], tier=agent_session
        )
        self.registry.register_instance(
            self.guide_del, keys=[GuideDelivery], tier=agent_session
        )
        self.registry.register_instance(
            self.edit_mgr, keys=[EditManager], tier=agent_session
        )
        self.registry.register_instance(
            self.role_cfg, keys=[RoleConfig], tier=agent_session
        )
        self.registry.register_instance(
            self.sb, keys=[Sandbox], tier=agent_session
        )
        self.registry.register_instance(
            self.agent_cfg, keys=[AgentConfig], tier=agent_session
        )

    def test_run_controller_initialization_with_blame_and_step_mode(self) -> None:
        """CUJ: RunController installs advance, submit, fail, and blame tools when step mode and blame targets exist."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            ctrl = scope.get_singleton(RunController)
            # Requirement: Verification checks exposed by the run controller include the session verification checks from node config.
            # Requirement: [RunController] The run controller exposes verification checks that validate session criteria.
            self.assertEqual(ctrl.verification_checks, [])
            # Requirement: The run controller unconditionally installs the submit tool, fail tool, check file tool, and get work tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured.
            # Requirement: [RunController] The run controller installs an advance tool when guide step mode is active, coordinating step progression through guide delivery upon passing verification.
            # Requirement: [RunController] The run controller installs a submit tool that concludes target processing upon passing verification and enforces change documentation.
            # Requirement: [RunController] The run controller installs a fail tool that terminates the run in failure.
            # Requirement: [RunController] The run controller installs a check file tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
            # Requirement: [RunController] The run controller installs a blame tool when blame targets are configured, attributing task failure to an upstream dependency node.
            # Requirement: [RunController] The run controller installs a get work tool that retrieves active dirty nodes, materializes startup templates, and delivers the session task prompt.
            tool_names = {t.name for t in self.tool_mgr.installed_tools}
            # Requirement: The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.
            self.assertIn("advance", tool_names)
            # Requirement: The submit tool is named `submit`, accepting a target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
            self.assertIn("submit", tool_names)
            # Requirement: The fail tool is named `fail`, accepting a target parameter and a text explanation parameter.
            self.assertIn("fail", tool_names)
            # Requirement: The check file tool is named `check_file`, accepting a path parameter (with src accepted as an alias), and shares a constant suppression key `check_file`.
            self.assertIn("check_file", tool_names)
            # Requirement: The blame tool is named `blame`, accepting a source target parameter, a file alias blame target parameter, and a text explanation parameter.
            self.assertIn("blame", tool_names)
            # Requirement: The get work tool is named `get_work`, accepting an integer max batch size parameter.
            self.assertIn("get_work", tool_names)

    def test_run_controller_initialization_without_blame_and_step_mode(self) -> None:
        """CUJ: RunController omits advance and blame tools when step mode is inactive and blame targets are empty."""
        reg = LifecycleRegistry()
        __initialize__(reg)
        tool_mgr = MockToolManager()
        cfg = MockNodeConfig(blame_targets=set(), is_step_mode=False, guide=None)
        reg.register_instance(
            self.storage, keys=[dag_storage.DagStorage], tier=system
        )
        reg.register_instance(
            self.subgraph, keys=[DagSubgraph], tier=system
        )
        reg.register_instance(tool_mgr, keys=[ToolManager], tier=agent_session)
        reg.register_instance(
            self.str_conv, keys=[StringParameterConverter], tier=agent_session
        )
        reg.register_instance(
            self.int_conv, keys=[IntegerParameterConverter], tier=agent_session
        )
        reg.register_instance(self.alias_mgr, keys=[AliasManager], tier=agent_session)
        reg.register_instance(
            self.tmpl_formatter,
            keys=[template_format.TemplateFormatter],
            tier=agent_session,
        )
        reg.register_instance(cfg, keys=[NodeConfig], tier=agent_session)
        reg.register_instance(
            self.guide_del, keys=[GuideDelivery], tier=agent_session
        )
        reg.register_instance(self.edit_mgr, keys=[EditManager], tier=agent_session)
        reg.register_instance(
            self.role_cfg, keys=[RoleConfig], tier=agent_session
        )
        reg.register_instance(
            self.sb, keys=[Sandbox], tier=agent_session
        )
        reg.register_instance(
            self.agent_cfg, keys=[AgentConfig], tier=agent_session
        )

        with enter_phase(agent_session, registry=reg) as scope:
            ctrl = scope.get_singleton(RunController)
            # Requirement: The run controller unconditionally installs the submit tool, fail tool, check file tool, and get work tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured.
            tool_names = {t.name for t in tool_mgr.installed_tools}
            self.assertIn("submit", tool_names)
            self.assertIn("fail", tool_names)
            self.assertIn("check_file", tool_names)
            self.assertIn("get_work", tool_names)
            self.assertNotIn("advance", tool_names)
            self.assertNotIn("blame", tool_names)

    def test_run_controller_evaluate_verification_caching(self) -> None:
        """CUJ: RunController caches verification results and reuses them when file revision unchanged."""
        check = MockVerificationCheck(
            passes=False, diagnostic="Syntax error in /workspace/pkg/dep.py:5"
        )
        self.node_cfg._verification_checks = [check]
        self.edit_mgr.file_update_revision = 1

        with enter_phase(agent_session, registry=self.registry) as scope:
            ctrl = scope.get_singleton(RunControllerImpl)
            # First evaluation executes checks and caches result
            # Requirement: Evaluation of verification checks is cached alongside the edit manager file update revision.
            # Requirement: [RunController] The run controller caches verification evaluation results alongside the edit manager file update revision, reusing the cached verification outcome as long as no workspace files have been updated since that evaluation.
            # Requirement: Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when workspace files have been updated since the previous evaluation.
            passed1, diag1 = ctrl.evaluate_verification()
            self.assertFalse(passed1)
            self.assertEqual(check.call_count, 1)
            self.assertIn("dep.py:5", diag1)

            # Re-evaluation with same file revision reuses cached result without re-executing checks
            # Requirement: When workspace files have not been updated since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.
            passed2, diag2 = ctrl.evaluate_verification()
            self.assertFalse(passed2)
            self.assertEqual(check.call_count, 1)
            self.assertEqual(diag1, diag2)

            # Modifying workspace files updates revision and triggers re-execution
            self.edit_mgr.file_update_revision = 2
            check.passes = True
            passed3, _ = ctrl.evaluate_verification()
            self.assertTrue(passed3)
            self.assertEqual(check.call_count, 2)

    def test_advance_tool_initial_delivery_omits_verification_update(self) -> None:
        """CUJ: AdvanceTool delivers initial guide summary on first execution without evaluating verification checks."""
        vcheck = MockVerificationCheck(passes=False, diagnostic="Failing initial check")
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            advance = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings=set())

            # Requirement: The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.
            self.assertEqual(advance.name, "advance")
            self.assertEqual(advance.parameters, set())
            self.assertIsInstance(advance.description, str)

            # Requirement: On its first execution, the advance tool delivers the initial guide summary through guide delivery without updating verification results.
            resp = advance.execute_tool(b)
            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(resp.content, "Guide Summary")
            self.assertEqual(vcheck.call_count, 0)
            self.assertEqual(resp.suppression_key, "advance")

    def test_advance_tool_subsequent_execution_fails_when_verification_failing(
        self,
    ) -> None:
        """CUJ: Subsequent advance call evaluates verification and fails when verification fails."""
        vcheck = MockVerificationCheck(passes=False, diagnostic="Syntax error")
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            advance = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings=set())

            _ = advance.execute_tool(b)
            # Requirement: On subsequent executions, executing the advance tool updates verification results if outdated.
            # Requirement: Tool execution fails when verification is failing, reminding the agent that the check file tool should be called first and specifying a follow-up execution of the check file tool with reasoning text indicating that verification results must be inspected before advancing.
            resp = advance.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(vcheck.call_count, 1)
            self.assertIsNotNone(resp.reminder)
            assert resp.reminder is not None
            self.assertIn("check file tool should be called first", resp.reminder)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "check_file")
            self.assertEqual(
                resp.follow_up_tool_call.reasoning_text,
                "Verification results must be inspected before advancing.",
            )

    def test_advance_tool_steps_remaining_delivers_next_step(self) -> None:
        """CUJ: AdvanceTool advances guide step and delivers next step section when verification passes."""
        self.guide_del.has_steps_remaining = True
        self.guide_del.next_step_content = "Step 1: Write initial test case"
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            advance = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings=set())

            _ = advance.execute_tool(b)
            # Requirement: Tool execution advances guide delivery and delivers the next step section when verification is passing and guide steps remain.
            resp = advance.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(resp.content, "Step 1: Write initial test case")
            self.assertEqual(resp.suppression_key, "advance")

    def test_advance_tool_no_steps_remaining_files_modified_requires_submit(
        self,
    ) -> None:
        """CUJ: AdvanceTool fails with reminder to call submit tool when no steps remain and files were modified."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            advance = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings=set())

            _ = advance.execute_tool(b)
            # Requirement: Tool execution fails with a reminder to call the submit tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.
            resp = advance.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            assert resp.reminder is not None
            self.assertIn("submit", resp.reminder)
            self.assertEqual(resp.suppression_key, "advance")

    def test_advance_tool_no_steps_remaining_no_files_modified_specifies_submit_followup(
        self,
    ) -> None:
        """CUJ: AdvanceTool specifies submit follow-up tool call when no steps remain and no files were modified."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            advance = scope.get_singleton(AdvanceToolImpl)
            b = ActualParameterBindings(bindings=set())

            _ = advance.execute_tool(b)
            # Requirement: Tool execution produces a response specifying a follow-up execution of the submit tool without a change summary and with reasoning text indicating that all guide steps are complete when verification is passing, no steps remain, and no workspace files were modified.
            resp = advance.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "submit")
            self.assertEqual(
                len(resp.follow_up_tool_call.wire_parameter_bindings.bindings), 0
            )
            self.assertEqual(
                resp.follow_up_tool_call.reasoning_text,
                "All guide steps are complete.",
            )
            self.assertEqual(resp.suppression_key, "advance")

    def test_submit_tool_parameters_and_converters(self) -> None:
        """CUJ: SubmitTool declares target and change_summary parameters with converters."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            # Requirement: The submit tool is named `submit`, accepting a target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
            self.assertEqual(submit.name, "submit")
            self.assertIsInstance(submit.description, str)
            self.assertEqual(submit.parameters, {submit.target, submit.change_summary})
            # Requirement: The submit tool change summary parameter uses a string parameter converter to accept text.
            self.assertIs(submit.change_summary.parameter_converter, self.str_conv)
            self.assertIs(submit.target.parameter_converter, self.alias_mgr)

    def test_submit_tool_fails_when_steps_remain_specifies_advance_followup(
        self,
    ) -> None:
        """CUJ: SubmitTool fails when guide steps remain and specifies advance as follow-up."""
        self.guide_del.has_steps_remaining = True
        vcheck = MockVerificationCheck(passes=False)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Executing the submit tool updates verification results if outdated.
            # Requirement: Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call with reasoning text indicating that remaining guide steps must be completed before finishing.
            resp = submit.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "advance")
            self.assertEqual(
                len(resp.follow_up_tool_call.wire_parameter_bindings.bindings), 0
            )
            self.assertEqual(
                resp.follow_up_tool_call.reasoning_text,
                "Remaining guide steps must be completed before finishing.",
            )
            # Requirement: The submit tool is named `submit`, accepting a target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
            self.assertEqual(resp.suppression_key, "submit")

    def test_submit_tool_fails_when_verification_failing_specifies_check_file_followup(
        self,
    ) -> None:
        """CUJ: SubmitTool fails when verification fails and specifies check_file follow-up."""
        self.guide_del.has_steps_remaining = False
        self.node_cfg._feedback = ["Previous feedback"]
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(
            passes=False, diagnostic="Syntax error in /workspace/pkg/dep.py:20"
        )
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Executing the submit tool updates verification results if outdated.
            # Requirement: Tool execution fails when verification is failing, reminding the agent that the check file tool should be called first and specifying a follow-up execution of the check file tool targeting the submitted target with reasoning text indicating that verification results must be inspected before submitting.
            resp = submit.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            assert resp.reminder is not None
            self.assertIn("check file tool should be called first", resp.reminder)
            self.assertIsNotNone(resp.follow_up_tool_call)
            assert resp.follow_up_tool_call is not None
            self.assertEqual(resp.follow_up_tool_call.tool_name, "check_file")
            self.assertEqual(
                resp.follow_up_tool_call.wire_parameter_bindings.bindings,
                {("path", "target")},
            )
            self.assertEqual(
                resp.follow_up_tool_call.reasoning_text,
                "Verification results must be inspected before submitting.",
            )
            self.assertEqual(resp.suppression_key, "submit")

    def test_submit_tool_fails_when_feedback_present_and_no_files_modified(
        self,
    ) -> None:
        """CUJ: SubmitTool fails when feedback is present and no workspace files were modified."""
        self.guide_del.has_steps_remaining = False
        self.node_cfg._feedback = ["Must address edge cases"]
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.
            resp = submit.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertEqual(resp.suppression_key, "submit")

    def test_submit_tool_fails_when_files_modified_and_summary_omitted(self) -> None:
        """CUJ: SubmitTool fails when workspace files modified but change summary omitted."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(bindings=set())
            # Requirement: Tool execution fails if workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files.
            resp = submit.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIsNotNone(resp.reminder)
            self.assertEqual(resp.suppression_key, "submit")

    def test_submit_tool_succeeds_when_no_files_modified_and_summary_provided(
        self,
    ) -> None:
        """CUJ: SubmitTool succeeds and terminates when no workspace files modified but change summary provided."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = False
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(
                bindings={(submit.change_summary, "Unneeded change summary")}
            )
            # Requirement: Tool execution marks the target as submitted and resolves the target.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When all session targets are resolved, resolving a target produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.
            resp = submit.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertIn("Unneeded change summary", resp.content)
            self.assertEqual(resp.suppression_key, "submit")

    def test_submit_tool_succeeds_and_terminates_session(self) -> None:
        """CUJ: SubmitTool succeeds and terminates session when criteria met and verification passes."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            b = ActualParameterBindings(
                bindings={(submit.change_summary, "Added new feature")}
            )
            # Requirement: Tool execution marks the target as submitted and resolves the target.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When all session targets are resolved, resolving a target produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.
            resp = submit.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertIn("Added new feature", resp.content)
            self.assertEqual(resp.suppression_key, "submit")

    def test_fail_tool(self) -> None:
        """CUJ: FailTool produces terminating failure response carrying explanation."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            fail_tool = scope.get_singleton(FailToolImpl)
            self.assertIsInstance(fail_tool.description, str)
            self.assertGreater(len(fail_tool.parameters), 0)
            # Requirement: The fail tool is named `fail`, accepting a target parameter and a text explanation parameter.
            self.assertEqual(fail_tool.name, "fail")
            self.assertIs(fail_tool.explanation.parameter_converter, self.str_conv)

            b = ActualParameterBindings(
                bindings={(fail_tool.explanation, "Cannot solve bug")}
            )
            # Requirement: When a target parameter is omitted, it defaults to the single session read-write file or remaining unsubmitted target.
            # Requirement: Executing the fail tool marks the target as failed and resolves the target.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When all session targets are resolved, resolving a target produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.
            resp = fail_tool.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertTrue(resp.is_terminated)
            self.assertIn("Cannot solve bug", resp.content)

    def test_blame_tool(self) -> None:
        """CUJ: BlameTool validates target and produces terminating feedback attribution."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            blame_tool = scope.get_singleton(BlameToolImpl)
            self.assertIsInstance(blame_tool.description, str)
            self.assertGreater(len(blame_tool.parameters), 0)
            # Requirement: The blame tool is named `blame`, accepting a source target parameter, a file alias blame target parameter, and a text explanation parameter.
            self.assertEqual(blame_tool.name, "blame")
            self.assertIs(blame_tool.blame_target.parameter_converter, self.alias_mgr)
            self.assertIs(blame_tool.explanation.parameter_converter, self.str_conv)

            # Invalid target fails
            unrecognized = ReadOnlyFile(
                relative_path="unknown.py",
                workspace_path=_make_workspace_path("unknown.py"),
                owning_node=Node(unit_address="//pkg:unknown", role_address="lib"),
            )
            b_invalid = ActualParameterBindings(
                bindings={
                    (blame_tool.blame_target, unrecognized),
                    (blame_tool.explanation, "Broken"),
                }
            )
            # Requirement: Tool execution defaults the source target parameter using session target defaulting rules when the source target parameter is omitted and cannot be inferred from the blame target.
            # Requirement: Tool execution fails if the blame target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.
            resp_inv = blame_tool.execute_tool(b_invalid)
            self.assertTrue(resp_inv.is_failed)
            self.assertIsNotNone(resp_inv.reminder)

            # Valid target terminates with Blamed attribution
            b_valid = ActualParameterBindings(
                bindings={
                    (blame_tool.blame_target, self.blame_target_file),
                    (blame_tool.explanation, "Broken type signature"),
                }
            )
            # Requirement: Tool execution defaults the source target parameter to that session target when the blame target matches a configured blame target of an open session target.
            # Requirement: Tool execution marks the blame target as attributed and resolves the source target on successful tool execution.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When all session targets are resolved, resolving a target produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.
            resp_val = blame_tool.execute_tool(b_valid)
            self.assertFalse(resp_val.is_failed)
            self.assertTrue(resp_val.is_terminated)
            self.assertIn("dep.py: Broken type signature", resp_val.content)

            # Backward compatibility: raw_target provided instead of blame_target
            b_legacy = ActualParameterBindings(
                bindings={
                    (blame_tool.target, self.blame_target_file),
                    (blame_tool.explanation, "Legacy blame call"),
                }
            )
            # Requirement: Tool execution defaults the blame target parameter to that target and the source target parameter to the session target configured with that blame target when the blame target parameter is omitted and the source target parameter matches a configured blame target.
            # Requirement: Tool execution marks the blame target as attributed and resolves the source target on successful tool execution.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When all session targets are resolved, resolving a target produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.
            resp_leg = blame_tool.execute_tool(b_legacy)
            self.assertFalse(resp_leg.is_failed)
            self.assertTrue(resp_leg.is_terminated)
            self.assertIn("dep.py: Legacy blame call", resp_leg.content)

    def test_multi_node_submit_and_in_session_dependencies(self) -> None:
        """CUJ: Multi-node session enforces in-session dependency order, validates targets, and marks completion."""
        node1 = Node(unit_address="//pkg:unit1", role_address="lib")
        node2 = Node(unit_address="//pkg:unit2", role_address="lib")
        self.node_cfg.src_file_alias_by_node = {node1: "unit1.py", node2: "unit2.py"}
        self.storage.dependencies[node2] = {Dependency(node=node1)}

        vcheck1 = MockVerificationCheck(passes=True)
        vcheck2 = MockVerificationCheck(passes=True)
        self.node_cfg.verification_checks_by_node = {node1: [vcheck1], node2: [vcheck2]}
        self.guide_del.has_steps_remaining = False

        with enter_phase(agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            rc = scope.get_singleton(RunControllerImpl)

            # Address lookup by unit address fallback
            self.assertEqual(rc.get_node_for_alias("//pkg:unit1"), node1)

            # 1. Submitting without target in multi-target session fails when multiple unsubmitted targets exist
            b_no_target = ActualParameterBindings(bindings=set())
            # Requirement: When a target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open session target.
            resp1 = submit.execute_tool(b_no_target)
            self.assertTrue(resp1.is_failed)
            self.assertIn("Target parameter must be specified", resp1.content)

            # 1b. Submitting without target defaults to last read or written path if open session target
            self.edit_mgr.last_read_or_edited_file = TargetFileObj("unit2.py")
            # Requirement: When a target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open session target.
            # Requirement: Tool execution fails when an in-session dependency of the target has not yet been submitted, reminding the agent that in-session dependencies must be submitted before dependent targets.
            resp_dep_def = submit.execute_tool(b_no_target)
            self.assertTrue(resp_dep_def.is_failed)
            self.assertIn("must be submitted before `unit2.py`", resp_dep_def.content)
            self.edit_mgr.last_read_or_edited_file = None

            # 2. Submitting unknown target fails
            b_unknown = ActualParameterBindings(
                bindings={(submit.target, "unknown.py")}
            )
            # Requirement: Tool execution fails when a target parameter is omitted and cannot be defaulted, or when the specified target parameter does not match an open session target, reminding the agent to specify an open target.
            resp2 = submit.execute_tool(b_unknown)
            self.assertTrue(resp2.is_failed)
            self.assertIn("is not an open target", resp2.content)

            # 3. Submitting node2 before node1 fails due to in-session dependency
            b_dep_first = ActualParameterBindings(
                bindings={(submit.target, "unit2.py")}
            )
            # Requirement: Tool execution fails when an in-session dependency of the target has not yet been submitted, reminding the agent that in-session dependencies must be submitted before dependent targets.
            resp3 = submit.execute_tool(b_dep_first)
            self.assertTrue(resp3.is_failed)
            self.assertIn("must be submitted before `unit2.py`", resp3.content)

            # 4. Submitting node1 succeeds: marks node1 SUBMITTED, leaves session open with remaining open files
            b_node1 = ActualParameterBindings(
                bindings={
                    (submit.target, TargetFileObj("unit1.py")),
                    (submit.change_summary, "Cleaned unit 1"),
                }
            )
            # Requirement: Tool execution marks the target as submitted and resolves the target.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When blame, submit, or fail is successfully called on a submit target and other submit targets remain, resolving the target produces a non-terminating response with a reminder listing remaining submit targets left for the agent to handle formatted via the template formatter.
            resp4 = submit.execute_tool(b_node1)
            self.assertFalse(resp4.is_failed)
            self.assertFalse(resp4.is_terminated)
            self.assertEqual(rc.get_node_state(node1), "SUBMITTED")
            self.assertIn("Target `unit1.py` submitted successfully.", resp4.content)
            self.assertIn("- `unit2.py`", resp4.content)

            # 5. Submitting when only one unsubmitted target remains defaults to that target
            # Requirement: When a target parameter is omitted, it defaults to the single session read-write file or remaining unsubmitted target.
            # Requirement: Tool execution marks the target as submitted and resolves the target.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When all session targets are resolved, resolving a target produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.
            resp5 = submit.execute_tool(b_no_target)
            self.assertFalse(resp5.is_failed)
            self.assertTrue(resp5.is_terminated)
            self.assertEqual(rc.get_node_state(node2), "SUBMITTED")
            self.assertIn("Session completed successfully.", resp5.content)
            self.assertEqual(rc.format_open_targets_reminder(), "")

    def test_multi_node_fail_blocks_dependents_and_terminates(self) -> None:
        """CUJ: Multi-node fail marks target FAILED, dependents BLOCKED, and terminates when no open nodes remain."""
        node1 = Node(unit_address="//pkg:f_unit1", role_address="lib")
        node2 = Node(unit_address="//pkg:f_unit2", role_address="lib")
        node3 = Node(unit_address="//pkg:f_unit3", role_address="lib")
        self.node_cfg.src_file_alias_by_node = {
            node1: "f_unit1.py",
            node2: "f_unit2.py",
            node3: "f_unit3.py",
        }
        self.storage.dependencies[node2] = {Dependency(node=node1)}
        f_rw1 = ReadWriteFile(
            relative_path="f_unit1.py",
            workspace_path=_make_workspace_path("pkg/f_unit1.py"),
            owning_node=node1,
        )
        f_rw3 = ReadWriteFile(
            relative_path="f_unit3.py",
            workspace_path=_make_workspace_path("pkg/f_unit3.py"),
            owning_node=node3,
        )
        self.node_cfg._read_write_files = {f_rw1, f_rw3}

        with enter_phase(agent_session, registry=self.registry) as scope:
            fail_tool = scope.get_singleton(FailToolImpl)
            rc = scope.get_singleton(RunControllerImpl)

            # 1. Failing without target in multi-target session fails when multiple unsubmitted targets exist
            b_no_target = ActualParameterBindings(
                bindings={(fail_tool.explanation, "No target")}
            )
            # Requirement: When a target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open session target.
            resp_no_target = fail_tool.execute_tool(b_no_target)
            self.assertTrue(resp_no_target.is_failed)
            self.assertIn("Target parameter must be specified", resp_no_target.content)

            # 1b. Defaulting to last read/written path when multiple unsubmitted exist
            self.edit_mgr.last_read_or_edited_file = TargetFileObj("f_unit1.py")
            # Requirement: When a target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open session target.
            # Requirement: Executing the fail tool marks the target as failed and resolves the target.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When blame, submit, or fail is successfully called on a submit target and other submit targets remain, resolving the target produces a non-terminating response with a reminder listing remaining submit targets left for the agent to handle formatted via the template formatter.
            resp1 = fail_tool.execute_tool(b_no_target)
            self.assertFalse(resp1.is_failed)
            self.assertFalse(resp1.is_terminated)
            self.assertEqual(rc.get_node_state(node1), "FAILED")
            self.assertEqual(rc.get_node_state(node2), "BLOCKED")
            self.assertIn("Remaining submit targets to handle:\n- `f_unit3.py`", resp1.content)
            self.assertIn(f_rw1, self.edit_mgr.locked_files)
            self.edit_mgr.last_read_or_edited_file = None

            # 2. Failing already-failed node fails because it is not an open target
            b_fail_again = ActualParameterBindings(
                bindings={
                    (fail_tool.target, TargetFileObj("f_unit1.py")),
                    (fail_tool.explanation, "Already failed"),
                }
            )
            # Requirement: Tool execution fails when a target parameter is omitted and cannot be defaulted, or when the specified target parameter does not match an open session target, reminding the agent to specify an open target.
            resp_inv = fail_tool.execute_tool(b_fail_again)
            self.assertTrue(resp_inv.is_failed)
            self.assertIn("is not an open target", resp_inv.content)

            # 3. Failing when only 1 unsubmitted target remains defaults to that target
            # Requirement: When a target parameter is omitted, it defaults to the single session read-write file or remaining unsubmitted target.
            # Requirement: Executing the fail tool marks the target as failed and resolves the target.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When all session targets are resolved, resolving a target produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.
            resp2 = fail_tool.execute_tool(b_no_target)
            self.assertTrue(resp2.is_failed)
            self.assertTrue(resp2.is_terminated)
            self.assertEqual(rc.get_node_state(node3), "FAILED")
            self.assertIn(f_rw3, self.edit_mgr.locked_files)
            self.assertIn("Failed: No target", resp2.content)

    def test_multi_node_blame_blocks_dependents_and_terminates(self) -> None:
        """CUJ: Multi-node blame marks target BLAME, dependents BLOCKED, and terminates when no open nodes remain."""
        node1 = Node(unit_address="//pkg:b_unit1", role_address="lib")
        node2 = Node(unit_address="//pkg:b_unit2", role_address="lib")
        node3 = Node(unit_address="//pkg:b_unit3", role_address="lib")
        self.node_cfg.src_file_alias_by_node = {
            node1: "b_unit1.py",
            node2: "b_unit2.py",
            node3: "b_unit3.py",
        }
        self.storage.dependencies[node2] = {Dependency(node=node1)}
        b_rw1 = ReadWriteFile(
            relative_path="b_unit1.py",
            workspace_path=_make_workspace_path("pkg/b_unit1.py"),
            owning_node=node1,
        )
        b_rw3 = ReadWriteFile(
            relative_path="b_unit3.py",
            workspace_path=_make_workspace_path("pkg/b_unit3.py"),
            owning_node=node3,
        )
        self.node_cfg._read_write_files = {b_rw1, b_rw3}
        bt1 = ReadOnlyFile(
            relative_path="upstream_spec1.md",
            workspace_path=_make_workspace_path("pkg/upstream_spec1.md"),
            owning_node=Node(unit_address="//pkg:upstream_unit1", role_address="spec"),
        )
        bt3 = ReadOnlyFile(
            relative_path="upstream_spec3.md",
            workspace_path=_make_workspace_path("pkg/upstream_spec3.md"),
            owning_node=Node(unit_address="//pkg:upstream_unit3", role_address="spec"),
        )
        self.node_cfg.blame_targets_by_node = {node1: {bt1}, node3: {bt3}}

        with enter_phase(agent_session, registry=self.registry) as scope:
            blame_tool = scope.get_singleton(BlameToolImpl)
            rc = scope.get_singleton(RunControllerImpl)

            # Blame node1 with invalid target fails
            b_bad = ActualParameterBindings(
                bindings={
                    (blame_tool.target, "b_unit1.py"),
                    (blame_tool.blame_target, "wrong.py"),
                    (blame_tool.explanation, "Bad"),
                }
            )
            # Requirement: Tool execution fails if the blame target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.
            resp_bad = blame_tool.execute_tool(b_bad)
            self.assertTrue(resp_bad.is_failed)

            # Blame node1 with valid target and omitted target: infers node1 from blame target!
            b_ok = ActualParameterBindings(
                bindings={
                    (blame_tool.blame_target, "upstream_spec1.md"),
                    (blame_tool.explanation, "Spec defect"),
                }
            )
            # Requirement: Tool execution defaults the source target parameter to that session target when the blame target matches a configured blame target of an open session target.
            # Requirement: Tool execution marks the blame target as attributed and resolves the source target on successful tool execution.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When blame, submit, or fail is successfully called on a submit target and other submit targets remain, resolving the target produces a non-terminating response with a reminder listing remaining submit targets left for the agent to handle formatted via the template formatter.
            resp_ok = blame_tool.execute_tool(b_ok)
            self.assertFalse(resp_ok.is_failed)
            self.assertFalse(resp_ok.is_terminated)
            self.assertEqual(rc.get_node_state(node1), "BLAME")
            self.assertEqual(rc.get_node_state(node2), "BLOCKED")
            self.assertEqual(rc.get_node_state(node3), "OPEN")
            self.assertIn(b_rw1, self.edit_mgr.locked_files)
            self.assertNotIn(b_rw3, self.edit_mgr.locked_files)
            self.assertNotIn(bt1, self.edit_mgr.locked_files)
            self.assertIn(
                "Target `b_unit1.py` blamed `upstream_spec1.md`: Spec defect",
                resp_ok.content,
            )
            self.assertIn("- `b_unit3.py`", resp_ok.content)

            # Blame node3: blame target passed via target parameter -> terminates!
            b_ok3 = ActualParameterBindings(
                bindings={
                    (blame_tool.target, "upstream_spec3.md"),
                    (blame_tool.explanation, "Spec defect 3"),
                }
            )
            # Requirement: Tool execution defaults the blame target parameter to that target and the source target parameter to the session target configured with that blame target when the blame target parameter is omitted and the source target parameter matches a configured blame target.
            # Requirement: Tool execution marks the blame target as attributed and resolves the source target on successful tool execution.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When all session targets are resolved, resolving a target produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.
            resp_ok3 = blame_tool.execute_tool(b_ok3)
            self.assertFalse(resp_ok3.is_failed)
            self.assertTrue(resp_ok3.is_terminated)
            self.assertEqual(rc.get_node_state(node3), "BLAME")
            self.assertIn(b_rw3, self.edit_mgr.locked_files)
            self.assertNotIn(bt3, self.edit_mgr.locked_files)
            self.assertIn("Blamed upstream_spec3.md: Spec defect 3", resp_ok3.content)

    def test_check_file_with_src_parameter(self) -> None:
        """CUJ: CheckFileTool evaluates specific verification checks when src target is specified."""
        node1 = Node(unit_address="//pkg:rt_unit1", role_address="lib")
        node2 = Node(unit_address="//pkg:rt_unit2", role_address="lib")
        self.node_cfg.src_file_alias_by_node = {
            node1: "rt_unit1.py",
            node2: "rt_unit2.py",
        }
        vcheck1 = MockVerificationCheck(passes=True, diagnostic="Check 1 passed")
        vcheck2 = MockVerificationCheck(passes=False, diagnostic="Check 2 failed")
        self.node_cfg.verification_checks_by_node = {
            node1: [vcheck1],
            node2: [vcheck2],
        }

        with enter_phase(agent_session, registry=self.registry) as scope:
            check_file = scope.get_singleton(CheckFileTool)

            # Test target rt_unit1.py passes
            # Requirement: Executing the check file tool updates verification results if outdated and evaluates verification checks for that target.
            b1 = ActualParameterBindings(
                bindings={(check_file.src, TargetFileObj("rt_unit1.py"))}
            )
            resp1 = check_file.execute_tool(b1)
            self.assertFalse(resp1.is_failed)
            self.assertEqual(vcheck1.call_count, 1)
            self.assertEqual(vcheck2.call_count, 0)

            # Cached verification check evaluation for node without file revision updates
            resp1_cached = check_file.execute_tool(b1)
            self.assertFalse(resp1_cached.is_failed)
            self.assertEqual(vcheck1.call_count, 1)

            # Test target rt_unit2.py fails
            b2 = ActualParameterBindings(bindings={(check_file.src, "rt_unit2.py")})
            resp2 = check_file.execute_tool(b2)
            self.assertTrue(resp2.is_failed)
            self.assertEqual(vcheck2.call_count, 1)

            # Test target via path parameter alias
            b_path = ActualParameterBindings(bindings={(check_file.path, "rt_unit1.py")})
            resp_path = check_file.execute_tool(b_path)
            self.assertFalse(resp_path.is_failed)

            # Test target via invalid path parameter
            # Requirement: Tool execution fails when a target parameter is omitted and cannot be defaulted, or when the specified target parameter does not match an open session target, reminding the agent to specify an open target.
            b_bad = ActualParameterBindings(
                bindings={(check_file.path, "nonexistent.py")}
            )
            resp_bad = check_file.execute_tool(b_bad)
            self.assertTrue(resp_bad.is_failed)
            self.assertIn(
                "does not match an open session target", resp_bad.content
            )
            self.assertIsNotNone(resp_bad.reminder)
            assert resp_bad.reminder is not None
            self.assertIn("Specify an open target:", resp_bad.reminder)

            # When path parameter is omitted and multiple unsubmitted targets exist, fails if last accessed target is None
            b_empty = ActualParameterBindings(bindings=set())
            # Requirement: When the path parameter is omitted, the path parameter defaults using session target defaulting rules.
            resp_empty = check_file.execute_tool(b_empty)
            self.assertTrue(resp_empty.is_failed)
            self.assertIn("'path' must be specified when multiple unsubmitted targets exist", resp_empty.content)

            # When last read or written path is set to an open session target, defaults to it
            self.edit_mgr.last_read_or_edited_file = TargetFileObj("rt_unit1.py")
            self.edit_mgr.file_update_revision = 10
            # Requirement: When the path parameter is omitted, the path parameter defaults using session target defaulting rules.
            # Requirement: Executing the check file tool updates verification results if outdated and evaluates verification checks for that target.
            resp_def = check_file.execute_tool(b_empty)
            self.assertFalse(resp_def.is_failed)
            self.assertIn("Check 1 passed", resp_def.content)
            self.edit_mgr.last_read_or_edited_file = None

            # When exactly one unsubmitted target remains, defaults to that target
            rc = scope.get_singleton(RunControllerImpl)
            rc.set_node_state(node1, "SUBMITTED")
            self.edit_mgr.file_update_revision = 11

            # Specifying a target that is already SUBMITTED fails
            # Requirement: Tool execution fails when a target parameter is omitted and cannot be defaulted, or when the specified target parameter does not match an open session target, reminding the agent to specify an open target.
            b_closed = ActualParameterBindings(
                bindings={(check_file.path, "rt_unit1.py")}
            )
            resp_closed = check_file.execute_tool(b_closed)
            self.assertTrue(resp_closed.is_failed)
            self.assertIn(
                "does not match an open session target", resp_closed.content
            )
            self.assertIsNotNone(resp_closed.reminder)
            assert resp_closed.reminder is not None
            self.assertIn("Specify an open target: `rt_unit2.py`", resp_closed.reminder)

            # Requirement: When the path parameter is omitted, the path parameter defaults using session target defaulting rules.
            # Requirement: Executing the check file tool updates verification results if outdated and evaluates verification checks for that target.
            resp_one = check_file.execute_tool(b_empty)
            self.assertTrue(resp_one.is_failed)
            self.assertIn("Check 2 failed", resp_one.content)

    def test_check_file_tool_failing_verification_presents_diagnostics_and_instructions(
        self,
    ) -> None:
        """CUJ: CheckFileTool fails when verification fails, presenting sanitized diagnostics and failure instructions."""
        self.guide_del._guide = Guide(
            summary="Summary",
            sections=[],
            verification_failure="Inspect diagnostics and fix workspace files.",
        )
        vcheck = MockVerificationCheck(
            passes=False, diagnostic="Syntax error in /workspace/pkg/dep.py:12"
        )
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            check_file = scope.get_singleton(CheckFileTool)
            # Requirement: The check file tool is named `check_file`, accepting a path parameter (with src accepted as an alias), and shares a constant suppression key `check_file`.
            self.assertEqual(check_file.name, "check_file")
            self.assertEqual(check_file.parameters, {check_file.path, check_file.src})
            self.assertIsInstance(check_file.description, str)

            b = ActualParameterBindings(bindings=set())
            # Requirement: [RunController] The run controller installs a check file tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
            # Requirement: Tool execution fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.
            resp = check_file.execute_tool(b)

            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIn("dep.py:12", resp.content)
            self.assertNotIn("/workspace/pkg/", resp.content)
            self.assertIn(
                "## Verification failure\nInspect diagnostics and fix workspace files.",
                resp.content,
            )
            # Requirement: The check file tool is named `check_file`, accepting a path parameter (with src accepted as an alias), and shares a constant suppression key `check_file`.
            self.assertEqual(resp.suppression_key, "check_file")

    def test_check_file_tool_passing_verification_presents_results(self) -> None:
        """CUJ: CheckFileTool produces a passing response when verification passes."""
        vcheck = MockVerificationCheck(
            passes=True, diagnostic="All tests pass in /workspace/pkg/test.py"
        )
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            check_file = scope.get_singleton(CheckFileTool)
            b = ActualParameterBindings(bindings=set())
            # Requirement: [RunController] The run controller installs a check file tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
            # Requirement: Tool execution produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.
            resp = check_file.execute_tool(b)

            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIn("Verification passed", resp.content)
            self.assertIn("All tests pass in test.py", resp.content)
            # Requirement: The check file tool is named `check_file`, accepting a path parameter (with src accepted as an alias), and shares a constant suppression key `check_file`.
            self.assertEqual(resp.suppression_key, "check_file")

            # Custom verification_success_message
            # Requirement: Tool execution produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.
            self.node_cfg._verification_success_message = "Test test.py passed."
            self.edit_mgr.file_update_revision = 99
            resp2 = check_file.execute_tool(b)
            self.assertIn("Test test.py passed.", resp2.content)

    def test_check_file_tool_updates_verification_results_if_outdated(self) -> None:
        """CUJ: CheckFileTool caches verification results and re-evaluates when workspace files updated."""
        vcheck = MockVerificationCheck(passes=False, diagnostic="Error 1")
        self.node_cfg._verification_checks = [vcheck]
        self.edit_mgr.file_update_revision = 1

        with enter_phase(agent_session, registry=self.registry) as scope:
            check_file = scope.get_singleton(CheckFileTool)
            b = ActualParameterBindings(bindings=set())

            # First execution runs checks
            # Requirement: [RunController] The run controller installs a check file tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
            # Requirement: Executing the check file tool updates verification results if outdated and evaluates verification checks for that target.
            resp1 = check_file.execute_tool(b)
            self.assertTrue(resp1.is_failed)
            self.assertEqual(vcheck.call_count, 1)
            self.assertIsNone(resp1.reminder)
            self.assertIsNone(resp1.follow_up_tool_call)

            # Second execution without file updates reuses cache
            # Requirement: Tool execution reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when workspace files have not been updated since the previous check file tool execution.
            resp2 = check_file.execute_tool(b)
            self.assertTrue(resp2.is_failed)
            self.assertEqual(vcheck.call_count, 1)
            self.assertIsNotNone(resp2.reminder)
            assert resp2.reminder is not None
            self.assertIn(
                "Verification failed, no new information will be revealed",
                resp2.reminder,
            )

            # Third execution after file update re-evaluates
            self.edit_mgr.file_update_revision = 2
            vcheck.passes = True
            resp3 = check_file.execute_tool(b)
            self.assertFalse(resp3.is_failed)
            self.assertEqual(vcheck.call_count, 2)
            self.assertIsNone(resp3.reminder)
            self.assertIsNone(resp3.follow_up_tool_call)

    def test_check_file_tool_repeated_with_read_write_file_specifies_view_file_followup(
        self,
    ) -> None:
        """CUJ: Repeated check_file execution specifies follow-up read of the source file with view_file and reasoning."""
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]
        rw_file = ReadWriteFile(
            relative_path="src.py",
            workspace_path=_make_workspace_path("/workspace/src.py"),
            owning_node=Node(unit_address="//pkg:target", role_address="lib"),
        )
        self.node_cfg._read_write_files = {rw_file}
        self.edit_mgr.file_update_revision = 1

        with enter_phase(agent_session, registry=self.registry) as scope:
            check_file = scope.get_singleton(CheckFileTool)
            b = ActualParameterBindings(bindings=set())

            resp1 = check_file.execute_tool(b)
            self.assertFalse(resp1.is_failed)
            self.assertIsNone(resp1.reminder)
            self.assertIsNone(resp1.follow_up_tool_call)

            # Requirement: Tool execution reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when workspace files have not been updated since the previous check file tool execution.
            # Requirement: Tool execution specifies a follow-up execution of the view file tool on the session source file (resolving to the specified path target if a read-write file, the last accessed read-write file, or the primary session read-write file) and reasoning text noting that verification passed and to advance or submit the session if correct, or noting that verification failed until files are updated, when workspace files have not been updated since the previous check file tool execution.
            # When is_step_mode is False (default for coverage / non-step nodes), reasoning directs to submit
            self.node_cfg.is_step_mode = False
            resp2 = check_file.execute_tool(b)
            self.assertFalse(resp2.is_failed)
            self.assertIsNotNone(resp2.reminder)
            assert resp2.reminder is not None
            self.assertIn(
                "Verification passes, no new information will be revealed by this tool call until src.py is updated.",
                resp2.reminder,
            )
            self.assertIsNotNone(resp2.follow_up_tool_call)
            assert resp2.follow_up_tool_call is not None
            self.assertEqual(resp2.follow_up_tool_call.tool_name, "view_file")
            self.assertEqual(
                resp2.follow_up_tool_call.wire_parameter_bindings.bindings,
                {("path", "src.py")},
            )
            self.assertEqual(
                resp2.follow_up_tool_call.reasoning_text,
                "Oh, verification passes and no new information will be revealed by calling check_file again until files are updated. Let me read src.py again and see if I can figure out a different course of action. If it is already correct, I need to submit the agent session rather than check files again.",
            )

            # In step mode, reasoning directs the agent to advance rather than submit
            self.node_cfg.is_step_mode = True
            resp_step = check_file.execute_tool(b)
            assert resp_step.follow_up_tool_call is not None
            self.assertEqual(
                resp_step.follow_up_tool_call.reasoning_text,
                "Oh, verification passes and no new information will be revealed by calling check_file again until files are updated. Let me read src.py again and see if I can figure out a different course of action. If it is already correct, I need to advance the agent session rather than check files again.",
            )

            # When verification fails, reasoning indicates no more tests until files are updated
            vcheck.passes = False
            self.edit_mgr.file_update_revision = 2
            _ = check_file.execute_tool(b)
            resp_fail = check_file.execute_tool(b)
            assert resp_fail.follow_up_tool_call is not None
            self.assertEqual(
                resp_fail.follow_up_tool_call.reasoning_text,
                "Oh, verification failed and no new information will be revealed by calling check_file again until files are updated. Let me read src.py again and see if I can figure out a different course of action.",
            )

            # Multi-target session source file resolution:
            # 1. Resolves to specified path target when provided and matching read-write files
            rw2 = ReadWriteFile(
                relative_path="src2.py",
                workspace_path=_make_workspace_path("/workspace/src2.py"),
                owning_node=Node(unit_address="//pkg:target2", role_address="lib"),
            )
            self.node_cfg._read_write_files = {rw_file, rw2}
            self.edit_mgr.file_update_revision = 3
            b_target = ActualParameterBindings(bindings={(check_file.path, rw2)})
            _ = check_file.execute_tool(b_target)
            resp_target = check_file.execute_tool(b_target)
            assert resp_target.follow_up_tool_call is not None
            self.assertEqual(
                resp_target.follow_up_tool_call.wire_parameter_bindings.bindings,
                {("path", "src2.py")},
            )
            assert resp_target.reminder is not None
            self.assertIn("until src2.py is updated.", resp_target.reminder)

            # 2. Resolves to last accessed read-write file when target not specified
            self.edit_mgr.last_read_or_edited_file = rw2
            self.edit_mgr.file_update_revision = 4
            _ = check_file.execute_tool(b)
            resp_last = check_file.execute_tool(b)
            assert resp_last.follow_up_tool_call is not None
            self.assertEqual(
                resp_last.follow_up_tool_call.wire_parameter_bindings.bindings,
                {("path", "src2.py")},
            )
            assert resp_last.reminder is not None
            self.assertIn("until src2.py is updated.", resp_last.reminder)

    def test_default_target_resolution_with_read_write_files(self) -> None:
        """CUJ: RunController resolves default targets across single, multiple unsubmitted, and locked files."""
        node1 = Node(unit_address="//pkg:t1", role_address="lib")
        node2 = Node(unit_address="//pkg:t2", role_address="lib")
        rw1 = ReadWriteFile(
            relative_path="t1.py",
            workspace_path=_make_workspace_path("/workspace/t1.py"),
            owning_node=node1,
        )
        rw2 = ReadWriteFile(
            relative_path="t2.py",
            workspace_path=_make_workspace_path("/workspace/t2.py"),
            owning_node=node2,
        )
        ro_file = ReadOnlyFile(
            relative_path="readme.md",
            workspace_path=_make_workspace_path("/workspace/readme.md"),
            owning_node=Node(unit_address="//pkg:ro", role_address="doc"),
        )
        self.node_cfg._read_write_files = {rw1, rw2}
        vcheck1 = MockVerificationCheck(passes=True)
        vcheck2 = MockVerificationCheck(passes=True)
        self.node_cfg.verification_checks_by_node = {node1: [vcheck1], node2: [vcheck2]}

        with enter_phase(agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            check_file = scope.get_singleton(CheckFileTool)
            rc = scope.get_singleton(RunControllerImpl)

            b_empty = ActualParameterBindings(bindings=set())

            # 1. Multiple unsubmitted files, last_read_or_edited_file is None -> submit & check_file fail
            # Requirement: When a target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open session target.
            # Requirement: When the path parameter is omitted, the path parameter defaults using session target defaulting rules.
            resp_sub_fail = submit.execute_tool(b_empty)
            self.assertTrue(resp_sub_fail.is_failed)
            self.assertIn("Target parameter must be specified", resp_sub_fail.content)
            resp_chk_fail = check_file.execute_tool(b_empty)
            self.assertTrue(resp_chk_fail.is_failed)
            self.assertIn("'path' must be specified", resp_chk_fail.content)

            # 2. Multiple unsubmitted files, last_read_or_edited_file is read-only -> fails
            self.edit_mgr.last_read_or_edited_file = ro_file
            # Requirement: When a target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open session target.
            # Requirement: When the path parameter is omitted, the path parameter defaults using session target defaulting rules.
            self.assertTrue(submit.execute_tool(b_empty).is_failed)
            self.assertTrue(check_file.execute_tool(b_empty).is_failed)

            # 3. Multiple unsubmitted files, last_read_or_edited_file is rw1 -> defaults to rw1
            self.edit_mgr.last_read_or_edited_file = rw1
            # Requirement: When the path parameter is omitted, the path parameter defaults using session target defaulting rules.
            # Requirement: Executing the check file tool updates verification results if outdated and evaluates verification checks for that target.
            resp_chk_ok = check_file.execute_tool(b_empty)
            self.assertFalse(resp_chk_ok.is_failed)

            # Requirement: When a target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open session target.
            # Requirement: Tool execution marks the target as submitted and resolves the target.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When blame, submit, or fail is successfully called on a submit target and other submit targets remain, resolving the target produces a non-terminating response with a reminder listing remaining submit targets left for the agent to handle formatted via the template formatter.
            resp_sub_ok = submit.execute_tool(b_empty)
            self.assertFalse(resp_sub_ok.is_failed)
            self.assertEqual(rc.get_node_state(node1), "SUBMITTED")
            self.assertIn(rw1, self.edit_mgr.locked_files)

            # 4. Now rw1 is submitted and locked; last_read_or_edited_file is still rw1 (now locked)
            # Exactly one unsubmitted read-write file remains (rw2) -> defaults to rw2 even if last accessed was rw1
            # Requirement: When a target parameter is omitted, it defaults to the single session read-write file or remaining unsubmitted target.
            # Requirement: When the path parameter is omitted, the path parameter defaults using session target defaulting rules.
            # Requirement: Executing the check file tool updates verification results if outdated and evaluates verification checks for that target.
            self.edit_mgr.file_update_revision = 50
            resp_chk_rw2 = check_file.execute_tool(b_empty)
            self.assertFalse(resp_chk_rw2.is_failed)

            # Requirement: When a target parameter is omitted, it defaults to the single session read-write file or remaining unsubmitted target.
            # Requirement: Tool execution marks the target as submitted and resolves the target.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When all session targets are resolved, resolving a target produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.
            resp_sub_rw2 = submit.execute_tool(b_empty)
            self.assertFalse(resp_sub_rw2.is_failed)
            self.assertTrue(resp_sub_rw2.is_terminated)
            self.assertEqual(rc.get_node_state(node2), "SUBMITTED")
            self.assertIn(rw2, self.edit_mgr.locked_files)

    def test_multi_node_target_matching_by_alias_relative_path_and_unique_filename(
        self,
    ) -> None:
        """CUJ: Run controller matches session targets by alias, relative path, or unique filename across submit, check_file, fail, and blame."""
        node1 = Node(unit_address="//pkg:unit1", role_address="lib")
        node2 = Node(unit_address="//pkg:unit2", role_address="lib")
        node3 = Node(unit_address="//pkg2:unit2", role_address="lib")
        self.node_cfg.src_file_alias_by_node = {
            node1: "testing/parts/pkg/logs/unit1_qa.log",
            node2: "testing/parts/pkg/logs/unit2_qa.log",
            node3: "testing/parts/pkg2/logs/unit2_qa.log",
        }
        vcheck1 = MockVerificationCheck(passes=True)
        vcheck2 = MockVerificationCheck(passes=True)
        vcheck3 = MockVerificationCheck(passes=True)
        self.node_cfg.verification_checks_by_node = {
            node1: [vcheck1],
            node2: [vcheck2],
            node3: [vcheck3],
        }
        self.guide_del.has_steps_remaining = False

        with enter_phase(agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            check_file = scope.get_singleton(CheckFileToolImpl)
            fail = scope.get_singleton(FailToolImpl)
            rc = scope.get_singleton(RunControllerImpl)

            # Requirement: Session targets are matched by alias, relative path, or unique filename against open session targets.
            # 1. Look up by exact alias / relative path
            self.assertEqual(
                rc.get_node_for_alias("testing/parts/pkg/logs/unit1_qa.log"), node1
            )
            # 2. Look up by unit address
            self.assertEqual(rc.get_node_for_alias("//pkg:unit1"), node1)
            # 3. Look up by unique filename / basename
            self.assertEqual(rc.get_node_for_alias("unit1_qa.log"), node1)
            # 4. Ambiguous basename returns None (unit2_qa.log is shared by node2 and node3)
            self.assertIsNone(rc.get_node_for_alias("unit2_qa.log"))

            # 5. Check file tool accepts unique filename
            # Requirement: Executing the check file tool updates verification results if outdated and evaluates verification checks for that target.
            resp_chk = check_file.execute_tool(
                ActualParameterBindings(
                    bindings={(check_file.path, TargetFileObj("unit1_qa.log"))}
                )
            )
            self.assertFalse(resp_chk.is_failed)

            # 6. Submit tool accepts unique filename
            # Requirement: When all session targets are resolved, resolving a target produces a non-terminating response with a reminder to call the get work tool when mcp mode is active.
            resp_sub = submit.execute_tool(
                ActualParameterBindings(
                    bindings={
                        (submit.target, TargetFileObj("unit1_qa.log")),
                        (submit.change_summary, "Completed unit 1"),
                    }
                )
            )
            self.assertFalse(resp_sub.is_failed)
            self.assertEqual(rc.get_node_state(node1), "SUBMITTED")

            # 7. Fail tool accepts exact relative path for node2
            # Requirement: Executing the fail tool marks the target as failed and resolves the target.
            # Requirement: Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
            # Requirement: When all session targets are resolved, resolving a target produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.
            resp_fail = fail.execute_tool(
                ActualParameterBindings(
                    bindings={
                        (fail.target, "testing/parts/pkg/logs/unit2_qa.log"),
                        (fail.explanation, "Failing unit 2"),
                    }
                )
            )
            self.assertFalse(resp_fail.is_failed)
            self.assertEqual(rc.get_node_state(node2), "FAILED")

    def test_mcp_mode_non_terminating_resolutions(self) -> None:
        """CUJ: In MCP mode, submit, fail, and blame produce non-terminating responses with a reminder to call get_work when all targets are resolved."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]
        self.agent_cfg.is_mcp_mode = True

        with enter_phase(agent_session, registry=self.registry) as scope:
            submit = scope.get_singleton(SubmitToolImpl)
            # Requirement: When all session targets are resolved, resolving a target produces a non-terminating response with a reminder to call the get work tool when mcp mode is active.
            resp_sub = submit.execute_tool(
                ActualParameterBindings(
                    bindings={(submit.change_summary, "Added new feature")}
                )
            )
            self.assertFalse(resp_sub.is_failed)
            self.assertFalse(resp_sub.is_terminated)
            self.assertIn("get_work", resp_sub.reminder or "")

        # 2. Fail in MCP mode when all session targets resolved
        self.setUp()
        self.agent_cfg.is_mcp_mode = True
        with enter_phase(agent_session, registry=self.registry) as scope:
            fail = scope.get_singleton(FailToolImpl)
            # Requirement: When all session targets are resolved, resolving a target produces a non-terminating response with a reminder to call the get work tool when mcp mode is active.
            resp_fail = fail.execute_tool(
                ActualParameterBindings(
                    bindings={(fail.explanation, "Cannot solve bug")}
                )
            )
            self.assertTrue(resp_fail.is_failed)
            self.assertFalse(resp_fail.is_terminated)
            self.assertIn("get_work", resp_fail.reminder or "")

        # 3. Blame in MCP mode when all session targets resolved
        self.setUp()
        self.agent_cfg.is_mcp_mode = True
        with enter_phase(agent_session, registry=self.registry) as scope:
            blame = scope.get_singleton(BlameToolImpl)
            # Requirement: When all session targets are resolved, resolving a target produces a non-terminating response with a reminder to call the get work tool when mcp mode is active.
            resp_blame = blame.execute_tool(
                ActualParameterBindings(
                    bindings={
                        (blame.blame_target, self.blame_target_file),
                        (blame.explanation, "Broken type signature"),
                    }
                )
            )
            self.assertFalse(resp_blame.is_failed)
            self.assertFalse(resp_blame.is_terminated)
            self.assertIn("get_work", resp_blame.reminder or "")

    def test_get_work_tool_schema_and_open_targets_blocking(self) -> None:
        """CUJ: GetWorkTool schema defines name and max_batch_size parameter; execution fails when open session targets remain."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            rc = scope.get_singleton(RunControllerImpl)
            open_target = Node(unit_address="//pkg:open_target")
            rc.reset_nodes([open_target])
            get_work = scope.get_singleton(GetWorkToolImpl)
            self.assertEqual(get_work.name, "get_work")
            self.assertEqual(
                get_work.description,
                "Retrieves active dirty targets, materializes startup templates, and returns the session task prompt.",
            )
            param_names = {p.name for p in get_work.parameters}
            self.assertIn("max_batch_size", param_names)
            # Requirement: The get work tool is named `get_work`, accepting an integer max batch size parameter.
            self.assertEqual(get_work.max_batch_size.name, "max_batch_size")
            self.assertFalse(get_work.max_batch_size.is_required)

            # Requirement: Tool execution fails when open session targets remain, reminding the agent that open targets must be resolved before requesting new work.
            # Requirement: [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
            resp = get_work.execute_tool(ActualParameterBindings(bindings=set()))
            self.assertTrue(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertIn("Open session targets remain", resp.content)
            self.assertIn("must be resolved before requesting new work", resp.reminder or "")

    def test_get_work_idle_when_no_dirty_nodes_ready(self) -> None:
        """CUJ: When no open targets remain and no dirty nodes are ready in dag subgraph, get_work returns an idle response."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        with enter_phase(agent_session, registry=self.registry) as scope:
            rc = scope.get_singleton(RunControllerImpl)
            submit = scope.get_singleton(SubmitToolImpl)
            get_work = scope.get_singleton(GetWorkToolImpl)

            submit.execute_tool(
                ActualParameterBindings(
                    bindings={(submit.change_summary, "Done")}
                )
            )
            self.assertEqual(len(rc.open_nodes()), 0)

            self.subgraph.ready_batches = []
            self.subgraph.batch_index = 0

            # Requirement: Tool execution obtains dirty nodes from dag storage and dag subgraph, updating the active nodes and execution version on role config, when no open targets remain.
            # Requirement: Tool execution produces an idle response indicating that no dirty nodes are ready if no dirty nodes are ready for cleaning.
            resp = get_work.execute_tool(ActualParameterBindings(bindings=set()))
            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertEqual(resp.content, "No dirty nodes are ready for cleaning.")
            self.assertEqual(resp.reminder, "No dirty nodes are ready for cleaning.")

    def test_get_work_materializes_templates_and_delivers_task_prompt(self) -> None:
        """CUJ: When ready dirty nodes exist, get_work updates role config, materializes startup templates, and returns rendered task prompt."""
        self.guide_del.has_steps_remaining = False
        self.edit_mgr.has_modifications = True
        vcheck = MockVerificationCheck(passes=True)
        self.node_cfg._verification_checks = [vcheck]

        node_a = Node(unit_address="//pkg:unit_a", role_address="lib")
        node_b = Node(unit_address="//pkg:unit_b", role_address="lib")
        self.subgraph.ready_batches = [[node_a, node_b]]
        self.subgraph.batch_index = 0

        self.storage.dirty_nodes = {node_a, node_b}
        self.storage.node_definitions = {
            node_a: MockNodeDefinition(task_prompt="Clean unit A"),
            node_b: MockNodeDefinition(task_prompt="Clean unit B"),
        }
        self.storage.messages = {
            node_a: [dag_storage.Feedback(content="Fix linter in unit A")],
            node_b: [],
        }

        with enter_phase(agent_session, registry=self.registry) as scope:
            rc = scope.get_singleton(RunControllerImpl)
            submit = scope.get_singleton(SubmitToolImpl)
            get_work = scope.get_singleton(GetWorkToolImpl)

            # Resolve existing open target
            submit.execute_tool(
                ActualParameterBindings(
                    bindings={(submit.change_summary, "Done")}
                )
            )
            self.assertEqual(len(rc.open_nodes()), 0)

            # Call get_work with max_batch_size = 1
            # Requirement: [Tool] When a parameter is required, an argument must be supplied for tool execution.
            # Requirement: The get work tool is named `get_work`, accepting an integer max batch size parameter.
            # Requirement: Tool execution obtains dirty nodes from dag storage and dag subgraph, updating the active nodes and execution version on role config, when no open targets remain.
            # Requirement: Tool execution materializes startup templates on disk, constructs the task prompt from dirty node definitions, guide instructions, and incoming messages from dag storage formatted via the template formatter, and returns the rendered task prompt when ready dirty nodes are obtained.
            initial_version = self.role_cfg.execution_version
            resp = get_work.execute_tool(
                ActualParameterBindings(
                    bindings={(get_work.max_batch_size, 1)}
                )
            )
            self.assertFalse(resp.is_failed)
            self.assertFalse(resp.is_terminated)
            self.assertTrue(self.sb.materialize_startup_templates_called)
            self.assertEqual(self.role_cfg.active_nodes, [node_a])
            self.assertEqual(self.role_cfg.execution_version, initial_version + 1)
            self.assertIn("Clean unit A", resp.content)
            self.assertIn("Fix linter in unit A", resp.content)
            self.assertEqual(rc.open_nodes(), [node_a])


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
