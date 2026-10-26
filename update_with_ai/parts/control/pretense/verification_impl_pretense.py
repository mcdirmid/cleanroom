"""Pretense state machine, fake synthesis, unit tests, parity tests, and fuzzing for VerificationEvaluator."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseDict
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.control.lib import verification, verification_impl
from update_with_ai.parts.control.lib.verification import (
    VerificationEvaluator,
    VerificationResult,
)
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress


@dataclass
class VerificationState:
    """Canonical model state for verification evaluator."""
    results_by_node: PretenseDict[DagNode, VerificationResult] = field(default_factory=PretenseDict)
    default_result: VerificationResult = field(
        default_factory=lambda: VerificationResult(passed=True, diagnostic_output="All checks passed.", is_cached=False)
    )


proto = StateMachineProto[VerificationState]()


# Noise patterns matching verification_impl._NOISE_PATTERNS
_NOISE_PATTERNS = (
    re.compile(r"^INFO: Analyzed target"),
    re.compile(r"^INFO: Found \d+ test target"),
    re.compile(r"^INFO: Elapsed time"),
    re.compile(r"^INFO: Total time"),
    re.compile(r"^INFO: Build (completed|time)"),
    re.compile(r"^INFO: \d+ processes"),
    re.compile(r"^Elapsed time"),
    re.compile(r"^\[\d+ / \d+\]"),
    re.compile(r"^Loading:"),
    re.compile(r"^Analyzing:"),
    re.compile(r"^Target //"),
    re.compile(r"^bazel-bin/"),
    re.compile(r"^Executed \d+ out of"),
)


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_verification_result(): pass

@seed_verification_result.arguments
def _(
    state: VerificationState,
    this: Any,
    node: Optional[DagNode] | NotBoundType = NotBound,
    passed: bool | NotBoundType = NotBound,
    diagnostic: str | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[DagNode], bool, str]]:
    n = None if isinstance(node, NotBoundType) else node
    p = True if isinstance(passed, NotBoundType) else bool(passed)
    d = "Passed" if isinstance(diagnostic, NotBoundType) else str(diagnostic)
    return (n, p, d)

@seed_verification_result.provide
def _(
    state: VerificationState,
    this: Any,
    node: Optional[DagNode],
    passed: bool,
    diagnostic: str,
    result: None = None,
) -> None:
    res = VerificationResult(passed=passed, diagnostic_output=diagnostic, is_cached=False)
    if node is None:
        state.default_result = res
    else:
        state.results_by_node[node] = res


# ==============================================================================
# 2. VerificationEvaluator Transitions
# ==============================================================================

@proto.transition(VerificationEvaluator.clean_diagnostic_noise)
def clean_diagnostic_noise(): pass

@clean_diagnostic_noise.arguments
def _(
    state: VerificationState,
    this: Any,
    text: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    t = "INFO: Elapsed time 0.1s\nError on line 12" if isinstance(text, NotBoundType) else str(text)
    return (t,)

@clean_diagnostic_noise.returns
def _(
    state: VerificationState,
    this: Any,
    text: str,
    outcome: object = NotBound,
) -> Optional[Outcome[str]]:
    lines = text.splitlines()
    filtered = [
        line for line in lines
        if not any(pattern.search(line.strip()) for pattern in _NOISE_PATTERNS)
    ]
    expected = "\n".join(filtered).strip()
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(VerificationEvaluator.evaluate_verification)
def evaluate_verification(): pass

@evaluate_verification.arguments
def _(
    state: VerificationState,
    this: Any,
    target: Optional[DagNode] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[DagNode]]]:
    t = None if isinstance(target, NotBoundType) else target
    return (t,)

@evaluate_verification.returns
def _(
    state: VerificationState,
    this: Any,
    target: Optional[DagNode],
    outcome: object = NotBound,
) -> Optional[Outcome[VerificationResult]]:
    if target is not None and target in state.results_by_node:
        expected = state.results_by_node[target]
    else:
        expected = state.default_result

    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_verification_fake(state: Optional[VerificationState] = None) -> VerificationEvaluator:
    """Instantiate a synthesized VerificationEvaluator fake."""
    st = state or VerificationState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(VerificationEvaluator)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestVerificationEvaluatorUnit(unittest.TestCase):
    """Unit tests for synthesized VerificationEvaluator fake."""

    def setUp(self) -> None:
        self.state = VerificationState()
        self.sm = proto.make_state_machine(self.state)
        self.node = DagNode(UnitAddress("part_a"), RoleAddress("lib"))
        self.sm.seed_verification_result(self.node, passed=False, diagnostic="Compilation error in part_a")
        self.fake: VerificationEvaluator = self.sm.as_fake(VerificationEvaluator)

    def test_evaluate_verification_specific_node(self) -> None:
        res = self.fake.evaluate_verification(self.node)
        self.assertFalse(res.passed)
        self.assertEqual(res.diagnostic_output, "Compilation error in part_a")

    def test_evaluate_verification_default(self) -> None:
        res = self.fake.evaluate_verification(None)
        self.assertTrue(res.passed)

    def test_clean_diagnostic_noise(self) -> None:
        raw = "INFO: Build completed\nERROR: undefined symbol\n[1 / 2] Compiling\nDone."
        cleaned = self.fake.clean_diagnostic_noise(raw)
        self.assertEqual(cleaned, "ERROR: undefined symbol\nDone.")


# ==============================================================================
# 5. Parity Tests
# ==============================================================================

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import file_alias, node_config
from update_with_ai.parts.agent.lib.session import agent_session
from update_with_ai.parts.core.lib import file_paths


class MockCheckWithVerify:
    def __init__(self, passed: bool, diagnostic: str = "") -> None:
        self.passed = passed
        self.diagnostic = diagnostic

    def verify(self) -> Tuple[bool, str]:
        return self.passed, self.diagnostic


class MockCheckWithCommand:
    def __init__(self, command: str) -> None:
        self.command = command


class MockNodeConfigVerification:
    tier = agent_session

    def __init__(self) -> None:
        self.verification_checks_by_node: Dict[DagNode, List[Any]] = {}
        self.read_write_files: List[Any] = []


class MockRoleConfigVerification:
    tier = agent_session

    def __init__(self) -> None:
        self.nodes: List[DagNode] = []


class TestVerificationEvaluatorReal(unittest.TestCase):
    """Direct unit tests for verification_impl.VerificationEvaluator."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        verification_impl.__initialize__(self.registry)

        self.mock_node_cfg = MockNodeConfigVerification()
        self.mock_role_cfg = MockRoleConfigVerification()

        self.registry.register_instance(self.mock_node_cfg, keys=[node_config.NodeConfig], tier=agent_session)
        self.registry.register_instance(self.mock_role_cfg, keys=[node_config.RoleConfig], tier=agent_session)

        self.node = DagNode(UnitAddress("pkg:unit"), RoleAddress("lib"))

    def test_evaluate_verification_specific_target(self) -> None:
        self.mock_node_cfg.verification_checks_by_node[self.node] = [
            MockCheckWithVerify(passed=True, diagnostic=""),
        ]

        with enter_phase(agent_session, registry=self.registry) as scope:
            evaluator = scope.get_singleton(verification_impl.VerificationEvaluator)

            # First run: evaluated
            res1 = evaluator.evaluate_verification(self.node)
            self.assertTrue(res1.passed)
            self.assertFalse(res1.is_cached)

            # Second run: cached
            res2 = evaluator.evaluate_verification(self.node)
            self.assertTrue(res2.passed)
            self.assertTrue(res2.is_cached)

    def test_evaluate_verification_failure_and_command(self) -> None:
        self.mock_node_cfg.verification_checks_by_node[self.node] = [
            MockCheckWithVerify(passed=False, diagnostic="Syntax error on line 5"),
        ]

        with enter_phase(agent_session, registry=self.registry) as scope:
            evaluator = scope.get_singleton(verification_impl.VerificationEvaluator)
            res = evaluator.evaluate_verification(self.node)
            self.assertFalse(res.passed)
            self.assertIn("Syntax error on line 5", res.diagnostic_output)

        # Check passed with diagnostic
        self.mock_node_cfg.verification_checks_by_node[self.node] = [
            MockCheckWithVerify(passed=True, diagnostic="Warning: unused variable"),
        ]
        with enter_phase(agent_session, registry=self.registry) as scope:
            evaluator = scope.get_singleton(verification_impl.VerificationEvaluator)
            res = evaluator.evaluate_verification(self.node)
            self.assertTrue(res.passed)
            self.assertIn("Warning: unused variable", res.diagnostic_output)

        # Command-based check
        self.mock_node_cfg.verification_checks_by_node[self.node] = [
            MockCheckWithCommand("true"),
        ]
        with enter_phase(agent_session, registry=self.registry) as scope:
            evaluator = scope.get_singleton(verification_impl.VerificationEvaluator)
            res_cmd = evaluator.evaluate_verification(self.node)
            self.assertTrue(res_cmd.passed)

        # Command-based failing check
        self.mock_node_cfg.verification_checks_by_node[self.node] = [
            MockCheckWithCommand("false"),
        ]
        with enter_phase(agent_session, registry=self.registry) as scope:
            evaluator = scope.get_singleton(verification_impl.VerificationEvaluator)
            res_fail = evaluator.evaluate_verification(self.node)
            self.assertFalse(res_fail.passed)

    def test_evaluate_verification_global_all_open(self) -> None:
        self.mock_role_cfg.nodes = [self.node]
        self.mock_node_cfg.verification_checks_by_node[self.node] = [
            MockCheckWithVerify(passed=True, diagnostic=""),
        ]

        with enter_phase(agent_session, registry=self.registry) as scope:
            evaluator = scope.get_singleton(verification_impl.VerificationEvaluator)

            # Global evaluation
            res1 = evaluator.evaluate_verification(None)
            self.assertTrue(res1.passed)
            self.assertFalse(res1.is_cached)

            # Global evaluation cached
            res2 = evaluator.evaluate_verification(None)
            self.assertTrue(res2.passed)
            self.assertTrue(res2.is_cached)

    def test_helpers(self) -> None:
        ws_root = file_paths.WorkspaceRoot(file_paths.PathString("/ws"))
        ws_path = file_paths.WorkspacePath(file_paths.PathString("dir/file.py"))
        bound = file_alias.BoundFile(file_alias.RelativePath("dir/file.py"), ws_path, owning_node=self.node)
        self.assertEqual(verification_impl._bound_file_path(bound), "dir/file.py")
        self.assertEqual(verification_impl._bound_file_path("simple.py"), "simple.py")

        self.assertEqual(verification_impl._compute_path_hash("nonexistent_path"), "")


class TestVerificationEvaluatorParity(unittest.TestCase):
    """Parity tests between Pretense fake and real VerificationEvaluator implementation."""

    def setUp(self) -> None:
        self.fake = make_verification_fake()
        self.real = verification_impl.VerificationEvaluator()

    def test_clean_diagnostic_noise_parity(self) -> None:
        dirty_output = (
            "INFO: Analyzed target //parts/core:core (0 packages loaded, 0 targets configured).\n"
            "Loading:\n"
            "Analyzing: 1 target (0 packages loaded, 0 targets configured)\n"
            "parts/core/lib/demo.py:10: error: Incompatible types in assignment\n"
            "INFO: Found 1 test target...\n"
            "Executed 1 out of 1 test: 1 test passes.\n"
            "INFO: Build completed successfully, 1 total action"
        )
        fake_cleaned = self.fake.clean_diagnostic_noise(dirty_output)
        real_cleaned = self.real.clean_diagnostic_noise(dirty_output)
        self.assertEqual(fake_cleaned, real_cleaned)
        self.assertEqual(fake_cleaned, "parts/core/lib/demo.py:10: error: Incompatible types in assignment")


# ==============================================================================
# 6. Hypothesis Fuzz Testing
# ==============================================================================

class TestVerificationEvaluatorFuzz(unittest.TestCase):
    """Property fuzz testing for VerificationEvaluator."""

    @settings(max_examples=30)
    @given(
        noise_prefixes=st.lists(
            st.sampled_from([
                "INFO: Analyzed target",
                "INFO: Found 2 test target",
                "INFO: Elapsed time 1.2s",
                "Loading:",
                "Analyzing:",
                "[1 / 5]",
            ]),
            min_size=1,
            max_size=5,
        ),
        real_messages=st.lists(
            st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz0123456789 -_:"),
            min_size=1,
            max_size=3,
        ),
    )
    def test_clean_noise_invariants(self, noise_prefixes: list[str], real_messages: list[str]) -> None:
        fake = make_verification_fake()
        lines = []
        for i, m in enumerate(real_messages):
            if i < len(noise_prefixes):
                lines.append(noise_prefixes[i])
            lines.append(m)

        cleaned = fake.clean_diagnostic_noise("\n".join(lines))
        # Ensure all noise prefixes were stripped
        for n in noise_prefixes:
            self.assertNotIn(n, cleaned.splitlines())
        # Ensure non-noise messages survived
        for m in real_messages:
            if m.strip():
                self.assertIn(m.strip(), cleaned)
