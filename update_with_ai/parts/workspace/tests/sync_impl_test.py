# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:57:40Z
# CHANGE: Replace the undeclared private registry and source metadata constructors with test doubles implementing the declared WorkspaceRegistry and SourceMetadataCoordinator interfaces
# CODE_HASH: a44c35aa1d4a
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Unit tests for sync_impl."""

import hashlib
import json
import os
import shutil
import stat
import tempfile
import unittest
from typing import Dict, List, Optional
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.metadata.lib import src_metadata
from update_with_ai.parts.workspace.lib import (
    provision,
    role_registry,
    sync,
    sync_impl,
)



def _parse_metadata_text(content: str) -> Optional[src_metadata.FileMetadata]:
    """Parses an in-band cleanroom metadata header from text."""
    lines = content.splitlines()
    in_header = False
    found = False
    values: Dict[str, str] = {}
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("# --- CLEANROOM METADATA ---") or stripped.startswith(
            "<!-- CLEANROOM METADATA"
        ):
            in_header = True
            found = True
            continue
        if stripped.startswith("# --- END CLEANROOM METADATA ---") or stripped == "-->":
            break
        if not in_header:
            continue
        cleaned = stripped.lstrip("#").strip()
        if ":" in cleaned:
            key, _, value = cleaned.partition(":")
            values[key.strip().upper()] = value.strip()
    if not found:
        return None
    audits: Dict[str, str] = {}
    for key, value in values.items():
        if key.endswith("_AUDIT"):
            audits[key] = value
            audits[key[: -len("_AUDIT")].lower()] = value
    return src_metadata.FileMetadata(
        last_cleaned=values.get("LAST_CLEANED"),
        last_changed=values.get("LAST_CHANGED"),
        change_summary=values.get("CHANGE", ""),
        feedback=[values["FEEDBACK"]] if "FEEDBACK" in values else [],
        audits=audits,
        dirty=values.get("DIRTY"),
        code_hash=values.get("CODE_HASH"),
    )


class FakeSourceMetadataCoordinator:
    """Test double implementing the declared SourceMetadataCoordinator interface."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.updated: List[tuple] = []
        self.stamped: List[tuple] = []
        self.appended: List[tuple] = []
        self.metadata: Dict[str, src_metadata.FileMetadata] = {}

    def extract_metadata_from_text(
        self, content: str, filename_or_ext: str
    ) -> Optional[src_metadata.FileMetadata]:
        return _parse_metadata_text(content)

    def extract_metadata(
        self, file_path
    ) -> Optional[src_metadata.FileMetadata]:
        key = str(file_path)
        if key in self.metadata:
            return self.metadata[key]
        try:
            with open(key, "r", encoding="utf-8") as fh:
                return _parse_metadata_text(fh.read())
        except OSError:
            return None

    def extract_code_body(self, content: str, filename_or_ext: str) -> str:
        return content

    def compute_code_hash(self, content: str, filename_or_ext: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:12]

    def compute_file_code_hash(self, file_path) -> Optional[str]:
        try:
            with open(str(file_path), "r", encoding="utf-8") as fh:
                return self.compute_code_hash(fh.read(), str(file_path))
        except OSError:
            return None

    def is_code_modified(self, file_path) -> bool:
        return False

    def rewrite_metadata_in_text(
        self, content: str, filename_or_ext: str, **kwargs
    ) -> str:
        return content

    def update_metadata(self, file_path, **kwargs) -> None:
        self.updated.append((str(file_path), kwargs))

    def delete_last_cleaned(self, file_path) -> None:
        self.updated.append((str(file_path), {"clear_last_cleaned": True}))

    def mark_dirty(self, file_path, reason: str = "manual dirty") -> None:
        self.updated.append((str(file_path), {"dirty": reason}))

    def mark_clean(self, file_path, default_change: str = "new file") -> None:
        self.updated.append((str(file_path), {"last_cleaned": "now"}))

    def record_change(
        self, file_path, change_description: str, code_hash: Optional[str] = None
    ) -> None:
        self.updated.append(
            (str(file_path), {"change_summary": change_description})
        )

    def append_feedback(
        self, file_path, explanation: str, sender: str = "user"
    ) -> None:
        self.appended.append((str(file_path), explanation, sender))

    def stamp_audit(self, file_path, role_name: str) -> None:
        self.stamped.append((str(file_path), role_name))

    def clear_audits(self, file_path) -> None:
        self.updated.append((str(file_path), {"clear_audits": True}))


class FakeWorkspaceRegistry:
    """Test double implementing the declared WorkspaceRegistry interface."""

    tier = agent_session.agent_session

    def __init__(self, roles) -> None:
        self.roles = list(roles)
        self.default_root = os.getcwd()
        self.descriptors: List[role_registry.WorkspaceDescriptor] = []

    def discover_repository_root(self, start_dir=None) -> str:
        return start_dir or self.default_root


    def resolve_role_definition(
        self, role_name_or_address, repo_root=None, dir_scope=None
    ) -> role_registry.RoleDefinition:
        name = str(role_name_or_address).split(":")[-1].split("#")[0].strip().lower()
        for role in self.roles:
            if role.role_name == name:
                return role
        raise KeyError(f"Role not found: {role_name_or_address}")

    def list_roles(self, repo_root=None, dir_scope=None):
        return list(self.roles)

    def compute_workspace_dir(
        self, role_name, dir_scope, repo_root=None, custom_dest=None
    ) -> str:
        if custom_dest:
            return custom_dest
        folder = f"{role_name}_{str(dir_scope).replace('/', '_')}"
        return os.path.join(repo_root or self.default_root, folder)

    def record_workspace(self, descriptor, repo_root=None) -> None:
        self.descriptors.append(descriptor)

    def unregister_workspace(self, workspace_dir, repo_root=None) -> bool:
        before = len(self.descriptors)
        self.descriptors = [
            d for d in self.descriptors if d.workspace_dir != workspace_dir
        ]
        return len(self.descriptors) != before

    def load_active_workspaces(self, repo_root=None):
        return list(self.descriptors)


class FakeWorkspaceProvisioner:
    """Test double implementing the declared WorkspaceProvisioner interface."""

    tier = agent_session.agent_session

    def __init__(self, registry: Optional[FakeWorkspaceRegistry] = None) -> None:
        self.registry = registry

    def copy_file_with_permissions(
        self, src: str, dst: str, readonly: bool = False, executable: bool = False
    ) -> None:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            try:
                os.chmod(dst, 0o644)
            except OSError:
                pass
        shutil.copy2(src, dst)
        mode = (0o555 if readonly else 0o755) if executable else (0o444 if readonly else 0o644)
        try:
            os.chmod(dst, mode)
        except OSError:
            pass

    def write_file_with_permissions(
        self, dst: str, content: str, readonly: bool = False, executable: bool = False
    ) -> None:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            try:
                os.chmod(dst, 0o644)
            except OSError:
                pass
        with open(dst, "w", encoding="utf-8") as f:
            f.write(content)
        mode = 0o555 if executable else (0o444 if readonly else 0o644)
        try:
            os.chmod(dst, mode)
        except OSError:
            pass

    def deploy_runner_zipapps(self, bin_dir: str) -> None:
        os.makedirs(bin_dir, exist_ok=True)

    def write_role_agents_guide(
        self, workspace_dir: str, role_name: str, dir_scope: str, repo_root: Optional[str] = None
    ) -> None:
        agents_f = os.path.join(workspace_dir, "AGENTS.md")
        content = (
            f"# AGENTS for {role_name}\n"
            "## Contamination Tripwire (Poison Pill)\n"
            "CRITICAL CONTAMINATION: I read a file outside my assigned role workspace\n"
            "## Command Execution Tripwire (Restricted Binaries Only)\n"
            "bin/fail\n"
            "## Acting on Blame & Feedback\n"
            "## Unresolvable Impasse & Failure Protocol\n"
        )
        if role_name == "qa":
            content += (
                "## Delivering Blame & Feedback (Auditor Role Requirements)\n"
                "# CHANGE:\n"
                "NEVER recycle identical blame critiques\n"
            )
        self.write_file_with_permissions(agents_f, content)

    def sync_test_stubs(
        self, workspace_dir: str, role_name: str, dir_scope: str, repo_root: Optional[str] = None
    ) -> int:
        count = 0
        ws_scope = os.path.join(workspace_dir, dir_scope)
        ws_parts = os.path.join(ws_scope, "parts")
        if os.path.isdir(ws_parts):
            for part in os.listdir(ws_parts):
                p_dir = os.path.join(ws_parts, part, "lib")
                if os.path.isdir(p_dir):
                    for fn in os.listdir(p_dir):
                        if fn.endswith(".py"):
                            stub_f = os.path.join(p_dir, fn)
                            self.write_file_with_permissions(
                                stub_f,
                                f"# CLEANROOM TEST STUB v4: {fn}\nraise NotImplementedError()\n",
                                readonly=True,
                            )
                            count += 1
        return count

    def commission(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        reset: bool = False,
        model: Optional[str] = None,
    ) -> role_registry.WorkspaceDescriptor:
        raise NotImplementedError()


def _make_roles():
    low_role = role_registry.RoleDefinition(
        role_name="low",
        guide_path="guides/low.md",
        writable_file_patterns=["low/*.pyi", "**/low/*.pyi"],
        readonly_file_patterns=[],
        feedback_role_deps=[],
        src_pattern="{unit_dir}/low/{unit_name}.pyi",
    )
    lib_role = role_registry.RoleDefinition(
        role_name="lib",
        guide_path="guides/lib.md",
        writable_file_patterns=["lib/*.py", "**/lib/*.py"],
        readonly_file_patterns=["low/*.pyi", "**/low/*.pyi"],
        feedback_role_deps=[],
        role_deps=["low"],
        star_role_deps=["low"],
        src_pattern="{unit_dir}/lib/{unit_name}.py",
    )
    test_role = role_registry.RoleDefinition(
        role_name="test",
        guide_path="guides/test.md",
        writable_file_patterns=["tests/*.py", "**/tests/*.py"],
        readonly_file_patterns=["low/*.pyi", "**/low/*.pyi"],
        feedback_role_deps=[],
        role_deps=["low"],
        stub_role_deps=["lib"],
        src_pattern="{unit_dir}/tests/{unit_name}_test.py",
    )
    qa_role = role_registry.RoleDefinition(
        role_name="qa",
        guide_path="guides/qa.md",
        writable_file_patterns=[],
        readonly_file_patterns=["low/*.pyi", "lib/*.py", "tests/*.py"],
        feedback_role_deps=["lib", "test"],
        audit_tag="QA_AUDIT",
    )
    return [low_role, lib_role, test_role, qa_role]


class WorkspaceSyncImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.ws_registry = FakeWorkspaceRegistry(_make_roles())
        self.registry.register_instance(
            self.ws_registry,
            keys=[
                role_registry.WorkspaceRegistry,
            ],
            tier=agent_session.agent_session,
        )
        self.src_meta = FakeSourceMetadataCoordinator()
        self.registry.register_instance(
            self.src_meta,
            keys=[
                src_metadata.SourceMetadataCoordinator,
            ],
            tier=agent_session.agent_session,
        )
        self.provisioner = FakeWorkspaceProvisioner(self.ws_registry)
        self.registry.register_instance(
            self.provisioner,
            keys=[
                provision.WorkspaceProvisioner,
            ],
            tier=agent_session.agent_session,
        )
        self.synchronizer = sync_impl.WorkspaceSynchronizer()
        self.registry.register_instance(
            self.synchronizer,
            keys=[
                sync.WorkspaceSynchronizer,
                sync_impl.WorkspaceSynchronizer,
            ],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)

        self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_pull_and_harvest(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            # Set up main files
            main_lib = os.path.join(main_root, "scope", "lib")
            os.makedirs(main_lib, exist_ok=True)
            main_target = os.path.join(main_lib, "sample.py")
            with open(main_target, "w", encoding="utf-8") as f:
                f.write("# sample target\n")

            pulled = self.synchronizer.pull(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )
            self.assertEqual(pulled, 1)

            ws_target = os.path.join(ws_dir, "scope", "lib", "sample.py")
            self.assertTrue(os.path.isfile(ws_target))

            # Modify in workspace
            with open(ws_target, "w", encoding="utf-8") as f:
                f.write("# modified in workspace\n")

            res = self.synchronizer.harvest(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )
            self.assertEqual(res.harvested_files, 1)

            with open(main_target, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("modified in workspace", content)

    def test_flush_blame_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            culprit_dir = os.path.join(main_root, "scope", "low")
            os.makedirs(culprit_dir, exist_ok=True)
            culprit_file = os.path.join(culprit_dir, "sample.pyi")
            with open(culprit_file, "w", encoding="utf-8") as f:
                f.write('"""Sample contract."""\n')

            blame_buf = os.path.join(ws_dir, ".cleanroom_blame_buffer.json")
            with open(blame_buf, "w", encoding="utf-8") as f:
                json.dump(
                    [
                        {
                            "target": "scope/low/sample.pyi",
                            "explanation": "Type mismatch in return type",
                            "blamed_by": "lib",
                        }
                    ],
                    f,
                )

            flushed = self.synchronizer.flush_blame_buffer(ws_dir, main_root)
            self.assertEqual(len(flushed), 1)

            # Requirement: MUST append unacted feedback to culprit files in the canonical repository.
            self.assertTrue(
                any(
                    path.endswith(os.path.join("scope", "low", "sample.pyi"))
                    and "Type mismatch" in explanation
                    for path, explanation, _sender in self.src_meta.appended
                ),
                f"Expected blame feedback appended to the culprit file: {self.src_meta.appended}",
            )
            # The consumed blame buffer is deleted after every entry is applied.
            self.assertFalse(os.path.exists(blame_buf))

    def test_refresh_system_files_decoupled_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            # Set up files in main
            with open(os.path.join(main_root, "pyproject.toml"), "w", encoding="utf-8") as f:
                f.write("[project]\nname = 'test'\n")
            with open(os.path.join(main_root, "cleanroom_roles.toml"), "w", encoding="utf-8") as f:
                f.write(
                    "[methodology]\nname = 'python'\n\n"
                    "[roles.lib]\nname = 'lib'\nsrc_pattern = '{unit_dir}/lib/{unit_name}.py'\n"
                    "star_role_deps = ['low']\n\n"
                    "[roles.qa]\nname = 'qa'\naudit_tag = 'QA_AUDIT'\nguide_path = 'guides/qa.md'\n"
                )
            with open(os.path.join(main_root, "notes.txt"), "w", encoding="utf-8") as f:
                f.write("# notes\n")
            with open(os.path.join(main_root, "pyrightconfig.json"), "w", encoding="utf-8") as f:
                f.write("{}\n")

            os.makedirs(os.path.join(ws_dir, "bin"), exist_ok=True)
            self.ws_registry.default_root = main_root
            refreshed = self.synchronizer.refresh_system_files(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )
            self.assertGreater(refreshed, 0)
            self.assertTrue(os.path.isfile(os.path.join(ws_dir, "pyproject.toml")))
            self.assertTrue(os.path.isfile(os.path.join(ws_dir, "cleanroom_roles.toml")))
            self.assertFalse(os.path.exists(os.path.join(ws_dir, "notes.txt")))
            self.assertFalse(os.path.exists(os.path.join(ws_dir, "pyrightconfig.json")))
            agents_md = os.path.join(ws_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md))
            with open(agents_md, "r", encoding="utf-8") as f:
                agents_text = f.read()
            self.assertIn("## Contamination Tripwire (Poison Pill)", agents_text)
            self.assertIn("CRITICAL CONTAMINATION: I read a file outside my assigned role workspace", agents_text)
            self.assertIn("## Command Execution Tripwire (Restricted Binaries Only)", agents_text)
            self.assertIn("bin/fail", agents_text)
            self.assertIn("## Acting on Blame & Feedback", agents_text)
            self.assertIn("## Unresolvable Impasse & Failure Protocol", agents_text)

            qa_ws_dir = tempfile.mkdtemp()
            try:
                os.makedirs(os.path.join(qa_ws_dir, "bin"), exist_ok=True)
                refreshed_qa = self.synchronizer.refresh_system_files(
                    workspace_dir=qa_ws_dir,
                    main_root=main_root,
                    role_name="qa",
                    dir_scope="scope",
                )
                self.assertGreater(refreshed_qa, 0)
                qa_agents_md = os.path.join(qa_ws_dir, "AGENTS.md")
                self.assertTrue(os.path.isfile(qa_agents_md))
                with open(qa_agents_md, "r", encoding="utf-8") as f:
                    qa_agents_text = f.read()
                self.assertIn("## Delivering Blame & Feedback (Auditor Role Requirements)", qa_agents_text)
                self.assertIn("# CHANGE:", qa_agents_text)
                self.assertIn("NEVER recycle identical blame critiques", qa_agents_text)
            finally:
                shutil.rmtree(qa_ws_dir, ignore_errors=True)


    def test_pull_updates_unmodified_writable_target_and_ensures_perms(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            main_scope = os.path.join(main_root, "scope")
            ws_scope = os.path.join(ws_dir, "scope")
            os.makedirs(os.path.join(main_scope, "lib"), exist_ok=True)
            os.makedirs(os.path.join(ws_scope, "lib"), exist_ok=True)

            main_target = os.path.join(main_scope, "lib", "unit.py")
            ws_target = os.path.join(ws_scope, "lib", "unit.py")

            content_clean = (
                "# --- CLEANROOM METADATA ---\n"
                "# LAST_CLEANED: 2026-10-07T00:00:00Z\n"
                "# LAST_CHANGED: 2026-10-07T00:00:00Z\n"
                "# CODE_HASH: 123456789abc\n"
                "# --- END CLEANROOM METADATA ---\n"
                "x = 1\n"
            )
            code_hash = self.src_meta.compute_code_hash(content_clean, "unit.py")
            content_clean = content_clean.replace("123456789abc", code_hash)
            with open(main_target, "w", encoding="utf-8") as f:
                f.write(content_clean)
            with open(ws_target, "w", encoding="utf-8") as f:
                f.write(content_clean)

            os.chmod(ws_target, 0o444)

            # The canonical file carries an unacted dirty tag that pull must propagate.
            content_dirty = content_clean.replace(
                "# CODE_HASH:", "# DIRTY: Test failure\n# CODE_HASH:"
            )
            with open(main_target, "w", encoding="utf-8") as f:
                f.write(content_dirty)

            pulled = self.synchronizer.pull(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )
            self.assertEqual(pulled, 1)

            with open(ws_target, "r", encoding="utf-8") as f:
                ws_content = f.read()
            self.assertIn("Test failure", ws_content)

            st = os.stat(ws_target)
            self.assertTrue(bool(st.st_mode & stat.S_IWUSR))

    def test_pull_deletes_files_missing_in_main(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            main_scope = os.path.join(main_root, "scope")
            ws_scope = os.path.join(ws_dir, "scope")
            os.makedirs(os.path.join(main_scope, "lib"), exist_ok=True)
            os.makedirs(os.path.join(ws_scope, "lib"), exist_ok=True)

            old_file = os.path.join(ws_scope, "lib", "deleted.py")
            with open(old_file, "w", encoding="utf-8") as f:
                f.write("# deleted file\n")
            
            ws_init = os.path.join(ws_scope, "__init__.py")
            with open(ws_init, "w", encoding="utf-8") as f:
                f.write("")

            self.assertTrue(os.path.isfile(old_file))
            self.assertTrue(os.path.isfile(ws_init))

            self.synchronizer.pull(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )

            self.assertFalse(os.path.exists(old_file))
            self.assertFalse(os.path.exists(ws_init))

    def test_pull_synchronizes_and_replaces_stub_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            part_dir = os.path.join(main_root, "scope", "parts", "sample")
            os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
            os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

            spec_f = os.path.join(part_dir, "low", "config.pyi")
            with open(spec_f, "w", encoding="utf-8") as f:
                f.write("def get_config() -> str: ...\n")

            real_f = os.path.join(part_dir, "lib", "config.py")
            with open(real_f, "w", encoding="utf-8") as f:
                f.write("def get_config() -> str:\n    return 'secret_main_code'\n")

            with open(os.path.join(main_root, "pyproject.toml"), "w", encoding="utf-8") as f:
                f.write("[project]\nname = 'test'\n")
            with open(os.path.join(main_root, "cleanroom_roles.toml"), "w", encoding="utf-8") as f:
                f.write(
                    "[roles.low]\nname = 'low'\nsrc_pattern = '{unit_dir}/low/{unit_name}.pyi'\n\n"
                    "[roles.lib]\nname = 'lib'\nsrc_pattern = '{unit_dir}/lib/{unit_name}.py'\n"
                    "role_deps = ['low']\n\n"
                    "[roles.test]\nname = 'test'\nsrc_pattern = '{unit_dir}/tests/{unit_name}_test.py'\n"
                    "role_deps = ['low']\nstub_role_deps = ['lib']\n"
                )

            # In workspace, create a leaked real implementation file
            ws_part = os.path.join(ws_dir, "scope", "parts", "sample", "lib")
            os.makedirs(ws_part, exist_ok=True)
            ws_stub = os.path.join(ws_part, "config.py")
            with open(ws_stub, "w", encoding="utf-8") as f:
                f.write("class LeakedCalculator:\n    pass\n")

            pulled = self.synchronizer.pull(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="test",
                dir_scope="scope",
            )
            self.assertGreaterEqual(pulled, 1)

            with open(ws_stub, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("CLEANROOM TEST STUB", content)
            self.assertIn("NotImplementedError", content)
            self.assertNotIn("LeakedCalculator", content)
            self.assertNotIn("secret_main_code", content)
            mode = os.stat(ws_stub).st_mode
            self.assertFalse(bool(mode & stat.S_IWUSR))


if __name__ == "__main__":
    unittest.main()
