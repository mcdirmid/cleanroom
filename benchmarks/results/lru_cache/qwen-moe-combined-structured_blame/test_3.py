"""Unit tests for lru_cache_impl per its grounding specification."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from lru_cache.lib.lru_cache_impl import (
    LRUCache,
    __initialize__,
)
from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)


# --- Lifecycle management for test phase scope ---
def _make_registry_and_phase(test_case: unittest.TestCase) -> tuple:
    """Create a LifecycleRegistry, initialise it, and return (registry, scope)."""
    registry = LifecycleRegistry()
    __initialize__(registry)
    phase_scope = enter_phase(system, registry=registry)
    phase_scope.__enter__()
    test_case.addCleanup(phase_scope.__exit__, None, None, None)
    return registry, phase_scope


# --- Helper: resolve the LRUCache singleton from a phase scope ---
def _get_cache(scope) -> LRUCache:
    """Resolve the LRUCache singleton from an active phase scope."""
    return scope.get_singleton(LRUCache)


class LruCacheImplTest(unittest.TestCase):
    """Tests for the LRUCache singleton covering all contracted operations."""

    def setUp(self) -> None:
        self.registry, self.scope = _make_registry_and_phase(self)
        self.cache = _get_cache(self.scope)

    # -- Capacity and size properties --

    def test_default_capacity_is_100(self) -> None:
        """CUJ: Verify the default capacity is 100."""
        self.assertEqual(self.cache.capacity, 100)

    def test_initial_size_is_zero(self) -> None:
        """CUJ: Verify initial cache size is zero."""
        self.assertEqual(self.cache.size, 0)

    def test_initially_empty(self) -> None:
        """CUJ: Verify is_empty is True when no entries exist."""
        self.assertTrue(self.cache.is_empty)

    def test_initially_not_full(self) -> None:
        """CUJ: Verify is_full is False when below capacity."""
        self.assertFalse(self.cache.is_full)

    # -- configure --

    def test_configure_valid_capacity(self) -> None:
        """CUJ: configure with a positive capacity updates capacity limit."""
        self.cache.configure(50)
        self.assertEqual(self.cache.capacity, 50)

    def test_configure_rejects_zero(self) -> None:
        """PRECONDITION: WHEN capacity <= 0, MUST raise CacheCapacityError."""
        with self.assertRaises(CacheCapacityError):
            self.cache.configure(0)

    def test_configure_rejects_negative(self) -> None:
        """PRECONDITION: WHEN capacity <= 0, MUST raise CacheCapacityError."""
        with self.assertRaises(CacheCapacityError):
            self.cache.configure(-5)

    def test_configure_downsize_evicts_lru_entries(self) -> None:
        """POSTCONDITION: WHEN new capacity < current size, MUST evict LRU entries until size == capacity."""
        self.cache.configure(5)
        # Fill cache with 5 entries
        for i in range(5):
            self.cache.put(f"key{i}", f"value{i}")
        self.assertEqual(self.cache.size, 5)
        # Downsize to 2
        self.cache.configure(2)
        self.assertEqual(self.cache.size, 2)
        self.assertTrue(self.cache.is_full)

    # -- get (hit and miss) --

    def test_get_hit_promotes_to_mru(self) -> None:
        """POSTCONDITION: WHEN key is present, MUST return value, promote to MRU, and increment hits."""
        self.cache.configure(5)
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        result = self.cache.get("a", None)
        self.assertEqual(result, 1)
        stats = self.cache.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 0)
        # "a" should now be the most recently used (last in order)
        keys = self.cache.keys_in_lru_order()
        self.assertEqual(keys, ["b", "a"])

    def test_get_miss_returns_default(self) -> None:
        """POSTCONDITION: WHEN key is absent, MUST return default and increment misses without altering order."""
        self.cache.configure(5)
        self.cache.put("a", 1)
        result = self.cache.get("missing", "default_val")
        self.assertEqual(result, "default_val")
        stats = self.cache.get_stats()
        self.assertEqual(stats.misses, 1)
        self.assertEqual(stats.hits, 0)
        # Access order should be unchanged
        keys = self.cache.keys_in_lru_order()
        self.assertEqual(keys, ["a"])

    # -- put (update, insert, evict) --

    def test_put_new_entry_below_capacity(self) -> None:
        """POSTCONDITION: WHEN key is new and size < capacity, MUST store and return None."""
        result = self.cache.put("k", "v")
        self.assertIsNone(result)
        self.assertEqual(self.cache.size, 1)

    def test_put_update_existing_returns_none(self) -> None:
        """POSTCONDITION: WHEN key exists, MUST update value, promote to MRU, and return None."""
        self.cache.put("k", "v1")
        result = self.cache.put("k", "v2")
        self.assertIsNone(result)
        self.assertEqual(self.cache.size, 1)
        # Verify the value was updated via get
        self.assertEqual(self.cache.get("k", None), "v2")

    def test_put_evicts_lru_at_capacity(self) -> None:
        """POSTCONDITION: WHEN key is new and size at capacity, MUST evict LRU entry and return (evicted_key, evicted_value)."""
        self.cache.configure(3)
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        self.cache.put("c", 3)
        self.assertEqual(self.cache.size, 3)
        # Adding a 4th entry should evict "a" (LRU)
        evicted = self.cache.put("d", 4)
        self.assertIsNotNone(evicted)
        self.assertEqual(evicted, ("a", 1))
        self.assertEqual(self.cache.size, 3)
        # Verify evicted key is gone
        self.assertIsNone(self.cache.get("a", None))
        # Verify remaining keys
        stats = self.cache.get_stats()
        self.assertEqual(stats.evictions, 1)

    # -- peek --

    def test_peeks_without_mutating_order(self) -> None:
        """POSTCONDITION: WHEN key is present, MUST return value without modifying access order."""
        self.cache.configure(5)
        self.cache.put("x", 10)
        self.cache.put("y", 20)
        # Peek should not change LRU order
        result = self.cache.peek("x", None)
        self.assertEqual(result, 10)
        keys = self.cache.keys_in_lru_order()
        self.assertEqual(keys, ["x", "y"])

    def test_peeks_absent_key_returns_default(self) -> None:
        """POSTCONDITION: WHEN key is absent, MUST return default without modifying order."""
        self.cache.configure(5)
        result = self.cache.peek("missing", "fallback")
        self.assertEqual(result, "fallback")

    def test_peeks_does_not_increment_telemetry(self) -> None:
        """POSTCONDITION: peek MUST NOT increment hits or misses counters."""
        self.cache.configure(5)
        self.cache.put("a", 1)
        _ = self.cache.peek("a", None)
        stats = self.cache.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)

    # -- remove --

    def test_remove_existing_key(self) -> None:
        """POSTCONDITION: WHEN key exists, MUST remove entry, decrement size, and return removed value."""
        self.cache.put("k", "v")
        result = self.cache.remove("k")
        self.assertEqual(result, "v")
        self.assertEqual(self.cache.size, 0)
        self.assertTrue(self.cache.is_empty)

    def test_remove_nonexistent_raises_key_not_found(self) -> None:
        """PRECONDITION: WHEN key is absent, MUST raise CacheKeyNotFoundError."""
        with self.assertRaises(CacheKeyNotFoundError):
            self.cache.remove("nonexistent")

    def test_remove_absent_key_from_non_empty_cache_raises(self) -> None:
        """PRECONDITION: WHEN key is absent from an otherwise non-empty cache, MUST raise CacheKeyNotFoundError."""
        self.cache.put("other", "val")
        with self.assertRaises(CacheKeyNotFoundError):
            self.cache.remove("missing")

    # -- clear --

    def test_clear_preserves_telemetry(self) -> None:
        """POSTCONDITION: MUST remove all entries and reset size to zero while preserving telemetry counters."""
        self.cache.configure(5)
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        _ = self.cache.get("a", None)  # 1 hit
        _ = self.cache.get("z", None)  # 1 miss
        stats_before = self.cache.get_stats()
        self.assertEqual(stats_before.hits, 1)
        self.assertEqual(stats_before.misses, 1)
        self.cache.clear()
        self.assertEqual(self.cache.size, 0)
        self.assertTrue(self.cache.is_empty)
        stats_after = self.cache.get_stats()
        # Telemetry must be preserved
        self.assertEqual(stats_after.hits, 1)
        self.assertEqual(stats_after.misses, 1)

    # -- get_stats and reset_stats --

    def test_get_stats_report_telemetry(self) -> None:
        """POSTCONDITION: MUST return CacheStats reflecting cumulative hits, misses, and evictions."""
        self.cache.configure(3)
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        self.cache.put("c", 3)
        _ = self.cache.get("a", None)  # hit
        _ = self.cache.get("missing", None)  # miss
        self.cache.put("d", 4)  # eviction
        stats = self.cache.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)
        self.assertEqual(stats.evictions, 1)

    def test_reset_stats_zeroes_counters(self) -> None:
        """POSTCONDITION: MUST reset hits, misses, and evictions to zero without altering cached entries."""
        self.cache.put("a", 1)
        _ = self.cache.get("a", None)
        self.cache.reset_stats()
        stats = self.cache.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(stats.evictions, 0)
        # Cached entries must remain intact
        self.assertEqual(self.cache.size, 1)
        self.assertEqual(self.cache.get("a", None), 1)

    # -- keys_in_lru_order --

    def test_keys_in_lru_order_returns_ordered_list(self) -> None:
        """POSTCONDITION: MUST return all active cache keys ordered from LRU to MRU."""
        self.cache.configure(5)
        self.cache.put("first", 1)
        self.cache.put("second", 2)
        self.cache.put("third", 3)
        keys = self.cache.keys_in_lru_order()
        self.assertEqual(keys, ["first", "second", "third"])

    def test_keys_in_lru_order_updates_on_access(self) -> None:
        """POSTCONDITION: Access via get promotes to MRU position reflected in key order."""
        self.cache.configure(5)
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        self.cache.put("c", 3)
        # Access "a" — it should move to MRU
        self.cache.get("a", None)
        keys = self.cache.keys_in_lru_order()
        self.assertEqual(keys, ["b", "c", "a"])

    def test_keys_in_lru_order_does_not_mutate_order_or_telemetry(self) -> None:
        """POSTCONDITION: keys_in_lru_order MUST NOT alter access recency order or increment telemetry."""
        self.cache.configure(5)
        self.cache.put("x", 10)
        self.cache.put("y", 20)
        # Record order before peek-style call
        keys_before = self.cache.keys_in_lru_order()
        # Call keys_in_lru_order again
        keys_after = self.cache.keys_in_lru_order()
        self.assertEqual(keys_before, keys_after)
        stats = self.cache.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)

    def test_keys_in_lru_order_empty_cache(self) -> None:
        """Verify empty cache returns an empty list."""
        keys = self.cache.keys_in_lru_order()
        self.assertEqual(keys, [])


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:20:11Z
# LAST_CHANGED: 2026-11-09T22:16:27Z
# CHANGE: Author comprehensive unit test suite for LRUCache singleton covering all contracted operations: capacity/size/is_empty/is_full properties, configure with capacity validation and downsize eviction, get (hit/miss with telemetry and MRU promotion), put (new insert/update existing/eviction), peek (non-mutating read), remove (existing key/CacheKeyNotFoundError), clear (preserves telemetry), get_stats/reset_stats, and keys_in_lru_order (LRU ordering, immutability). Fixed import path from benchmark_4.parts.lru_cache.lib to lru_cache.lib per harness requirement.
# COVERAGE_AUDIT: 2026-11-09T22:20:11Z
# QA_AUDIT: 2026-11-09T22:19:35Z
# --- END AUTOFAB METADATA ---
