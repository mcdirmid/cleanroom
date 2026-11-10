# === File: lru_cache_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for LRUCache."""

from __future__ import annotations

from typing import Any, Optional, Tuple
import unittest

from pretense import (
    call_target,
    raises,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)
from benchmark_2.parts.lru_cache.lib.lru_cache_impl import LRUCache, __initialize__
from benchmark_2.parts.lru_cache.pretense.lru_cache_pretense import LruCacheStateMachine


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# Implementation pseudo-state machines inherit every outer transition (including
# require/require_arg guards and model state mutations) from the interface state
# machine and override only inner transition pivots to invoke the concrete SUT.

class LruCacheImplPseudoStateMachine(LruCacheStateMachine):
    """Implementation pseudo-state machine for LruCache."""

    def inner_configure(self, capacity: int) -> None:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.configure(capacity))
        assert target.capacity == capacity
        assert target.size == min(len(self.state.items), capacity)
        return ret

    def inner_get(self, key: str, default: Optional[Any]) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.get(key, default))
        assert target.size == len(self.state.items)
        return ret

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        target: LRUCache = sut(LRUCache)
        existing = key in self.state.items
        at_capacity = len(self.state.items) >= self.state.capacity
        ret = call_target(target.put(key, value))
        if existing or at_capacity:
            assert target.size == len(self.state.items)
        else:
            assert target.size == len(self.state.items) + 1
        return ret

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.peek(key, default))
        assert target.size == len(self.state.items)
        return ret

    def inner_remove(self, key: str) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.remove(key))
        assert target.size == len(self.state.items) - 1
        return ret

    def inner_clear(self) -> None:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.clear())
        assert target.size == 0
        return ret

    def inner_get_stats(self) -> CacheStats:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.get_stats())
        assert ret == CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        )
        return ret

    def inner_reset_stats(self) -> None:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.reset_stats())
        assert target.get_stats() == CacheStats()
        return ret

    def inner_keys_in_lru_order(self) -> list[str]:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.keys_in_lru_order())
        assert ret == list(self.state.items.keys())
        return ret

    def inner_capacity(self) -> int:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "capacity"))
        return ret

    def inner_size(self) -> int:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "size"))
        return ret

    def inner_is_empty(self) -> bool:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "is_empty"))
        return ret

    def inner_is_full(self) -> bool:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "is_full"))
        return ret


proto = LruCacheImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestLruCacheImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(LRUCache)
        self.sm = LruCacheImplPseudoStateMachine(singletons={LRUCache: self.real})
        # The checked adapter exposes contract-violating dispatch in addition to
        # the target protocol surface, so it is deliberately kept dynamically typed.
        self.checked: Any = self.sm.as_checked(LRUCache, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_initial_state(self) -> None:
        assert self.checked.capacity == 100
        assert self.checked.size == 0
        assert self.checked.is_empty is True
        assert self.checked.is_full is False
        assert self.checked.keys_in_lru_order() == []
        assert self.checked.get_stats() == CacheStats()

    def test_configure_updates_capacity(self) -> None:
        self.checked.configure(2)
        assert self.checked.capacity == 2
        assert self.checked.size == 0

    def test_put_get_peek_remove(self) -> None:
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.size == 2
        assert self.checked.get("a", 0) == 1
        assert self.checked.peek("b", 0) == 2
        assert self.checked.get("z", 9) == 9
        assert self.checked.peek("z", 9) == 9
        assert self.checked.keys_in_lru_order() == ["b", "a"]
        assert self.checked.remove("a") == 1
        assert self.checked.size == 1
        assert self.checked.keys_in_lru_order() == ["b"]

    def test_put_update_and_eviction(self) -> None:
        self.checked.configure(2)
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.is_full is True
        assert self.checked.put("a", 3) is None
        assert self.checked.keys_in_lru_order() == ["b", "a"]
        assert self.checked.put("c", 4) == ("b", 2)
        assert self.checked.keys_in_lru_order() == ["a", "c"]
        assert self.checked.size == 2
        assert self.checked.get_stats().evictions == 1

    def test_configure_downsize_evicts_lru_entries(self) -> None:
        self.checked.configure(2)
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.put("c", 3) == ("a", 1)
        self.checked.configure(1)
        assert self.checked.capacity == 1
        assert self.checked.size == 1
        assert self.checked.keys_in_lru_order() == ["c"]
        assert self.checked.get_stats().evictions == 2

    def test_clear_preserves_telemetry(self) -> None:
        assert self.checked.put("a", 1) is None
        assert self.checked.get("a", 0) == 1
        assert self.checked.get("z", 0) == 0
        self.checked.clear()
        assert self.checked.size == 0
        assert self.checked.is_empty is True
        assert self.checked.get_stats() == CacheStats(hits=1, misses=1, evictions=0)
        self.checked.reset_stats()
        assert self.checked.get_stats() == CacheStats()

    def test_peek_does_not_alter_order_or_telemetry(self) -> None:
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.peek("a", 0) == 1
        assert self.checked.keys_in_lru_order() == ["a", "b"]
        assert self.checked.get_stats() == CacheStats()

    def test_configure_invalid_capacity_raises(self) -> None:
        """A non-positive capacity must raise CacheCapacityError without mutating capacity."""
        with self.assertRaises(CacheCapacityError):
            self.real.configure(0)
        assert self.real.capacity == 100
        assert self.real.size == 0

    def test_remove_missing_key_raises(self) -> None:
        """Removing an absent key must raise CacheKeyNotFoundError without mutating the cache."""
        with self.assertRaises(CacheKeyNotFoundError):
            self.real.remove("missing")
        assert self.real.size == 0
        assert self.real.is_empty is True


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real SUT
# ==============================================================================

def make_sut() -> LRUCache:
    registry = LifecycleRegistry()
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(LRUCache)


LruCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="LruCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T21:35:51Z
# LAST_CHANGED: 2026-11-09T21:35:09Z
# CHANGE: Fix contracted error verification: assert CacheCapacityError and CacheKeyNotFoundError directly against the concrete SUT (the checked-adapter violating dispatch suppressed the expected errors), and verify the cache is unmodified after each failed operation
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T21:35:51Z
# PRETENSE_QA_AUDIT: 2026-11-09T21:35:29Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for LruCache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
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
from benchmark_2.parts.lru_cache.lib.lru_cache import CacheStats, LRUCache


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions live naturally inside the single
# transition body (multi-transition splitting is prohibited). require_arg defines
# the caller precondition contract (checked at runtime on real calls).


def _same(actual: Any, expected: Any) -> bool:
    """Value parity tolerant of non-reflexive values such as NaN payloads."""
    return actual is expected or actual == expected


@dataclass
class LruCacheState:
    """Canonical model state for LruCache operations."""

    capacity: int
    items: Dict[str, Any] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    seeded: bool = True


class LruCacheStateMachine(StateMachine[LruCacheState]):
    """Unified Pretense State Machine for LruCache."""

    def __init__(
        self,
        state: Optional[LruCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> LruCacheState:
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return LruCacheState(capacity=100)

    # ------------------------------------------------------------------
    # Inner transition pivots (overridden by implementation pseudo state
    # machines to execute the concrete target; they compute fake returns here).
    # ------------------------------------------------------------------

    def inner_configure(self, capacity: int) -> None:
        return None

    def inner_get(self, key: str, default: Optional[Any]) -> Any:
        if key in self.state.items:
            fake_ret: Any = self.state.items[key]
        else:
            fake_ret = default
        return fake_ret

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        if key in self.state.items:
            fake_ret: Optional[Tuple[str, Any]] = None
        elif len(self.state.items) >= self.state.capacity:
            evicted_key = next(iter(self.state.items))
            fake_ret = (evicted_key, self.state.items[evicted_key])
        else:
            fake_ret = None
        return fake_ret

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        if key in self.state.items:
            fake_ret: Any = self.state.items[key]
        else:
            fake_ret = default
        return fake_ret

    def inner_remove(self, key: str) -> Any:
        return self.state.items[key]

    def inner_clear(self) -> None:
        return None

    def inner_get_stats(self) -> CacheStats:
        return CacheStats(
                hits=self.state.hits,
                misses=self.state.misses,
                evictions=self.state.evictions,
            )

    def inner_reset_stats(self) -> None:
        return None

    def inner_keys_in_lru_order(self) -> List[str]:
        return list(self.state.items.keys())

    def inner_capacity(self) -> int:
        return self.state.capacity

    def inner_size(self) -> int:
        return len(self.state.items)

    def inner_is_empty(self) -> bool:
        return len(self.state.items) == 0

    def inner_is_full(self) -> bool:
        return len(self.state.items) >= self.state.capacity

    # ------------------------------------------------------------------
    # 1:1 outer transitions
    # ------------------------------------------------------------------

    @transition(LRUCache.configure)
    def configure(
        self,
        capacity: int,
    ) -> None:
        require_arg(capacity, Domain.range(1, 100), preferred=[1, 2, 5])
        ret: None = self.inner_configure(capacity)
        assert ret is None
        overflow = len(self.state.items) - capacity
        if overflow > 0:
            evicted_keys = list(self.state.items.keys())[:overflow]
            for evicted_key in evicted_keys:
                del self.state.items[evicted_key]
            self.state.evictions += overflow
        self.state.capacity = capacity
        assert self.state.capacity == capacity
        assert len(self.state.items) <= capacity
        return ret

    @transition(LRUCache.get)
    def get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require_arg(key, Domain.type(str), preferred=["alpha", "beta", "gamma"])
        require_arg(default, Domain.any())
        if key in self.state.items:
            expected: Any = self.state.items[key]
        else:
            expected = default
        ret: Any = self.inner_get(key, default)
        assert _same(ret, expected)
        if key in self.state.items:
            value = self.state.items.pop(key)
            self.state.items[key] = value
            self.state.hits += 1
        else:
            self.state.misses += 1
        assert len(self.state.items) <= self.state.capacity
        return ret

    @transition(LRUCache.put)
    def put(
        self,
        key: str,
        value: Any,
    ) -> Optional[Tuple[str, Any]]:
        require_arg(key, Domain.type(str), preferred=["alpha", "beta", "gamma"])
        require_arg(value, Domain.any())
        if key in self.state.items:
            expected: Optional[Tuple[str, Any]] = None
        elif len(self.state.items) >= self.state.capacity:
            lru_key = next(iter(self.state.items))
            expected = (lru_key, self.state.items[lru_key])
        else:
            expected = None
        ret: Optional[Tuple[str, Any]] = self.inner_put(key, value)
        if expected is None:
            assert ret is None
        else:
            assert ret is not None
            assert ret[0] == expected[0]
            assert _same(ret[1], expected[1])
        if key in self.state.items:
            del self.state.items[key]
            self.state.items[key] = value
        elif len(self.state.items) >= self.state.capacity:
            evicted_key = next(iter(self.state.items))
            del self.state.items[evicted_key]
            self.state.evictions += 1
            self.state.items[key] = value
        else:
            self.state.items[key] = value
        assert len(self.state.items) <= self.state.capacity
        return ret

    @transition(LRUCache.peek)
    def peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require_arg(key, Domain.type(str), preferred=["alpha", "beta", "gamma"])
        require_arg(default, Domain.any())
        if key in self.state.items:
            expected: Any = self.state.items[key]
        else:
            expected = default
        ret: Any = self.inner_peek(key, default)
        assert _same(ret, expected)
        return ret

    @transition(LRUCache.remove)
    def remove(
        self,
        key: str,
    ) -> Any:
        require(len(self.state.items) > 0)
        require_arg(key, Domain.in_set(set(self.state.items)))
        if key in self.state.items:
            expected: Any = self.state.items[key]
        else:
            expected = None
        ret: Any = self.inner_remove(key)
        if key in self.state.items:
            assert _same(ret, expected)
            del self.state.items[key]
            assert key not in self.state.items
        return ret

    @transition(LRUCache.clear)
    def clear(
        self,
    ) -> None:
        ret: None = self.inner_clear()
        assert ret is None
        self.state.items.clear()
        assert len(self.state.items) == 0
        return ret

    @transition(LRUCache.get_stats)
    def get_stats(
        self,
    ) -> CacheStats:
        expected = CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        )
        ret: CacheStats = self.inner_get_stats()
        assert ret == expected
        return ret

    @transition(LRUCache.reset_stats)
    def reset_stats(
        self,
    ) -> None:
        ret: None = self.inner_reset_stats()
        assert ret is None
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        return ret

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(
        self,
    ) -> List[str]:
        expected: List[str] = list(self.state.items.keys())
        ret: List[str] = self.inner_keys_in_lru_order()
        assert ret == expected
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        ret: int = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    @transition(name="size")
    def size(self) -> int:
        ret: int = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret: bool = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret: bool = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the model state as an active, blank cache configuration.

        Seeding only normalizes abstract model bookkeeping; it deliberately does
        not reset configured capacity, entries, or telemetry so that an already
        configured real target stays in parity with the model.
        """
        self.state.seeded = True
        assert self.state.capacity >= 1


proto = LruCacheStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeLruCache = synthesize_fake(LruCacheStateMachine)


def make_lru_cache_fake(state: Optional[LruCacheState] = None) -> LRUCache:
    """Synthesizes a fake LRUCache sharing the supplied model state."""
    return FakeLruCache(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestLruCacheFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_lru_cache_fake()
        self.sm = LruCacheStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises every declared transition and seeding transition on the model."""
        self.sm.seed_initial()
        assert self.sm.capacity() == 100
        assert self.sm.size() == 0
        assert self.sm.is_empty() is True
        assert self.sm.is_full() is False
        self.sm.configure(2)
        assert self.sm.capacity() == 2
        assert self.sm.put("alpha", 1) is None
        assert self.sm.put("beta", 2) is None
        assert self.sm.is_full() is True
        assert self.sm.get("alpha", 0) == 1
        assert self.sm.peek("beta", 0) == 2
        assert self.sm.remove("beta") == 2
        self.sm.clear()
        assert self.sm.keys_in_lru_order() == []
        self.sm.get_stats()
        self.sm.reset_stats()

    def test_fake_insert_and_lookup(self) -> None:
        """Drives the synthesized fake through insert, lookup, removal, and reset."""
        self.fake.configure(3)
        assert self.fake.capacity == 3
        assert self.fake.size == 0
        assert self.fake.is_empty is True
        assert self.fake.is_full is False
        assert self.fake.put("alpha", 1) is None
        assert self.fake.put("beta", 2) is None
        assert self.fake.get("alpha", 0) == 1
        assert self.fake.peek("beta", 0) == 2
        assert self.fake.keys_in_lru_order() == ["beta", "alpha"]
        assert self.fake.remove("beta") == 2
        assert self.fake.keys_in_lru_order() == ["alpha"]
        assert self.fake.get("beta", 9) == 9
        stats = self.fake.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        self.fake.reset_stats()
        assert self.fake.get_stats() == CacheStats()
        self.fake.clear()
        assert self.fake.is_empty is True
        assert self.fake.size == 0

    def test_fake_eviction(self) -> None:
        """Verifies that the synthesized fake evicts the least-recently-used entry."""
        self.fake.configure(2)
        assert self.fake.put("alpha", 1) is None
        assert self.fake.put("beta", 2) is None
        assert self.fake.is_full is True
        assert self.fake.put("gamma", 3) == ("alpha", 1)
        assert self.fake.keys_in_lru_order() == ["beta", "gamma"]
        assert self.fake.size == 2
        assert self.fake.get_stats().evictions == 1


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeLruCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeLruCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T21:28:42Z
# LAST_CHANGED: 2026-11-09T21:28:42Z
# CHANGE: Implement LRUCache interface state machine: ordered model state, 1:1 transitions with concrete domains/inner pivots/parity assertions, fake synthesis factory, fixed fake scenarios covering all transitions, and fake hypothesis fuzzing
# --- END AUTOFAB METADATA ---
