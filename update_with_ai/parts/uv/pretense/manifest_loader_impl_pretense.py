"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for UvManifestLoader."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress
from update_with_ai.parts.uv.lib.manifest_loader import (
    TargetLabel,
    TargetManifest,
    UvManifestLoader,
)


@dataclass
class ManifestLoaderState:
    """Canonical model state for UvManifestLoader."""
    manifests: PretenseDict[str, TargetManifest] = field(default_factory=PretenseDict)


class ManifestLoaderStateMachine(StateMachine[ManifestLoaderState]):
    """Pretense StateMachine for UvManifestLoader."""

    def __init__(self, state: Optional[ManifestLoaderState] = None):
        super().__init__(state=state or ManifestLoaderState())

    # ==============================================================================
    # 1. Seeding Transitions
    # ==============================================================================

    @transition.seeding()
    def seed_manifest(
        self,
        ctx: TransitionContext[None, [str, str, str], None],
    ) -> None:
        ctx.arguments(
                    unit_address=Domain(strategy=lambda: '//parts/core:core'),
                    role_address=Domain(strategy=lambda: 'lib'),
                    label=Domain(strategy=lambda: '//parts/core:core#lib'),
                )
        def _consequent(
            res: None,
            unit_address: str = "//parts/core:core",
            role_address: str = "lib",
            label: str = "//parts/core:core#lib",
        ) -> None:
            manifest = TargetManifest(
                label=TargetLabel(label),
                dependencies=(),
                silent_dependencies=(),
                star_dependencies=(),
                feedback_dependencies=(),
            )
            key = f"{unit_address}#{role_address}"
            self.state.manifests[key] = manifest
        ctx.update(_consequent)

    # ==============================================================================
    # 2. Manifest Loader Transitions
    # ==============================================================================

    @transition(UvManifestLoader.retrieve_manifest)
    def retrieve_manifest(
        self,
        ctx: TransitionContext[UvManifestLoader, [DagNode], Optional[TargetManifest]],
    ) -> None:
        ctx.arguments(node=Domain(strategy=lambda: DagNode(UnitAddress('//parts/core:core'), RoleAddress('lib'))))
        def _returns(node: Optional[DagNode] = None) -> Optional[TargetManifest]:
            if node is None:
                return None
            key = f"{node.unit_address}#{node.role_address}"
            return self.state.manifests.get(key)
        ctx.returns(_returns)

    @transition(UvManifestLoader.load_manifest)
    def load_manifest(
        self,
        ctx: TransitionContext[UvManifestLoader, [DagNode], None],
    ) -> None:
        ctx.arguments(node=Domain(strategy=lambda: DagNode(UnitAddress('//parts/core:core'), RoleAddress('lib'))))
        ctx.returns(lambda node=None: None)


proto = ManifestLoaderStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_manifest_loader_fake(state: Optional[ManifestLoaderState] = None) -> UvManifestLoader:
    """Instantiate a synthesized UvManifestLoader fake."""
    sm = ManifestLoaderStateMachine(state)
    return sm.as_fake(UvManifestLoader)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestManifestLoaderUnit(unittest.TestCase):
    """Unit tests for synthesized UvManifestLoader fake."""

    def setUp(self) -> None:
        self.state = ManifestLoaderState()
        self.sm = ManifestLoaderStateMachine(self.state)
        self.sm.seed_manifest("//parts/core:core", "lib", "//parts/core:core#lib")
        self.fake: UvManifestLoader = self.sm.as_fake(UvManifestLoader)

    def test_retrieve_manifest(self) -> None:
        node = DagNode(UnitAddress("//parts/core:core"), RoleAddress("lib"))
        manifest = self.fake.retrieve_manifest(node)
        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(manifest.label, "//parts/core:core#lib")

    def test_load_manifest(self) -> None:
        node = DagNode(UnitAddress("//parts/core:core"), RoleAddress("lib"))
        self.fake.load_manifest(node)


class TestManifestLoaderImplReal(unittest.TestCase):
    """Direct unit tests for manifest_loader_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.core.lib import file_paths_impl
        from update_with_ai.parts.dag.lib import subgraph_impl
        from update_with_ai.parts.metadata.lib import src_metadata_impl, src_storage_impl
        from update_with_ai.parts.uv.lib import manifest_loader, manifest_loader_impl, target_impl
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

        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.loader = self.scope.get_singleton(manifest_loader_impl.UvManifestLoader)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_retrieve_manifest_and_load_manifest(self) -> None:
        node = DagNode(UnitAddress("//update_with_ai/parts/core:file_paths"), RoleAddress("lib"))
        manifest = self.loader.retrieve_manifest(node)
        if manifest is not None:
            self.assertIn("file_paths", str(manifest.label))
            self.loader.load_manifest(node)


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestManifestLoaderFuzz(unittest.TestCase):
    """Property fuzz testing for UvManifestLoader."""

    @settings(max_examples=30)
    @given(
        unit=st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
        role=st.sampled_from(["high", "planning", "low", "lib", "test"]),
    )
    def test_manifest_invariants(self, unit: str, role: str) -> None:
        state = ManifestLoaderState()
        sm = ManifestLoaderStateMachine(state)
        sm.seed_manifest(f"//pkg:{unit}", role, f"//pkg:{unit}#{role}")
        fake = sm.as_fake(UvManifestLoader)

        node = DagNode(UnitAddress(f"//pkg:{unit}"), RoleAddress(role))
        manifest = fake.retrieve_manifest(node)
        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(manifest.label, f"//pkg:{unit}#{role}")
