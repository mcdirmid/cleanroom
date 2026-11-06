"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


class RingBufferImplTest(unittest.TestCase):
    """Verifies the bounded FIFO circular buffer contracts of RingBuffer."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state(self) -> None:
        """Default capacity is 10 and a fresh buffer is empty and not full."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(10, buffer.capacity)
            self.assertEqual(0, buffer.size)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual([], buffer.snapshot_items())

    def test_push_below_capacity_returns_none(self) -> None:
        """POSTCONDITIONS: push with size < capacity stores item, increments size, returns None."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertIsNone(buffer.push("alpha"))
            self.assertEqual(1, buffer.size)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertIsNone(buffer.push("beta"))
            self.assertEqual(2, buffer.size)
            self.assertEqual(["alpha", "beta"], buffer.snapshot_items())
            self.assertEqual(10, buffer.capacity)

    def test_push_at_capacity_evicts_oldest(self) -> None:
        """POSTCONDITIONS: push with size == capacity evicts oldest, keeps size, returns evicted item."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(10):
                self.assertIsNone(buffer.push(value))
            self.assertTrue(buffer.is_full)
            self.assertEqual(10, buffer.size)
            evicted = buffer.push(10)
            self.assertEqual(0, evicted)
            self.assertEqual(10, buffer.size)
            self.assertTrue(buffer.is_full)
            self.assertEqual(list(range(1, 11)), buffer.snapshot_items())
            self.assertEqual(10, buffer.capacity)

    def test_push_wraps_repeatedly_in_fifo_order(self) -> None:
        """Repeated overwrite eviction preserves FIFO arrival order across wrap-arounds."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(25):
                buffer.push(value)
            self.assertEqual(10, buffer.size)
            self.assertEqual(list(range(15, 25)), buffer.snapshot_items())
            self.assertTrue(buffer.is_full)
            self.assertEqual(10, buffer.capacity)

    def test_pop_returns_oldest_item(self) -> None:
        """POSTCONDITIONS: pop removes and returns oldest item, decrementing size."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("first")
            buffer.push("second")
            buffer.push("third")
            self.assertEqual("first", buffer.pop())
            self.assertEqual(2, buffer.size)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(["second", "third"], buffer.snapshot_items())
            self.assertEqual("second", buffer.pop())
            self.assertEqual("third", buffer.pop())
            self.assertEqual(0, buffer.size)
            self.assertTrue(buffer.is_empty)

    def test_pop_empty_raises_buffer_empty_error(self) -> None:
        """PRECONDITIONS: pop when size == 0 MUST raise BufferEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            with self.assertRaises(BufferEmptyError):
                buffer.pop()

    def test_pop_empty_after_draining_raises_buffer_empty_error(self) -> None:
        """PRECONDITIONS: pop MUST raise BufferEmptyError once all items are drained."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("only")
            self.assertEqual("only", buffer.pop())
            self.assertTrue(buffer.is_empty)
            with self.assertRaises(BufferEmptyError):
                buffer.pop()

    def test_clear_resets_buffer(self) -> None:
        """POSTCONDITIONS: clear removes all items and resets size to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(5):
                buffer.push(value)
            buffer.clear()
            self.assertEqual(0, buffer.size)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual([], buffer.snapshot_items())
            self.assertEqual(10, buffer.capacity)

    def test_clear_frees_capacity_for_future_pushes(self) -> None:
        """POSTCONDITIONS: push after clear stores item without eviction."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(10):
                buffer.push(value)
            self.assertTrue(buffer.is_full)
            buffer.clear()
            self.assertIsNone(buffer.push("fresh"))
            self.assertEqual(1, buffer.size)
            self.assertEqual(["fresh"], buffer.snapshot_items())

    def test_snapshot_items_is_non_destructive(self) -> None:
        """POSTCONDITIONS: snapshot_items preserves contents, size, capacity, and state."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(4):
                buffer.push(value)
            first = buffer.snapshot_items()
            second = buffer.snapshot_items()
            self.assertEqual([0, 1, 2, 3], first)
            self.assertEqual(first, second)
            self.assertEqual(4, buffer.size)
            self.assertEqual(10, buffer.capacity)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertIsNone(buffer.push("next"))
            self.assertEqual([0, 1, 2, 3, "next"], buffer.snapshot_items())


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:07:01Z
# LAST_CHANGED: 2026-11-06T20:06:07Z
# CHANGE: Full RingBuffer impl test suite: import path fixed; covers initial state, push below/at capacity with eviction, repeated wrap-around FIFO order, pop ordering, BufferEmptyError preconditions, clear reset, and non-destructive snapshot_items
# COVERAGE_AUDIT: 2026-11-06T20:07:01Z
# QA_AUDIT: 2026-11-06T20:06:47Z
# --- END AUTOFAB METADATA ---
