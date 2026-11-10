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

# Module-level sentinel modeling a caller-supplied default domain value.
_DEFAULT: object = object()


class LruCacheImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state_exposes_default_capacity_and_empty_telemetry(self) -> None:
        """Happy path: fresh cache starts with default limit 100 and no entries."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            self.assertEqual(cache.capacity, 100)
            self.assertEqual(cache.size, 0)
            self.assertTrue(cache.is_empty)
            self.assertFalse(cache.is_full)
            self.assertEqual(cache.keys_in_lru_order(), [])
            self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))

    def test_configure_updates_capacity_limit(self) -> None:
        """Configuring a larger capacity limit updates the reported capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(8)
            self.assertEqual(cache.capacity, 8)
            self.assertEqual(cache.size, 0)
            self.assertFalse(cache.is_full)

    def test_configure_growth_preserves_existing_entries(self) -> None:
        """Growing the capacity limit preserves all existing cached entries."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(2)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.configure(5)
            self.assertEqual(cache.capacity, 5)
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
            self.assertEqual(cache.get_stats().evictions, 0)
            self.assertFalse(cache.is_full)

    def test_configure_downsize_evicts_least_recently_used_entries(self) -> None:
        """Shrinking the capacity limit evicts oldest entries until size fits."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(5)
            for key in ["a", "b", "c", "d", "e"]:
                cache.put(key, key.upper())
            cache.configure(3)
            self.assertEqual(cache.capacity, 3)
            self.assertEqual(cache.size, 3)
            self.assertEqual(cache.keys_in_lru_order(), ["c", "d", "e"])
            self.assertEqual(cache.get_stats().evictions, 2)
            self.assertTrue(cache.is_full)

    def test_configure_rejects_non_positive_capacity(self) -> None:
        """Non-positive capacity limits are rejected with CacheCapacityError."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            with self.assertRaises(CacheCapacityError):
                cache.configure(0)
            with self.assertRaises(CacheCapacityError):
                cache.configure(-5)

    def test_get_present_key_returns_value_and_promotes_to_most_recently_used(self) -> None:
        """Looking up a present key returns its value, promotes it, and counts a hit."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertEqual(cache.get("a", _DEFAULT), 1)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "a"])
            self.assertEqual(cache.get_stats(), CacheStats(hits=1, misses=0, evictions=0))

    def test_get_absent_key_returns_default_and_counts_miss(self) -> None:
        """Looking up an absent key returns the default, counts a miss, and keeps order."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            self.assertIs(cache.get("missing", _DEFAULT), _DEFAULT)
            self.assertEqual(cache.keys_in_lru_order(), ["a"])
            self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=1, evictions=0))

    def test_put_new_key_below_capacity_inserts_at_most_recently_used(self) -> None:
        """Inserting new keys below capacity stores them and returns None."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            self.assertIsNone(cache.put("a", 1))
            self.assertIsNone(cache.put("b", 2))
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
            self.assertFalse(cache.is_empty)
            self.assertEqual(cache.peek("b", _DEFAULT), 2)

    def test_put_existing_key_updates_value_without_growing_size(self) -> None:
        """Updating an existing key changes its value, promotes it, and returns None."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertIsNone(cache.put("a", 99))
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "a"])
            self.assertEqual(cache.peek("a", _DEFAULT), 99)

    def test_put_new_key_at_capacity_evicts_least_recently_used(self) -> None:
        """Inserting at capacity evicts the oldest entry and returns the evicted pair."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(2)
            cache.put("a", 1)
            cache.put("b", 2)
            evicted = cache.put("c", 3)
            self.assertEqual(evicted, ("a", 1))
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "c"])
            self.assertEqual(cache.get_stats().evictions, 1)
            self.assertTrue(cache.is_full)

    def test_put_returns_none_when_no_eviction_is_needed(self) -> None:
        """Insertions that fit below capacity never report an eviction."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(3)
            self.assertIsNone(cache.put("a", 1))
            self.assertIsNone(cache.put("b", 2))
            self.assertEqual(cache.get_stats().evictions, 0)

    def test_peek_present_key_returns_value_without_touching_recency_or_telemetry(self) -> None:
        """Peeking a present key returns its value without reordering or counting."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertEqual(cache.peek("a", _DEFAULT), 1)
            self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
            self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))

    def test_peek_absent_key_returns_default_without_touching_recency_or_telemetry(self) -> None:
        """Peeking an absent key returns the default without changing any state."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            self.assertIs(cache.peek("missing", _DEFAULT), _DEFAULT)
            self.assertEqual(cache.keys_in_lru_order(), ["a"])
            self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))

    def test_remove_existing_key_returns_value_and_shrinks_size(self) -> None:
        """Removing an existing key returns its value and shrinks the cache."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertEqual(cache.remove("a"), 1)
            self.assertEqual(cache.size, 1)
            self.assertEqual(cache.keys_in_lru_order(), ["b"])
            self.assertIs(cache.peek("a", _DEFAULT), _DEFAULT)

    def test_remove_absent_key_raises_key_not_found(self) -> None:
        """Removing an absent key is rejected with CacheKeyNotFoundError."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            with self.assertRaises(CacheKeyNotFoundError):
                cache.remove("missing")
            self.assertEqual(cache.size, 1)
            self.assertEqual(cache.keys_in_lru_order(), ["a"])

    def test_clear_removes_entries_and_preserves_telemetry(self) -> None:
        """Clearing removes every entry but preserves accumulated telemetry counters."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.get("a", _DEFAULT)
            cache.get("missing", _DEFAULT)
            before = cache.get_stats()
            cache.clear()
            self.assertEqual(cache.size, 0)
            self.assertTrue(cache.is_empty)
            self.assertEqual(cache.keys_in_lru_order(), [])
            self.assertEqual(cache.get_stats(), before)

    def test_get_stats_reports_cumulative_telemetry(self) -> None:
        """Reported statistics accumulate hits, misses, and evictions."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(1)
            cache.put("a", 1)
            cache.get("a", _DEFAULT)
            cache.get("missing", _DEFAULT)
            cache.put("b", 2)
            stats = cache.get_stats()
            self.assertIsInstance(stats, CacheStats)
            self.assertEqual(stats, CacheStats(hits=1, misses=1, evictions=1))

    def test_reset_stats_zeroes_counters_without_altering_entries(self) -> None:
        """Resetting statistics zeroes counters while keeping cached entries."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(1)
            cache.put("a", 1)
            cache.get("a", _DEFAULT)
            cache.get("missing", _DEFAULT)
            cache.put("b", 2)
            cache.reset_stats()
            self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))
            self.assertEqual(cache.size, 1)
            self.assertEqual(cache.keys_in_lru_order(), ["b"])
            self.assertEqual(cache.peek("b", _DEFAULT), 2)

    def test_keys_in_lru_order_reports_recency_without_mutating_state(self) -> None:
        """Key listing reports recency order without altering entries or telemetry."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.put("c", 3)
            cache.put("a", 10)
            cache.get("b", _DEFAULT)
            before = cache.get_stats()
            self.assertEqual(cache.keys_in_lru_order(), ["c", "a", "b"])
            self.assertEqual(cache.keys_in_lru_order(), ["c", "a", "b"])
            self.assertEqual(cache.get_stats(), before)
            self.assertEqual(cache.size, 3)

    def test_singleton_resolution_returns_one_instance_per_scope(self) -> None:
        """Happy path: LRUCache resolves as a single lifecycle singleton instance."""
        with enter_phase(system, registry=self.registry) as scope:
            first = scope.get_singleton(LRUCache)
            second = scope.get_singleton(LRUCache)
            self.assertIs(first, second)
            first.put("a", 1)
            self.assertEqual(second.size, 1)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:07:14Z
# LAST_CHANGED: 2026-11-09T22:06:27Z
# CHANGE: Implemented full unit test suite for LRUCache singleton: default capacity/initial state, configure update/growth/downsize eviction with telemetry, non-positive capacity rejection (CacheCapacityError), get hit promotion/miss default, put insert/update/evict-on-capacity, peek non-mutating, remove existing/missing (CacheKeyNotFoundError), clear with telemetry preservation, stats accumulation and reset, and non-mutating LRU-order key listing.
# COVERAGE_AUDIT: 2026-11-09T22:07:14Z
# QA_AUDIT: 2026-11-09T22:07:00Z
# --- END AUTOFAB METADATA ---
