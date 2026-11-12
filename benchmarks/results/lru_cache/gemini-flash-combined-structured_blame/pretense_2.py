# === File: lru_cache_impl_pretense.py ===
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from pretense import sut, sut_state
from support.lib.lifecycle import LifecycleTestCase

from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)
from lru_cache.lib.lru_cache_impl import LRUCache as LRUCacheImpl
from lru_cache.pretense.lru_cache_pretense import LRUCacheState, LRUCacheStateMachine, proto


# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class LRUCacheImplPseudoStateMachine(LRUCacheStateMachine):
    """Implementation pseudo-state machine for LRUCache measuring differentials and SUT state."""

    def inner_capacity(self) -> int:
        target: LRUCache = sut(LRUCache)
        return target.capacity

    def inner_size(self) -> int:
        target: LRUCache = sut(LRUCache)
        return target.size

    def inner_is_empty(self) -> bool:
        target: LRUCache = sut(LRUCache)
        return target.is_empty

    def inner_is_full(self) -> bool:
        target: LRUCache = sut(LRUCache)
        return target.is_full

    def inner_configure(self, capacity: int) -> None:
        target: LRUCache = sut(LRUCache)
        target.configure(capacity)

    def inner_get(self, key: str, default: Optional[Any]) -> Any:
        target: LRUCache = sut(LRUCache)
        return target.get(key, default)

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        target: LRUCache = sut(LRUCache)
        return target.put(key, value)

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        target: LRUCache = sut(LRUCache)
        return target.peek(key, default)

    def inner_remove(self, key: str) -> Any:
        target: LRUCache = sut(LRUCache)
        return target.remove(key)

    def inner_clear(self) -> None:
        target: LRUCache = sut(LRUCache)
        target.clear()

    def inner_get_stats(self) -> CacheStats:
        target: LRUCache = sut(LRUCache)
        return target.get_stats()

    def inner_reset_stats(self) -> None:
        target: LRUCache = sut(LRUCache)
        target.reset_stats()

    def inner_keys_in_lru_order(self) -> List[str]:
        target: LRUCache = sut(LRUCache)
        return target.keys_in_lru_order()


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestLRUCacheImplReal(LifecycleTestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        super().setUp()
        self.real: LRUCache = self.sut
        self.sm = LRUCacheImplPseudoStateMachine(singletons={LRUCache: self.real})
        self.checked = self.sm.as_checked(LRUCache, self.real)

    def test_lifecycle_and_basic_caching(self) -> None:
        """Verifies basic cache insertions, lookups, peeks, and telemetry."""
        _ = self.checked.is_empty
        _ = self.checked.capacity
        _ = self.checked.size
        self.checked.configure(3)
        _ = self.checked.put("k1", "v1")
        _ = self.checked.is_empty
        _ = self.checked.put("k2", "v2")
        _ = self.checked.peek("k1", None)
        _ = self.checked.peek("k5", "default_val")
        _ = self.checked.get("k1", None)
        _ = self.checked.get("k5", "default_val")
        _ = self.checked.put("k1", "v1_updated")
        _ = self.checked.put("k3", "v3")
        _ = self.checked.is_full
        _ = self.checked.put("k4", "v4")
        _ = self.checked.keys_in_lru_order()
        _ = self.checked.get_stats()
        self.checked.reset_stats()
        _ = self.checked.remove("k1")
        self.checked.clear()

    def test_configure_downsize_eviction(self) -> None:
        """Verifies downsizing cache capacity evicts least-recently-used entries."""
        self.checked.configure(5)
        _ = self.checked.put("k1", "v1")
        _ = self.checked.put("k2", "v2")
        _ = self.checked.put("k3", "v3")
        self.checked.configure(1)
        _ = self.checked.size
        _ = self.checked.keys_in_lru_order()

    def test_configure_invalid_capacity_zero(self) -> None:
        """Verifies configuring capacity to zero raises CacheCapacityError."""
        self.checked.violating(CacheCapacityError).configure(0)

    def test_configure_invalid_capacity_negative(self) -> None:
        """Verifies configuring capacity to negative value raises CacheCapacityError."""
        self.checked.violating(CacheCapacityError).configure(-5)

    def test_remove_missing_key_raises_error(self) -> None:
        """Verifies removing non-existent key raises CacheKeyNotFoundError."""
        self.checked.violating(CacheKeyNotFoundError).remove("missing_key")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T04:23:29Z
# LAST_CHANGED: 2026-11-12T04:21:53Z
# CHANGE: Use in-domain absent key 'k5' for peek and get cache miss assertions in TestLRUCacheImplReal
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T04:23:29Z
# PRETENSE_QA_AUDIT: 2026-11-12T04:23:03Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple
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

from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)


@dataclass
class LRUCacheState:
    """Canonical model state tracking capacity, items, and telemetry counters."""
    capacity: int = 100
    items: dict[str, Any] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def keys(self) -> set[str]:
        return set(self.items.keys())


class LRUCacheStateMachine(StateMachine[LRUCacheState]):
    """Unified Pretense State Machine for LRUCache."""

    def __init__(
        self,
        state: Optional[LRUCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> LRUCacheState:
        return LRUCacheState()

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.capacity = 100
        self.state.items["seed_k"] = "seed_v"
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0

    @transition(name="capacity")
    def capacity(self) -> int:
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    def inner_capacity(self) -> int:
        return self.state.capacity

    @transition(name="size")
    def size(self) -> int:
        ret = self.inner_size()
        assert ret == len(self.state.items)
        return ret

    def inner_size(self) -> int:
        return len(self.state.items)

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret = self.inner_is_empty()
        assert ret == (len(self.state.items) == 0)
        return ret

    def inner_is_empty(self) -> bool:
        return len(self.state.items) == 0

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret = self.inner_is_full()
        assert ret == (len(self.state.items) >= self.state.capacity)
        return ret

    def inner_is_full(self) -> bool:
        return len(self.state.items) >= self.state.capacity

    @transition(LRUCache.configure)
    def configure(self, capacity: int) -> None:
        require_arg(capacity, Domain.integers(1, 100), preferred=[1, 5, 10, 50, 100])
        self.inner_configure(capacity)
        self.state.capacity = capacity
        if len(self.state.items) > self.state.capacity:
            num_to_evict = len(self.state.items) - self.state.capacity
            for _ in range(num_to_evict):
                oldest_key = next(iter(self.state.items))
                del self.state.items[oldest_key]
                self.state.evictions += 1

    def inner_configure(self, capacity: int) -> None:
        pass

    @transition(LRUCache.get)
    def get(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, Domain.sampled_from(["k1", "k2", "k3", "k4", "k5", "seed_k"]), preferred=["k1", "seed_k"])
        require_arg(default, Domain.any(), preferred=[None, "default_val"])
        ret = self.inner_get(key, default)
        if key in self.state.items:
            val = self.state.items.pop(key)
            self.state.items[key] = val
            self.state.hits += 1
            assert ret == val
        else:
            self.state.misses += 1
            assert ret == default
        return ret

    def inner_get(self, key: str, default: Optional[Any]) -> Any:
        return self.state.items.get(key, default)

    @transition(LRUCache.put)
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        require_arg(key, Domain.sampled_from(["k1", "k2", "k3", "k4", "k5", "seed_k"]), preferred=["k1", "k2"])
        require_arg(value, Domain.any(), preferred=["v1", "v2", 42])
        ret = self.inner_put(key, value)
        if key in self.state.items:
            del self.state.items[key]
            self.state.items[key] = value
            assert ret is None
        elif len(self.state.items) >= self.state.capacity:
            oldest_key = next(iter(self.state.items))
            oldest_val = self.state.items.pop(oldest_key)
            self.state.items[key] = value
            self.state.evictions += 1
            assert ret == (oldest_key, oldest_val)
        else:
            self.state.items[key] = value
            assert ret is None
        return ret

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        if key in self.state.items:
            return None
        if len(self.state.items) >= self.state.capacity:
            oldest_key = next(iter(self.state.items))
            oldest_val = self.state.items[oldest_key]
            return (oldest_key, oldest_val)
        return None

    @transition(LRUCache.peek)
    def peek(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, Domain.sampled_from(["k1", "k2", "k3", "k4", "k5", "seed_k"]), preferred=["k1", "seed_k"])
        require_arg(default, Domain.any(), preferred=[None, "default_val"])
        ret = self.inner_peek(key, default)
        expected = self.state.items.get(key, default)
        assert ret == expected
        return ret

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        return self.state.items.get(key, default)

    @transition(LRUCache.remove)
    def remove(self, key: str) -> Any:
        require(bool(self.state.items))
        require_arg(key, Domain.in_set(self.state.keys))
        ret = self.inner_remove(key)
        val = self.state.items.pop(key)
        assert ret == val
        return ret

    def inner_remove(self, key: str) -> Any:
        return self.state.items[key]

    @transition(LRUCache.clear)
    def clear(self) -> None:
        self.inner_clear()
        self.state.items.clear()

    def inner_clear(self) -> None:
        pass

    @transition(LRUCache.get_stats)
    def get_stats(self) -> CacheStats:
        ret = self.inner_get_stats()
        expected = CacheStats(hits=self.state.hits, misses=self.state.misses, evictions=self.state.evictions)
        assert ret == expected
        return ret

    def inner_get_stats(self) -> CacheStats:
        return CacheStats(hits=self.state.hits, misses=self.state.misses, evictions=self.state.evictions)

    @transition(LRUCache.reset_stats)
    def reset_stats(self) -> None:
        self.inner_reset_stats()
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0

    def inner_reset_stats(self) -> None:
        pass

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(self) -> List[str]:
        ret = self.inner_keys_in_lru_order()
        assert ret == list(self.state.items.keys())
        return ret

    def inner_keys_in_lru_order(self) -> List[str]:
        return list(self.state.items.keys())


proto = LRUCacheStateMachine()
FakeLRUCache = synthesize_fake(LRUCacheStateMachine)


def make_lru_cache_fake(state: Optional[LRUCacheState] = None) -> LRUCache:
    """Synthesizes fake instance for LRUCache."""
    return FakeLRUCache(state=state or proto.make_initial_state())


FakeLRUCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeLRUCacheFuzzTest",
)


class TestLRUCacheFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_lru_cache_fake()
        self.sm = LRUCacheStateMachine(singletons={LRUCache: self.fake})

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        _ = self.fake.capacity
        _ = self.fake.size
        _ = self.fake.is_empty
        _ = self.fake.is_full
        self.fake.configure(2)
        _ = self.fake.put("k1", "v1")
        _ = self.fake.put("k2", "v2")
        _ = self.fake.put("k3", "v3")
        _ = self.fake.get("k3", None)
        _ = self.fake.peek("k3", None)
        _ = self.fake.remove("k3")
        _ = self.fake.keys_in_lru_order()
        _ = self.fake.get_stats()
        self.fake.reset_stats()
        self.fake.clear()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T04:14:43Z
# LAST_CHANGED: 2026-11-12T04:14:43Z
# CHANGE: Implement LRUCache state machine, fake synthesis, and fake tests
# --- END AUTOFAB METADATA ---
