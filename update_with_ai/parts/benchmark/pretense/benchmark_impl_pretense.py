"""Pretense specifications and tests for benchmark_impl."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pretense import Domain, StateMachine, TransitionContext, transition
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.benchmark.lib import benchmark
from update_with_ai.parts.benchmark.lib.benchmark_impl import (
    BenchmarkEvaluator as BenchmarkEvaluatorImpl,
    __initialize__,
)


# ==============================================================================
# 1. Pretense State Definitions
# ==============================================================================

@dataclass
class BenchmarkState:
    flights_executed: List[str] = field(default_factory=list)


class BenchmarkStateMachine(StateMachine[BenchmarkState]):
    """Unified Pretense State Machine for BenchmarkEvaluator."""

    def __init__(
        self,
        state: Optional[BenchmarkState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or BenchmarkState(), singletons=singletons)

    @transition(benchmark.BenchmarkEvaluator.get_suite_catalog)
    def get_suite_catalog(
        self,
        ctx: TransitionContext[benchmark.BenchmarkEvaluator, [], Mapping[str, Sequence[benchmark.BenchmarkUnit]]],
    ) -> None:
        ctx.arguments()
        ctx.returns(lambda: {})
        ctx.update(lambda res: None)

    @transition(benchmark.BenchmarkEvaluator.execute_flight)
    def execute_flight(
        self,
        ctx: TransitionContext[benchmark.BenchmarkEvaluator, ..., benchmark.FlightRecord],
    ) -> None:
        ctx.arguments(
                    arg_0=Domain(strategy=lambda: benchmark.ModelSpec(identifier='m', tier=1, tier_label='T1', provider='test', rate_uncached_in=0.1, rate_cached_in=0.01, rate_out=0.2)),
                    arg_1=Domain(strategy=lambda: benchmark.BenchmarkUnit(suite='s', task_id='t', unit_dir='/dir', target_address='//target')),
                    arg_2=Domain(strategy=lambda: 'rq1'),
                    arg_3=Domain(strategy=lambda: 'loop'),
                    arg_4=Domain(strategy=lambda: False),
                    arg_5=Domain(strategy=lambda: True),
                    arg_6=Domain(strategy=lambda: False),
                    arg_7=Domain(strategy=lambda: None),
                    arg_8=Domain(strategy=lambda: True),
                    arg_9=Domain(strategy=lambda: None),
                    arg_10=Domain(strategy=lambda: 'message'),
                    arg_11=Domain(strategy=lambda: False),
                )
        def returns(model=None, unit=None, rq="rq1", harness="loop", *args: Any, **kwargs: Any) -> benchmark.FlightRecord:
            m = model or benchmark.ModelSpec(
                identifier="m",
                tier=1,
                tier_label="T1",
                provider="test",
                rate_uncached_in=0.1,
                rate_cached_in=0.01,
                rate_out=0.2,
            )
            u = unit or benchmark.BenchmarkUnit(
                suite="s",
                task_id="t",
                unit_dir="/dir",
                target_address="//target",
            )
            return benchmark.FlightRecord(
                flight_id="f1",
                timestamp="2026-10-25T00:00:00Z",
                rq=rq,
                model={"identifier": m.identifier},
                benchmark_unit={"task_id": u.task_id},
                methodology="cleanroom",
                stages_executed=["stage1"],
                measurements=benchmark.FlightMeasurements(),
                verification_outcomes=benchmark.VerificationOutcomes(),
            )
        ctx.returns(returns)
        def provide(res: benchmark.FlightRecord, *args: Any, **kwargs: Any) -> None:
            self.state.flights_executed.append("flight")
        ctx.update(provide)


proto = BenchmarkStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_benchmark_evaluator_fake(
    state: Optional[BenchmarkState] = None,
) -> benchmark.BenchmarkEvaluator:
    """Instantiate a synthesized BenchmarkEvaluator fake."""
    st = state or BenchmarkState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(benchmark.BenchmarkEvaluator)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestBenchmarkEvaluatorUnit(unittest.TestCase):
    """Unit tests for synthesized BenchmarkEvaluator fake."""

    def setUp(self) -> None:
        self.state = BenchmarkState()
        self.fake = make_benchmark_evaluator_fake(self.state)

    def test_get_suite_catalog(self) -> None:
        catalog = self.fake.get_suite_catalog()
        self.assertIsInstance(catalog, Mapping)

    def test_execute_flight(self) -> None:
        m = benchmark.ModelSpec(
            identifier="m",
            tier=1,
            tier_label="T1",
            provider="test",
            rate_uncached_in=0.1,
            rate_cached_in=0.01,
            rate_out=0.2,
        )
        u = benchmark.BenchmarkUnit(
            suite="s",
            task_id="t",
            unit_dir="/dir",
            target_address="//target",
        )
        rec = self.fake.execute_flight(model=m, unit=u, rq="rq1", harness="loop")
        self.assertEqual(rec.rq, "rq1")
        self.assertIn("flight", self.state.flights_executed)


class TestBenchmarkImplReal(unittest.TestCase):
    """Direct unit tests for benchmark_impl.py."""

    def setUp(self) -> None:
        self.evaluator = BenchmarkEvaluatorImpl()

    def test_model_catalog(self) -> None:
        cat = self.evaluator.get_model_catalog()
        self.assertIn("deepseek-v41-flash", cat)
        ds = cat["deepseek-v41-flash"]
        cost = ds.compute_cost(uncached_in=1000000, cached_in=2000000, out=1000000)
        self.assertAlmostEqual(cost, 0.756, places=3)

    def test_suite_catalog(self) -> None:
        suites = self.evaluator.get_suite_catalog()
        self.assertIsInstance(suites, dict)
