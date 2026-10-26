"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for UvManifestLoader."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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


proto = StateMachineProto[ManifestLoaderState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_manifest(): pass

@seed_manifest.arguments
def _(
    state: ManifestLoaderState,
    this: Any,
    unit_address: str | NotBoundType = NotBound,
    role_address: str | NotBoundType = NotBound,
    label: str | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, str]]:
    u = "//parts/core:core" if isinstance(unit_address, NotBoundType) else str(unit_address)
    r = "lib" if isinstance(role_address, NotBoundType) else str(role_address)
    l = f"{u}#{r}" if isinstance(label, NotBoundType) else str(label)
    return (u, r, l)

@seed_manifest.provide
def _(
    state: ManifestLoaderState,
    this: Any,
    unit_address: str,
    role_address: str,
    label: str,
    result: None = None,
) -> None:
    manifest = TargetManifest(
        label=TargetLabel(label),
        dependencies=(),
        silent_dependencies=(),
        star_dependencies=(),
        feedback_dependencies=(),
    )
    key = f"{unit_address}#{role_address}"
    state.manifests[key] = manifest


# ==============================================================================
# 2. Manifest Loader Transitions
# ==============================================================================

@proto.transition(UvManifestLoader.retrieve_manifest)
def retrieve_manifest(): pass

@retrieve_manifest.arguments
def _(
    state: ManifestLoaderState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    n = DagNode(UnitAddress("//parts/core:core"), RoleAddress("lib")) if isinstance(node, NotBoundType) else node
    return (n,)

@retrieve_manifest.returns
def _(
    state: ManifestLoaderState,
    this: Any,
    node: DagNode,
    outcome: object = NotBound,
) -> Optional[Outcome[Optional[TargetManifest]]]:
    key = f"{node.unit_address}#{node.role_address}"
    expected = state.manifests.get(key)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(UvManifestLoader.load_manifest)
def load_manifest(): pass

@load_manifest.arguments
def _(
    state: ManifestLoaderState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    n = DagNode(UnitAddress("//parts/core:core"), RoleAddress("lib")) if isinstance(node, NotBoundType) else node
    return (n,)

@load_manifest.returns
def _(
    state: ManifestLoaderState,
    this: Any,
    node: DagNode,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    return Value(None)


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_manifest_loader_fake(state: Optional[ManifestLoaderState] = None) -> UvManifestLoader:
    """Instantiate a synthesized UvManifestLoader fake."""
    st = state or ManifestLoaderState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(UvManifestLoader)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestManifestLoaderUnit(unittest.TestCase):
    """Unit tests for synthesized UvManifestLoader fake."""

    def setUp(self) -> None:
        self.state = ManifestLoaderState()
        self.sm = proto.make_state_machine(self.state)
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
        sm = proto.make_state_machine(state)
        sm.seed_manifest(f"//pkg:{unit}", role, f"//pkg:{unit}#{role}")
        fake = sm.as_fake(UvManifestLoader)

        node = DagNode(UnitAddress(f"//pkg:{unit}"), RoleAddress(role))
        manifest = fake.retrieve_manifest(node)
        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(manifest.label, f"//pkg:{unit}#{role}")
