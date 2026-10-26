"""Pretense state machine, fake synthesis, unit tests, parity tests, and fuzzing for DshWorkspaceConfigurer."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.dsh.lib import dsh_workspace, dsh_workspace_impl
from update_with_ai.parts.dsh.lib.dsh_workspace import (
    DshWorkspaceConfinementReport,
    DshWorkspaceConfigurer,
)
from update_with_ai.parts.workspace.lib import role_registry


@dataclass
class DshWorkspaceState:
    """Canonical model state for DshWorkspace."""
    configured_workspaces: Dict[str, DshWorkspaceConfinementReport] = field(default_factory=dict)


proto = StateMachineProto[DshWorkspaceState]()


# ==============================================================================
# 1. DshWorkspaceConfigurer Transitions
# ==============================================================================

@proto.transition(DshWorkspaceConfigurer.configure_role_workspace)
def configure_role_workspace(): pass

@configure_role_workspace.arguments
def _(
    state: DshWorkspaceState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    role_name: str | NotBoundType = NotBound,
    model_name: Optional[str] | NotBoundType = NotBound,
    provider: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, Optional[str], Optional[str]]]:
    ws = "/tmp/sample_ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    r = "low" if isinstance(role_name, NotBoundType) else str(role_name)
    m = None if isinstance(model_name, NotBoundType) else model_name
    p = None if isinstance(provider, NotBoundType) else provider
    return (ws, r, m, p)

@configure_role_workspace.returns
def _(
    state: DshWorkspaceState,
    this: Any,
    workspace_dir: str,
    role_name: str,
    model_name: Optional[str],
    provider: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[DshWorkspaceConfinementReport]]:
    agents_md = os.path.join(workspace_dir, "AGENTS.md")
    patch_path = os.path.join(workspace_dir, ".cleanroom", "dsh_patch.yml")
    expected = DshWorkspaceConfinementReport(
        workspace_dir=workspace_dir,
        role_name=role_name,
        configured_files=[agents_md, patch_path],
        status="configured",
    )
    state.configured_workspaces[workspace_dir] = expected

    if isinstance(outcome, Value) and outcome.val.status == "configured":
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 2. Synthesized Fake Implementation
# ==============================================================================

def make_dsh_workspace_fake(
    state: Optional[DshWorkspaceState] = None,
) -> DshWorkspaceConfigurer:
    """Instantiate a synthesized DshWorkspaceConfigurer fake."""
    st = state or DshWorkspaceState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(DshWorkspaceConfigurer)


# ==============================================================================
# 3. Deterministic Unit Tests
# ==============================================================================

class _FakeWorkspaceRegistry:
    tier = agent_session.agent_session

    def resolve_role_definition(
        self,
        role_name_or_address: str,
        repo_root: Optional[str] = None,
        dir_scope: Optional[str] = None,
    ) -> role_registry.RoleDefinition:
        clean = role_name_or_address.split(":")[-1].strip().lower()
        if clean in ("qa", "coverage", "spec_qa"):
            return role_registry.RoleDefinition(
                role_name=clean,
                guide_path=f"guides/{clean}.md",
                writable_file_patterns=[],
                readonly_file_patterns=[],
                feedback_role_deps=["lib", "test"],
                audit_tag=f"{clean.upper()}_AUDIT",
            )
        return role_registry.RoleDefinition(
            role_name=clean,
            guide_path=f"guides/{clean}.md",
            writable_file_patterns=[f"{clean}/*"],
            readonly_file_patterns=[],
            feedback_role_deps=["planning"] if clean in ("low", "scenarios") else [],
        )


class TestDshWorkspaceUnit(unittest.TestCase):
    """Deterministic unit tests validating state machine and synthesized fake."""

    def test_configure_role_workspace(self) -> None:
        fake = make_dsh_workspace_fake()
        report = fake.configure_role_workspace(
            workspace_dir="/tmp/sample_ws",
            role_name="low",
            model_name="deepseek-chat",
        )
        self.assertEqual(report.status, "configured")
        self.assertEqual(report.workspace_dir, "/tmp/sample_ws")
        self.assertEqual(report.role_name, "low")
        self.assertEqual(len(report.configured_files), 2)
        self.assertIn("/tmp/sample_ws/AGENTS.md", report.configured_files)


class TestDshWorkspaceParity(unittest.TestCase):
    """Parity tests verifying alignment between real implementation and state machine."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        dsh_workspace_impl.__initialize__(self.registry)
        self.registry.register_instance(
            _FakeWorkspaceRegistry(),
            keys=[role_registry.WorkspaceRegistry],
            tier=agent_session.agent_session,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_configure_parity(self) -> None:
        fake = make_dsh_workspace_fake()
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            real = scope.get_singleton(dsh_workspace.DshWorkspaceConfigurer)
            real_report = real.configure_role_workspace(
                workspace_dir=self.test_dir,
                role_name="lib",
                model_name="deepseek-flash",
            )
            fake_report = fake.configure_role_workspace(
                workspace_dir=self.test_dir,
                role_name="lib",
                model_name="deepseek-flash",
            )

            self.assertEqual(real_report.status, fake_report.status)
            self.assertEqual(real_report.workspace_dir, fake_report.workspace_dir)
            self.assertEqual(real_report.role_name, fake_report.role_name)
            self.assertEqual(
                sorted(real_report.configured_files), sorted(fake_report.configured_files)
            )


class TestDshWorkspaceFuzz(unittest.TestCase):
    """Hypothesis fuzz tests for workspace configuration."""

    @given(
        workspace_dir=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_/-", min_size=1, max_size=30
        ),
        role_name=st.sampled_from(["high", "planning", "low", "lib", "test", "qa", "coverage"]),
    )
    @settings(max_examples=25)
    def test_workspace_configuration_invariants(
        self, workspace_dir: str, role_name: str
    ) -> None:
        state = DshWorkspaceState()
        fake = make_dsh_workspace_fake(state)
        report = fake.configure_role_workspace(
            workspace_dir=workspace_dir,
            role_name=role_name,
        )
        self.assertEqual(report.status, "configured")
        self.assertEqual(report.workspace_dir, workspace_dir)
        self.assertEqual(report.role_name, role_name)
        self.assertEqual(len(report.configured_files), 2)
        self.assertIn(workspace_dir, state.configured_workspaces)
