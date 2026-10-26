"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceSynchronizer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.workspace.lib.sync import (
    SyncResult,
    WorkspaceSynchronizer,
)


@dataclass
class SyncState:
    """Canonical model state for WorkspaceSynchronizer."""
    pulled_count: int = 5
    refreshed_count: int = 3
    harvested_files: PretenseSet[str] = field(default_factory=PretenseSet)
    stamped_audits: PretenseSet[str] = field(default_factory=PretenseSet)
    flushed_blames: PretenseSet[str] = field(default_factory=PretenseSet)


proto = StateMachineProto[SyncState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_sync_counts(): pass

@seed_sync_counts.arguments
def _(
    state: SyncState,
    this: Any,
    pulled_count: int | NotBoundType = NotBound,
    refreshed_count: int | NotBoundType = NotBound,
) -> Optional[Tuple[int, int]]:
    p = 5 if isinstance(pulled_count, NotBoundType) else int(pulled_count)
    r = 3 if isinstance(refreshed_count, NotBoundType) else int(refreshed_count)
    return (p, r)

@seed_sync_counts.provide
def _(
    state: SyncState,
    this: Any,
    pulled_count: int,
    refreshed_count: int,
    result: None = None,
) -> None:
    state.pulled_count = pulled_count
    state.refreshed_count = refreshed_count


@proto.seeding()
def seed_harvest_artifacts(): pass

@seed_harvest_artifacts.arguments
def _(
    state: SyncState,
    this: Any,
    harvested_files: Optional[Sequence[str]] | NotBoundType = NotBound,
    stamped_audits: Optional[Sequence[str]] | NotBoundType = NotBound,
    flushed_blames: Optional[Sequence[str]] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[str], Sequence[str], Sequence[str]]]:
    h = () if isinstance(harvested_files, NotBoundType) or harvested_files is None else tuple(harvested_files)
    a = () if isinstance(stamped_audits, NotBoundType) or stamped_audits is None else tuple(stamped_audits)
    b = () if isinstance(flushed_blames, NotBoundType) or flushed_blames is None else tuple(flushed_blames)
    return (h, a, b)

@seed_harvest_artifacts.provide
def _(
    state: SyncState,
    this: Any,
    harvested_files: Sequence[str],
    stamped_audits: Sequence[str],
    flushed_blames: Sequence[str],
    result: None = None,
) -> None:
    state.harvested_files = PretenseSet(harvested_files)
    state.stamped_audits = PretenseSet(stamped_audits)
    state.flushed_blames = PretenseSet(flushed_blames)


# ==============================================================================
# 2. WorkspaceSynchronizer Transitions
# ==============================================================================

@proto.transition(WorkspaceSynchronizer.pull)
def pull(): pass

@pull.arguments
def _(
    state: SyncState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    main_root: str | NotBoundType = NotBound,
    role_name: str | NotBoundType = NotBound,
    dir_scope: str | NotBoundType = NotBound,
    silent: bool | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, str, str, bool]]:
    w = "/repo/staging/role_workspaces/lib" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    m = "/repo" if isinstance(main_root, NotBoundType) else str(main_root)
    r = "lib" if isinstance(role_name, NotBoundType) else str(role_name)
    d = "staging" if isinstance(dir_scope, NotBoundType) else str(dir_scope)
    s = False if isinstance(silent, NotBoundType) else bool(silent)
    return (w, m, r, d, s)

@pull.returns
def _(
    state: SyncState,
    this: Any,
    workspace_dir: str,
    main_root: str,
    role_name: str,
    dir_scope: str,
    silent: bool,
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    expected = state.pulled_count
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(WorkspaceSynchronizer.refresh_system_files)
def refresh_system_files(): pass

@refresh_system_files.arguments
def _(
    state: SyncState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    main_root: str | NotBoundType = NotBound,
    role_name: str | NotBoundType = NotBound,
    dir_scope: str | NotBoundType = NotBound,
    silent: bool | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, str, str, bool]]:
    w = "/repo/staging/role_workspaces/lib" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    m = "/repo" if isinstance(main_root, NotBoundType) else str(main_root)
    r = "lib" if isinstance(role_name, NotBoundType) else str(role_name)
    d = "staging" if isinstance(dir_scope, NotBoundType) else str(dir_scope)
    s = False if isinstance(silent, NotBoundType) else bool(silent)
    return (w, m, r, d, s)

@refresh_system_files.returns
def _(
    state: SyncState,
    this: Any,
    workspace_dir: str,
    main_root: str,
    role_name: str,
    dir_scope: str,
    silent: bool,
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    expected = state.refreshed_count
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(WorkspaceSynchronizer.harvest)
def harvest(): pass

@harvest.arguments
def _(
    state: SyncState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    main_root: str | NotBoundType = NotBound,
    role_name: str | NotBoundType = NotBound,
    dir_scope: str | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, str, str]]:
    w = "/repo/staging/role_workspaces/lib" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    m = "/repo" if isinstance(main_root, NotBoundType) else str(main_root)
    r = "lib" if isinstance(role_name, NotBoundType) else str(role_name)
    d = "staging" if isinstance(dir_scope, NotBoundType) else str(dir_scope)
    return (w, m, r, d)

@harvest.returns
def _(
    state: SyncState,
    this: Any,
    workspace_dir: str,
    main_root: str,
    role_name: str,
    dir_scope: str,
    outcome: object = NotBound,
) -> Optional[Outcome[SyncResult]]:
    expected = SyncResult(
        pulled_files=state.pulled_count,
        harvested_files=len(state.harvested_files),
        stamped_audits=tuple(sorted(state.stamped_audits)),
        flushed_blames=tuple(sorted(state.flushed_blames)),
    )
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_sync_fake(state: Optional[SyncState] = None) -> WorkspaceSynchronizer:
    """Instantiate a synthesized WorkspaceSynchronizer fake."""
    st = state or SyncState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(WorkspaceSynchronizer)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestWorkspaceSynchronizerUnit(unittest.TestCase):
    """Unit tests for synthesized WorkspaceSynchronizer fake."""

    def setUp(self) -> None:
        self.state = SyncState()
        self.sm = proto.make_state_machine(self.state)
        self.sm.seed_sync_counts(pulled_count=4, refreshed_count=2)
        self.sm.seed_harvest_artifacts(
            harvested_files=["parts/core/lib/demo.py"],
            stamped_audits=["parts/core/lib/demo.py"],
            flushed_blames=[],
        )
        self.fake: WorkspaceSynchronizer = self.sm.as_fake(WorkspaceSynchronizer)

    def test_pull(self) -> None:
        pulled = self.fake.pull("/ws", "/repo", "lib", "staging")
        self.assertEqual(pulled, 4)

    def test_refresh_system_files(self) -> None:
        refreshed = self.fake.refresh_system_files("/ws", "/repo", "lib", "staging")
        self.assertEqual(refreshed, 2)

    def test_harvest(self) -> None:
        result = self.fake.harvest("/ws", "/repo", "lib", "staging")
        self.assertEqual(result.pulled_files, 4)
        self.assertEqual(result.harvested_files, 1)
        self.assertEqual(result.stamped_audits, ("parts/core/lib/demo.py",))


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkspaceSynchronizerFuzz(unittest.TestCase):
    """Property fuzz testing for WorkspaceSynchronizer."""

    @settings(max_examples=30)
    @given(
        pulled=st.integers(min_value=0, max_value=20),
        refreshed=st.integers(min_value=0, max_value=10),
    )
    def test_sync_counts_invariants(self, pulled: int, refreshed: int) -> None:
        state = SyncState()
        sm = proto.make_state_machine(state)
        sm.seed_sync_counts(pulled_count=pulled, refreshed_count=refreshed)
        fake = sm.as_fake(WorkspaceSynchronizer)

        self.assertEqual(fake.pull("/ws", "/repo", "lib", "staging"), pulled)
        self.assertEqual(fake.refresh_system_files("/ws", "/repo", "lib", "staging"), refreshed)


class TestWorkspaceSynchronizerImplReal(unittest.TestCase):
    """Direct unit tests for sync_impl.py."""

    def setUp(self) -> None:
        import os
        import shutil
        import tempfile
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.metadata.lib import src_metadata_impl
        from update_with_ai.parts.workspace.lib import (
            provision,
            role_registry,
            roles,
            roles_impl,
            role_registry_impl,
            sync,
            sync_impl,
        )

        self.registry = LifecycleRegistry()
        src_metadata_impl.__initialize__(self.registry)
        roles_impl.__initialize__(self.registry)
        role_registry_impl.__initialize__(self.registry)
        sync_impl.__initialize__(self.registry)

        class DummyProvisioner:
            tier = agent_session.agent_session
            def sync_test_stubs(self, **kwargs: Any) -> int:
                return 0
            def deploy_runner_zipapps(self, bin_dir: str) -> None:
                os.makedirs(bin_dir, exist_ok=True)
            def write_role_agents_guide(self, workspace_dir: str, role_name: str, dir_scope: str, repo_root: Optional[str] = None) -> None:
                pass
            def copy_file_with_permissions(self, src: str, dst: str, readonly: bool = False, executable: bool = False) -> None:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(dst):
                    try:
                        os.chmod(dst, 0o644)
                    except OSError:
                        pass
                shutil.copy2(src, dst)
                mode = 0o444 if readonly else 0o644
                try:
                    os.chmod(dst, mode)
                except OSError:
                    pass
            def write_file_with_permissions(self, dst: str, content: str, readonly: bool = False, executable: bool = False) -> None:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(dst):
                    try:
                        os.chmod(dst, 0o644)
                    except OSError:
                        pass
                with open(dst, "w", encoding="utf-8") as f:
                    f.write(content)
                mode = 0o444 if readonly else 0o644
                try:
                    os.chmod(dst, mode)
                except OSError:
                    pass

        self.registry.register_instance(
            DummyProvisioner(),
            keys=[provision.WorkspaceProvisioner],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.sync = self.scope.get_singleton(sync_impl.WorkspaceSynchronizer)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_pull_and_harvest(self) -> None:
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            # Setup role config
            roles_file = os.path.join(main_root, "cleanroom_roles.toml")
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

            # Create sample files in main
            main_lib = os.path.join(main_root, "scope", "lib")
            main_low = os.path.join(main_root, "scope", "low")
            os.makedirs(main_lib, exist_ok=True)
            os.makedirs(main_low, exist_ok=True)

            with open(os.path.join(main_lib, "sample.py"), "w", encoding="utf-8") as f:
                f.write("# sample impl\n")
            with open(os.path.join(main_low, "sample.pyi"), "w", encoding="utf-8") as f:
                f.write("# sample spec\n")

            # 1. Pull
            pulled = self.sync.pull(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )
            self.assertEqual(pulled, 2)

            ws_target = os.path.join(ws_dir, "scope", "lib", "sample.py")
            self.assertTrue(os.path.isfile(ws_target))

            # 2. Modify in workspace and harvest
            with open(ws_target, "w", encoding="utf-8") as f:
                f.write("# modified impl\n")

            res = self.sync.harvest(
                workspace_dir=ws_dir,
                main_root=main_root,
                role_name="lib",
                dir_scope="scope",
            )
            self.assertEqual(res.harvested_files, 1)

            with open(os.path.join(main_lib, "sample.py"), "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# modified impl", content)

    def test_flush_blame_buffer(self) -> None:
        import json
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            culprit_dir = os.path.join(main_root, "scope", "low")
            os.makedirs(culprit_dir, exist_ok=True)
            culprit_file = os.path.join(culprit_dir, "sample.pyi")
            with open(culprit_file, "w", encoding="utf-8") as f:
                f.write('"""Sample contract."""\n')

            blame_buf = os.path.join(ws_dir, ".cleanroom_blame_buffer.json")
            with open(blame_buf, "w", encoding="utf-8") as f:
                json.dump([
                    {
                        "target": "scope/low/sample.pyi",
                        "explanation": "contract violation",
                        "blamed_by": "lib",
                    }
                ], f)

            flushed = self.sync.flush_blame_buffer(ws_dir, main_root)
            self.assertEqual(len(flushed), 1)
            self.assertFalse(os.path.exists(blame_buf))

    def test_refresh_system_files(self) -> None:
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            roles_file = os.path.join(main_root, "cleanroom_roles.toml")
            with open(roles_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.lib]\n'
                    'name = "lib"\n'
                    'src_pattern = "{unit_dir}/lib/{unit_name}.py"\n'
                    'guide = "//parts:guide"\n'
                )
            guide_dir = os.path.join(main_root, "parts")
            os.makedirs(guide_dir, exist_ok=True)
            with open(os.path.join(guide_dir, "guide.md"), "w", encoding="utf-8") as f:
                f.write("# Guide content\n")

            refreshed = self.sync.refresh_system_files(ws_dir, main_root, "lib", "scope")
            self.assertGreaterEqual(refreshed, 0)

    def test_pull_deletes_orphan_workspace_files(self) -> None:
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            roles_file = os.path.join(main_root, "cleanroom_roles.toml")
            with open(roles_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.lib]\n'
                    'name = "lib"\n'
                    'src_pattern = "{unit_dir}/lib/{unit_name}.py"\n'
                )

            main_scope = os.path.join(main_root, "scope", "lib")
            ws_scope = os.path.join(ws_dir, "scope", "lib")
            os.makedirs(main_scope, exist_ok=True)
            os.makedirs(ws_scope, exist_ok=True)

            # File that only exists in ws
            orphan_ws = os.path.join(ws_scope, "orphan.py")
            with open(orphan_ws, "w", encoding="utf-8") as f:
                f.write("# orphan\n")

            self.sync.pull(ws_dir, main_root, "lib", "scope")
            self.assertFalse(os.path.exists(orphan_ws))

    def test_harvest_auditor_stamping(self) -> None:
        import json
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            roles_file = os.path.join(main_root, "cleanroom_roles.toml")
            with open(roles_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.low]\n'
                    'name = "low"\n'
                    'src_pattern = "{unit_dir}/low/{unit_name}.pyi"\n\n'
                    '[roles.qa]\n'
                    'name = "qa"\n'
                    'audit_tag = "QA_AUDIT"\n'
                    'role_deps = []\n'
                    'star_role_deps = []\n'
                    'feedback_role_deps = ["low"]\n'
                )

            main_low = os.path.join(main_root, "scope", "low")
            os.makedirs(main_low, exist_ok=True)
            target = os.path.join(main_low, "sample.pyi")
            with open(target, "w", encoding="utf-8") as f:
                f.write(
                    '# --- CLEANROOM METADATA ---\n'
                    '# LAST_CLEANED: 2026-10-15T00:00:00Z\n'
                    '# LAST_CHANGED: 2026-10-15T00:00:00Z\n'
                    '# CHANGE: initial spec\n'
                    '# --- END CLEANROOM METADATA ---\n'
                    'def test() -> None: ...\n'
                )

            # Write audit buffer file
            audit_buf = os.path.join(ws_dir, ".cleanroom_audit_buffer.json")
            with open(audit_buf, "w", encoding="utf-8") as f:
                json.dump([{"target": "scope/low/sample.pyi", "audit_tag": "QA_AUDIT"}], f)

            res = self.sync.harvest(ws_dir, main_root, "qa", "scope")
            self.assertEqual(list(res.stamped_audits), ["scope/low/sample.pyi"])

    def test_harvest_conflict_raises_runtime_error(self) -> None:
        import os
        import tempfile
        from update_with_ai.parts.metadata.lib import src_metadata

        with tempfile.TemporaryDirectory() as main_root, tempfile.TemporaryDirectory() as ws_dir:
            roles_file = os.path.join(main_root, "cleanroom_roles.toml")
            with open(roles_file, "w", encoding="utf-8") as f:
                f.write('[roles.lib]\nname = "lib"\nsrc_pattern = "{unit_dir}/lib/{unit_name}.py"\n')

            main_lib = os.path.join(main_root, "scope", "lib")
            ws_lib = os.path.join(ws_dir, "scope", "lib")
            os.makedirs(main_lib, exist_ok=True)
            os.makedirs(ws_lib, exist_ok=True)

            main_f = os.path.join(main_lib, "test.py")
            ws_f = os.path.join(ws_lib, "test.py")

            with open(main_f, "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            src_metadata.record_change(main_f, "initial")

            self.sync.pull(ws_dir, main_root, "lib", "scope")

            # Main is modified concurrently
            with open(main_f, "w", encoding="utf-8") as f:
                f.write("x = 2\n")
            src_metadata.record_change(main_f, "concurrent edit")

            # Workspace is also modified while keeping its metadata header with code_hash
            with open(ws_f, "a", encoding="utf-8") as f:
                f.write("# local edit\n")

            with self.assertRaises(RuntimeError) as ctx:
                self.sync.harvest(ws_dir, main_root, "lib", "scope")
            self.assertIn("Conflict detected during harvest", str(ctx.exception))


    def test_helpers(self) -> None:
        import tempfile
        from update_with_ai.parts.workspace.lib import sync_impl

        matched = sync_impl._find_matching_files(".", ["*.nonexistent"])
        self.assertEqual(matched, [])

        self.assertTrue(sync_impl._is_runtime_support_library("support/lib/lifecycle.py"))
        self.assertFalse(sync_impl._is_runtime_support_library("support/lib/lint_tool.py"))

        d, sfx, ext = sync_impl._parse_pat_to_glob("{unit_dir}/lib/{unit_name}.py")
        self.assertEqual(d, "lib")
        self.assertEqual(ext, ".py")

        with tempfile.TemporaryDirectory() as tmp_root:
            pkg = sync_impl._resolve_active_methodology_pkg(tmp_root, "scope")
            self.assertIsNone(pkg)



