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
    """Tests for bounded circular ring buffer lifecycle, properties, and invariants."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.scope = enter_phase(system, registry=self.registry)
        self.phase = self.scope.__enter__()

    def tearDown(self) -> None:
        self.scope.__exit__(None, None, None)

    def _ring_buffer(self) -> RingBuffer:
        """Resolve the RingBuffer singleton from the active phase scope."""
        return self.phase.get_singleton(RingBuffer)

    def test_initialization_registers_ring_buffer(self) -> None:
        """CUJ: Verify RingBuffer is registered in the lifecycle registry."""
        self.assertIsNotNone(self.phase.get_singleton(RingBuffer))

    def test_capacity_is_ten(self) -> None:
        """INVARIANT: capacity property returns self._capacity.
        GROUNDING confirms capacity is 10 per the component spec."""
        rb = self._ring_buffer()
        self.assertEqual(rb.capacity, 10)

    def test_initial_size_is_zero(self) -> None:
        """INVARIANT: Newly created buffer has zero items."""
        rb = self._ring_buffer()
        self.assertEqual(rb.size, 0)

    def test_initial_is_empty(self) -> None:
        """INVARIANT: Newly created empty buffer reports is_empty."""
        rb = self._ring_buffer()
        self.assertTrue(rb.is_empty)

    def test_initial_is_not_full(self) -> None:
        """INVARIANT: Newly created buffer with items below capacity is not full."""
        rb = self._ring_buffer()
        self.assertFalse(rb.is_full)

    def test_push_with_available_capacity_returns_none(self) -> None:
        """Happy-path: pushes items below capacity and verifies size increments."""
        rb = self._ring_buffer()
        self.assertEqual(rb.size, 0)
        self.assertIsNone(rb.push(1))
        self.assertEqual(rb.size, 1)
        self.assertIsNone(rb.push(2))
        self.assertEqual(rb.size, 2)
        self.assertIsNone(rb.push(3))
        self.assertEqual(rb.size, 3)

    def test_push_fills_buffer_to_capacity(self) -> None:
        """Happy-path: sequential pushes fill buffer and size reaches capacity."""
        rb = self._ring_buffer()
        for i in range(10):
            self.assertIsNone(rb.push(i))
        self.assertEqual(rb.size, 10)

    def test_is_full_when_at_capacity(self) -> None:
        """INVARIANT: Buffer reports is_full when size equals capacity."""
        rb = self._ring_buffer()
        for _ in range(10):
            rb.push(0)
        self.assertTrue(rb.is_full)

    def test_push_overwrite_eviction_returns_evicted_item(self) -> None:
        """Error branch: buffer at capacity, push evicts oldest item and returns it."""
        rb = self._ring_buffer()
        for i in range(10):
            rb.push(i)
        self.assertEqual(rb.size, 10)
        self.assertTrue(rb.is_full)
        # Buffer is full; next push evicts oldest (0)
        evicted = rb.push(99)
        self.assertEqual(evicted, 0)
        self.assertEqual(rb.size, 10)
        self.assertTrue(rb.is_full)

    def test_push_eviction_preserves_capacity_bound(self) -> None:
        """INVARIANT: After eviction, size stays at capacity, never exceeds it.

        Multiple eviction pushes keep buffer at its capacity bound."""
        rb = self._ring_buffer()
        for i in range(10):
            rb.push(i)
        for i in range(5):
            evicted = rb.push(100 + i)
            self.assertEqual(evicted, i)
        self.assertEqual(rb.size, 10)
        self.assertTrue(rb.is_full)

    def test_pop_returns_oldest_item(self) -> None:
        """Happy-path: pops items and verifies FIFO order and size decrement."""
        rb = self._ring_buffer()
        rb.push(1)
        rb.push(2)
        rb.push(3)
        self.assertEqual(rb.size, 3)
        oldest = rb.pop()
        self.assertEqual(oldest, 1)
        self.assertEqual(rb.size, 2)

    def test_pop_fifo_order(self) -> None:
        """Happy-path: sequential pops return items in FIFO arrival order."""
        rb = self._ring_buffer()
        rb.push(10)
        rb.push(20)
        rb.push(30)
        self.assertEqual(rb.pop(), 10)
        self.assertEqual(rb.pop(), 20)
        self.assertEqual(rb.pop(), 30)

    def test_pop_empty_raises_buffer_empty_error(self) -> None:
        """Error branch: popping from an empty buffer raises BufferEmptyError."""
        rb = self._ring_buffer()
        self.assertTrue(rb.is_empty)
        with self.assertRaises(BufferEmptyError):
            rb.pop()

    def test_pop_empty_after_filling_and_draining(self) -> None:
        """Error branch: after popping all items, buffer is empty and pop raises."""
        rb = self._ring_buffer()
        for i in range(5):
            rb.push(i)
        for _ in range(5):
            rb.pop()
        self.assertTrue(rb.is_empty)
        with self.assertRaises(BufferEmptyError):
            rb.pop()

    def test_clear_resets_size_to_zero(self) -> None:
        """Happy-path: clearing a buffer with items resets size to zero."""
        rb = self._ring_buffer()
        for i in range(5):
            rb.push(i)
        self.assertEqual(rb.size, 5)
        rb.clear()
        self.assertEqual(rb.size, 0)
        self.assertTrue(rb.is_empty)

    def test_clear_empty_buffer_has_no_effect(self) -> None:
        """Happy-path: clearing an empty buffer succeeds without error."""
        rb = self._ring_buffer()
        rb.clear()
        self.assertEqual(rb.size, 0)
        self.assertTrue(rb.is_empty)

    def test_snapshot_returns_fifo_order(self) -> None:
        """Happy-path: snapshot returns items in FIFO arrival order."""
        rb = self._ring_buffer()
        rb.push(1)
        rb.push(2)
        rb.push(3)
        snapshot = rb.snapshot_items()
        self.assertEqual(snapshot, [1, 2, 3])

    def test_snapshot_non_mutating(self) -> None:
        """Invariant: snapshot does not modify buffer contents, size, or capacity."""
        rb = self._ring_buffer()
        rb.push(10)
        rb.push(20)
        size_before = rb.size
        capacity_before = rb.capacity
        snapshot_before = rb.snapshot_items()
        # Call snapshot_items multiple times
        rb.snapshot_items()
        rb.snapshot_items()
        # Verify no mutation
        self.assertEqual(rb.size, size_before)
        self.assertEqual(rb.capacity, capacity_before)
        self.assertEqual(rb.snapshot_items(), snapshot_before)

    def test_mixed_push_pop_snapshot(self) -> None:
        """INVARIANT: Mixed push/pop operations preserve FIFO order in snapshots."""
        rb = self._ring_buffer()
        rb.push(1)
        rb.push(2)
        rb.push(3)
        self.assertEqual(rb.snapshot_items(), [1, 2, 3])
        rb.pop()  # Remove 1
        self.assertEqual(rb.snapshot_items(), [2, 3])
        rb.push(4)
        self.assertEqual(rb.snapshot_items(), [2, 3, 4])

    def test_lifecycle_tier_is_system(self) -> None:
        """INVARIANT: RingBuffer singleton is registered at system tier."""
        self.assertEqual(RingBuffer.tier, "system")


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T05:58:16Z
# LAST_CHANGED: 2026-11-10T05:57:31Z
# CHANGE: Fixed capacity value from 16 to 10 across all tests to match spec GROUNDING (default capacity=10). Updated: test_capacity_is_sixteen→test_capacity_is_ten, test_push_fills_buffer_to_capacity, test_is_full_when_at_capacity, test_push_overwrite_eviction_returns_evicted_item, test_push_eviction_preserves_capacity_bound.
# COVERAGE_AUDIT: 2026-11-10T05:58:16Z
# QA_AUDIT: 2026-11-10T05:57:53Z
# --- END AUTOFAB METADATA ---
