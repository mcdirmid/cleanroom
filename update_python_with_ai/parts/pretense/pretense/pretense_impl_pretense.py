"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for Pretense."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    PretenseRunnerConfig,
    StateMachine,
    TransitionContext,
    compile_hypothesis_test_case,
    transition,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from update_python_with_ai.parts.pretense.lib.pretense_impl import PretenseEngine, ActiveStepTracker, WatchdogMonitor, __initialize__


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class PretenseState:
    """Canonical model state for Pretense operations."""
    initialized: bool = True


class PretenseStateMachine(StateMachine[PretenseState]):
    """Unified Pretense State Machine for Pretense engine and utilities."""

    def __init__(
        self,
        state: Optional[PretenseState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or PretenseState(), singletons=singletons)

    @transition(PretenseEngine.compile_state_machine)
    def compile_state_machine(self, ctx: TransitionContext[PretenseEngine, [Any], Any]) -> None:
        ctx.arguments(machine_cls=Domain(strategy=lambda: None))
        ctx.returns(lambda machine_cls=None: None)
        ctx.update(lambda res, machine_cls=None: None)

    @transition(PretenseEngine.run_suite)
    def run_suite(self, ctx: TransitionContext[PretenseEngine, [Any], Any]) -> None:
        ctx.arguments(config=Domain(strategy=lambda: {}))
        ctx.returns(lambda config={}: None)
        ctx.update(lambda res, config={}: None)

    @transition(PretenseEngine.synthesize_test)
    def synthesize_test(self, ctx: TransitionContext[PretenseEngine, [Any, Any], Any]) -> None:
        ctx.arguments(
            target_cls=Domain(strategy=lambda: "sample_target_cls"),
            trace=Domain(strategy=lambda: None),
        )
        ctx.returns(lambda target_cls="sample_target_cls", trace=None: None)
        ctx.update(lambda res, target_cls="sample_target_cls", trace=None: None)

    @transition(ActiveStepTracker.get_active_step)
    def get_active_step(self, ctx: TransitionContext[ActiveStepTracker, [], Any]) -> None:
        ctx.arguments()
        ctx.returns(lambda: None)
        ctx.update(lambda res: None)

    @transition(ActiveStepTracker.format_active_step_diagnostic)
    def format_active_step_diagnostic(self, ctx: TransitionContext[ActiveStepTracker, [Any, Any], Any]) -> None:
        ctx.arguments(
            prefix=Domain(strategy=lambda: None),
            target_name=Domain(strategy=lambda: "sample_target_name"),
        )
        ctx.returns(lambda prefix=None, target_name="sample_target_name": None)
        ctx.update(lambda res, prefix=None, target_name="sample_target_name": None)

    @transition(WatchdogMonitor.arm)
    def arm(self, ctx: TransitionContext[WatchdogMonitor, [Any, Any], Any]) -> None:
        ctx.arguments(
            timeout_seconds=Domain(strategy=lambda: None),
            target_name=Domain(strategy=lambda: "sample_target_name"),
        )
        ctx.returns(lambda timeout_seconds=None, target_name="sample_target_name": None)
        ctx.update(lambda res, timeout_seconds=None, target_name="sample_target_name": None)

    @transition(WatchdogMonitor.disarm)
    def disarm(self, ctx: TransitionContext[WatchdogMonitor, [Any], Any]) -> None:
        ctx.arguments(handle=Domain(strategy=lambda: None))
        ctx.returns(lambda handle=None: None)
        ctx.update(lambda res, handle=None: None)


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

def make_pretense_fakes(
    state: PretenseState,
) -> Tuple[PretenseEngine, ActiveStepTracker, WatchdogMonitor]:
    """Synthesizes fake instances for component services sharing model state."""
    sm = PretenseStateMachine(state=state)
    return (
        sm.as_fake(PretenseEngine),
        sm.as_fake(ActiveStepTracker),
        sm.as_fake(WatchdogMonitor),
    )


# ==============================================================================
# 3. Fake Unit Tests
# ==============================================================================

class TestPretenseUnit(unittest.TestCase):
    """Verifies that synthesized fakes conform to state machine specification."""

    def setUp(self) -> None:
        self.state = PretenseState()
        self.pretenseengine, self.activesteptracker, self.watchdogmonitor = make_pretense_fakes(self.state)

    def test_fake_initial_state(self) -> None:
        self.assertTrue(self.state.initialized)

    def test_fake_compile_state_machine(self) -> None:
        res = self.pretenseengine.compile_state_machine(PretenseStateMachine)
        self.assertIsNone(res)

    def test_fake_run_suite(self) -> None:
        cfg = PretenseRunnerConfig(target_paths=["."])
        res = self.pretenseengine.run_suite(cfg)
        self.assertIsNone(res)

    def test_fake_synthesize_test(self) -> None:
        res = self.pretenseengine.synthesize_test(PretenseEngine, [])
        self.assertIsNone(res)

    def test_fake_get_active_step(self) -> None:
        res = self.activesteptracker.get_active_step()
        self.assertIsNone(res)

    def test_fake_format_active_step_diagnostic(self) -> None:
        res = self.activesteptracker.format_active_step_diagnostic("prefix", "sample_target_name")
        self.assertIsNone(res)

    def test_fake_arm(self) -> None:
        res = self.watchdogmonitor.arm(1.0, "sample_target_name")
        self.assertIsNone(res)

    def test_fake_disarm(self) -> None:
        res = self.watchdogmonitor.disarm(None)
        self.assertIsNone(res)


# ==============================================================================
# 4. Real Implementation Tests
# ==============================================================================

class TestPretenseImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.pretenseengine = get_singleton(PretenseEngine)
        self.activesteptracker = ActiveStepTracker()
        self.watchdogmonitor = WatchdogMonitor()

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_real_conformance(self) -> None:
        self.assertIsNotNone(self.pretenseengine)
        self.assertIsNotNone(self.activesteptracker)
        self.assertIsNotNone(self.watchdogmonitor)


# ==============================================================================
# 5. Hypothesis Stateful Fuzzing
# ==============================================================================

class PretenseSUT:
    """Aggregate SUT exposing component services for Hypothesis fuzzing."""

    tier = system

    def __init__(self) -> None:
        self.__dict__["_services"] = ()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.pretenseengine = get_singleton(PretenseEngine)
        self.activesteptracker = ActiveStepTracker()
        self.watchdogmonitor = WatchdogMonitor()
        self.__dict__["_services"] = (self.pretenseengine, self.activesteptracker, self.watchdogmonitor,)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for service in self.__dict__.get("_services", ()):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")


def make_sut() -> PretenseSUT:
    return PretenseSUT()


PretenseFuzzTest = compile_hypothesis_test_case(
    proto=PretenseStateMachine,
    sut_factory=make_sut,
    initial_state_factory=PretenseState,
    name="PretenseFuzzTest",
)
