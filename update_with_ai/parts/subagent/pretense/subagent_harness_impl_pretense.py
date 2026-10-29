"""Pretense specifications and tests for subagent_harness_impl."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pretense import Domain, StateMachine, TransitionContext, transition
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import session as agent_session
from update_with_ai.parts.subagent.lib import (
    subagent_coordinator,
    subagent_harness,
    subagent_harness_impl,
)
from update_with_ai.parts.workspace_cli.lib import work


# ==============================================================================
# 1. Pretense State Definitions
# ==============================================================================

@dataclass
class HarnessRegistryState:
    installed: Dict[str, Any] = field(default_factory=dict)


class SubagentHarnessStateMachine(StateMachine[HarnessRegistryState]):
    """Unified Pretense State Machine for HarnessRegistry."""

    def __init__(
        self,
        state: Optional[HarnessRegistryState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or HarnessRegistryState(), singletons=singletons)

    @transition(subagent_harness.HarnessRegistry.install_harness)
    def install_harness(
        self,
        ctx: TransitionContext[subagent_harness.HarnessRegistry, [str, Any], None],
    ) -> None:
        ctx.arguments(
                    platform_name=Domain(strategy=lambda: 'test_platform'),
                    adapter_factory=Domain(strategy=lambda: lambda **kwargs: None),
                )
        ctx.returns(lambda platform_name="test_platform", adapter_factory=None: None)
        ctx.update(lambda res, platform_name="test_platform", adapter_factory=None: (
            self.state.installed.__setitem__(platform_name, adapter_factory)
        ))


proto = SubagentHarnessStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_harness_registry_fake(
    state: Optional[HarnessRegistryState] = None,
) -> subagent_harness.HarnessRegistry:
    """Instantiate a synthesized HarnessRegistry fake."""
    st = state or HarnessRegistryState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(subagent_harness.HarnessRegistry)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestHarnessRegistryUnit(unittest.TestCase):
    """Unit tests for synthesized HarnessRegistry fake."""

    def setUp(self) -> None:
        self.state = HarnessRegistryState()
        self.fake = make_harness_registry_fake(self.state)

    def test_install_harness(self) -> None:
        def factory(
            model_name: Optional[str] = None,
            timeout_seconds: Optional[float] = None,
            max_context_tokens: Optional[int] = None,
            custom_cmd: Optional[str] = None,
            simulation_mode: bool = False,
            **kwargs: Any,
        ) -> Any:
            return None
        self.fake.install_harness("my_plat", factory)
        self.assertIn("my_plat", self.state.installed)


class FakeWorkspaceWorkManager:
    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.pending: dict[str, list[str]] = {}

    def get_pending_work(self, workspace_dir: str) -> list[str]:
        return list(self.pending.get(workspace_dir, []))

    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        self.pending[workspace_dir] = list(targets)

    def clear_pending_work(self, workspace_dir: str) -> None:
        self.pending.pop(workspace_dir, None)

    def remove_pending_target(self, workspace_dir: str, target: str) -> bool:
        items = self.pending.get(workspace_dir, [])
        if target in items:
            items.remove(target)
            return True
        return False


class TestSubagentHarnessImplReal(unittest.TestCase):
    """Direct unit tests for subagent_harness_impl.py."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        subagent_harness_impl.__initialize__(self.registry)
        self.work_mgr = FakeWorkspaceWorkManager()
        self.registry.register_instance(
            self.work_mgr,
            keys=[work.WorkspaceWorkManager],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_format_task_prompt(self) -> None:
        adapter = subagent_harness_impl.CommandHarnessAdapter(simulation_mode=True)
        dispatch = subagent_coordinator.RoleDispatch(
            role_name="lib",
            workspace_dir=self.test_dir,
            dir_scope="pkg_a",
            ready_targets=("lib/module.py",),
        )
        prompt = adapter.format_task_prompt(dispatch)
        self.assertIn("Role: lib", prompt)
        self.assertIn("Scope: pkg_a", prompt)
        self.assertIn("- lib/module.py", prompt)

    def test_simulation_dispatch_and_await(self) -> None:
        adapter = subagent_harness_impl.CommandHarnessAdapter(simulation_mode=True)
        dispatch = subagent_coordinator.RoleDispatch(
            role_name="lib",
            workspace_dir=self.test_dir,
            dir_scope="pkg_a",
            ready_targets=("lib/a.py", "lib/b.py"),
        )
        handle = adapter.dispatch_role(dispatch)
        self.work_mgr.set_pending_work(self.test_dir, ["lib/b.py"])
        result = adapter.await_role(handle)
        self.assertEqual(result.status, "clean")
        self.assertEqual(result.submitted_targets, ("lib/a.py",))

    def test_harness_registry_resolve(self) -> None:
        reg = self.scope.get_singleton(subagent_harness.HarnessRegistry)
        adapter = reg.resolve_harness(platform_name="simulation", simulation_mode=True)
        self.assertIsNotNone(adapter)
