"""Unit tests for the bounded circular ring buffer implementation."""

from __future__ import annotations

import unittest
from typing import Any, List

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


class RingBufferImplTest(unittest.TestCase):
    """Verifies RingBuffer contracts declared in low/ring_buffer_impl.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state_is_empty_with_default_capacity(self) -> None:
        """Initial state exposes the default capacity of 10 with zero stored items."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buffer.capacity, 10)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_push_when_space_available_stores_item_and_returns_none(self) -> None:
        """POSTCONDITION: WHEN size < capacity, MUST store item, increment size, return None."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertIsNone(buffer.push("alpha"))
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), ["alpha"])
            self.assertIsNone(buffer.push("beta"))
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.snapshot_items(), ["alpha", "beta"])

    def test_push_when_full_evicts_oldest_and_returns_it(self) -> None:
        """POSTCONDITION: WHEN size == capacity, MUST evict oldest, keep size at capacity, return evicted item."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(10):
                self.assertIsNone(buffer.push(index))
            self.assertTrue(buffer.is_full)
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertEqual(buffer.push(10), 0)
            self.assertTrue(buffer.is_full)
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertEqual(buffer.snapshot_items(), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    def test_push_eviction_preserves_fifo_order_across_wraparound(self) -> None:
        """Repeated saturation eviction always removes the oldest remaining item."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(10):
                buffer.push(index)
            self.assertEqual(buffer.push(10), 0)
            self.assertEqual(buffer.push(11), 1)
            self.assertEqual(buffer.push(12), 2)
            self.assertEqual(buffer.size, 10)
            self.assertEqual(
                buffer.snapshot_items(), [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
            )

    def test_push_accepts_arbitrary_item_types(self) -> None:
        """Any item type can be stored and is returned in FIFO arrival order."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            items: List[Any] = [42, "text", (1, 2), {"key": "value"}]
            for item in items:
                self.assertIsNone(buffer.push(item))
            self.assertEqual(buffer.size, len(items))
            self.assertEqual(buffer.snapshot_items(), items)

    def test_pop_returns_oldest_item_and_decrements_size(self) -> None:
        """POSTCONDITION: WHEN size > 0, MUST remove oldest item, decrement size by 1, return it."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("first")
            buffer.push("second")
            self.assertEqual(buffer.pop(), "first")
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), ["second"])
            self.assertEqual(buffer.pop(), "second")
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)

    def test_pop_when_empty_raises_buffer_empty_error(self) -> None:
        """PRECONDITION: WHEN size == 0, MUST raise BufferEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertTrue(buffer.is_empty)
            with self.assertRaises(BufferEmptyError):
                buffer.pop()
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)

    def test_pop_after_clear_raises_buffer_empty_error(self) -> None:
        """Clearing the buffer restores the empty precondition that makes pop fail."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("only")
            buffer.clear()
            with self.assertRaises(BufferEmptyError):
                buffer.pop()

    def test_clear_removes_all_items_and_resets_size_to_zero(self) -> None:
        """POSTCONDITION: MUST remove all items and reset size to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(4):
                buffer.push(index)
            self.assertFalse(buffer.is_empty)
            buffer.clear()
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])
            self.assertEqual(buffer.capacity, 10)

    def test_clear_when_already_empty_keeps_buffer_empty(self) -> None:
        """Clearing an empty buffer leaves size at zero and the buffer reusable."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.clear()
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), [])
            self.assertIsNone(buffer.push("after-clear"))
            self.assertEqual(buffer.snapshot_items(), ["after-clear"])

    def test_snapshot_items_is_non_destructive(self) -> None:
        """POSTCONDITION: snapshot MUST NOT modify contents, size, capacity, or state."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for item in ["a", "b", "c"]:
                buffer.push(item)
            capacity_before = buffer.capacity
            size_before = buffer.size
            first_snapshot = buffer.snapshot_items()
            second_snapshot = buffer.snapshot_items()
            self.assertEqual(first_snapshot, ["a", "b", "c"])
            self.assertEqual(second_snapshot, ["a", "b", "c"])
            self.assertEqual(buffer.capacity, capacity_before)
            self.assertEqual(buffer.size, size_before)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.pop(), "a")


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T19:22:47Z
# LAST_CHANGED: 2026-11-06T19:20:44Z
# CHANGE: Authored lifecycle-scoped unit tests for RingBuffer covering initial state, push with and without saturation eviction, FIFO order across wraparound, arbitrary item types, pop (including BufferEmptyError preconditions), clear, and non-destructive snapshot_items.
# COVERAGE_AUDIT: 2026-11-06T19:22:47Z
# QA_AUDIT: 2026-11-06T19:22:35Z
# --- END AUTOFAB METADATA ---
