"""Unit tests for lru_cache_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)
from lru_cache.lib.lru_cache_impl import (
    LRUCache,
    __initialize__,
)


class LruCacheImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_default_state_after_initialization(self) -> None:
        """INVARIANT: a fresh cache is empty and defaults to a capacity limit of 100."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            self.assertEqual(cache.capacity, 100)
            self.assertEqual(cache.size, 0)
            self.assertTrue(cache.is_empty)
            self.assertFalse(cache.is_full)
            self.assertEqual(cache.keys_in_lru_order(), [])

    def test_put_insert_below_capacity(self) -> None:
        """A new key below capacity is stored as most-recently-used and put returns None."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(4)
            self.assertIsNone(cache.put("a", 1))
            self.assertEqual(cache.size, 1)
            self.assertFalse(cache.is_empty)
            self.assertFalse(cache.is_full)
            self.assertEqual(cache.peek("a", None), 1)
            self.assertIsNone(cache.put("b", 2))
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])

    def test_put_update_existing(self) -> None:
        """Updating an existing key replaces its value, promotes it, and leaves size unchanged."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(4)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertIsNone(cache.put("a", 9))
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.peek("a", None), 9)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "a"])
            stats = cache.get_stats()
            self.assertEqual(stats.evictions, 0)

    def test_put_evict_on_capacity(self) -> None:
        """Inserting at capacity evicts the least-recently-used entry and returns the (key, value) tuple."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(2)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertTrue(cache.is_full)
            evicted = cache.put("c", 3)
            self.assertEqual(evicted, ("a", 1))
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "c"])
            self.assertIsNone(cache.peek("a", None))
            self.assertEqual(cache.get_stats().evictions, 1)

    def test_get_hit(self) -> None:
        """A cache hit returns the stored value, promotes the key, and increments the hits counter."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(4)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertEqual(cache.get("a", None), 1)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "a"])
            self.assertEqual(cache.get_stats().hits, 1)

    def test_get_miss(self) -> None:
        """A cache miss returns the default, increments the misses counter, and keeps access order."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(4)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertEqual(cache.get("missing", "fallback"), "fallback")
            self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
            stats = cache.get_stats()
            self.assertEqual(stats.misses, 1)
            self.assertEqual(stats.hits, 0)
            self.assertEqual(cache.size, 2)

    def test_peek_present_key(self) -> None:
        """Peeking a present key returns its value without changing recency or telemetry."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(4)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertEqual(cache.peek("a", None), 1)
            self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
            stats = cache.get_stats()
            self.assertEqual(stats.hits, 0)
            self.assertEqual(stats.misses, 0)
            self.assertEqual(stats.evictions, 0)

    def test_peek_absent_key(self) -> None:
        """Peeking an absent key returns the default without changing recency or telemetry."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            self.assertEqual(cache.peek("missing", 42), 42)
            self.assertEqual(cache.keys_in_lru_order(), ["a"])
            stats = cache.get_stats()
            self.assertEqual(stats.hits, 0)
            self.assertEqual(stats.misses, 0)

    def test_remove_existing_key(self) -> None:
        """Removing an existing key returns its value and decrements size."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(4)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertEqual(cache.remove("a"), 1)
            self.assertEqual(cache.size, 1)
            self.assertFalse(cache.is_empty)
            self.assertEqual(cache.keys_in_lru_order(), ["b"])
            self.assertEqual(cache.remove("b"), 2)
            self.assertEqual(cache.size, 0)
            self.assertTrue(cache.is_empty)

    def test_remove_key_not_found(self) -> None:
        """Removing an absent key raises CacheKeyNotFoundError and leaves entries intact."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            with self.assertRaises(CacheKeyNotFoundError):
                cache.remove("missing")
            self.assertEqual(cache.size, 1)
            self.assertEqual(cache.peek("a", None), 1)

    def test_configure_update_limit(self) -> None:
        """Configuring a new limit updates capacity without evicting entries below it."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(3)
            self.assertEqual(cache.capacity, 3)
            self.assertFalse(cache.is_full)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.put("c", 3)
            self.assertTrue(cache.is_full)
            cache.configure(5)
            self.assertEqual(cache.capacity, 5)
            self.assertFalse(cache.is_full)
            self.assertEqual(cache.size, 3)
            self.assertEqual(cache.get_stats().evictions, 0)

    def test_configure_downsize_eviction(self) -> None:
        """Configuring a smaller limit evicts least-recently-used entries until size matches capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(4)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.put("c", 3)
            cache.put("d", 4)
            cache.configure(2)
            self.assertEqual(cache.capacity, 2)
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["c", "d"])
            self.assertEqual(cache.get_stats().evictions, 2)
            self.assertIsNone(cache.peek("a", None))
            self.assertIsNone(cache.peek("b", None))

    def test_configure_invalid_capacity(self) -> None:
        """Configuring a non-positive limit raises CacheCapacityError and keeps the prior limit."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            with self.assertRaises(CacheCapacityError):
                cache.configure(0)
            with self.assertRaises(CacheCapacityError):
                cache.configure(-5)
            self.assertEqual(cache.capacity, 100)

    def test_clear_resets_entries_but_preserves_telemetry(self) -> None:
        """Clearing removes all entries while preserving telemetry counters."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(2)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.put("c", 3)
            self.assertEqual(cache.get("b", None), 2)
            cache.clear()
            self.assertEqual(cache.size, 0)
            self.assertTrue(cache.is_empty)
            self.assertEqual(cache.keys_in_lru_order(), [])
            self.assertIsNone(cache.peek("a", None))
            stats = cache.get_stats()
            self.assertEqual(stats.hits, 1)
            self.assertEqual(stats.evictions, 1)
            self.assertIsNone(cache.put("d", 4))
            self.assertEqual(cache.size, 1)
            self.assertEqual(cache.keys_in_lru_order(), ["d"])

    def test_get_stats_report_telemetry(self) -> None:
        """Statistics report cumulative hits, misses, and evictions."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(2)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.put("c", 3)
            self.assertEqual(cache.get("b", None), 2)
            self.assertIsNone(cache.get("missing", None))
            stats = cache.get_stats()
            self.assertEqual(stats, CacheStats(hits=1, misses=1, evictions=1))

    def test_reset_stats(self) -> None:
        """Resetting statistics zeroes the counters without altering cached entries."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(2)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.put("c", 3)
            self.assertEqual(cache.get("b", None), 2)
            self.assertIsNone(cache.get("missing", None))
            cache.reset_stats()
            self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["c", "b"])

    def test_keys_in_lru_order(self) -> None:
        """Keys are ordered least-recently-used to most-recently-used without mutating state."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(4)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.put("c", 3)
            self.assertEqual(cache.keys_in_lru_order(), ["a", "b", "c"])
            self.assertEqual(cache.get("a", None), 1)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "c", "a"])
            self.assertEqual(cache.peek("b", None), 2)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "c", "a"])
            self.assertEqual(cache.get_stats(), CacheStats(hits=1, misses=0, evictions=0))


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:41:10Z
# LAST_CHANGED: 2026-11-08T17:40:37Z
# CHANGE: Fix test_reset_stats recency expectation to ['c','b'] after get('b') promotes it to most-recently-used; reset_stats must not alter entry recency
# COVERAGE_AUDIT: 2026-11-08T17:41:10Z
# QA_AUDIT: 2026-11-08T17:40:57Z
# --- END AUTOFAB METADATA ---
