"""Unit tests for lru_cache_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)
from lru_cache.lib.lru_cache_impl import LRUCache, __initialize__


class LruCacheImplTest(unittest.TestCase):
    """Verifies the LRUCache singleton against its low-level behavioral contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.scope = self.enterContext(enter_phase(system, registry=self.registry))

    def test_initial_state_is_empty_cache(self) -> None:
        """Happy path: a fresh cache is empty and reports the default capacity limit."""
        cache = self.scope.get_singleton(LRUCache)
        self.assertEqual(cache.capacity, 100)
        self.assertEqual(cache.size, 0)
        self.assertTrue(cache.is_empty)
        self.assertFalse(cache.is_full)
        self.assertEqual(cache.keys_in_lru_order(), [])
        self.assertEqual(cache.get_stats(), CacheStats())

    def test_get_hit_returns_value_and_promotes_key(self) -> None:
        """A present key returns its value, becomes most-recently-used, and counts as a hit."""
        cache = self.scope.get_singleton(LRUCache)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertEqual(cache.keys_in_lru_order(), ["a", "b", "c"])
        self.assertEqual(cache.get("a", None), 1)
        self.assertEqual(cache.keys_in_lru_order(), ["b", "c", "a"])
        self.assertEqual(cache.get_stats(), CacheStats(hits=1, misses=0, evictions=0))
        self.assertEqual(cache.size, 3)

    def test_get_miss_returns_default_without_reordering(self) -> None:
        """An absent key returns the default, counts a miss, and leaves access order unchanged."""
        cache = self.scope.get_singleton(LRUCache)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertIsNone(cache.get("missing", None))
        self.assertEqual(cache.get("other", "fallback"), "fallback")
        self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
        self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=2, evictions=0))
        self.assertEqual(cache.size, 2)

    def test_put_update_existing_returns_none_without_growing(self) -> None:
        """An existing key is updated and promoted without growing the cache or evicting."""
        cache = self.scope.get_singleton(LRUCache)
        cache.configure(2)
        self.assertIsNone(cache.put("a", 1))
        self.assertIsNone(cache.put("b", 2))
        self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
        cache.get("a", None)
        self.assertEqual(cache.keys_in_lru_order(), ["b", "a"])
        self.assertIsNone(cache.put("a", 10))
        self.assertEqual(cache.size, 2)
        self.assertEqual(cache.keys_in_lru_order(), ["b", "a"])
        self.assertEqual(cache.get("a", None), 10)
        self.assertEqual(cache.get_stats().evictions, 0)

    def test_put_new_key_below_capacity_inserts_at_mru(self) -> None:
        """A new key below capacity is stored as most-recently-used, grows size, and returns None."""
        cache = self.scope.get_singleton(LRUCache)
        cache.configure(3)
        self.assertTrue(cache.is_empty)
        self.assertIsNone(cache.put("a", 1))
        self.assertEqual(cache.size, 1)
        self.assertFalse(cache.is_empty)
        self.assertFalse(cache.is_full)
        self.assertIsNone(cache.put("b", 2))
        self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
        self.assertEqual(cache.size, 2)
        self.assertFalse(cache.is_full)
        self.assertEqual(cache.get_stats(), CacheStats())

    def test_put_new_key_at_capacity_evicts_lru_and_returns_entry(self) -> None:
        """A new key at capacity evicts the least-recently-used entry and returns its pair."""
        cache = self.scope.get_singleton(LRUCache)
        cache.configure(2)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertTrue(cache.is_full)
        self.assertEqual(cache.put("c", 3), ("a", 1))
        self.assertEqual(cache.size, 2)
        self.assertEqual(cache.keys_in_lru_order(), ["b", "c"])
        self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=0, evictions=1))
        self.assertIsNone(cache.peek("a", None))
        self.assertEqual(cache.peek("c", None), 3)

    def test_configure_updates_capacity_limit(self) -> None:
        """Configuring a new capacity updates the reported limit and fullness threshold."""
        cache = self.scope.get_singleton(LRUCache)
        cache.configure(4)
        self.assertEqual(cache.capacity, 4)
        self.assertTrue(cache.is_empty)
        self.assertFalse(cache.is_full)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertFalse(cache.is_full)
        cache.put("d", 4)
        self.assertTrue(cache.is_full)
        self.assertEqual(cache.size, 4)

    def test_configure_downsize_evicts_lru_entries_in_sequence(self) -> None:
        """Shrinking capacity evicts least-recently-used entries until size equals capacity."""
        cache = self.scope.get_singleton(LRUCache)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.configure(2)
        self.assertEqual(cache.capacity, 2)
        self.assertEqual(cache.size, 2)
        self.assertEqual(cache.keys_in_lru_order(), ["b", "c"])
        self.assertTrue(cache.is_full)
        self.assertEqual(cache.get_stats().evictions, 1)
        cache.configure(1)
        self.assertEqual(cache.capacity, 1)
        self.assertEqual(cache.size, 1)
        self.assertEqual(cache.keys_in_lru_order(), ["c"])
        self.assertEqual(cache.get_stats().evictions, 2)
        cache.configure(5)
        self.assertEqual(cache.capacity, 5)
        self.assertEqual(cache.size, 1)
        self.assertFalse(cache.is_full)
        self.assertEqual(cache.get_stats().evictions, 2)

    def test_configure_rejects_non_positive_capacity(self) -> None:
        """Non-positive capacities are rejected with CacheCapacityError."""
        cache = self.scope.get_singleton(LRUCache)
        with self.assertRaises(CacheCapacityError):
            cache.configure(0)
        with self.assertRaises(CacheCapacityError):
            cache.configure(-5)

    def test_peek_present_key_returns_value_without_mutation(self) -> None:
        """A present key is returned without promoting it or touching telemetry."""
        cache = self.scope.get_singleton(LRUCache)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.peek("a", None), 1)
        self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
        self.assertEqual(cache.get_stats(), CacheStats())
        self.assertEqual(cache.size, 2)

    def test_peek_absent_key_returns_default_without_mutation(self) -> None:
        """An absent key returns the default without promoting anything or touching telemetry."""
        cache = self.scope.get_singleton(LRUCache)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertIsNone(cache.peek("missing", None))
        self.assertEqual(cache.peek("missing", "fallback"), "fallback")
        self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
        self.assertEqual(cache.get_stats(), CacheStats())
        self.assertEqual(cache.size, 2)

    def test_remove_existing_key_returns_value(self) -> None:
        """An existing entry is removed, the size is decremented, and its value is returned."""
        cache = self.scope.get_singleton(LRUCache)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.remove("a"), 1)
        self.assertEqual(cache.size, 1)
        self.assertEqual(cache.keys_in_lru_order(), ["b"])
        self.assertIsNone(cache.peek("a", None))

    def test_remove_missing_key_raises(self) -> None:
        """Removing an absent key raises CacheKeyNotFoundError and leaves entries intact."""
        cache = self.scope.get_singleton(LRUCache)
        cache.put("a", 1)
        with self.assertRaises(CacheKeyNotFoundError):
            cache.remove("missing")
        self.assertEqual(cache.size, 1)
        self.assertEqual(cache.keys_in_lru_order(), ["a"])

    def test_clear_removes_entries_and_preserves_telemetry(self) -> None:
        """Clearing removes every entry while preserving cumulative telemetry counters."""
        cache = self.scope.get_singleton(LRUCache)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a", None)
        cache.get("missing", None)
        cache.configure(1)
        self.assertEqual(cache.get_stats(), CacheStats(hits=1, misses=1, evictions=1))
        cache.clear()
        self.assertEqual(cache.size, 0)
        self.assertTrue(cache.is_empty)
        self.assertEqual(cache.keys_in_lru_order(), [])
        self.assertEqual(cache.get_stats(), CacheStats(hits=1, misses=1, evictions=1))
        self.assertEqual(cache.capacity, 1)

    def test_get_stats_reports_cumulative_telemetry(self) -> None:
        """Telemetry statistics aggregate hits, misses, and evictions."""
        cache = self.scope.get_singleton(LRUCache)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a", None)
        cache.get("a", None)
        cache.get("missing", None)
        cache.configure(1)
        stats = cache.get_stats()
        self.assertEqual(stats, CacheStats(hits=2, misses=1, evictions=1))
        self.assertEqual(stats.hits, 2)
        self.assertEqual(stats.misses, 1)
        self.assertEqual(stats.evictions, 1)

    def test_reset_stats_zeroes_telemetry_and_keeps_entries(self) -> None:
        """Resetting telemetry zeroes the counters while keeping cached entries."""
        cache = self.scope.get_singleton(LRUCache)
        cache.put("a", 1)
        cache.get("a", None)
        cache.get("missing", None)
        self.assertEqual(cache.get_stats(), CacheStats(hits=1, misses=1, evictions=0))
        cache.reset_stats()
        self.assertEqual(cache.get_stats(), CacheStats())
        self.assertEqual(cache.size, 1)
        self.assertEqual(cache.keys_in_lru_order(), ["a"])
        self.assertEqual(cache.peek("a", None), 1)

    def test_keys_in_lru_order_reflects_recency_without_mutation(self) -> None:
        """Keys are ordered from least- to most-recently-used and querying them is read-only."""
        cache = self.scope.get_singleton(LRUCache)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertEqual(cache.keys_in_lru_order(), ["a", "b", "c"])
        cache.get("a", None)
        self.assertEqual(cache.keys_in_lru_order(), ["b", "c", "a"])
        cache.peek("b", None)
        self.assertEqual(cache.keys_in_lru_order(), ["b", "c", "a"])
        cache.put("b", 20)
        self.assertEqual(cache.keys_in_lru_order(), ["c", "a", "b"])
        self.assertEqual(cache.keys_in_lru_order(), ["c", "a", "b"])
        self.assertEqual(cache.get_stats(), CacheStats(hits=1, misses=0, evictions=0))
        self.assertEqual(cache.size, 3)

    def test_invariants_hold_across_operations(self) -> None:
        """Size tracks entry count and is_empty/is_full track size against capacity."""
        cache = self.scope.get_singleton(LRUCache)
        cache.configure(2)
        self.assertTrue(cache.is_empty)
        self.assertEqual(cache.size, 0)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertFalse(cache.is_empty)
        self.assertTrue(cache.is_full)
        self.assertEqual(cache.size, 2)
        self.assertEqual(len(cache.keys_in_lru_order()), cache.size)
        cache.remove("a")
        self.assertEqual(cache.size, 1)
        self.assertFalse(cache.is_full)
        self.assertEqual(len(cache.keys_in_lru_order()), cache.size)
        cache.clear()
        self.assertEqual(cache.size, 0)
        self.assertTrue(cache.is_empty)
        self.assertFalse(cache.is_full)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T17:02:34Z
# LAST_CHANGED: 2026-11-10T17:01:54Z
# CHANGE: Implemented comprehensive lifecycle-scoped unit tests for LRUCache covering all contracted postconditions: initial state/capacity, get hit/miss, put update/insert/evict branches, configure update/downsize/invalid-capacity, peek present/absent, remove existing/missing, clear with telemetry preservation, stats reporting/reset, LRU key ordering and non-mutation, plus cross-operation invariants.
# COVERAGE_AUDIT: 2026-11-10T17:02:34Z
# QA_AUDIT: 2026-11-10T17:02:21Z
# --- END AUTOFAB METADATA ---
