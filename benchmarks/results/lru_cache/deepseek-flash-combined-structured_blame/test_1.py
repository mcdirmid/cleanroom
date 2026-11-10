"""Unit tests for the LRUCache singleton in ``lib/lru_cache_impl.py``.

Covers capacity configuration, recency promotion, overflow eviction, telemetry
accounting, and non-mutating inspection as fixed by the low-level
specifications ``low/lru_cache_impl.pyi`` and ``low/lru_cache.pyi``.
"""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)
from lru_cache.lib.lru_cache_impl import LRUCache, __initialize__


class LRUCacheImplTest(unittest.TestCase):
    """Verifies LRUCache singleton behavior within an active system phase scope."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state_defaults(self) -> None:
        """A fresh singleton starts empty at the default capacity of 100."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            self.assertEqual(cache.capacity, 100)
            self.assertEqual(cache.size, 0)
            self.assertTrue(cache.is_empty)
            self.assertFalse(cache.is_full)
            self.assertEqual(cache.keys_in_lru_order(), [])
            self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))

    def test_configure_updates_capacity(self) -> None:
        """Configuring a positive capacity updates the exposed capacity limit."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(7)
            self.assertEqual(cache.capacity, 7)
            self.assertEqual(cache.size, 0)

    def test_is_full_tracks_capacity(self) -> None:
        """is_full becomes True only once size reaches the configured capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(2)
            self.assertFalse(cache.is_full)
            cache.put("a", 1)
            self.assertFalse(cache.is_full)
            cache.put("b", 2)
            self.assertTrue(cache.is_full)
            self.assertEqual(cache.size, 2)

    def test_configure_invalid_capacity_raises(self) -> None:
        """Configuring a capacity of zero or below raises CacheCapacityError."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            with self.assertRaises(CacheCapacityError):
                cache.configure(0)
            with self.assertRaises(CacheCapacityError):
                cache.configure(-5)
            self.assertEqual(cache.capacity, 100)

    def test_configure_downsize_evicts_lru_entries(self) -> None:
        """Shrinking capacity below the current size evicts least-recently-used entries."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.put("c", 3)
            cache.put("d", 4)
            cache.configure(2)
            self.assertEqual(cache.capacity, 2)
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["c", "d"])
            self.assertEqual(cache.get_stats().evictions, 2)

    def test_get_present_key_returns_value_and_promotes(self) -> None:
        """Getting a present key returns its value, promotes it, and counts a hit."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertEqual(cache.get("a", None), 1)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "a"])
            self.assertEqual(cache.size, 2)
            stats = cache.get_stats()
            self.assertEqual(stats.hits, 1)
            self.assertEqual(stats.misses, 0)

    def test_get_absent_key_returns_default_and_counts_miss(self) -> None:
        """Getting an absent key returns the default and counts a miss without reordering."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertEqual(cache.get("missing", "fallback"), "fallback")
            self.assertIsNone(cache.get("other", None))
            self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
            stats = cache.get_stats()
            self.assertEqual(stats.misses, 2)
            self.assertEqual(stats.hits, 0)

    def test_put_existing_key_updates_value_and_promotes(self) -> None:
        """Putting an existing key updates its value, promotes it, keeps size, returns None."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            self.assertIsNone(cache.put("a", 1))
            self.assertIsNone(cache.put("b", 2))
            self.assertIsNone(cache.put("a", 3))
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.peek("a", None), 3)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "a"])
            self.assertEqual(cache.get_stats().evictions, 0)

    def test_put_existing_key_at_capacity_does_not_evict(self) -> None:
        """Updating an existing key at capacity refreshes it without evicting anything."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(2)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertIsNone(cache.put("a", 9))
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "a"])
            self.assertEqual(cache.get_stats().evictions, 0)

    def test_put_new_key_below_capacity_returns_none(self) -> None:
        """Putting a new key below capacity inserts at the MRU end and returns None."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(3)
            self.assertIsNone(cache.put("a", 1))
            self.assertEqual(cache.size, 1)
            self.assertIsNone(cache.put("b", 2))
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
            self.assertEqual(cache.get_stats().evictions, 0)

    def test_put_new_key_at_capacity_evicts_lru(self) -> None:
        """Putting a new key at capacity evicts the LRU entry and returns its pair."""
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

    def test_peek_present_key_is_non_mutating(self) -> None:
        """Peeking a present key returns its value without recency or telemetry changes."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertEqual(cache.peek("a", None), 1)
            self.assertEqual(cache.keys_in_lru_order(), ["a", "b"])
            self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))

    def test_peek_absent_key_returns_default_without_mutation(self) -> None:
        """Peeking an absent key returns the default without any mutation."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            self.assertEqual(cache.peek("missing", "fallback"), "fallback")
            self.assertIsNone(cache.peek("missing2", None))
            self.assertEqual(cache.keys_in_lru_order(), ["a"])
            self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))

    def test_remove_existing_key_returns_value(self) -> None:
        """Removing an existing key deletes it and returns its stored value."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            self.assertEqual(cache.remove("a"), 1)
            self.assertEqual(cache.size, 1)
            self.assertEqual(cache.keys_in_lru_order(), ["b"])
            self.assertFalse(cache.is_empty)

    def test_remove_absent_key_raises(self) -> None:
        """Removing an absent key raises CacheKeyNotFoundError and keeps state intact."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            with self.assertRaises(CacheKeyNotFoundError):
                cache.remove("missing")
            self.assertEqual(cache.size, 1)
            self.assertEqual(cache.keys_in_lru_order(), ["a"])

    def test_clear_resets_entries_and_preserves_telemetry(self) -> None:
        """Clearing removes every entry while telemetry counters persist."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.get("a", None)
            cache.get("missing", None)
            cache.clear()
            self.assertEqual(cache.size, 0)
            self.assertTrue(cache.is_empty)
            self.assertEqual(cache.keys_in_lru_order(), [])
            stats = cache.get_stats()
            self.assertEqual(stats.hits, 1)
            self.assertEqual(stats.misses, 1)
            self.assertEqual(stats.evictions, 0)

    def test_get_stats_reports_cumulative_telemetry(self) -> None:
        """get_stats returns an immutable record of cumulative hits, misses, evictions."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(1)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.get("b", None)
            cache.get("missing", None)
            stats = cache.get_stats()
            self.assertIsInstance(stats, CacheStats)
            self.assertEqual(stats, CacheStats(hits=1, misses=1, evictions=1))

    def test_reset_stats_zeroes_telemetry_preserving_entries(self) -> None:
        """reset_stats zeroes counters without disturbing cached entries."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(2)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.put("c", 3)
            cache.get("b", None)
            cache.get("missing", None)
            cache.reset_stats()
            self.assertEqual(cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))
            self.assertEqual(cache.size, 2)
            self.assertEqual(cache.keys_in_lru_order(), ["c", "b"])

    def test_keys_in_lru_order_tracks_recency(self) -> None:
        """Keys are reported in least-to-most-recently-used order."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.configure(5)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.put("c", 3)
            self.assertEqual(cache.keys_in_lru_order(), ["a", "b", "c"])
            cache.get("a", None)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "c", "a"])
            cache.peek("b", None)
            self.assertEqual(cache.keys_in_lru_order(), ["b", "c", "a"])

    def test_keys_in_lru_order_is_non_mutating(self) -> None:
        """Querying LRU order does not reorder entries or touch telemetry."""
        with enter_phase(system, registry=self.registry) as scope:
            cache = scope.get_singleton(LRUCache)
            cache.put("a", 1)
            cache.put("b", 2)
            cache.get("a", None)
            before_stats = cache.get_stats()
            first = cache.keys_in_lru_order()
            second = cache.keys_in_lru_order()
            self.assertEqual(first, ["b", "a"])
            self.assertEqual(second, ["b", "a"])
            self.assertEqual(cache.get_stats(), before_stats)
            self.assertEqual(cache.size, 2)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:46:00Z
# LAST_CHANGED: 2026-11-08T17:45:19Z
# CHANGE: Author full LRUCache singleton test suite: default capacity/state, configure update & downsize eviction, invalid capacity errors, get hit/miss with recency and telemetry, put update/insert/evict branches, non-mutating peek, remove success & missing-key error, clear preserving telemetry, stats reporting/reset, and LRU key ordering invariants
# COVERAGE_AUDIT: 2026-11-08T17:46:00Z
# QA_AUDIT: 2026-11-08T17:45:46Z
# --- END AUTOFAB METADATA ---
