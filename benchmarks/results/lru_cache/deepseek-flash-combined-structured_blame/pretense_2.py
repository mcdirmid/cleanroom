# === File: lru_cache_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for LRUCache."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple
import unittest

from pretense import call_target, sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.lru_cache.pretense.lru_cache_pretense import (
    LruCacheState,
    LruCacheStateMachine,
)
from benchmark_2.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)
from benchmark_2.parts.lru_cache.lib.lru_cache_impl import LRUCache, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# The pseudo-state machine inherits every outer transition (preconditions,
# domains, model mutations, and postconditions) from the interface state machine.
# It only overrides inner transitions to execute the real SUT.

class LruCacheImplPseudoStateMachine(LruCacheStateMachine):
    """Implementation pseudo-state machine binding LruCache transitions to the concrete SUT."""

    def make_initial_state(self) -> LruCacheState:
        """Concrete implementation initializes its capacity limit to 100."""
        return LruCacheState(capacity=100)

    def inner_configure(
        self,
        capacity: int,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.configure(capacity))
        assert target.capacity == capacity
        assert target.size <= target.capacity
        return ret

    def inner_get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        present = key in self.state.items
        ret = call_target(target.get(key, default))
        if present:
            assert target.keys_in_lru_order()[-1] == key
        else:
            assert target.keys_in_lru_order() == list(self.state.items.keys())
        return ret

    def inner_put(
        self,
        key: str,
        value: Any,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        exists = key in self.state.items
        at_capacity = len(self.state.items) >= self.state.capacity
        evicted: Optional[Tuple[str, Any]] = None
        if not exists and at_capacity:
            oldest = next(iter(self.state.items))
            evicted = (oldest, self.state.items[oldest])
        ret = call_target(target.put(key, value))
        assert ret == evicted
        assert target.size <= target.capacity
        assert target.keys_in_lru_order()[-1] == key
        return ret

    def inner_peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        order_before = list(self.state.items.keys())
        ret = call_target(target.peek(key, default))
        assert target.keys_in_lru_order() == order_before
        return ret

    def inner_remove(
        self,
        key: str,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.remove(key))
        if key in self.state.items:
            assert ret == self.state.items[key]
        assert key not in target.keys_in_lru_order()
        return ret

    def inner_clear(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.clear())
        assert target.size == 0
        assert target.is_empty
        return ret

    def inner_get_stats(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.get_stats())
        assert ret.hits == self.state.hits
        assert ret.misses == self.state.misses
        assert ret.evictions == self.state.evictions
        return ret

    def inner_reset_stats(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.reset_stats())
        assert target.get_stats() == CacheStats()
        return ret

    def inner_keys_in_lru_order(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        order_before = list(self.state.items.keys())
        ret = call_target(target.keys_in_lru_order())
        assert ret == order_before
        return ret

    def inner_capacity(self) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "capacity"))
        assert ret == self.state.capacity
        return ret

    def inner_size(self) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "size"))
        assert ret == len(self.state.items)
        return ret

    def inner_is_empty(self) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "is_empty"))
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_full(self) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "is_full"))
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret


proto = LruCacheImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestLruCacheImplReal(unittest.TestCase):
    """Verifies that the concrete implementation satisfies the LruCache contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(LRUCache)
        self.sm = LruCacheImplPseudoStateMachine(singletons={LRUCache: self.real})
        self.checked: Any = self.sm.as_checked(LRUCache, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_default_properties(self) -> None:
        assert self.checked.capacity == 100
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert not self.checked.is_full

    def test_configure_updates_capacity(self) -> None:
        self.checked.configure(3)
        assert self.checked.capacity == 3
        assert self.checked.size == 0
        assert self.checked.is_empty
        assert not self.checked.is_full

    def test_put_get_roundtrip(self) -> None:
        self.checked.configure(2)
        assert self.checked.put("alpha", 1) is None
        assert self.checked.put("beta", 2) is None
        assert self.checked.is_full
        assert self.checked.get("alpha", None) == 1
        assert self.checked.get("missing", -1) == -1
        assert self.checked.peek("beta", None) == 2
        assert self.checked.peek("missing", -1) == -1
        assert self.checked.put("alpha", 10) is None
        assert self.checked.keys_in_lru_order() == ["beta", "alpha"]

    def test_put_evicts_least_recently_used(self) -> None:
        self.checked.configure(2)
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        evicted = self.checked.put("gamma", 3)
        assert evicted == ("alpha", 1)
        assert self.checked.size == 2
        assert self.checked.keys_in_lru_order() == ["beta", "gamma"]
        assert self.checked.get_stats().evictions == 1

    def test_configure_downsizes_by_evicting(self) -> None:
        self.checked.configure(3)
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        self.checked.put("gamma", 3)
        self.checked.configure(1)
        assert self.checked.capacity == 1
        assert self.checked.size == 1
        assert self.checked.keys_in_lru_order() == ["gamma"]
        assert self.checked.get_stats().evictions == 2
        assert self.checked.is_full

    def test_remove_and_clear(self) -> None:
        self.checked.configure(4)
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        assert self.checked.remove("alpha") == 1
        assert self.checked.size == 1
        assert self.checked.keys_in_lru_order() == ["beta"]
        self.checked.clear()
        assert self.checked.is_empty
        assert self.checked.get_stats() == CacheStats()

    def test_telemetry_reporting_and_reset(self) -> None:
        self.checked.configure(1)
        self.checked.put("alpha", 1)
        assert self.checked.get("alpha", None) == 1
        assert self.checked.get("missing", None) is None
        self.checked.put("beta", 2)
        stats = self.checked.get_stats()
        assert stats == CacheStats(hits=1, misses=1, evictions=1)
        self.checked.reset_stats()
        assert self.checked.get_stats() == CacheStats()

    def test_configure_rejects_invalid_capacity(self) -> None:
        self.checked.violating(CacheCapacityError).configure(0)

    def test_remove_rejects_missing_key(self) -> None:
        self.checked.configure(2)
        self.checked.put("alpha", 1)
        self.checked.violating(CacheKeyNotFoundError).remove("missing")


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
# LAST_CLEANED: 2026-11-09T22:11:12Z
# LAST_CHANGED: 2026-11-09T22:10:31Z
# CHANGE: Implement LruCache implementation pseudo-state machine: make_initial_state specializing capacity to 100, inner-transition overrides that call the concrete SUT and verify target observables (capacity, size, order, stats, eviction returns), real scenario tests covering all statements and both contracted error branches via violating(...), and real Hypothesis fuzzing with sut_factory.
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T22:11:12Z
# PRETENSE_QA_AUDIT: 2026-11-09T22:10:51Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for LruCache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
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
# 1. Model State & 1:1 Transitions
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches and contracted exceptions live naturally inside the single
# transition body. require_arg defines the caller precondition contract, and
# every transition delegates its return value to a matching inner transition so
# that implementation pseudo-state machines can bind the concrete SUT.


@dataclass
class LruCacheState:
    """Canonical model state for LruCache operations."""

    capacity: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    items: Dict[str, Any] = field(default_factory=dict)


class LruCacheStateMachine(StateMachine[LruCacheState]):
    """Unified Pretense State Machine for LruCache."""

    def __init__(
        self,
        state: Optional[LruCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    @property
    def initial_capacity(self) -> int:
        """Default capacity limit of the interface model.

        The public interface leaves the starting capacity unspecified; concrete
        implementations specialize this hook with their own initial limit.
        """
        return 4

    def make_initial_state(self) -> LruCacheState:
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return LruCacheState(capacity=self.initial_capacity)

    # --------------------------------------------------------------------------
    # Return value producers (inner transitions) used by the synthesized fake.
    # Implementation pseudo-state machines override these to call the real SUT.
    # --------------------------------------------------------------------------

    def inner_configure(self, capacity: int) -> None:
        return make_return_value()

    def inner_get(self, key: str, default: Optional[Any]) -> Any:
        if key in self.state.items:
            return make_return_value(self.state.items[key])
        return make_return_value(default)

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        if key in self.state.items:
            return make_return_value()
        if len(self.state.items) >= self.state.capacity:
            oldest = next(iter(self.state.items))
            return make_return_value((oldest, self.state.items[oldest]))
        return make_return_value()

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        if key in self.state.items:
            return make_return_value(self.state.items[key])
        return make_return_value(default)

    def inner_remove(self, key: str) -> Any:
        return make_return_value(self.state.items[key])

    def inner_clear(self) -> None:
        return make_return_value()

    def inner_get_stats(self) -> CacheStats:
        return make_return_value(
            CacheStats(
                hits=self.state.hits,
                misses=self.state.misses,
                evictions=self.state.evictions,
            )
        )

    def inner_reset_stats(self) -> None:
        return make_return_value()

    def inner_keys_in_lru_order(self) -> List[str]:
        return make_return_value(list(self.state.items.keys()))

    def inner_capacity(self) -> int:
        return make_return_value(self.state.capacity)

    def inner_size(self) -> int:
        return make_return_value(len(self.state.items))

    def inner_is_empty(self) -> bool:
        return make_return_value(len(self.state.items) == 0)

    def inner_is_full(self) -> bool:
        return make_return_value(len(self.state.items) >= self.state.capacity)

    # --------------------------------------------------------------------------
    # 1:1 transitions.
    # --------------------------------------------------------------------------

    @transition(LRUCache.configure)
    def configure(
        self,
        capacity: int,
    ) -> None:
        require_arg(capacity, Domain.range(1, 100), preferred=[1, 2, 3])
        ret = self.inner_configure(capacity)
        assert ret is None
        self.state.capacity = capacity
        for _ in range(len(self.state.items)):
            if len(self.state.items) <= self.state.capacity:
                break
            oldest = next(iter(self.state.items))
            del self.state.items[oldest]
            self.state.evictions += 1
        assert len(self.state.items) <= self.state.capacity
        assert self.state.capacity == capacity
        return ret

    @transition(LRUCache.get)
    def get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require_arg(key, Domain.type(str), preferred=["alpha", "beta", "gamma"])
        require_arg(default, Domain.optional(Domain.type(int)), preferred=[None, -1])
        present = key in self.state.items
        expected = self.state.items[key] if present else default
        ret = self.inner_get(key, default)
        assert ret == expected
        if present:
            del self.state.items[key]
            self.state.items[key] = expected
            self.state.hits += 1
            assert list(self.state.items.keys())[-1] == key
        else:
            self.state.misses += 1
            assert key not in self.state.items
        return ret

    @transition(LRUCache.put)
    def put(
        self,
        key: str,
        value: Any,
    ) -> Optional[Tuple[str, Any]]:
        require_arg(key, Domain.type(str), preferred=["alpha", "beta", "gamma"])
        require_arg(value, Domain.type(int), preferred=[0, 1, 2])
        exists = key in self.state.items
        at_capacity = len(self.state.items) >= self.state.capacity
        evicted: Optional[Tuple[str, Any]] = None
        if not exists and at_capacity:
            oldest = next(iter(self.state.items))
            evicted = (oldest, self.state.items[oldest])
        ret = self.inner_put(key, value)
        assert ret == evicted
        if exists:
            del self.state.items[key]
            self.state.items[key] = value
            assert len(self.state.items) <= self.state.capacity
        elif evicted is not None:
            del self.state.items[evicted[0]]
            self.state.items[key] = value
            self.state.evictions += 1
        else:
            self.state.items[key] = value
        assert key in self.state.items
        assert list(self.state.items.keys())[-1] == key
        return ret

    @transition(LRUCache.peek)
    def peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require_arg(key, Domain.type(str), preferred=["alpha", "beta", "gamma"])
        require_arg(default, Domain.optional(Domain.type(int)), preferred=[None, -1])
        present = key in self.state.items
        expected = self.state.items[key] if present else default
        order_before = list(self.state.items.keys())
        ret = self.inner_peek(key, default)
        assert ret == expected
        assert list(self.state.items.keys()) == order_before
        return ret

    @transition(LRUCache.remove)
    def remove(
        self,
        key: str,
    ) -> Any:
        require_arg(key, Domain.in_set(list(self.state.items.keys())))
        ret = self.inner_remove(key)
        expected = self.state.items[key]
        assert ret == expected
        del self.state.items[key]
        assert key not in self.state.items
        return ret

    @transition(LRUCache.clear)
    def clear(
        self,
    ) -> None:
        stats_before = CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        )
        ret = self.inner_clear()
        assert ret is None
        self.state.items.clear()
        assert len(self.state.items) == 0
        assert CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        ) == stats_before
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
        ret = self.inner_get_stats()
        assert ret == expected
        assert ret.hits == self.state.hits
        assert ret.misses == self.state.misses
        assert ret.evictions == self.state.evictions
        return ret

    @transition(LRUCache.reset_stats)
    def reset_stats(
        self,
    ) -> None:
        size_before = len(self.state.items)
        ret = self.inner_reset_stats()
        assert ret is None
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        assert len(self.state.items) == size_before
        assert CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        ) == CacheStats()
        return ret

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(
        self,
    ) -> List[str]:
        order_before = list(self.state.items.keys())
        ret = self.inner_keys_in_lru_order()
        assert ret == order_before
        assert list(self.state.items.keys()) == order_before
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    @transition(name="size")
    def size(self) -> int:
        ret = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    @transition.seeding
    def seed_empty(self) -> None:
        """Seeds a blank cache model with the default capacity and cleared telemetry."""
        self.state.capacity = self.make_initial_state().capacity
        self.state.items.clear()
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0


proto = LruCacheStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeLruCache = synthesize_fake(LruCacheStateMachine)


def make_lru_cache_fake(state: Optional[LruCacheState] = None) -> LRUCache:
    """Synthesizes a fake LRUCache double backed by model state."""
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
        """Exercises every transition and seeding transition on the synthesized fake."""
        self.sm.seed_empty()
        self.fake.configure(2)
        assert self.fake.capacity == 2
        assert self.fake.size == 0
        assert self.fake.is_empty
        assert not self.fake.is_full
        assert self.fake.put("alpha", 1) is None
        assert self.fake.put("beta", 2) is None
        assert self.fake.is_full
        assert self.fake.get("alpha", None) == 1
        assert self.fake.get("missing", -1) == -1
        assert self.fake.peek("beta", None) == 2
        assert self.fake.peek("missing", -1) == -1
        assert self.fake.put("alpha", 10) is None
        assert self.fake.put("gamma", 3) == ("beta", 2)
        assert self.fake.remove("alpha") == 10
        stats = self.fake.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.evictions == 1
        assert self.fake.keys_in_lru_order() == ["gamma"]
        self.fake.clear()
        assert self.fake.is_empty
        self.fake.reset_stats()
        assert self.fake.get_stats() == CacheStats()

    def test_state_machine_transitions(self) -> None:
        """Exercises every transition and seeding transition on the model state machine."""
        self.sm.seed_empty()
        self.sm.configure(2)
        assert self.sm.capacity() == 2
        assert self.sm.size() == 0
        assert self.sm.is_empty()
        assert not self.sm.is_full()
        assert self.sm.put("alpha", 1) is None
        assert self.sm.put("beta", 2) is None
        assert self.sm.is_full()
        assert self.sm.get("alpha", None) == 1
        assert self.sm.get("missing", -1) == -1
        assert self.sm.peek("beta", None) == 2
        assert self.sm.put("alpha", 10) is None
        assert self.sm.put("gamma", 3) == ("beta", 2)
        assert self.sm.remove("alpha") == 10
        assert self.sm.get_stats() == CacheStats(hits=1, misses=1, evictions=1)
        assert self.sm.keys_in_lru_order() == ["gamma"]
        self.sm.clear()
        assert self.sm.is_empty()
        self.sm.reset_stats()
        assert self.sm.get_stats() == CacheStats()


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeLruCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeLruCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:10:25Z
# LAST_CHANGED: 2026-11-09T22:10:25Z
# CHANGE: Implement full LruCache interface pretense model: LRU-ordered dict state with capacity/telemetry, 13 1:1 transitions with concrete domains (Domain.range, Domain.optional, Domain.in_set for remove), inner-transition return producers, seeding transition, synthesized fake factory, fixed fake coverage suite, and fake Hypothesis fuzzing.
# --- END AUTOFAB METADATA ---
