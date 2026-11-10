# === File: lru_cache_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for LRUCache."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_3.parts.lru_cache.pretense.lru_cache_pretense import (LruCacheStateMachine, LruCacheState, FakeLruCache, make_lru_cache_fake)
from benchmark_3.parts.lru_cache.lib.lru_cache_impl import LRUCache, __initialize__
from benchmark_3.parts.lru_cache.lib.lru_cache import CacheCapacityError, CacheKeyNotFoundError


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================
# REFERENCE PATTERNS:
#   # Implementation pseudo-state machine transition override with call_target:
#   @transition(TargetClass.method)
#   def method(self, *args) -> Any:
#       target: TargetClass = sut(TargetClass)
#       old_val = target.property
#       ret = call_target(target.method(*args))
#       assert target.property == old_val
#       return ret
#
#   # Real implementation scenario test driving self.checked (100% statement coverage):
#   class TestTargetImplReal(unittest.TestCase):
#       def setUp(self) -> None:
#           self.registry = LifecycleRegistry()
#           __initialize__(self.registry)
#           self.phase_scope = enter_phase(system, registry=self.registry)
#           self.phase_scope.__enter__()
#           self.real = get_singleton(TargetClass)
#           self.sm = TargetImplPseudoStateMachine(singletons={TargetClass: self.real})
#           self.checked = self.sm.as_checked(TargetClass, self.real)
#       def tearDown(self) -> None:
#           self.phase_scope.__exit__(None, None, None)
#       def test_real_conformance(self) -> None:
#           self.checked.method(*args)

class LruCacheImplPseudoStateMachine(LruCacheStateMachine):
    """Implementation pseudo-state machine for LruCache."""

    @transition(LRUCache.configure)
    def configure(
        self,
        capacity: int,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.configure(capacity))
        return ret

    @transition(LRUCache.get)
    def get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.get(key, default))
        return ret

    @transition(LRUCache.put)
    def put(
        self,
        key: str,
        value: Any,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.put(key, value))
        return ret

    @transition(LRUCache.peek)
    def peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.peek(key, default))
        return ret

    @transition(LRUCache.remove)
    def remove(
        self,
        key: str,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.remove(key))
        return ret

    @transition(LRUCache.clear)
    def clear(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.clear())
        return ret

    @transition(LRUCache.get_stats)
    def get_stats(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.get_stats())
        return ret

    @transition(LRUCache.reset_stats)
    def reset_stats(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.reset_stats())
        return ret

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.keys_in_lru_order())
        return ret

    @transition(name="capacity")
    def capacity(self) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "capacity"))
        return ret

    @transition(name="size")
    def size(self) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "size"))
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "is_empty"))
        return ret

    @transition(name="is_full")
    def is_full(self) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "is_full"))
        return ret


proto = LruCacheImplPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestLruCacheImplReal(unittest.TestCase):
    """Verifies that concrete implementation satisfies contracts."""

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

    def test_real_conformance(self) -> None:
        """Drives all transitions via self.checked for 100% statement coverage."""
        self.checked.configure(10)
        assert self.checked.capacity == 10
        assert self.checked.is_empty is True
        assert self.checked.is_full is False
        self.checked.put("a", 1)
        result = self.checked.get("a", None)
        assert result == 1
        assert self.checked.size == 1
        assert self.checked.is_empty is False
        self.checked.put("b", 2)
        self.checked.put("c", 3)
        keys = self.checked.keys_in_lru_order()
        assert keys == ["a", "b", "c"]
        self.checked.get("a", None)
        keys = self.checked.keys_in_lru_order()
        assert keys == ["b", "c", "a"]
        self.checked.peek("b", None)
        keys = self.checked.keys_in_lru_order()
        assert keys == ["b", "c", "a"]
        result = self.checked.put("d", 4)
        assert result is None
        assert self.checked.size == 4
        self.checked.put("a", 10)
        result = self.checked.get("a", None)
        assert result == 10
        self.checked.remove("b")
        assert self.checked.size == 3
        stats = self.checked.get_stats()
        self.checked.clear()
        assert self.checked.size == 0
        stats_after = self.checked.get_stats()
        assert stats_after.hits == stats.hits
        assert stats_after.misses == stats.misses
        self.checked.reset_stats()
        stats = self.checked.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        result = self.checked.get("missing", "default")
        assert result == "default"

    def test_configure_invalid_capacity(self) -> None:
        """Verifies contract: configure with capacity <= 0 raises CacheCapacityError."""
        with self.assertRaises(CacheCapacityError):
            self.checked.configure(0)
        with self.assertRaises(CacheCapacityError):
            self.checked.configure(-1)

    def test_configure_downsize_eviction(self) -> None:
        """Verifies contract: configuring smaller capacity evicts LRU entries."""
        self.checked.configure(10)
        self.checked.put("a", 1)
        self.checked.put("b", 2)
        self.checked.put("c", 3)
        assert self.checked.size == 3
        self.checked.configure(2)
        assert self.checked.size == 2
        keys = self.checked.keys_in_lru_order()
        assert "c" in keys
        stats = self.checked.get_stats()
        assert stats.evictions >= 1

    def test_put_evict_on_capacity(self) -> None:
        """Verifies contract: putting at capacity evicts the oldest entry."""
        self.checked.configure(3)
        evicted = self.checked.put("a", 1)
        assert evicted is None
        evicted = self.checked.put("b", 2)
        assert evicted is None
        evicted = self.checked.put("c", 3)
        assert evicted is None
        assert self.checked.size == 3
        evicted = self.checked.put("d", 4)
        assert evicted == ("a", 1)
        assert self.checked.size == 3
        assert self.checked.get("a", None) is None
        assert self.checked.get("d", None) == 4

    def test_remove_key_not_found(self) -> None:
        """Verifies contract: removing non-existent key raises CacheKeyNotFoundError."""
        self.checked.configure(10)
        self.checked.put("x", 100)
        with self.assertRaises(CacheKeyNotFoundError):
            self.checked.remove("nonexistent_key")
        assert self.checked.size == 1


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
# LAST_CLEANED: 2026-11-09T06:49:59Z
# LAST_CHANGED: 2026-11-09T06:43:06Z
# CHANGE: Removed precondition guard from configure (guide prohibits duplicating require() preconditions in impl transitions). Clean delegation ret = call_target(target.configure(capacity)); return ret matching remove pattern.
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T06:49:59Z
# PRETENSE_QA_AUDIT: 2026-11-09T06:48:51Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for LruCache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set, Tuple
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
from benchmark_3.parts.lru_cache.lib.lru_cache import (
    CacheStats,
    CacheCapacityError,
    CacheKeyNotFoundError,
    LRUCache,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class LruCacheState:
    """Canonical model state for LruCache operations."""
    initialized: bool = True
    capacity: int = 100
    items: dict[str, Any] = field(default_factory=dict)
    access_order: List[str] = field(default_factory=list)
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class LruCacheStateMachine(StateMachine[LruCacheState]):
    """Unified Pretense State Machine for LruCache."""

    def __init__(
        self,
        state: Optional[LruCacheState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or LruCacheState(), singletons=singletons)

    @transition(LRUCache.configure)
    def configure(self, capacity: int) -> None:
        require_arg(capacity, Domain.type(int), preferred=[10])
        if capacity <= 0:
            with raises(CacheCapacityError):
                raise CacheCapacityError(f"capacity must be greater than zero, got {capacity}")
        require(self.state.initialized)
        ret = make_return_value(None)
        assert ret is None
        self.state.capacity = capacity
        if capacity > 0 and len(self.state.items) > capacity:
            excess = len(self.state.items) - capacity
            keys_to_remove = self.state.access_order[:excess]
            for _k in keys_to_remove:
                if _k in self.state.items:
                    del self.state.items[_k]
                    self.state.evictions += 1
            self.state.access_order = self.state.access_order[excess:]
        return ret

    @transition(LRUCache.get)
    def get(self, key: str, default: Optional[Any]) -> Any:
        require(self.state.initialized)
        require_arg(key, Domain.type(str), preferred=["default_key"])
        require_arg(default, Domain.type(object), preferred=[None])
        if key in self.state.items:
            self.state.access_order.remove(key)
            self.state.access_order.append(key)
            self.state.hits += 1
            ret = make_return_value(self.state.items[key])
            assert ret == self.state.items[key]
            return ret
        else:
            self.state.misses += 1
            ret = make_return_value(default)
            assert ret == default
            return ret

    @transition(LRUCache.put)
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        require(self.state.initialized)
        require_arg(key, Domain.type(str), preferred=["new_key"])
        require_arg(value, Domain.type(object), preferred=["value"])
        if key in self.state.items:
            self.state.items[key] = value
            self.state.access_order.remove(key)
            self.state.access_order.append(key)
            ret = make_return_value(None)
            assert ret is None
            return ret
        if len(self.state.items) >= self.state.capacity and self.state.capacity > 0:
            lru_key = self.state.access_order.pop(0)
            evicted_value = self.state.items.pop(lru_key)
            self.state.evictions += 1
            self.state.items[key] = value
            self.state.access_order.append(key)
            ret = make_return_value((lru_key, evicted_value))
            assert ret == (lru_key, evicted_value)
            return ret
        self.state.items[key] = value
        self.state.access_order.append(key)
        ret = make_return_value(None)
        assert ret is None
        return ret

    @transition(LRUCache.peek)
    def peek(self, key: str, default: Optional[Any]) -> Any:
        require(self.state.initialized)
        require_arg(key, Domain.type(str), preferred=["peek_key"])
        require_arg(default, Domain.type(object), preferred=[None])
        if key in self.state.items:
            ret = make_return_value(self.state.items[key])
            assert ret == self.state.items[key]
            assert key in self.state.access_order
            return ret
        else:
            ret = make_return_value(default)
            assert ret == default
            return ret

    @transition(LRUCache.remove)
    def remove(self, key: str) -> Any:
        require(self.state.initialized)
        require_arg(key, Domain.type(str), preferred=["remove_key"])
        if key not in self.state.items:
            with raises(CacheKeyNotFoundError):
                ret = make_return_value(None)
                assert ret is None
                return ret
        value = self.state.items.pop(key)
        self.state.access_order.remove(key)
        ret = make_return_value(value)
        assert ret == value
        return ret

    @transition(LRUCache.clear)
    def clear(self) -> None:
        require(self.state.initialized)
        self.state.items.clear()
        self.state.access_order.clear()
        ret = make_return_value(None)
        assert ret is None
        return ret

    @transition(LRUCache.get_stats)
    def get_stats(self) -> CacheStats:
        require(self.state.initialized)
        ret = make_return_value(CacheStats(
            hits=self.state.hits,
            misses=self.state.misses,
            evictions=self.state.evictions,
        ))
        assert isinstance(ret, CacheStats)
        return ret

    @transition(LRUCache.reset_stats)
    def reset_stats(self) -> None:
        require(self.state.initialized)
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        ret = make_return_value(None)
        assert ret is None
        return ret

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(self) -> List[str]:
        require(self.state.initialized)
        ret = make_return_value(list(self.state.access_order))
        assert ret == list(self.state.access_order)
        return ret

    @transition(name="capacity")
    def capacity(self) -> int:
        require(self.state.initialized)
        ret = make_return_value(self.state.capacity)
        assert ret == self.state.capacity
        return ret

    @transition(name="size")
    def size(self) -> int:
        require(self.state.initialized)
        ret = make_return_value(len(self.state.items))
        assert ret == len(self.state.items)
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        require(self.state.initialized)
        ret = make_return_value(len(self.state.items) == 0)
        assert isinstance(ret, bool)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        require(self.state.initialized)
        ret = make_return_value(len(self.state.items) >= self.state.capacity and self.state.capacity > 0)
        assert isinstance(ret, bool)
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seed state machine state for fake initialization."""
        self.state.initialized = True

    @transition.seeding
    def seed_with_capacity(self, capacity: int) -> None:
        """Seed state machine with a specific capacity."""
        self.state.initialized = True
        self.state.capacity = capacity

    @transition.seeding
    def seed_with_items(self, items: List[Tuple[str, Any]], capacity: int) -> None:
        """Seed state machine with multiple items."""
        self.state.initialized = True
        self.state.capacity = capacity
        for key, value in items:
            self.state.items[key] = value
            self.state.access_order.append(key)


proto = LruCacheStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeLruCache = synthesize_fake(LruCacheStateMachine)


def make_lru_cache_fake(
    state: Optional[LruCacheState] = None,
) -> LRUCache:
    """Synthesizes fake instance for LruCache component."""
    return FakeLruCache(state=state or LruCacheState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestLruCacheFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all transitions and seeding transitions."""

    def setUp(self) -> None:
        self.fake = make_lru_cache_fake()
        self.sm = LruCacheStateMachine()

    def test_transitions_coverage(self) -> None:
        """Exercises all transitions and seeding transitions on the fake."""
        self.sm.seed_initial()
        _ = self.sm.capacity()
        _ = self.sm.size()
        _ = self.sm.is_empty()
        _ = self.sm.is_full()
        self.sm.configure(10)
        self.sm.get("key1", None)
        self.sm.put("key1", "value1")
        self.sm.peek("key1", None)
        self.sm.remove("key1")
        self.sm.clear()
        self.sm.get_stats()
        self.sm.reset_stats()
        self.sm.keys_in_lru_order()

    def test_seed_with_capacity(self) -> None:
        """Tests seeding with a specific capacity."""
        self.sm.seed_with_capacity(5)
        self.fake.put("a", 1)
        result = self.fake.get("a", None)
        assert result == 1

    def test_seed_with_items(self) -> None:
        """Tests seeding with multiple items."""
        self.sm.seed_with_items([("x", 1), ("y", 2)], 10)
        result = self.fake.get("x", None)
        assert result == 1
        keys = self.fake.keys_in_lru_order()
        assert keys == ["x", "y"]

    def test_get_hit(self) -> None:
        """Tests get returns value on hit."""
        self.sm.put("key", "val")
        result = self.fake.get("key", None)
        assert result == "val"

    def test_get_miss(self) -> None:
        """Tests get returns default on miss."""
        result = self.fake.get("missing", "default")
        assert result == "default"

    def test_put_new(self) -> None:
        """Tests put inserts new entry."""
        self.sm.configure(10)
        result = self.fake.put("k", "v")
        assert result is None

    def test_put_existing(self) -> None:
        """Tests put updates existing entry."""
        self.sm.configure(10)
        self.fake.put("k", "v1")
        result = self.fake.put("k", "v2")
        assert result is None
        assert self.fake.get("k", None) == "v2"

    def test_eviction(self) -> None:
        """Tests eviction when capacity is reached."""
        self.sm.configure(2)
        self.fake.put("a", 1)
        self.fake.put("b", 2)
        result = self.fake.put("c", 3)
        assert result is not None
        evicted_key, evicted_value = result
        assert evicted_key == "a"

    def test_remove_existing(self) -> None:
        """Tests remove on existing key."""
        self.fake.put("k", "v")
        result = self.fake.remove("k")
        assert result == "v"

    def test_clear_preserves_stats(self) -> None:
        """Tests clear preserves telemetry counters."""
        self.sm.configure(10)
        self.fake.get("missing", None)
        self.fake.clear()
        stats = self.fake.get_stats()
        assert stats.misses == 1
        assert len(self.fake.keys_in_lru_order()) == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeLruCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=LruCacheState,
    name="FakeLruCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T05:52:19Z
# LAST_CHANGED: 2026-11-09T05:52:19Z
# CHANGE: Fix state model capacity mismatch: changed LruCacheState.capacity default from 0 to 100 to match real LRUCache constructor default. Removed broken configure monkey-patch that failed because synthesize_fake does not synthesize configure (returns None method not synthesized).
# --- END AUTOFAB METADATA ---
