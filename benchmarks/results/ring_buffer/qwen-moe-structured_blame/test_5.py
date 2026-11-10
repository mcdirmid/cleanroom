"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Any, cast
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from ring_buffer.lib.ring_buffer import BufferEmptyError


class RingBufferImplTest(unittest.TestCase):
    """Tests for the bounded circular ring buffer singleton."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase("system", registry=self.registry)

    def tearDown(self) -> None:
        self.phase_scope.close()

    def _get_buffer(self) -> Any:
        """Resolve the RingBuffer singleton from the active phase scope."""
        return self.phase_scope.get_singleton(RingBuffer)

    # --- Lifecycle and Property Tests ---

    def test_initialization(self) -> None:
        """CUJ: Verify lifecycle registration and singleton resolution."""
        buf = self._get_buffer()
        self.assertIsNotNone(buf)

    def test_default_capacity(self) -> None:
        """POSTCONDITION: capacity returns 10 by default."""
        buf = self._get_buffer()
        self.assertEqual(buf.capacity, 10)

    def test_initial_state(self) -> None:
        """POSTCONDITION: initial size is 0, is_empty is True, is_full is False."""
        buf = self._get_buffer()
        self.assertEqual(buf.size, 0)
        self.assertTrue(cast(bool, buf.is_empty))
        self.assertFalse(cast(bool, buf.is_full))

    # --- Push Tests ---

    def test_push_available_capacity(self) -> None:
        """Happy path: push when size < capacity, stores item, increments size, returns None."""
        buf = self._get_buffer()
        result = buf.push("a")
        self.assertIsNone(result)
        self.assertEqual(buf.size, 1)
        self.assertFalse(cast(bool, buf.is_empty))

    def test_push_multiple_items(self) -> None:
        """Happy path: push multiple items, size increments each time."""
        buf = self._get_buffer()
        for i in range(5):
            result = buf.push(i)
            self.assertIsNone(result)
            self.assertEqual(buf.size, i + 1)

    def test_push_overwrite_eviction(self) -> None:
        """When size == capacity, evict oldest item, return evicted item, maintain size at capacity."""
        buf = self._get_buffer()
        # Fill the buffer to capacity
        for i in range(10):
            buf.push(i)
        self.assertEqual(buf.size, 10)
        self.assertTrue(cast(bool, buf.is_full))
        # Push one more, should evict oldest (0)
        evicted = buf.push(10)
        self.assertEqual(evicted, 0)
        self.assertEqual(buf.size, 10)
        self.assertTrue(cast(bool, buf.is_full))

    def test_push_overwrite_preserves_fifo_order(self) -> None:
        """After eviction, snapshot shows correct FIFO order with newest item."""
        buf = self._get_buffer()
        for i in range(10):
            buf.push(i)
        evicted = buf.push(100)
        self.assertEqual(evicted, 0)
        items = buf.snapshot_items()
        self.assertEqual(items, [1, 2, 3, 4, 5, 6, 7, 8, 9, 100])

    # --- Pop Tests ---

    def test_pop_non_empty(self) -> None:
        """When size > 0, remove oldest item, decrement size, return it."""
        buf = self._get_buffer()
        buf.push("first")
        buf.push("second")
        result = buf.pop()
        self.assertEqual(result, "first")
        self.assertEqual(buf.size, 1)

    def test_pop_fifo_order(self) -> None:
        """POP in FIFO: oldest pushed item is returned first."""
        buf = self._get_buffer()
        for i in range(5):
            buf.push(i)
        self.assertEqual(buf.pop(), 0)
        self.assertEqual(buf.pop(), 1)
        self.assertEqual(buf.pop(), 2)

    def test_pop_empty_raises_buffer_empty_error(self) -> None:
        """When size == 0, MUST raise BufferEmptyError."""
        buf = self._get_buffer()
        with self.assertRaises(BufferEmptyError):
            buf.pop()

    # --- Clear Tests ---

    def test_clear_resets_size(self) -> None:
        """Remove all items from buffer, reset size to zero."""
        buf = self._get_buffer()
        for i in range(5):
            buf.push(i)
        self.assertEqual(buf.size, 5)
        buf.clear()
        self.assertEqual(buf.size, 0)
        self.assertTrue(cast(bool, buf.is_empty))

    def test_clear_makes_buffer_empty(self) -> None:
        """POSTCONDITION: after clear, is_empty is True and is_full is False."""
        buf = self._get_buffer()
        for i in range(10):
            buf.push(i)
        self.assertTrue(cast(bool, buf.is_full))
        buf.clear()
        self.assertTrue(cast(bool, buf.is_empty))
        self.assertFalse(cast(bool, buf.is_full))

    # --- Snapshot Tests ---

    def test_snapshot_fifo_order(self) -> None:
        """Return all items in FIFO arrival order."""
        buf = self._get_buffer()
        buf.push("a")
        buf.push("b")
        buf.push("c")
        items = buf.snapshot_items()
        self.assertEqual(items, ["a", "b", "c"])

    def test_snapshot_non_mutating(self) -> None:
        """Must NOT modify buffer contents, size, or state."""
        buf = self._get_buffer()
        buf.push(1)
        buf.push(2)
        before_size = buf.size
        before_items = buf.snapshot_items()
        # Call snapshot again
        after_items = buf.snapshot_items()
        self.assertEqual(buf.size, before_size)
        self.assertEqual(after_items, before_items)

    def test_snapshot_empty_buffer(self) -> None:
        """Snapshot of an empty buffer returns an empty list."""
        buf = self._get_buffer()
        items = buf.snapshot_items()
        self.assertEqual(items, [])

    # --- Integrated Tests ---

    def test_push_pop_cycle(self) -> None:
        """FIFO: push N items, pop N items in order, buffer ends empty."""
        buf = self._get_buffer()
        for i in range(10):
            buf.push(i)
        for i in range(10):
            self.assertEqual(buf.pop(), i)
        self.assertTrue(cast(bool, buf.is_empty))

    def test_push_pop_with_eviction(self) -> None:
        """FIFO with eviction: pushing past capacity evicts oldest, pops reflect remaining items."""
        buf = self._get_buffer()
        for i in range(10):
            buf.push(i)
        buf.push(100)  # evicts 0
        self.assertEqual(buf.pop(), 1)
        self.assertEqual(buf.pop(), 2)
        self.assertEqual(buf.pop(), 3)
        self.assertEqual(buf.pop(), 4)
        self.assertEqual(buf.size, 6)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T06:45:40Z
# LAST_CHANGED: 2026-11-10T06:44:58Z
# CHANGE: Fixed test_push_pop_with_eviction: corrected 4th pop assertion from 100 to 4. After pushing 0-9 then 100 (evicting 0), buffer state is [1,2,3,4,5,6,7,8,9,100]; FIFO pop order gives 1,2,3,4 before reaching 100.
# COVERAGE_AUDIT: 2026-11-10T06:45:40Z
# QA_AUDIT: 2026-11-10T06:45:17Z
# --- END AUTOFAB METADATA ---
