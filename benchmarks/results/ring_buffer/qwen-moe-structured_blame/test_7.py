"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import cast

from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from ring_buffer.lib.ring_buffer import BufferEmptyError
from support.lib.lifecycle import LifecycleRegistry, enter_phase


class RingBufferImplTest(unittest.TestCase):
    """Tests for RingBuffer singleton covering all contracts in ring_buffer_impl.pyi and ring_buffer.pyi."""

    def setUp(self) -> None:
        self._registry = LifecycleRegistry()
        __initialize__(self._registry)
        self._phase_scope = None
        self._buffer: RingBuffer = cast(RingBuffer, None)

    def tearDown(self) -> None:
        if self._phase_scope is not None:
            self._phase_scope.__exit__(None, None, None)
            self._phase_scope = None

    def _activate_phase(self) -> None:
        """Helper to enter an active phase scope and resolve the RingBuffer singleton."""
        self._phase_scope = enter_phase("system", registry=self._registry)
        scope = self._phase_scope.__enter__()
        self._buffer = scope.get_singleton(RingBuffer)

    # -- Happy-path tests --

    def test_initial_state(self) -> None:
        """Verifies initial capacity (10), size (0), is_empty (True), is_full (False).

        POSTCONDITIONS verified: capacity defaults to 10, size starts at 0.
        """
        self._activate_phase()
        self.assertEqual(self._buffer.capacity, 10)
        self.assertEqual(self._buffer.size, 0)
        self.assertTrue(self._buffer.is_empty)
        self.assertFalse(self._buffer.is_full)

    def test_push_available_capacity_returns_none(self) -> None:
        """Verifies push stores item and returns None when capacity is available."""
        self._activate_phase()
        result = self._buffer.push(42)
        self.assertIsNone(result)
        self.assertEqual(self._buffer.size, 1)
        self.assertFalse(self._buffer.is_empty)

    def test_push_pop_basic_flow(self) -> None:
        """Verifies push followed by pop returns the pushed item in correct order."""
        self._activate_phase()
        self._buffer.push(1)
        self._buffer.push(2)
        self.assertEqual(self._buffer.size, 2)
        popped = self._buffer.pop()
        self.assertEqual(popped, 1)
        self.assertEqual(self._buffer.size, 1)

    def test_push_fifo_order(self) -> None:
        """Items are returned in FIFO arrival order via pop."""
        self._activate_phase()
        self._buffer.push(1)
        self._buffer.push(2)
        self._buffer.push(3)
        self.assertEqual(self._buffer.pop(), 1)
        self.assertEqual(self._buffer.pop(), 2)
        self.assertEqual(self._buffer.pop(), 3)
        self.assertTrue(self._buffer.is_empty)

    def test_push_eviction_on_saturation(self) -> None:
        """Verifies oldest item is evicted and returned when buffer is full."""
        self._activate_phase()
        for i in range(10):
            evicted = self._buffer.push(i)
            self.assertIsNone(evicted)
        self.assertTrue(self._buffer.is_full)
        self.assertEqual(self._buffer.size, 10)

        evicted = self._buffer.push(99)
        self.assertEqual(evicted, 0)
        self.assertEqual(self._buffer.size, 10)
        self.assertTrue(self._buffer.is_full)

    def test_evicted_items_no_longer_in_buffer(self) -> None:
        """After eviction, evicted items are gone from the buffer."""
        self._activate_phase()
        for i in range(10):
            self._buffer.push(i)
        self._buffer.push(99)
        items = self._buffer.snapshot_items()
        self.assertNotIn(0, items)
        self.assertIn(99, items)
        self.assertEqual(len(items), 10)

    def test_is_full_when_at_capacity(self) -> None:
        """Verifies is_full transitions to True when buffer reaches capacity."""
        self._activate_phase()
        self.assertFalse(self._buffer.is_full)
        for i in range(10):
            self._buffer.push(i)
        self.assertTrue(self._buffer.is_full)

    def test_is_empty_after_pop_all(self) -> None:
        """Verifies is_empty transitions to True after popping all items."""
        self._activate_phase()
        for i in range(5):
            self._buffer.push(i)
        self.assertFalse(self._buffer.is_empty)
        while not self._buffer.is_empty:
            self._buffer.pop()
        self.assertTrue(self._buffer.is_empty)

    def test_clear_resets_buffer(self) -> None:
        """Verifies clear removes all items and resets size to zero."""
        self._activate_phase()
        self._buffer.push(1)
        self._buffer.push(2)
        self._buffer.push(3)
        self.assertEqual(self._buffer.size, 3)
        self.assertFalse(self._buffer.is_empty)
        self._buffer.clear()
        self.assertTrue(self._buffer.is_empty)
        self.assertEqual(self._buffer.size, 0)

    def test_push_after_clear(self) -> None:
        """Verifies buffer works correctly after clear (fresh start)."""
        self._activate_phase()
        self._buffer.push(1)
        self._buffer.push(2)
        self._buffer.clear()
        self._buffer.push(3)
        self._buffer.push(4)
        self.assertEqual(self._buffer.size, 2)
        self.assertEqual(self._buffer.pop(), 3)
        self.assertEqual(self._buffer.pop(), 4)

    def test_snapshot_fifo_order(self) -> None:
        """snapshot_items returns all items in FIFO arrival order."""
        self._activate_phase()
        self._buffer.push(10)
        self._buffer.push(20)
        self._buffer.push(30)
        items = self._buffer.snapshot_items()
        self.assertEqual(items, [10, 20, 30])

    def test_snapshot_non_mutating(self) -> None:
        """snapshot_items must not modify buffer contents, size, capacity, or state."""
        self._activate_phase()
        self._buffer.push(1)
        self._buffer.push(2)
        size_before = self._buffer.size
        items_before = self._buffer.snapshot_items()
        self._buffer.snapshot_items()
        self.assertEqual(self._buffer.size, size_before)
        self.assertEqual(self._buffer.snapshot_items(), items_before)
        self.assertTrue(self._buffer.snapshot_items())

    # -- Error branch tests --

    def test_pop_empty_raises_buffer_empty_error(self) -> None:
        """Pop on an empty buffer MUST raise BufferEmptyError."""
        self._activate_phase()
        with self.assertRaises(BufferEmptyError):
            self._buffer.pop()

    def test_pop_multiple_then_empty_raises(self) -> None:
        """After popping all items, a subsequent pop MUST raise BufferEmptyError."""
        self._activate_phase()
        self._buffer.push(1)
        self._buffer.pop()
        with self.assertRaises(BufferEmptyError):
            self._buffer.pop()


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T08:03:11Z
# LAST_CHANGED: 2026-11-10T08:02:07Z
# CHANGE: Implemented comprehensive unit test suite for RingBuffer singleton. Fixed import path to use package-qualified . Tests cover: (1) initial state — capacity=10, size=0, is_empty/is_full flags; (2) push with available capacity — stores item, returns None, increments size; (3) FIFO order — items returned in arrival order; (4) overwrite eviction — oldest item evicted/returned when full; (5) eviction verification — evicted items no longer accessible; (6) boundary flags — is_full at capacity, is_empty after emptying; (7) clear — resets size to 0, removes all items; (8) post-clear operations — fresh start after clear; (9) snapshot_items — FIFO order and non-mutating; (10) BufferEmptyError on pop of empty buffer.
# COVERAGE_AUDIT: 2026-11-10T08:03:11Z
# QA_AUDIT: 2026-11-10T08:02:48Z
# --- END AUTOFAB METADATA ---
