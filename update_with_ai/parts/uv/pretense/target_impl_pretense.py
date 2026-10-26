"""Pretense state machine, fake synthesis, unit tests, parity tests, and fuzzing for UvTarget."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Dict, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseDict
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress
from update_with_ai.parts.uv.lib import target, target_impl
from update_with_ai.parts.uv.lib.target import NodeDirectory, TargetIdentifier, UvTarget


@dataclass
class TargetState:
    """Canonical model state for UvTarget."""
    overrides: PretenseDict[str, DagNode] = field(default_factory=PretenseDict)


proto = StateMachineProto[TargetState]()


def _canonical_normalize(raw: str) -> DagNode:
    s = raw.strip()
    role = ""
    if "#" in s:
        s, role = s.split("#", 1)

    if s.startswith("@@//"):
        s = s[2:]
    elif s.startswith("@//"):
        s = s[1:]

    if "//" in s:
        s = "//" + s.split("//", 1)[1]
    elif not s.startswith("//"):
        s = f"//{s.lstrip('/')}"

    if ":" not in s:
        parts = s[2:].split("/")
        tgt_name = parts[-1] if parts and parts[-1] else ""
        s = f"{s}:{tgt_name}"

    return DagNode(UnitAddress(s), RoleAddress(role))


# ==============================================================================
# 1. UvTarget Transitions
# ==============================================================================

@proto.transition(UvTarget.normalize_target)
def normalize_target(): pass

@normalize_target.arguments
def _(
    state: TargetState,
    this: Any,
    target_identifier: TargetIdentifier | str | NotBoundType = NotBound,
) -> Optional[Tuple[TargetIdentifier]]:
    t = TargetIdentifier("//parts/core:core") if isinstance(target_identifier, NotBoundType) else TargetIdentifier(str(target_identifier))
    return (t,)

@normalize_target.returns
def _(
    state: TargetState,
    this: Any,
    target_identifier: TargetIdentifier,
    outcome: object = NotBound,
) -> Optional[Outcome[DagNode]]:
    raw = str(target_identifier)
    if raw in state.overrides:
        expected = state.overrides[raw]
    else:
        expected = _canonical_normalize(raw)

    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(UvTarget.extract_node_dir)
def extract_node_dir(): pass

@extract_node_dir.arguments
def _(
    state: TargetState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    n = DagNode(UnitAddress("//parts/core:core"), RoleAddress("lib")) if isinstance(node, NotBoundType) else node
    return (n,)

@extract_node_dir.returns
def _(
    state: TargetState,
    this: Any,
    node: DagNode,
    outcome: object = NotBound,
) -> Optional[Outcome[NodeDirectory]]:
    addr = str(node.unit_address)
    pkg = addr.split(":")[0].lstrip("/").strip()
    expected = NodeDirectory(file_paths.PathString(pkg))
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 2. Helper Factory
# ==============================================================================

def make_uv_target_fake(state: Optional[TargetState] = None) -> UvTarget:
    """Instantiate a synthesized UvTarget fake."""
    st = state or TargetState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(UvTarget)


# ==============================================================================
# 3. Unit Tests
# ==============================================================================

class TestUvTargetUnit(unittest.TestCase):
    """Unit tests for synthesized UvTarget fake."""

    def setUp(self) -> None:
        self.fake = make_uv_target_fake()

    def test_normalize_target_label_syntax(self) -> None:
        node1 = self.fake.normalize_target(TargetIdentifier("//parts/core:core"))
        self.assertEqual(node1.unit_address, "//parts/core:core")
        self.assertEqual(node1.role_address, "")

        node2 = self.fake.normalize_target(TargetIdentifier("//parts/dag:dag#test"))
        self.assertEqual(node2.unit_address, "//parts/dag:dag")
        self.assertEqual(node2.role_address, "test")

    def test_extract_node_dir(self) -> None:
        node = DagNode(UnitAddress("//parts/metadata:metadata"), RoleAddress("lib"))
        node_dir = self.fake.extract_node_dir(node)
        self.assertEqual(node_dir.path, "parts/metadata")


# ==============================================================================
# 4. Parity Tests
# ==============================================================================

class TestUvTargetParity(unittest.TestCase):
    """Parity tests comparing fake with real target_impl.UvTarget."""

    def setUp(self) -> None:
        self.fake = make_uv_target_fake()
        self.real = target_impl.UvTarget()

    def test_normalize_target_parity(self) -> None:
        targets = [
            "//parts/core:core",
            "//parts/dag:dag#low",
            "@//parts/agent:agent#spec_qa",
        ]
        for t in targets:
            fake_node = self.fake.normalize_target(TargetIdentifier(t))
            real_node = self.real.normalize_target(TargetIdentifier(t))
            self.assertEqual(fake_node.unit_address, real_node.unit_address)
            self.assertEqual(fake_node.role_address, real_node.role_address)

    def test_normalize_file_paths_inference(self) -> None:
        node = self.real.normalize_target(TargetIdentifier("parts/core/lib/file_paths.py"))
        self.assertEqual(node.unit_address, "//parts/core:file_paths")
        self.assertEqual(node.role_address, "lib")

        node2 = self.real.normalize_target(TargetIdentifier("parts/core/tests/file_paths_test.py"))
        self.assertEqual(node2.unit_address, "//parts/core:file_paths")
        self.assertEqual(node2.role_address, "test")

        dir_res = self.real.extract_node_dir(node)
        self.assertEqual(dir_res.path, "parts/core")



# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestUvTargetFuzz(unittest.TestCase):
    """Property fuzz testing for UvTarget."""

    @settings(max_examples=30)
    @given(
        pkg=st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz_"),
        unit=st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz_"),
        role=st.sampled_from(["high", "planning", "low", "lib", "test", "spec_qa", "qa"]),
    )
    def test_target_normalization_invariants(self, pkg: str, unit: str, role: str) -> None:
        fake = make_uv_target_fake()
        raw = f"//{pkg}:{unit}#{role}"
        node = fake.normalize_target(TargetIdentifier(raw))
        self.assertEqual(node.unit_address, f"//{pkg}:{unit}")
        self.assertEqual(node.role_address, role)

        node_dir = fake.extract_node_dir(node)
        self.assertEqual(node_dir.path, pkg)
