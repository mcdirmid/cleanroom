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
from benchmark_3.parts.lru_cache.pretense.lru_cache_pretense import (
    LruCacheStateMachine,
    LruCacheState,
    FakeLruCache,
    make_lru_cache_fake,
)
from benchmark_3.parts.lru_cache.lib.lru_cache_impl import LRUCache, __initialize__


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
        # Verify property accessors on empty cache
        self.assertTrue(self.checked.capacity >= 0)
        self.assertEqual(self.checked.size, 0)
        self.assertTrue(self.checked.is_empty)
        self.assertFalse(self.checked.is_full)

        # Set initial capacity, fill to 5, then downsize to trigger eviction
        self.checked.configure(5)
        self.assertIsNone(self.checked.put("a", 1))
        self.assertIsNone(self.checked.put("b", 2))
        self.assertIsNone(self.checked.put("c", 3))
        self.assertIsNone(self.checked.put("d", 4))
        self.assertIsNone(self.checked.put("e", 5))
        self.assertEqual(self.checked.size, 5)
        self.assertTrue(self.checked.is_full)

        # Downsize eviction: capacity 5 -> 2, must evict 3 LRU entries
        stats_before = self.checked.get_stats()
        self.checked.configure(2)
        self.assertEqual(self.checked.size, 2)
        self.assertTrue(self.checked.is_full)
        self.assertFalse(self.checked.is_empty)
        stats_after = self.checked.get_stats()
        self.assertEqual(stats_after.evictions, stats_before.evictions + 3)

        # Verify remaining keys are the 2 most-recently-used (d, e)
        keys = self.checked.keys_in_lru_order()
        self.assertEqual(keys, ["d", "e"])

        # Verify evicted keys are gone
        self.assertEqual(self.checked.get("a", "FOUND"), "FOUND")
        self.assertEqual(self.checked.get("b", "FOUND"), "FOUND")
        self.assertEqual(self.checked.get("c", "FOUND"), "FOUND")

        # get - hit case (promotes to MRU)
        val = self.checked.get("d", None)
        self.assertEqual(val, 4)
        self.assertEqual(self.checked.size, 2)

        # get - miss case
        val = self.checked.get("missing", "default")
        self.assertEqual(val, "default")

        # peek - present key (no order change)
        val = self.checked.peek("e", None)
        self.assertEqual(val, 5)

        # peek - absent key
        val = self.checked.peek("missing", None)
        self.assertEqual(val, None)

        # put - update existing
        self.assertIsNone(self.checked.put("d", 10))

        # put - evict on capacity reached (2 -> 3)
        result = self.checked.put("f", 6)
        assert result is not None
        self.assertEqual(result[0], "e")
        self.assertEqual(self.checked.size, 2)

        # Remove existing key
        val = self.checked.remove("d")
        self.assertEqual(val, 10)
        self.assertEqual(self.checked.size, 1)

        # Verify telemetry
        stats = self.checked.get_stats()
        self.assertGreater(stats.hits, 0)
        self.assertGreater(stats.misses, 0)

        # Reset stats
        self.checked.reset_stats()
        stats = self.checked.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(stats.evictions, 0)

        # Clear preserves telemetry
        self.checked.clear()
        self.assertEqual(self.checked.size, 0)
        self.assertTrue(self.checked.is_empty)

        # Contract violations
        with self.assertRaises(Exception):
            self.checked.configure(0)

        with self.assertRaises(Exception):
            self.checked.remove("nonexistent")

        # keys_in_lru_order
        self.checked.configure(10)
        self.checked.put("x", 1)
        self.checked.put("y", 2)
        self.checked.put("z", 3)
        keys = self.checked.keys_in_lru_order()
        self.assertEqual(keys, ["x", "y", "z"])


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
# LAST_CLEANED: 2026-11-09T07:48:28Z
# LAST_CHANGED: 2026-11-09T07:40:13Z
# CHANGE: Fixed incorrect assertFalse(is_full) assertion after downsize eviction test — after configure(2) with 2 remaining entries, size equals capacity so is_full must be True.
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T07:48:28Z
# PRETENSE_QA_AUDIT: 2026-11-09T07:47:30Z
# --- END AUTOFAB METADATA ---


# === File: lru_cache_pretense.py ===
"""Pretense state machine, fake synthesis, and property fuzzing for LruCache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Set, Tuple

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
    capacity: int = 0
    items: dict[str, Any] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
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

    # -- property transitions --

    @transition(name="capacity")
    def capacity(self) -> int:
        return self.inner_capacity()

    @transition(name="size")
    def size(self) -> int:
        return self.inner_size()

    @transition(name="is_empty")
    def is_empty(self) -> bool:
        return self.inner_is_empty()

    @transition(name="is_full")
    def is_full(self) -> bool:
        return self.inner_is_full()

    # -- operation transitions --

    @transition(LRUCache.configure)
    def configure(
        self,
        capacity: int,
    ) -> None:
        require_arg(capacity, Domain.type(int))
        if capacity <= 0:
            ret = None
            with raises(CacheCapacityError):
                ret = self.inner_configure(capacity)
            return ret
        old_items = self.state.items
        old_order = self.state.order
        self.state.capacity = capacity
        if capacity < len(old_items):
            evict_count = len(old_items) - capacity
            evict_keys = old_order[:evict_count]
            for k in evict_keys:
                del old_items[k]
            self.state.evictions += evict_count
            self.state.order = old_order[evict_count:]
        ret = self.inner_configure(capacity)
        return ret

    @transition(LRUCache.get)
    def get(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require_arg(key, Domain.type(str))
        require_arg(default, Domain.optional(Domain.any()))
        if key in self.state.items:
            self.state.order.remove(key)
            self.state.order.append(key)
            self.state.hits += 1
            ret = self.inner_get(key, default)
            return ret
        else:
            self.state.misses += 1
            ret = self.inner_get(key, default)
            return ret

    @transition(LRUCache.put)
    def put(
        self,
        key: str,
        value: Any,
    ) -> Optional[Tuple[str, Any]]:
        require_arg(key, Domain.type(str))
        require_arg(value, Domain.any())
        if key in self.state.items:
            self.state.order.remove(key)
            self.state.items[key] = value
            self.state.order.append(key)
            ret = self.inner_put(key, value)
            assert ret is None
            return ret
        elif len(self.state.items) >= self.state.capacity and self.state.capacity > 0:
            lru_key = self.state.order.pop(0)
            evicted = self.state.items.pop(lru_key)
            self.state.evictions += 1
            self.state.items[key] = value
            self.state.order.append(key)
            ret = self.inner_put(key, value)
            assert ret is not None
            return ret
        else:
            self.state.items[key] = value
            self.state.order.append(key)
            ret = self.inner_put(key, value)
            assert ret is None
            return ret

    @transition(LRUCache.peek)
    def peek(
        self,
        key: str,
        default: Optional[Any],
    ) -> Any:
        require_arg(key, Domain.type(str))
        require_arg(default, Domain.optional(Domain.any()))
        if key in self.state.items:
            ret = self.inner_peek(key, default)
            return ret
        else:
            ret = self.inner_peek(key, default)
            return ret

    @transition(LRUCache.remove)
    def remove(
        self,
        key: str,
    ) -> Any:
        require_arg(key, Domain.type(str))
        if key not in self.state.items:
            ret = None
            with raises(CacheKeyNotFoundError):
                ret = self.inner_remove(key)
            return ret
        value = self.state.items.pop(key)
        self.state.order.remove(key)
        ret = self.inner_remove(key)
        return ret

    @transition(LRUCache.clear)
    def clear(self) -> None:
        self.state.items.clear()
        self.state.order.clear()
        ret = self.inner_clear()
        assert ret is None
        return ret

    @transition(LRUCache.get_stats)
    def get_stats(self) -> CacheStats:
        ret = self.inner_get_stats()
        assert ret is not None
        return ret

    @transition(LRUCache.reset_stats)
    def reset_stats(self) -> None:
        self.state.hits = 0
        self.state.misses = 0
        self.state.evictions = 0
        ret = self.inner_reset_stats()
        assert ret is None
        return ret

    @transition(LRUCache.keys_in_lru_order)
    def keys_in_lru_order(self) -> List[str]:
        ret = self.inner_keys_in_lru_order()
        assert ret is not None
        return ret


proto = LruCacheStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeLruCache = synthesize_fake(LruCacheStateMachine)


def make_lru_cache_fake(
    state: Optional[LruCacheState] = None,
) -> LRUCache:
    """Synthesizes a fake LruCache instance."""
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
        _ = self.sm.capacity()
        _ = self.sm.size()
        _ = self.sm.is_empty()
        _ = self.sm.is_full()

        # configure - sets capacity
        self.sm.configure(10)

        # get / peek - miss case
        _ = self.sm.get("missing_key", None)
        _ = self.sm.peek("missing_key", None)

        # put - insert entries
        self.sm.put("a", 1)
        self.sm.put("b", 2)
        self.sm.put("c", 3)

        # get / peek - hit case
        _ = self.sm.get("a", None)
        _ = self.sm.peek("b", None)

        # configure - eviction
        self.sm.configure(1)

        # configure - invalid capacity
        with self.assertRaises(CacheCapacityError):
            self.sm.configure(-1)

        # put - update existing
        self.sm.put("a", 100)

        # remove
        _ = self.sm.remove("a")

        # remove - missing key
        with self.assertRaises(CacheKeyNotFoundError):
            self.sm.remove("nonexistent")

        # get_stats and reset_stats
        _ = self.sm.get_stats()
        self.sm.reset_stats()

        # clear
        self.sm.clear()

        # keys_in_lru_order
        _ = self.sm.keys_in_lru_order()


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake
# ==============================================================================

FakeLruCacheFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeLruCacheFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T07:46:57Z
# LAST_CHANGED: 2026-11-09T07:46:57Z
# CHANGE: Fixed downsize eviction to remove LRU (oldest) entries instead of newest — evict_count = old_size - new_capacity, remove old_order[:evict_count] (front of LRU list), retain old_order[evict_count:] (MRU entries).
# --- END AUTOFAB METADATA ---
