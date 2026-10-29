"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceRegistry."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict
from update_with_ai.parts.workspace.lib.role_registry import (
    WorkspaceDescriptor,
    WorkspaceRegistry,
)
from update_with_ai.parts.workspace.lib.roles import RoleDefinition


@dataclass
class WorkspaceRegistryState:
    """Canonical model state for WorkspaceRegistry."""
    repo_root: str = "/repo"
    roles: PretenseDict[str, RoleDefinition] = field(default_factory=PretenseDict)
    workspaces: PretenseDict[str, WorkspaceDescriptor] = field(default_factory=PretenseDict)


class WorkspaceRegistryStateMachine(StateMachine[WorkspaceRegistryState]):
    """Unified Pretense State Machine for WorkspaceRegistry."""

    def __init__(
        self,
        state: Optional[WorkspaceRegistryState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or WorkspaceRegistryState(), singletons=singletons)

    @transition.seeding(name="seed_registry_workspace")
    def seed_registry_workspace(
        self,
        ctx: TransitionContext[Any, [str, str, str], None],
    ) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/repo/staging/role_workspaces/lib'),
                    directory_scope=Domain(strategy=lambda: 'staging'),
                    role_name=Domain(strategy=lambda: 'lib'),
                )
        ctx.returns(lambda workspace_dir="/repo/staging/role_workspaces/lib", directory_scope="staging", role_name="lib": None)
        def provide(res: None, workspace_dir: str = "/repo/staging/role_workspaces/lib", directory_scope: str = "staging", role_name: str = "lib") -> None:
            role_def = self.state.roles.get(
                role_name,
                RoleDefinition(
                    role_name=role_name,
                    guide_path=f"guides/{role_name}.md",
                    writable_file_patterns=(f"{role_name}/*",),
                    readonly_file_patterns=(),
                    feedback_role_deps=(),
                ),
            )
            desc = WorkspaceDescriptor(
                workspace_dir=workspace_dir,
                main_repository_root=self.state.repo_root,
                directory_scope=directory_scope,
                role_definition=role_def,
            )
            self.state.workspaces[workspace_dir] = desc
        ctx.update(provide)

    @transition(WorkspaceRegistry.discover_repository_root)
    def discover_repository_root(
        self,
        ctx: TransitionContext[WorkspaceRegistry, [Optional[str]], str],
    ) -> None:
        ctx.arguments(start_dir=Domain(strategy=lambda: None))
        ctx.returns(lambda start_dir=None: self.state.repo_root)
        ctx.update(lambda res, start_dir=None: None)

    @transition(WorkspaceRegistry.resolve_role_definition)
    def resolve_role_definition(
        self,
        ctx: TransitionContext[WorkspaceRegistry, [str, Optional[str], Optional[str]], RoleDefinition],
    ) -> None:
        ctx.arguments(
                    role_name_or_address=Domain(strategy=lambda: 'lib'),
                    repo_root=Domain(strategy=lambda: None),
                    dir_scope=Domain(strategy=lambda: None),
                )
        def returns(role_name_or_address: str = "lib", repo_root: Optional[str] = None, dir_scope: Optional[str] = None) -> RoleDefinition:
            clean_name = role_name_or_address.split(":")[-1].split("#")[-1].strip().lower()
            return self.state.roles.get(
                clean_name,
                RoleDefinition(
                    role_name=clean_name,
                    guide_path=f"guides/{clean_name}.md",
                    writable_file_patterns=(f"{clean_name}/*",),
                    readonly_file_patterns=(),
                    feedback_role_deps=(),
                ),
            )
        ctx.returns(returns)
        ctx.update(lambda res, role_name_or_address="lib", repo_root=None, dir_scope=None: None)

    @transition(WorkspaceRegistry.list_roles)
    def list_roles(
        self,
        ctx: TransitionContext[WorkspaceRegistry, [Optional[str], Optional[str]], Sequence[RoleDefinition]],
    ) -> None:
        ctx.arguments(
                    repo_root=Domain(strategy=lambda: None),
                    dir_scope=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda repo_root=None, dir_scope=None: tuple(self.state.roles.values()))
        ctx.update(lambda res, repo_root=None, dir_scope=None: None)

    @transition(WorkspaceRegistry.compute_workspace_dir)
    def compute_workspace_dir(
        self,
        ctx: TransitionContext[WorkspaceRegistry, [str, str, Optional[str], Optional[str]], str],
    ) -> None:
        ctx.arguments(
                    role_name=Domain(strategy=lambda: 'lib'),
                    dir_scope=Domain(strategy=lambda: 'staging'),
                    repo_root=Domain(strategy=lambda: None),
                    custom_dest=Domain(strategy=lambda: None),
                )
        def returns(role_name: str = "lib", dir_scope: str = "staging", repo_root: Optional[str] = None, custom_dest: Optional[str] = None) -> str:
            if custom_dest:
                return custom_dest
            root = repo_root or self.state.repo_root
            return os.path.join(root, dir_scope, "role_workspaces", role_name)
        ctx.returns(returns)
        ctx.update(lambda res, role_name="lib", dir_scope="staging", repo_root=None, custom_dest=None: None)

    @transition(WorkspaceRegistry.record_workspace)
    def record_workspace(
        self,
        ctx: TransitionContext[WorkspaceRegistry, [WorkspaceDescriptor, Optional[str]], None],
    ) -> None:
        ctx.arguments(
                    descriptor=Domain(strategy=lambda: WorkspaceDescriptor(workspace_dir='/repo/staging/role_workspaces/lib', main_repository_root=self.state.repo_root, directory_scope='staging', role_definition=RoleDefinition(role_name='lib', guide_path='guides/lib.md', writable_file_patterns=('lib/*',), readonly_file_patterns=(), feedback_role_deps=()))),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda descriptor, repo_root=None: None)
        ctx.update(lambda res, descriptor, repo_root=None: self.state.workspaces.__setitem__(descriptor.workspace_dir, descriptor))

    @transition(WorkspaceRegistry.unregister_workspace)
    def unregister_workspace(
        self,
        ctx: TransitionContext[WorkspaceRegistry, [str, Optional[str]], bool],
    ) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/repo/staging/role_workspaces/lib'),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda workspace_dir="/repo/staging/role_workspaces/lib", repo_root=None: workspace_dir in self.state.workspaces)
        def provide(res: bool, workspace_dir: str = "/repo/staging/role_workspaces/lib", repo_root: Optional[str] = None) -> None:
            self.state.workspaces.pop(workspace_dir, None)
        ctx.update(provide)

    @transition(WorkspaceRegistry.load_active_workspaces)
    def load_active_workspaces(
        self,
        ctx: TransitionContext[WorkspaceRegistry, [Optional[str]], Sequence[WorkspaceDescriptor]],
    ) -> None:
        ctx.arguments(repo_root=Domain(strategy=lambda: None))
        ctx.returns(lambda repo_root=None: tuple(self.state.workspaces.values()))
        ctx.update(lambda res, repo_root=None: None)


proto = WorkspaceRegistryStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_workspace_registry_fake(state: Optional[WorkspaceRegistryState] = None) -> WorkspaceRegistry:
    """Instantiate a synthesized WorkspaceRegistry fake."""
    st = state or WorkspaceRegistryState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(WorkspaceRegistry)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestWorkspaceRegistryUnit(unittest.TestCase):
    """Unit tests for synthesized WorkspaceRegistry fake."""

    def setUp(self) -> None:
        self.state = WorkspaceRegistryState(repo_root="/workspace/root")
        self.sm = proto.make_state_machine(self.state)
        self.sm.seed_registry_workspace("/workspace/root/staging/role_workspaces/lib", "staging", "lib")
        self.fake: WorkspaceRegistry = self.sm.as_fake(WorkspaceRegistry)

    def test_discover_repository_root(self) -> None:
        self.assertEqual(self.fake.discover_repository_root(), "/workspace/root")

    def test_compute_workspace_dir(self) -> None:
        ws_dir = self.fake.compute_workspace_dir("test", "staging")
        self.assertEqual(ws_dir, "/workspace/root/staging/role_workspaces/test")

    def test_load_and_unregister_workspace(self) -> None:
        active = self.fake.load_active_workspaces()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].role_definition.role_name, "lib")

        unregistered = self.fake.unregister_workspace("/workspace/root/staging/role_workspaces/lib")
        self.assertTrue(unregistered)
        self.assertEqual(len(self.fake.load_active_workspaces()), 0)


class TestWorkspaceRegistryImplReal(unittest.TestCase):
    """Direct unit tests for role_registry_impl.py."""

    def setUp(self) -> None:
        import tempfile
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.workspace.lib import role_registry_impl, roles_impl

        self.registry = LifecycleRegistry()
        roles_impl.__initialize__(self.registry)
        role_registry_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.ws_registry = self.scope.get_singleton(role_registry_impl.WorkspaceRegistry)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_discover_repository_root_env_and_markers(self) -> None:
        import tempfile
        from update_with_ai.parts.workspace.lib import role_registry_impl

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. CLEANROOM_MAIN_ROOT
            old_env = os.environ.get("CLEANROOM_MAIN_ROOT")
            try:
                os.environ["CLEANROOM_MAIN_ROOT"] = tmp_dir
                self.assertEqual(
                    os.path.realpath(self.ws_registry.discover_repository_root()),
                    os.path.realpath(tmp_dir),
                )
            finally:
                if old_env is None:
                    os.environ.pop("CLEANROOM_MAIN_ROOT", None)
                else:
                    os.environ["CLEANROOM_MAIN_ROOT"] = old_env

            # 2. Sibling workspace conventions
            projects_root = os.path.join(tmp_dir, "projects")
            main_repo = os.path.join(projects_root, "myrepo")
            os.makedirs(os.path.join(main_repo, ".git"), exist_ok=True)
            workspaces_dir = os.path.join(projects_root, "role_workspaces")
            role_ws = os.path.join(workspaces_dir, "myrepo_lib_staging")
            os.makedirs(role_ws, exist_ok=True)
            with open(os.path.join(role_ws, ".cleanroom_role.json"), "w", encoding="utf-8") as f:
                f.write('{"role_name": "lib"}')

            discovered = self.ws_registry.discover_repository_root(role_ws)
            self.assertEqual(os.path.realpath(discovered), os.path.realpath(main_repo))

            # 3. Ancestor markers
            sub_sub = os.path.join(main_repo, "a", "b", "c")
            os.makedirs(sub_sub, exist_ok=True)
            self.assertEqual(
                os.path.realpath(self.ws_registry.discover_repository_root(sub_sub)),
                os.path.realpath(main_repo),
            )

            # 4. Marker with pyproject.toml
            other_repo = os.path.join(tmp_dir, "other_repo")
            os.makedirs(other_repo, exist_ok=True)
            with open(os.path.join(other_repo, "pyproject.toml"), "w", encoding="utf-8") as f:
                f.write("[project]\nname='test'\n")
            other_sub = os.path.join(other_repo, "sub")
            os.makedirs(other_sub, exist_ok=True)
            self.assertEqual(
                os.path.realpath(self.ws_registry.discover_repository_root(other_sub)),
                os.path.realpath(other_repo),
            )

            # 5. Explicit start_dir with no markers
            empty_dir = os.path.join(tmp_dir, "empty")
            os.makedirs(empty_dir, exist_ok=True)
            self.assertEqual(
                os.path.realpath(self.ws_registry.discover_repository_root(empty_dir)),
                os.path.realpath(empty_dir),
            )

    def test_resolve_role_definition_and_list_roles(self) -> None:
        roles = self.ws_registry.list_roles()
        self.assertTrue(len(roles) > 0)
        role_def = self.ws_registry.resolve_role_definition("lib")
        self.assertEqual(role_def.role_name, "lib")

    def test_compute_workspace_dir(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_root:
            ws_dir = self.ws_registry.compute_workspace_dir("lib", "staging", repo_root=tmp_root)
            self.assertTrue(ws_dir.endswith("lib_staging"))
            self.assertIn("role_workspaces", ws_dir)

            custom = os.path.join(tmp_root, "custom_ws")
            ws_custom = self.ws_registry.compute_workspace_dir(
                "lib", "staging", repo_root=tmp_root, custom_dest=custom
            )
            self.assertEqual(ws_custom, custom)

    def test_record_load_and_unregister_workspace(self) -> None:
        import tempfile
        from update_with_ai.parts.workspace.lib import role_registry, role_registry_impl

        with tempfile.TemporaryDirectory() as tmp_root:
            role_def = self.ws_registry.resolve_role_definition("lib")
            ws_dir = os.path.join(tmp_root, "role_workspaces", "test_lib_staging")
            desc = role_registry.WorkspaceDescriptor(
                workspace_dir=ws_dir,
                main_repository_root=tmp_root,
                directory_scope="staging",
                role_definition=role_def,
            )

            self.ws_registry.record_workspace(desc, repo_root=tmp_root)
            active = self.ws_registry.load_active_workspaces(repo_root=tmp_root)
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0].workspace_dir, ws_dir)

            # Load when target_repo does not match
            other_active = self.ws_registry.load_active_workspaces(repo_root="/other/path")
            self.assertEqual(len(other_active), 0)

            unregistered = self.ws_registry.unregister_workspace(ws_dir, repo_root=tmp_root)
            self.assertTrue(unregistered)
            active_after = self.ws_registry.load_active_workspaces(repo_root=tmp_root)
            self.assertEqual(len(active_after), 0)

    def test_discover_active_workspaces_from_disk_metadata(self) -> None:
        import json
        import tempfile
        from update_with_ai.parts.workspace.lib import role_registry_impl

        with tempfile.TemporaryDirectory() as base_tmp:
            repo_root = os.path.join(base_tmp, "my_repo")
            os.makedirs(repo_root, exist_ok=True)
            roles_file = os.path.join(repo_root, "cleanroom_roles.toml")
            with open(roles_file, "w", encoding="utf-8") as f:
                f.write('[roles.lib]\nname = "lib"\nsrc_pattern = "{unit_dir}/lib/{unit_name}.py"\n')

            workspaces_dir = os.path.join(base_tmp, "role_workspaces")
            ws_dir = os.path.join(workspaces_dir, "my_repo_lib_staging")
            os.makedirs(ws_dir, exist_ok=True)
            meta_path = os.path.join(ws_dir, ".cleanroom_role.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({
                    "role_name": "lib",
                    "dir_scope": "staging",
                    "last_sync_timestamp": "2026-01-02T03:04:05Z",
                }, f)

            # Also create an invalid/skipped workspace
            bad_ws = os.path.join(workspaces_dir, "my_repo_bad")
            os.makedirs(bad_ws, exist_ok=True)
            with open(os.path.join(bad_ws, ".cleanroom_role.json"), "w", encoding="utf-8") as f:
                f.write("invalid json")

            fresh_registry = role_registry_impl.WorkspaceRegistry()
            active = fresh_registry.load_active_workspaces(repo_root=repo_root)
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0].workspace_dir, os.path.abspath(ws_dir))
            self.assertEqual(active[0].role_definition.role_name, "lib")
            self.assertEqual(active[0].directory_scope, "staging")

    def test_helpers_with_and_without_filepath_manager(self) -> None:
        from update_with_ai.parts.core.lib import file_paths_impl
        from update_with_ai.parts.workspace.lib import role_registry_impl

        p1 = role_registry_impl._create_absolute_path("/some/path")
        self.assertTrue(os.path.isabs(p1))

        p2 = role_registry_impl._create_workspace_path_under("/parent", "child")
        self.assertTrue(os.path.isabs(p2))

        # With file_paths_impl registered
        file_paths_impl.__initialize__(self.registry)
        p3 = role_registry_impl._create_absolute_path("/some/path")
        self.assertTrue(os.path.isabs(p3))
        p4 = role_registry_impl._create_workspace_path_under("/parent", "child")
        self.assertTrue(os.path.isabs(p4))

    def test_additional_edge_cases(self) -> None:
        import tempfile
        from update_with_ai.parts.workspace.lib import role_registry, role_registry_impl

        # compute_workspace_dir with colon in role name
        ws_col = self.ws_registry.compute_workspace_dir("//pkg:lib", "scope")
        self.assertIn("lib_scope", ws_col)

        # _match_sibling_workspace_conventions edge cases
        self.assertIsNone(role_registry_impl._match_sibling_workspace_conventions("/some/other/path"))
        self.assertIsNone(role_registry_impl._match_sibling_workspace_conventions("/nonexistent_parent/role_workspaces/child"))

        with tempfile.TemporaryDirectory() as base_tmp:
            workspaces_dir = os.path.join(base_tmp, "role_workspaces")
            os.makedirs(workspaces_dir, exist_ok=True)
            # No matching sibling directory
            self.assertIsNone(role_registry_impl._match_sibling_workspace_conventions(
                os.path.join(workspaces_dir, "myrepo_lib")
            ))

            # discover_repository_root when .cleanroom_role.json exists but no sibling matches
            ws_orphan = os.path.join(workspaces_dir, "orphan_role")
            os.makedirs(ws_orphan, exist_ok=True)
            with open(os.path.join(ws_orphan, ".cleanroom_role.json"), "w", encoding="utf-8") as f:
                f.write('{"role_name": "orphan"}')
            # Should fall back to ancestor or start_dir
            res = self.ws_registry.discover_repository_root(ws_orphan)
            self.assertTrue(os.path.exists(res))

            # load_active_workspaces edge cases
            repo_root = os.path.join(base_tmp, "myrepo")
            os.makedirs(repo_root, exist_ok=True)
            with open(os.path.join(repo_root, "cleanroom_roles.toml"), "w", encoding="utf-8") as f:
                f.write('[roles.lib]\nname = "lib"\nsrc_pattern = "{unit_dir}/lib/{unit_name}.py"\n')

            # 1. Non-matching prefix
            other_ws = os.path.join(workspaces_dir, "other_role")
            os.makedirs(other_ws, exist_ok=True)
            with open(os.path.join(other_ws, ".cleanroom_role.json"), "w", encoding="utf-8") as f:
                f.write('{"role_name": "lib"}')

            # 2. Empty role_name
            empty_role_ws = os.path.join(workspaces_dir, "myrepo_empty")
            os.makedirs(empty_role_ws, exist_ok=True)
            with open(os.path.join(empty_role_ws, ".cleanroom_role.json"), "w", encoding="utf-8") as f:
                f.write('{"role_name": ""}')

            # 3. Unknown role definition
            unk_ws = os.path.join(workspaces_dir, "myrepo_unknown")
            os.makedirs(unk_ws, exist_ok=True)
            with open(os.path.join(unk_ws, ".cleanroom_role.json"), "w", encoding="utf-8") as f:
                f.write('{"role_name": "unknown_role_xyz"}')

            # 4. Seen dirs
            seen_ws = os.path.join(workspaces_dir, "myrepo_seen")
            os.makedirs(seen_ws, exist_ok=True)
            with open(os.path.join(seen_ws, ".cleanroom_role.json"), "w", encoding="utf-8") as f:
                f.write('{"role_name": "lib"}')
            role_def = self.ws_registry.resolve_role_definition("lib")
            self.ws_registry.record_workspace(
                role_registry.WorkspaceDescriptor(
                    workspace_dir=seen_ws,
                    main_repository_root=repo_root,
                    directory_scope="",
                    role_definition=role_def,
                )
            )

            # 5. Target repo mismatch
            diff_ws = os.path.join(workspaces_dir, "myrepo_diff")
            os.makedirs(diff_ws, exist_ok=True)
            with open(os.path.join(diff_ws, ".cleanroom_role.json"), "w", encoding="utf-8") as f:
                f.write('{"role_name": "lib"}')

            reg = role_registry_impl.WorkspaceRegistry()
            # Call with a different target_repo
            other_repo = os.path.join(base_tmp, "other_repo")
            os.makedirs(other_repo, exist_ok=True)
            # This should skip items not matching target_repo
            loaded = reg.load_active_workspaces(repo_root=other_repo)
            self.assertEqual(len(loaded), 0)




# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkspaceRegistryFuzz(unittest.TestCase):
    """Property fuzz testing for WorkspaceRegistry."""

    @settings(max_examples=30)
    @given(
        roles=st.lists(
            st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnopqrstuvwxyz"),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    def test_workspace_registry_invariants(self, roles: list[str]) -> None:
        state = WorkspaceRegistryState(repo_root="/repo")
        sm = proto.make_state_machine(state)
        for r in roles:
            sm.seed_registry_workspace(f"/repo/staging/role_workspaces/{r}", "staging", r)

        fake = sm.as_fake(WorkspaceRegistry)
        active = fake.load_active_workspaces()
        self.assertEqual(len(active), len(roles))

        # Unregister each workspace
        for r in roles:
            ws_path = f"/repo/staging/role_workspaces/{r}"
            self.assertTrue(fake.unregister_workspace(ws_path))
        self.assertEqual(len(fake.load_active_workspaces()), 0)
