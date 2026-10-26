"""Pretense specifications and tests for benchmark_impl."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value

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


proto = StateMachineProto[BenchmarkState]()


# ==============================================================================
# 2. BenchmarkEvaluator Transitions
# ==============================================================================

@proto.transition(benchmark.BenchmarkEvaluator.get_suite_catalog)
def get_suite_catalog(): pass

@get_suite_catalog.arguments
def _(state: BenchmarkState, this: Any) -> Optional[Tuple[()]]:
    return ()

@get_suite_catalog.returns
def _(state: BenchmarkState, this: Any, outcome: object = None) -> Optional[Outcome[Mapping[str, Sequence[benchmark.BenchmarkUnit]]]]:
    return Value({})


@proto.transition(benchmark.BenchmarkEvaluator.execute_flight)
def execute_flight(): pass

@execute_flight.arguments
def _(
    state: BenchmarkState,
    this: Any,
    model: benchmark.ModelSpec | NotBoundType = NotBound,
    unit: benchmark.BenchmarkUnit | NotBoundType = NotBound,
    rq: str | NotBoundType = NotBound,
    harness: str | NotBoundType = NotBound,
    dry_run: bool | NotBoundType = NotBound,
    simulate: bool | NotBoundType = NotBound,
    mutation_testing: bool | NotBoundType = NotBound,
    results_dir: Optional[str] | NotBoundType = NotBound,
    wait_for_convergence: bool | NotBoundType = NotBound,
    timeout: Optional[float] | NotBoundType = NotBound,
    antigravity_dispatch: str | NotBoundType = NotBound,
    baseline: bool | NotBoundType = NotBound,
) -> Optional[Tuple[Any, ...]]:
    m = (
        benchmark.ModelSpec(
            identifier="m",
            tier=1,
            tier_label="T1",
            provider="test",
            rate_uncached_in=0.1,
            rate_cached_in=0.01,
            rate_out=0.2,
        )
        if isinstance(model, NotBoundType)
        else model
    )
    u = (
        benchmark.BenchmarkUnit(
            suite="s",
            task_id="t",
            unit_dir="/dir",
            target_address="//target",
        )
        if isinstance(unit, NotBoundType)
        else unit
    )
    r = "rq1" if isinstance(rq, NotBoundType) else rq
    h = "loop" if isinstance(harness, NotBoundType) else harness
    return (m, u, r, h, False, True, False, None, True, None, "message", False)

@execute_flight.returns
def _(
    state: BenchmarkState,
    this: Any,
    model: benchmark.ModelSpec | NotBoundType = NotBound,
    unit: benchmark.BenchmarkUnit | NotBoundType = NotBound,
    rq: str | NotBoundType = NotBound,
    harness: str | NotBoundType = NotBound,
    dry_run: bool | NotBoundType = NotBound,
    simulate: bool | NotBoundType = NotBound,
    mutation_testing: bool | NotBoundType = NotBound,
    results_dir: Optional[str] | NotBoundType = NotBound,
    wait_for_convergence: bool | NotBoundType = NotBound,
    timeout: Optional[float] | NotBoundType = NotBound,
    antigravity_dispatch: str | NotBoundType = NotBound,
    baseline: bool | NotBoundType = NotBound,
    outcome: object = None,
) -> Optional[Outcome[benchmark.FlightRecord]]:
    m = (
        benchmark.ModelSpec(
            identifier="m",
            tier=1,
            tier_label="T1",
            provider="test",
            rate_uncached_in=0.1,
            rate_cached_in=0.01,
            rate_out=0.2,
        )
        if isinstance(model, NotBoundType)
        else model
    )
    u = (
        benchmark.BenchmarkUnit(
            suite="s",
            task_id="t",
            unit_dir="/dir",
            target_address="//target",
        )
        if isinstance(unit, NotBoundType)
        else unit
    )
    rec = benchmark.FlightRecord(
        flight_id="f1",
        timestamp="2026-10-25T00:00:00Z",
        rq="rq1" if isinstance(rq, NotBoundType) else rq,
        model={"identifier": m.identifier},
        benchmark_unit={"task_id": u.task_id},
        methodology="cleanroom",
        stages_executed=["stage1"],
        measurements=benchmark.FlightMeasurements(),
        verification_outcomes=benchmark.VerificationOutcomes(),
    )
    return Value(rec)

@execute_flight.provide
def _(
    state: BenchmarkState,
    this: Any,
    model: benchmark.ModelSpec | NotBoundType = NotBound,
    unit: benchmark.BenchmarkUnit | NotBoundType = NotBound,
    rq: str | NotBoundType = NotBound,
    harness: str | NotBoundType = NotBound,
    dry_run: bool | NotBoundType = NotBound,
    simulate: bool | NotBoundType = NotBound,
    mutation_testing: bool | NotBoundType = NotBound,
    results_dir: Optional[str] | NotBoundType = NotBound,
    wait_for_convergence: bool | NotBoundType = NotBound,
    timeout: Optional[float] | NotBoundType = NotBound,
    antigravity_dispatch: str | NotBoundType = NotBound,
    baseline: bool | NotBoundType = NotBound,
    result: Optional[benchmark.FlightRecord] = None,
) -> None:
    state.flights_executed.append("flight")


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
