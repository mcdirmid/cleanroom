# === File: lru_cache_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for LRUCache."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    call_target,
    sut,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmarks.runs.lru_cache_deepseek_flash_1.parts.lru_cache.pretense.lru_cache_pretense import (
    LruCacheState,
    LruCacheStateMachine,
)
from benchmarks.runs.lru_cache_deepseek_flash_1.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)
from benchmarks.runs.lru_cache_deepseek_flash_1.parts.lru_cache.lib.lru_cache_impl import (
    LRUCache,
    __initialize__,
)


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class LruCacheImplPseudoStateMachine(LruCacheStateMachine):
    """Implementation pseudo-state machine for LruCache."""

    def make_initial_state(self) -> LruCacheState:
        """Specializes the open cache limit to the concrete implementation default."""
        return LruCacheState(capacity=100)

    def inner_configure(
        self,
        capacity: int,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        evictions_before = target.get_stats().evictions
        ret = call_target(target.configure(capacity))
        assert target.capacity == capacity
        assert target.size <= capacity
        assert target.get_stats().evictions >= evictions_before
        return ret

    def inner_get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        stats_before = target.get_stats()
        ret = call_target(target.get(key, default))
        stats_after = target.get_stats()
        assert stats_after.hits + stats_after.misses == stats_before.hits + stats_before.misses + 1
        return ret

    def inner_put(
        self,
        key: str,
        value: Any,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        size_before = target.size
        ret = call_target(target.put(key, value))
        assert target.size >= size_before
        assert target.size <= size_before + 1
        return ret

    def inner_peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        stats_before = target.get_stats()
        ret = call_target(target.peek(key, default))
        assert target.get_stats() == stats_before
        return ret

    def inner_remove(
        self,
        key: str,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        size_before = target.size
        ret = call_target(target.remove(key))
        assert target.size == size_before - 1
        return ret

    def inner_clear(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        stats_before = target.get_stats()
        ret = call_target(target.clear())
        assert target.size == 0
        assert target.get_stats() == stats_before
        return ret

    def inner_get_stats(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.get_stats())
        assert ret.hits >= 0
        assert ret.misses >= 0
        assert ret.evictions >= 0
        return ret

    def inner_reset_stats(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        size_before = target.size
        ret = call_target(target.reset_stats())
        assert target.get_stats() == CacheStats()
        assert target.size == size_before
        return ret

    def inner_keys_in_lru_order(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        stats_before = target.get_stats()
        ret = call_target(target.keys_in_lru_order())
        assert target.get_stats() == stats_before
        assert len(ret) == target.size
        return ret

    def inner_capacity(self) -> int:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.capacity)
        return ret

    def inner_size(self) -> int:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.size)
        return ret

    def inner_is_empty(self) -> bool:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.is_empty)
        return ret

    def inner_is_full(self) -> bool:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.is_full)
        return ret


proto = LruCacheImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestLruCacheImplReal(unittest.TestCase):
    """Verifies that the concrete LRUCache implementation satisfies its contracts."""

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

    def test_initial_properties(self) -> None:
        """Fresh cache reports the implementation default capacity and blank state."""
        self.assertEqual(self.checked.capacity, 100)
        self.assertEqual(self.checked.size, 0)
        self.assertTrue(self.checked.is_empty)
        self.assertFalse(self.checked.is_full)
        self.assertEqual(self.checked.keys_in_lru_order(), [])

    def test_configure_updates_capacity(self) -> None:
        """Configuring a positive capacity updates the reported limit."""
        self.checked.configure(4)
        self.assertEqual(self.checked.capacity, 4)
        self.assertEqual(self.checked.size, 0)
        self.assertTrue(self.checked.is_empty)
        self.assertFalse(self.checked.is_full)

    def test_put_insert_below_capacity(self) -> None:
        """Inserting below capacity grows the cache without eviction."""
        self.checked.configure(3)
        self.assertIsNone(self.checked.put("alpha", 1))
        self.assertIsNone(self.checked.put("beta", 2))
        self.assertEqual(self.checked.size, 2)
        self.assertEqual(self.checked.keys_in_lru_order(), ["alpha", "beta"])
        stats = self.checked.get_stats()
        self.assertEqual(stats.evictions, 0)

    def test_put_evicts_least_recently_used(self) -> None:
        """Inserting at capacity evicts the least-recently-used entry."""
        self.checked.configure(2)
        self.assertIsNone(self.checked.put("alpha", 1))
        self.assertIsNone(self.checked.put("beta", 2))
        self.assertTrue(self.checked.is_full)
        self.assertEqual(self.checked.put("gamma", 3), ("alpha", 1))
        self.assertEqual(self.checked.size, 2)
        self.assertEqual(self.checked.keys_in_lru_order(), ["beta", "gamma"])
        stats = self.checked.get_stats()
        self.assertEqual(stats.evictions, 1)

    def test_put_updates_existing_entry(self) -> None:
        """Updating an existing key keeps the size stable and promotes recency."""
        self.checked.configure(2)
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        self.assertIsNone(self.checked.put("alpha", 10))
        self.assertEqual(self.checked.size, 2)
        self.assertEqual(self.checked.keys_in_lru_order(), ["beta", "alpha"])
        self.assertEqual(self.checked.peek("alpha", None), 10)

    def test_get_hit_and_miss(self) -> None:
        """Hits return stored values and promote recency; misses return the default."""
        self.checked.configure(3)
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        self.checked.put("gamma", 3)
        self.assertEqual(self.checked.get("alpha", -1), 1)
        self.assertEqual(self.checked.keys_in_lru_order(), ["beta", "gamma", "alpha"])
        self.assertEqual(self.checked.get("absent", -1), -1)
        self.assertEqual(self.checked.keys_in_lru_order(), ["beta", "gamma", "alpha"])
        stats = self.checked.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)

    def test_peek_preserves_order_and_telemetry(self) -> None:
        """Peek inspects present values and returns defaults without telemetry changes."""
        self.checked.configure(3)
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        self.assertEqual(self.checked.peek("alpha", None), 1)
        self.assertIsNone(self.checked.peek("absent", None))
        self.assertEqual(self.checked.keys_in_lru_order(), ["alpha", "beta"])
        stats = self.checked.get_stats()
        self.assertEqual((stats.hits, stats.misses, stats.evictions), (0, 0, 0))

    def test_remove_existing_entry(self) -> None:
        """Removing an existing key returns its value and shrinks the cache."""
        self.checked.configure(3)
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        self.assertEqual(self.checked.remove("alpha"), 1)
        self.assertEqual(self.checked.size, 1)
        self.assertFalse(self.checked.is_empty)
        self.assertEqual(self.checked.keys_in_lru_order(), ["beta"])

    def test_clear_preserves_telemetry(self) -> None:
        """Clearing drops all entries while keeping accumulated counters."""
        self.checked.configure(2)
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        self.assertEqual(self.checked.get("alpha", None), 1)
        self.assertEqual(self.checked.put("gamma", 3), ("beta", 2))
        self.checked.clear()
        self.assertEqual(self.checked.size, 0)
        self.assertTrue(self.checked.is_empty)
        self.assertEqual(self.checked.keys_in_lru_order(), [])
        stats = self.checked.get_stats()
        self.assertEqual((stats.hits, stats.misses, stats.evictions), (1, 0, 1))

    def test_get_stats_reports_telemetry(self) -> None:
        """get_stats reports cumulative hits, misses, and evictions."""
        self.checked.configure(1)
        self.checked.put("alpha", 1)
        self.checked.get("alpha", None)
        self.checked.get("absent", None)
        self.checked.put("beta", 2)
        stats = self.checked.get_stats()
        self.assertEqual((stats.hits, stats.misses, stats.evictions), (1, 1, 1))

    def test_reset_stats_preserves_entries(self) -> None:
        """reset_stats zeroes telemetry without disturbing cached entries."""
        self.checked.configure(3)
        self.checked.put("alpha", 1)
        self.checked.get("alpha", None)
        self.checked.get("absent", None)
        self.checked.reset_stats()
        stats = self.checked.get_stats()
        self.assertEqual((stats.hits, stats.misses, stats.evictions), (0, 0, 0))
        self.assertEqual(self.checked.size, 1)
        self.assertEqual(self.checked.keys_in_lru_order(), ["alpha"])

    def test_configure_downsize_evicts_least_recently_used(self) -> None:
        """Shrinking capacity evicts least-recently-used entries until size fits."""
        self.checked.configure(3)
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        self.checked.put("gamma", 3)
        self.assertEqual(self.checked.get("beta", None), 2)
        self.checked.configure(1)
        self.assertEqual(self.checked.capacity, 1)
        self.assertEqual(self.checked.size, 1)
        self.assertEqual(self.checked.keys_in_lru_order(), ["beta"])
        stats = self.checked.get_stats()
        self.assertEqual(stats.evictions, 2)

    def test_configure_invalid_capacity(self) -> None:
        """Configuring a non-positive capacity violates the caller contract."""
        self.checked.violating(CacheCapacityError).configure(0)

    def test_configure_negative_capacity(self) -> None:
        """Configuring a negative capacity violates the caller contract."""
        self.checked.violating(CacheCapacityError).configure(-3)

    def test_remove_missing_key(self) -> None:
        """Removing an absent key violates the caller contract."""
        self.checked.configure(2)
        self.checked.put("alpha", 1)
        self.checked.violating(CacheKeyNotFoundError).remove("absent")


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
# LAST_CLEANED: 2026-11-10T17:06:02Z
# LAST_CHANGED: 2026-11-10T17:05:23Z
# CHANGE: Initial LRUCache implementation pretense: pseudo-state machine inheriting LruCacheStateMachine with make_initial_state specializing the open capacity to the concrete default 100 and inner_<name> overrides binding each concrete LRUCache call via call_target with postcondition parity assertions; TestLruCacheImplReal drives all contracts through self.checked (configure/get/put/peek/remove/clear/get_stats/reset_stats/keys_in_lru_order plus properties and downsize eviction) with violating(CacheCapacityError)/violating(CacheKeyNotFoundError) scenarios as terminal calls; LruCacheFuzzTest fuzzes the real SUT.
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T17:06:02Z
# PRETENSE_QA_AUDIT: 2026-11-10T17:05:41Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for LRUCache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
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
from benchmarks.runs.lru_cache_deepseek_flash_1.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Contract violations (*Error, e.g. CacheKeyNotFoundError) are preconditions:
# gate them with require(...) / require_arg(..., error=...) and NEVER `with raises(...)`.
# Operational postcondition exceptions (*Exception) would use `with raises(...)` around
# the pivot, but this unit declares no *Exception contracts.

@dataclass
class LruCacheState:
    """Canonical model state for LRUCache operations."""

    initialized: bool = True
    capacity: int = 8
    entries: Dict[str, Any] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def keys(self) -> List[str]:
        """Active cache keys ordered from least-recently-used to most-recently-used."""
        return list(self.entries)

    @property
    def size(self) -> int:
        """Current count of active cache entries."""
        return len(self.entries)

    @property
    def stats(self) -> CacheStats:
        """Telemetry snapshot derived from the model counters."""
        return CacheStats(hits=self.hits, misses=self.misses, evictions=self.evictions)


class LruCacheStateMachine(StateMachine[LruCacheState]):
    """Unified Pretense State Machine for LruCache."""

    def __init__(
        self,
        state: Optional[LruCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    @property
    def default_capacity(self) -> int:
        """Interface-level capacity assumed for unspecified (open) cache limits."""
        return 8

    def make_initial_state(self) -> LruCacheState:
        """Constructs initial model state. May be specialized by pseudo-state machines."""
        return LruCacheState(capacity=self.default_capacity)

    @transition(LRUCache.configure)
    def configure(
        self,
        capacity: int,
    ) -> None:
        require(self.state.initialized)
        require_arg(capacity, Domain.range(1, 64), preferred=[1, 2, 3, 8], error=CacheCapacityError)
        ret = make_return_value(None)
        assert ret is None
        for _ in range(self.state.size - capacity):
            evicted_key = self.state.keys[0]
            del self.state.entries[evicted_key]
            self.state.evictions += 1
        self.state.capacity = capacity
        assert sut(LRUCache).capacity == capacity
        assert sut(LRUCache).size == self.state.size
        assert sut(LRUCache).keys_in_lru_order() == self.state.keys

    @transition(LRUCache.get)
    def get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require(self.state.initialized)
        require_arg(key, Domain.type(str), preferred=["alpha", "beta", "gamma"])
        require_arg(default, Domain.any())
        if key in self.state.entries:
            cached = self.state.entries[key]
            hit: Any = make_return_value(cached)
            assert hit == cached
            del self.state.entries[key]
            self.state.entries[key] = cached
            self.state.hits += 1
            assert sut(LRUCache).size == self.state.size
            assert sut(LRUCache).keys_in_lru_order() == self.state.keys
            return hit
        missed: Any = make_return_value(default)
        assert missed == default
        self.state.misses += 1
        assert sut(LRUCache).size == self.state.size
        return missed

    @transition(LRUCache.put)
    def put(
        self,
        key: str,
        value: Any,
    ) -> Optional[Tuple[str, Any]]:
        require(self.state.initialized)
        require_arg(key, Domain.type(str), preferred=["alpha", "beta", "gamma"])
        require_arg(value, Domain.any())
        if key in self.state.entries:
            updated: Optional[Tuple[str, Any]] = make_return_value(None)
            assert updated is None
            del self.state.entries[key]
            self.state.entries[key] = value
            assert sut(LRUCache).size == self.state.size
            return updated
        if self.state.size >= self.state.capacity:
            evicted_key = self.state.keys[0]
            evicted_value = self.state.entries[evicted_key]
            evicted: Optional[Tuple[str, Any]] = (evicted_key, evicted_value)
            eviction_result = make_return_value(evicted)
            assert eviction_result == evicted
            del self.state.entries[evicted_key]
            self.state.evictions += 1
            self.state.entries[key] = value
            assert sut(LRUCache).size == self.state.size
            return eviction_result
        inserted: Optional[Tuple[str, Any]] = make_return_value(None)
        assert inserted is None
        self.state.entries[key] = value
        assert sut(LRUCache).size == self.state.size
        return inserted

    @transition(LRUCache.peek)
    def peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require(self.state.initialized)
        require_arg(key, Domain.type(str), preferred=["alpha", "beta", "gamma"])
        require_arg(default, Domain.any())
        expected = self.state.entries.get(key, default)
        inspected: Any = make_return_value(expected)
        assert inspected == expected
        assert sut(LRUCache).get_stats() == self.state.stats
        assert sut(LRUCache).keys_in_lru_order() == self.state.keys
        return inspected

    @transition(LRUCache.remove)
    def remove(
        self,
        key: str,
    ) -> Any:
        require(self.state.initialized)
        require(bool(self.state.entries), error=CacheKeyNotFoundError)
        require_arg(key, Domain.in_set(self.state.keys), error=CacheKeyNotFoundError)
        expected = self.state.entries.get(key)
        removed: Any = make_return_value(expected)
        assert removed == expected
        del self.state.entries[key]
        assert sut(LRUCache).size == self.state.size
        return removed

    @transition(LRUCache.clear)
    def clear(
        self,
    ) -> None:
        require(self.state.initialized)
        stats_before = self.state.stats
        ret = make_return_value(None)
        assert ret is None
        self.state.entries.clear()
        assert sut(LRUCache).is_empty
        assert sut(LRUCache).get_stats() == stats_before

    @transition(LRUCache.get_stats)
    def get_stats(
        self,
    ) -> CacheStats:
        require(self.state.initialized)
        expected = self.state.stats
        reported: CacheStats = make_return_value(expected)
        assert reported == expected
        return reported

    @transition(LRUCache.reset_stats)
    def reset_stats(
        self,
    ) -> None:
        require(self.state.initialized)
        size_before = self.state.size
        ret = make_return_value(None)
        assert ret is None
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        assert sut(LRUCache).get_stats() == CacheStats()
        assert sut(LRUCache).size == size_before

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(
        self,
    ) -> List[str]:
        require(self.state.initialized)
        expected = self.state.keys
        ordered: List[str] = make_return_value(expected)
        assert ordered == expected
        assert sut(LRUCache).size == self.state.size
        return ordered

    @transition(name="capacity")
    def capacity(self) -> int:
        require(self.state.initialized)
        expected = self.state.capacity
        configured: int = make_return_value(expected)
        assert configured == expected
        return configured

    @transition(name="size")
    def size(self) -> int:
        require(self.state.initialized)
        expected = self.state.size
        counted: int = make_return_value(expected)
        assert counted == expected
        return counted

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        require(self.state.initialized)
        expected = self.state.size == 0
        empty: bool = make_return_value(expected)
        assert empty == expected
        return empty

    @transition(name="is_full")
    def is_full(self) -> bool:
        require(self.state.initialized)
        expected = self.state.size >= self.state.capacity
        full: bool = make_return_value(expected)
        assert full == expected
        return full

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds a blank cache model state for fake initialization."""
        self.state.initialized = True


proto = LruCacheStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeLruCache = synthesize_fake(LruCacheStateMachine)


def make_lru_cache_fake(
    state: Optional[LruCacheState] = None,
) -> LRUCache:
    """Synthesizes a fake LRUCache instance backed by shared model state."""
    return FakeLruCache(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestLruCacheFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_lru_cache_fake()
        self.sm = LruCacheStateMachine()

    def test_seeding_transition(self) -> None:
        """Exercises the initial seeding transition."""
        self.sm.seed_initial()
        self.assertTrue(self.sm.state.initialized)

    def test_property_transitions(self) -> None:
        """Exercises the capacity, size, is_empty, and is_full transitions."""
        self.assertEqual(self.fake.capacity, 8)
        self.assertEqual(self.fake.size, 0)
        self.assertTrue(self.fake.is_empty)
        self.assertFalse(self.fake.is_full)
        self.fake.configure(2)
        self.assertEqual(self.fake.capacity, 2)
        self.fake.put("alpha", 1)
        self.fake.put("beta", 2)
        self.assertEqual(self.fake.size, 2)
        self.assertTrue(self.fake.is_full)

    def test_put_eviction_and_recency(self) -> None:
        """Exercises put insertion, update, and least-recently-used eviction."""
        self.fake.configure(2)
        self.assertIsNone(self.fake.put("alpha", 1))
        self.assertIsNone(self.fake.put("beta", 2))
        self.assertEqual(self.fake.put("gamma", 3), ("alpha", 1))
        self.assertEqual(self.fake.keys_in_lru_order(), ["beta", "gamma"])
        self.assertIsNone(self.fake.put("beta", 20))
        self.assertEqual(self.fake.peek("beta", None), 20)
        self.assertEqual(self.fake.keys_in_lru_order(), ["gamma", "beta"])

    def test_get_hit_and_miss(self) -> None:
        """Exercises cache hits, misses, and hit-driven recency promotion."""
        self.fake.put("alpha", 1)
        self.fake.put("beta", 2)
        self.assertEqual(self.fake.get("alpha", -1), 1)
        self.assertEqual(self.fake.keys_in_lru_order(), ["beta", "alpha"])
        self.assertEqual(self.fake.get("absent", -1), -1)
        stats = self.fake.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)

    def test_peek_does_not_mutate(self) -> None:
        """Exercises non-mutating peek for present and absent keys."""
        self.fake.put("alpha", 1)
        self.fake.put("beta", 2)
        self.assertEqual(self.fake.peek("alpha", None), 1)
        self.assertIsNone(self.fake.peek("absent", None))
        self.assertEqual(self.fake.keys_in_lru_order(), ["alpha", "beta"])
        stats = self.fake.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)

    def test_remove_clear_and_telemetry(self) -> None:
        """Exercises remove, clear, get_stats, and reset_stats transitions."""
        self.fake.put("alpha", 1)
        self.fake.get("alpha", None)
        self.assertEqual(self.fake.remove("alpha"), 1)
        self.assertEqual(self.fake.size, 0)
        self.fake.put("beta", 2)
        self.fake.clear()
        self.assertTrue(self.fake.is_empty)
        stats = self.fake.get_stats()
        self.assertEqual(stats.hits, 1)
        self.fake.reset_stats()
        reset = self.fake.get_stats()
        self.assertEqual((reset.hits, reset.misses, reset.evictions), (0, 0, 0))
        self.assertEqual(self.fake.size, 0)


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeLruCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeLruCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T17:05:16Z
# LAST_CHANGED: 2026-11-10T17:05:16Z
# CHANGE: Initial LRUCache interface pretense: model state (capacity, LRU-ordered entries, hits/misses/evictions), 1:1 transitions for configure/get/put/peek/remove/clear/get_stats/reset_stats/keys_in_lru_order plus capacity/size/is_empty/is_full properties, contract-violation gating via require/require_arg with error=CacheCapacityError/CacheKeyNotFoundError, seeding transition, synthesized FakeLruCache with make_lru_cache_fake factory, TestLruCacheFake covering every transition, and FakeLruCacheFuzzTest.
# --- END AUTOFAB METADATA ---
