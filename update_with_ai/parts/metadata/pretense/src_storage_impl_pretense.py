"""Pretense state machine, fake synthesis, unit tests, and fuzzing for AgentStorage in src_storage_impl."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import node_storage
from update_with_ai.parts.agent.lib.node_storage import (
    AgentStorage,
    NodeDefinition,
    TaskPrompt,
)
from update_with_ai.parts.core.lib.file_paths import (
    AbsolutePath,
    FilePathManager,
    HostPath,
    PathString,
    WorkspacePath,
    WorkspaceRoot,
)
from update_with_ai.parts.dag.lib.dag_storage import (
    ChangeDescription,
    ChangeMessage,
    DagDependency,
    DagMessage,
    DagNode,
    DagStorage,
    FeedbackMessage,
    MessageContent,
    RoleAddress,
    UnitAddress,
)
from update_with_ai.parts.metadata.lib import src_metadata, src_metadata_impl
from update_with_ai.parts.metadata.lib.src_storage_impl import (
    AgentStorage as AgentStorageImpl,
    __initialize__,
)


def _make_dag_node(unit_address: str, role_address: str = "") -> DagNode:
    return DagNode(
        unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address)
    )


class FakeSourceMetadataCoordinator:
    tier = "system"

    def __init__(self) -> None:
        self.metadata: dict[str, src_metadata.FileMetadata] = {}

    def _now(self) -> str:
        return src_metadata.current_utc_timestamp()

    def _write_disk(self, file_path: str, meta: src_metadata.FileMetadata) -> None:
        is_html = file_path.endswith(".md")
        lines: list[str] = []
        if is_html:
            lines.append("<!-- CLEANROOM METADATA")
            if meta.last_cleaned:
                lines.append(f"LAST_CLEANED: {meta.last_cleaned}")
            if meta.last_changed:
                lines.append(f"LAST_CHANGED: {meta.last_changed}")
            if meta.change_summary:
                lines.append(f"CHANGE: {meta.change_summary}")
            if meta.code_hash:
                lines.append(f"CODE_HASH: {meta.code_hash}")
            if meta.dirty:
                lines.append(f"DIRTY: {meta.dirty}")
            for k, v in sorted(meta.audits.items()):
                lines.append(f"{k}: {v}")
            if meta.feedback:
                lines.append("FEEDBACK:")
                for fb in meta.feedback:
                    lines.append(f"- {fb}")
            lines.append("-->\n")
        else:
            lines.append("# --- CLEANROOM METADATA ---")
            if meta.last_cleaned:
                lines.append(f"# LAST_CLEANED: {meta.last_cleaned}")
            if meta.last_changed:
                lines.append(f"# LAST_CHANGED: {meta.last_changed}")
            if meta.change_summary:
                lines.append(f"# CHANGE: {meta.change_summary}")
            if meta.code_hash:
                lines.append(f"# CODE_HASH: {meta.code_hash}")
            if meta.dirty:
                lines.append(f"# DIRTY: {meta.dirty}")
            for k, v in sorted(meta.audits.items()):
                lines.append(f"# {k}: {v}")
            if meta.feedback:
                lines.append("# FEEDBACK:")
                for fb in meta.feedback:
                    lines.append(f"# - {fb}")
            lines.append("# --- END CLEANROOM METADATA ---\n")

        body = ""
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                raw_lines = content.splitlines()
                bounds = src_metadata._extract_block_boundaries(raw_lines, is_html)
                if bounds:
                    b_lines = raw_lines[: bounds[0]] + raw_lines[bounds[1] + 1 :]
                    body = "\n".join(b_lines).strip()
                else:
                    body = content.strip()
            except Exception:
                body = ""
        full = (body + "\n\n" if body else "") + "\n".join(lines)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full)

    def extract_metadata(self, file_path: Any) -> Optional[src_metadata.FileMetadata]:
        p = str(file_path)
        if p in self.metadata:
            return self.metadata[p]
        if not os.path.isfile(p):
            return None
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        return src_metadata.extract_metadata_from_text(content, os.path.basename(p))

    def mark_dirty(self, file_path: Any, reason: str = "") -> None:
        p = str(file_path)
        cur = self.extract_metadata(p)
        ts = self._now()
        meta = src_metadata.FileMetadata(
            last_cleaned=cur.last_cleaned if cur else None,
            last_changed=cur.last_changed if cur else ts,
            change_summary=cur.change_summary if cur else "change",
            feedback=list(cur.feedback) if cur else [],
            audits=dict(cur.audits) if cur else {},
            dirty=reason or "dirty",
            code_hash=cur.code_hash if cur else "abcd1234efgh",
        )
        self.metadata[p] = meta
        self._write_disk(p, meta)

    def mark_clean(self, file_path: Any, default_change: str = "initial clean") -> None:
        p = str(file_path)
        cur = self.extract_metadata(p)
        ts = self._now()
        meta = src_metadata.FileMetadata(
            last_cleaned=ts,
            last_changed=cur.last_changed if cur else ts,
            change_summary=cur.change_summary if cur and cur.change_summary else default_change,
            feedback=[],
            audits=dict(cur.audits) if cur else {},
            dirty=None,
            code_hash="abcd1234efgh",
        )
        self.metadata[p] = meta
        self._write_disk(p, meta)

    def append_feedback(self, file_path: Any, explanation: str, sender: Optional[str] = None) -> None:
        p = str(file_path)
        cur = self.extract_metadata(p)
        ts = self._now()
        fb = list(cur.feedback) if cur else []
        fb.append(explanation)
        meta = src_metadata.FileMetadata(
            last_cleaned=cur.last_cleaned if cur else None,
            last_changed=cur.last_changed if cur else ts,
            change_summary=cur.change_summary if cur else "change",
            feedback=fb,
            audits=dict(cur.audits) if cur else {},
            dirty="feedback pending",
            code_hash=cur.code_hash if cur else "abcd1234efgh",
        )
        self.metadata[p] = meta
        self._write_disk(p, meta)

    def is_code_modified(self, file_path: Any) -> bool:
        p = str(file_path)
        if not os.path.isfile(p):
            return True
        meta = self.extract_metadata(p)
        if not meta or not meta.code_hash:
            return True
        return False

    def stamp_audit(self, file_path: Any, role_name: str) -> None:
        p = str(file_path)
        cur = self.extract_metadata(p)
        ts = self._now()
        tag = src_metadata.get_audit_tag(role_name)
        audits = dict(cur.audits) if cur else {}
        audits[tag] = ts
        meta = src_metadata.FileMetadata(
            last_cleaned=cur.last_cleaned if cur else None,
            last_changed=cur.last_changed if cur else ts,
            change_summary=cur.change_summary if cur else "audited",
            feedback=list(cur.feedback) if cur else [],
            audits=audits,
            dirty=cur.dirty if cur else None,
            code_hash=cur.code_hash if cur else "abcd1234efgh",
        )
        self.metadata[p] = meta
        self._write_disk(p, meta)

    def clear_audits(self, file_path: Any) -> None:
        p = str(file_path)
        cur = self.extract_metadata(p)
        if cur:
            meta = src_metadata.FileMetadata(
                last_cleaned=cur.last_cleaned,
                last_changed=cur.last_changed,
                change_summary=cur.change_summary,
                feedback=list(cur.feedback),
                audits={},
                dirty=cur.dirty,
                code_hash=cur.code_hash,
            )
            self.metadata[p] = meta
            self._write_disk(p, meta)

    def delete_last_cleaned(self, file_path: Any) -> None:
        p = str(file_path)
        cur = self.extract_metadata(p)
        if cur:
            meta = src_metadata.FileMetadata(
                last_cleaned=None,
                last_changed=cur.last_changed,
                change_summary=cur.change_summary,
                feedback=list(cur.feedback),
                audits=dict(cur.audits),
                dirty=cur.dirty,
                code_hash=cur.code_hash,
            )
            self.metadata[p] = meta
            self._write_disk(p, meta)

    def record_change(self, file_path: Any, change_description: str) -> None:
        p = str(file_path)
        cur = self.extract_metadata(p)
        ts = self._now()
        meta = src_metadata.FileMetadata(
            last_cleaned=cur.last_cleaned if cur else None,
            last_changed=ts,
            change_summary=change_description,
            feedback=[],
            audits=dict(cur.audits) if cur else {},
            dirty=None,
            code_hash="abcd1234efgh",
        )
        self.metadata[p] = meta
        self._write_disk(p, meta)


class FakeFilePathManager:
    tier = "system"

    def __init__(self, root: str) -> None:
        self.root = root

    def resolve_path(self, root: AbsolutePath, path: WorkspacePath) -> AbsolutePath:
        return AbsolutePath(PathString(os.path.join(root.path, path.path)))

    def create_absolute_path(self, path: PathString) -> AbsolutePath:
        return AbsolutePath(path)

    def create_workspace_path(self, path: PathString) -> WorkspacePath:
        return WorkspacePath(path)

    def create_host_path(self, path: PathString) -> HostPath:
        return HostPath(path)


# ==============================================================================
# 1. State Machine Protocol & Model State
# ==============================================================================

@dataclass
class StorageState:
    """Canonical model state for AgentStorage."""
    nodes: Dict[DagNode, NodeDefinition] = field(default_factory=dict)
    dependencies: Dict[DagNode, Set[DagDependency]] = field(default_factory=dict)
    feedback_deps: Dict[DagNode, Set[DagNode]] = field(default_factory=dict)
    dirty_nodes: Set[DagNode] = field(default_factory=set)


proto = StateMachineProto[StorageState]()


@proto.transition(AgentStorage.get_node_definition)
def get_node_definition(): pass

@get_node_definition.arguments
def _(state: StorageState, this: Any, node: DagNode | NotBoundType = NotBound) -> Optional[Tuple[DagNode]]:
    n = _make_dag_node("//pkg:default") if isinstance(node, NotBoundType) else node
    return (n,)

@get_node_definition.returns
def _(state: StorageState, this: Any, node: DagNode, outcome: object = NotBound) -> Optional[Outcome[NodeDefinition]]:
    expected = state.nodes.get(node, NodeDefinition(task_prompt=TaskPrompt("default")))
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(AgentStorage.is_dirty)
def is_dirty(): pass

@is_dirty.arguments
def _(state: StorageState, this: Any, node: DagNode | NotBoundType = NotBound) -> Optional[Tuple[DagNode]]:
    n = _make_dag_node("//pkg:default") if isinstance(node, NotBoundType) else node
    return (n,)

@is_dirty.returns
def _(state: StorageState, this: Any, node: DagNode, outcome: object = NotBound) -> Optional[Outcome[bool]]:
    res = node in state.dirty_nodes
    if isinstance(outcome, Value) and outcome.val == res:
        return outcome
    if outcome is NotBound:
        return Value(res)
    return None


def make_storage_fake(state: Optional[StorageState] = None) -> AgentStorage:
    st = state or StorageState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(AgentStorage)


# ==============================================================================
# 2. Comprehensive Non-Fuzz Unit Tests on Real Implementation
# ==============================================================================

class TestSrcStorageReal(unittest.TestCase):
    """Direct verification of AgentStorageImpl covering all lifecycle methods."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.orig_env = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.test_dir

        self.registry = LifecycleRegistry()
        self.meta_coord = src_metadata_impl.SourceMetadataCoordinator()
        self.fake_fps = FakeFilePathManager(self.test_dir)

        self.registry.register_instance(
            self.meta_coord,
            keys=[src_metadata.SourceMetadataCoordinator],
            tier="system",
        )
        self.registry.register_instance(
            self.fake_fps,
            keys=[FilePathManager],
            tier="system",
        )
        self.registry.register_instance(
            WorkspaceRoot(PathString(self.test_dir)),
            keys=[WorkspaceRoot],
            tier="system",
        )
        __initialize__(self.registry)

    def tearDown(self) -> None:
        if self.orig_env is not None:
            os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.orig_env
        else:
            os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_node_definition_and_dependencies(self) -> None:
        node = _make_dag_node("//pkg:target")
        dep_node = _make_dag_node("//pkg:dep")
        defn = NodeDefinition(task_prompt=TaskPrompt("Clean prompt"))

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            self.assertIsInstance(storage, AgentStorageImpl)

            storage.store_node_definition(node, defn)
            self.assertEqual(storage.get_node_definition(node), defn)
            self.assertEqual(storage.get_task_prompt(node), defn.task_prompt)

            dep = DagDependency(node=dep_node, is_silent=False)
            storage.store_dependencies(node, {dep})
            self.assertEqual(storage.get_dependencies(node), {dep})

    def test_messages_persistence_and_dirty_state(self) -> None:
        node = _make_dag_node("//pkg/sub:target", "lib")
        rel_path = "pkg/sub/target.py"
        abs_src = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_src), exist_ok=True)
        with open(abs_src, "w", encoding="utf-8") as f:
            f.write("# Target implementation\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(node, rel_path)

            self.assertTrue(storage.is_dirty(node))
            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))

            feedback = FeedbackMessage(content=MessageContent("fix error"))
            storage.add_message(feedback, to=node)
            self.assertTrue(storage.is_dirty(node))

            msgs = storage.get_messages(node)
            self.assertTrue(any(isinstance(m, FeedbackMessage) and "fix error" in str(m.content) for m in msgs))

            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))

    def test_dependency_change_invalidates_downstream_node(self) -> None:
        dep_node = _make_dag_node("//pkg:upstream", "lib")
        dep_path = "pkg/upstream.py"
        abs_dep = os.path.join(self.test_dir, dep_path)
        os.makedirs(os.path.dirname(abs_dep), exist_ok=True)
        with open(abs_dep, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T15:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T15:00:00Z\n"
                "# CHANGE: upstream update\n"
                "# --- END CLEANROOM METADATA ---\n"
            )

        node = _make_dag_node("//pkg:downstream", "lib")
        node_path = "pkg/downstream.py"
        abs_node = os.path.join(self.test_dir, node_path)
        with open(abs_node, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T14:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T14:00:00Z\n"
                "# CHANGE: initial main\n"
                "# --- END CLEANROOM METADATA ---\n"
            )

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(dep_node, dep_path)
            storage.record_source_file(node, node_path)
            storage.store_dependencies(
                node, {DagDependency(node=dep_node, is_silent=False)}
            )

            # Upstream changed at 15:00, downstream cleaned at 14:00 -> downstream is dirty
            self.assertTrue(storage.is_dirty(node))

            # Cleaning downstream makes it not dirty
            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))

    def test_auditor_role_lifecycle(self) -> None:
        target_node = _make_dag_node("//pkg:unit", "lib")
        target_path = "pkg/unit.py"
        abs_target = os.path.join(self.test_dir, target_path)
        os.makedirs(os.path.dirname(abs_target), exist_ok=True)
        with open(abs_target, "w", encoding="utf-8") as f:
            f.write("# Target\n")

        auditor_node = _make_dag_node("//pkg:unit", "qa")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(target_node, target_path)

            # Auditor without feedback dependencies raises KeyError
            with self.assertRaises(KeyError):
                storage.is_dirty(auditor_node)

            storage.store_feedback_dependencies(auditor_node, {target_node})
            storage.mark_node_clean(target_node)

            # Auditor is dirty because target has not been audited by qa
            self.assertTrue(storage.is_dirty(auditor_node))

            # Marking auditor clean stamps QA_AUDIT on target
            storage.mark_node_clean(auditor_node)
            self.assertFalse(storage.is_dirty(auditor_node))

            with open(abs_target, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("QA_AUDIT:", content)

    def test_auditor_role_without_feedback_dependencies_delegates_to_forward_dependencies(
        self,
    ) -> None:
        asm_coverage = _make_dag_node("//pkg:clean_room_asm", "coverage")
        constituent_target = _make_dag_node("//pkg:constituent", "lib")
        constituent_coverage = _make_dag_node("//pkg:constituent", "coverage")
        constituent_path = "pkg/constituent.py"
        abs_path = os.path.join(self.test_dir, constituent_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("# Constituent\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(constituent_target, constituent_path)
            storage.store_feedback_dependencies(
                constituent_coverage, {constituent_target}
            )
            storage.store_feedback_dependencies(asm_coverage, set())
            storage.store_dependencies(
                asm_coverage,
                {DagDependency(node=constituent_coverage, is_silent=False)},
            )

            # When constituent is dirty, asm_coverage is dirty
            self.assertTrue(storage.is_dirty(constituent_coverage))
            self.assertTrue(storage.is_dirty(asm_coverage))

            # When constituent is marked clean, asm_coverage becomes clean
            storage.mark_node_clean(constituent_target)
            storage.mark_node_clean(constituent_coverage)
            self.assertFalse(storage.is_dirty(constituent_coverage))
            self.assertFalse(storage.is_dirty(asm_coverage))

    def test_materialize_template_with_command(self) -> None:
        node = _make_dag_node("//pkg:worker", "custom_role")
        rel_path = "pkg/worker.py"
        abs_path = os.path.join(self.test_dir, rel_path)

        roles_toml = os.path.join(self.test_dir, "cleanroom_roles.toml")
        with open(roles_toml, "w", encoding="utf-8") as f:
            f.write(
                '[roles.custom_role]\n'
                'name = "custom_role"\n'
                'src_pattern = "{unit_dir}/{unit_name}.py"\n'
                'template_command = "python3 -c \\"import sys; open(sys.argv[1], \'w\').write(\'# Custom Scaffolding\\\\n\')\\" {target_file}"\n'
            )

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(node, rel_path)

            old_bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            try:
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.test_dir
                self.assertFalse(os.path.exists(abs_path))
                storage.materialize_template(node)
                self.assertTrue(os.path.exists(abs_path))
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("# Custom Scaffolding", content)
            finally:
                if old_bwd is not None:
                    os.environ["BUILD_WORKSPACE_DIRECTORY"] = old_bwd
                elif "BUILD_WORKSPACE_DIRECTORY" in os.environ:
                    del os.environ["BUILD_WORKSPACE_DIRECTORY"]

    def test_add_change_message_marks_dirty_in_band(self) -> None:
        node = _make_dag_node("//pkg:widget", "lib")
        rel_path = "pkg/widget.py"
        abs_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("# Widget implementation\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(node, rel_path)

            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(len(storage.get_messages(node)), 0)

            msg = ChangeMessage(content=MessageContent("Rework needed"))
            storage.add_message(msg, to=node)

            self.assertTrue(storage.is_dirty(node))
            messages = storage.get_messages(node)
            self.assertEqual(len(messages), 1)

            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# DIRTY: Rework needed", content)

            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))

    def test_delete_last_cleaned_auditor(self) -> None:
        target_node = _make_dag_node("//pkg:item", "lib")
        rel_path = "pkg/item.py"
        abs_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("# Item\n")

        auditor_node = _make_dag_node("//pkg:item", "qa")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(target_node, rel_path)
            storage.store_feedback_dependencies(auditor_node, {target_node})
            storage.mark_node_clean(target_node)
            storage.mark_node_clean(auditor_node)

            with open(abs_path, "r", encoding="utf-8") as f:
                self.assertIn("QA_AUDIT:", f.read())

            storage.mark_node_dirty(auditor_node, reason="re-audit needed")

            with open(abs_path, "r", encoding="utf-8") as f:
                self.assertNotIn("QA_AUDIT:", f.read())

    def test_auditor_get_messages(self) -> None:
        target_node = _make_dag_node("//pkg:unit", "lib")
        target_path = "pkg/unit.py"
        abs_target = os.path.join(self.test_dir, target_path)
        os.makedirs(os.path.dirname(abs_target), exist_ok=True)
        with open(abs_target, "w", encoding="utf-8") as f:
            f.write("# Target\n")

        auditor_node = _make_dag_node("//pkg:unit", "qa")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(target_node, target_path)
            storage.store_feedback_dependencies(auditor_node, {target_node})
            storage.mark_node_clean(target_node)

            # Auditor is dirty -> get_messages should return synthesized audit change message
            msgs = storage.get_messages(auditor_node)
            self.assertTrue(any("audit qa" in str(getattr(m, "content", "")) for m in msgs))

    def test_materialize_template_with_manifest_loader(self) -> None:
        try:
            from update_with_ai.parts.uv.lib import manifest_loader
        except ImportError:
            return

        @dataclass
        class MockManifest:
            template: str = "//templates:my_template"

        class MockLoader:
            tier = "system"
            def load_manifest(self, node: Any) -> None:
                pass
            def retrieve_manifest(self, node: Any) -> Any:
                return MockManifest()

        loader = MockLoader()
        self.registry.register_instance(loader, keys=[manifest_loader.UvManifestLoader], tier="system")

        tmpl_file = os.path.join(self.test_dir, "templates", "my_template.py")
        os.makedirs(os.path.dirname(tmpl_file), exist_ok=True)
        with open(tmpl_file, "w", encoding="utf-8") as f:
            f.write("# Generated from manifest for <name>\n")

        node = _make_dag_node("//pkg:gen_item", "lib")
        rel_path = "pkg/gen_item.py"
        abs_path = os.path.join(self.test_dir, rel_path)

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(node, rel_path)
            storage.materialize_template(node)
            self.assertTrue(os.path.exists(abs_path))
            with open(abs_path, "r", encoding="utf-8") as f:
                self.assertIn("# Generated from manifest for", f.read())

    def test_virtual_node_dirtiness(self) -> None:
        virtual_node = _make_dag_node("//pkg:virtual_target")
        child_node = _make_dag_node("//pkg:child", "lib")
        rel_path = "pkg/child.py"
        abs_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("# Child\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(child_node, rel_path)
            # Virtual node with no source path
            self.assertFalse(storage.is_dirty(virtual_node))

            # Virtual node with message
            storage.add_message(ChangeMessage(content=MessageContent("virtual dirty")), to=virtual_node)
            self.assertTrue(storage.is_dirty(virtual_node))
            storage.clear_messages(virtual_node)
            self.assertFalse(storage.is_dirty(virtual_node))

            # Virtual node depending on dirty child
            storage.store_dependencies(virtual_node, {DagDependency(node=child_node)})
            self.assertTrue(storage.is_dirty(child_node))
            self.assertTrue(storage.is_dirty(virtual_node))

            # Clean child
            storage.mark_node_clean(child_node)
            self.assertFalse(storage.is_dirty(virtual_node))

    def test_auditor_contract_dep_changed_invalidates_audit(self) -> None:
        target_node = _make_dag_node("//pkg:unit", "lib")
        target_path = "pkg/unit.py"
        abs_target = os.path.join(self.test_dir, target_path)
        os.makedirs(os.path.dirname(abs_target), exist_ok=True)
        with open(abs_target, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T14:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T14:00:00Z\n"
                "# QA_AUDIT: 2026-10-02T14:00:00Z\n"
                "# --- END CLEANROOM METADATA ---\n"
            )

        contract_node = _make_dag_node("//pkg:spec", "spec")
        contract_path = "pkg/spec.py"
        abs_contract = os.path.join(self.test_dir, contract_path)
        with open(abs_contract, "w", encoding="utf-8") as f:
            f.write(
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-02T16:00:00Z\n"
                "# LAST_CHANGED: 2026-10-02T16:00:00Z\n"
                "# CHANGE: spec updated\n"
                "# --- END CLEANROOM METADATA ---\n"
            )

        auditor_node = _make_dag_node("//pkg:unit", "qa")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(target_node, target_path)
            storage.record_source_file(contract_node, contract_path)
            storage.store_dependencies(auditor_node, {DagDependency(node=contract_node)})
            storage.store_feedback_dependencies(auditor_node, {target_node})

            # Auditor is dirty because contract LAST_CHANGED (16:00) > QA_AUDIT (14:00)
            self.assertTrue(storage.is_dirty(auditor_node))


    def test_materialize_template_with_cleanroom_toml_methodology(self) -> None:
        pkg_dir = os.path.join(self.test_dir, "my_pkg")
        os.makedirs(pkg_dir, exist_ok=True)
        with open(os.path.join(pkg_dir, "cleanroom.toml"), "w", encoding="utf-8") as f:
            f.write('methodology = "//custom_meth:roles"\n')

        custom_meth_dir = os.path.join(self.test_dir, "custom_meth")
        os.makedirs(custom_meth_dir, exist_ok=True)
        with open(os.path.join(custom_meth_dir, "cleanroom_roles.toml"), "w", encoding="utf-8") as f:
            f.write(
                '[roles.lib]\n'
                'name = "lib"\n'
                'template_command = "python3 -c \\"import sys; open(sys.argv[1], \'w\').write(\'# Custom Lib Meth\\\\n\')\\" {target_file}"\n'
            )

        node = _make_dag_node("//my_pkg:unit", "lib")
        rel_path = "my_pkg/unit.py"
        abs_path = os.path.join(self.test_dir, rel_path)

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(node, rel_path)
            storage.materialize_template(node)
            self.assertTrue(os.path.exists(abs_path))
            with open(abs_path, "r", encoding="utf-8") as f:
                self.assertIn("# Custom Lib Meth", f.read())

    def test_materialize_template_with_manifest_and_role_template(self) -> None:
        templates_dir = os.path.join(self.test_dir, "templates")
        os.makedirs(templates_dir, exist_ok=True)
        tmpl_path = os.path.join(templates_dir, "lib_template.py")
        with open(tmpl_path, "w", encoding="utf-8") as f:
            f.write("# Template for <name>\n")

        node = _make_dag_node("//pkg/sub:my_impl", "lib")
        rel_path = "pkg/sub/my_impl.py"
        abs_path = os.path.join(self.test_dir, rel_path)

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(node, rel_path)
            storage.materialize_template(node)
            self.assertTrue(os.path.exists(abs_path))
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# Template for", content)



        root = _make_dag_node("//pkg:root", "lib")
        dep1 = _make_dag_node("//pkg:dep1", "lib")
        dep2 = _make_dag_node("//pkg:dep2", "lib")

        root_path = "pkg/root.py"
        dep1_path = "pkg/dep1.py"
        dep2_path = "pkg/dep2.py"

        abs_root = os.path.join(self.test_dir, root_path)
        abs_dep1 = os.path.join(self.test_dir, dep1_path)
        abs_dep2 = os.path.join(self.test_dir, dep2_path)

        os.makedirs(os.path.dirname(abs_root), exist_ok=True)
        with open(abs_root, "w", encoding="utf-8") as f:
            f.write("# Root\n")
        with open(abs_dep1, "w", encoding="utf-8") as f:
            f.write("# Dep1\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(root, root_path)
            storage.record_source_file(dep1, dep1_path)
            storage.record_source_file(dep2, dep2_path)

            storage.store_dependencies(root, {DagDependency(node=dep1)})
            storage.store_dependencies(dep1, {DagDependency(node=dep2)})

            storage.mark_subgraph_clean(root)
            self.assertFalse(storage.is_dirty(root))
            self.assertFalse(storage.is_dirty(dep1))
            self.assertFalse(storage.is_dirty(dep2))
            self.assertTrue(os.path.exists(abs_dep2))

        node = _make_dag_node("//pkg/sub:missing", "lib")
        rel_path = "pkg/sub/missing.py"

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(node, rel_path)
            self.assertTrue(storage.is_dirty(node))
            msgs = storage.get_messages(node)
            self.assertTrue(any(isinstance(m, ChangeMessage) for m in msgs))

    def test_auditor_role_and_subgraph_clean(self) -> None:
        auditor_node = _make_dag_node("//pkg:target", "qa")
        fwd_dep = _make_dag_node("//pkg:target", "lib")
        rel_path = "pkg/target.py"
        abs_src = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_src), exist_ok=True)
        with open(abs_src, "w", encoding="utf-8") as f:
            f.write("# Code\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(fwd_dep, rel_path)
            storage.store_dependencies(auditor_node, {DagDependency(node=fwd_dep, is_silent=False)})
            storage.store_feedback_dependencies(auditor_node, {fwd_dep})

            # Forward dep not audited -> auditor dirty
            storage.mark_node_clean(fwd_dep)
            self.assertTrue(storage.is_dirty(auditor_node))

            # Mark clean stamps audit
            storage.mark_node_clean(auditor_node)
            self.assertFalse(storage.is_dirty(auditor_node))

            # Subgraph clean
            storage.mark_subgraph_clean(auditor_node)
            self.assertFalse(storage.is_dirty(auditor_node))

    def test_materialize_template(self) -> None:
        node = _make_dag_node("//pkg:unit", "lib")
        rel_path = "pkg/unit.py"
        abs_path = os.path.join(self.test_dir, rel_path)

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(node, rel_path)
            self.assertFalse(os.path.exists(abs_path))
            storage.materialize_template(node)
            self.assertTrue(os.path.exists(abs_path))

    def test_mark_node_dirty_operations(self) -> None:
        node = _make_dag_node("//pkg:item", "lib")
        rel_path = "pkg/item.py"
        abs_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("# Item\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorageImpl)
            storage.record_source_file(node, rel_path)
            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))

            # Mark dirty with reason
            storage.mark_node_dirty(node, reason="contract broken")
            self.assertTrue(storage.is_dirty(node))

            # Delete last cleaned
            storage.delete_last_cleaned(node)
            self.assertTrue(storage.is_dirty(node))


# ==============================================================================
# 3. Hypothesis Fuzz Testing
# ==============================================================================

class TestSrcStorageFuzz(unittest.TestCase):
    """Property fuzz testing for AgentStorage invariants."""

    @given(
        is_dirty_flag=st.booleans(),
        unit_name=st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
    )
    @settings(max_examples=25)
    def test_fake_dirty_invariants(self, is_dirty_flag: bool, unit_name: str) -> None:
        node = _make_dag_node(f"//pkg:{unit_name}")
        state = StorageState()
        if is_dirty_flag:
            state.dirty_nodes.add(node)
        fake = make_storage_fake(state)
        self.assertEqual(fake.is_dirty(node), is_dirty_flag)
