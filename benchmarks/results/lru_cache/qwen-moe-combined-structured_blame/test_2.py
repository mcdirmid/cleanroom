"""Unit tests for lru_cache_impl per its grounding specification."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from lru_cache.lib.lru_cache_impl import (
    LRUCache,
    __initialize__,
)
from lru_cache.lib.lru_cache import (
    CacheCapacityError,
    CacheKeyNotFoundError,
    CacheStats,
)


# --- Mock helpers for collaborator wiring (none needed for standalone LRUCache) ---


class LruCacheImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase("system", registry=self.registry)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _get_cache(self) -> LRUCache:
        """Resolve the LRUCache singleton from the active phase scope."""
        return self.phase_scope.get_singleton(LRUCache)

    # -- Lifecycle initialization --

    def test_initialization(self) -> None:
        """CUJ: Verify initial component presence."""
        self.assertIsNotNone(self.registry)
        for sym in [LRUCache]:
            self.assertIsNotNone(sym)

    # -- Property invariants --

    def test_properties_default_state(self) -> None:
        """INVARIANT: Default cache has capacity 100, size 0, is_empty True, is_full False."""
        cache = self._get_cache()
        self.assertEqual(cache.capacity, 100)
        self.assertEqual(cache.size, 0)
        self.assertTrue(cache.is_empty)
        self.assertFalse(cache.is_full)

    def test_is_full_at_capacity(self) -> None:
        """INVARIANT: is_full becomes True when size equals capacity."""
        cache = self._get_cache()
        # Fill cache to capacity
        for i in range(100):
            cache.put(f"key_{i}", f"value_{i}")
        self.assertTrue(cache.is_full)
        self.assertEqual(cache.size, 100)

    # -- configure (capacity + eviction on downsize) --

    def test_configure_updates_capacity(self) -> None:
        """POSTCONDITION: configure MUST update the cache capacity limit."""
        cache = self._get_cache()
        cache.configure(50)
        self.assertEqual(cache.capacity, 50)
        self.assertEqual(cache.size, 0)

    def test_configure_invalid_capacity_raises(self) -> None:
        """PRECONDITION: WHEN capacity <= 0, MUST raise CacheCapacityError."""
        cache = self._get_cache()
        with self.assertRaises(CacheCapacityError):
            cache.configure(0)
        with self.assertRaises(CacheCapacityError):
            cache.configure(-5)

    def test_configure_downsize_evicts_lru_entries(self) -> None:
        """POSTCONDITION: WHEN new capacity < current size, MUST evict LRU entries in sequence."""
        cache = self._get_cache()
        cache.configure(10)
        # Fill to capacity
        for i in range(10):
            cache.put(f"key_{i}", f"value_{i}")
        self.assertEqual(cache.size, 10)
        old_evictions = cache.get_stats().evictions

        # Downsize: capacity 10 -> 3, should evict 7 LRU entries
        cache.configure(3)
        self.assertEqual(cache.capacity, 3)
        self.assertEqual(cache.size, 3)
        # Evictions counter should reflect the 7 evicted entries
        self.assertEqual(cache.get_stats().evictions, old_evictions + 7)
        # Remaining keys should be the most recently added
        keys = cache.keys_in_lru_order()
        self.assertEqual(keys, ["key_7", "key_8", "key_9"])

    def test_configure_upsize_no_eviction(self) -> None:
        """POSTCONDITION: WHEN new capacity > current size, no eviction occurs."""
        cache = self._get_cache()
        cache.configure(5)
        for i in range(3):
            cache.put(f"key_{i}", f"value_{i}")
        old_evictions = cache.get_stats().evictions
        cache.configure(20)
        self.assertEqual(cache.capacity, 20)
        self.assertEqual(cache.size, 3)
        self.assertEqual(cache.get_stats().evictions, old_evictions)

    # -- get (hit / miss + telemetry + LRU promotion) --

    def test_get_hit_promotes_to_mru(self) -> None:
        """POSTCONDITION: WHEN key present, MUST return value, promote to MRU, increment hits."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # Access "a" to promote it
        result = cache.get("a", None)
        self.assertEqual(result, 1)
        self.assertEqual(cache.get_stats().hits, 1)
        self.assertEqual(cache.get_stats().misses, 0)
        # "a" should now be the MRU
        self.assertEqual(cache.keys_in_lru_order(), ["b", "c", "a"])

    def test_get_miss_returns_default(self) -> None:
        """POSTCONDITION: WHEN key absent, MUST return default and increment misses."""
        cache = self._get_cache()
        cache.put("a", 1)
        result = cache.get("nonexistent", "fallback")
        self.assertEqual(result, "fallback")
        self.assertEqual(cache.get_stats().hits, 0)
        self.assertEqual(cache.get_stats().misses, 1)

    # -- put (update existing / insert / evict) --

    def test_put_update_existing_returns_none(self) -> None:
        """POSTCONDITION: WHEN key exists, MUST update value, promote to MRU, return None."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("a", 1)
        result = cache.put("a", 2)
        self.assertIsNone(result)
        self.assertEqual(cache.get("a", None), 2)
        self.assertEqual(cache.size, 1)

    def test_put_insert_below_capacity(self) -> None:
        """POSTCONDITION: WHEN key new and size < capacity, MUST store entry, return None."""
        cache = self._get_cache()
        cache.configure(5)
        result = cache.put("a", 1)
        self.assertIsNone(result)
        self.assertEqual(cache.size, 1)
        self.assertEqual(cache.get("a", None), 1)

    def test_put_evict_on_capacity(self) -> None:
        """POSTCONDITION: WHEN key new and at capacity, MUST evict LRU entry and return it."""
        cache = self._get_cache()
        cache.configure(3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # Cache is full, inserting "d" should evict "a" (LRU)
        result = cache.put("d", 4)
        self.assertEqual(result, ("a", 1))
        self.assertEqual(cache.size, 3)
        self.assertEqual(cache.get_stats().evictions, 1)
        self.assertIsNone(cache.get("a", None))  # evicted
        self.assertEqual(cache.keys_in_lru_order(), ["b", "c", "d"])

    # -- peek (non-mutating observation) --

    def test_peek_present_key(self) -> None:
        """POSTCONDITION: WHEN key present, MUST return value without modifying order or counters."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("a", 1)
        cache.put("b", 2)
        before_order = cache.keys_in_lru_order()
        before_stats = cache.get_stats()
        result = cache.peek("a", None)
        self.assertEqual(result, 1)
        self.assertEqual(cache.keys_in_lru_order(), before_order)
        self.assertEqual(cache.get_stats(), before_stats)

    def test_peek_absent_key(self) -> None:
        """POSTCONDITION: WHEN key absent, MUST return default without modifying state."""
        cache = self._get_cache()
        before_stats = cache.get_stats()
        result = cache.peek("nonexistent", "default")
        self.assertEqual(result, "default")
        self.assertEqual(cache.get_stats(), before_stats)

    # -- remove (existing / missing key) --

    def test_remove_existing_key(self) -> None:
        """POSTCONDITION: WHEN key exists, MUST remove entry, decrement size, return value."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("a", 1)
        cache.put("b", 2)
        result = cache.remove("a")
        self.assertEqual(result, 1)
        self.assertEqual(cache.size, 1)
        self.assertIsNone(cache.get("a", None))

    def test_remove_nonexistent_key_raises(self) -> None:
        """PRECONDITION: WHEN key absent, MUST raise CacheKeyNotFoundError."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("a", 1)
        with self.assertRaises(CacheKeyNotFoundError):
            cache.remove("nonexistent")

    # -- clear (resets entries, preserves telemetry) --

    def test_clear_preserves_telemetry(self) -> None:
        """POSTCONDITION: MUST remove all entries but preserve telemetry counters."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a", None)
        cache.get("missing", None)
        before_clear_stats = cache.get_stats()
        self.assertEqual(before_clear_stats.hits, 1)
        self.assertEqual(before_clear_stats.misses, 1)
        self.assertEqual(before_clear_stats.evictions, 0)

        cache.clear()
        self.assertTrue(cache.is_empty)
        self.assertEqual(cache.size, 0)
        # Telemetry preserved
        stats = cache.get_stats()
        self.assertEqual(stats.hits, before_clear_stats.hits)
        self.assertEqual(stats.misses, before_clear_stats.misses)
        self.assertEqual(stats.evictions, before_clear_stats.evictions)

    # -- telemetry (stats + reset) --

    def test_get_stats_reports_telemetry(self) -> None:
        """POSTCONDITION: MUST return CacheStats reflecting cumulative hits, misses, evictions."""
        cache = self._get_cache()
        cache.configure(3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)  # evicts "a"
        cache.get("a", None)  # miss
        cache.get("b", None)  # hit

        stats = cache.get_stats()
        self.assertIsInstance(stats, CacheStats)
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)
        self.assertEqual(stats.evictions, 1)

    def test_reset_stats_zeroes_counters(self) -> None:
        """POSTCONDITION: MUST reset hits, misses, evictions to zero without altering entries."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("a", 1)
        cache.get("a", None)
        cache.reset_stats()
        stats = cache.get_stats()
        self.assertEqual(stats.hits, 0)
        self.assertEqual(stats.misses, 0)
        self.assertEqual(stats.evictions, 0)
        # Entries preserved
        self.assertEqual(cache.size, 1)
        self.assertEqual(cache.get("a", None), 1)

    # -- keys_in_lru_order (test-only observability) --

    def test_keys_in_lru_order_reflects_access_recency(self) -> None:
        """POSTCONDITION: MUST return all active keys ordered LRU to MRU."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("first", 1)
        cache.put("second", 2)
        cache.put("third", 3)
        # Access "first" to make it MRU
        cache.get("first", None)
        # Order: second (LRU), third, first (MRU)
        self.assertEqual(
            cache.keys_in_lru_order(),
            ["second", "third", "first"],
        )

    def test_keys_in_lru_order_non_mutating(self) -> None:
        """POSTCONDITION: MUST NOT alter access recency order or increment counters."""
        cache = self._get_cache()
        cache.configure(5)
        cache.put("a", 1)
        cache.put("b", 2)
        before_order = cache.keys_in_lru_order()
        before_stats = cache.get_stats()
        cache.keys_in_lru_order()
        after_order = cache.keys_in_lru_order()
        after_stats = cache.get_stats()
        self.assertEqual(after_order, before_order)
        self.assertEqual(after_stats, before_stats)

    def test_keys_in_lru_order_empty_cache(self) -> None:
        """POSTCONDITION: Empty cache returns empty list."""
        cache = self._get_cache()
        self.assertEqual(cache.keys_in_lru_order(), [])


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T07:34:33Z
# LAST_CHANGED: 2026-11-09T07:16:08Z
# CHANGE: Implemented comprehensive unit tests for LRUCache lifecycle-managed singleton covering all low-level contracts: initialization, property invariants (capacity/size/is_empty/is_full), configure (capacity update, invalid capacity error, downsize eviction), get (hit with LRU promotion, miss with telemetry), put (update existing, insert below capacity, evict on capacity), peek (non-mutating observation for present/absent keys), remove (existing key return, missing key error), clear (entry reset with telemetry preservation), telemetry (stats reporting, counter reset), and keys_in_lru_order (LRU-to-MRU ordering, non-mutating, empty cache). All tests use lifecycle phase scoping pattern with enter_phase and resolve the singleton from the active scope.
# COVERAGE_AUDIT: 2026-11-09T07:34:33Z
# QA_AUDIT: 2026-11-09T07:34:10Z
# --- END AUTOFAB METADATA ---
