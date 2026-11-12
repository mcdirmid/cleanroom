from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleTestCase
from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)
from lru_cache.lib.lru_cache_impl import LRUCache


class LRUCacheImplTest(LifecycleTestCase):
    """Unit tests for bounded least-recently-used cache implementation."""

    target = LRUCache

    def test_initial_state(self) -> None:
        """Verify initial default properties and telemetry counters of new cache instance."""
        self.assertEqual(self.sut.capacity, 100)
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.keys_in_lru_order(), [])
        stats = self.sut.get_stats()
        self.assertEqual(stats, CacheStats(hits=0, misses=0, evictions=0))

    def test_configure_valid_capacity(self) -> None:
        """Verify updating cache capacity limit to a valid positive integer."""
        self.sut.configure(50)
        self.assertEqual(self.sut.capacity, 50)

    def test_configure_zero_capacity_raises_error(self) -> None:
        """Verify setting capacity to zero raises CacheCapacityError."""
        with self.assertRaises(CacheCapacityError):
            self.sut.configure(0)

    def test_configure_negative_capacity_raises_error(self) -> None:
        """Verify setting capacity to negative value raises CacheCapacityError."""
        with self.assertRaises(CacheCapacityError):
            self.sut.configure(-10)

    def test_configure_downsize_evicts_lru_entries(self) -> None:
        """Verify downsizing capacity evicts least-recently-used entries in sequence."""
        self.sut.put("first", 1)
        self.sut.put("second", 2)
        self.sut.put("third", 3)
        self.sut.put("fourth", 4)
        self.assertEqual(self.sut.size, 4)

        self.sut.configure(2)
        self.assertEqual(self.sut.capacity, 2)
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.keys_in_lru_order(), ["third", "fourth"])
        self.assertEqual(self.sut.get_stats().evictions, 2)

    def test_configure_downsize_no_eviction_when_within_limit(self) -> None:
        """Verify downsizing to size greater than or equal to current size causes no evictions."""
        self.sut.put("a", 1)
        self.sut.put("b", 2)
        self.sut.configure(2)
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.get_stats().evictions, 0)
        self.sut.configure(5)
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.get_stats().evictions, 0)

    def test_put_below_capacity(self) -> None:
        """Verify storing new entry below capacity increments size and returns None."""
        self.sut.configure(3)
        result = self.sut.put("alpha", "val1")
        self.assertIsNone(result)
        self.assertEqual(self.sut.size, 1)
        self.assertFalse(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.keys_in_lru_order(), ["alpha"])

    def test_put_update_existing_key(self) -> None:
        """Verify updating existing key updates value, promotes to MRU, and returns None."""
        self.sut.configure(3)
        self.sut.put("k1", 100)
        self.sut.put("k2", 200)
        self.assertEqual(self.sut.keys_in_lru_order(), ["k1", "k2"])

        update_result = self.sut.put("k1", 999)
        self.assertIsNone(update_result)
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.keys_in_lru_order(), ["k2", "k1"])
        self.assertEqual(self.sut.get("k1", None), 999)

    def test_put_at_capacity_evicts_lru_entry(self) -> None:
        """Verify inserting at capacity evicts least-recently-used entry and returns eviction tuple."""
        self.sut.configure(2)
        self.sut.put("k1", "v1")
        self.sut.put("k2", "v2")
        self.assertTrue(self.sut.is_full)

        evicted = self.sut.put("k3", "v3")
        self.assertEqual(evicted, ("k1", "v1"))
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.keys_in_lru_order(), ["k2", "k3"])
        self.assertEqual(self.sut.get_stats().evictions, 1)

    def test_get_hit_promotes_key_and_increments_hits(self) -> None:
        """Verify retrieving existing key returns value, promotes to MRU, and increments hits."""
        self.sut.configure(3)
        self.sut.put("a", 10)
        self.sut.put("b", 20)
        self.sut.put("c", 30)
        self.assertEqual(self.sut.keys_in_lru_order(), ["a", "b", "c"])

        val = self.sut.get("a", None)
        self.assertEqual(val, 10)
        self.assertEqual(self.sut.keys_in_lru_order(), ["b", "c", "a"])
        stats = self.sut.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 0)

    def test_get_miss_returns_default_and_increments_misses(self) -> None:
        """Verify retrieving missing key returns default, increments misses, and preserves order."""
        self.sut.configure(3)
        self.sut.put("x", 1)
        self.sut.put("y", 2)
        self.assertEqual(self.sut.keys_in_lru_order(), ["x", "y"])

        val = self.sut.get("z", "fallback")
        self.assertEqual(val, "fallback")
        self.assertEqual(self.sut.keys_in_lru_order(), ["x", "y"])
        stats = self.sut.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 1)

    def test_get_stored_none_value_counts_as_hit(self) -> None:
        """Verify retrieving entry stored with None value returns None and counts as hit."""
        self.sut.put("nil_key", None)
        val = self.sut.get("nil_key", "default_not_used")
        self.assertIsNone(val)
        self.assertEqual(self.sut.get_stats().hits, 1)
        self.assertEqual(self.sut.get_stats().misses, 0)

    def test_peek_present_key_without_modifications(self) -> None:
        """Verify inspecting cached value does not alter recency order or telemetry."""
        self.sut.configure(3)
        self.sut.put("first", 1)
        self.sut.put("second", 2)

        val = self.sut.peek("first", None)
        self.assertEqual(val, 1)
        self.assertEqual(self.sut.keys_in_lru_order(), ["first", "second"])
        stats = self.sut.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)

    def test_peek_absent_key_returns_default_without_modifications(self) -> None:
        """Verify peeking absent key returns default without altering telemetry or order."""
        self.sut.put("exist", "val")
        val = self.sut.peek("absent", "default_val")
        self.assertEqual(val, "default_val")
        stats = self.sut.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)

    def test_peek_stored_none_value(self) -> None:
        """Verify peeking key stored with None returns None without modifying counters."""
        self.sut.put("key_with_none", None)
        val = self.sut.peek("key_with_none", "fallback")
        self.assertIsNone(val)
        stats = self.sut.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)

    def test_remove_existing_key(self) -> None:
        """Verify removing existing key decrements size and returns removed value."""
        self.sut.put("del_key", 42)
        self.assertEqual(self.sut.size, 1)

        val = self.sut.remove("del_key")
        self.assertEqual(val, 42)
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertEqual(self.sut.keys_in_lru_order(), [])

    def test_remove_absent_key_raises_error(self) -> None:
        """Verify removing absent key raises CacheKeyNotFoundError."""
        with self.assertRaises(CacheKeyNotFoundError):
            self.sut.remove("nonexistent_key")

    def test_clear_removes_entries_and_preserves_telemetry(self) -> None:
        """Verify clear resets entries to empty while preserving cumulative telemetry counters."""
        self.sut.configure(2)
        self.sut.put("k1", 1)
        self.sut.put("k2", 2)
        self.sut.get("k1", None)
        self.sut.get("missing", None)
        self.sut.put("k3", 3)

        stats_before = self.sut.get_stats()
        self.assertEqual(stats_before.hits, 1)
        self.assertEqual(stats_before.misses, 1)
        self.assertEqual(stats_before.evictions, 1)

        self.sut.clear()
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.keys_in_lru_order(), [])

        stats_after = self.sut.get_stats()
        self.assertEqual(stats_after, stats_before)

    def test_get_stats_returns_immutable_record(self) -> None:
        """Verify get_stats returns immutable CacheStats record matching current counters."""
        self.sut.put("item", "data")
        self.sut.get("item", None)
        self.sut.get("item", None)
        self.sut.get("other", None)

        stats = self.sut.get_stats()
        self.assertEqual(stats.hits, 2)
        self.assertEqual(stats.misses, 1)
        self.assertEqual(stats.evictions, 0)

    def test_reset_stats_clears_counters_without_altering_entries(self) -> None:
        """Verify reset_stats sets counters to zero while preserving cached entries and order."""
        self.sut.put("first", 10)
        self.sut.put("second", 20)
        self.sut.get("first", None)
        self.sut.get("absent", None)

        self.assertEqual(self.sut.get_stats().hits, 1)
        self.assertEqual(self.sut.get_stats().misses, 1)

        self.sut.reset_stats()
        stats = self.sut.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(stats.evictions, 0)
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.keys_in_lru_order(), ["second", "first"])

    def test_keys_in_lru_order_is_non_mutating(self) -> None:
        """Verify keys_in_lru_order does not modify recency order or telemetry."""
        self.sut.put("a", 1)
        self.sut.put("b", 2)
        self.sut.put("c", 3)

        keys1 = self.sut.keys_in_lru_order()
        keys2 = self.sut.keys_in_lru_order()
        self.assertEqual(keys1, ["a", "b", "c"])
        self.assertEqual(keys2, ["a", "b", "c"])
        stats = self.sut.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(stats.evictions, 0)

    def test_is_full_transitions(self) -> None:
        """Verify is_full reflects capacity occupancy transitions."""
        self.sut.configure(1)
        self.assertFalse(self.sut.is_full)
        self.sut.put("only", "one")
        self.assertTrue(self.sut.is_full)
        self.sut.remove("only")
        self.assertFalse(self.sut.is_full)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T04:35:29Z
# LAST_CHANGED: 2026-11-12T04:34:30Z
# CHANGE: Implement comprehensive unit tests for LRUCache covering lifecycle, capacity configuration, evictions, access recency promotion, peek, remove, clear, and telemetry
# COVERAGE_AUDIT: 2026-11-12T04:35:29Z
# QA_AUDIT: 2026-11-12T04:35:02Z
# --- END AUTOFAB METADATA ---
