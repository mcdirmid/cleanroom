"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system
from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)

DEFAULT_CAPACITY = 10


class RingBufferImplTest(unittest.TestCase):
    """Verifies the RingBuffer singleton against low/ring_buffer_impl.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def _buffer(self, scope: LifecycleScope) -> RingBuffer:
        """Resolves the target singleton inside the caller's active phase scope."""
        return scope.get_singleton(RingBuffer)

    def test_initialization_exposes_empty_default_buffer(self) -> None:
        """INVARIANTS: a fresh buffer is empty with default capacity 10 and is not full."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_push_below_capacity_stores_item_and_returns_none(self) -> None:
        """POSTCONDITIONS: push when size < capacity stores item, increments size, returns None."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            self.assertIsNone(buffer.push("alpha"))
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), ["alpha"])

    def test_push_to_capacity_reports_full_without_eviction(self) -> None:
        """POSTCONDITIONS: filling to capacity keeps every item and returns None for each push."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            for index in range(buffer.capacity):
                self.assertIsNone(buffer.push(index))
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertTrue(buffer.is_full)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), list(range(buffer.capacity)))

    def test_push_at_capacity_evicts_oldest_and_returns_it(self) -> None:
        """POSTCONDITIONS: push when size == capacity evicts the oldest item and keeps size fixed."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            for index in range(buffer.capacity):
                buffer.push(index)
            evicted = buffer.push(buffer.capacity)
            self.assertEqual(evicted, 0)
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertTrue(buffer.is_full)
            self.assertEqual(
                buffer.snapshot_items(),
                list(range(1, buffer.capacity + 1)),
            )

    def test_repeated_eviction_preserves_fifo_arrival_order(self) -> None:
        """POSTCONDITIONS: successive saturation pushes evict oldest items in FIFO order."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            capacity = buffer.capacity
            for index in range(capacity):
                buffer.push(index)
            for index in range(3):
                self.assertEqual(buffer.push(100 + index), index)
            self.assertEqual(buffer.size, capacity)
            self.assertEqual(
                buffer.snapshot_items(),
                list(range(3, capacity)) + [100, 101, 102],
            )

    def test_pop_returns_oldest_and_decrements_size(self) -> None:
        """POSTCONDITIONS: pop when size > 0 removes the oldest item and decrements size."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            buffer.push("first")
            buffer.push("second")
            self.assertEqual(buffer.pop(), "first")
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), ["second"])

    def test_pop_on_empty_buffer_raises_buffer_empty_error(self) -> None:
        """PRECONDITIONS: pop when size equals zero MUST raise BufferEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            self.assertTrue(buffer.is_empty)
            with self.assertRaises(BufferEmptyError):
                buffer.pop()
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)

    def test_pop_after_draining_raises_buffer_empty_error(self) -> None:
        """PRECONDITIONS: pop after draining the last item MUST raise BufferEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            buffer.push("only")
            self.assertEqual(buffer.pop(), "only")
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            with self.assertRaises(BufferEmptyError):
                buffer.pop()

    def test_clear_removes_all_items_and_resets_size(self) -> None:
        """POSTCONDITIONS: clear removes every item, resets size to zero, and preserves capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            for index in range(3):
                buffer.push(index)
            buffer.clear()
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])
            self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)

    def test_clear_on_empty_buffer_leaves_buffer_empty(self) -> None:
        """POSTCONDITIONS: clear on an already empty buffer leaves size at zero."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            buffer.clear()
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_clear_full_buffer_permits_reuse_at_capacity(self) -> None:
        """POSTCONDITIONS: a cleared full buffer accepts capacity items again without eviction."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            capacity = buffer.capacity
            for index in range(capacity):
                buffer.push(index)
            self.assertTrue(buffer.is_full)
            buffer.clear()
            self.assertEqual(buffer.size, 0)
            self.assertFalse(buffer.is_full)
            for index in range(capacity):
                self.assertIsNone(buffer.push(index))
            self.assertEqual(buffer.size, capacity)
            self.assertEqual(buffer.snapshot_items(), list(range(capacity)))

    def test_snapshot_items_returns_non_destructive_fifo_copy(self) -> None:
        """POSTCONDITIONS: snapshot_items reports FIFO order without modifying buffer state."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            for index in range(3):
                buffer.push(index)
            first = buffer.snapshot_items()
            second = buffer.snapshot_items()
            self.assertEqual(first, [0, 1, 2])
            self.assertEqual(second, [0, 1, 2])
            first.append(99)
            self.assertEqual(buffer.snapshot_items(), [0, 1, 2])
            self.assertEqual(buffer.size, 3)
            self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)

    def test_push_and_pop_preserve_arbitrary_item_identity(self) -> None:
        """POSTCONDITIONS: push stores and pop returns the same arbitrary object instance."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = self._buffer(scope)
            marker = object()
            self.assertIsNone(buffer.push(marker))
            self.assertIs(buffer.pop(), marker)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:07:04Z
# LAST_CHANGED: 2026-11-06T20:06:15Z
# CHANGE: Replace initialization placeholder with full behavioral test suite for RingBuffer: default capacity/empty invariants, push below and at capacity (eviction + FIFO return), repeated eviction order, pop success and BufferEmptyError preconditions, clear on populated/empty/full buffers, and non-destructive FIFO snapshot_items. All tests run inside an active system phase scope resolving the singleton via scope.get_singleton.
# COVERAGE_AUDIT: 2026-11-06T20:07:04Z
# QA_AUDIT: 2026-11-06T20:06:53Z
# --- END AUTOFAB METADATA ---
