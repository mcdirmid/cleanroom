# === File: lru_cache_impl_pretense.py ===
"""Pretense implementation pseudo-state machine and real test suite for LRUCache."""

from __future__ import annotations

from typing import Any, List, Optional, Protocol, Tuple, cast


class _CheckedAdapter(Protocol):
    """Protocol for the adapter returned by StateMachine.as_checked.

    The adapter wraps both the target class (providing all LRUCache methods)
    and adds dynamic adapter capabilities like violating() for contract violation testing.
    """

    def violating(self, error: type[Exception]) -> Any: ...
    # Dynamic attribute access for all LRUCache methods
    def __getattr__(self, name: str) -> Any: ...
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_4.parts.lru_cache.pretense.lru_cache_pretense import (
    LruCacheStateMachine,
    LruCacheState,
    FakeLruCache,
    make_lru_cache_fake,
)
from benchmark_4.parts.lru_cache.lib.lru_cache import CacheCapacityError, CacheKeyNotFoundError
from benchmark_4.parts.lru_cache.lib.lru_cache_impl import LRUCache, __initialize__


# ==============================================================================
# 1. Implementation Pseudo-State Machine
# ==============================================================================

class LruCacheImplPseudoStateMachine(LruCacheStateMachine):
    """Implementation pseudo-state machine for LruCache."""

    def inner_configure(
        self,
        capacity: int,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.configure(capacity))
        return ret

    def inner_get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.get(key, default))
        return ret

    def inner_put(
        self,
        key: str,
        value: Any,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.put(key, value))
        return ret

    def inner_peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.peek(key, default))
        return ret

    def inner_remove(
        self,
        key: str,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.remove(key))
        return ret

    def inner_clear(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.clear())
        return ret

    def inner_get_stats(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.get_stats())
        return ret

    def inner_reset_stats(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.reset_stats())
        return ret

    def inner_keys_in_lru_order(
        self,
    ) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(target.keys_in_lru_order())
        return ret

    def inner_capacity(self) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "capacity"))
        return ret

    def inner_size(self) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "size"))
        return ret

    def inner_is_empty(self) -> Any:
        target: LRUCache = sut(LRUCache)
        ret = call_target(getattr(target, "is_empty"))
        return ret

    def inner_is_full(self) -> Any:
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
        self.checked = cast(_CheckedAdapter, self.sm.as_checked(LRUCache, self.real))

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_configure_basic(self) -> None:
        """Verify configure sets capacity."""
        self.checked.configure(5)
        assert self.sm.capacity() == 5

    def test_configure_invalid_capacity(self) -> None:
        """Verify configure rejects non-positive capacity."""
        self.checked.violating(CacheCapacityError).configure(0)

    def test_put_and_get_hit(self) -> None:
        """Verify put stores and get retrieves with hit."""
        self.checked.put("key1", "value1")
        result = self.checked.get("key1", None)
        assert result == "value1"

    def test_put_and_get_miss(self) -> None:
        """Verify get returns default for absent key."""
        result = self.checked.get("missing", "default")
        assert result == "default"

    def test_put_update_existing(self) -> None:
        """Verify put updates existing key without eviction."""
        self.checked.put("key1", "old")
        result = self.checked.put("key1", "new")
        assert result is None
        assert self.checked.get("key1", None) == "new"

    def test_put_evict_on_capacity(self) -> None:
        """Verify LRU eviction when at capacity."""
        self.checked.configure(2)
        self.checked.put("a", "1")
        self.checked.put("b", "2")
        result = self.checked.put("c", "3")
        assert result is not None
        assert result[0] == "a"

    def test_peek_preserves_order(self) -> None:
        """Verify peek does not alter access recency."""
        self.checked.configure(5)
        self.checked.put("a", "1")
        self.checked.put("b", "2")
        _ = self.checked.peek("a", None)
        order = self.checked.keys_in_lru_order()
        assert order[0] == "a"
        assert order[1] == "b"

    def test_remove_existing(self) -> None:
        """Verify remove returns value and reduces size."""
        self.checked.put("key1", "value1")
        result = self.checked.remove("key1")
        assert result == "value1"
        assert self.sm.size() == 0

    def test_remove_nonexistent(self) -> None:
        """Verify remove raises on absent key."""
        self.checked.violating(CacheKeyNotFoundError).remove("ghost")

    def test_clear_preserves_telemetry(self) -> None:
        """Verify clear removes entries but preserves telemetry."""
        self.checked.put("a", "1")
        self.checked.put("b", "2")
        self.checked.get("a", None)
        stats_before = self.checked.get_stats()
        self.checked.clear()
        assert self.sm.size() == 0
        stats_after = self.checked.get_stats()
        assert stats_after.hits == stats_before.hits
        assert stats_after.misses == stats_before.misses

    def test_reset_stats(self) -> None:
        """Verify reset_stats zeroes counters without affecting entries."""
        self.checked.put("a", "1")
        self.checked.get("a", None)
        self.checked.reset_stats()
        stats = self.checked.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert self.sm.size() == 1

    def test_properties(self) -> None:
        """Verify capacity, size, is_empty, is_full properties."""
        self.checked.configure(3)
        assert self.checked.capacity == 3
        assert self.checked.size == 0
        assert self.checked.is_empty is True
        assert self.checked.is_full is False
        self.checked.put("a", "1")
        self.checked.put("b", "2")
        assert self.checked.size == 2
        assert self.checked.is_empty is False
        self.checked.put("c", "3")
        assert self.checked.is_full is True

    def test_configure_downsize_eviction(self) -> None:
        """Verify configuring to a smaller capacity evicts the oldest entries."""
        self.checked.configure(5)
        self.checked.put("a", "1")
        self.checked.put("b", "2")
        self.checked.put("c", "3")
        self.checked.put("d", "4")
        self.checked.put("e", "5")
        stats_before = self.checked.get_stats()
        assert stats_before.evictions == 0
        assert self.checked.size == 5
        self.checked.configure(2)
        assert self.checked.size == 2
        assert self.checked.is_full is True
        stats_after = self.checked.get_stats()
        assert stats_after.evictions == 3

    def test_get_stats_reporting(self) -> None:
        """Verify get_stats reports cumulative telemetry."""
        self.checked.put("a", "1")
        self.checked.put("b", "2")
        self.checked.get("a", None)
        self.checked.get("missing", None)
        self.checked.get("a", None)
        stats = self.checked.get_stats()
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.evictions == 0

    def test_eviction_counter_increments(self) -> None:
        """Verify evictions counter increments on eviction."""
        self.checked.configure(2)
        self.checked.put("a", "1")
        self.checked.put("b", "2")
        self.checked.put("c", "3")
        stats = self.checked.get_stats()
        assert stats.evictions == 1


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
# LAST_CLEANED: 2026-11-09T22:39:00Z
# LAST_CHANGED: 2026-11-09T22:38:04Z
# CHANGE: Added test_configure_downsize_eviction to exercise configure(capacity > current) → fill → configure(capacity < current) eviction path (fixes post.unexercised on lru_cache.configure.downsize_eviction). Changed test_properties to access capacity/size/is_empty/is_full via self.checked (real SUT adapter) instead of self.sm, exercising the real property getters on the LRUCache singleton.
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T22:39:00Z
# PRETENSE_QA_AUDIT: 2026-11-09T22:38:26Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for LruCache."""

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
from benchmark_4.parts.lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
    LRUCache,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class LruCacheState:
    """Canonical model state for LruCache operations."""
    capacity: int = 100
    keys: List[str] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)
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
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> LruCacheState:
        """Constructs initial model state."""
        return LruCacheState()

    # --- Property transitions ---

    @transition(name="capacity")
    def capacity(self) -> int:
        ret = self.inner_capacity()
        assert ret == self.state.capacity
        return ret

    @transition(name="size")
    def size(self) -> int:
        ret = self.inner_size()
        assert ret == len(self.state.keys)
        return ret

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        ret = self.inner_is_empty()
        assert ret == (len(self.state.keys) == 0)
        return ret

    @transition(name="is_full")
    def is_full(self) -> bool:
        ret = self.inner_is_full()
        assert ret == (len(self.state.keys) >= self.state.capacity)
        return ret

    # --- configure ---

    @transition(LRUCache.configure)
    def configure(self, capacity: int) -> None:
        require_arg(capacity, Domain.type(int), preferred=[10])
        ret: Any = None
        if capacity <= 0:
            with raises(CacheCapacityError):
                ret = self.inner_configure(capacity)
            return ret
        self.state.capacity = capacity
        evictions_needed = len(self.state.keys) - self.state.capacity
        for _ in range(evictions_needed):
            evicted_key = self.state.keys.pop(0)
            del self.state.values[evicted_key]
            self.state.evictions += 1
        ret = self.inner_configure(capacity)
        assert ret is None
        return ret

    # --- get ---

    @transition(LRUCache.get)
    def get(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, Domain.type(str), preferred=["key"])
        require_arg(default, Domain.optional(Domain.type(object)), preferred=[None])
        if key in self.state.values:
            self.state.keys.remove(key)
            self.state.keys.append(key)
            self.state.hits += 1
            ret = self.inner_get(key, default)
            assert ret == self.state.values[key]
            assert self.state.hits > 0
            return ret
        else:
            self.state.misses += 1
            ret = self.inner_get(key, default)
            assert ret == default
            return ret

    # --- put ---

    @transition(LRUCache.put)
    def put(self, key: str, value: Any) -> Optional[Tuple[str, Any]]:
        require_arg(key, Domain.type(str), preferred=["key"])
        require_arg(value, Domain.any(), preferred=[1])
        if key in self.state.values:
            self.state.values[key] = value
            self.state.keys.remove(key)
            self.state.keys.append(key)
            ret = self.inner_put(key, value)
            assert ret is None
            return ret
        elif len(self.state.keys) >= self.state.capacity:
            evicted_key = self.state.keys.pop(0)
            evicted_value = self.state.values.pop(evicted_key)
            self.state.evictions += 1
            self.state.values[key] = value
            self.state.keys.append(key)
            ret = self.inner_put(key, value)
            assert ret == (evicted_key, evicted_value)
            return ret
        else:
            self.state.values[key] = value
            self.state.keys.append(key)
            ret = self.inner_put(key, value)
            assert ret is None
            return ret

    # --- peek ---

    @transition(LRUCache.peek)
    def peek(self, key: str, default: Optional[Any]) -> Any:
        require_arg(key, Domain.type(str), preferred=["key"])
        require_arg(default, Domain.optional(Domain.type(object)), preferred=[None])
        if key in self.state.values:
            ret = self.inner_peek(key, default)
            assert ret == self.state.values[key]
            assert ret == self.state.values[key]
            return ret
        else:
            ret = self.inner_peek(key, default)
            assert ret == default
            return ret

    # --- remove ---

    @transition(LRUCache.remove)
    def remove(self, key: str) -> Any:
        require_arg(key, Domain.type(str), preferred=["key"])
        ret: Any = None
        if key not in self.state.values:
            with raises(CacheKeyNotFoundError):
                ret = self.inner_remove(key)
            return ret
        removed_value = self.state.values.pop(key)
        self.state.keys.remove(key)
        ret = self.inner_remove(key)
        assert ret == removed_value
        return ret

    # --- clear ---

    @transition(LRUCache.clear)
    def clear(self) -> None:
        self.state.keys.clear()
        self.state.values.clear()
        ret = self.inner_clear()
        assert ret is None
        return ret

    # --- get_stats ---

    @transition(LRUCache.get_stats)
    def get_stats(self) -> CacheStats:
        ret = self.inner_get_stats()
        assert ret.hits == self.state.hits
        assert ret.misses == self.state.misses
        assert ret.evictions == self.state.evictions
        return ret

    # --- reset_stats ---

    @transition(LRUCache.reset_stats)
    def reset_stats(self) -> None:
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        ret = self.inner_reset_stats()
        assert ret is None
        return ret

    # --- keys_in_lru_order ---

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(self) -> List[str]:
        ret = self.inner_keys_in_lru_order()
        assert ret == list(self.state.keys)
        return ret

    # --- seeding transitions ---

    @transition.seeding
    def seed_entries(self, count: int) -> None:
        """Seed the state with entries for testing."""
        for i in range(count):
            key = f"seed_{i}"
            value = f"val_{i}"
            if key not in self.state.values:
                if len(self.state.keys) >= self.state.capacity:
                    evicted_key = self.state.keys.pop(0)
                    self.state.values.pop(evicted_key)
                    self.state.evictions += 1
                self.state.values[key] = value
                self.state.keys.append(key)


proto = LruCacheStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeLruCache = synthesize_fake(LruCacheStateMachine)


def make_lru_cache_fake(
    state: Optional[LruCacheState] = None,
) -> LRUCache:
    """Synthesizes fake instance for component service."""
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
        # Property transitions
        _ = self.sm.capacity
        _ = self.sm.size
        _ = self.sm.is_empty
        _ = self.sm.is_full
        # configure
        self.sm.configure(10)
        _ = self.sm.capacity
        # put (insert below capacity)
        self.sm.put("key1", "value1")
        self.sm.put("key2", "value2")
        _ = self.sm.size
        # get (hit)
        _ = self.sm.get("key1", None)
        # get (miss)
        _ = self.sm.get("missing", "default")
        # peek (present)
        _ = self.sm.peek("key2", None)
        # peek (absent)
        _ = self.sm.peek("missing", "default")
        # remove (existing)
        self.sm.remove("key1")
        # configure with downsize eviction
        self.sm.configure(1)
        _ = self.sm.size
        # get_stats
        stats = self.sm.get_stats()
        # reset_stats
        self.sm.reset_stats()
        _ = self.sm.get_stats()
        # clear
        self.sm.clear()
        _ = self.sm.is_empty
        # keys_in_lru_order
        _ = self.sm.keys_in_lru_order()
        # seeding
        self.sm.seed_entries(3)
        _ = self.sm.size
        _ = self.sm.keys_in_lru_order()

    def test_put_update_existing(self) -> None:
        """Exercise the put-update-existing path."""
        self.sm.configure(10)
        self.sm.put("key1", "old")
        result = self.sm.put("key1", "new")
        assert result is None

    def test_put_evict_on_capacity(self) -> None:
        """Exercise the put-eviction path."""
        self.sm.configure(2)
        self.sm.put("a", "1")
        self.sm.put("b", "2")
        result = self.sm.put("c", "3")
        assert result is not None

    def test_clear_preserves_telemetry(self) -> None:
        """Verify clear preserves telemetry counters."""
        self.sm.configure(10)
        self.sm.put("a", "1")
        _ = self.sm.get("a", None)
        _ = self.sm.get("a", None)
        self.sm.clear()
        stats = self.sm.get_stats()
        assert stats.hits > 0
        assert stats.misses == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeLruCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeLruCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:29:33Z
# LAST_CHANGED: 2026-11-09T22:29:33Z
# CHANGE: Added missing require_arg(value, Domain.any(), preferred=[1]) to put transition to satisfy pre.missing_require_arg feedback for the value parameter
# --- END AUTOFAB METADATA ---
