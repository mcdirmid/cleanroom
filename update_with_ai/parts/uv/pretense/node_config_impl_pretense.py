"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for NodeConfig."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.agent.lib.node_config import NodeConfig, NodeGuide
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress


@dataclass
class NodeConfigState:
    """Canonical model state for NodeConfig."""
    allows_step: bool = True
    is_step: bool = False


class NodeConfigStateMachine(StateMachine[NodeConfigState]):
    """Pretense StateMachine for NodeConfig."""

    def __init__(self, state: Optional[NodeConfigState] = None):
        super().__init__(state=state or NodeConfigState())

    # ==============================================================================
    # 1. Seeding Transitions
    # ==============================================================================

    @transition.seeding()
    def seed_node_config_data(
        self,
        ctx: TransitionContext[None, [bool, bool], None],
    ) -> None:
        ctx.arguments(
                    allows_step=Domain(strategy=lambda: True),
                    is_step=Domain(strategy=lambda: False),
                )
        def _consequent(res: None, allows_step: bool = True, is_step: bool = False) -> None:
            self.state.allows_step = allows_step
            self.state.is_step = is_step
        ctx.update(_consequent)

    # ==============================================================================
    # 2. NodeConfig Transitions
    # ==============================================================================

    @transition(getattr(NodeConfig, "allows_step_mode"))
    def allows_step_mode(
        self,
        ctx: TransitionContext[NodeConfig, [], bool],
    ) -> None:
        ctx.returns(lambda: self.state.allows_step)

    @transition(getattr(NodeConfig, "is_step_mode"))
    def is_step_mode(
        self,
        ctx: TransitionContext[NodeConfig, [], bool],
    ) -> None:
        ctx.returns(lambda: self.state.is_step)


proto = NodeConfigStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_node_config_fake(state: Optional[NodeConfigState] = None) -> NodeConfig:
    """Instantiate a synthesized NodeConfig fake."""
    sm = NodeConfigStateMachine(state)
    return sm.as_fake(NodeConfig)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestNodeConfigUnit(unittest.TestCase):
    """Unit tests for synthesized NodeConfig fake."""

    def setUp(self) -> None:
        self.state = NodeConfigState(allows_step=True, is_step=False)
        self.sm = NodeConfigStateMachine(self.state)
        self.fake: NodeConfig = self.sm.as_fake(NodeConfig)

    def test_allows_step_mode_and_is_step_mode(self) -> None:
        self.assertTrue(self.fake.allows_step_mode)
        self.assertFalse(self.fake.is_step_mode)


class TestNodeConfigImplReal(unittest.TestCase):
    """Direct unit tests for node_config_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.core.lib import file_paths_impl
        from update_with_ai.parts.dag.lib import subgraph_impl
        from update_with_ai.parts.metadata.lib import src_metadata_impl, src_storage_impl
        from update_with_ai.parts.uv.lib import manifest_loader_impl, node_config_impl, target_impl
        from update_with_ai.parts.workspace.lib import role_registry_impl, roles_impl

        self.registry = LifecycleRegistry()
        file_paths_impl.__initialize__(self.registry)
        target_impl.__initialize__(self.registry)
        roles_impl.__initialize__(self.registry)
        role_registry_impl.__initialize__(self.registry)
        src_metadata_impl.__initialize__(self.registry)
        src_storage_impl.__initialize__(self.registry)
        subgraph_impl.__initialize__(self.registry)
        manifest_loader_impl.__initialize__(self.registry)
        node_config_impl.__initialize__(self.registry)

        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.node_cfg = self.scope.get_singleton(node_config_impl.NodeConfig)
        self.alias_mgr = self.scope.get_singleton(node_config_impl.AliasManager)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_node_config_and_alias_manager(self) -> None:
        from update_with_ai.parts.agent.lib import file_alias
        from update_with_ai.parts.uv.lib import node_config_impl

        self.assertTrue(self.node_cfg.allows_step_mode)
        self.assertFalse(self.node_cfg.is_step_mode)
        self.assertIsInstance(self.node_cfg.read_only_files, set)
        self.assertIsInstance(self.node_cfg.read_write_files, set)

        # Verification check
        check = node_config_impl.CommandVerificationCheck(command="echo ok")
        ok, diag = check.verify()
        self.assertTrue(ok)

        # Alias manager
        sanitized = self.alias_mgr.sanitize_text(file_alias.UnsanitizedText("hello world"))
        self.assertIn("hello world", sanitized)


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestNodeConfigFuzz(unittest.TestCase):
    """Property fuzz testing for NodeConfig."""

    @settings(max_examples=30)
    @given(
        allows_step=st.booleans(),
        is_step=st.booleans(),
    )
    def test_node_config_invariants(self, allows_step: bool, is_step: bool) -> None:
        state = NodeConfigState(allows_step=allows_step, is_step=is_step)
        sm = NodeConfigStateMachine(state)
        fake = sm.as_fake(NodeConfig)

        self.assertEqual(fake.allows_step_mode, allows_step)
        self.assertEqual(fake.is_step_mode, is_step)



