# === File: lru_cache_pretense.py ===
"""Pretense interface and fake state machine for the bounded LRU cache.

This module contains the stateless behavioral contract for ``LRUCache``
(``LRUCacheStateMachine``) plus the stateful in-memory fake used for
hypothesis fuzzing (``LRUCacheFakeStateMachine``).  The concrete
implementation is bound in the companion ``pretense_impl`` module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple, cast
import unittest

from pretense import (
    StateMachine,
    domain,
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

_MISSING: object = object()


# ==============================================================================
# 1. Stateless Interface State Machine (<Iface>StateMachine)
# ==============================================================================


class LRUCacheStateMachine(StateMachine[Any]):
    """Stateless behavioral contract for the bounded least-recently-used cache."""

    @domain(
        valid=lambda self: [1, 2, 3, 4, 5, 10, 100],
        invalid=lambda self: [0, -1, -100],
    )
    def positive_capacity(self, capacity: int) -> bool:
        return isinstance(capacity, int) and capacity > 0

    @domain(
        valid=lambda self: cast(
            "LRUCacheStateMachine", self
        ).inner_keys_in_lru_order(),
        invalid=lambda self: ["__absent_key__", ""],
    )
    def present_key(self, key: str) -> bool:
        return key in self.inner_keys_in_lru_order()

    @transition(name="capacity")
    def capacity(self) -> int:
        ret = self.inner_capacity()
        assert isinstance(ret, int)
        assert ret > 0
        return ret

    @transition(name="size")
    def size(self) -> int:
        ret = self.inner_size()
        assert isinstance(ret, int)
        assert ret >= 0
        assert ret <= self.inner_capacity()
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        old_size = self.inner_size()
        ret = self.inner_is_empty()
        assert ret is (old_size == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        old_size = self.inner_size()
        old_capacity = self.inner_capacity()
        ret = self.inner_is_full()
        assert ret is (old_size >= old_capacity)
        return ret

    @transition(LRUCache.configure)
    def configure(self, capacity: int) -> None:
        require_arg(capacity, self.positive_capacity, error=CacheCapacityError)
        old_keys = self.inner_keys_in_lru_order()
        old_size = self.inner_size()
        old_stats = self.inner_get_stats()
        ret = self.inner_configure(capacity)
        new_keys = self.inner_keys_in_lru_order()
        new_size = self.inner_size()
        new_stats = self.inner_get_stats()
        assert ret is None
        assert self.inner_capacity() == capacity
        assert new_size == min(old_size, capacity)
        if old_size > capacity:
            expected_keys = old_keys[old_size - capacity :]
            expected_evictions = old_size - capacity
        else:
            expected_keys = list(old_keys)
            expected_evictions = 0
        assert new_keys == expected_keys
        assert new_stats.evictions == old_stats.evictions + expected_evictions
        assert new_stats.hits == old_stats.hits
        assert new_stats.misses == old_stats.misses
        return ret

    @transition(LRUCache.get)
    def get(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, str)
        require_arg(default, object)
        old_keys = self.inner_keys_in_lru_order()
        old_stats = self.inner_get_stats()
        old_value = self.inner_peek(key, _MISSING)
        ret = self.inner_get(key, default)
        new_keys = self.inner_keys_in_lru_order()
        new_stats = self.inner_get_stats()
        if old_value is not _MISSING:
            assert ret is old_value or ret == old_value
            expected_keys = [k for k in old_keys if k != key]
            expected_keys.append(key)
            assert new_keys == expected_keys
            assert new_stats.hits == old_stats.hits + 1
            assert new_stats.misses == old_stats.misses
        else:
            assert ret is default or ret == default
            assert new_keys == old_keys
            assert new_stats.misses == old_stats.misses + 1
            assert new_stats.hits == old_stats.hits
        assert new_stats.evictions == old_stats.evictions
        return ret

    @transition(LRUCache.put)
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        require_arg(key, str)
        require_arg(value, object)
        old_keys = self.inner_keys_in_lru_order()
        old_stats = self.inner_get_stats()
        old_size = self.inner_size()
        old_capacity = self.inner_capacity()
        old_value = self.inner_peek(key, _MISSING)
        evicted_value = self.inner_peek(old_keys[0], _MISSING) if old_keys else _MISSING
        ret = self.inner_put(key, value)
        new_keys = self.inner_keys_in_lru_order()
        new_size = self.inner_size()
        new_stats = self.inner_get_stats()
        stored_value = self.inner_peek(key, _MISSING)
        assert stored_value is not _MISSING
        assert stored_value is value or stored_value == value
        if old_value is not _MISSING:
            assert ret is None
            expected_keys = [k for k in old_keys if k != key]
            expected_keys.append(key)
            assert new_keys == expected_keys
            assert new_size == old_size
            assert new_stats.evictions == old_stats.evictions
        elif old_size >= old_capacity:
            assert isinstance(ret, tuple)
            assert len(ret) == 2
            assert ret[0] == old_keys[0]
            assert ret[1] is evicted_value or ret[1] == evicted_value
            assert new_keys == old_keys[1:] + [key]
            assert new_size == old_size
            assert new_stats.evictions == old_stats.evictions + 1
        else:
            assert ret is None
            assert new_keys == old_keys + [key]
            assert new_size == old_size + 1
            assert new_stats.evictions == old_stats.evictions
        assert new_stats.hits == old_stats.hits
        assert new_stats.misses == old_stats.misses
        return ret

    @transition(LRUCache.peek)
    def peek(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, str)
        require_arg(default, object)
        old_keys = self.inner_keys_in_lru_order()
        old_stats = self.inner_get_stats()
        old_value = self.inner_peek(key, _MISSING)
        ret = self.inner_peek(key, default)
        new_keys = self.inner_keys_in_lru_order()
        new_stats = self.inner_get_stats()
        if old_value is not _MISSING:
            assert ret is old_value or ret == old_value
        else:
            assert ret is default or ret == default
        assert new_keys == old_keys
        assert new_stats == old_stats
        return ret

    @transition(LRUCache.remove)
    def remove(self, key: str) -> Any:
        old_keys = self.inner_keys_in_lru_order()
        require_arg(key, self.present_key, error=CacheKeyNotFoundError)
        old_value = self.inner_peek(key, _MISSING)
        ret = self.inner_remove(key)
        new_keys = self.inner_keys_in_lru_order()
        assert ret is old_value or ret == old_value
        assert new_keys == [k for k in old_keys if k != key]
        assert self.inner_size() == len(new_keys)
        return ret

    @transition(LRUCache.clear)
    def clear(self) -> None:
        old_stats = self.inner_get_stats()
        ret = self.inner_clear()
        assert ret is None
        assert self.inner_size() == 0
        assert self.inner_is_empty()
        assert self.inner_keys_in_lru_order() == []
        assert self.inner_get_stats() == old_stats
        return ret

    @transition(LRUCache.get_stats)
    def get_stats(self) -> CacheStats:
        old_stats = self.inner_get_stats()
        ret = self.inner_get_stats()
        assert ret == old_stats
        assert ret.hits >= 0
        assert ret.misses >= 0
        assert ret.evictions >= 0
        return ret

    @transition(LRUCache.reset_stats)
    def reset_stats(self) -> None:
        old_keys = self.inner_keys_in_lru_order()
        ret = self.inner_reset_stats()
        new_stats = self.inner_get_stats()
        assert ret is None
        assert new_stats.hits == 0
        assert new_stats.misses == 0
        assert new_stats.evictions == 0
        assert self.inner_keys_in_lru_order() == old_keys
        return ret

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(self) -> list[str]:
        old_stats = self.inner_get_stats()
        ret = self.inner_keys_in_lru_order()
        assert isinstance(ret, list)
        assert len(ret) == self.inner_size()
        assert len(set(ret)) == len(ret)
        assert self.inner_get_stats() == old_stats
        return ret

    def inner_capacity(self) -> int: ...

    def inner_size(self) -> int: ...

    def inner_is_empty(self) -> bool: ...

    def inner_is_full(self) -> bool: ...

    def inner_configure(self, capacity: int) -> None: ...

    def inner_get(self, key: str, default: Optional[Any]) -> Any: ...

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]: ...

    def inner_peek(self, key: str, default: Optional[Any]) -> Any: ...

    def inner_remove(self, key: str) -> Any: ...

    def inner_clear(self) -> None: ...

    def inner_get_stats(self) -> CacheStats: ...

    def inner_reset_stats(self) -> None: ...

    def inner_keys_in_lru_order(self) -> list[str]: ...


# ==============================================================================
# 2. Stateful Fake State Machine and Fuzzing (<Iface>FakeStateMachine)
# ==============================================================================


@dataclass
class LRUCacheState:
    """Model state owned exclusively by LRUCacheFakeStateMachine."""

    capacity: int = 100
    entries: dict[str, Any] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class LRUCacheFakeStateMachine(LRUCacheStateMachine):
    """Stateful in-memory fake for the bounded least-recently-used cache."""

    def __init__(
        self,
        state: Optional[LRUCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(
            state=state if state is not None else self.make_initial_state(),
            singletons=singletons,
        )

    def make_initial_state(self) -> LRUCacheState:
        return LRUCacheState()

    @transition.seeding
    def seed_empty(self) -> None:
        self.state.capacity = 100
        self.state.entries = {}
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0

    @transition.seeding
    def seed_partially_filled(self) -> None:
        self.state.capacity = 4
        self.state.entries = {"alpha": 1, "beta": 2}
        self.state.hits = 2
        self.state.misses = 1
        self.state.evictions = 0

    @transition.seeding
    def seed_full(self) -> None:
        self.state.capacity = 3
        self.state.entries = {"oldest": 10, "middle": 20, "newest": 30}
        self.state.hits = 5
        self.state.misses = 2
        self.state.evictions = 2

    def inner_capacity(self) -> int:
        return self.state.capacity

    def inner_size(self) -> int:
        return len(self.state.entries)

    def inner_is_empty(self) -> bool:
        return len(self.state.entries) == 0

    def inner_is_full(self) -> bool:
        return len(self.state.entries) >= self.state.capacity

    def inner_configure(self, capacity: int) -> None:
        self.state.capacity = capacity
        while len(self.state.entries) > capacity:
            evicted_key = next(iter(self.state.entries))
            del self.state.entries[evicted_key]
            self.state.evictions += 1

    def inner_get(self, key: str, default: Optional[Any]) -> Any:
        if key in self.state.entries:
            value = self.state.entries.pop(key)
            self.state.entries[key] = value
            self.state.hits += 1
            return value
        self.state.misses += 1
        return default

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        if key in self.state.entries:
            self.state.entries.pop(key)
            self.state.entries[key] = value
            return None
        evicted: Optional[Tuple[str, Any]] = None
        if len(self.state.entries) >= self.state.capacity:
            evicted_key = next(iter(self.state.entries))
            evicted = (evicted_key, self.state.entries.pop(evicted_key))
            self.state.evictions += 1
        self.state.entries[key] = value
        return evicted

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        if key in self.state.entries:
            return self.state.entries[key]
        return default

    def inner_remove(self, key: str) -> Any:
        return self.state.entries.pop(key)

    def inner_clear(self) -> None:
        self.state.entries.clear()

    def inner_get_stats(self) -> CacheStats:
        return CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        )

    def inner_reset_stats(self) -> None:
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0

    def inner_keys_in_lru_order(self) -> list[str]:
        return list(self.state.entries.keys())


FakeLRUCache = synthesize_fake(LRUCacheFakeStateMachine)


def make_lru_cache_fake(state: Optional[LRUCacheState] = None) -> LRUCache:
    return FakeLRUCache(
        state=state
        if state is not None
        else LRUCacheFakeStateMachine().make_initial_state()
    )


FakeLRUCacheFuzzTest = compile_hypothesis_test_case(
    LRUCacheFakeStateMachine,
    name="FakeLRUCacheFuzzTest",
)


class TestLRUCacheFake(unittest.TestCase):
    """Fixed fake tests for branches not reliably reached by fuzzing."""

    def setUp(self) -> None:
        self.fake: LRUCache = make_lru_cache_fake()

    def test_initial_state(self) -> None:
        self.assertEqual(self.fake.capacity, 100)
        self.assertEqual(self.fake.size, 0)
        self.assertTrue(self.fake.is_empty)
        self.assertFalse(self.fake.is_full)
        self.assertEqual(self.fake.keys_in_lru_order(), [])
        stats = self.fake.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(stats.evictions, 0)

    def test_insert_lookup_and_ordering(self) -> None:
        self.assertIsNone(self.fake.put("a", 1))
        self.assertIsNone(self.fake.put("b", 2))
        self.assertEqual(self.fake.keys_in_lru_order(), ["a", "b"])
        self.assertEqual(self.fake.get("a", None), 1)
        self.assertEqual(self.fake.keys_in_lru_order(), ["b", "a"])
        self.assertEqual(self.fake.peek("b", None), 2)
        self.assertEqual(self.fake.keys_in_lru_order(), ["b", "a"])
        stats = self.fake.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 0)

    def test_eviction_at_capacity(self) -> None:
        self.assertIsNone(self.fake.put("a", 1))
        self.assertIsNone(self.fake.put("b", 2))
        self.fake.configure(2)
        self.assertEqual(self.fake.put("c", 3), ("a", 1))
        self.assertEqual(self.fake.keys_in_lru_order(), ["b", "c"])
        self.assertEqual(self.fake.get_stats().evictions, 1)

    def test_downsize_evicts_least_recently_used(self) -> None:
        self.fake.put("a", 1)
        self.fake.put("b", 2)
        self.fake.put("c", 3)
        self.fake.configure(1)
        self.assertEqual(self.fake.keys_in_lru_order(), ["c"])
        self.assertEqual(self.fake.get_stats().evictions, 2)

    def test_clear_preserves_telemetry(self) -> None:
        self.fake.put("a", 1)
        self.fake.get("a", None)
        self.fake.get("missing", None)
        self.fake.clear()
        self.assertTrue(self.fake.is_empty)
        self.assertEqual(self.fake.keys_in_lru_order(), [])
        stats = self.fake.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)

    def test_reset_stats_keeps_entries(self) -> None:
        self.fake.put("a", 1)
        self.fake.get("a", None)
        self.fake.get("missing", None)
        self.fake.reset_stats()
        stats = self.fake.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(stats.evictions, 0)
        self.assertEqual(self.fake.keys_in_lru_order(), ["a"])

    def test_update_existing_key(self) -> None:
        self.assertIsNone(self.fake.put("a", 1))
        self.assertIsNone(self.fake.put("a", 2))
        self.assertEqual(self.fake.size, 1)
        self.assertEqual(self.fake.keys_in_lru_order(), ["a"])
        self.assertEqual(self.fake.peek("a", None), 2)

    def test_remove_returns_value(self) -> None:
        self.fake.put("a", 7)
        self.assertEqual(self.fake.remove("a"), 7)
        self.assertEqual(self.fake.size, 0)
        self.assertTrue(self.fake.is_empty)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T09:21:21Z
# LAST_CHANGED: 2026-11-15T09:21:21Z
# CHANGE: Implement LRUCacheStateMachine contract (capacity, size, is_empty, is_full, configure, get, put, peek, remove, clear, get_stats, reset_stats, keys_in_lru_order) and LRUCacheFakeStateMachine with seeding, in-memory fake, synthesize_fake(FakeLRUCache), make_lru_cache_fake, FakeLRUCacheFuzzTest, and fixed fake tests for update/eviction/downsize/clear/reset paths.
# --- END AUTOFAB METADATA ---


# === File: lru_cache_impl_pretense.py ===
"""Pretense implementation bindings and tests for the bounded LRU cache.

This module binds the concrete ``LRUCache`` implementation
(``lib/lru_cache_impl.py``) to the stateless behavioral contract
``LRUCacheStateMachine`` declared in ``pretense_intf/lru_cache_pretense.py``.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from pretense import sut
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
from lru_cache_deepseek_flash_1.parts.lru_cache.pretense_intf.lru_cache_pretense import (
    LRUCacheStateMachine,
)


# ==============================================================================
# 1. Stateless Implementation State Machine (<Impl>StateMachine(<Iface>StateMachine))
# ==============================================================================


class LRUCacheImplStateMachine(LRUCacheStateMachine):
    """Implementation binding for the concrete ``LRUCacheImpl`` cache."""

    def inner_capacity(self) -> int:
        return sut(LRUCache).capacity

    def inner_size(self) -> int:
        return sut(LRUCache).size

    def inner_is_empty(self) -> bool:
        return sut(LRUCache).is_empty

    def inner_is_full(self) -> bool:
        return sut(LRUCache).is_full

    def inner_configure(self, capacity: int) -> None:
        sut(LRUCache).configure(capacity)

    def inner_get(self, key: str, default: Optional[Any]) -> Any:
        return sut(LRUCache).get(key, default)

    def inner_put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        return sut(LRUCache).put(key, value)

    def inner_peek(self, key: str, default: Optional[Any]) -> Any:
        return sut(LRUCache).peek(key, default)

    def inner_remove(self, key: str) -> Any:
        return sut(LRUCache).remove(key)

    def inner_clear(self) -> None:
        sut(LRUCache).clear()

    def inner_get_stats(self) -> CacheStats:
        return sut(LRUCache).get_stats()

    def inner_reset_stats(self) -> None:
        sut(LRUCache).reset_stats()

    def inner_keys_in_lru_order(self) -> list[str]:
        return list(sut(LRUCache).keys_in_lru_order())


# ==============================================================================
# 2. Real Implementation Tests & Fuzzing
# ==============================================================================


class TestLRUCacheImplReal(LifecycleTestCase):
    """Fixed scenarios for the concrete cache implementation."""

    target = LRUCacheImpl

    def setUp(self) -> None:
        super().setUp()
        self.sm = LRUCacheImplStateMachine(singletons={LRUCache: self.sut})
        self.checked = self.sm.as_checked(LRUCache, self.sut)

    def test_initial_state(self) -> None:
        self.assertEqual(self.checked.capacity, 100)
        self.assertEqual(self.checked.size, 0)
        self.assertTrue(self.checked.is_empty)
        self.assertFalse(self.checked.is_full)
        self.assertEqual(self.checked.keys_in_lru_order(), [])
        stats = self.checked.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(stats.evictions, 0)

    def test_put_get_and_recency_promotion(self) -> None:
        self.assertIsNone(self.checked.put("a", 1))
        self.assertIsNone(self.checked.put("b", 2))
        self.assertEqual(self.checked.keys_in_lru_order(), ["a", "b"])
        self.assertEqual(self.checked.size, 2)
        self.assertEqual(self.checked.get("a", None), 1)
        self.assertEqual(self.checked.keys_in_lru_order(), ["b", "a"])
        self.assertEqual(self.checked.get("missing", "fallback"), "fallback")
        stats = self.checked.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)

    def test_update_existing_key_keeps_size(self) -> None:
        self.checked.put("a", 1)
        self.checked.put("b", 2)
        self.assertIsNone(self.checked.put("a", 10))
        self.assertEqual(self.checked.size, 2)
        self.assertEqual(self.checked.keys_in_lru_order(), ["b", "a"])
        self.assertEqual(self.checked.peek("a", None), 10)

    def test_peek_does_not_promote_or_track(self) -> None:
        self.checked.put("a", 1)
        self.checked.put("b", 2)
        self.assertEqual(self.checked.peek("a", None), 1)
        self.assertEqual(self.checked.keys_in_lru_order(), ["a", "b"])
        stats = self.checked.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)

    def test_eviction_at_capacity(self) -> None:
        self.checked.configure(2)
        self.checked.put("a", 1)
        self.checked.put("b", 2)
        self.assertTrue(self.checked.is_full)
        self.assertEqual(self.checked.put("c", 3), ("a", 1))
        self.assertEqual(self.checked.keys_in_lru_order(), ["b", "c"])
        self.assertEqual(self.checked.get_stats().evictions, 1)

    def test_downsize_evicts_least_recently_used(self) -> None:
        self.checked.put("a", 1)
        self.checked.put("b", 2)
        self.checked.put("c", 3)
        self.checked.configure(1)
        self.assertEqual(self.checked.capacity, 1)
        self.assertEqual(self.checked.keys_in_lru_order(), ["c"])
        self.assertEqual(self.checked.get_stats().evictions, 2)

    def test_remove_existing_key(self) -> None:
        self.checked.put("a", 7)
        self.checked.put("b", 8)
        self.assertEqual(self.checked.remove("a"), 7)
        self.assertEqual(self.checked.size, 1)
        self.assertEqual(self.checked.keys_in_lru_order(), ["b"])

    def test_clear_preserves_telemetry(self) -> None:
        self.checked.put("a", 1)
        self.checked.get("a", None)
        self.checked.get("missing", None)
        self.checked.clear()
        self.assertTrue(self.checked.is_empty)
        self.assertEqual(self.checked.keys_in_lru_order(), [])
        stats = self.checked.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)

    def test_reset_stats_keeps_entries(self) -> None:
        self.checked.put("a", 1)
        self.checked.get("a", None)
        self.checked.get("missing", None)
        self.checked.reset_stats()
        stats = self.checked.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(stats.evictions, 0)
        self.assertEqual(self.checked.keys_in_lru_order(), ["a"])

    def test_violating_zero_capacity(self) -> None:
        self.checked.violating(CacheCapacityError).configure(0)

    def test_violating_negative_capacity(self) -> None:
        self.checked.violating(CacheCapacityError).configure(-1)

    def test_violating_remove_absent_key(self) -> None:
        self.checked.put("present", 1)
        self.checked.violating(CacheKeyNotFoundError).remove("__absent_key__")


def make_sut() -> LRUCache:
    """Constructs the concrete cache singleton inside an active system phase."""
    registry = LifecycleRegistry()
    registry.register_singleton(LRUCacheImpl)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(LRUCache)


LRUCacheImplFuzzTest = compile_hypothesis_test_case(
    LRUCacheImplStateMachine,
    sut_factory=make_sut,
    name="LRUCacheImplFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-15T09:24:37Z
# LAST_CHANGED: 2026-11-15T09:24:04Z
# CHANGE: Implemented LRUCacheImplStateMachine(LRUCacheStateMachine) binding all inner_* contract hooks to the concrete lib.lru_cache_impl.LRUCache singleton via sut(LRUCache); added TestLRUCacheImplReal LifecycleTestCase scenarios (initial state, recency promotion, update, peek non-mutation, capacity eviction, downsize eviction, remove, clear telemetry, reset_stats) with dedicated terminal violating() tests for CacheCapacityError.configure(0/-1) and CacheKeyNotFoundError.remove(absent); added make_sut() lifecycle wiring and LRUCacheImplFuzzTest hypothesis compilation.
# PRETENSE_COVERAGE_AUDIT: 2026-11-15T09:24:37Z
# PRETENSE_QA_AUDIT: 2026-11-15T09:24:21Z
# --- END AUTOFAB METADATA ---
