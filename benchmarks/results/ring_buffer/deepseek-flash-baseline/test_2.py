"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest

from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


class RingBufferImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initialization(self) -> None:
        """CUJ: Verify initial component presence."""
        self.assertIsNotNone(self.registry)
        for sym in [RingBuffer]:
            self.assertIsNotNone(sym)

    def test_initial_state(self) -> None:
        """POSTCONDITIONS: a new buffer is empty, not full, and defaults to capacity 10."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buffer.capacity, 10)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_push_within_capacity(self) -> None:
        """POSTCONDITION: WHEN size is less than capacity, MUST store item, increment size, return None."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertIsNone(buffer.push("alpha"))
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), ["alpha"])

    def test_push_reaches_capacity(self) -> None:
        """POSTCONDITION: WHEN size reaches capacity, is_full and size MUST reflect the capacity limit."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(9):
                self.assertIsNone(buffer.push(index))
            self.assertFalse(buffer.is_full)
            self.assertIsNone(buffer.push(9))
            self.assertTrue(buffer.is_full)
            self.assertEqual(buffer.size, 10)
            self.assertEqual(buffer.snapshot_items(), list(range(10)))

    def test_push_evicts_oldest_when_full(self) -> None:
        """POSTCONDITION: WHEN size equals capacity, MUST evict oldest, keep size at capacity, return evicted."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(10):
                self.assertIsNone(buffer.push(index))
            evicted = buffer.push(10)
            self.assertEqual(evicted, 0)
            self.assertEqual(buffer.size, 10)
            self.assertTrue(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), list(range(1, 11)))

    def test_repeated_eviction_preserves_fifo_order(self) -> None:
        """INVARIANT: repeated pushes past capacity preserve FIFO arrival order of the newest items."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(13):
                buffer.push(index)
            self.assertEqual(buffer.size, 10)
            self.assertEqual(buffer.snapshot_items(), list(range(3, 13)))
            self.assertEqual(buffer.pop(), 3)
            self.assertEqual(buffer.pop(), 4)

    def test_pop_returns_oldest_item(self) -> None:
        """POSTCONDITION: WHEN size is greater than zero, MUST remove oldest item, decrement size, return it."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("first")
            buffer.push("second")
            self.assertEqual(buffer.pop(), "first")
            self.assertEqual(buffer.size, 1)
            self.assertEqual(buffer.snapshot_items(), ["second"])

    def test_pop_until_empty(self) -> None:
        """POSTCONDITION: popping all items MUST leave the buffer empty with size zero."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push(1)
            buffer.push(2)
            self.assertEqual(buffer.pop(), 1)
            self.assertEqual(buffer.pop(), 2)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.size, 0)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_pop_on_empty_raises_buffer_empty_error(self) -> None:
        """PRECONDITION: WHEN size equals zero, MUST raise BufferEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertTrue(buffer.is_empty)
            with self.assertRaises(BufferEmptyError):
                buffer.pop()

    def test_clear_removes_all_items(self) -> None:
        """POSTCONDITION: MUST remove all items from the buffer and reset size to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("a")
            buffer.push("b")
            buffer.push("c")
            self.assertEqual(buffer.size, 3)
            buffer.clear()
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])
            self.assertEqual(buffer.capacity, 10)

    def test_snapshot_items_is_non_destructive(self) -> None:
        """POSTCONDITIONS: MUST return all active items in FIFO order without modifying buffer state."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("one")
            buffer.push("two")
            buffer.push("three")
            snapshot = buffer.snapshot_items()
            self.assertEqual(snapshot, ["one", "two", "three"])
            self.assertEqual(buffer.capacity, 10)
            self.assertEqual(buffer.size, 3)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), ["one", "two", "three"])
            self.assertEqual(buffer.pop(), "one")


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T19:52:26Z
# LAST_CHANGED: 2026-11-06T19:52:26Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: eaba15681604
# COVERAGE_AUDIT: 2026-11-06T19:52:26Z
# QA_AUDIT: 2026-11-06T19:52:26Z
# --- END AUTOFAB METADATA ---
