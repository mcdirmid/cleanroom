# === File: lru_cache_impl_pretense.py ===
from __future__ import annotations

from typing import Any, List, Optional, Tuple
import unittest

from pretense import sut
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, LifecycleTestCase, enter_phase, system
from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)
from lru_cache.lib.lru_cache_impl import LRUCache as LRUCacheImpl
from lru_cache.pretense.lru_cache_pretense import LRUCacheStateMachine


class LRUCacheImplPseudoStateMachine(LRUCacheStateMachine):
    """Implementation pseudo-state machine for LRUCache."""

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


proto = LRUCacheImplPseudoStateMachine()


def make_sut() -> LRUCache:
    registry = LifecycleRegistry()
    registry.register_singleton(LRUCacheImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return scope.get_singleton(LRUCache)


LRUCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="LRUCacheFuzzTest",
)


class TestLRUCacheImplReal(LifecycleTestCase):
    """Verifies that concrete library implementation satisfies contracts."""

    target = LRUCacheImpl

    def setUp(self) -> None:
        super().setUp()
        self.real = self.sut
        self.sm = LRUCacheImplPseudoStateMachine(singletons={LRUCache: self.real})
        self.checked = self.sm.as_checked(LRUCache, self.real)

    def test_basic_put_and_get(self) -> None:
        _ = self.checked.is_empty
        self.checked.put("k1", "v1")
        self.checked.put("k2", "v2")
        self.checked.get("k1", None)
        self.checked.get("missing", "default")
        self.checked.peek("k1", None)
        self.checked.peek("missing", "default")
        _ = self.checked.capacity
        _ = self.checked.size
        _ = self.checked.is_empty
        _ = self.checked.is_full

    def test_put_update_existing(self) -> None:
        self.checked.put("k1", "v1")
        self.checked.put("k1", "v1_updated")

    def test_eviction_on_capacity(self) -> None:
        self.checked.configure(2)
        self.checked.put("k1", "v1")
        self.checked.put("k2", "v2")
        _ = self.checked.is_full
        self.checked.put("k3", "v3")
        self.checked.keys_in_lru_order()

    def test_configure_downsize_eviction(self) -> None:
        self.checked.configure(5)
        self.checked.put("k1", "v1")
        self.checked.put("k2", "v2")
        self.checked.put("k3", "v3")
        self.checked.configure(1)
        self.checked.keys_in_lru_order()

    def test_remove_existing_key(self) -> None:
        self.checked.put("k1", "v1")
        self.checked.put("k2", "v2")
        self.checked.remove("k1")
        self.checked.keys_in_lru_order()

    def test_clear_and_stats(self) -> None:
        self.checked.put("k1", "v1")
        self.checked.get("k1", None)
        self.checked.get("missing", None)
        self.checked.get_stats()
        self.checked.reset_stats()
        self.checked.get_stats()
        self.checked.clear()
        _ = self.checked.is_empty

    def test_violating_configure_zero(self) -> None:
        self.checked.violating(CacheCapacityError).configure(0)

    def test_violating_configure_negative(self) -> None:
        self.checked.violating(CacheCapacityError).configure(-10)

    def test_violating_remove_missing(self) -> None:
        self.checked.violating(CacheKeyNotFoundError).remove("absent_key")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T04:38:32Z
# LAST_CHANGED: 2026-11-12T04:37:29Z
# CHANGE: Implement LRUCacheImplPseudoStateMachine with inner transitions, fuzz testing, and TestLRUCacheImplReal scenario tests
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T04:38:32Z
# PRETENSE_QA_AUDIT: 2026-11-12T04:38:02Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
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
from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)


@dataclass
class LRUCacheState:
    """Canonical model state for LRUCache."""
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
        return 100

    def make_initial_state(self) -> LRUCacheState:
        return LRUCacheState(capacity=self.default_capacity)

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed initial state machine state for fake initialization."""
        self.state.items.clear()
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
        ret = self.inner_configure(capacity)
        self.state.capacity = capacity
        if len(self.state.items) > capacity:
            excess = len(self.state.items) - capacity
            for _ in range(excess):
                oldest_key = next(iter(self.state.items))
                del self.state.items[oldest_key]
                self.state.evictions += 1
        assert self.state.capacity == capacity
        assert len(self.state.items) <= capacity
        return ret

    def inner_configure(self, capacity: int) -> None:
        pass

    @transition(LRUCache.get)
    def get(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, Domain.type(str), preferred=["k1", "k2", "k3"])
        require_arg(default, Domain.any(), preferred=[None, "default", 0])
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
        require_arg(key, Domain.type(str), preferred=["k1", "k2", "k3"])
        require_arg(value, Domain.any(), preferred=["v1", "v2", 1, 2])
        ret = self.inner_put(key, value)
        if key in self.state.items:
            self.state.items.pop(key)
            self.state.items[key] = value
            assert ret is None
        elif len(self.state.items) >= self.state.capacity:
            oldest_key = next(iter(self.state.items))
            oldest_val = self.state.items.pop(oldest_key)
            self.state.evictions += 1
            self.state.items[key] = value
            assert ret == (oldest_key, oldest_val)
        else:
            self.state.items[key] = value
            assert ret is None
        return ret

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        if key in self.state.items:
            return None
        elif len(self.state.items) >= self.state.capacity:
            oldest_key = next(iter(self.state.items))
            return (oldest_key, self.state.items[oldest_key])
        else:
            return None

    @transition(LRUCache.peek)
    def peek(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, Domain.type(str), preferred=["k1", "k2", "k3"])
        require_arg(default, Domain.any(), preferred=[None, "default", 0])
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
        require(bool(self.state.items))
        require_arg(key, Domain.in_set(set(self.state.items.keys())), preferred=["k1", "k2"])
        ret = self.inner_remove(key)
        val = self.state.items.pop(key)
        assert ret == val
        return ret

    def inner_remove(self, key: str) -> Any:
        return self.state.items[key]

    @transition(LRUCache.clear)
    def clear(self) -> None:
        ret = self.inner_clear()
        self.state.items.clear()
        assert len(self.state.items) == 0
        return ret

    def inner_clear(self) -> None:
        pass

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
        return ret

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
        self.sm.seed_initial()
        self.fake.configure(2)
        self.fake.put("k1", "v1")
        self.fake.put("k2", "v2")
        self.fake.put("k1", "v1_updated")
        self.fake.put("k3", "v3")
        self.fake.configure(1)
        self.fake.get("k3", None)
        self.fake.get("missing", "default")
        self.fake.peek("k3", None)
        self.fake.peek("missing", "default")
        self.fake.keys_in_lru_order()
        self.fake.get_stats()
        self.fake.reset_stats()
        self.fake.remove("k3")
        self.fake.clear()
        _ = self.fake.capacity
        _ = self.fake.size
        _ = self.fake.is_empty
        _ = self.fake.is_full

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T04:37:22Z
# LAST_CHANGED: 2026-11-12T04:37:22Z
# CHANGE: Implement LRUCacheState, LRUCacheStateMachine with 1:1 transitions, fake synthesis, and fake test suite
# --- END AUTOFAB METADATA ---
