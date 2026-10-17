# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:55:00Z
# CHANGE: Unit tests for stub_impl
# CODE_HASH: 582ebf00c993
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Unit tests for stub_impl."""

import os
import stat
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.workspace.lib import (
    role_registry,
    stub,
    stub_impl,
)


class FakeWorkspaceRegistry:
    """Test double implementing WorkspaceRegistry for stub testing."""

    tier = agent_session.agent_session

    def __init__(self, roles) -> None:
        self.roles = list(roles)

    def discover_repository_root(self, start_dir=None) -> str:
        return start_dir or os.getcwd()

    def resolve_role_definition(
        self, role_name_or_address, repo_root=None, dir_scope=None
    ) -> role_registry.RoleDefinition:
        name = str(role_name_or_address).split(":")[-1].split("#")[0].strip().lower()
        for role in self.roles:
            if role.role_name == name:
                return role
        if not name and len(self.roles) == 1:
            return self.roles[0]
        raise KeyError(f"Role not found: {role_name_or_address}")


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
        readonly_file_patterns=[
            "low/*.pyi",
            "**/low/*.pyi",
        ],
        feedback_role_deps=[],
        role_deps=["low"],
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
    return [low_role, lib_role, test_role]


class WorkspaceStubImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.ws_registry = FakeWorkspaceRegistry(_make_roles())
        self.registry.register_instance(
            self.ws_registry,
            keys=[role_registry.WorkspaceRegistry],
            tier=agent_session.agent_session,
        )
        self.stub_synth = stub_impl.WorkspaceStubSynthesizer()
        self.registry.register_instance(
            self.stub_synth,
            keys=[
                stub.WorkspaceStubSynthesizer,
                stub_impl.WorkspaceStubSynthesizer,
            ],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_generate_readonly_test_stub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            pyi_path = os.path.join(tmp_dir, "calc.pyi")
            with open(pyi_path, "w", encoding="utf-8") as f:
                f.write(
                    "class Calculator:\n"
                    "    def add(self, a: int, b: int) -> int: ...\n"
                    "def helper(x: str) -> None: ...\n"
                )
            out_stub = os.path.join(tmp_dir, "calc.py")
            self.stub_synth.generate_readonly_test_stub(
                pyi_path, "calc", out_stub, dep_dir="lib"
            )

            self.assertTrue(os.path.isfile(out_stub))
            self.assertTrue(self.stub_synth.is_valid_test_stub(out_stub))

            with open(out_stub, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("CLEANROOM TEST STUB", content)
            self.assertIn("class Calculator", content)
            self.assertIn("def add", content)
            self.assertIn("raise NotImplementedError", content)
            self.assertIn("def helper", content)

            mode = os.stat(out_stub).st_mode
            self.assertFalse(bool(mode & stat.S_IWUSR))

    def test_is_stub_dep_file(self) -> None:
        roles = _make_roles()
        test_role = [r for r in roles if r.role_name == "test"][0]
        lib_role = [r for r in roles if r.role_name == "lib"][0]

        # Test role has stub_role_deps=['lib']
        self.assertTrue(
            self.stub_synth.is_stub_dep_file(
                "parts/sample/lib/calc.py", test_role
            )
        )
        # __init__.py is not treated as a stub dep file
        self.assertFalse(
            self.stub_synth.is_stub_dep_file(
                "parts/sample/lib/__init__.py", test_role
            )
        )
        # lib role has no stub_role_deps
        self.assertFalse(
            self.stub_synth.is_stub_dep_file(
                "parts/sample/lib/calc.py", lib_role
            )
        )

    def test_sync_all_stub_deps(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            scope_dir = os.path.join(root, "my_scope")
            part_dir = os.path.join(scope_dir, "parts", "calc_part")
            os.makedirs(os.path.join(part_dir, "low"), exist_ok=True)
            os.makedirs(os.path.join(part_dir, "lib"), exist_ok=True)

            pyi_path = os.path.join(part_dir, "low", "calc.pyi")
            with open(pyi_path, "w", encoding="utf-8") as f:
                f.write("def compute(x: int) -> int: ...\n")

            lib_path = os.path.join(part_dir, "lib", "calc.py")
            with open(lib_path, "w", encoding="utf-8") as f:
                f.write("def compute(x: int) -> int:\n    return x * 2\n")

            ws_dir = os.path.join(root, "workspace")
            os.makedirs(ws_dir, exist_ok=True)

            roles = _make_roles()
            test_role = [r for r in roles if r.role_name == "test"][0]

            count = self.stub_synth.sync_all_stub_deps(
                workspace_dir=ws_dir,
                main_root=root,
                role_def=test_role,
                dir_scope="my_scope",
            )
            self.assertEqual(count, 1)

            ws_stub = os.path.join(
                ws_dir, "my_scope", "parts", "calc_part", "lib", "calc.py"
            )
            self.assertTrue(os.path.isfile(ws_stub))
            self.assertTrue(self.stub_synth.is_valid_test_stub(ws_stub))
            with open(ws_stub, "r", encoding="utf-8") as f:
                stub_text = f.read()
            self.assertIn("NotImplementedError", stub_text)
            self.assertNotIn("x * 2", stub_text)

            # Idempotent call when stub is already up to date
            count2 = self.stub_synth.sync_all_stub_deps(
                workspace_dir=ws_dir,
                main_root=root,
                role_def=test_role,
                dir_scope="my_scope",
            )
            self.assertEqual(count2, 0)


if __name__ == "__main__":
    unittest.main()
