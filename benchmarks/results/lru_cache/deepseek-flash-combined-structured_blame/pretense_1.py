# === File: lru_cache_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for LRUCache."""

from __future__ import annotations

from typing import Any, Optional, Tuple
import unittest

from pretense import (
    call_target,
    sut,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_2.parts.lru_cache.pretense.lru_cache_pretense import (
    LruCacheState,
    LruCacheStateMachine,
)
from benchmark_2.parts.lru_cache.lib.lru_cache import CacheCapacityError, CacheKeyNotFoundError
from benchmark_2.parts.lru_cache.lib.lru_cache_impl import LRUCache, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class LruCacheImplPseudoStateMachine(LruCacheStateMachine):
    """Implementation pseudo-state machine for LRUCache."""

    @transition(name="capacity")
    def capacity(self) -> int:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.capacity)
        assert ret > 0
        return ret

    @transition(name="size")
    def size(self) -> int:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.size)
        assert ret >= 0
        assert ret == len(target.keys_in_lru_order())
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.is_empty)
        assert ret == (target.size == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.is_full)
        assert ret == (target.size >= target.capacity)
        return ret

    @transition(LRUCache.configure)
    def configure(
        self,
        capacity: int,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.configure(capacity))
        assert target.capacity == capacity
        assert target.size <= capacity
        return ret

    @transition(LRUCache.get)
    def get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        order_before = target.keys_in_lru_order()
        present = key in order_before
        expected = target.peek(key, default)
        ret = call_target(target.get(key, default))
        order_after = target.keys_in_lru_order()
        assert ret is expected
        assert sorted(order_after) == sorted(order_before)
        if present:
            assert order_after[-1] == key
        else:
            assert order_after == order_before
        return ret

    @transition(LRUCache.put)
    def put(
        self,
        key: str,
        value: Any,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        order_before = target.keys_in_lru_order()
        size_before = target.size
        present = key in order_before
        ret = call_target(target.put(key, value))
        order_after = target.keys_in_lru_order()
        assert key in order_after
        assert order_after[-1] == key
        assert target.peek(key, None) is value
        if present:
            assert ret is None
            assert target.size == size_before
        else:
            assert target.size == min(size_before + 1, target.capacity)
            if ret is not None:
                evicted_key, evicted_value = ret
                assert evicted_key == order_before[0]
                assert evicted_key not in order_after
                assert target.peek(evicted_key, None) is None
            else:
                assert size_before < target.capacity
        return ret

    @transition(LRUCache.peek)
    def peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        order_before = target.keys_in_lru_order()
        stats_before = target.get_stats()
        ret = call_target(target.peek(key, default))
        assert target.keys_in_lru_order() == order_before
        assert target.get_stats() == stats_before
        assert ret is target.peek(key, default)
        return ret

    @transition(LRUCache.remove)
    def remove(
        self,
        key: str,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        order_before = target.keys_in_lru_order()
        ret = call_target(target.remove(key))
        order_after = target.keys_in_lru_order()
        assert key not in order_after
        assert target.size == len(order_before) - 1
        return ret

    @transition(LRUCache.clear)
    def clear(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        stats_before = target.get_stats()
        ret = call_target(target.clear())
        assert target.size == 0
        assert target.is_empty is True
        assert target.get_stats() == stats_before
        return ret

    @transition(LRUCache.get_stats)
    def get_stats(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.get_stats())
        assert ret.hits >= 0
        assert ret.misses >= 0
        assert ret.evictions >= 0
        return ret

    @transition(LRUCache.reset_stats)
    def reset_stats(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        size_before = target.size
        ret = call_target(target.reset_stats())
        stats = target.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert target.size == size_before
        return ret

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.keys_in_lru_order())
        assert len(ret) == target.size
        assert len(set(ret)) == len(ret)
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
        self.checked = self.sm.as_checked(LRUCache, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_defaults_and_configure(self) -> None:
        assert self.checked.capacity == 100
        assert self.checked.size == 0
        assert self.checked.is_empty is True
        assert self.checked.is_full is False
        self.checked.configure(2)
        assert self.checked.capacity == 2
        assert self.checked.size == 0
        self.checked.configure(4)
        assert self.checked.capacity == 4

    def test_put_get_hit_and_miss(self) -> None:
        self.checked.configure(3)
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.size == 2
        assert self.checked.is_full is False
        assert self.checked.keys_in_lru_order() == ["a", "b"]
        assert self.checked.get("a", None) == 1
        assert self.checked.keys_in_lru_order() == ["b", "a"]
        assert self.checked.get("missing", 42) == 42
        stats = self.checked.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.evictions == 0

    def test_update_existing_keeps_size(self) -> None:
        self.checked.configure(2)
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.is_full is True
        assert self.checked.put("a", 10) is None
        assert self.checked.size == 2
        assert self.checked.keys_in_lru_order() == ["b", "a"]
        assert self.checked.get("a", None) == 10

    def test_put_evicts_lru_at_capacity(self) -> None:
        self.checked.configure(2)
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.put("c", 3) == ("a", 1)
        assert self.checked.size == 2
        assert self.checked.keys_in_lru_order() == ["b", "c"]
        assert self.checked.get_stats().evictions == 1

    def test_configure_downsize_evicts_lru(self) -> None:
        self.checked.configure(4)
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.put("c", 3) is None
        assert self.checked.get("a", None) == 1
        self.checked.configure(2)
        assert self.checked.size == 2
        assert self.checked.keys_in_lru_order() == ["c", "a"]
        assert self.checked.get_stats().evictions == 1

    def test_peek_is_non_mutating(self) -> None:
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        order_before = self.checked.keys_in_lru_order()
        stats_before = self.checked.get_stats()
        assert self.checked.peek("a", None) == 1
        assert self.checked.peek("absent", 7) == 7
        assert self.checked.keys_in_lru_order() == order_before
        assert self.checked.get_stats() == stats_before

    def test_remove_and_clear(self) -> None:
        self.checked.configure(3)
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.remove("a") == 1
        assert self.checked.size == 1
        assert self.checked.keys_in_lru_order() == ["b"]
        assert self.checked.put("c", 3) is None
        hits_before = self.checked.get_stats().hits
        self.checked.clear()
        assert self.checked.size == 0
        assert self.checked.is_empty is True
        assert self.checked.is_full is False
        assert self.checked.get_stats().hits == hits_before

    def test_reset_stats(self) -> None:
        assert self.checked.put("a", 1) is None
        assert self.checked.put("b", 2) is None
        assert self.checked.put("c", 3) is None
        assert self.checked.get("a", None) == 1
        assert self.checked.get("missing", None) is None
        self.checked.configure(2)
        self.checked.reset_stats()
        stats = self.checked.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert self.checked.size == 2

    def test_configure_rejects_non_positive_capacity(self) -> None:
        assert self.real.capacity == 100
        with self.assertRaises(CacheCapacityError):
            self.real.configure(0)
        with self.assertRaises(CacheCapacityError):
            self.real.configure(-4)
        assert self.real.capacity == 100
        assert self.real.size == 0

    def test_remove_absent_key_raises(self) -> None:
        assert self.checked.put("present", 1) is None
        with self.assertRaises(CacheKeyNotFoundError):
            self.real.remove("absent")
        assert self.checked.size == 1
        assert self.checked.keys_in_lru_order() == ["present"]


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
    initial_state_factory=LruCacheState,
    name="LruCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:53:19Z
# LAST_CHANGED: 2026-11-08T17:52:47Z
# CHANGE: Add deterministic terminal contract-violation scenarios to TestLruCacheImplReal: drive the real SUT with configure(0)/configure(-4) expecting CacheCapacityError and remove('absent') after a seeded entry expecting CacheKeyNotFoundError, covering the contracted precondition raise paths.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:53:19Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:52:56Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for LRUCache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple
import unittest

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


DEFAULT_CAPACITY = 100
PREFERRED_KEYS = ["a", "b", "c"]
PREFERRED_CAPACITIES = [1, 2, 3, 5]


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class LruCacheState:
    """Canonical model state for LRUCache operations.

    ``items`` is maintained in access recency ascending order (least-recently-used
    first, most-recently-used last) so that lru order is directly observable.
    """

    capacity: int = DEFAULT_CAPACITY
    items: dict[str, Any] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class LruCacheStateMachine(StateMachine[LruCacheState]):
    """Unified Pretense State Machine for LRUCache."""

    def __init__(
        self,
        state: Optional[LruCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or LruCacheState(), singletons=singletons)

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

    @transition(LRUCache.configure)
    def configure(
        self,
        capacity: int,
    ) -> None:
        require_arg(capacity, Domain.range(1, 100), preferred=PREFERRED_CAPACITIES)
        ret = self.inner_configure(capacity)
        self.state.capacity = capacity
        excess = len(self.state.items) - capacity
        doomed_keys = list(self.state.items.keys())[:max(0, excess)]
        for doomed_key in doomed_keys:
            del self.state.items[doomed_key]
            self.state.evictions += 1
        assert ret is None
        assert self.state.capacity == capacity
        assert len(self.state.items) <= capacity
        return ret

    @transition(LRUCache.get)
    def get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require_arg(key, Domain.type(str), preferred=PREFERRED_KEYS)
        require_arg(default, Domain.any())
        present = key in self.state.items
        fake_ret = self.state.items[key] if present else default
        ret = self.inner_get(key, default)
        if present:
            value = self.state.items.pop(key)
            self.state.items[key] = value
            self.state.hits += 1
            assert key == list(self.state.items.keys())[-1]
        else:
            self.state.misses += 1
        assert ret == fake_ret
        return ret

    @transition(LRUCache.put)
    def put(
        self,
        key: str,
        value: Any,
    ) -> Optional[Tuple[str, Any]]:
        require_arg(key, Domain.type(str), preferred=PREFERRED_KEYS)
        require_arg(value, Domain.any())
        size_before = len(self.state.items)
        if key in self.state.items:
            fake_ret = None
            evicted_key = None
        elif len(self.state.items) >= self.state.capacity:
            evicted_key = next(iter(self.state.items))
            fake_ret = (evicted_key, self.state.items[evicted_key])
        else:
            fake_ret = None
            evicted_key = None
        ret = self.inner_put(key, value)
        if key in self.state.items:
            assert ret is None
            self.state.items.pop(key)
            self.state.items[key] = value
            assert len(self.state.items) == size_before
            assert key == list(self.state.items.keys())[-1]
        elif evicted_key is not None:
            evicted_value = self.state.items.pop(evicted_key)
            self.state.items[key] = value
            self.state.evictions += 1
            assert ret == fake_ret
            assert len(self.state.items) == size_before
            assert key == list(self.state.items.keys())[-1]
        else:
            assert ret is None
            self.state.items[key] = value
            assert len(self.state.items) == size_before + 1
            assert key == list(self.state.items.keys())[-1]
        return ret

    @transition(LRUCache.peek)
    def peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require_arg(key, Domain.type(str), preferred=PREFERRED_KEYS)
        require_arg(default, Domain.any())
        order_before = list(self.state.items.keys())
        stats_before = CacheStats(self.state.hits, self.state.misses, self.state.evictions)
        fake_ret = self.state.items[key] if key in self.state.items else default
        ret = self.inner_peek(key, default)
        assert ret == fake_ret
        assert list(self.state.items.keys()) == order_before
        assert CacheStats(self.state.hits, self.state.misses, self.state.evictions) == stats_before
        return ret

    @transition(LRUCache.remove)
    def remove(
        self,
        key: str,
    ) -> Any:
        require(len(self.state.items) > 0)
        require_arg(key, Domain.in_set(list(self.state.items.keys())))
        fake_ret = self.state.items[key]
        ret = self.inner_remove(key)
        del self.state.items[key]
        assert ret == fake_ret
        assert key not in self.state.items
        return ret

    @transition(LRUCache.clear)
    def clear(
        self,
    ) -> None:
        stats_before = CacheStats(self.state.hits, self.state.misses, self.state.evictions)
        ret = self.inner_clear()
        self.state.items.clear()
        assert ret is None
        assert len(self.state.items) == 0
        assert CacheStats(self.state.hits, self.state.misses, self.state.evictions) == stats_before
        return ret

    @transition(LRUCache.get_stats)
    def get_stats(
        self,
    ) -> CacheStats:
        expected = CacheStats(self.state.hits, self.state.misses, self.state.evictions)
        ret = self.inner_get_stats()
        assert ret == expected
        return ret

    @transition(LRUCache.reset_stats)
    def reset_stats(
        self,
    ) -> None:
        size_before = len(self.state.items)
        ret = self.inner_reset_stats()
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        assert ret is None
        assert self.state.hits == 0
        assert self.state.misses == 0
        assert self.state.evictions == 0
        assert len(self.state.items) == size_before
        return ret

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(
        self,
    ) -> List[str]:
        fake_ret = list(self.state.items.keys())
        ret = self.inner_keys_in_lru_order()
        assert ret == fake_ret
        return ret


proto = LruCacheStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeLruCache = synthesize_fake(LruCacheStateMachine)


def make_lru_cache_fake(state: Optional[LruCacheState] = None) -> LRUCache:
    """Synthesizes a fake LRUCache double backed by canonical model state."""
    return FakeLruCache(state=state or LruCacheState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestLruCacheFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies every declared transition."""

    def setUp(self) -> None:
        self.fake = make_lru_cache_fake()
        self.sm = LruCacheStateMachine()

    def test_initial_queries(self) -> None:
        assert self.fake.capacity == DEFAULT_CAPACITY
        assert self.fake.size == 0
        assert self.fake.is_empty is True
        assert self.fake.is_full is False
        assert self.fake.get_stats() == CacheStats()
        assert self.fake.keys_in_lru_order() == []

    def test_configure_updates_capacity(self) -> None:
        self.fake.configure(3)
        assert self.fake.capacity == 3
        assert self.fake.size == 0
        assert self.fake.is_full is False

    def test_get_and_peek_hit(self) -> None:
        assert self.fake.put("a", 1) is None
        assert self.fake.get("a", None) == 1
        assert self.fake.peek("a", None) == 1
        assert self.fake.keys_in_lru_order() == ["a"]
        stats = self.fake.get_stats()
        assert stats.hits == 1
        assert stats.misses == 0
        assert stats.evictions == 0

    def test_get_and_peek_miss(self) -> None:
        assert self.fake.put("a", 1) is None
        assert self.fake.get("missing", 7) == 7
        assert self.fake.peek("missing", 7) == 7
        assert self.fake.keys_in_lru_order() == ["a"]
        stats = self.fake.get_stats()
        assert stats.hits == 0
        assert stats.misses == 1

    def test_recency_promotion_and_eviction(self) -> None:
        self.fake.configure(2)
        assert self.fake.put("a", 1) is None
        assert self.fake.put("b", 2) is None
        assert self.fake.get("a", None) == 1
        assert self.fake.keys_in_lru_order() == ["b", "a"]
        assert self.fake.put("c", 3) == ("b", 2)
        assert self.fake.keys_in_lru_order() == ["a", "c"]
        assert self.fake.get_stats().evictions == 1

    def test_update_existing_entry(self) -> None:
        self.fake.configure(2)
        assert self.fake.put("a", 1) is None
        assert self.fake.put("b", 2) is None
        assert self.fake.put("a", 9) is None
        assert self.fake.size == 2
        assert self.fake.keys_in_lru_order() == ["b", "a"]
        assert self.fake.peek("a", None) == 9

    def test_configure_downsize_eviction(self) -> None:
        self.fake.configure(4)
        assert self.fake.put("a", 1) is None
        assert self.fake.put("b", 2) is None
        assert self.fake.put("c", 3) is None
        self.fake.configure(1)
        assert self.fake.size == 1
        assert self.fake.keys_in_lru_order() == ["c"]
        assert self.fake.get_stats().evictions == 2

    def test_remove_and_clear(self) -> None:
        assert self.fake.put("a", 1) is None
        assert self.fake.put("b", 2) is None
        assert self.fake.remove("a") == 1
        assert self.fake.keys_in_lru_order() == ["b"]
        self.fake.clear()
        assert self.fake.size == 0
        assert self.fake.is_empty is True

    def test_stats_lifecycle(self) -> None:
        assert self.fake.put("a", 1) is None
        assert self.fake.get("a", None) == 1
        assert self.fake.get("missing", None) is None
        stats = self.fake.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        self.fake.reset_stats()
        assert self.fake.get_stats() == CacheStats()

    def test_state_machine_transition_coverage(self) -> None:
        sm = self.sm
        assert sm.capacity() == DEFAULT_CAPACITY
        assert sm.size() == 0
        assert sm.is_empty() is True
        assert sm.is_full() is False
        assert sm.put("a", 1) is None
        assert sm.get("a", None) == 1
        assert sm.peek("a", None) == 1
        assert sm.remove("a") == 1
        sm.configure(2)
        assert sm.capacity() == 2
        assert sm.put("b", 2) is None
        assert sm.put("c", 3) is None
        assert sm.put("d", 4) == ("b", 2)
        assert sm.is_full() is True
        stats = sm.get_stats()
        assert stats.hits == 1
        assert stats.evictions == 1
        sm.reset_stats()
        assert sm.get_stats() == CacheStats()
        sm.clear()
        assert sm.keys_in_lru_order() == []


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeLruCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=LruCacheState,
    name="FakeLruCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:47:42Z
# LAST_CHANGED: 2026-11-08T17:47:42Z
# CHANGE: Implement LRUCache interface pretense state machine (model state with recency-ordered items, 1:1 transitions for all 8 operations + 4 properties, arg/state preconditions, pivots), synthesize the fake, fixed fake coverage tests, and fake Hypothesis fuzz suite.
# --- END AUTOFAB METADATA ---
