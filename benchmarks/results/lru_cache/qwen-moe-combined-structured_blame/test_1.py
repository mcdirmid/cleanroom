"""Unit tests for lru_cache_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Tuple, cast

from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)
from lru_cache.lib.lru_cache_impl import (
    LRUCache,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


def _make_value(n: int) -> str:
    """Factory helper converting int to domain string value."""
    return f"value_{n}"


def _make_key(n: int) -> str:
    """Factory helper converting int to domain string key."""
    return f"key_{n}"


class LRUCacheImplTest(unittest.TestCase):
    """Tests for the LRUCache LRU cache implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def _get_cache(self) -> LRUCache:
        """Resolve the LRUCache singleton from an active phase scope."""
        with enter_phase(system, registry=self.registry) as scope:
            return scope.get_singleton(LRUCache)

    # ------------------------------------------------------------------ #
    # Property tests
    # ------------------------------------------------------------------ #

    def test_capacity_property(self) -> None:
        """CUJ: Verify capacity property returns configured limit."""
        cache = self._get_cache()
        self.assertEqual(cache.capacity, 100)

    def test_capacity_after_configure(self) -> None:
        """CUJ: Verify capacity updates after configure."""
        cache = self._get_cache()
        cache.configure(10)
        self.assertEqual(cache.capacity, 10)

    def test_size_property_initial(self) -> None:
        """CUJ: Verify size is zero for an empty cache."""
        cache = self._get_cache()
        self.assertEqual(cache.size, 0)

    def test_size_after_insert(self) -> None:
        """CUJ: Verify size increments on insert."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        self.assertEqual(cache.size, 1)

    def test_size_after_eviction(self) -> None:
        """CUJ: Verify size stays at capacity after eviction."""
        cache = self._get_cache()
        cache.configure(2)
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.put("key_3", "value_3")
        self.assertEqual(cache.size, 2)

    def test_is_empty_true_initially(self) -> None:
        """CUJ: Verify is_empty is True for an empty cache."""
        cache = self._get_cache()
        self.assertTrue(cache.is_empty)

    def test_is_empty_false_after_insert(self) -> None:
        """CUJ: Verify is_empty is False after inserting an entry."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        self.assertFalse(cache.is_empty)

    def test_is_empty_true_after_clear(self) -> None:
        """CUJ: Verify is_empty is True after clearing."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.clear()
        self.assertTrue(cache.is_empty)

    def test_is_full_true_at_capacity(self) -> None:
        """CUJ: Verify is_full is True when cache reaches capacity."""
        cache = self._get_cache()
        cache.configure(2)
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        self.assertTrue(cache.is_full)

    def test_is_full_false_below_capacity(self) -> None:
        """CUJ: Verify is_full is False when below capacity."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("key_1", "value_1")
        self.assertFalse(cache.is_full)

    # ------------------------------------------------------------------ #
    # configure tests
    # ------------------------------------------------------------------ #

    def test_configure_valid_capacity(self) -> None:
        """CUJ: Verify configure with valid capacity."""
        cache = self._get_cache()
        cache.configure(50)
        self.assertEqual(cache.capacity, 50)

    def test_configure_invalid_capacity_raises(self) -> None:
        """CUJ: Verify configure raises CacheCapacityError for zero capacity."""
        cache = self._get_cache()
        with self.assertRaises(CacheCapacityError):
            cache.configure(0)

    def test_configure_invalid_negative_capacity_raises(self) -> None:
        """CUJ: Verify configure raises CacheCapacityError for negative capacity."""
        cache = self._get_cache()
        with self.assertRaises(CacheCapacityError):
            cache.configure(-5)

    def test_configure_downsize_evicts_lru_entries(self) -> None:
        """CUJ: Verify downsize evicts least-recently-used entries."""
        cache = self._get_cache()
        cache.configure(5)
        for i in range(5):
            cache.put(_make_key(i), _make_value(i))
        cache.configure(2)
        self.assertEqual(cache.size, 2)
        # Only the two most recent keys remain
        self.assertIn("key_3", cache.keys_in_lru_order())
        self.assertIn("key_4", cache.keys_in_lru_order())
        self.assertEqual(len(cache.keys_in_lru_order()), 2)

    # ------------------------------------------------------------------ #
    # get tests
    # ------------------------------------------------------------------ #

    def test_get_hit_promotes_to_mru(self) -> None:
        """CUJ: Verify get returns value on hit and promotes key."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.put("key_3", "value_3")
        # Access key_1 to promote it
        result = cache.get("key_1", None)
        self.assertEqual(result, "value_1")
        # LRU order should show key_3 first (LRU) then key_1 (MRU)
        keys = cache.keys_in_lru_order()
        self.assertEqual(keys, ["key_2", "key_3", "key_1"])

    def test_get_hit_increments_hits_counter(self) -> None:
        """CUJ: Verify get increments hits on cache hit."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.get("key_1", None)
        stats = cache.get_stats()
        self.assertEqual(stats.hits, 1)

    def test_get_miss_returns_default(self) -> None:
        """CUJ: Verify get returns default on cache miss."""
        cache = self._get_cache()
        result = cache.get("nonexistent", "default_val")
        self.assertEqual(result, "default_val")

    def test_get_miss_returns_none_by_default(self) -> None:
        """CUJ: Verify get returns None when key absent and default is None."""
        cache = self._get_cache()
        result = cache.get("nonexistent", None)
        self.assertIsNone(result)

    def test_get_miss_increments_misses_counter(self) -> None:
        """CUJ: Verify get increments misses on cache miss."""
        cache = self._get_cache()
        cache.get("nonexistent", None)
        stats = cache.get_stats()
        self.assertEqual(stats.misses, 1)

    def test_get_miss_does_not_alter_access_order(self) -> None:
        """CUJ: Verify get miss does not alter LRU access order."""
        cache = self._get_cache()
        cache.configure(3)
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        keys_before = cache.keys_in_lru_order()
        cache.get("nonexistent", None)
        keys_after = cache.keys_in_lru_order()
        self.assertEqual(keys_before, keys_after)

    # ------------------------------------------------------------------ #
    # put tests
    # ------------------------------------------------------------------ #

    def test_put_insert_below_capacity(self) -> None:
        """CUJ: Verify put inserts new entry when below capacity."""
        cache = self._get_cache()
        result = cache.put("key_1", "value_1")
        self.assertIsNone(result)
        self.assertEqual(cache.size, 1)

    def test_put_update_existing_returns_none(self) -> None:
        """CUJ: Verify put updates existing key and returns None."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        result = cache.put("key_1", "updated_value")
        self.assertIsNone(result)
        self.assertEqual(cache.get("key_1", None), "updated_value")
        self.assertEqual(cache.size, 1)

    def test_put_update_existing_promotes_to_mru(self) -> None:
        """CUJ: Verify put promotes updated key to most-recently-used."""
        cache = self._get_cache()
        cache.configure(3)
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.put("key_3", "value_3")
        cache.put("key_1", "updated")
        keys = cache.keys_in_lru_order()
        self.assertEqual(keys, ["key_2", "key_3", "key_1"])

    def test_put_evicts_on_capacity(self) -> None:
        """CUJ: Verify put evicts LRU entry when at capacity."""
        cache = self._get_cache()
        cache.configure(2)
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        evicted = cache.put("key_3", "value_3")
        evicted_tuple: Tuple[str, str] = cast(Tuple[str, str], evicted)
        self.assertIsNotNone(evicted_tuple)
        self.assertEqual(evicted_tuple[0], "key_1")
        self.assertEqual(evicted_tuple[1], "value_1")
        self.assertEqual(cache.size, 2)

    def test_put_eviction_increments_evictions_counter(self) -> None:
        """CUJ: Verify put eviction increments eviction counter."""
        cache = self._get_cache()
        cache.configure(2)
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.put("key_3", "value_3")
        stats = cache.get_stats()
        self.assertEqual(stats.evictions, 1)

    def test_put_returns_none_when_no_eviction(self) -> None:
        """CUJ: Verify put returns None when no eviction occurs."""
        cache = self._get_cache()
        result = cache.put("key_1", "value_1")
        self.assertIsNone(result)
        result2 = cache.put("key_2", "value_2")
        self.assertIsNone(result2)

    # ------------------------------------------------------------------ #
    # peek tests
    # ------------------------------------------------------------------ #

    def test_peek_present_key_no_mutation(self) -> None:
        """CUJ: Verify peek returns value without altering recency order."""
        cache = self._get_cache()
        cache.configure(3)
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.put("key_3", "value_3")
        keys_before = cache.keys_in_lru_order()
        result = cache.peek("key_1", None)
        self.assertEqual(result, "value_1")
        keys_after = cache.keys_in_lru_order()
        self.assertEqual(keys_before, keys_after)

    def test_peek_absent_key_returns_default(self) -> None:
        """CUJ: Verify peek returns default for absent key."""
        cache = self._get_cache()
        result = cache.peek("nonexistent", "default")
        self.assertEqual(result, "default")

    def test_peek_does_not_increment_telemetry(self) -> None:
        """CUJ: Verify peek does not increment hits or misses."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.peek("key_1", None)
        cache.peek("nonexistent", None)
        stats = cache.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)

    def test_peek_does_not_increment_misses(self) -> None:
        """CUJ: Verify absent key peek does not increment misses counter."""
        cache = self._get_cache()
        cache.peek("absent", None)
        stats = cache.get_stats()
        self.assertEqual(stats.misses, 0)

    # ------------------------------------------------------------------ #
    # remove tests
    # ------------------------------------------------------------------ #

    def test_remove_existing_key(self) -> None:
        """CUJ: Verify remove returns value and decrements size."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        result = cache.remove("key_1")
        self.assertEqual(result, "value_1")
        self.assertEqual(cache.size, 0)

    def test_remove_nonexistent_key_raises(self) -> None:
        """CUJ: Verify remove raises CacheKeyNotFoundError for absent key."""
        cache = self._get_cache()
        with self.assertRaises(CacheKeyNotFoundError):
            cache.remove("nonexistent")

    def test_remove_moves_key_out_of_lru_order(self) -> None:
        """CUJ: Verify removed key disappears from LRU order."""
        cache = self._get_cache()
        cache.configure(3)
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.remove("key_1")
        keys = cache.keys_in_lru_order()
        self.assertEqual(keys, ["key_2"])
        self.assertNotIn("key_1", keys)

    # ------------------------------------------------------------------ #
    # clear tests
    # ------------------------------------------------------------------ #

    def test_clear_removes_all_entries(self) -> None:
        """CUJ: Verify clear removes all entries."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.clear()
        self.assertEqual(cache.size, 0)
        self.assertTrue(cache.is_empty)

    def test_clear_preserves_telemetry(self) -> None:
        """CUJ: Verify clear preserves telemetry counters."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.get("key_1", None)
        cache.get("missing", None)
        hits_before = cache.get_stats().hits
        cache.clear()
        stats = cache.get_stats()
        self.assertEqual(stats.hits, hits_before)
        self.assertEqual(stats.misses, 1)
        self.assertEqual(stats.evictions, 0)

    def test_clear_preserves_capacity(self) -> None:
        """CUJ: Verify clear does not reset capacity."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("key_1", "value_1")
        cache.clear()
        self.assertEqual(cache.capacity, 5)

    # ------------------------------------------------------------------ #
    # stats tests
    # ------------------------------------------------------------------ #

    def test_get_stats_report_telemetry(self) -> None:
        """CUJ: Verify get_stats returns accurate telemetry."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.get("key_1", None)
        cache.get("missing", None)
        stats = cache.get_stats()
        self.assertIsInstance(stats, CacheStats)
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)
        self.assertEqual(stats.evictions, 0)

    def test_get_stats_after_eviction(self) -> None:
        """CUJ: Verify get_stats includes eviction count."""
        cache = self._get_cache()
        cache.configure(2)
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.put("key_3", "value_3")
        stats = cache.get_stats()
        self.assertEqual(stats.evictions, 1)

    def test_reset_stats_resets_counters(self) -> None:
        """CUJ: Verify reset_stats zeroes all telemetry counters."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.get("key_1", None)
        cache.get("missing", None)
        cache.reset_stats()
        stats = cache.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(stats.evictions, 0)

    def test_reset_stats_preserves_entries(self) -> None:
        """CUJ: Verify reset_stats does not remove cached entries."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.reset_stats()
        self.assertEqual(cache.size, 2)
        self.assertEqual(cache.get("key_1", None), "value_1")
        self.assertEqual(cache.get("key_2", None), "value_2")

    # ------------------------------------------------------------------ #
    # keys_in_lru_order tests
    # ------------------------------------------------------------------ #

    def test_keys_in_lru_order_initially_empty(self) -> None:
        """CUJ: Verify keys_in_lru_order returns empty list initially."""
        cache = self._get_cache()
        self.assertEqual(cache.keys_in_lru_order(), [])

    def test_keys_in_lru_order_insertion_order(self) -> None:
        """CUJ: Verify keys are ordered LRU to MRU after sequential inserts."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.put("key_3", "value_3")
        keys = cache.keys_in_lru_order()
        self.assertEqual(keys, ["key_1", "key_2", "key_3"])

    def test_keys_in_lru_order_after_access(self) -> None:
        """CUJ: Verify keys reorder after get promotes accessed key."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.put("key_3", "value_3")
        cache.get("key_1", None)
        keys = cache.keys_in_lru_order()
        self.assertEqual(keys, ["key_2", "key_3", "key_1"])

    def test_keys_in_lru_order_is_non_mutating(self) -> None:
        """CUJ: Verify keys_in_lru_order does not alter recency or telemetry."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        keys_before = cache.keys_in_lru_order()
        stats_before = cache.get_stats()
        _ = cache.keys_in_lru_order()
        keys_after = cache.keys_in_lru_order()
        stats_after = cache.get_stats()
        self.assertEqual(keys_before, keys_after)
        self.assertEqual(stats_before, stats_after)

    def test_keys_in_lru_order_after_eviction(self) -> None:
        """CUJ: Verify keys exclude evicted entries."""
        cache = self._get_cache()
        cache.configure(2)
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.put("key_3", "value_3")
        keys = cache.keys_in_lru_order()
        self.assertEqual(keys, ["key_2", "key_3"])
        self.assertNotIn("key_1", keys)

    def test_keys_in_lru_order_after_remove(self) -> None:
        """CUJ: Verify keys exclude removed entries."""
        cache = self._get_cache()
        cache.put("key_1", "value_1")
        cache.put("key_2", "value_2")
        cache.remove("key_1")
        keys = cache.keys_in_lru_order()
        self.assertEqual(keys, ["key_2"])

    # ------------------------------------------------------------------ #
    # Combined scenario tests
    # ------------------------------------------------------------------ #

    def test_comprehensive_lru_workflow(self) -> None:
        """CUJ: Verify comprehensive LRU cache workflow with eviction and stats.

        Exercises multiple postconditions in a single scenario.
        """
        cache = self._get_cache()
        cache.configure(3)

        # Insert three entries
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertEqual(cache.size, 3)
        self.assertTrue(cache.is_full)

        # Access 'a' to promote it
        self.assertEqual(cache.get("a", None), 1)
        stats = cache.get_stats()
        self.assertEqual(stats.hits, 1)

        # Insert 'd' to trigger eviction of 'b' (LRU)
        evicted = cache.put("d", 4)
        self.assertIsNotNone(evicted)
        self.assertEqual(evicted, ("b", 2))
        self.assertEqual(cache.size, 3)
        self.assertEqual(cache.get_stats().evictions, 1)

        # Verify LRU order: b evicted, so order is c->a->d
        keys = cache.keys_in_lru_order()
        self.assertEqual(keys, ["c", "a", "d"])

        # Verify evicted key is gone - returns default when absent
        self.assertEqual(cache.get("b", "default"), "default")
        stats_miss = cache.get_stats()
        self.assertEqual(stats_miss.misses, 1)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T06:49:13Z
# LAST_CHANGED: 2026-11-09T04:40:40Z
# CHANGE: Fixed test_comprehensive_lru_workflow: changed assertIsNone to assertEqual with 'default' for the get call on evicted key, matching the contract postcondition [slug:lru_cache.get.miss] which specifies returning the default value when key is absent.
# COVERAGE_AUDIT: 2026-11-09T06:49:13Z
# QA_AUDIT: 2026-11-09T06:48:40Z
# --- END AUTOFAB METADATA ---
