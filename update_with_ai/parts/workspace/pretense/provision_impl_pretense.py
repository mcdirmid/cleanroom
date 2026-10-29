"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceProvisioner."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import stat
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict, PretenseSet
from update_with_ai.parts.workspace.lib import role_registry
from update_with_ai.parts.workspace.lib.provision import WorkspaceProvisioner


@dataclass
class ProvisionerState:
    """Canonical model state for WorkspaceProvisioner."""
    commissioned_workspaces: PretenseDict[str, role_registry.WorkspaceDescriptor] = field(default_factory=PretenseDict)
    stubs_count: int = 0


class WorkspaceProvisionStateMachine(StateMachine[ProvisionerState]):
    """Unified Pretense State Machine for WorkspaceProvisioner."""

    def __init__(
        self,
        state: Optional[ProvisionerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or ProvisionerState(), singletons=singletons)

    @transition.seeding(name="seed_provisioner_data")
    def seed_provisioner_data(
        self,
        ctx: TransitionContext[Any, [int], None],
    ) -> None:
        ctx.arguments(stubs_count=Domain(strategy=lambda: 2))
        ctx.returns(lambda stubs_count=2: None)
        ctx.update(lambda res, stubs_count=2: setattr(self.state, "stubs_count", int(stubs_count)))

    @transition(WorkspaceProvisioner.commission)
    def commission(
        self,
        ctx: TransitionContext[WorkspaceProvisioner, [str, str, Optional[str], Optional[str], bool, Optional[str]], role_registry.WorkspaceDescriptor],
    ) -> None:
        ctx.arguments(
                    role_name=Domain(strategy=lambda: 'lib'),
                    dir_scope=Domain(strategy=lambda: 'staging'),
                    repo_root=Domain(strategy=lambda: None),
                    custom_dest=Domain(strategy=lambda: None),
                    reset=Domain(strategy=lambda: False),
                    model=Domain(strategy=lambda: None),
                )
        def returns(role_name: str = "lib", dir_scope: str = "staging", repo_root: Optional[str] = None, custom_dest: Optional[str] = None, reset: bool = False, model: Optional[str] = None) -> role_registry.WorkspaceDescriptor:
            ws_dir = custom_dest or f"/tmp/workspaces/{role_name}_{dir_scope.replace('/', '_')}"
            desc = role_registry.WorkspaceDescriptor(
                workspace_dir=ws_dir,
                main_repository_root=repo_root or "/repo",
                directory_scope=dir_scope,
                role_definition=role_registry.RoleDefinition(
                    role_name=role_name,
                    guide_path=f"guides/{role_name}.md",
                    writable_file_patterns=(f"{role_name}/*.py",),
                    readonly_file_patterns=(),
                    feedback_role_deps=(),
                ),
            )
            self.state.commissioned_workspaces[ws_dir] = desc
            return desc
        ctx.returns(returns)
        ctx.update(lambda res, role_name="lib", dir_scope="staging", repo_root=None, custom_dest=None, reset=False, model=None: None)

    @transition(WorkspaceProvisioner.copy_file_with_permissions)
    def copy_file_with_permissions(
        self,
        ctx: TransitionContext[WorkspaceProvisioner, [str, str, bool, bool], None],
    ) -> None:
        ctx.arguments(
                    src=Domain(strategy=lambda: '/tmp/src'),
                    dst=Domain(strategy=lambda: '/tmp/dst'),
                    readonly=Domain(strategy=lambda: False),
                    executable=Domain(strategy=lambda: False),
                )
        ctx.returns(lambda src="/tmp/src", dst="/tmp/dst", readonly=False, executable=False: None)
        ctx.update(lambda res, src="/tmp/src", dst="/tmp/dst", readonly=False, executable=False: None)

    @transition(WorkspaceProvisioner.write_file_with_permissions)
    def write_file_with_permissions(
        self,
        ctx: TransitionContext[WorkspaceProvisioner, [str, str, bool, bool], None],
    ) -> None:
        ctx.arguments(
                    dst=Domain(strategy=lambda: '/tmp/dst'),
                    content=Domain(strategy=lambda: 'data'),
                    readonly=Domain(strategy=lambda: False),
                    executable=Domain(strategy=lambda: False),
                )
        ctx.returns(lambda dst="/tmp/dst", content="data", readonly=False, executable=False: None)
        ctx.update(lambda res, dst="/tmp/dst", content="data", readonly=False, executable=False: None)

    @transition(WorkspaceProvisioner.deploy_runner_zipapps)
    def deploy_runner_zipapps(
        self,
        ctx: TransitionContext[WorkspaceProvisioner, [str], None],
    ) -> None:
        ctx.arguments(bin_dir=Domain(strategy=lambda: '/tmp/bin'))
        ctx.returns(lambda bin_dir="/tmp/bin": None)
        ctx.update(lambda res, bin_dir="/tmp/bin": None)

    @transition(WorkspaceProvisioner.write_role_agents_guide)
    def write_role_agents_guide(
        self,
        ctx: TransitionContext[WorkspaceProvisioner, [str, str, str, Optional[str]], None],
    ) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    role_name=Domain(strategy=lambda: 'lib'),
                    dir_scope=Domain(strategy=lambda: 'staging'),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda workspace_dir="/tmp/ws", role_name="lib", dir_scope="staging", repo_root=None: None)
        ctx.update(lambda res, workspace_dir="/tmp/ws", role_name="lib", dir_scope="staging", repo_root=None: None)

    @transition(WorkspaceProvisioner.sync_test_stubs)
    def sync_test_stubs(
        self,
        ctx: TransitionContext[WorkspaceProvisioner, [str, str, str, Optional[str]], int],
    ) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    role_name=Domain(strategy=lambda: 'test'),
                    dir_scope=Domain(strategy=lambda: 'staging'),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda workspace_dir="/tmp/ws", role_name="test", dir_scope="staging", repo_root=None: self.state.stubs_count)
        ctx.update(lambda res, workspace_dir="/tmp/ws", role_name="test", dir_scope="staging", repo_root=None: None)


proto = WorkspaceProvisionStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_provision_fake(state: Optional[ProvisionerState] = None) -> WorkspaceProvisioner:
    """Instantiate a synthesized WorkspaceProvisioner fake."""
    st = state or ProvisionerState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(WorkspaceProvisioner)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestWorkspaceProvisionerUnit(unittest.TestCase):
    """Unit tests for synthesized WorkspaceProvisioner fake."""

    def setUp(self) -> None:
        self.state = ProvisionerState()
        self.sm = proto.make_state_machine(self.state)
        self.sm.seed_provisioner_data(stubs_count=3)
        self.fake: WorkspaceProvisioner = self.sm.as_fake(WorkspaceProvisioner)

    def test_commission(self) -> None:
        desc = self.fake.commission("lib", "staging", "/repo")
        self.assertEqual(desc.role_definition.role_name, "lib")
        self.assertEqual(desc.directory_scope, "staging")

    def test_sync_test_stubs(self) -> None:
        count = self.fake.sync_test_stubs("/ws", "test", "staging")
        self.assertEqual(count, 3)


class TestWorkspaceProvisionerImplReal(unittest.TestCase):
    """Direct unit tests for provision_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.workspace.lib import (
            provision,
            provision_impl,
            role_registry_impl,
            roles_impl,
            scaffold_impl,
            stub_impl,
        )

        self.registry = LifecycleRegistry()
        roles_impl.__initialize__(self.registry)
        role_registry_impl.__initialize__(self.registry)
        scaffold_impl.__initialize__(self.registry)
        stub_impl.__initialize__(self.registry)
        provision_impl.__initialize__(self.registry)

        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.provisioner = self.scope.get_singleton(provision_impl.WorkspaceProvisioner)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_commission_and_reset(self) -> None:
        with tempfile.TemporaryDirectory() as base_tmp:
            repo_root = os.path.join(base_tmp, "repo")
            ws_custom = os.path.join(base_tmp, "ws_custom")
            os.makedirs(repo_root, exist_ok=True)

            roles_file = os.path.join(repo_root, "cleanroom_roles.toml")
            with open(roles_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.low]\n'
                    'name = "low"\n'
                    'src_pattern = "{unit_dir}/low/{unit_name}.pyi"\n\n'
                    '[roles.lib]\n'
                    'name = "lib"\n'
                    'src_pattern = "{unit_dir}/lib/{unit_name}.py"\n'
                    'role_deps = ["low"]\n'
                )

            # Create sample files in main scope
            scope_dir = os.path.join(repo_root, "scope", "parts", "unit")
            os.makedirs(os.path.join(scope_dir, "lib"), exist_ok=True)
            os.makedirs(os.path.join(scope_dir, "low"), exist_ok=True)

            with open(os.path.join(scope_dir, "lib", "sample.py"), "w", encoding="utf-8") as f:
                f.write("# lib impl\n")
            with open(os.path.join(scope_dir, "low", "sample.pyi"), "w", encoding="utf-8") as f:
                f.write("# low spec\n")

            desc = self.provisioner.commission(
                role_name="lib",
                dir_scope="scope",
                repo_root=repo_root,
                custom_dest=ws_custom,
            )
            self.assertEqual(desc.workspace_dir, ws_custom)
            self.assertEqual(desc.role_definition.role_name, "lib")

            # Check that files were created
            self.assertTrue(os.path.isfile(os.path.join(ws_custom, "bin", "get_work")))
            self.assertTrue(os.path.isfile(os.path.join(ws_custom, "AGENTS.md")))
            self.assertTrue(os.path.isfile(os.path.join(ws_custom, ".cleanroom_role.json")))

            # Check writable vs read-only projected files
            ws_lib = os.path.join(ws_custom, "scope", "parts", "unit", "lib", "sample.py")
            ws_low = os.path.join(ws_custom, "scope", "parts", "unit", "low", "sample.pyi")
            self.assertTrue(os.path.isfile(ws_lib))
            self.assertTrue(os.path.isfile(ws_low))

            # Commission with reset=True
            stale_f = os.path.join(ws_custom, ".cleanroom_pending_work.json")
            with open(stale_f, "w", encoding="utf-8") as f:
                f.write("{}")

            self.provisioner.commission(
                role_name="lib",
                dir_scope="scope",
                repo_root=repo_root,
                custom_dest=ws_custom,
                reset=True,
            )
            self.assertFalse(os.path.exists(stale_f))

    def test_delegated_methods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            dst = os.path.join(tmp_dir, "out.txt")
            self.provisioner.write_file_with_permissions(dst, "test data", readonly=False)
            self.assertTrue(os.path.isfile(dst))

            dst_copy = os.path.join(tmp_dir, "copy.txt")
            self.provisioner.copy_file_with_permissions(dst, dst_copy, readonly=True)
            self.assertTrue(os.path.isfile(dst_copy))
            mode = stat.S_IMODE(os.stat(dst_copy).st_mode)
            self.assertEqual(mode, 0o444)

            bin_dir = os.path.join(tmp_dir, "bin")
            self.provisioner.deploy_runner_zipapps(bin_dir)
            self.assertTrue(os.path.isfile(os.path.join(bin_dir, "get_work")))


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkspaceProvisionerFuzz(unittest.TestCase):
    """Property fuzz testing for WorkspaceProvisioner."""

    @settings(max_examples=30)
    @given(
        roles=st.lists(
            st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnopqrstuvwxyz"),
            min_size=1,
            max_size=4,
            unique=True,
        )
    )
    def test_provisioner_invariants(self, roles: list[str]) -> None:
        state = ProvisionerState()
        sm = proto.make_state_machine(state)
        fake = sm.as_fake(WorkspaceProvisioner)

        for r in roles:
            desc = fake.commission(r, "scope")
            self.assertEqual(desc.role_definition.role_name, r)
