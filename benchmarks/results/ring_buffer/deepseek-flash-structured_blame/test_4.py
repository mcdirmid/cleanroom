from __future__ import annotations

import unittest

from ring_buffer.lib.ring_buffer import (
    BufferEmptyError,
)
from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


class RingBufferImplTest(unittest.TestCase):
    """Unit tests for the RingBuffer singleton realized by ring_buffer_impl.py.

    Every test runs inside an active ``system`` lifecycle phase so the buffer
    singleton can be resolved from a per-test registry, following the contracts
    declared in low/ring_buffer_impl.pyi and low/ring_buffer.pyi.
    """

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state_reflects_default_capacity(self) -> None:
        """A fresh buffer starts empty with the grounded default capacity of 10."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buffer.capacity, 10)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_push_with_available_capacity_stores_item_and_returns_none(self) -> None:
        """When size is less than capacity, the item is stored, size grows by one,
        and None is returned.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertIsNone(buffer.push(1))
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertIsNone(buffer.push(2))
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.snapshot_items(), [1, 2])

    def test_push_when_full_evicts_oldest_item(self) -> None:
        """When size equals capacity, the oldest item is evicted, the new item is
        stored at the most recent position, size stays at capacity, and the evicted
        item is returned.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(1, buffer.capacity + 1):
                self.assertIsNone(buffer.push(value))
            self.assertTrue(buffer.is_full)
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertEqual(buffer.push(11), 1)
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertTrue(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
            self.assertEqual(buffer.push(12), 2)
            self.assertEqual(buffer.snapshot_items(), [3, 4, 5, 6, 7, 8, 9, 10, 11, 12])

    def test_pop_removes_and_returns_oldest_item(self) -> None:
        """When size is greater than zero, the oldest item is removed, size
        decrements by one, and the removed item is returned.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push(1)
            buffer.push(2)
            buffer.push(3)
            self.assertEqual(buffer.pop(), 1)
            self.assertEqual(buffer.size, 2)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), [2, 3])
            self.assertEqual(buffer.pop(), 2)
            self.assertEqual(buffer.pop(), 3)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)

    def test_pop_empty_buffer_raises_buffer_empty_error(self) -> None:
        """When size equals zero, popping raises BufferEmptyError without
        altering the empty state.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            with self.assertRaises(BufferEmptyError):
                buffer.pop()
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)

            buffer.push(7)
            self.assertEqual(buffer.pop(), 7)
            with self.assertRaises(BufferEmptyError):
                buffer.pop()
            self.assertEqual(buffer.size, 0)

    def test_clear_removes_all_items_and_resets_size(self) -> None:
        """Clearing removes all items and resets size to zero while preserving
        capacity so the buffer can accept new items.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(1, buffer.capacity + 1):
                buffer.push(value)
            self.assertTrue(buffer.is_full)
            buffer.clear()
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])
            self.assertEqual(buffer.capacity, 10)
            self.assertIsNone(buffer.push(99))
            self.assertEqual(buffer.size, 1)
            self.assertEqual(buffer.snapshot_items(), [99])

    def test_snapshot_items_returns_fifo_arrival_order(self) -> None:
        """A snapshot lists all currently stored items in FIFO arrival order,
        including across overwrite eviction.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buffer.snapshot_items(), [])
            buffer.push(1)
            buffer.push(2)
            buffer.push(3)
            self.assertEqual(buffer.snapshot_items(), [1, 2, 3])
            for value in range(4, buffer.capacity + 1):
                buffer.push(value)
            self.assertEqual(buffer.snapshot_items(), list(range(1, 11)))
            self.assertEqual(buffer.push(11), 1)
            self.assertEqual(buffer.snapshot_items(), list(range(2, 12)))

    def test_snapshot_items_does_not_mutate_buffer_state(self) -> None:
        """Snapshotting must not modify buffer contents, size, capacity, or
        operational state.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push(1)
            buffer.push(2)
            first = buffer.snapshot_items()
            second = buffer.snapshot_items()
            self.assertEqual(first, [1, 2])
            self.assertEqual(second, [1, 2])
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.capacity, 10)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.pop(), 1)
            self.assertEqual(buffer.snapshot_items(), [2])

    def test_push_pop_cycle_after_wraparound_preserves_fifo_order(self) -> None:
        """Push/pop operations across capacity boundaries preserve FIFO ordering."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(1, 11):
                buffer.push(value)
            self.assertEqual(buffer.pop(), 1)
            self.assertEqual(buffer.pop(), 2)
            self.assertEqual(buffer.size, 8)
            self.assertIsNone(buffer.push(11))
            self.assertIsNone(buffer.push(12))
            self.assertEqual(buffer.size, 10)
            self.assertTrue(buffer.is_full)
            self.assertEqual(
                buffer.snapshot_items(),
                [3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
            )
            self.assertEqual(buffer.pop(), 3)
            self.assertIsNone(buffer.push(13))
            self.assertEqual(buffer.push(14), 4)
            self.assertEqual(
                buffer.snapshot_items(),
                [5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
            )


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T05:14:37Z
# LAST_CHANGED: 2026-11-11T05:12:21Z
# CHANGE: Author ring_buffer_impl unit tests: lifecycle-scoped coverage of default capacity/empty state, push available-capacity and overwrite-eviction branches, pop non-empty and empty BufferEmptyError, clear reset, snapshot FIFO order and non-mutation, and push/pop wraparound ordering.
# COVERAGE_AUDIT: 2026-11-11T05:14:37Z
# QA_AUDIT: 2026-11-11T05:14:15Z
# --- END AUTOFAB METADATA ---
