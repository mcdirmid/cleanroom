# === File: lru_cache_impl_pretense.py ===
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from pretense import StateMachine, require, sut
from pretense.compiler import compile_hypothesis_test_case

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from lru_cache_deepseek_flash_1.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)
from lru_cache_deepseek_flash_1.parts.lru_cache.lib.lru_cache_impl import (
    LRUCache as LRUCacheImpl,
)
from lru_cache_deepseek_flash_1.parts.lru_cache.pretense.lru_cache_pretense import (
    LRUCacheStateMachine,
)

# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class LRUCacheImplPseudoStateMachine(LRUCacheStateMachine):
    """Implementation pseudo-state machine binding concrete LRUCache SUT calls.

    Inherits every interface transition, including argument domains, model state
    mutations, and postcondition assertions, and overrides only the inner hooks
    that supply concrete SUT behavior.
    """

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
# 2. SUT Factory and Hypothesis Stateful Fuzzing (Implementation Components)
# ==============================================================================

def make_sut() -> LRUCache:
    """Constructs a concrete LRUCache singleton within a scoped lifecycle registry."""
    registry = LifecycleRegistry()
    registry.register_singleton(LRUCacheImpl, keys=[LRUCacheImpl, LRUCache])
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(LRUCache)


proto = LRUCacheImplPseudoStateMachine()

LRUCacheFuzzTest = compile_hypothesis_test_case(
    proto=LRUCacheImplPseudoStateMachine,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="LRUCacheFuzzTest",
)


# ==============================================================================
# 3. Real Implementation Scenarios (Implementation Components)
# ==============================================================================

class TestLRUCacheImplReal(LifecycleTestCase):
    """Fixed scenarios covering uncovered postconditions and precondition errors."""

    target = LRUCacheImpl

    def setUp(self) -> None:
        super().setUp()
        self.real = self.sut
        self.sm = LRUCacheImplPseudoStateMachine(singletons={LRUCache: self.real})
        self.checked = self.sm.as_checked(LRUCache, self.real)

    def test_configure_downsize_eviction(self) -> None:
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        self.checked.put("gamma", 3)
        self.checked.configure(1)
        self.checked.keys_in_lru_order()

    def test_put_evict_on_capacity(self) -> None:
        self.checked.configure(2)
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        self.checked.put("gamma", 3)

    def test_configure_invalid_capacity(self) -> None:
        self.checked.violating(CacheCapacityError).configure(0)

    def test_remove_existing_key(self) -> None:
        self.checked.put("alpha", 1)
        self.checked.put("beta", 2)
        self.checked.remove("alpha")
        self.checked.keys_in_lru_order()

    def test_remove_missing_key(self) -> None:
        self.checked.put("alpha", 1)
        self.checked.violating(CacheKeyNotFoundError).remove("missing")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:42:26Z
# LAST_CHANGED: 2026-11-14T20:41:50Z
# CHANGE: Add test_remove_existing_key scenario to TestLRUCacheImplReal: populate two entries, remove an existing key, and verify the returned prior value plus recency order, covering the lru_cache.remove.existing_key postcondition (entry purge and value return) cited by pretense_coverage.
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T20:42:26Z
# PRETENSE_QA_AUDIT: 2026-11-14T20:42:03Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple
import unittest

from pretense import (
    StateMachine,
    require,
    require_arg,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from lru_cache_deepseek_flash_1.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions - Interface Components)
# ==============================================================================

@dataclass
class LRUCacheState:
    """Canonical model state for a bounded least-recently-used cache.

    Attributes:
        capacity: Maximum number of entries permitted in the cache.
        items: Mapping from active cache key to associated value.
        order: Active cache keys ordered from least- to most-recently-used.
        hits: Cumulative successful lookup counter.
        misses: Cumulative failed lookup counter.
        evictions: Cumulative capacity-driven eviction counter.
    """
    capacity: int = 100
    items: dict[str, Any] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class LRUCacheStateMachine(StateMachine[LRUCacheState]):
    """Unified Pretense state machine modeling LRUCache interface transitions."""

    def __init__(
        self,
        state: Optional[LRUCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> LRUCacheState:
        """Constructs the blank initial cache model state."""
        return LRUCacheState(capacity=100)

    # ------------------------------------------------------------------
    # Observability properties
    # ------------------------------------------------------------------

    @transition(name="capacity")
    def capacity(self) -> int:
        """Models the maximum configured capacity limit."""
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    def inner_capacity(self) -> int:
        return self.state.capacity

    @transition(name="size")
    def size(self) -> int:
        """Models the current count of active entries."""
        ret = self.inner_size()
        assert ret == len(self.state.order)
        assert ret == len(self.state.items)
        return ret

    def inner_size(self) -> int:
        return len(self.state.order)

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        """Models whether the cache holds zero entries."""
        ret = self.inner_is_empty()
        assert ret == (len(self.state.order) == 0)
        return ret

    def inner_is_empty(self) -> bool:
        return len(self.state.order) == 0

    @transition(name="is_full")
    def is_full(self) -> bool:
        """Models whether the cache has reached its capacity limit."""
        ret = self.inner_is_full()
        assert ret == (len(self.state.order) >= self.state.capacity)
        return ret

    def inner_is_full(self) -> bool:
        return len(self.state.order) >= self.state.capacity

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    @domain(valid=lambda self: [1, 2, 5], invalid=lambda self: [0, -1])
    def _is_positive_capacity(self, value: int) -> bool:
        """Recognizes valid capacity arguments (strictly positive integers)."""
        return value > 0

    @transition(LRUCache.configure)
    def configure(self, capacity: int) -> None:
        """Reconfigures capacity, evicting least-recently-used entries when downsizing."""
        require_arg(
            capacity,
            self._is_positive_capacity,
        )
        ret = self.inner_configure(capacity)
        self.state.capacity = capacity
        excess = max(len(self.state.order) - capacity, 0)
        evicted = self.state.order[:excess]
        self.state.order = self.state.order[excess:]
        self.state.items = {
            key: value for key, value in self.state.items.items() if key not in evicted
        }
        self.state.evictions += excess
        assert ret is None
        assert len(self.state.order) <= self.state.capacity
        assert len(self.state.items) == len(self.state.order)
        return ret

    def inner_configure(self, capacity: int) -> None:
        return None

    @transition(LRUCache.get)
    def get(self, key: str, default: Optional[Any]) -> Any:
        """Models a lookup that promotes a hit to most-recently-used."""
        require_arg(key, str, preferred=["alpha", "beta", "gamma"])
        require_arg(default, object, preferred=[None, "missing"])
        ret = self.inner_get(key, default)
        if key in self.state.items:
            value = self.state.items[key]
            self.state.hits += 1
            self.state.order.remove(key)
            self.state.order.append(key)
            assert ret == value
            assert self.state.order[-1] == key
        else:
            self.state.misses += 1
            assert ret == default
        return ret

    def inner_get(self, key: str, default: Optional[Any]) -> Any:
        if key in self.state.items:
            return self.state.items[key]
        return default

    @transition(LRUCache.put)
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        """Models insertion or update, evicting the LRU entry when at capacity."""
        require_arg(key, str, preferred=["alpha", "beta", "gamma"])
        require_arg(value, object, preferred=[1, "payload"])
        ret = self.inner_put(key, value)
        if key in self.state.items:
            self.state.items[key] = value
            self.state.order.remove(key)
            self.state.order.append(key)
            assert ret is None
            assert self.state.order[-1] == key
        elif len(self.state.order) >= self.state.capacity:
            evicted_key = self.state.order[0]
            evicted_value = self.state.items.pop(evicted_key)
            self.state.order = self.state.order[1:]
            self.state.evictions += 1
            self.state.items[key] = value
            self.state.order.append(key)
            assert ret == (evicted_key, evicted_value)
        else:
            self.state.items[key] = value
            self.state.order.append(key)
            assert ret is None
        assert len(self.state.order) == len(self.state.items)
        assert len(self.state.order) <= self.state.capacity
        return ret

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        if key in self.state.items:
            return None
        if len(self.state.order) >= self.state.capacity:
            evicted_key = self.state.order[0]
            return (evicted_key, self.state.items[evicted_key])
        return None

    @transition(LRUCache.peek)
    def peek(self, key: str, default: Optional[Any]) -> Any:
        """Models a non-mutating lookup preserving recency and telemetry."""
        require_arg(key, str, preferred=["alpha", "beta", "gamma"])
        require_arg(default, object, preferred=[None, "missing"])
        order_before = list(self.state.order)
        ret = self.inner_peek(key, default)
        if key in self.state.items:
            assert ret == self.state.items[key]
        else:
            assert ret == default
        assert self.state.order == order_before
        return ret

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        if key in self.state.items:
            return self.state.items[key]
        return default

    @transition(LRUCache.remove)
    def remove(self, key: str) -> Any:
        """Models removal of an existing key."""
        require(bool(self.state.order))
        require_arg(key, self.state.items, preferred=["alpha", "beta", "gamma"])
        ret = self.inner_remove(key)
        removed = self.state.items.pop(key)
        self.state.order.remove(key)
        assert ret == removed
        assert len(self.state.order) == len(self.state.items)
        return ret

    def inner_remove(self, key: str) -> Any:
        return self.state.items[key]

    @transition(LRUCache.clear)
    def clear(self) -> None:
        """Models removal of all entries while preserving telemetry counters."""
        ret = self.inner_clear()
        self.state.items = {}
        self.state.order = []
        assert ret is None
        assert len(self.state.order) == 0
        assert len(self.state.items) == 0
        return ret

    def inner_clear(self) -> None:
        return None

    @transition(LRUCache.get_stats)
    def get_stats(self) -> CacheStats:
        """Models telemetry reporting."""
        ret = self.inner_get_stats()
        assert ret.hits == self.state.hits
        assert ret.misses == self.state.misses
        assert ret.evictions == self.state.evictions
        return ret

    def inner_get_stats(self) -> CacheStats:
        return CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        )

    @transition(LRUCache.reset_stats)
    def reset_stats(self) -> None:
        """Models telemetry counter resetting without altering entries."""
        ret = self.inner_reset_stats()
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        assert ret is None
        assert self.state.hits == 0
        assert self.state.misses == 0
        assert self.state.evictions == 0
        return ret

    def inner_reset_stats(self) -> None:
        return None

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(self) -> List[str]:
        """Models non-mutating recency-ordered key enumeration."""
        order_before = list(self.state.order)
        ret = self.inner_keys_in_lru_order()
        assert ret == order_before
        assert self.state.order == order_before
        return ret

    def inner_keys_in_lru_order(self) -> List[str]:
        return list(self.state.order)

    # ------------------------------------------------------------------
    # Seeding transitions
    # ------------------------------------------------------------------

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds a minimal configured cache with a single entry."""
        self.state.capacity = 100
        self.state.items = {"alpha": 1}
        self.state.order = ["alpha"]
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0

    @transition.seeding
    def seed_full(self) -> None:
        """Seeds a small cache at capacity with recorded telemetry."""
        self.state.capacity = 2
        self.state.items = {"alpha": 1, "beta": 2}
        self.state.order = ["alpha", "beta"]
        self.state.hits = 1
        self.state.misses = 1
        self.state.evictions = 0


proto = LRUCacheStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeLRUCache = synthesize_fake(LRUCacheStateMachine)


def make_lru_cache_fake(state: Optional[LRUCacheState] = None) -> LRUCache:
    """Synthesizes a fake LRUCache backed by the interface state machine."""
    return FakeLRUCache(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Fake Fuzzing (Interface Components)
# ==============================================================================

FakeLRUCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeLRUCacheFuzzTest",
)


# ==============================================================================
# 4. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestLRUCacheFake(unittest.TestCase):
    """Fixed fake scenarios covering downsize eviction and telemetry retention."""

    def setUp(self) -> None:
        self.fake = make_lru_cache_fake()

    def test_downsize_eviction(self) -> None:
        self.fake.put("alpha", 1)
        self.fake.put("beta", 2)
        self.fake.configure(1)
        self.assertEqual(self.fake.keys_in_lru_order(), ["beta"])
        self.assertEqual(self.fake.size, 1)
        self.assertEqual(self.fake.get_stats().evictions, 1)

    def test_clear_preserves_telemetry(self) -> None:
        self.fake.put("alpha", 1)
        self.fake.get("alpha", None)
        self.fake.get("beta", None)
        self.fake.clear()
        self.assertEqual(self.fake.size, 0)
        self.assertTrue(self.fake.is_empty)
        self.assertEqual(self.fake.get_stats().hits, 1)
        self.assertEqual(self.fake.get_stats().misses, 1)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:37:25Z
# LAST_CHANGED: 2026-11-14T20:37:25Z
# CHANGE: Implement LRUCache interface pretense state machine: capacity/size/is_empty/is_full properties, configure with downsize eviction, get/put/peek/remove/clear/get_stats/reset_stats/keys_in_lru_order transitions, seeding transitions, synthesized fake, fake fuzz test, and fixed fake scenarios covering downsize eviction and telemetry retention.
# --- END AUTOFAB METADATA ---
