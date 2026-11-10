"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Any, List

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


DEFAULT_CAPACITY = 10


class RingBufferImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initialization(self) -> None:
        """CUJ: Verify initial component presence."""
        self.assertIsNotNone(self.registry)
        for sym in [RingBuffer]:
            self.assertIsNotNone(sym)

    def test_initial_state_is_empty(self) -> None:
        """Happy path: a freshly created buffer is empty at its default capacity.

        Verifies the grounded initial state: capacity 10, size 0, is_empty True,
        is_full False, and an empty snapshot in FIFO order.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_push_available_capacity_stores_item_and_returns_none(self) -> None:
        """Happy path: pushing below capacity stores the item and returns None.

        WHEN size is less than capacity, MUST store item, increment size by 1,
        and return None.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertIsNone(buffer.push("alpha"))
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), ["alpha"])

    def test_push_to_capacity_marks_full(self) -> None:
        """Saturation: filling to capacity keeps returning None and flips is_full.

        Filling the buffer to capacity keeps each push returning None while
        size grows by one and is_full becomes True at capacity.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(DEFAULT_CAPACITY):
                self.assertIsNone(buffer.push(index))
                self.assertEqual(buffer.size, index + 1)
            self.assertEqual(buffer.size, DEFAULT_CAPACITY)
            self.assertTrue(buffer.is_full)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), list(range(DEFAULT_CAPACITY)))

    def test_push_overwrite_evicts_oldest(self) -> None:
        """Alternate: pushing onto a full buffer evicts and returns the oldest item.

        WHEN size equals capacity, MUST evict the oldest item, store the new item
        at the most recent position, maintain size at capacity, and return the
        evicted item.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(DEFAULT_CAPACITY):
                buffer.push(index)
            self.assertTrue(buffer.is_full)

            evicted = buffer.push(DEFAULT_CAPACITY)

            self.assertEqual(evicted, 0)
            self.assertEqual(buffer.size, DEFAULT_CAPACITY)
            self.assertTrue(buffer.is_full)
            self.assertEqual(
                buffer.snapshot_items(), list(range(1, DEFAULT_CAPACITY + 1))
            )
            self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)

    def test_repeated_overwrite_evicts_oldest_each_time(self) -> None:
        """Alternate: repeated pushes on a saturated buffer evict in FIFO order.

        Successive pushes on a saturated buffer must keep evicting and returning
        the then-oldest surviving item while size remains pinned at capacity.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(DEFAULT_CAPACITY):
                buffer.push(index)

            for offset in range(3):
                evicted = buffer.push(DEFAULT_CAPACITY + offset)
                self.assertEqual(evicted, offset)
                self.assertEqual(buffer.size, DEFAULT_CAPACITY)

            self.assertEqual(
                buffer.snapshot_items(), list(range(3, DEFAULT_CAPACITY + 3))
            )

    def test_pop_non_empty_returns_oldest(self) -> None:
        """Happy path: popping a non-empty buffer returns the oldest item.

        WHEN size is greater than zero, MUST remove the oldest item, decrement
        size by 1, and return the removed item.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("first")
            buffer.push("second")

            self.assertEqual(buffer.pop(), "first")
            self.assertEqual(buffer.size, 1)
            self.assertEqual(buffer.snapshot_items(), ["second"])

            self.assertEqual(buffer.pop(), "second")
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)

    def test_pop_empty_raises_buffer_empty_error(self) -> None:
        """Error: popping an empty buffer raises BufferEmptyError.

        WHEN size equals zero, MUST raise BufferEmptyError.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertTrue(buffer.is_empty)

            with self.assertRaises(BufferEmptyError):
                buffer.pop()

            self.assertEqual(buffer.size, 0)
            self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)

    def test_clear_resets_size(self) -> None:
        """Happy path: clearing removes every item and resets size to zero.

        MUST remove all items from the buffer and reset size to zero.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(DEFAULT_CAPACITY):
                buffer.push(index)
            self.assertEqual(buffer.size, DEFAULT_CAPACITY)

            buffer.clear()

            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_clear_then_reuse(self) -> None:
        """Alternate: a cleared buffer accepts new items via available capacity.

        A cleared buffer must accept new items through the normal available
        capacity path, returning None and preserving FIFO order.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("stale-one")
            buffer.push("stale-two")
            buffer.clear()

            self.assertIsNone(buffer.push("fresh"))
            self.assertEqual(buffer.size, 1)
            self.assertEqual(buffer.snapshot_items(), ["fresh"])

    def test_snapshot_items_preserves_fifo_order(self) -> None:
        """Happy path: the snapshot lists every stored item in FIFO arrival order.

        MUST return a list containing all currently stored items in FIFO arrival
        order from oldest to newest.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            items = ["a", "b", "c", "d"]
            for item in items:
                buffer.push(item)

            snapshot = buffer.snapshot_items()

            self.assertEqual(snapshot, items)
            self.assertEqual(buffer.size, len(items))

    def test_snapshot_items_does_not_mutate_buffer(self) -> None:
        """Happy path: taking a snapshot leaves buffer state untouched.

        MUST NOT modify buffer contents, size, capacity, or operational state;
        repeated snapshots agree and mutating a returned list leaves the buffer
        untouched.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("x")
            buffer.push("y")

            first: List[Any] = buffer.snapshot_items()
            second = buffer.snapshot_items()

            self.assertEqual(first, second)
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
            self.assertFalse(buffer.is_empty)

            first.append("injected")

            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.snapshot_items(), ["x", "y"])

    def test_fifo_order_survives_interleaved_push_and_pop(self) -> None:
        """INVARIANT: FIFO arrival order is preserved across interleaved operations."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push(1)
            buffer.push(2)
            buffer.push(3)

            self.assertEqual(buffer.pop(), 1)

            buffer.push(4)
            self.assertEqual(buffer.snapshot_items(), [2, 3, 4])

            self.assertEqual(buffer.pop(), 2)
            self.assertEqual(buffer.snapshot_items(), [3, 4])
            self.assertEqual(buffer.size, 2)

    def test_is_empty_tracks_buffer_lifecycle(self) -> None:
        """INVARIANT: is_empty reflects size transitions across the buffer lifecycle."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertTrue(buffer.is_empty)

            buffer.push("only")
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.size, 1)

            self.assertEqual(buffer.pop(), "only")
            self.assertTrue(buffer.is_empty)

    def test_capacity_remains_constant_under_operations(self) -> None:
        """INVARIANT: capacity is a fixed bound that never decreases with load."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(DEFAULT_CAPACITY + 5):
                buffer.push(index)
                self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
                self.assertLessEqual(buffer.size, DEFAULT_CAPACITY)
            self.assertTrue(buffer.is_full)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T18:41:27Z
# LAST_CHANGED: 2026-11-10T18:40:07Z
# CHANGE: Author comprehensive unit tests for RingBuffer impl: fix import to ring_buffer.lib.ring_buffer_impl, test lifecycle-scoped initialization, initial state (capacity 10, empty, not full), push available-capacity returning None, push saturation marking full, push overwrite eviction returning oldest, repeated eviction FIFO, pop non-empty returning oldest, pop empty raising BufferEmptyError, clear reset and reuse, snapshot FIFO order, snapshot non-mutation, interleaved FIFO invariant, is_empty lifecycle tracking, and fixed capacity invariant.
# COVERAGE_AUDIT: 2026-11-10T18:41:27Z
# QA_AUDIT: 2026-11-10T18:41:15Z
# --- END AUTOFAB METADATA ---
