from __future__ import annotations

import unittest
from typing import Any, List, Optional, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)
from lru_cache.lib.lru_cache_impl import LRUCache, __initialize__


class LRUCacheImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.cache = self.phase_scope.get_singleton(LRUCache)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_initial_state(self) -> None:
        """Verifies default capacity, zero size, empty state, and initial zero telemetry."""
        self.assertEqual(self.cache.capacity, 100)
        self.assertEqual(self.cache.size, 0)
        self.assertTrue(self.cache.is_empty)
        self.assertFalse(self.cache.is_full)
        self.assertEqual(self.cache.keys_in_lru_order(), [])
        self.assertEqual(self.cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))

    def test_configure_update_limit(self) -> None:
        """Verifies updating cache capacity to a valid limit."""
        self.cache.configure(5)
        self.assertEqual(self.cache.capacity, 5)

    def test_configure_invalid_capacity_zero(self) -> None:
        """Verifies setting capacity to zero raises CacheCapacityError."""
        with self.assertRaises(CacheCapacityError):
            self.cache.configure(0)

    def test_configure_invalid_capacity_negative(self) -> None:
        """Verifies setting negative capacity raises CacheCapacityError."""
        with self.assertRaises(CacheCapacityError):
            self.cache.configure(-10)

    def test_configure_downsize_eviction(self) -> None:
        """Verifies downsizing capacity evicts oldest entries and increments eviction counter."""
        self.cache.configure(4)
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        self.cache.put("c", 3)
        self.cache.put("d", 4)
        self.cache.configure(2)
        self.assertEqual(self.cache.size, 2)
        self.assertEqual(self.cache.capacity, 2)
        self.assertEqual(self.cache.keys_in_lru_order(), ["c", "d"])
        self.assertEqual(self.cache.get_stats().evictions, 2)

    def test_put_insert_below_capacity(self) -> None:
        """Verifies inserting new entry when below capacity stores entry and returns None."""
        result = self.cache.put("k1", "v1")
        self.assertIsNone(result)
        self.assertEqual(self.cache.size, 1)
        self.assertFalse(self.cache.is_empty)
        self.assertEqual(self.cache.keys_in_lru_order(), ["k1"])

    def test_put_update_existing(self) -> None:
        """Verifies updating existing key modifies value and promotes to MRU without increasing size."""
        self.cache.put("k1", "v1")
        self.cache.put("k2", "v2")
        result = self.cache.put("k1", "v1_updated")
        self.assertIsNone(result)
        self.assertEqual(self.cache.size, 2)
        self.assertEqual(self.cache.keys_in_lru_order(), ["k2", "k1"])
        self.assertEqual(self.cache.get("k1", None), "v1_updated")

    def test_put_evict_on_capacity(self) -> None:
        """Verifies inserting when at capacity evicts LRU entry and returns evicted key-value pair."""
        self.cache.configure(2)
        self.cache.put("k1", "v1")
        self.cache.put("k2", "v2")
        self.assertTrue(self.cache.is_full)
        evicted = self.cache.put("k3", "v3")
        self.assertEqual(evicted, ("k1", "v1"))
        self.assertEqual(self.cache.size, 2)
        self.assertEqual(self.cache.keys_in_lru_order(), ["k2", "k3"])
        self.assertEqual(self.cache.get_stats().evictions, 1)

    def test_get_hit(self) -> None:
        """Verifies getting existing key returns value, promotes to MRU, and increments hits."""
        self.cache.put("k1", 100)
        self.cache.put("k2", 200)
        val = self.cache.get("k1", None)
        self.assertEqual(val, 100)
        self.assertEqual(self.cache.keys_in_lru_order(), ["k2", "k1"])
        self.assertEqual(self.cache.get_stats().hits, 1)
        self.assertEqual(self.cache.get_stats().misses, 0)

    def test_get_miss(self) -> None:
        """Verifies getting absent key returns default value and increments misses."""
        self.cache.put("k1", 100)
        val = self.cache.get("absent", "default_val")
        self.assertEqual(val, "default_val")
        self.assertEqual(self.cache.keys_in_lru_order(), ["k1"])
        self.assertEqual(self.cache.get_stats().hits, 0)
        self.assertEqual(self.cache.get_stats().misses, 1)

    def test_peek_present_key(self) -> None:
        """Verifies peeking existing key returns value without altering recency order or stats."""
        self.cache.put("k1", 100)
        self.cache.put("k2", 200)
        val = self.cache.peek("k1", None)
        self.assertEqual(val, 100)
        self.assertEqual(self.cache.keys_in_lru_order(), ["k1", "k2"])
        self.assertEqual(self.cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))

    def test_peek_absent_key(self) -> None:
        """Verifies peeking absent key returns default without altering recency order or stats."""
        self.cache.put("k1", 100)
        val = self.cache.peek("absent", "default_val")
        self.assertEqual(val, "default_val")
        self.assertEqual(self.cache.keys_in_lru_order(), ["k1"])
        self.assertEqual(self.cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))

    def test_remove_existing_key(self) -> None:
        """Verifies removing existing key returns value and decrements size."""
        self.cache.put("k1", 100)
        self.cache.put("k2", 200)
        removed = self.cache.remove("k1")
        self.assertEqual(removed, 100)
        self.assertEqual(self.cache.size, 1)
        self.assertEqual(self.cache.keys_in_lru_order(), ["k2"])

    def test_remove_key_not_found(self) -> None:
        """Verifies removing absent key raises CacheKeyNotFoundError."""
        with self.assertRaises(CacheKeyNotFoundError):
            self.cache.remove("unknown")

    def test_clear_reset_entries_and_preserve_telemetry(self) -> None:
        """Verifies clearing removes entries and resets size while preserving stats."""
        self.cache.configure(2)
        self.cache.put("k1", 1)
        self.cache.put("k2", 2)
        self.cache.get("k1", None)
        self.cache.get("missing", None)
        self.cache.put("k3", 3)
        self.assertEqual(self.cache.get_stats(), CacheStats(hits=1, misses=1, evictions=1))
        self.cache.clear()
        self.assertEqual(self.cache.size, 0)
        self.assertTrue(self.cache.is_empty)
        self.assertEqual(self.cache.keys_in_lru_order(), [])
        self.assertEqual(self.cache.get_stats(), CacheStats(hits=1, misses=1, evictions=1))

    def test_reset_stats(self) -> None:
        """Verifies resetting stats zeroes telemetry counters without altering stored entries."""
        self.cache.put("k1", 1)
        self.cache.get("k1", None)
        self.cache.get("missing", None)
        self.assertEqual(self.cache.get_stats(), CacheStats(hits=1, misses=1, evictions=0))
        self.cache.reset_stats()
        self.assertEqual(self.cache.get_stats(), CacheStats(hits=0, misses=0, evictions=0))
        self.assertEqual(self.cache.size, 1)
        self.assertEqual(self.cache.peek("k1", None), 1)

    def test_keys_in_lru_order_non_mutating(self) -> None:
        """Verifies keys_in_lru_order returns keys in LRU order without mutating order or stats."""
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        self.cache.put("c", 3)
        self.cache.get("a", None)
        order1 = self.cache.keys_in_lru_order()
        self.assertEqual(order1, ["b", "c", "a"])
        order2 = self.cache.keys_in_lru_order()
        self.assertEqual(order2, ["b", "c", "a"])
        self.assertEqual(self.cache.get_stats(), CacheStats(hits=1, misses=0, evictions=0))

    def test_is_empty_and_is_full_transitions(self) -> None:
        """Verifies state transitions for is_empty and is_full predicates."""
        self.cache.configure(2)
        self.assertTrue(self.cache.is_empty)
        self.assertFalse(self.cache.is_full)
        self.cache.put("k1", 1)
        self.assertFalse(self.cache.is_empty)
        self.assertFalse(self.cache.is_full)
        self.cache.put("k2", 2)
        self.assertFalse(self.cache.is_empty)
        self.assertTrue(self.cache.is_full)
        self.cache.remove("k1")
        self.assertFalse(self.cache.is_empty)
        self.assertFalse(self.cache.is_full)
        self.cache.remove("k2")
        self.assertTrue(self.cache.is_empty)
        self.assertFalse(self.cache.is_full)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:19:36Z
# LAST_CHANGED: 2026-11-09T22:18:42Z
# CHANGE: Author unit tests for LRUCache verifying all contract postconditions, preconditions, and invariants
# COVERAGE_AUDIT: 2026-11-09T22:19:36Z
# QA_AUDIT: 2026-11-09T22:19:10Z
# --- END AUTOFAB METADATA ---
