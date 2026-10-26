"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for AttributionCoordinator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.control.lib.attribution import (
    AttributionCoordinator,
    AttributionOutcome,
)
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress


@dataclass
class AttributionState:
    """Canonical model state for defect attribution and failure routing."""
    feedbacks: PretenseDict[DagNode, List[str]] = field(default_factory=PretenseDict)
    file_feedbacks: PretenseDict[str, List[str]] = field(default_factory=PretenseDict)
    dirty_nodes: PretenseSet[DagNode] = field(default_factory=PretenseSet)
    failed_nodes: PretenseSet[DagNode] = field(default_factory=PretenseSet)


proto = StateMachineProto[AttributionState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_attribution_node(): pass

@seed_attribution_node.arguments
def _(
    state: AttributionState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
    is_dirty: bool | NotBoundType = NotBound,
    is_failed: bool | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, bool, bool]]:
    n = DagNode(UnitAddress("target"), RoleAddress("lib")) if isinstance(node, NotBoundType) else node
    d = False if isinstance(is_dirty, NotBoundType) else bool(is_dirty)
    f = False if isinstance(is_failed, NotBoundType) else bool(is_failed)
    return (n, d, f)

@seed_attribution_node.provide
def _(
    state: AttributionState,
    this: Any,
    node: DagNode,
    is_dirty: bool,
    is_failed: bool,
    result: None = None,
) -> None:
    if is_dirty:
        state.dirty_nodes.add(node)
    else:
        state.dirty_nodes.discard(node)
    if is_failed:
        state.failed_nodes.add(node)
    else:
        state.failed_nodes.discard(node)


# ==============================================================================
# 2. AttributionCoordinator Transitions
# ==============================================================================

@proto.transition(AttributionCoordinator.blame_target)
def blame_target(): pass

@blame_target.arguments
def _(
    state: AttributionState,
    this: Any,
    source_node: DagNode | NotBoundType = NotBound,
    blame_target_node: DagNode | NotBoundType = NotBound,
    explanation: str | NotBoundType = NotBound,
    in_batch_dependencies: Optional[Sequence[DagNode]] | NotBoundType = NotBound,
    in_batch_dependents: Optional[Sequence[DagNode]] | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, DagNode, str, Optional[Sequence[DagNode]], Optional[Sequence[DagNode]]]]:
    src = DagNode(UnitAddress("src"), RoleAddress("test")) if isinstance(source_node, NotBoundType) else source_node
    tgt = DagNode(UnitAddress("tgt"), RoleAddress("lib")) if isinstance(blame_target_node, NotBoundType) else blame_target_node
    exp = "Defect detected in contract" if isinstance(explanation, NotBoundType) else str(explanation)
    in_deps = None if isinstance(in_batch_dependencies, NotBoundType) else in_batch_dependencies
    in_downs = None if isinstance(in_batch_dependents, NotBoundType) else in_batch_dependents
    return (src, tgt, exp, in_deps, in_downs)

@blame_target.returns
def _(
    state: AttributionState,
    this: Any,
    source_node: DagNode,
    blame_target_node: DagNode,
    explanation: str,
    in_batch_dependencies: Optional[Sequence[DagNode]],
    in_batch_dependents: Optional[Sequence[DagNode]],
    outcome: object = NotBound,
) -> Optional[Outcome[AttributionOutcome]]:
    # Invariant: critique must be single paragraph
    if "\n" in explanation.strip():
        expected = AttributionOutcome(
            accepted=False,
            message="Critique must be a single paragraph without newline characters",
            affected_nodes=(),
        )
    # Invariant: self-blame is disallowed
    elif source_node == blame_target_node:
        expected = AttributionOutcome(
            accepted=False,
            message=f"Cannot blame target {blame_target_node}: self-blame is disallowed",
            affected_nodes=(),
        )
    else:
        affected = [blame_target_node]
        if in_batch_dependents:
            affected.extend(in_batch_dependents)
        expected = AttributionOutcome(
            accepted=True,
            message=f"Blame successfully attributed to {blame_target_node}",
            affected_nodes=tuple(affected),
        )

    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@blame_target.provide
def _(
    state: AttributionState,
    this: Any,
    source_node: DagNode,
    blame_target_node: DagNode,
    explanation: str,
    in_batch_dependencies: Optional[Sequence[DagNode]],
    in_batch_dependents: Optional[Sequence[DagNode]],
    result: AttributionOutcome,
) -> None:
    if result.accepted:
        state.feedbacks.setdefault(blame_target_node, []).append(explanation)
        state.dirty_nodes.add(blame_target_node)
        state.failed_nodes.add(source_node)
        if in_batch_dependents:
            for dep in in_batch_dependents:
                state.failed_nodes.add(dep)


@proto.transition(AttributionCoordinator.fail_target)
def fail_target(): pass

@fail_target.arguments
def _(
    state: AttributionState,
    this: Any,
    target_node: DagNode | NotBoundType = NotBound,
    explanation: str | NotBoundType = NotBound,
    in_batch_dependents: Optional[Sequence[DagNode]] | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, str, Optional[Sequence[DagNode]]]]:
    tgt = DagNode(UnitAddress("node"), RoleAddress("lib")) if isinstance(target_node, NotBoundType) else target_node
    exp = "Task failed to converge" if isinstance(explanation, NotBoundType) else str(explanation)
    in_downs = None if isinstance(in_batch_dependents, NotBoundType) else in_batch_dependents
    return (tgt, exp, in_downs)

@fail_target.returns
def _(
    state: AttributionState,
    this: Any,
    target_node: DagNode,
    explanation: str,
    in_batch_dependents: Optional[Sequence[DagNode]],
    outcome: object = NotBound,
) -> Optional[Outcome[AttributionOutcome]]:
    affected = [target_node]
    if in_batch_dependents:
        affected.extend(in_batch_dependents)
    expected = AttributionOutcome(
        accepted=True,
        message=f"Failure recorded for node {target_node}",
        affected_nodes=tuple(affected),
    )
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@fail_target.provide
def _(
    state: AttributionState,
    this: Any,
    target_node: DagNode,
    explanation: str,
    in_batch_dependents: Optional[Sequence[DagNode]],
    result: AttributionOutcome,
) -> None:
    state.failed_nodes.add(target_node)
    state.feedbacks.setdefault(target_node, []).append(explanation)
    if in_batch_dependents:
        for dep in in_batch_dependents:
            state.failed_nodes.add(dep)


@proto.transition(AttributionCoordinator.blame_culprit_file)
def blame_culprit_file(): pass

@blame_culprit_file.arguments
def _(
    state: AttributionState,
    this: Any,
    culprit_file: str | NotBoundType = NotBound,
    critique: str | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
    workspace_root: Optional[str] | NotBoundType = NotBound,
    caller_role: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, Optional[str], Optional[str], Optional[str]]]:
    c = "lib/module.py" if isinstance(culprit_file, NotBoundType) else str(culprit_file)
    q = "Missing edge case handling" if isinstance(critique, NotBoundType) else str(critique)
    r = None if isinstance(repo_root, NotBoundType) else repo_root
    w = None if isinstance(workspace_root, NotBoundType) else workspace_root
    role = None if isinstance(caller_role, NotBoundType) else caller_role
    return (c, q, r, w, role)

@blame_culprit_file.returns
def _(
    state: AttributionState,
    this: Any,
    culprit_file: str,
    critique: str,
    repo_root: Optional[str],
    workspace_root: Optional[str],
    caller_role: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[AttributionOutcome]]:
    if "\n" in critique.strip():
        expected = AttributionOutcome(
            accepted=False,
            message="Critique must be a single paragraph without newline characters",
            affected_nodes=(),
        )
    else:
        expected = AttributionOutcome(
            accepted=True,
            message=f"Blame attributed to file {culprit_file}",
            affected_nodes=(),
        )
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@blame_culprit_file.provide
def _(
    state: AttributionState,
    this: Any,
    culprit_file: str,
    critique: str,
    repo_root: Optional[str],
    workspace_root: Optional[str],
    caller_role: Optional[str],
    result: AttributionOutcome,
) -> None:
    if result.accepted:
        state.file_feedbacks.setdefault(culprit_file, []).append(critique)


@proto.transition(AttributionCoordinator.fail_target_file)
def fail_target_file(): pass

@fail_target_file.arguments
def _(
    state: AttributionState,
    this: Any,
    target_file: str | NotBoundType = NotBound,
    reason: Optional[str] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
    workspace_root: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, Optional[str], Optional[str], Optional[str]]]:
    t = "lib/module.py" if isinstance(target_file, NotBoundType) else str(target_file)
    r = "Verification failed" if isinstance(reason, NotBoundType) or reason is None else str(reason)
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    w = None if isinstance(workspace_root, NotBoundType) else workspace_root
    return (t, r, rr, w)

@fail_target_file.returns
def _(
    state: AttributionState,
    this: Any,
    target_file: str,
    reason: Optional[str],
    repo_root: Optional[str],
    workspace_root: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[AttributionOutcome]]:
    expected = AttributionOutcome(
        accepted=True,
        message=f"Failure recorded for file {target_file}",
        affected_nodes=(),
    )
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@fail_target_file.provide
def _(
    state: AttributionState,
    this: Any,
    target_file: str,
    reason: Optional[str],
    repo_root: Optional[str],
    workspace_root: Optional[str],
    result: AttributionOutcome,
) -> None:
    if reason:
        state.file_feedbacks.setdefault(target_file, []).append(reason)


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_attribution_fake(state: Optional[AttributionState] = None) -> AttributionCoordinator:
    """Instantiate a synthesized AttributionCoordinator fake."""
    st = state or AttributionState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(AttributionCoordinator)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

import os
import tempfile
from update_with_ai.parts.control.lib import attribution_impl
from update_with_ai.parts.agent.lib import file_alias, node_config
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton
from update_with_ai.parts.agent.lib.session import agent_session
from update_with_ai.parts.core.lib import file_paths


class MockDagStorageReal:
    tier = agent_session

    def __init__(self) -> None:
        self.dependencies: Dict[DagNode, List[Any]] = {}
        self.dirty_nodes: Set[DagNode] = set()
        self.feedbacks: Dict[DagNode, List[Any]] = {}

    def get_dependencies(self, node: DagNode) -> List[Any]:
        return self.dependencies.get(node, [])

    def is_dirty(self, node: DagNode) -> bool:
        return node in self.dirty_nodes

    def add_feedback_message(self, node: DagNode, msg: Any) -> None:
        self.feedbacks.setdefault(node, []).append(msg)

    def mark_node_dirty(self, node: DagNode, reason: str = "") -> None:
        self.dirty_nodes.add(node)


class MockNodeConfigReal:
    tier = agent_session

    def __init__(self) -> None:
        self.blame_targets_by_node: Dict[DagNode, Set[Any]] = {}
        self.role_definitions: Dict[str, Any] = {
            "test": {
                "role_name": "test",
                "src_pattern": "{unit_dir}/tests/{unit_name}_test.py",
                "feedback_role_deps": ["lib"],
            },
            "lib": {
                "role_name": "lib",
                "src_pattern": "{unit_dir}/lib/{unit_name}.py",
                "feedback_role_deps": [],
            },
        }


class MockAliasManagerReal:
    tier = agent_session

    def to_alias(self, path: str) -> Any:
        return file_alias.FileAlias(file_alias.RelativePath(path))


@dataclass
class MockDep:
    node: DagNode


class TestAttributionImplReal(unittest.TestCase):
    """Direct unit tests for attribution_impl.AttributionCoordinator."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        attribution_impl.__initialize__(self.registry)

        self.mock_storage = MockDagStorageReal()
        self.mock_node_cfg = MockNodeConfigReal()
        self.mock_alias_mgr = MockAliasManagerReal()

        self.registry.register_instance(self.mock_storage, keys=[dag_storage.DagStorage], tier=agent_session)
        self.registry.register_instance(self.mock_node_cfg, keys=[node_config.NodeConfig], tier=agent_session)
        self.registry.register_instance(self.mock_alias_mgr, keys=[file_alias.AliasManager], tier=agent_session)

        self.src = DagNode(UnitAddress("pkg:calc"), RoleAddress("test"))
        self.tgt = DagNode(UnitAddress("pkg:calc"), RoleAddress("lib"))

    def test_match_blame_target(self) -> None:
        ws_root = file_paths.WorkspaceRoot(file_paths.PathString("/ws"))
        ws_path = file_paths.WorkspacePath(file_paths.PathString("pkg/lib/calc.py"))
        bound = file_alias.BoundFile(file_alias.RelativePath("pkg/lib/calc.py"), ws_path, owning_node=self.tgt)
        self.mock_node_cfg.blame_targets_by_node[self.src] = {bound}

        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(attribution_impl.AttributionCoordinator)

            # 1. Exact value match
            self.assertEqual(coord.match_blame_target(self.src, bound, "pkg/lib/calc.py"), bound)

            # 2. String alias match
            self.assertEqual(coord.match_blame_target(self.src, None, "pkg/lib/calc.py"), bound)

            # 3. Suffix match
            self.assertEqual(coord.match_blame_target(self.src, None, "lib/calc.py"), bound)

            # 4. Basename match
            self.assertEqual(coord.match_blame_target(self.src, None, "other/dir/calc.py"), bound)

            # 5. No match
            self.assertIsNone(coord.match_blame_target(self.src, None, "unrelated.py"))

    def test_blame_target_rejections_and_success(self) -> None:
        self.mock_storage.dependencies[self.src] = [MockDep(node=self.tgt)]

        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(attribution_impl.AttributionCoordinator)

            # 1. Newline rejection
            outcome = coord.blame_target(self.src, self.tgt, "Line 1\nLine 2")
            self.assertFalse(outcome.accepted)
            self.assertIn("single paragraph", outcome.message)

            # 2. Not an upstream dependency
            unrelated = DagNode(UnitAddress("pkg:other"), RoleAddress("lib"))
            outcome = coord.blame_target(self.src, unrelated, "Critique")
            self.assertFalse(outcome.accepted)
            self.assertIn("not an upstream dependency", outcome.message)

            # 3. Role not configured for feedback
            lib_to_test = DagNode(UnitAddress("pkg:calc"), RoleAddress("lib"))
            test_target = DagNode(UnitAddress("pkg:calc"), RoleAddress("test"))
            self.mock_storage.dependencies[lib_to_test] = [MockDep(node=test_target)]
            outcome = coord.blame_target(lib_to_test, test_target, "Critique")
            self.assertFalse(outcome.accepted)
            self.assertIn("not configured to deliver feedback", outcome.message)

            # 4. In-batch dependency is dirty
            in_batch_dep = DagNode(UnitAddress("pkg:dep"), RoleAddress("lib"))
            self.mock_storage.dirty_nodes.add(in_batch_dep)
            outcome = coord.blame_target(
                self.src, self.tgt, "Critique", in_batch_dependencies=[in_batch_dep]
            )
            self.assertFalse(outcome.accepted)
            self.assertIn("must be submitted before dependent targets", outcome.message)

            # 5. Successful blame target
            self.mock_storage.dirty_nodes.clear()
            downstream = DagNode(UnitAddress("pkg:downstream"), RoleAddress("qa"))
            outcome = coord.blame_target(
                self.src, self.tgt, "Contract violated on zero input", in_batch_dependents=[downstream]
            )
            self.assertTrue(outcome.accepted)
            self.assertIn("Defect attributed to upstream dependency", outcome.message)
            self.assertIn(self.tgt, self.mock_storage.dirty_nodes)
            self.assertEqual(len(self.mock_storage.feedbacks[self.tgt]), 1)
            self.assertIn(self.src, outcome.affected_nodes)
            self.assertIn(downstream, outcome.affected_nodes)

    def test_fail_target(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(attribution_impl.AttributionCoordinator)
            downstream = DagNode(UnitAddress("pkg:downstream"), RoleAddress("qa"))
            outcome = coord.fail_target(self.src, "Timeout exceeded", in_batch_dependents=[downstream])
            self.assertTrue(outcome.accepted)
            self.assertIn(self.src, self.mock_storage.dirty_nodes)
            self.assertEqual(len(self.mock_storage.feedbacks[self.src]), 1)
            self.assertIn(self.src, outcome.affected_nodes)
            self.assertIn(downstream, outcome.affected_nodes)

    def test_blame_culprit_file_and_fail_target_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = os.path.join(tmp_dir, "repo")
            ws_root = os.path.join(tmp_dir, "ws")
            os.makedirs(os.path.join(repo_root, "pkg/lib"), exist_ok=True)
            os.makedirs(os.path.join(repo_root, "pkg/tests"), exist_ok=True)
            os.makedirs(os.path.join(ws_root, "pkg/lib"), exist_ok=True)

            lib_file = os.path.join(repo_root, "pkg/lib/calc.py")
            with open(lib_file, "w", encoding="utf-8") as f:
                f.write("# --- CLEANROOM METADATA ---\n# --- END CLEANROOM METADATA ---\ndef calc(): pass\n")

            ws_lib_file = os.path.join(ws_root, "pkg/lib/calc.py")
            with open(ws_lib_file, "w", encoding="utf-8") as f:
                f.write("# --- CLEANROOM METADATA ---\n# --- END CLEANROOM METADATA ---\ndef calc(): pass\n")

            # Write role metadata in workspace
            role_json = os.path.join(ws_root, ".cleanroom_role.json")
            import json
            with open(role_json, "w", encoding="utf-8") as f:
                json.dump({"role_name": "test", "max_feedback_chars": 50}, f)

            with enter_phase(agent_session, registry=self.registry) as scope:
                coord = scope.get_singleton(attribution_impl.AttributionCoordinator)

                # 1. Newline in critique
                res = coord.blame_culprit_file("pkg/lib/calc.py", "line 1\nline 2", repo_root=repo_root, workspace_root=ws_root)
                self.assertFalse(res.accepted)
                self.assertIn("single line/paragraph", res.message)

                # 2. Exceeds max_feedback_chars
                long_critique = "A" * 60
                res = coord.blame_culprit_file("pkg/lib/calc.py", long_critique, repo_root=repo_root, workspace_root=ws_root)
                self.assertFalse(res.accepted)
                self.assertIn("exceeds maximum length", res.message)

                # 3. File not found
                res = coord.blame_culprit_file("pkg/lib/nonexistent.py", "Fix bug", repo_root=repo_root, workspace_root=ws_root)
                self.assertFalse(res.accepted)
                self.assertIn("Could not locate", res.message)

                # 4. Caller role not allowed to blame
                res = coord.blame_culprit_file(
                    "pkg/lib/calc.py", "Fix bug", repo_root=repo_root, workspace_root=ws_root, caller_role="lib"
                )
                self.assertFalse(res.accepted)
                self.assertIn("not configured to deliver feedback", res.message)

                # 5. Successful blame_culprit_file
                res = coord.blame_culprit_file(
                    "pkg/lib/calc.py", "Contract return mismatch", repo_root=repo_root, workspace_root=ws_root, caller_role="test"
                )
                self.assertTrue(res.accepted)
                self.assertIn("[BLAME]", res.message)

                # 6. fail_target_file nonexistent
                res = coord.fail_target_file("pkg/lib/missing.py", repo_root=repo_root, workspace_root=ws_root)
                self.assertFalse(res.accepted)
                self.assertIn("not found", res.message)

                # 7. fail_target_file success
                res = coord.fail_target_file("pkg/lib/calc.py", reason="Syntax failure", repo_root=repo_root, workspace_root=ws_root)
                self.assertTrue(res.accepted)
                self.assertIn("Marked failure", res.message)

    def test_helpers(self) -> None:
        d_name, pfx, sfx = attribution_impl._parse_pattern_info("{unit_dir}/tests/test_{unit_name}.py")
        self.assertEqual(d_name, "tests")
        self.assertEqual(pfx, "test_")
        self.assertEqual(sfx, ".py")

        d_name2, pfx2, sfx2 = attribution_impl._parse_pattern_info("{unit_dir}/lib/*.py")
        self.assertEqual(d_name2, "lib")
        self.assertEqual(pfx2, "")
        self.assertEqual(sfx2, ".py")

        empty_p = attribution_impl._parse_pattern_info("")
        self.assertEqual(empty_p, ("", "", ""))

        with enter_phase(agent_session, registry=self.registry):
            role = attribution_impl._resolve_file_role("pkg/lib/calc.py")
            self.assertEqual(role, "lib")

            with self.assertRaises(ValueError):
                attribution_impl._resolve_file_role("pkg/unknown_dir/calc.xyz")

        # _role_audit_tag
        self.assertIsNone(attribution_impl._role_audit_tag({}))
        self.assertEqual(attribution_impl._role_audit_tag({"audit_tag": "spec"}), "spec")

        # _bound_file_path
        ws_root = file_paths.WorkspaceRoot(file_paths.PathString("/ws"))
        ws_path = file_paths.WorkspacePath(file_paths.PathString("dir/file.py"))
        bound = file_alias.BoundFile(file_alias.RelativePath("dir/file.py"), ws_path, owning_node=self.tgt)
        self.assertEqual(attribution_impl._bound_file_path(bound), "dir/file.py")
        self.assertEqual(attribution_impl._bound_file_path("simple.py"), "simple.py")

        with enter_phase(agent_session, registry=self.registry):
            # _node_display_alias branches
            n_slash = DagNode(UnitAddress("pkg/calc"), RoleAddress("lib"))
            self.assertEqual(attribution_impl._node_display_alias(n_slash), "pkg/lib/calc.py")
            n_plain = DagNode(UnitAddress("calc"), RoleAddress("lib"))
            self.assertEqual(attribution_impl._node_display_alias(n_plain), "lib/calc.py")
            n_norole = DagNode(UnitAddress("pkg/calc"), RoleAddress(""))
            self.assertEqual(attribution_impl._node_display_alias(n_norole), "pkg/calc")

        # _resolve_target_path
        self.assertTrue(os.path.isabs(attribution_impl._resolve_target_path("/abs/path", "/repo")))
        self.assertTrue(os.path.isabs(attribution_impl._resolve_target_path("rel/path", "/repo")))

    def test_model_configs_toml_in_blame_culprit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = os.path.join(tmp_dir, "repo")
            ws_root = os.path.join(tmp_dir, "ws")
            os.makedirs(os.path.join(repo_root, "pkg/lib"), exist_ok=True)
            os.makedirs(ws_root, exist_ok=True)

            lib_file = os.path.join(repo_root, "pkg/lib/calc.py")
            with open(lib_file, "w", encoding="utf-8") as f:
                f.write("# --- CLEANROOM METADATA ---\n# --- END CLEANROOM METADATA ---\ndef calc(): pass\n")

            # Write model_configs.toml in repo_root with max_feedback_chars
            toml_path = os.path.join(repo_root, "model_configs.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write('default = "test_model"\n[models.test_model]\nmax_feedback_chars = 30\n')

            with enter_phase(agent_session, registry=self.registry) as scope:
                coord = scope.get_singleton(attribution_impl.AttributionCoordinator)
                # Critique longer than 30 chars rejected via model_configs.toml threshold
                res = coord.blame_culprit_file(
                    "pkg/lib/calc.py",
                    "This critique is definitely longer than thirty chars",
                    repo_root=repo_root,
                    workspace_root=ws_root,
                    caller_role="test",
                )
                self.assertFalse(res.accepted)
                self.assertIn("exceeds maximum length of 30 characters", res.message)


class TestAttributionCoordinatorUnit(unittest.TestCase):
    """Unit tests for synthesized AttributionCoordinator fake."""

    def setUp(self) -> None:
        self.state = AttributionState()
        self.sm = proto.make_state_machine(self.state)
        self.src = DagNode(UnitAddress("part_test"), RoleAddress("test"))
        self.tgt = DagNode(UnitAddress("part_lib"), RoleAddress("lib"))
        self.fake: AttributionCoordinator = self.sm.as_fake(AttributionCoordinator)

    def test_blame_target_success(self) -> None:
        outcome = self.fake.blame_target(self.src, self.tgt, "Incorrect return value on empty list")
        self.assertTrue(outcome.accepted)
        self.assertIn(self.tgt, outcome.affected_nodes)
        self.assertIn(self.tgt, self.state.dirty_nodes)
        self.assertIn(self.src, self.state.failed_nodes)
        self.assertEqual(self.state.feedbacks[self.tgt], ["Incorrect return value on empty list"])

    def test_blame_target_rejects_self_blame(self) -> None:
        outcome = self.fake.blame_target(self.src, self.src, "Self blame attempt")
        self.assertFalse(outcome.accepted)
        self.assertIn("self-blame is disallowed", outcome.message)

    def test_blame_target_rejects_newlines_in_critique(self) -> None:
        outcome = self.fake.blame_target(self.src, self.tgt, "Line 1\nLine 2")
        self.assertFalse(outcome.accepted)
        self.assertIn("single paragraph", outcome.message)

    def test_fail_target(self) -> None:
        downstream = DagNode(UnitAddress("part_downstream"), RoleAddress("qa"))
        outcome = self.fake.fail_target(self.src, "Exceeded turns", in_batch_dependents=[downstream])
        self.assertTrue(outcome.accepted)
        self.assertIn(self.src, self.state.failed_nodes)
        self.assertIn(downstream, self.state.failed_nodes)
        self.assertEqual(self.state.feedbacks[self.src], ["Exceeded turns"])


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestAttributionCoordinatorFuzz(unittest.TestCase):
    """Property fuzz testing for AttributionCoordinator."""

    @settings(max_examples=30)
    @given(
        critique=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _-."),
        has_newline=st.booleans(),
    )
    def test_newline_rejection_invariant(self, critique: str, has_newline: bool) -> None:
        fake = make_attribution_fake()
        src = DagNode(UnitAddress("src"), RoleAddress("test"))
        tgt = DagNode(UnitAddress("tgt"), RoleAddress("lib"))

        full_critique = f"{critique}\nMore text" if has_newline else critique
        outcome = fake.blame_target(src, tgt, full_critique)

        if has_newline:
            self.assertFalse(outcome.accepted)
            self.assertIn("single paragraph", outcome.message)
        else:
            self.assertTrue(outcome.accepted)
