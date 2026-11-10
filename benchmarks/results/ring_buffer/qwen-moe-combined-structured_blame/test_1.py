"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from ring_buffer.lib import ring_buffer


class RingBufferImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def tearDown(self) -> None:
        self.registry = None

    # -- Initialization --

    def test_singleton_registered(self) -> None:
        """CUJ: Verify singleton is resolvable from registry."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            self.assertIsNotNone(instance)

    # -- Property contracts --

    def test_capacity_returns_default_ten(self) -> None:
        """CUJ: capacity property returns 10 by default."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            self.assertEqual(instance.capacity, 10)

    def test_size_is_zero_initially(self) -> None:
        """CUJ: size property returns 0 for an empty buffer."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            self.assertEqual(instance.size, 0)

    def test_is_empty_is_true_initially(self) -> None:
        """CUJ: is_empty returns True when buffer has no items."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            self.assertTrue(instance.is_empty)

    def test_is_full_is_false_initially(self) -> None:
        """CUJ: is_full returns False when buffer is below capacity."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            self.assertFalse(instance.is_full)

    # -- Push postconditions --

    def test_push_available_capacity_returns_none(self) -> None:
        """CUJ: push returns None when size < capacity (POST: available_capacity)."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            result = instance.push(42)
            self.assertIsNone(result)
            self.assertEqual(instance.size, 1)

    def test_push_incremental_size_growth(self) -> None:
        """CUJ: each push below capacity increments size by 1."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            for i in range(5):
                instance.push(i)
            self.assertEqual(instance.size, 5)

    def test_push_sets_is_full_at_capacity(self) -> None:
        """CUJ: is_full becomes True once capacity items are stored."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            for i in range(10):
                instance.push(i)
            self.assertTrue(instance.is_full)

    def test_push_overwrite_eviction_returns_evicted_item(self) -> None:
        """CUJ: push at capacity evicts oldest item and returns it (POST: overwrite_eviction)."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            for i in range(10):
                instance.push(i)
            self.assertEqual(instance.size, 10)
            evicted = instance.push(99)
            self.assertEqual(evicted, 0)
            self.assertEqual(instance.size, 10)

    def test_push_fifo_order_after_eviction(self) -> None:
        """CUJ: snapshot_items shows correct FIFO order after eviction cycles."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            for i in range(10):
                instance.push(i)
            evicted = instance.push(99)
            self.assertEqual(evicted, 0)
            self.assertEqual(instance.size, 10)
            evicted2 = instance.push(100)
            self.assertEqual(evicted2, 1)
            self.assertEqual(instance.size, 10)
            items = instance.snapshot_items()
            self.assertEqual(items, [2, 3, 4, 5, 6, 7, 8, 9, 99, 100])

    # -- Pop preconditions and postconditions --

    def test_pop_empty_raises_buffer_empty_error(self) -> None:
        """CUJ: pop on empty buffer raises BufferEmptyError (PRE: empty_buffer)."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            with self.assertRaises(ring_buffer.BufferEmptyError):
                instance.pop()

    def test_pop_returns_oldest_item(self) -> None:
        """CUJ: pop returns the oldest item in FIFO order (POST: non_empty)."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            for i in range(5):
                instance.push(i)
            first = instance.pop()
            self.assertEqual(first, 0)
            self.assertEqual(instance.size, 4)

    def test_pop_decrements_size(self) -> None:
        """CUJ: pop decrements size by 1."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            instance.push("a")
            instance.push("b")
            instance.pop()
            self.assertEqual(instance.size, 1)

    def test_pop_empty_decrements_to_zero(self) -> None:
        """CUJ: pop last item reduces size to zero and sets is_empty True."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            instance.push(42)
            instance.pop()
            self.assertEqual(instance.size, 0)
            self.assertTrue(instance.is_empty)

    # -- Clear postcondition --

    def test_clear_resets_size_to_zero(self) -> None:
        """CUJ: clear removes all items and resets size to zero (POST: reset_size)."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            for i in range(5):
                instance.push(i)
            instance.clear()
            self.assertEqual(instance.size, 0)
            self.assertTrue(instance.is_empty)

    def test_clear_is_not_full_after_fill(self) -> None:
        """CUJ: clear after filling buffer sets is_full to False."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            for i in range(10):
                instance.push(i)
            self.assertTrue(instance.is_full)
            instance.clear()
            self.assertFalse(instance.is_full)

    # -- snapshot_items postconditions --

    def test_snapshot_items_fifo_order(self) -> None:
        """CUJ: snapshot_items returns items in FIFO arrival order (POST: fifo_order)."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            instance.push(1)
            instance.push(2)
            instance.push(3)
            items = instance.snapshot_items()
            self.assertEqual(items, [1, 2, 3])

    def test_snapshot_items_non_mutating(self) -> None:
        """CUJ: snapshot_items does not modify buffer contents or state (POST: non_mutating)."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            for i in range(3):
                instance.push(i)
            size_before = instance.size
            empty_before = instance.is_empty
            snapshot = instance.snapshot_items()
            self.assertEqual(instance.size, size_before)
            self.assertEqual(instance.is_empty, empty_before)
            # Snapshot is a copy, mutating it does not affect the buffer.
            snapshot.append(999)
            self.assertNotIn(999, instance.snapshot_items())

    def test_snapshot_items_empty_returns_empty_list(self) -> None:
        """CUJ: snapshot_items on empty buffer returns an empty list."""
        with enter_phase("system", registry=self.registry) as scope:
            instance = scope.get_singleton(RingBuffer)
            self.assertEqual(instance.snapshot_items(), [])


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T17:06:53Z
# LAST_CHANGED: 2026-11-10T17:05:56Z
# CHANGE: Fixed test_push_fifo_order_after_eviction: after filling buffer with 0-9 and pushing 99 (evicting 0), the buffer remains full so push(100) also evicts and returns 1, not None. Updated assertions to verify correct chaining of eviction cycles.
# COVERAGE_AUDIT: 2026-11-10T17:06:53Z
# QA_AUDIT: 2026-11-10T17:06:29Z
# --- END AUTOFAB METADATA ---
