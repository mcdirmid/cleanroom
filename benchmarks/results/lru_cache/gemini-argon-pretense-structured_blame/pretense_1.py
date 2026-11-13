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

from lru_cache_gemini_argon_1.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache as LRUCacheInterface,
)
from lru_cache_gemini_argon_1.parts.lru_cache.lib.lru_cache_impl import LRUCache
from lru_cache_gemini_argon_1.parts.lru_cache.pretense.lru_cache_pretense import (
    LRUCacheState,
    LRUCacheStateMachine,
)


class LRUCacheImplPseudoStateMachine(LRUCacheStateMachine):
    """Implementation pseudo-state machine for LRUCache binding concrete SUT."""

    default_capacity: int = 100

    def make_initial_state(self) -> LRUCacheState:
        return LRUCacheState(capacity=100)

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
    registry.register_singleton(LRUCache)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(LRUCache)


TestLRUCacheImplFuzz = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=proto.make_initial_state,
    name="TestLRUCacheImplFuzz",
)

LRUCacheImplFuzzTest = TestLRUCacheImplFuzz


class TestLRUCacheImplReal(LifecycleTestCase):
    """Verifies concrete LRUCache implementation operational and error contracts."""

    def setUp(self) -> None:
        super().setUp()
        real = get_singleton(LRUCache)
        self.sm = LRUCacheImplPseudoStateMachine(
            singletons={LRUCache: real, LRUCacheInterface: real}
        )
        self.checked = self.sm.as_checked(LRUCache, real)

    def test_put_get_peek_and_eviction(self) -> None:
        _ = self.checked.capacity
        _ = self.checked.size
        _ = self.checked.is_empty
        _ = self.checked.is_full
        self.checked.configure(2)
        self.checked.put("k1", 1)
        self.checked.put("k2", 2)
        _ = self.checked.is_full
        self.checked.put("k1", 10)
        self.checked.get("k1", None)
        self.checked.get("missing", "fallback")
        self.checked.peek("k2", None)
        self.checked.peek("missing", "fallback")
        self.checked.put("k3", 3)
        self.checked.keys_in_lru_order()
        self.checked.get_stats()

    def test_configure_downsize_remove_clear_and_reset_stats(self) -> None:
        self.checked.configure(4)
        self.checked.put("k1", 1)
        self.checked.put("k2", 2)
        self.checked.put("k3", 3)
        self.checked.put("k4", 4)
        self.checked.configure(2)
        self.checked.remove("k3")
        self.checked.clear()
        self.checked.reset_stats()
        self.checked.get_stats()

    def test_configure_zero_capacity_error(self) -> None:
        self.checked.violating(CacheCapacityError).configure(0)

    def test_configure_negative_capacity_error(self) -> None:
        self.checked.violating(CacheCapacityError).configure(-1)

    def test_remove_nonexistent_key_error(self) -> None:
        self.checked.violating(CacheKeyNotFoundError).remove("missing")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T21:53:09Z
# LAST_CHANGED: 2026-11-13T21:51:01Z
# CHANGE: Rename Hypothesis fuzz test class to TestLRUCacheImplFuzz and add comprehensive operational scenarios in TestLRUCacheImplReal covering put, get, peek, configure downsize eviction, remove, clear, get_stats, and reset_stats
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T21:53:09Z
# PRETENSE_QA_AUDIT: 2026-11-13T21:52:36Z
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

from lru_cache_gemini_argon_1.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)


@dataclass
class LRUCacheState:
    """Canonical model state tracking cache entries, recency order, and telemetry."""

    capacity: int = 3
    entries: dict[str, Any] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class LRUCacheStateMachine(StateMachine[LRUCacheState]):
    """Unified Pretense State Machine for LRUCache."""

    default_capacity: int = 3

    def __init__(
        self,
        state: Optional[LRUCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> LRUCacheState:
        """Constructs initial model state with open default capacity."""
        return LRUCacheState(capacity=self.default_capacity)

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
        assert ret == len(self.state.order)
        return ret

    def inner_size(self) -> int:
        return len(self.state.order)

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret = self.inner_is_empty()
        assert ret == (len(self.state.order) == 0)
        return ret

    def inner_is_empty(self) -> bool:
        return len(self.state.order) == 0

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret = self.inner_is_full()
        assert ret == (len(self.state.order) >= self.state.capacity)
        return ret

    def inner_is_full(self) -> bool:
        return len(self.state.order) >= self.state.capacity

    @transition(LRUCache.configure)
    def configure(self, capacity: int) -> None:
        require_arg(
            capacity,
            Domain.integers(min_value=1),
            error=CacheCapacityError,
            preferred=[1, 2, 3, 5],
            fuzz_domain=Domain.integers(min_value=1, max_value=5),
        )
        ret = self.inner_configure(capacity)
        self.state.capacity = capacity
        if len(self.state.order) > capacity:
            evict_count = len(self.state.order) - capacity
            evicted_keys = self.state.order[:evict_count]
            self.state.order = self.state.order[evict_count:]
            for k in evicted_keys:
                del self.state.entries[k]
            self.state.evictions += evict_count
        target: LRUCache = sut(LRUCache)
        assert target.capacity == self.state.capacity
        assert target.size == len(self.state.order)
        assert target.keys_in_lru_order() == self.state.order
        assert target.get_stats().evictions == self.state.evictions
        return ret

    def inner_configure(self, capacity: int) -> None:
        return None

    @transition(LRUCache.get)
    def get(self, key: str, default: Optional[Any]) -> Any:
        require_arg(
            key,
            Domain.text(min_size=1),
            preferred=["k1", "k2", "k3", "k4"],
            fuzz_domain=Domain.sampled_from(["k1", "k2", "k3", "k4"]),
        )
        require_arg(
            default,
            Domain.optional(Domain.type(object)),
            preferred=[None, 0, "default"],
            fuzz_domain=Domain.sampled_from([None, 0, "default"]),
        )
        ret = self.inner_get(key, default)
        if key in self.state.entries:
            expected = self.state.entries[key]
            self.state.order.remove(key)
            self.state.order.append(key)
            self.state.hits += 1
            assert ret == expected
        else:
            self.state.misses += 1
            assert ret == default
        target: LRUCache = sut(LRUCache)
        assert target.keys_in_lru_order() == self.state.order
        assert target.get_stats().hits == self.state.hits
        assert target.get_stats().misses == self.state.misses
        return ret

    def inner_get(self, key: str, default: Optional[Any]) -> Any:
        if key in self.state.entries:
            return self.state.entries[key]
        return default

    @transition(LRUCache.put)
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        require_arg(
            key,
            Domain.text(min_size=1),
            preferred=["k1", "k2", "k3", "k4"],
            fuzz_domain=Domain.sampled_from(["k1", "k2", "k3", "k4"]),
        )
        require_arg(
            value,
            Domain.optional(Domain.type(object)),
            preferred=[1, 2, "v1", "v2"],
            fuzz_domain=Domain.sampled_from([1, 2, "v1", "v2"]),
        )
        ret = self.inner_put(key, value)
        if key in self.state.entries:
            self.state.entries[key] = value
            self.state.order.remove(key)
            self.state.order.append(key)
            assert ret is None
        elif len(self.state.order) >= self.state.capacity:
            evicted_key = self.state.order.pop(0)
            evicted_val = self.state.entries.pop(evicted_key)
            self.state.evictions += 1
            self.state.entries[key] = value
            self.state.order.append(key)
            assert ret == (evicted_key, evicted_val)
        else:
            self.state.entries[key] = value
            self.state.order.append(key)
            assert ret is None
        target: LRUCache = sut(LRUCache)
        assert target.size == len(self.state.order)
        assert target.keys_in_lru_order() == self.state.order
        assert target.peek(key, None) == value
        assert target.get_stats().evictions == self.state.evictions
        return ret

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        if key in self.state.entries:
            return None
        if len(self.state.order) >= self.state.capacity:
            oldest_key = self.state.order[0]
            return (oldest_key, self.state.entries[oldest_key])
        return None

    @transition(LRUCache.peek)
    def peek(self, key: str, default: Optional[Any]) -> Any:
        require_arg(
            key,
            Domain.text(min_size=1),
            preferred=["k1", "k2", "k3", "k4"],
            fuzz_domain=Domain.sampled_from(["k1", "k2", "k3", "k4"]),
        )
        require_arg(
            default,
            Domain.optional(Domain.type(object)),
            preferred=[None, 0, "default"],
            fuzz_domain=Domain.sampled_from([None, 0, "default"]),
        )
        ret = self.inner_peek(key, default)
        if key in self.state.entries:
            assert ret == self.state.entries[key]
        else:
            assert ret == default
        target: LRUCache = sut(LRUCache)
        assert target.keys_in_lru_order() == self.state.order
        assert target.get_stats().hits == self.state.hits
        assert target.get_stats().misses == self.state.misses
        assert target.get_stats().evictions == self.state.evictions
        return ret

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        if key in self.state.entries:
            return self.state.entries[key]
        return default

    @transition(LRUCache.remove)
    def remove(self, key: str) -> Any:
        require(bool(self.state.entries), error=CacheKeyNotFoundError)
        require_arg(key, Domain.in_set(self.state.entries), error=CacheKeyNotFoundError)
        ret = self.inner_remove(key)
        expected = self.state.entries.pop(key)
        self.state.order.remove(key)
        assert ret == expected
        target: LRUCache = sut(LRUCache)
        assert target.size == len(self.state.order)
        assert target.keys_in_lru_order() == self.state.order
        return ret

    def inner_remove(self, key: str) -> Any:
        return self.state.entries[key]

    @transition(LRUCache.clear)
    def clear(self) -> None:
        ret = self.inner_clear()
        self.state.entries.clear()
        self.state.order.clear()
        target: LRUCache = sut(LRUCache)
        assert target.size == 0
        assert target.is_empty is True
        assert target.keys_in_lru_order() == []
        assert target.get_stats().hits == self.state.hits
        assert target.get_stats().misses == self.state.misses
        assert target.get_stats().evictions == self.state.evictions
        return ret

    def inner_clear(self) -> None:
        return None

    @transition(LRUCache.get_stats)
    def get_stats(self) -> CacheStats:
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
        ret = self.inner_reset_stats()
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        target: LRUCache = sut(LRUCache)
        assert target.get_stats().hits == 0
        assert target.get_stats().misses == 0
        assert target.get_stats().evictions == 0
        assert target.keys_in_lru_order() == self.state.order
        return ret

    def inner_reset_stats(self) -> None:
        return None

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(self) -> List[str]:
        ret = self.inner_keys_in_lru_order()
        assert ret == self.state.order
        return ret

    def inner_keys_in_lru_order(self) -> List[str]:
        return list(self.state.order)


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
    """Fixed fake test exercising make_lru_cache_fake factory."""

    def test_make_fake(self) -> None:
        fake_cache = make_lru_cache_fake()
        assert fake_cache.capacity == 3
        assert fake_cache.is_empty is True

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T21:36:22Z
# LAST_CHANGED: 2026-11-13T21:36:22Z
# CHANGE: Author LRUCacheState, LRUCacheStateMachine, FakeLRUCache, and FakeLRUCacheFuzzTest per lru_cache.pyi
# --- END AUTOFAB METADATA ---
