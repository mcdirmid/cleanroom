"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for CoverageEvaluator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tempfile
import textwrap
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from update_with_ai.parts.workspace_cli.lib.coverage import CoverageEvaluator, ModuleCoverage


@dataclass
class CoverageState:
    """Canonical model state for CoverageEvaluator."""
    default_report: str = "coverage report"


class CoverageStateMachine(StateMachine[CoverageState]):
    """Unified Pretense State Machine for CoverageEvaluator."""

    def __init__(
        self,
        state: Optional[CoverageState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or CoverageState(), singletons=singletons)

    @transition.seeding(name="seed_coverage_data")
    def seed_coverage_data(
        self,
        ctx: TransitionContext[Any, [str], None],
    ) -> None:
        ctx.arguments(default_report=Domain(strategy=lambda: 'report'))
        ctx.returns(lambda default_report="report": None)
        ctx.update(lambda res, default_report="report": setattr(self.state, "default_report", str(default_report)))

    @transition(CoverageEvaluator.format_ranges)
    def format_ranges(
        self,
        ctx: TransitionContext[CoverageEvaluator, [Sequence[int]], str],
    ) -> None:
        ctx.arguments(lines=Domain(strategy=lambda: ()))
        def returns(lines: Sequence[int] = ()) -> str:
            if not lines:
                return ""
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
            return ", ".join(f"{s}-{e}" if s != e else str(s) for s, e in spans)

        ctx.returns(returns)
        ctx.update(lambda res, lines=(): None)

    @transition(CoverageEvaluator.group_into_spans)
    def group_into_spans(
        self,
        ctx: TransitionContext[CoverageEvaluator, [Sequence[int]], List[Tuple[int, int]]],
    ) -> None:
        ctx.arguments(lines=Domain(strategy=lambda: ()))
        def returns(lines: Sequence[int] = ()) -> List[Tuple[int, int]]:
            if not lines:
                return []
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
            return spans

        ctx.returns(returns)
        ctx.update(lambda res, lines=(): None)

    @transition(CoverageEvaluator.normalize_target_query)
    def normalize_target_query(
        self,
        ctx: TransitionContext[CoverageEvaluator, [str], str],
    ) -> None:
        ctx.arguments(raw_query=Domain(strategy=lambda: 'sample_test'))
        def returns(raw_query: str = "sample_test") -> str:
            cleaned = raw_query.split(":")[-1].split("/")[-1]
            if cleaned.endswith(".py"):
                cleaned = cleaned[:-3]
            return cleaned

        ctx.returns(returns)
        ctx.update(lambda res, raw_query="sample_test": None)

    @transition(CoverageEvaluator.format_spans_report)
    def format_spans_report(
        self,
        ctx: TransitionContext[CoverageEvaluator, [ModuleCoverage, Optional[int]], str],
    ) -> None:
        ctx.arguments(
                    cov=Domain(strategy=lambda: ModuleCoverage(module_name='demo', test_name='demo_test', file_path='demo.py', test_path='demo_test.py', total_executable=10, covered=8, missed=2, coverage_pct=80.0, missing_lines=[9, 10], missing_ranges='9-10', missing_spans=[(9, 10)])),
                    max_spans=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda cov, max_spans=None: f"Report for {cov.module_name}: {cov.missing_ranges}")
        ctx.update(lambda res, cov, max_spans=None: None)


proto = CoverageStateMachine()


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
