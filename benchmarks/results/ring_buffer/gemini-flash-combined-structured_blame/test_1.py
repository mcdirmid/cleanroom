from __future__ import annotations

import unittest
from typing import Any, List

from ring_buffer.lib.ring_buffer import BufferEmptyError, BufferError
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


class RingBufferImplTest(unittest.TestCase):
    """Unit tests for RingBuffer circular buffer implementation."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_buffer_state(self) -> None:
        """Verify initial state of freshly created ring buffer singleton."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            self.assertEqual(buf.capacity, 10)
            self.assertEqual(buf.size, 0)
            self.assertTrue(buf.is_empty)
            self.assertFalse(buf.is_full)
            self.assertEqual(buf.snapshot_items(), [])

    def test_push_available_capacity(self) -> None:
        """Verify push stores item and returns None when capacity is available."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            result = buf.push("item_1")
            self.assertIsNone(result)
            self.assertEqual(buf.size, 1)
            self.assertFalse(buf.is_empty)
            self.assertFalse(buf.is_full)
            self.assertEqual(buf.snapshot_items(), ["item_1"])

    def test_push_multiple_items_within_capacity(self) -> None:
        """Verify multiple sequential pushes within available capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(9):
                result = buf.push(f"val_{i}")
                self.assertIsNone(result)
                self.assertEqual(buf.size, i + 1)
                self.assertFalse(buf.is_empty)
                self.assertFalse(buf.is_full)

    def test_push_reaches_full_capacity(self) -> None:
        """Verify pushing up to maximum capacity marks buffer as full."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(10):
                result = buf.push(i)
                self.assertIsNone(result)

            self.assertEqual(buf.size, 10)
            self.assertFalse(buf.is_empty)
            self.assertTrue(buf.is_full)
            self.assertEqual(buf.snapshot_items(), list(range(10)))

    def test_push_overwrite_eviction_when_full(self) -> None:
        """Verify overwrite eviction on saturation when size equals capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)

            evicted_first = buf.push(10)
            self.assertEqual(evicted_first, 0)
            self.assertEqual(buf.size, 10)
            self.assertTrue(buf.is_full)

            evicted_second = buf.push(11)
            self.assertEqual(evicted_second, 1)
            self.assertEqual(buf.size, 10)
            self.assertTrue(buf.is_full)

            expected_items = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
            self.assertEqual(buf.snapshot_items(), expected_items)

    def test_pop_empty_buffer_raises_buffer_empty_error(self) -> None:
        """Verify popping an empty buffer raises BufferEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            self.assertEqual(buf.size, 0)
            with self.assertRaises(BufferEmptyError):
                buf.pop()

    def test_pop_single_item(self) -> None:
        """Verify pop removes and returns oldest item and decrements size."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.push("first")
            self.assertEqual(buf.size, 1)

            popped = buf.pop()
            self.assertEqual(popped, "first")
            self.assertEqual(buf.size, 0)
            self.assertTrue(buf.is_empty)
            self.assertFalse(buf.is_full)

    def test_pop_fifo_ordering(self) -> None:
        """Verify FIFO ordering when popping multiple items in sequence."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.push("item_a")
            buf.push("item_b")
            buf.push("item_c")

            self.assertEqual(buf.pop(), "item_a")
            self.assertEqual(buf.size, 2)
            self.assertEqual(buf.pop(), "item_b")
            self.assertEqual(buf.size, 1)
            self.assertEqual(buf.pop(), "item_c")
            self.assertEqual(buf.size, 0)
            self.assertTrue(buf.is_empty)

    def test_pop_after_overwrite_eviction(self) -> None:
        """Verify FIFO pop returns correct items after overwrite eviction."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)

            buf.push(10)
            buf.push(11)

            popped = buf.pop()
            self.assertEqual(popped, 2)
            self.assertEqual(buf.size, 9)
            self.assertFalse(buf.is_full)

    def test_pop_until_exhausted_raises_on_subsequent_pop(self) -> None:
        """Verify popping until empty and asserting BufferEmptyError on next pop."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.push(42)
            self.assertEqual(buf.pop(), 42)
            self.assertEqual(buf.size, 0)

            with self.assertRaises(BufferEmptyError):
                buf.pop()

    def test_clear_resets_size_and_removes_all_items(self) -> None:
        """Verify clear removes all items and resets size to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(5):
                buf.push(i)

            self.assertEqual(buf.size, 5)
            buf.clear()

            self.assertEqual(buf.size, 0)
            self.assertTrue(buf.is_empty)
            self.assertFalse(buf.is_full)
            self.assertEqual(buf.snapshot_items(), [])

            with self.assertRaises(BufferEmptyError):
                buf.pop()

    def test_clear_on_full_buffer(self) -> None:
        """Verify clear resets a completely full buffer."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            for i in range(10):
                buf.push(i)

            self.assertTrue(buf.is_full)
            buf.clear()

            self.assertEqual(buf.size, 0)
            self.assertTrue(buf.is_empty)
            self.assertFalse(buf.is_full)

            result = buf.push("after_clear")
            self.assertIsNone(result)
            self.assertEqual(buf.size, 1)

    def test_clear_on_already_empty_buffer(self) -> None:
        """Verify clear on an already empty buffer is safe and preserves state."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            self.assertEqual(buf.size, 0)
            buf.clear()
            self.assertEqual(buf.size, 0)
            self.assertTrue(buf.is_empty)

    def test_snapshot_items_fifo_order(self) -> None:
        """Verify snapshot_items returns items ordered from oldest to newest arrival."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            self.assertEqual(buf.snapshot_items(), [])

            items = ["alpha", "beta", "gamma"]
            for item in items:
                buf.push(item)

            self.assertEqual(buf.snapshot_items(), items)

    def test_snapshot_items_non_mutating(self) -> None:
        """Verify snapshot_items does not mutate buffer contents or operational state."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            buf.push("x")
            buf.push("y")
            buf.push("z")

            snapshot = buf.snapshot_items()
            self.assertEqual(snapshot, ["x", "y", "z"])

            snapshot.append("w")
            snapshot.clear()

            self.assertEqual(buf.size, 3)
            self.assertEqual(buf.capacity, 10)
            self.assertFalse(buf.is_empty)
            self.assertFalse(buf.is_full)

            second_snapshot = buf.snapshot_items()
            self.assertEqual(second_snapshot, ["x", "y", "z"])
            self.assertEqual(buf.pop(), "x")

    def test_buffer_empty_error_hierarchy(self) -> None:
        """Verify BufferEmptyError is a subclass of BufferError."""
        self.assertTrue(issubclass(BufferEmptyError, BufferError))

    def test_heterogeneous_items(self) -> None:
        """Verify ring buffer stores heterogeneous item types faithfully."""
        with enter_phase(system, registry=self.registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            test_items: List[Any] = [42, "hello", {"key": "val"}, (1, 2), [True, False]]
            for item in test_items:
                buf.push(item)

            self.assertEqual(buf.snapshot_items(), test_items)
            for expected in test_items:
                self.assertEqual(buf.pop(), expected)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T06:51:45Z
# LAST_CHANGED: 2026-11-10T06:50:46Z
# CHANGE: Implement comprehensive unit tests for RingBuffer singleton covering happy paths, overwrite eviction, pop FIFO ordering, BufferEmptyError, clear, and snapshot_items
# COVERAGE_AUDIT: 2026-11-10T06:51:45Z
# QA_AUDIT: 2026-11-10T06:51:19Z
# --- END AUTOFAB METADATA ---
