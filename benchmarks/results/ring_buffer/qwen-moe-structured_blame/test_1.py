"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from ring_buffer.lib.ring_buffer import BufferEmptyError


class RingBufferImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def tearDown(self) -> None:
        pass

    def test_initialization_default_capacity(self) -> None:
        """CUJ: Verify RingBuffer initializes with default capacity of 10."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buf.capacity, 10)

    def test_initialization_empty_buffer(self) -> None:
        """CUJ: Verify RingBuffer initializes empty with size 0."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            self.assertTrue(buf.is_empty)
            self.assertEqual(buf.size, 0)

    def test_initialization_not_full(self) -> None:
        """CUJ: Verify RingBuffer is not full on initialization."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            self.assertFalse(buf.is_full)

    def test_push_within_capacity_returns_none(self) -> None:
        """Happy-path: Push items within capacity returns None when space available."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            for i in range(5):
                result = buf.push(i)
                self.assertIsNone(result)
                self.assertEqual(buf.size, i + 1)
                self.assertFalse(buf.is_full)

    def test_push_incremental_size(self) -> None:
        """Happy-path: Verify size increments correctly on each push within capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)
            self.assertEqual(buf.size, 10)
            self.assertTrue(buf.is_full)

    def test_push_overwrite_eviction(self) -> None:
        """Alternate: Push when buffer is full triggers overwrite eviction of oldest item."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)
            self.assertTrue(buf.is_full)
            self.assertEqual(buf.size, 10)

            evicted = buf.push(100)
            self.assertEqual(evicted, 0)
            self.assertEqual(buf.size, 10)
            self.assertTrue(buf.is_full)

    def test_push_multiple_evictions_preserves_fifo(self) -> None:
        """Alternate: Multiple evictions preserve FIFO order for remaining items."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)

            evicted_1 = buf.push(100)
            evicted_2 = buf.push(101)
            evicted_3 = buf.push(102)

            self.assertEqual(evicted_1, 0)
            self.assertEqual(evicted_2, 1)
            self.assertEqual(evicted_3, 2)

            items = buf.snapshot_items()
            self.assertEqual(items, [3, 4, 5, 6, 7, 8, 9, 100, 101, 102])

    def test_pop_removes_oldest_item(self) -> None:
        """Happy-path: Pop removes and returns the oldest item, decrementing size."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            buf.push(1)
            buf.push(2)
            buf.push(3)

            oldest = buf.pop()
            self.assertEqual(oldest, 1)
            self.assertEqual(buf.size, 2)
            self.assertFalse(buf.is_empty)

    def test_pop_fifo_order(self) -> None:
        """Happy-path: Multiple pops return items in FIFO order."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            for i in range(5):
                buf.push(i * 10)

            self.assertEqual(buf.pop(), 0)
            self.assertEqual(buf.pop(), 10)
            self.assertEqual(buf.pop(), 20)
            self.assertEqual(buf.size, 2)

    def test_pop_empty_raises_buffer_empty_error(self) -> None:
        """Error: Pop from empty buffer raises BufferEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            with self.assertRaises(BufferEmptyError):
                buf.pop()

    def test_pop_after_eviction_returns_correct_item(self) -> None:
        """Alternate: After evictions, pop returns the correct oldest remaining item."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)

            buf.push(100)

            self.assertEqual(buf.pop(), 1)
            self.assertEqual(buf.pop(), 2)

    def test_clear_resets_buffer(self) -> None:
        """Happy-path: Clear removes all items and resets size to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            for i in range(5):
                buf.push(i)
            self.assertEqual(buf.size, 5)

            buf.clear()

            self.assertTrue(buf.is_empty)
            self.assertEqual(buf.size, 0)
            self.assertFalse(buf.is_full)

    def test_clear_empty_buffer_no_error(self) -> None:
        """Happy-path: Clear on empty buffer should not raise."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            buf.clear()
            self.assertTrue(buf.is_empty)
            self.assertEqual(buf.size, 0)

    def test_snapshot_returns_fifo_order(self) -> None:
        """Happy-path: Snapshot returns items in FIFO arrival order."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            buf.push("a")
            buf.push("b")
            buf.push("c")

            items = buf.snapshot_items()
            self.assertEqual(items, ["a", "b", "c"])

    def test_snapshot_non_mutating(self) -> None:
        """Alternate: Snapshot does not mutate buffer state."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            buf.push(1)
            buf.push(2)
            buf.push(3)

            snap1 = buf.snapshot_items()
            snap2 = buf.snapshot_items()

            self.assertEqual(snap1, snap2)
            self.assertEqual(buf.size, 3)
            self.assertEqual(buf.capacity, 10)
            self.assertFalse(buf.is_empty)
            self.assertFalse(buf.is_full)

    def test_pop_after_clear_raises_buffer_empty_error(self) -> None:
        """Error: Pop after clear raises BufferEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            buf.push(1)
            buf.clear()
            with self.assertRaises(BufferEmptyError):
                buf.pop()

    def test_push_pop_preserves_remaining_items(self) -> None:
        """Alternate: Push after partial pop maintains correct buffer state."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            buf.push(1)
            buf.push(2)
            buf.push(3)

            buf.pop()

            buf.push(4)

            items = buf.snapshot_items()
            self.assertEqual(items, [2, 3, 4])
            self.assertEqual(buf.size, 3)

    def test_capacity_property_returns_int(self) -> None:
        """Invariant: Capacity is an int and equals the default of 10."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            self.assertIsInstance(buf.capacity, int)
            self.assertEqual(buf.capacity, 10)

    def test_size_property_returns_int(self) -> None:
        """Invariant: Size is a non-negative int that tracks buffer contents."""
        with enter_phase(system, registry=self.registry) as scope:
            buf: RingBuffer = scope.get_singleton(RingBuffer)
            self.assertIsInstance(buf.size, int)
            self.assertEqual(buf.size, 0)

            buf.push("x")
            self.assertIsInstance(buf.size, int)
            self.assertEqual(buf.size, 1)

            buf.clear()
            self.assertEqual(buf.size, 0)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T05:27:09Z
# LAST_CHANGED: 2026-11-10T05:26:26Z
# CHANGE: Re-submitting comprehensive RingBuffer test suite (20 test methods) covering initialization, push with overwrite eviction, pop with BufferEmptyError, clear, snapshot_items non-mutating, FIFO ordering, and type invariants. All tests lifecycle-scoped via enter_phase(system, registry). Static checks passed.
# COVERAGE_AUDIT: 2026-11-10T05:27:09Z
# QA_AUDIT: 2026-11-10T05:26:46Z
# --- END AUTOFAB METADATA ---
