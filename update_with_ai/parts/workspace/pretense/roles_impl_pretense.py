"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for RoleResolver."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict
from update_with_ai.parts.workspace.lib.roles import (
    RoleDefinition,
    RoleResolver,
)


@dataclass
class RoleResolverState:
    """Canonical model state for RoleResolver."""
    roles: PretenseDict[str, RoleDefinition] = field(default_factory=PretenseDict)


class RoleResolverStateMachine(StateMachine[RoleResolverState]):
    """Unified Pretense State Machine for RoleResolver."""

    def __init__(
        self,
        state: Optional[RoleResolverState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or RoleResolverState(), singletons=singletons)

    @transition.seeding(name="seed_role")
    def seed_role(
        self,
        ctx: TransitionContext[Any, [str, str, Optional[Sequence[str]], Optional[Sequence[str]], Optional[Sequence[str]], str, Optional[Sequence[str]]], None],
    ) -> None:
        ctx.arguments(
                    role_name=Domain(strategy=lambda: 'lib'),
                    guide_path=Domain(strategy=lambda: 'guides/lib.md'),
                    writable_file_patterns=Domain(strategy=lambda: ('lib/*.py',)),
                    readonly_file_patterns=Domain(strategy=lambda: ('low/*.pyi',)),
                    feedback_role_deps=Domain(strategy=lambda: ('spec_qa',)),
                    src_pattern=Domain(strategy=lambda: 'lib/{unit_name}.py'),
                    role_deps=Domain(strategy=lambda: ('low',)),
                )
        ctx.returns(lambda role_name="lib", guide_path="guides/lib.md", writable_file_patterns=None, readonly_file_patterns=None, feedback_role_deps=None, src_pattern="lib/{unit_name}.py", role_deps=None: None)
        def provide(
            res: None,
            role_name: str = "lib",
            guide_path: str = "guides/lib.md",
            writable_file_patterns: Optional[Sequence[str]] = None,
            readonly_file_patterns: Optional[Sequence[str]] = None,
            feedback_role_deps: Optional[Sequence[str]] = None,
            src_pattern: str = "lib/{unit_name}.py",
            role_deps: Optional[Sequence[str]] = None,
        ) -> None:
            defn = RoleDefinition(
                role_name=role_name,
                guide_path=guide_path,
                writable_file_patterns=tuple(writable_file_patterns or (f"{role_name}/*.py",)),
                readonly_file_patterns=tuple(readonly_file_patterns or ("low/*.pyi",)),
                feedback_role_deps=tuple(feedback_role_deps or ("spec_qa",)),
                src_pattern=src_pattern,
                role_deps=tuple(role_deps or ("low",)),
            )
            self.state.roles[role_name] = defn
        ctx.update(provide)

    @transition(RoleResolver.resolve_role_definition)
    def resolve_role_definition(
        self,
        ctx: TransitionContext[RoleResolver, [str, Optional[str], Optional[str]], RoleDefinition],
    ) -> None:
        ctx.arguments(
                    role_name_or_address=Domain(strategy=lambda: 'lib'),
                    repo_root=Domain(strategy=lambda: None),
                    dir_scope=Domain(strategy=lambda: None),
                )
        def returns(role_name_or_address: str = "lib", repo_root: Optional[str] = None, dir_scope: Optional[str] = None) -> RoleDefinition:
            clean_name = role_name_or_address.split(":")[-1].split("#")[-1].strip().lower()
            if clean_name in self.state.roles:
                return self.state.roles[clean_name]
            return RoleDefinition(
                role_name=clean_name,
                guide_path=f"guides/{clean_name}.md",
                writable_file_patterns=(f"{clean_name}/*",),
                readonly_file_patterns=(),
                feedback_role_deps=(),
                src_pattern=f"{clean_name}/{{unit_name}}.py",
            )
        ctx.returns(returns)
        ctx.update(lambda res, role_name_or_address="lib", repo_root=None, dir_scope=None: None)

    @transition(RoleResolver.list_roles)
    def list_roles(
        self,
        ctx: TransitionContext[RoleResolver, [Optional[str], Optional[str]], Sequence[RoleDefinition]],
    ) -> None:
        ctx.arguments(
                    repo_root=Domain(strategy=lambda: None),
                    dir_scope=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda repo_root=None, dir_scope=None: tuple(self.state.roles.values()))
        ctx.update(lambda res, repo_root=None, dir_scope=None: None)


proto = RoleResolverStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_role_resolver_fake(state: Optional[RoleResolverState] = None) -> RoleResolver:
    """Instantiate a synthesized RoleResolver fake."""
    st = state or RoleResolverState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(RoleResolver)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestRoleResolverUnit(unittest.TestCase):
    """Unit tests for synthesized RoleResolver fake."""

    def setUp(self) -> None:
        self.state = RoleResolverState()
        self.sm = proto.make_state_machine(self.state)
        self.sm.seed_role("lib", "guides/lib.md", ["lib/*.py"], ["low/*.pyi"], ["spec_qa"], "lib/{unit_name}.py", ["low"])
        self.sm.seed_role("test", "guides/test.md", ["tests/*_test.py"], ["low/*.pyi"], ["spec_qa"], "tests/{unit_name}_test.py", ["low"])
        self.fake: RoleResolver = self.sm.as_fake(RoleResolver)

    def test_resolve_role_definition(self) -> None:
        defn = self.fake.resolve_role_definition("lib")
        self.assertEqual(defn.role_name, "lib")
        self.assertEqual(defn.guide_path, "guides/lib.md")
        self.assertEqual(defn.role_deps, ("low",))

    def test_resolve_role_definition_qualified_address(self) -> None:
        defn = self.fake.resolve_role_definition("//parts/core:core#lib")
        self.assertEqual(defn.role_name, "lib")

    def test_list_roles(self) -> None:
        roles = self.fake.list_roles()
        self.assertEqual(len(roles), 2)
        names = {r.role_name for r in roles}
        self.assertEqual(names, {"lib", "test"})


class TestRoleResolverImplReal(unittest.TestCase):
    """Direct unit tests for roles_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.workspace.lib import roles_impl

        self.registry = LifecycleRegistry()
        roles_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.resolver = self.scope.get_singleton(roles_impl.RoleResolver)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_resolve_standard_role_definition(self) -> None:
        role_def = self.resolver.resolve_role_definition("lib")
        self.assertEqual(role_def.role_name, "lib")
        self.assertIn("lib/*.py", role_def.writable_file_patterns)
        self.assertIn("low/*.pyi", role_def.readonly_file_patterns)
        self.assertEqual(list(role_def.silent_cross_role_deps), ["lib"])
        self.assertEqual(list(role_def.star_role_deps), ["low"])

    def test_resolve_auditor_role_definition(self) -> None:
        qa_def = self.resolver.resolve_role_definition(":qa")
        self.assertEqual(qa_def.role_name, "qa")
        self.assertEqual(qa_def.writable_file_patterns, [])
        self.assertEqual(qa_def.audit_tag, "QA_AUDIT")

    def test_unknown_role_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.resolver.resolve_role_definition("nonexistent_role_xyz")

    def test_list_roles(self) -> None:
        all_roles = self.resolver.list_roles()
        role_names = [r.role_name for r in all_roles]
        for expected in ("high", "scenario", "planning", "low", "spec_qa", "lib", "test", "qa", "coverage"):
            self.assertIn(expected, role_names)

    def test_reject_redundant_feedback_in_role_deps(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            toml_path = os.path.join(tmp_dir, "cleanroom_roles.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(
                    "[roles.bad]\n"
                    'role_deps = ["other"]\n'
                    'feedback_role_deps = ["other"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.resolver.list_roles(repo_root=tmp_dir)
            self.assertIn("redundantly declares feedback_role_deps", str(ctx.exception))

    def test_reject_redundant_star_in_role_deps(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            toml_path = os.path.join(tmp_dir, "cleanroom_roles.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(
                    "[roles.bad]\n"
                    'role_deps = ["other"]\n'
                    'star_role_deps = ["other"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.resolver.list_roles(repo_root=tmp_dir)
            self.assertIn("redundantly declares star_role_deps", str(ctx.exception))

    def test_reject_conflicting_silent_role_deps(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            toml_path = os.path.join(tmp_dir, "cleanroom_roles.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(
                    "[roles.bad]\n"
                    'role_deps = ["other"]\n'
                    'silent_role_deps = ["other"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.resolver.list_roles(repo_root=tmp_dir)
            self.assertIn("both a role dependency and a silent role dependency", str(ctx.exception))

    def test_reject_auditor_in_deps(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            toml_path = os.path.join(tmp_dir, "cleanroom_roles.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(
                    "[roles.auditor]\n"
                    'audit_tag = "AUDITOR_AUDIT"\n\n'
                    "[roles.dev]\n"
                    'role_deps = ["auditor"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.resolver.list_roles(repo_root=tmp_dir)
            self.assertIn("Auditor roles can only be silent_role_deps", str(ctx.exception))

        with tempfile.TemporaryDirectory() as tmp_dir:
            toml_path = os.path.join(tmp_dir, "cleanroom_roles.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(
                    "[roles.auditor]\n"
                    'audit_tag = "AUDITOR_AUDIT"\n\n'
                    "[roles.dev]\n"
                    'star_role_deps = ["auditor"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.resolver.list_roles(repo_root=tmp_dir)
            self.assertIn("Auditor roles can only be silent_role_deps", str(ctx.exception))

        with tempfile.TemporaryDirectory() as tmp_dir:
            toml_path = os.path.join(tmp_dir, "cleanroom_roles.toml")
            with open(toml_path, "w", encoding="utf-8") as f:
                f.write(
                    "[roles.auditor]\n"
                    'audit_tag = "AUDITOR_AUDIT"\n\n'
                    "[roles.dev]\n"
                    'feedback_role_deps = ["auditor"]\n'
                )
            with self.assertRaises(ValueError) as ctx:
                self.resolver.list_roles(repo_root=tmp_dir)
            self.assertIn("Auditor roles can only be silent_role_deps", str(ctx.exception))

    def test_methodology_binding_and_packages(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_root:
            meth_dir = os.path.join(tmp_root, "custom_meth")
            os.makedirs(meth_dir, exist_ok=True)
            roles_toml = os.path.join(meth_dir, "cleanroom_roles.toml")
            with open(roles_toml, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.scoped_role]\n'
                    'name = "scoped_role"\n'
                    'src_pattern = "{unit_dir}/scoped/{unit_name}.py"\n'
                    'guide = "//custom_meth:scoped_guide"\n'
                )

            scoped_parts = os.path.join(tmp_root, "my_scope", "parts")
            os.makedirs(scoped_parts, exist_ok=True)
            cleanroom_toml = os.path.join(scoped_parts, "cleanroom.toml")
            with open(cleanroom_toml, "w", encoding="utf-8") as f:
                f.write('methodology = "//custom_meth"\n')

            role_def = self.resolver.resolve_role_definition(
                "scoped_role", repo_root=tmp_root, dir_scope="my_scope/parts"
            )
            self.assertEqual(role_def.role_name, "scoped_role")
            self.assertEqual(role_def.guide_path, "custom_meth/scoped_guide.md")

            # List roles in dir_scope
            scoped_roles = self.resolver.list_roles(repo_root=tmp_root, dir_scope="my_scope/parts")
            self.assertIn("scoped_role", [r.role_name for r in scoped_roles])

            # Resolve package qualified role
            pkg_role = self.resolver.resolve_role_definition("//custom_meth:scoped_role", repo_root=tmp_root)
            self.assertEqual(pkg_role.role_name, "scoped_role")
            self.assertEqual(pkg_role.role_address, "//custom_meth:scoped_role")

    def test_load_roles_from_build_bazel(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_root:
            build_file = os.path.join(tmp_root, "BUILD.bazel")
            with open(build_file, "w", encoding="utf-8") as f:
                f.write(
                    'CONST_PAT = "{unit_dir}/bld/{unit_name}.py"\n'
                    'define_role(\n'
                    '    name = "bld_role",\n'
                    '    src_pattern = CONST_PAT,\n'
                    '    guide = ":my_guide",\n'
                    '    role_deps = ["other"],\n'
                    ')\n'
                    'define_role(\n'
                    '    name = "other",\n'
                    '    src_pattern = "{unit_dir}/other/{unit_name}.py",\n'
                    ')\n'
                )
            role_def = self.resolver.resolve_role_definition("bld_role", repo_root=tmp_root)
            self.assertEqual(role_def.role_name, "bld_role")
            self.assertEqual(role_def.guide_path, "my_guide.md")
            self.assertIn("other/*.py", role_def.readonly_file_patterns)

    def test_build_bazel_ast_evaluations(self) -> None:
        import tempfile
        from update_with_ai.parts.workspace.lib import roles_impl

        with tempfile.TemporaryDirectory() as tmp_root:
            build_file = os.path.join(tmp_root, "BUILD.bazel")
            with open(build_file, "w", encoding="utf-8") as f:
                f.write(
                    'FLAG_T = True\n'
                    'FLAG_F = False\n'
                    'NOTHING = None\n'
                    'TUP = ("a", "b")\n'
                    'DIC = {"k": "v"}\n'
                    'define_role(\n'
                    '    name = "ast_role",\n'
                    '    src_pattern = "{unit_dir}/lib/{unit_name}.py",\n'
                    '    workspace_files = ["file1"],\n'
                    ')\n'
                )
            defs = roles_impl._load_roles_from_build_file(build_file)
            self.assertIn("ast_role", defs)

            # Undefined identifier
            with open(build_file, "w", encoding="utf-8") as f:
                f.write('X = UNDEFINED_VAR\n')
            with self.assertRaises(ValueError):
                roles_impl._load_roles_from_build_file(build_file)

            # Methodology loading from BUILD.bazel
            pkg_dir = os.path.join(tmp_root, "my_bld_pkg")
            os.makedirs(pkg_dir, exist_ok=True)
            with open(os.path.join(pkg_dir, "BUILD.bazel"), "w", encoding="utf-8") as f:
                f.write('define_role(name="bld_pkg_role", src_pattern="x/y.py")\n')
            defs2 = roles_impl._load_roles_from_methodology(tmp_root, "//my_bld_pkg")
            self.assertIsNotNone(defs2)
            assert defs2 is not None
            self.assertIn("bld_pkg_role", defs2)

    def test_toml_bytes_and_zipapp(self) -> None:
        import tempfile
        import zipfile
        from update_with_ai.parts.workspace.lib import roles_impl

        toml_content = b'[roles.t1]\nname = "t1"\nsrc_pattern = "a/b.py"\n'
        defs = roles_impl._load_roles_from_toml_bytes(toml_content)
        self.assertIn("t1", defs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            bin_dir = os.path.join(tmp_dir, "bin")
            os.makedirs(bin_dir, exist_ok=True)
            tool_p = os.path.join(bin_dir, "check_files")
            with zipfile.ZipFile(tool_p, "w") as zf:
                zf.writestr("cleanroom_roles.toml", toml_content)

            old_cwd = os.getcwd()
            try:
                os.chdir(tmp_dir)
                roles_impl._ROLE_CACHE.pop("_BUNDLED_ZIPAPP_ROLES", None)
                loaded = roles_impl._load_roles_from_zipapp()
                self.assertIsNotNone(loaded)
                assert loaded is not None
                self.assertIn("t1", loaded)
            finally:
                os.chdir(old_cwd)

    def test_find_methodology_upward_and_file_not_found(self) -> None:
        import tempfile
        from update_with_ai.parts.workspace.lib import roles_impl

        self.assertIsNone(roles_impl._find_methodology_for_scope("/root", ""))

        with tempfile.TemporaryDirectory() as tmp_root:
            # cleanroom.toml at root of dir_scope
            scope = os.path.join(tmp_root, "scope")
            sub = os.path.join(scope, "sub", "sub2")
            os.makedirs(sub, exist_ok=True)
            with open(os.path.join(scope, "cleanroom.toml"), "w", encoding="utf-8") as f:
                f.write('methodology = "//base_meth"\n')

            meth = roles_impl._find_methodology_for_scope(tmp_root, "scope/sub/sub2")
            self.assertEqual(meth, "//base_meth")

            with self.assertRaises(FileNotFoundError):
                roles_impl._load_roles_from_toml_file(os.path.join(tmp_root, "nonexistent.toml"))

    def test_helpers_and_edge_cases(self) -> None:
        import tempfile
        from update_with_ai.parts.workspace.lib import roles_impl

        # _parse_pat_to_glob
        d, sfx, ext = roles_impl._parse_pat_to_glob("{unit_dir}/lib/{unit_name}.py")
        self.assertEqual(d, "lib")
        self.assertEqual(ext, ".py")
        self.assertEqual(roles_impl._parse_pat_to_glob(""), ("", "", ""))

        # guide path formatting
        defs = roles_impl.build_role_definitions({
            "test1": {"src_pattern": "a/b.py", "guide": "//pkg/tgt"},
            "test2": {"src_pattern": "a/b.py", "guide": "guide.md"},
            "test3": {"src_pattern": "", "guide": ""},
        })
        self.assertEqual(defs["test1"].guide_path, "pkg/tgt.md")
        self.assertEqual(defs["test2"].guide_path, "guide.md")
        self.assertEqual(defs["test3"].audit_tag, "TEST3_AUDIT")

        # BUILD.bazel invalid AST cases
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_bld = os.path.join(tmp_dir, "BUILD.bazel")
            with open(bad_bld, "w", encoding="utf-8") as f:
                f.write('x = 1 + 2\n')
            with self.assertRaises(ValueError):
                roles_impl._load_roles_from_build_file(bad_bld)

            # define_role without name
            with open(bad_bld, "w", encoding="utf-8") as f:
                f.write('define_role(src_pattern="xyz")\n')
            with self.assertRaises(ValueError):
                roles_impl._load_roles_from_build_file(bad_bld)



# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestRoleResolverFuzz(unittest.TestCase):
    """Property fuzz testing for RoleResolver."""

    @settings(max_examples=30)
    @given(
        roles=st.lists(
            st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
            min_size=1,
            max_size=6,
            unique=True,
        )
    )
    def test_role_resolution_invariants(self, roles: list[str]) -> None:
        state = RoleResolverState()
        sm = proto.make_state_machine(state)
        for r in roles:
            sm.seed_role(r, f"guides/{r}.md", [f"{r}/*"], [], [], f"{r}/file", [])

        fake = sm.as_fake(RoleResolver)
        all_roles = fake.list_roles()
        self.assertEqual(len(all_roles), len(roles))

        for r in roles:
            defn = fake.resolve_role_definition(r)
            self.assertEqual(defn.role_name, r)
            # Address resolution syntax //pkg:unit#role
            defn_qualified = fake.resolve_role_definition(f"//pkg/unit:{r}")
            self.assertEqual(defn_qualified.role_name, r)
