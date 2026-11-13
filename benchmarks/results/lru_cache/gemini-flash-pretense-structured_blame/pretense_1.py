# === File: lru_cache_impl_pretense.py ===
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTestCase,
    enter_phase,
    get_singleton,
    system,
)

from lru_cache_gemini_flash_2.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)
from lru_cache_gemini_flash_2.parts.lru_cache.lib.lru_cache_impl import (
    LRUCache as LRUCacheImpl,
)
from lru_cache_gemini_flash_2.parts.lru_cache.pretense.lru_cache_pretense import (
    LRUCacheStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class LRUCacheImplPseudoStateMachine(LRUCacheStateMachine):
    """Implementation pseudo-state machine for LRUCache binding concrete SUT calls."""

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
        return target.configure(capacity)

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
        return target.clear()

    def inner_get_stats(self) -> CacheStats:
        target: LRUCache = sut(LRUCache)
        return target.get_stats()

    def inner_reset_stats(self) -> None:
        target: LRUCache = sut(LRUCache)
        return target.reset_stats()

    def inner_keys_in_lru_order(self) -> List[str]:
        target: LRUCache = sut(LRUCache)
        return target.keys_in_lru_order()


# ==============================================================================
# 2. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestLRUCacheImplReal(LifecycleTestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    def setUp(self) -> None:
        super().setUp()
        self.real: LRUCache = self.sut
        self.sm = LRUCacheImplPseudoStateMachine(singletons={LRUCache: self.real})
        self.checked = self.sm.as_checked(LRUCache, self.real)

    def test_initial_properties(self) -> None:
        _ = self.checked.capacity
        _ = self.checked.size
        _ = self.checked.is_empty
        _ = self.checked.is_full
        _ = self.checked.keys_in_lru_order()
        _ = self.checked.get_stats()

    def test_put_and_get_hit(self) -> None:
        self.checked.put("k1", "v1")
        _ = self.checked.size
        _ = self.checked.is_empty
        self.checked.get("k1", None)
        _ = self.checked.get_stats()

    def test_get_miss(self) -> None:
        self.checked.get("missing", "default_val")
        _ = self.checked.get_stats()

    def test_put_update_existing_key(self) -> None:
        self.checked.put("k1", "v1")
        self.checked.put("k1", "v1_updated")
        self.checked.get("k1", None)

    def test_peek_present_and_absent(self) -> None:
        self.checked.put("k1", "v1")
        self.checked.peek("k1", None)
        self.checked.peek("missing", "default_val")

    def test_remove_success(self) -> None:
        self.checked.put("k1", "v1")
        self.checked.remove("k1")
        _ = self.checked.size
        _ = self.checked.is_empty

    def test_clear(self) -> None:
        self.checked.put("k1", "v1")
        self.checked.put("k2", "v2")
        self.checked.clear()
        _ = self.checked.size
        _ = self.checked.is_empty

    def test_reset_stats(self) -> None:
        self.checked.put("k1", "v1")
        self.checked.get("k1", None)
        self.checked.get("missing", None)
        self.checked.reset_stats()
        _ = self.checked.get_stats()

    def test_put_eviction_when_capacity_reached(self) -> None:
        self.checked.configure(2)
        self.checked.put("k1", "v1")
        self.checked.put("k2", "v2")
        _ = self.checked.is_full
        self.checked.put("k3", "v3")
        _ = self.checked.keys_in_lru_order()
        _ = self.checked.get_stats()

    def test_configure_downsize_eviction(self) -> None:
        self.checked.configure(5)
        self.checked.put("k1", "v1")
        self.checked.put("k2", "v2")
        self.checked.put("k3", "v3")
        self.checked.configure(2)
        _ = self.checked.size
        _ = self.checked.capacity
        _ = self.checked.keys_in_lru_order()
        _ = self.checked.get_stats()

    def test_access_order_lru_promotion(self) -> None:
        self.checked.configure(3)
        self.checked.put("k1", "v1")
        self.checked.put("k2", "v2")
        self.checked.put("k3", "v3")
        self.checked.get("k1", None)
        self.checked.put("k4", "v4")
        _ = self.checked.keys_in_lru_order()

    def test_configure_invalid_capacity_zero(self) -> None:
        self.checked.violating(CacheCapacityError).configure(0)

    def test_configure_invalid_capacity_negative(self) -> None:
        self.checked.violating(CacheCapacityError).configure(-5)

    def test_remove_missing_key_empty(self) -> None:
        self.checked.violating(CacheKeyNotFoundError).remove("missing_key")

    def test_remove_missing_key_non_empty(self) -> None:
        self.checked.put("k1", "v1")
        self.checked.violating(CacheKeyNotFoundError).remove("absent_key")


# ==============================================================================
# 3. Hypothesis Stateful Fuzzing on Real Implementation (Implementation Components)
# ==============================================================================

def make_sut() -> LRUCache:
    registry = LifecycleRegistry()
    registry.register_singleton(LRUCacheImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(LRUCacheImpl)


proto = LRUCacheImplPseudoStateMachine()

LRUCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="LRUCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T04:19:44Z
# LAST_CHANGED: 2026-11-13T04:18:12Z
# CHANGE: Initial implementation of LRUCacheImpl pseudo state machine, real scenario tests, and fuzzing
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T04:19:44Z
# PRETENSE_QA_AUDIT: 2026-11-13T04:19:05Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple
import unittest

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from lru_cache_gemini_flash_2.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)


# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class LRUCacheState:
    """Canonical model state tracking LRU cache entries, capacity, and telemetry."""
    capacity: int = 100
    items: dict[str, Any] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class LRUCacheStateMachine(StateMachine[LRUCacheState]):
    """Unified Pretense State Machine for LRUCache."""

    def __init__(
        self,
        state: Optional[LRUCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    @property
    def default_capacity(self) -> int:
        """Default initial cache capacity."""
        return 100

    def make_initial_state(self) -> LRUCacheState:
        """Constructs initial model state. Open parameters may be specialized by pseudo-state machines."""
        return LRUCacheState(capacity=self.default_capacity)

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.items["seed_k1"] = "seed_v1"
        self.state.items["seed_k2"] = "seed_v2"

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
        require_arg(
            capacity,
            Domain.integers(min_value=1),
            error=CacheCapacityError,
            preferred=[1, 5, 10, 100],
            fuzz_domain=Domain.integers(min_value=1, max_value=500),
        )
        ret = self.inner_configure(capacity)
        self.state.capacity = capacity
        if len(self.state.items) > capacity:
            excess = len(self.state.items) - capacity
            keys_to_evict = list(self.state.items.keys())[:excess]
            for k in keys_to_evict:
                del self.state.items[k]
                self.state.evictions += 1
        assert ret is None
        assert self.state.capacity == capacity
        assert len(self.state.items) <= capacity

    def inner_configure(self, capacity: int) -> None:
        return None

    @transition(LRUCache.get)
    def get(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, Domain.text(min_size=1), preferred=["k1", "k2", "seed_k1"])
        require_arg(default, Domain.optional(Domain.text()), preferred=[None, "missing"])
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
        require_arg(key, Domain.text(min_size=1), preferred=["k1", "k2", "k3"])
        require_arg(value, Domain.text(), preferred=["v1", "v2", "v3"])
        ret = self.inner_put(key, value)
        if key in self.state.items:
            del self.state.items[key]
            self.state.items[key] = value
            assert ret is None
        elif len(self.state.items) >= self.state.capacity:
            evicted_k = next(iter(self.state.items))
            evicted_v = self.state.items.pop(evicted_k)
            self.state.evictions += 1
            self.state.items[key] = value
            assert ret == (evicted_k, evicted_v)
        else:
            self.state.items[key] = value
            assert ret is None
        return ret

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        if key in self.state.items:
            return None
        if len(self.state.items) >= self.state.capacity:
            evicted_key = next(iter(self.state.items))
            evicted_val = self.state.items.get(evicted_key)
            return (evicted_key, evicted_val)
        return None

    @transition(LRUCache.peek)
    def peek(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, Domain.text(min_size=1), preferred=["k1", "k2", "seed_k1"])
        require_arg(default, Domain.optional(Domain.text()), preferred=[None, "missing"])
        ret = self.inner_peek(key, default)
        if key in self.state.items:
            assert ret == self.state.items[key]
        else:
            assert ret == default
        return ret

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        return self.state.items.get(key, default)

    @transition(LRUCache.remove)
    def remove(self, key: str) -> Any:
        require(bool(self.state.items), error=CacheKeyNotFoundError)
        require_arg(key, Domain.in_set(self.state.items), error=CacheKeyNotFoundError)
        ret = self.inner_remove(key)
        val = self.state.items.pop(key)
        assert ret == val
        return ret

    def inner_remove(self, key: str) -> Any:
        return self.state.items.get(key)

    @transition(LRUCache.clear)
    def clear(self) -> None:
        ret = self.inner_clear()
        self.state.items.clear()
        assert ret is None
        assert len(self.state.items) == 0

    def inner_clear(self) -> None:
        return None

    @transition(LRUCache.get_stats)
    def get_stats(self) -> CacheStats:
        ret = self.inner_get_stats()
        expected = CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        )
        assert ret == expected
        return ret

    def inner_get_stats(self) -> CacheStats:
        return CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        )

    @transition(LRUCache.reset_stats)
    def reset_stats(self) -> None:
        ret = self.inner_reset_stats()
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        assert ret is None
        assert self.state.hits == 0
        assert self.state.misses == 0
        assert self.state.evictions == 0

    def inner_reset_stats(self) -> None:
        return None

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(self) -> List[str]:
        ret = self.inner_keys_in_lru_order()
        assert ret == list(self.state.items.keys())
        return ret

    def inner_keys_in_lru_order(self) -> List[str]:
        return list(self.state.items.keys())


proto = LRUCacheStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeLRUCache = synthesize_fake(LRUCacheStateMachine)


def make_lru_cache_fake(state: Optional[LRUCacheState] = None) -> LRUCache:
    """Synthesizes fake instance for LRUCache."""
    return FakeLRUCache(state=state or LRUCacheState())


FakeLRUCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeLRUCacheFuzzTest",
)


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestLRUCacheFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_lru_cache_fake()
        self.sm = LRUCacheStateMachine(singletons={LRUCache: self.fake})

    def test_transitions_coverage(self) -> None:
        """Exercises 100% of transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        self.fake.configure(10)
        self.assertEqual(self.fake.capacity, 10)
        self.assertEqual(self.fake.size, 0)
        self.assertTrue(self.fake.is_empty)
        self.assertFalse(self.fake.is_full)
        res_put = self.fake.put("k1", "v1")
        self.assertIsNone(res_put)
        self.assertEqual(self.fake.size, 1)
        self.assertFalse(self.fake.is_empty)
        # Update existing key
        self.fake.put("k1", "v1_updated")
        res_get = self.fake.get("k1", None)
        self.assertEqual(res_get, "v1_updated")
        res_miss = self.fake.get("missing", "def")
        self.assertEqual(res_miss, "def")
        res_peek = self.fake.peek("k1", None)
        self.assertEqual(res_peek, "v1_updated")
        res_peek_miss = self.fake.peek("missing", "def")
        self.assertEqual(res_peek_miss, "def")
        res_keys = self.fake.keys_in_lru_order()
        self.assertIn("k1", res_keys)
        res_stats = self.fake.get_stats()
        self.assertEqual(res_stats.hits, 1)
        self.assertEqual(res_stats.misses, 1)
        self.fake.reset_stats()
        self.assertEqual(self.fake.get_stats().hits, 0)
        res_remove = self.fake.remove("k1")
        self.assertEqual(res_remove, "v1_updated")
        self.fake.clear()
        self.assertEqual(self.fake.size, 0)
        self.assertTrue(self.fake.is_empty)

    def test_put_eviction(self) -> None:
        """Exercises put eviction when capacity is reached."""
        self.fake.configure(2)
        self.fake.put("k1", "v1")
        self.fake.put("k2", "v2")
        self.assertTrue(self.fake.is_full)
        evicted = self.fake.put("k3", "v3")
        self.assertEqual(evicted, ("k1", "v1"))
        self.assertEqual(self.fake.size, 2)
        self.assertEqual(self.fake.get_stats().evictions, 1)

    def test_configure_downsize(self) -> None:
        """Exercises downsize eviction via configure."""
        self.fake.configure(10)
        self.fake.put("k1", "v1")
        self.fake.put("k2", "v2")
        self.fake.put("k3", "v3")
        self.fake.configure(2)
        self.assertEqual(self.fake.size, 2)
        self.assertEqual(self.fake.get_stats().evictions, 1)
        self.assertEqual(self.fake.keys_in_lru_order(), ["k2", "k3"])

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T04:17:17Z
# LAST_CHANGED: 2026-11-13T04:17:17Z
# CHANGE: Add CacheKeyNotFoundError error specification to remove require guard
# --- END AUTOFAB METADATA ---
