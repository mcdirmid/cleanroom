from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import unittest

from pretense import (
    StateMachine,
    domain,
    require,
    require_arg,
    require_env,
    sut,
    synthesize_fake,
    test_only,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, LifecycleTestCase, enter_phase, get_singleton, system

# ==============================================================================
# PART A: INTERFACE & FAKE MODULE (pretense/<name>_pretense.py)
# ==============================================================================

# 1. Stateless Interface State Machine (<Iface>StateMachine)
# - Inherits StateMachine[Any]; NEVER accesses or mutates self.state (PRE_LINT_INTF_NO_STATE).
# - @transition(Iface.method) 1:1 with contracted methods; @transition(name="<prop>") WITHOUT @property for properties.
# - inner_<method> stubs use `...` (ellipsis) ONLY — never `raise NotImplementedError` (PRE_LINT_NO_RAISE).
# - require_arg uses runtime types (int, str, float, bool, object, Enum) or @domain(valid=..., invalid=...) methods.

# class TargetStateMachine(StateMachine[Any]):
#     """Stateless behavioral contract for Target."""
#
#     @domain(
#         valid=lambda self: [1, 2, 10],
#         invalid=lambda self: [0, -1],
#     )
#     def positive_count(self, count: int) -> bool:
#         return isinstance(count, int) and count > 0
#
#     @transition(name="size")
#     def size(self) -> int:
#         ret = self.inner_size()
#         assert ret >= 0
#         return ret
#
#     @transition(TargetClass.process)
#     def process(self, item: str, count: int) -> str:
#         require(self.inner_is_initialized())
#         require_arg(item, str)
#         require_arg(count, self.positive_count, error=ValueError)
#         old_size = self.inner_size()
#         ret = self.inner_process(item, count)
#         assert self.inner_size() == old_size + 1
#         assert ret == f"result_{item}_{count}"
#         return ret
#
#     def inner_is_initialized(self) -> bool: ...
#     def inner_size(self) -> int: ...
#     def inner_process(self, item: str, count: int) -> str: ...


# 2. Stateful Fake State Machine & Fuzzing (<Iface>FakeStateMachine)
# @dataclass
# class TargetState:
#     """Model state owned exclusively by TargetFakeStateMachine."""
#     initialized: bool = True
#     items: list[str] = field(default_factory=list)
#
#
# class TargetFakeStateMachine(TargetStateMachine):
#     """Stateful in-memory fake for Target."""
#
#     def __init__(
#         self,
#         state: Optional[TargetState] = None,
#         singletons: Optional[dict[type[Any], Any]] = None,
#     ) -> None:
#         super().__init__(state=state or self.make_initial_state(), singletons=singletons)
#
#     def make_initial_state(self) -> TargetState:
#         return TargetState()
#
#     @transition.seeding()
#     def seed_initial(self) -> None:
#         self.state.initialized = True
#
#     def inner_is_initialized(self) -> bool:
#         return self.state.initialized
#
#     def inner_size(self) -> int:
#         return len(self.state.items)
#
#     def inner_process(self, item: str, count: int) -> str:
#         res = f"result_{item}_{count}"
#         self.state.items.append(res)
#         return res
#
#
# FakeTarget = synthesize_fake(TargetFakeStateMachine)
#
# def make_target_fake(state: Optional[TargetState] = None) -> TargetClass:
#     return FakeTarget(state=state or TargetFakeStateMachine().make_initial_state())
#
# FakeTargetFuzzTest = compile_hypothesis_test_case(
#     TargetFakeStateMachine,
#     name="FakeTargetFuzzTest",
# )
#
# class TestTargetFake(unittest.TestCase):
#     """Optional fixed fake tests only for valid-transition branches not covered by FakeTargetFuzzTest."""
#
#     def setUp(self) -> None:
#         self.fake = make_target_fake()
#
#     def test_uncovered_branch(self) -> None:
#         self.assertEqual(self.fake.process("ok", 1), "result_ok_1")


# ==============================================================================
# PART B: IMPLEMENTATION MODULE (pretense/<name>_pretense.py)
# ==============================================================================

# 1. Stateless Implementation State Machine (<Impl>StateMachine(<Iface>StateMachine))
# - Zero state dataclasses, zero require/require_arg, zero @transition, zero super() calls.
# - Override inner_<method> ONLY to invoke target = sut(TargetClass).
#
# class TargetImplStateMachine(TargetStateMachine):
#     """Implementation binding for TargetImpl."""
#
#     def inner_is_initialized(self) -> bool:
#         return True
#
#     def inner_size(self) -> int:
#         return sut(TargetClass).size
#
#     def inner_process(self, item: str, count: int) -> str:
#         return sut(TargetClass).process(item, count)


# 2. Real Implementation Tests & Fuzzing
# - NEVER bind or access `self.real` (PN_NO_DIRECT_REAL_ACCESS). Use `self.checked = self.sm.as_checked(TargetClass, self.sut)`.
# - Use `self.checked.violating(ExpectedError).<method>(...)` for *Error contract violations.
# - Use `with self.assertRaises(ExpectedException):` for *Exception operational exceptions.
#
# class TestTargetImplReal(LifecycleTestCase):
#     target = TargetImpl
#
#     def setUp(self) -> None:
#         super().setUp()
#         self.sm = TargetImplStateMachine(singletons={TargetClass: self.sut})
#         self.checked = self.sm.as_checked(TargetClass, self.sut)
#
#     def test_real_conformance(self) -> None:
#         self.checked.process("a", 1)
#         _ = self.checked.size
#         self.checked.violating(ValueError).process("a", 0)
#
# def make_sut() -> TargetClass:
#     registry = LifecycleRegistry()
#     registry.register_singleton(TargetImpl)
#     scope = enter_phase(system, registry=registry)
#     scope.__enter__()
#     return get_singleton(TargetClass)
#
# TargetImplFuzzTest = compile_hypothesis_test_case(
#     TargetImplStateMachine,
#     sut_factory=make_sut,
#     name="TargetImplFuzzTest",
# )
