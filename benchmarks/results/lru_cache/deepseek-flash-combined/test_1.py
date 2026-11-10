"""Unit tests for the concrete LRUCache implementation."""

from __future__ import annotations

import unittest

from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)
from lru_cache.lib.lru_cache_impl import LRUCache, __initialize__
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


class LruCacheImplTest(unittest.TestCase):
    """Exercises the system-tier LRUCache singleton within an isolated phase scope."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.cache = self.phase_scope.get_singleton(LRUCache)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_fresh_cache_defaults(self) -> None:
        """A fresh cache is empty and starts with the default capacity of 100."""
        self.assertEqual(self.cache.capacity, 100)
        self.assertEqual(self.cache.size, 0)
        self.assertTrue(self.cache.is_empty)
        self.assertFalse(self.cache.is_full)
        self.assertEqual(self.cache.keys_in_lru_order(), [])
        self.assertEqual(self.cache.get_stats(), CacheStats())

    def test_get_hit_returns_value_and_promotes(self) -> None:
        """A present key returns its value, becomes most recently used, and counts a hit."""
        self.cache.configure(3)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertIsNone(self.cache.put("c", 3))
        self.assertEqual(self.cache.keys_in_lru_order(), ["a", "b", "c"])
        self.assertEqual(self.cache.get("a", None), 1)
        self.assertEqual(self.cache.keys_in_lru_order(), ["b", "c", "a"])
        stats = self.cache.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(stats.evictions, 0)

    def test_get_miss_returns_default_and_counts(self) -> None:
        """An absent key returns the supplied default, counts a miss, and preserves order."""
        self.cache.configure(3)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertEqual(self.cache.get("absent", "fallback"), "fallback")
        self.assertEqual(self.cache.keys_in_lru_order(), ["a", "b"])
        stats = self.cache.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 1)

    def test_put_inserts_new_entry_below_capacity(self) -> None:
        """A new key below capacity returns None, grows the cache, and becomes most recently used."""
        self.cache.configure(3)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertEqual(self.cache.size, 1)
        self.assertEqual(self.cache.keys_in_lru_order(), ["a"])
        self.assertFalse(self.cache.is_empty)
        self.assertFalse(self.cache.is_full)
        self.assertIsNone(self.cache.put("b", 2))
        self.assertEqual(self.cache.size, 2)
        self.assertEqual(self.cache.keys_in_lru_order(), ["a", "b"])
        self.assertEqual(self.cache.get_stats().evictions, 0)

    def test_put_updates_existing_entry_without_growing(self) -> None:
        """Updating a present key replaces its value, becomes most recently used, and returns None."""
        self.cache.configure(3)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertIsNone(self.cache.put("a", 10))
        self.assertEqual(self.cache.size, 2)
        self.assertEqual(self.cache.keys_in_lru_order(), ["b", "a"])
        self.assertEqual(self.cache.get("a", None), 10)
        self.assertEqual(self.cache.get_stats().evictions, 0)

    def test_put_update_existing_at_capacity_does_not_evict(self) -> None:
        """Updating a present key at capacity never evicts an entry."""
        self.cache.configure(1)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("a", 2))
        self.assertEqual(self.cache.size, 1)
        self.assertEqual(self.cache.keys_in_lru_order(), ["a"])
        self.assertEqual(self.cache.get_stats().evictions, 0)

    def test_put_evicts_least_recently_used_at_capacity(self) -> None:
        """Inserting a new key at capacity evicts the least recently used entry and returns it."""
        self.cache.configure(2)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertTrue(self.cache.is_full)
        self.assertEqual(self.cache.put("c", 3), ("a", 1))
        self.assertEqual(self.cache.size, 2)
        self.assertEqual(self.cache.keys_in_lru_order(), ["b", "c"])
        self.assertIsNone(self.cache.peek("a", None))
        self.assertEqual(self.cache.get_stats().evictions, 1)

    def test_put_eviction_respects_promoted_recency(self) -> None:
        """A promoted key survives eviction while the stale least recently used key is evicted."""
        self.cache.configure(2)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertEqual(self.cache.get("a", None), 1)
        self.assertEqual(self.cache.keys_in_lru_order(), ["b", "a"])
        self.assertEqual(self.cache.put("c", 3), ("b", 2))
        self.assertEqual(self.cache.keys_in_lru_order(), ["a", "c"])
        stats = self.cache.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.evictions, 1)

    def test_is_full_tracks_capacity_limit(self) -> None:
        """The cache reports full exactly when its size reaches the capacity limit."""
        self.cache.configure(2)
        self.assertFalse(self.cache.is_full)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertFalse(self.cache.is_full)
        self.assertIsNone(self.cache.put("b", 2))
        self.assertTrue(self.cache.is_full)

    def test_peek_present_does_not_mutate_recency_or_telemetry(self) -> None:
        """Peeking a present key returns its value without changing recency or telemetry."""
        self.cache.configure(2)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertEqual(self.cache.peek("a", None), 1)
        self.assertEqual(self.cache.keys_in_lru_order(), ["a", "b"])
        self.assertEqual(self.cache.get_stats(), CacheStats())

    def test_peek_absent_returns_default_without_telemetry(self) -> None:
        """Peeking an absent key returns the default without changing recency or telemetry."""
        self.cache.configure(2)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertEqual(self.cache.peek("absent", "fallback"), "fallback")
        self.assertEqual(self.cache.keys_in_lru_order(), ["a"])
        self.assertEqual(self.cache.get_stats(), CacheStats())

    def test_remove_existing_entry_returns_value(self) -> None:
        """Removing a present key returns its value and shrinks the cache."""
        self.cache.configure(3)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertEqual(self.cache.remove("a"), 1)
        self.assertEqual(self.cache.size, 1)
        self.assertEqual(self.cache.keys_in_lru_order(), ["b"])
        self.assertEqual(self.cache.remove("b"), 2)
        self.assertEqual(self.cache.size, 0)
        self.assertTrue(self.cache.is_empty)
        self.assertEqual(self.cache.keys_in_lru_order(), [])

    def test_remove_absent_key_raises(self) -> None:
        """Removing an absent key raises the key-not-found error."""
        self.cache.configure(2)
        self.assertIsNone(self.cache.put("a", 1))
        with self.assertRaises(CacheKeyNotFoundError):
            self.cache.remove("absent")

    def test_configure_invalid_capacity_raises(self) -> None:
        """Configuring a non-positive capacity raises the capacity error."""
        with self.assertRaises(CacheCapacityError):
            self.cache.configure(0)
        with self.assertRaises(CacheCapacityError):
            self.cache.configure(-3)

    def test_configure_updates_capacity_limit(self) -> None:
        """Configuring a valid capacity updates the reported limit."""
        self.cache.configure(5)
        self.assertEqual(self.cache.capacity, 5)
        self.assertFalse(self.cache.is_full)
        self.cache.configure(7)
        self.assertEqual(self.cache.capacity, 7)

    def test_configure_downsize_evicts_lru_entries(self) -> None:
        """Shrinking capacity evicts least recently used entries one by one and counts evictions."""
        self.cache.configure(5)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertIsNone(self.cache.put("c", 3))
        self.assertIsNone(self.cache.put("d", 4))
        self.assertIsNone(self.cache.put("e", 5))
        self.assertEqual(self.cache.keys_in_lru_order(), ["a", "b", "c", "d", "e"])
        self.assertEqual(self.cache.get_stats().evictions, 0)
        self.cache.configure(2)
        self.assertEqual(self.cache.capacity, 2)
        self.assertEqual(self.cache.size, 2)
        self.assertEqual(self.cache.keys_in_lru_order(), ["d", "e"])
        self.assertEqual(self.cache.get_stats().evictions, 3)
        self.assertTrue(self.cache.is_full)

    def test_clear_removes_entries_and_preserves_telemetry(self) -> None:
        """Clearing drops every entry while preserving accumulated telemetry."""
        self.cache.configure(3)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertEqual(self.cache.get("a", None), 1)
        self.assertEqual(self.cache.get("absent", None), None)
        self.assertEqual(self.cache.get_stats(), CacheStats(hits=1, misses=1))
        self.cache.clear()
        self.assertEqual(self.cache.size, 0)
        self.assertTrue(self.cache.is_empty)
        self.assertEqual(self.cache.keys_in_lru_order(), [])
        self.assertEqual(self.cache.get_stats(), CacheStats(hits=1, misses=1))

    def test_reset_stats_zeroes_counters_preserving_entries(self) -> None:
        """Resetting telemetry zeroes the counters while keeping cached entries intact."""
        self.cache.configure(2)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertEqual(self.cache.get("a", None), 1)
        self.assertEqual(self.cache.get("absent", None), None)
        self.cache.reset_stats()
        self.assertEqual(self.cache.get_stats(), CacheStats())
        self.assertEqual(self.cache.size, 2)
        self.assertEqual(self.cache.keys_in_lru_order(), ["b", "a"])

    def test_get_stats_reports_hits_misses_evictions(self) -> None:
        """Statistics report the cumulative hit, miss, and eviction counts."""
        self.cache.configure(2)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertEqual(self.cache.get("a", None), 1)
        self.assertEqual(self.cache.put("c", 3), ("b", 2))
        self.assertEqual(self.cache.get("absent", None), None)
        stats = self.cache.get_stats()
        self.assertIsInstance(stats, CacheStats)
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)
        self.assertEqual(stats.evictions, 1)
        self.assertEqual(stats, CacheStats(hits=1, misses=1, evictions=1))

    def test_keys_in_lru_order_lists_lru_to_mru(self) -> None:
        """Keys are listed from least recently used to most recently used."""
        self.cache.configure(4)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertIsNone(self.cache.put("c", 3))
        self.assertEqual(self.cache.keys_in_lru_order(), ["a", "b", "c"])
        self.assertEqual(self.cache.get("a", None), 1)
        self.assertEqual(self.cache.keys_in_lru_order(), ["b", "c", "a"])
        self.assertEqual(self.cache.peek("b", None), 2)
        self.assertEqual(self.cache.keys_in_lru_order(), ["b", "c", "a"])

    def test_keys_in_lru_order_is_non_mutating(self) -> None:
        """Repeated key listings preserve recency order and telemetry counters."""
        self.cache.configure(3)
        self.assertIsNone(self.cache.put("a", 1))
        self.assertIsNone(self.cache.put("b", 2))
        self.assertIsNone(self.cache.put("c", 3))
        self.assertEqual(self.cache.get("a", None), 1)
        before = self.cache.get_stats()
        self.assertEqual(self.cache.keys_in_lru_order(), ["b", "c", "a"])
        self.assertEqual(self.cache.keys_in_lru_order(), ["b", "c", "a"])
        self.assertEqual(self.cache.get_stats(), before)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T21:26:20Z
# LAST_CHANGED: 2026-11-09T21:25:45Z
# CHANGE: Resolved QA feedback: test_reset_stats_zeroes_counters_preserving_entries now expects the recency order ['b','a'], matching the get-hit promotion contract (get('a') moves 'a' to most-recently-used) and confirming reset_stats leaves entries and their order untouched. Audited every other keys_in_lru_order assertion for the same promotion logic; all are consistent.
# COVERAGE_AUDIT: 2026-11-09T21:26:20Z
# QA_AUDIT: 2026-11-09T21:26:07Z
# --- END AUTOFAB METADATA ---
