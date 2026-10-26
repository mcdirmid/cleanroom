"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for CoverageEvaluator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tempfile
import textwrap
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.workspace_cli.lib.coverage import CoverageEvaluator, ModuleCoverage


@dataclass
class CoverageState:
    """Canonical model state for CoverageEvaluator."""
    default_report: str = "coverage report"


proto = StateMachineProto[CoverageState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_coverage_data(): pass

@seed_coverage_data.arguments
def _(
    state: CoverageState,
    this: Any,
    default_report: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    r = "report" if isinstance(default_report, NotBoundType) else str(default_report)
    return (r,)

@seed_coverage_data.provide
def _(
    state: CoverageState,
    this: Any,
    default_report: str,
    result: None = None,
) -> None:
    state.default_report = default_report


# ==============================================================================
# 2. Coverage Transitions
# ==============================================================================

@proto.transition(CoverageEvaluator.format_ranges)
def format_ranges(): pass

@format_ranges.arguments
def _(
    state: CoverageState,
    this: Any,
    lines: Sequence[int] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[int]]]:
    l = () if isinstance(lines, NotBoundType) else tuple(lines)
    return (l,)

@format_ranges.returns
def _(
    state: CoverageState,
    this: Any,
    lines: Sequence[int],
    outcome: object = NotBound,
) -> Optional[Outcome[str]]:
    if not lines:
        return Value("")
    sorted_lines = sorted(lines)
    spans: List[Tuple[int, int]] = []
    start = sorted_lines[0]
    end = start
    for line in sorted_lines[1:]:
        if line == end + 1:
            end = line
        else:
            spans.append((start, end))
            start = line
            end = line
    spans.append((start, end))
    formatted = ", ".join(f"{s}-{e}" if s != e else str(s) for s, e in spans)
    return Value(formatted)


@proto.transition(CoverageEvaluator.group_into_spans)
def group_into_spans(): pass

@group_into_spans.arguments
def _(
    state: CoverageState,
    this: Any,
    lines: Sequence[int] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[int]]]:
    l = () if isinstance(lines, NotBoundType) else tuple(lines)
    return (l,)

@group_into_spans.returns
def _(
    state: CoverageState,
    this: Any,
    lines: Sequence[int],
    outcome: object = NotBound,
) -> Optional[Outcome[List[Tuple[int, int]]]]:
    if not lines:
        return Value([])
    sorted_lines = sorted(lines)
    spans: List[Tuple[int, int]] = []
    start = sorted_lines[0]
    end = start
    for line in sorted_lines[1:]:
        if line == end + 1:
            end = line
        else:
            spans.append((start, end))
            start = line
            end = line
    spans.append((start, end))
    return Value(spans)


@proto.transition(CoverageEvaluator.normalize_target_query)
def normalize_target_query(): pass

@normalize_target_query.arguments
def _(
    state: CoverageState,
    this: Any,
    raw_query: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    q = "sample_test" if isinstance(raw_query, NotBoundType) else str(raw_query)
    return (q,)

@normalize_target_query.returns
def _(
    state: CoverageState,
    this: Any,
    raw_query: str,
    outcome: object = NotBound,
) -> Optional[Outcome[str]]:
    cleaned = raw_query.split(":")[-1].split("/")[-1]
    if cleaned.endswith(".py"):
        cleaned = cleaned[:-3]
    return Value(cleaned)


@proto.transition(CoverageEvaluator.format_spans_report)
def format_spans_report(): pass

@format_spans_report.arguments
def _(
    state: CoverageState,
    this: Any,
    cov: ModuleCoverage | NotBoundType = NotBound,
    max_spans: Optional[int] | NotBoundType = NotBound,
) -> Optional[Tuple[ModuleCoverage, Optional[int]]]:
    mc = (
        ModuleCoverage(
            module_name="demo",
            test_name="demo_test",
            file_path="demo.py",
            test_path="demo_test.py",
            total_executable=10,
            covered=8,
            missed=2,
            coverage_pct=80.0,
            missing_lines=[9, 10],
            missing_ranges="9-10",
            missing_spans=[(9, 10)],
        )
        if isinstance(cov, NotBoundType)
        else cov
    )
    ms = None if isinstance(max_spans, NotBoundType) else max_spans
    return (mc, ms)

@format_spans_report.returns
def _(
    state: CoverageState,
    this: Any,
    cov: ModuleCoverage,
    max_spans: Optional[int],
    outcome: object = NotBound,
) -> Optional[Outcome[str]]:
    return Value(f"Report for {cov.module_name}: {cov.missing_ranges}")


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_coverage_fake(state: Optional[CoverageState] = None) -> CoverageEvaluator:
    """Instantiate a synthesized CoverageEvaluator fake."""
    st = state or CoverageState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(CoverageEvaluator)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestCoverageEvaluatorUnit(unittest.TestCase):
    """Unit tests for synthesized CoverageEvaluator fake."""

    def setUp(self) -> None:
        self.state = CoverageState()
        self.sm = proto.make_state_machine(self.state)
        self.fake: CoverageEvaluator = self.sm.as_fake(CoverageEvaluator)

    def test_format_ranges(self) -> None:
        self.assertEqual(self.fake.format_ranges([]), "")
        self.assertEqual(self.fake.format_ranges([5]), "5")
        self.assertEqual(self.fake.format_ranges([1, 2, 3, 7, 8, 12]), "1-3, 7-8, 12")

    def test_group_into_spans(self) -> None:
        self.assertEqual(self.fake.group_into_spans([]), [])
        self.assertEqual(self.fake.group_into_spans([4]), [(4, 4)])
        self.assertEqual(self.fake.group_into_spans([1, 2, 3, 5]), [(1, 3), (5, 5)])

    def test_normalize_target_query(self) -> None:
        self.assertEqual(self.fake.normalize_target_query("//parts/tools:tool_test"), "tool_test")
        self.assertEqual(self.fake.normalize_target_query("update_with_ai/foo.py"), "foo")


class TestCoverageEvaluatorImplReal(unittest.TestCase):
    """Direct unit tests for coverage_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry
        from update_with_ai.parts.workspace_cli.lib import coverage, coverage_impl

        self.registry = LifecycleRegistry()
        coverage_impl.__initialize__(self.registry)
        self.evaluator = coverage_impl.CoverageEvaluator()
        self.registry.register_instance(
            self.evaluator,
            keys=[
                coverage.CoverageEvaluator,
                coverage_impl.CoverageEvaluator,
            ],
        )

    def test_format_ranges_and_spans(self) -> None:
        self.assertEqual(self.evaluator.format_ranges([]), "")
        self.assertEqual(self.evaluator.format_ranges([5]), "5")
        self.assertEqual(self.evaluator.format_ranges([1, 2, 3, 7, 8, 12]), "1-3, 7-8, 12")
        self.assertEqual(self.evaluator.format_ranges([10, 11, 12, 13]), "10-13")

        self.assertEqual(self.evaluator.group_into_spans([]), [])
        self.assertEqual(self.evaluator.group_into_spans([4]), [(4, 4)])
        self.assertEqual(self.evaluator.group_into_spans([1, 2, 3, 5, 8, 9]), [(1, 3), (5, 5), (8, 9)])

    def test_normalize_target_query(self) -> None:
        self.assertEqual(self.evaluator.normalize_target_query("//parts/tools:tool_coverage_impl_test"), "tool_coverage_impl_test")
        self.assertEqual(self.evaluator.normalize_target_query("update_with_ai/lib/foo_impl.py"), "foo_impl")
        self.assertEqual(self.evaluator.normalize_target_query("bar_test"), "bar_test")

    def test_get_non_executable_lines(self) -> None:
        src = textwrap.dedent(
            '''
            """Module docstring."""
            from typing import Optional

            def sample_function(
                arg1: int,
                arg2: Optional[str] = None,
            ) -> bool:
                """Function docstring."""
                if arg1 > 0:
                    return True
                else:  # pragma: no cover
                    return False
            '''
        ).strip()

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(src)
            f_path = f.name

        try:
            ignored = self.evaluator.get_non_executable_lines(f_path)
            self.assertIn(1, ignored)  # docstring
            self.assertIn(7, ignored)  # function docstring
        finally:
            Path(f_path).unlink(missing_ok=True)

    def test_format_spans_report(self) -> None:
        src = "line 1\nline 2\nline 3\nline 4\nline 5\n"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(src)
            f_path = f.name

        try:
            cov = ModuleCoverage(
                module_name="test_mod",
                test_name="test_test",
                file_path=f_path,
                test_path="test_test.py",
                total_executable=5,
                covered=3,
                missed=2,
                coverage_pct=60.0,
                missing_lines=[2, 3],
                missing_ranges="2-3",
                missing_spans=[(2, 3)],
            )
            report = self.evaluator.format_spans_report(cov, max_spans=1)
            self.assertIn("Uncovered statement spans in test_mod", report)
            self.assertIn("line 2", report)
        finally:
            Path(f_path).unlink(missing_ok=True)


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestCoverageEvaluatorFuzz(unittest.TestCase):
    """Property fuzz testing for CoverageEvaluator."""

    @settings(max_examples=30)
    @given(
        lines=st.lists(
            st.integers(min_value=1, max_value=100),
            min_size=0,
            max_size=20,
            unique=True,
        )
    )
    def test_ranges_invariants(self, lines: list[int]) -> None:
        state = CoverageState()
        sm = proto.make_state_machine(state)
        fake = sm.as_fake(CoverageEvaluator)

        spans = fake.group_into_spans(lines)
        ranges = fake.format_ranges(lines)
        if not lines:
            self.assertEqual(spans, [])
            self.assertEqual(ranges, "")
        else:
            self.assertTrue(len(spans) > 0)
            self.assertTrue(len(ranges) > 0)
