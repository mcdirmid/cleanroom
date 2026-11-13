from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class TargetState:
    """Canonical model state tracking abstract collections and values."""
    initialized: bool = True
    items: list[Any] = field(default_factory=list)


class TargetStateMachine(StateMachine[TargetState]):
    """Unified Pretense State Machine for Target."""

    def __init__(
        self,
        state: Optional[TargetState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> TargetState:
        """Constructs initial model state. Open parameters may be specialized by pseudo-state machines."""
        return TargetState()

    # 1:1 Transition Pattern (1:1 with target method, natural Python branching):
    # - require(...) inspects self.state ONLY (never method arguments, local variables, or SUT objects).
    # - require_arg(param, domain) gates argument domains (first arg must be bare parameter name).
    # - No while loops, lambdas, or bare try/except blocks inside transitions.
    # - Complex algorithms (e.g. DAG engines, topological sorts) are modeled as abstract state mutations
    #   and invariant assertions, NOT re-implemented with loops inside transitions.
    # - Transition delegates to inner transition method: `ret = self.inner_process(item, count)`.
    # @transition(TargetClass.process)
    # def process(self, item: str, count: int) -> str:
    #     require(self.state.initialized)
    #     require_arg(item, Domain.sampled_from(["sample_1", "sample_2"]), preferred=["sample_1"])
    #     require_arg(count, Domain.range(1, 100), preferred=[1, 10])
    #     ret = self.inner_process(item, count)
    #     # State mutation & postcondition assertions:
    #     self.state.items.append(ret)
    #     assert ret == f"result_{item}_{count}"
    #     return ret
    #
    # def inner_process(self, item: str, count: int) -> str:
    #     """Computes fake return value for synthesized fake."""
    #     return f"result_{item}_{count}"

    # Seeding Transition (Fake-only, sets up initial state outside default __init__):
    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.initialized = True


proto = TargetStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

# FakeTarget = synthesize_fake(TargetStateMachine)

# Single service fake factory:
# def make_target_fake(state: Optional[TargetState] = None) -> TargetClass:
#     """Synthesizes fake instance for TargetClass."""
#     return FakeTarget(state=state or proto.make_initial_state())

# Multi-service fakes factory (when target has multiple singletons sharing state):
# def make_target_fakes(state: Optional[TargetState] = None) -> Tuple[ServiceA, ServiceB]:
#     """Synthesizes fake instances for component services sharing model state."""
#     fake = FakeTarget(state=state or proto.make_initial_state())
#     return (fake, fake)

# Fake Fuzzing (Exercises synthesized fake against state machine contracts):
# FakeTargetFuzzTest = compile_hypothesis_test_case(
#     proto=proto,
#     initial_state_factory=proto.make_initial_state,
#     name="FakeTargetFuzzTest",
# )


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

# class TestTargetFake(unittest.TestCase):
#     """Optional fixed fake tests for transitions or branches not covered by FakeTargetFuzzTest."""
#
#     def setUp(self) -> None:
#         # Single service:
#         self.fake = make_target_fake()
#         self.sm = TargetStateMachine(singletons={TargetClass: self.fake})
#         # Multi-service:
#         # self.fakes = make_target_fakes()
#         # self.sm = TargetStateMachine()
#
#     def test_uncovered_branch(self) -> None:
#         """Exercises edge branches or seeding transitions not reached by FakeTargetFuzzTest."""
#         self.sm.seed_initial()
#         # Exercise only what FakeTargetFuzzTest does not cover:
#         # self.fake.process("sample_1", 10)
#         # _ = self.fake.items


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

# class TargetImplPseudoStateMachine(TargetStateMachine):
#     """Implementation pseudo-state machine for Target measuring differentials and SUT state."""
#     # Zero state dataclasses; zero require_arg statements (domain constraints are inherited from TargetStateMachine).
#     # NEVER declare @transition or override outer transitions (PN_IMPL_NO_OUTER_TRANSITION).
#     # Open model parameters (e.g. initial capacity or defaults) may be specialized via property or make_initial_state:
#     # def make_initial_state(self) -> TargetState:
#     #     return TargetState(capacity=100)
#
#     # Override inner transitions ONLY to drive target and evaluate private invariant assertions:
#     # def inner_process(self, item: str, count: int) -> str:
#     #     target: TargetClass = sut(TargetClass)
#     #     # Pre-state observation:
#     #     old_size = target.size
#     #     ret = target.process(item, count)
#     #     # Post-state verification:
#     #     assert target.size == old_size + 1
#     #     return ret


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================

# class TestTargetImplReal(LifecycleTestCase):
#     """Verifies that concrete library implementation satisfies contracts."""
#
#     # Target class and singletons under test are registered automatically by LifecycleTestCase.
#     # self.sut provides the primary service under test.
#     def setUp(self) -> None:
#         super().setUp()
#         # For single service:
#         # self.real = self.sut
#         # self.sm = TargetStateMachine(singletons={TargetClass: self.real})
#         # self.checked = self.sm.as_checked(TargetClass, self.real)
#         # For multi-service:
#         # self.service_a = get_singleton(ServiceA)
#         # self.service_b = get_singleton(ServiceB)
#         # self.sm = TargetStateMachine(singletons={ServiceA: self.service_a, ServiceB: self.service_b})
#         # self.checked_a = self.sm.as_checked(ServiceA, self.service_a)
#         # self.checked_b = self.sm.as_checked(ServiceB, self.service_b)
#
#     def test_real_conformance(self) -> None:
#         # Drive operational scenarios via self.checked.<method>(*args)
#         # to stabilize 100% statement coverage under --cov alongside fuzzing.
#         # Operational postconditions and invariants are verified automatically by transition asserts;
#         # fixed scenario tests should contain no redundant manual assertions (self.assertEqual, self.assertTrue).
#         #
#         # Contract violation testing (covering contracted *Error branches in lib):
#         # self.checked.violating(ExpectedError).method_that_violates(...)
#         #
#         # Collaborator isolation: if earlier calls exhaust a collaborator (e.g. advance a scheduler to finished),
#         # subsequent loops on that instance (e.g. runner.run()) exit immediately. Use separate test methods
#         # (def test_<scenario>(self)) with fresh setUp() scopes or isolated SUT instances for independent flows.
#         pass


# ==============================================================================
# 6. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

# Pattern A: Single Singleton SUT Factory
# def make_sut() -> TargetClass:
#     registry = LifecycleRegistry()
#     registry.register_singleton(TargetClass)
#     scope = enter_phase(system, registry=registry)
#     scope.__enter__()
#     return get_singleton(TargetClass)

# Pattern B: Multi-Singleton Aggregate SUT (delegates method lookups across services)
# class TargetSUT:
#     tier = system
#     def __init__(self) -> None:
#         self.__dict__["_services"] = ()
#         self.registry = LifecycleRegistry()
#         self.registry.register_singleton(ServiceA)
#         self.registry.register_singleton(ServiceB)
#         self.phase_scope = enter_phase(system, registry=self.registry)
#         self.phase_scope.__enter__()
#         self.service_a = get_singleton(ServiceA)
#         self.service_b = get_singleton(ServiceB)
#         self.__dict__["_services"] = (self.service_a, self.service_b)
#
#     def __getattr__(self, name: str) -> Any:
#         if name.startswith("__") and name.endswith("__"):
#             raise AttributeError(name)
#         for service in self.__dict__.get("_services", ()):
#             if hasattr(service, name):
#                 return getattr(service, name)
#         raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")
#
# def make_sut() -> TargetSUT:
#     return TargetSUT()

# TargetFuzzTest = compile_hypothesis_test_case(
#     proto=proto,
#     sut_factory=make_sut,
#     initial_state_factory=proto.make_initial_state,
#     name="TargetFuzzTest",
# )
