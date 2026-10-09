# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-08T00:46:00Z
# CHANGE: Unit tests for src_storage_impl
# CODE_HASH: a6a7b6b37dc2
# COVERAGE_AUDIT: 2026-10-09T21:19:01Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for src_storage_impl aligned with low-level specifications."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional, Set

from update_with_ai.parts.agent.lib.agent_storage import (
    AgentStorage,
    NodeDefinition,
    TaskPrompt,
)
from update_with_ai.parts.control.lib.src_storage_impl import (
    AgentStorage as AgentStorageImpl,
    __initialize__,
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
from update_with_ai.parts.control.lib import src_metadata
from support.lib.lifecycle import LifecycleRegistry, enter_phase


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
                if is_html and "<!-- CLEANROOM METADATA" in content:
                    idx = content.find("-->")
                    if idx != -1:
                        content = content[idx + 3 :].lstrip()
                elif not is_html and "# --- CLEANROOM METADATA ---" in content:
                    idx = content.find("# --- END CLEANROOM METADATA ---")
                    if idx != -1:
                        content = content[idx + len("# --- END CLEANROOM METADATA ---") :].lstrip()
                body = content
            except OSError:
                pass

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + body)

    def extract_metadata(self, file_path: Path | str) -> Optional[src_metadata.FileMetadata]:
        p = str(file_path)
        if not os.path.exists(p):
            return None
        return self.metadata.get(p)

    def extract_metadata_from_text(self, content: str, filename_or_ext: str) -> Optional[src_metadata.FileMetadata]:
        return None

    def extract_code_body(self, content: str, filename_or_ext: str) -> str:
        return content

    def compute_code_hash(self, content: str, filename_or_ext: str) -> str:
        return "fakehash1234"

    def compute_file_code_hash(self, file_path: Path | str) -> Optional[str]:
        return "fakehash1234"

    def is_code_modified(self, file_path: Path | str) -> bool:
        return False

    def rewrite_metadata_in_text(self, content: str, filename_or_ext: str, **kwargs: Any) -> str:
        return content

    def update_metadata(
        self,
        file_path: Path | str,
        last_cleaned: Optional[str] = None,
        clear_last_cleaned: bool = False,
        last_changed: Optional[str] = None,
        change_summary: Optional[str] = None,
        code_hash: Optional[str] = None,
        clear_code_hash: bool = False,
        clear_feedback: bool = False,
        append_feedback: Optional[str] = None,
        audits: Optional[Dict[str, str]] = None,
        clear_audits: bool = False,
        stamp_audit: Optional[str] = None,
        dirty: Optional[str] = None,
        clear_dirty: bool = False,
    ) -> None:
        p = str(file_path)
        curr = self.metadata.get(p)
        new_cleaned = None if clear_last_cleaned else (last_cleaned or (curr.last_cleaned if curr else None))
        new_changed = last_changed or (curr.last_changed if curr and curr.last_changed else self._now())
        new_summary = change_summary or (curr.change_summary if curr else "")
        new_fb = [] if clear_feedback else list(curr.feedback if curr else [])
        if append_feedback:
            new_fb.append(append_feedback)
        if clear_audits:
            new_audits: dict[str, str] = {}
        elif audits is not None:
            new_audits = dict(audits)
        else:
            new_audits = dict(curr.audits if curr else {})
        if stamp_audit:
            r_up = stamp_audit.upper().strip()
            tag = r_up if r_up.endswith("_AUDIT") else f"{r_up}_AUDIT"
            new_audits[tag] = self._now()
        new_dirty = None if clear_dirty else (dirty or (curr.dirty if curr else None))
        new_hash = None if clear_code_hash else (code_hash or (curr.code_hash if curr else None))
        new_meta = src_metadata.FileMetadata(
            last_cleaned=new_cleaned,
            last_changed=new_changed,
            change_summary=new_summary,
            feedback=new_fb,
            audits=new_audits,
            dirty=new_dirty,
            code_hash=new_hash,
        )
        self.metadata[p] = new_meta
        if os.path.exists(p):
            self._write_disk(p, new_meta)

    def delete_last_cleaned(self, file_path: Path | str) -> None:
        self.update_metadata(file_path, clear_last_cleaned=True)

    def mark_dirty(self, file_path: Path | str, reason: str = "manual dirty") -> None:
        now = self._now()
        self.update_metadata(file_path, dirty=reason, last_cleaned=now)

    def mark_clean(self, file_path: Path | str, default_change: str = "new file") -> None:
        now = self._now()
        self.update_metadata(file_path, last_cleaned=now, clear_dirty=True, clear_feedback=True)

    def record_change(self, file_path: Path | str, change_description: str, code_hash: Optional[str] = None) -> None:
        now = self._now()
        self.update_metadata(
            file_path,
            last_cleaned=now,
            last_changed=now,
            change_summary=change_description,
            code_hash=code_hash or "fakehash1234",
            clear_feedback=True,
            clear_audits=True,
            clear_dirty=True,
        )

    def append_feedback(self, file_path: Path | str, explanation: str, sender: str = "user") -> None:
        now = self._now()
        self.update_metadata(file_path, append_feedback=explanation, last_cleaned=now)

    def stamp_audit(self, file_path: Path | str, role_name: str) -> None:
        self.update_metadata(file_path, stamp_audit=role_name)

    def clear_audits(self, file_path: Path | str) -> None:
        self.update_metadata(file_path, clear_audits=True)


class FakeFilePaths:
    tier = "system"

    def __init__(self, root_dir: str) -> None:
        self.root_dir = root_dir

    def get_workspace_root(self) -> WorkspaceRoot:
        return WorkspaceRoot(path=PathString(self.root_dir))

    def create_host_path(self, path: str) -> HostPath:
        return HostPath(path=PathString(path))

    def create_absolute_path(self, path: str) -> AbsolutePath:
        return AbsolutePath(path=PathString(path))

    def create_workspace_path(self, path: str) -> WorkspacePath:
        return WorkspacePath(path=PathString(path))

    def resolve_path(self, root: AbsolutePath, relative: WorkspacePath) -> AbsolutePath:
        joined = os.path.join(root.path, relative.path)
        return AbsolutePath(path=PathString(joined))


class TestSrcStorageImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.orig_env = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.test_dir
        self.registry = LifecycleRegistry()
        self.file_paths_service = FakeFilePaths(self.test_dir)

        self.registry.register_instance(
            self.file_paths_service, keys=[FilePathManager], tier="system"
        )
        self.metadata_service = FakeSourceMetadataCoordinator()
        self.registry.register_instance(
            self.metadata_service,
            keys=[src_metadata.SourceMetadataCoordinator],
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
        """CUJ: Storing and querying node definitions and direct graph dependencies."""
        node = _make_dag_node("//pkg:target")
        dep_node = _make_dag_node("//pkg:dep")
        defn = NodeDefinition(task_prompt=TaskPrompt("Clean prompt"))

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            self.assertIsInstance(storage, AgentStorageImpl)
            assert isinstance(storage, AgentStorageImpl)

            # Store node definition
            storage.store_node_definition(node, defn)
            self.assertEqual(storage.get_node_definition(node), defn)
            self.assertEqual(storage.get_task_prompt(node), defn.task_prompt)

            # Dependencies
            dep = DagDependency(node=dep_node, is_silent=False)
            storage.store_dependencies(node, {dep})
            self.assertEqual(storage.get_dependencies(node), {dep})

    def test_messages_persistence_and_dirty_state(self) -> None:
        """CUJ: Adding messages persists feedback to in-band source metadata and controls dirty state."""
        node = _make_dag_node("//pkg/sub:target", "lib")
        rel_path = "pkg/sub/target.py"
        abs_src = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_src), exist_ok=True)
        with open(abs_src, "w", encoding="utf-8") as f:
            f.write("# Target implementation\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(node, rel_path)

            # Source has no metadata -> dirty
            self.assertTrue(storage.is_dirty(node))

            # Mark clean
            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))

            # Ingest feedback message -> written to metadata header
            feedback = FeedbackMessage(content=MessageContent("fix off-by-one error"))
            storage.add_message(feedback, to=node)
            self.assertTrue(storage.is_dirty(node))

            msgs = storage.get_messages(node)
            self.assertTrue(any(isinstance(m, FeedbackMessage) and "fix off-by-one error" in str(m.content) for m in msgs))

            # Marking clean clears feedback
            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))

    def test_missing_source_file_is_dirty_and_generates_change_message(self) -> None:
        """CUJ: Missing declared source file makes node dirty and generates change message."""
        node = _make_dag_node("//pkg/sub:missing", "lib")
        rel_path = "pkg/sub/missing.py"

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(node, rel_path)

            self.assertTrue(storage.is_dirty(node))
            msgs = storage.get_messages(node)
            self.assertTrue(
                any(
                    isinstance(m, ChangeMessage)
                    and f"implement {rel_path}" in str(m.content)
                    for m in msgs
                )
            )

    def test_dependency_change_invalidates_downstream_node(self) -> None:
        """CUJ: Upstream dependency update invalidates downstream node."""
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
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
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
        """CUJ: Auditor role verification, dirty checks, and audit stamping."""
        target_node = _make_dag_node("//pkg:unit", "lib")
        target_path = "pkg/unit.py"
        abs_target = os.path.join(self.test_dir, target_path)
        os.makedirs(os.path.dirname(abs_target), exist_ok=True)
        with open(abs_target, "w", encoding="utf-8") as f:
            f.write("# Target\n")

        auditor_node = _make_dag_node("//pkg:unit", "qa")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
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
        """CUJ: Auditor node without feedback dependencies delegates dirty evaluation to dependencies."""
        asm_coverage = _make_dag_node("//pkg:clean_room_asm", "coverage")
        constituent_target = _make_dag_node("//pkg:constituent", "lib")
        constituent_coverage = _make_dag_node("//pkg:constituent", "coverage")
        constituent_path = "pkg/constituent.py"
        abs_path = os.path.join(self.test_dir, constituent_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("# Constituent\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
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

    def test_materialize_template(self) -> None:
        """CUJ: Materializing template creates missing source files."""
        node = _make_dag_node("//pkg:unit", "lib")
        rel_path = "pkg/unit.py"
        abs_path = os.path.join(self.test_dir, rel_path)

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(node, rel_path)

            self.assertFalse(os.path.exists(abs_path))
            storage.materialize_template(node)
            self.assertTrue(os.path.exists(abs_path))

    def test_materialize_template_with_command(self) -> None:
        """CUJ: Materializing template executes role template_command when configured."""
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
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
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
        """CUJ: Adding ChangeMessage persists dirty tag in-band and marks node dirty."""
        node = _make_dag_node("//pkg:widget", "lib")
        rel_path = "pkg/widget.py"
        abs_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("# Widget implementation\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(node, rel_path)

            # Initially marked clean
            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(len(storage.get_messages(node)), 0)

            # Add ChangeMessage
            msg = ChangeMessage(content=MessageContent("Rework needed"))
            storage.add_message(msg, to=node)

            # Node is now dirty
            self.assertTrue(storage.is_dirty(node))
            messages = storage.get_messages(node)
            self.assertEqual(len(messages), 1)
            retrieved = next(iter(messages))
            self.assertIsInstance(retrieved, ChangeMessage)
            assert isinstance(retrieved, ChangeMessage)
            self.assertEqual(retrieved.content, "Rework needed")

            # Verify in-band persistence on disk
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# DIRTY: Rework needed", content)
            self.assertNotIn("LAST_CLEANED:", content)

            # Marking clean clears dirty tag
            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(len(storage.get_messages(node)), 0)

            with open(abs_path, "r", encoding="utf-8") as f:
                content_after = f.read()
            self.assertNotIn("# DIRTY:", content_after)
            self.assertIn("LAST_CLEANED:", content_after)

            # Deleting last cleaned marks node dirty on disk without setting dirty tag
            storage.delete_last_cleaned(node)
            self.assertTrue(storage.is_dirty(node))
            with open(abs_path, "r", encoding="utf-8") as f:
                content_deleted = f.read()
            self.assertNotIn("LAST_CLEANED:", content_deleted)

    def test_add_feedback_message(self) -> None:
        """CUJ: add_feedback_message appends feedback in-band and marks node dirty."""
        node = _make_dag_node("//pkg:worker", "lib")
        rel_path = "pkg/worker.py"
        abs_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("# Worker\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(node, rel_path)
            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))

            storage.add_feedback_message(
                node,
                FeedbackMessage(content=MessageContent("fix off-by-one")),
            )
            self.assertTrue(storage.is_dirty(node))
            msgs = storage.get_messages(node)
            self.assertTrue(
                any(
                    isinstance(m, FeedbackMessage)
                    and "fix off-by-one" in str(m.content)
                    for m in msgs
                )
            )
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# FEEDBACK:", content)
            self.assertIn("fix off-by-one", content)

    def test_mark_node_dirty_operations(self) -> None:
        """CUJ: mark_node_dirty marks node dirty with and without reason."""
        node = _make_dag_node("//pkg:item", "lib")
        rel_path = "pkg/item.py"
        abs_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("# Item\n")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(node, rel_path)

            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))

            # Mark dirty with reason
            storage.mark_node_dirty(node, reason="contract broken")
            self.assertTrue(storage.is_dirty(node))
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# DIRTY: contract broken", content)
            self.assertNotIn("LAST_CLEANED:", content)

            # Mark clean clears dirty
            storage.mark_node_clean(node)
            self.assertFalse(storage.is_dirty(node))

            # Mark dirty without reason
            storage.mark_node_dirty(node)
            self.assertTrue(storage.is_dirty(node))
            with open(abs_path, "r", encoding="utf-8") as f:
                content_no_reason = f.read()
            self.assertNotIn("LAST_CLEANED:", content_no_reason)
            self.assertNotIn("# DIRTY:", content_no_reason)

    def test_mark_node_dirty_auditor(self) -> None:
        """CUJ: mark_node_dirty on auditor node invalidates target audit tag."""
        target_node = _make_dag_node("//pkg:audited", "lib")
        target_path = "pkg/audited.py"
        abs_target = os.path.join(self.test_dir, target_path)
        os.makedirs(os.path.dirname(abs_target), exist_ok=True)
        with open(abs_target, "w", encoding="utf-8") as f:
            f.write("# Audited\n")

        auditor_node = _make_dag_node("//pkg:audited", "qa")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(target_node, target_path)
            storage.store_feedback_dependencies(auditor_node, {target_node})
            storage.mark_node_clean(target_node)
            storage.mark_node_clean(auditor_node)

            self.assertFalse(storage.is_dirty(auditor_node))

            storage.mark_node_dirty(auditor_node, reason="re-audit needed")
            self.assertTrue(storage.is_dirty(auditor_node))
            with open(abs_target, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("QA_AUDIT:", content)

    def test_mark_subgraph_clean(self) -> None:
        """CUJ: mark_subgraph_clean cleans all reachable dependencies and materializes templates."""
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
        # dep2 is intentionally missing to test template materialization

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            storage.record_source_file(root, root_path)
            storage.record_source_file(dep1, dep1_path)
            storage.record_source_file(dep2, dep2_path)

            storage.store_dependencies(root, {DagDependency(node=dep1)})
            storage.store_dependencies(dep1, {DagDependency(node=dep2)})

            # All are currently dirty
            self.assertTrue(storage.is_dirty(dep2))
            self.assertTrue(storage.is_dirty(dep1))
            self.assertTrue(storage.is_dirty(root))

            storage.mark_subgraph_clean(root)

            # Missing template was materialized
            self.assertTrue(os.path.exists(abs_dep2))

            # All nodes in subgraph are now clean
            self.assertFalse(storage.is_dirty(dep2))
            self.assertFalse(storage.is_dirty(dep1))
            self.assertFalse(storage.is_dirty(root))


if __name__ == "__main__":
    unittest.main()
