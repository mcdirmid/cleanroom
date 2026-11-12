from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleTestCase
from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)
from lru_cache.lib.lru_cache_impl import LRUCache as LRUCacheTarget

class LRUCacheImplTest(LifecycleTestCase):
    """Unit tests for bounded least-recently-used cache."""

    target = LRUCacheTarget
    sut: LRUCacheTarget

    def test_initial_properties(self) -> None:
        """Verify initial cache properties and default telemetry state."""
        self.assertEqual(self.sut.capacity, 100)
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.get_stats(), CacheStats(hits=0, misses=0, evictions=0))
        self.assertEqual(self.sut.keys_in_lru_order(), [])

    def test_configure_valid_capacity(self) -> None:
        """Verify updating cache capacity to a valid positive value."""
        self.sut.configure(10)
        self.assertEqual(self.sut.capacity, 10)

    def test_configure_zero_capacity_raises_error(self) -> None:
        """Verify configuring zero capacity raises CacheCapacityError."""
        with self.assertRaises(CacheCapacityError):
            self.sut.configure(0)

    def test_configure_negative_capacity_raises_error(self) -> None:
        """Verify configuring negative capacity raises CacheCapacityError."""
        with self.assertRaises(CacheCapacityError):
            self.sut.configure(-5)

    def test_configure_downsize_evicts_lru_entries(self) -> None:
        """Verify downsizing cache capacity evicts least-recently-used entries."""
        self.sut.configure(5)
        self.sut.put("k1", "v1")
        self.sut.put("k2", "v2")
        self.sut.put("k3", "v3")
        self.sut.put("k4", "v4")
        self.sut.configure(2)
        self.assertEqual(self.sut.capacity, 2)
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.get_stats().evictions, 2)
        self.assertEqual(self.sut.keys_in_lru_order(), ["k3", "k4"])

    def test_put_insert_below_capacity(self) -> None:
        """Verify inserting a new entry below maximum capacity."""
        self.sut.configure(3)
        evicted = self.sut.put("a", 1)
        self.assertIsNone(evicted)
        self.assertEqual(self.sut.size, 1)
        self.assertFalse(self.sut.is_empty)
        self.assertFalse(self.sut.is_full)
        self.assertEqual(self.sut.keys_in_lru_order(), ["a"])

    def test_put_update_existing_key(self) -> None:
        """Verify updating an existing key replaces value and promotes to MRU."""
        self.sut.configure(3)
        self.sut.put("a", 1)
        self.sut.put("b", 2)
        evicted = self.sut.put("a", 10)
        self.assertIsNone(evicted)
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.get("a", None), 10)
        self.assertEqual(self.sut.keys_in_lru_order(), ["b", "a"])

    def test_put_evict_on_capacity(self) -> None:
        """Verify inserting a new entry at full capacity evicts LRU entry."""
        self.sut.configure(2)
        self.sut.put("a", 1)
        self.sut.put("b", 2)
        self.assertTrue(self.sut.is_full)
        evicted = self.sut.put("c", 3)
        self.assertEqual(evicted, ("a", 1))
        self.assertEqual(self.sut.size, 2)
        self.assertEqual(self.sut.get_stats().evictions, 1)
        self.assertEqual(self.sut.keys_in_lru_order(), ["b", "c"])

    def test_get_hit_promotes_to_mru(self) -> None:
        """Verify retrieving an existing key returns value and promotes to MRU."""
        self.sut.configure(3)
        self.sut.put("a", 1)
        self.sut.put("b", 2)
        self.sut.put("c", 3)
        val = self.sut.get("a", None)
        self.assertEqual(val, 1)
        stats = self.sut.get_stats()
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(self.sut.keys_in_lru_order(), ["b", "c", "a"])

    def test_get_miss_returns_default(self) -> None:
        """Verify retrieving an absent key returns default value and counts miss."""
        self.sut.configure(3)
        self.sut.put("a", 1)
        val = self.sut.get("absent", "default_val")
        self.assertEqual(val, "default_val")
        stats = self.sut.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 1)
        self.assertEqual(self.sut.keys_in_lru_order(), ["a"])

    def test_peek_present_key(self) -> None:
        """Verify inspecting an existing key returns value without altering recency."""
        self.sut.configure(3)
        self.sut.put("a", 1)
        self.sut.put("b", 2)
        val = self.sut.peek("a", None)
        self.assertEqual(val, 1)
        self.assertEqual(self.sut.keys_in_lru_order(), ["a", "b"])
        self.assertEqual(self.sut.get_stats(), CacheStats(hits=0, misses=0, evictions=0))

    def test_peek_absent_key(self) -> None:
        """Verify inspecting an absent key returns default value without side effects."""
        self.sut.configure(3)
        self.sut.put("a", 1)
        val = self.sut.peek("absent", "fallback")
        self.assertEqual(val, "fallback")
        self.assertEqual(self.sut.keys_in_lru_order(), ["a"])
        self.assertEqual(self.sut.get_stats(), CacheStats(hits=0, misses=0, evictions=0))

    def test_remove_existing_key(self) -> None:
        """Verify removing an existing key decrements size and returns value."""
        self.sut.configure(3)
        self.sut.put("a", 1)
        self.sut.put("b", 2)
        val = self.sut.remove("a")
        self.assertEqual(val, 1)
        self.assertEqual(self.sut.size, 1)
        self.assertEqual(self.sut.keys_in_lru_order(), ["b"])

    def test_remove_absent_key_raises_error(self) -> None:
        """Verify removing an absent key raises CacheKeyNotFoundError."""
        self.sut.configure(3)
        self.sut.put("a", 1)
        with self.assertRaises(CacheKeyNotFoundError):
            self.sut.remove("absent")
        self.assertEqual(self.sut.size, 1)

    def test_clear_resets_entries_preserves_telemetry(self) -> None:
        """Verify clearing cache removes all entries while preserving telemetry."""
        self.sut.configure(3)
        self.sut.put("a", 1)
        self.sut.get("a", None)
        self.sut.get("b", None)
        self.sut.clear()
        self.assertEqual(self.sut.size, 0)
        self.assertTrue(self.sut.is_empty)
        self.assertEqual(self.sut.keys_in_lru_order(), [])
        self.assertEqual(self.sut.get_stats(), CacheStats(hits=1, misses=1, evictions=0))

    def test_reset_stats_clears_telemetry_preserves_entries(self) -> None:
        """Verify resetting statistics clears counters without altering entries."""
        self.sut.configure(3)
        self.sut.put("a", 1)
        self.sut.get("a", None)
        self.sut.get("b", None)
        self.sut.reset_stats()
        self.assertEqual(self.sut.get_stats(), CacheStats(hits=0, misses=0, evictions=0))
        self.assertEqual(self.sut.size, 1)
        self.assertEqual(self.sut.keys_in_lru_order(), ["a"])

    def test_keys_in_lru_order_non_mutating(self) -> None:
        """Verify querying keys in recency order is non-mutating."""
        self.sut.configure(3)
        self.sut.put("a", 1)
        self.sut.put("b", 2)
        self.sut.put("c", 3)
        order1 = self.sut.keys_in_lru_order()
        order2 = self.sut.keys_in_lru_order()
        self.assertEqual(order1, ["a", "b", "c"])
        self.assertEqual(order2, ["a", "b", "c"])
        self.assertEqual(self.sut.get_stats(), CacheStats(hits=0, misses=0, evictions=0))


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T04:23:26Z
# LAST_CHANGED: 2026-11-12T04:20:50Z
# CHANGE: Implement comprehensive unit test suite inheriting from LifecycleTestCase verifying all LRUCache properties, operations, errors, and LRU ordering
# COVERAGE_AUDIT: 2026-11-12T04:23:26Z
# QA_AUDIT: 2026-11-12T04:23:02Z
# --- END AUTOFAB METADATA ---
