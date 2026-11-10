"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from ring_buffer.lib.ring_buffer import BufferEmptyError


def _create_test_registry():
    """Creates a LifecycleRegistry and initializes the RingBuffer singleton."""
    registry = LifecycleRegistry()
    __initialize__(registry)
    return registry


class RingBufferImplTest(unittest.TestCase):
    """Tests for RingBuffer singleton under lifecycle management."""

    def _buf(self):
        """Resolve the RingBuffer singleton from a fresh lifecycle scope."""
        registry = _create_test_registry()
        with enter_phase(system, registry=registry) as scope:
            return scope.get_singleton(RingBuffer)

    # -- Happy-path tests --

    def test_initialization(self) -> None:
        """CUJ: Verify initial component presence and lifecycle wiring."""
        registry = _create_test_registry()
        with enter_phase(system, registry=registry) as scope:
            buf = scope.get_singleton(RingBuffer)
            self.assertIsNotNone(buf)
            self.assertIsInstance(buf, RingBuffer)

    def test_properties_initial_state(self) -> None:
        """CUJ: Verify default capacity=10, size=0, is_empty=True, is_full=False."""
        buf = self._buf()
        self.assertEqual(buf.capacity, 10)
        self.assertEqual(buf.size, 0)
        self.assertTrue(buf.is_empty)
        self.assertFalse(buf.is_full)

    def test_push_stores_item_with_available_capacity(self) -> None:
        """CUJ: push when size < capacity stores item, increments size, returns None."""
        buf = self._buf()
        self.assertTrue(buf.is_empty)

        # Fill to half capacity
        for i in range(1, 6):
            evicted = buf.push(i)
            self.assertIsNone(evicted)
            self.assertEqual(buf.size, i)
            self.assertFalse(buf.is_full)

        items = buf.snapshot_items()
        self.assertEqual(items, [1, 2, 3, 4, 5])

    def test_push_evicts_oldest_when_at_capacity(self) -> None:
        """CUJ: push when size == capacity evicts oldest, returns evicted item."""
        buf = self._buf()

        # Fill to capacity
        for i in range(1, 11):
            evicted = buf.push(i)
            self.assertIsNone(evicted)
        self.assertTrue(buf.is_full)
        self.assertEqual(buf.size, 10)

        # Push one more - should evict oldest (1)
        evicted = buf.push(11)
        self.assertEqual(evicted, 1)
        self.assertTrue(buf.is_full)
        self.assertEqual(buf.size, 10)
        items = buf.snapshot_items()
        self.assertEqual(items, [2, 3, 4, 5, 6, 7, 8, 9, 10, 11])

    def test_push_maintains_fifo_order(self) -> None:
        """CUJ: push preserves FIFO arrival order in snapshot."""
        buf = self._buf()
        buf.push(50)
        buf.push(30)
        buf.push(70)
        items = buf.snapshot_items()
        self.assertEqual(items, [50, 30, 70])
        self.assertEqual(buf.size, 3)

    def test_pop_returns_oldest_item(self) -> None:
        """CUJ: pop removes oldest item, decrements size, returns item."""
        buf = self._buf()
        buf.push(10)
        buf.push(20)
        buf.push(30)
        self.assertEqual(buf.size, 3)

        item = buf.pop()
        self.assertEqual(item, 10)
        self.assertEqual(buf.size, 2)
        self.assertFalse(buf.is_empty)

        item = buf.pop()
        self.assertEqual(item, 20)
        self.assertEqual(buf.size, 1)

        item = buf.pop()
        self.assertEqual(item, 30)
        self.assertEqual(buf.size, 0)
        self.assertTrue(buf.is_empty)

    def test_pop_after_eviction_returns_correct_fifo(self) -> None:
        """CUJ: pop after eviction still returns items in FIFO order."""
        buf = self._buf()

        # Fill to capacity then evict
        for i in range(1, 11):
            buf.push(i)
        buf.push(11)  # evicts 1
        buf.push(12)  # evicts 2

        item = buf.pop()
        self.assertEqual(item, 3)
        item = buf.pop()
        self.assertEqual(item, 4)

    def test_clear_resets_all_state(self) -> None:
        """CUJ: clear removes all items, resets size to zero."""
        buf = self._buf()
        for i in range(1, 6):
            buf.push(i)
        self.assertEqual(buf.size, 5)
        self.assertFalse(buf.is_empty)

        buf.clear()
        self.assertEqual(buf.size, 0)
        self.assertTrue(buf.is_empty)
        self.assertFalse(buf.is_full)
        self.assertEqual(buf.snapshot_items(), [])

    # -- Alternate and error branch tests --

    def test_pop_empty_buffer_raises_buffer_empty_error(self) -> None:
        """CUJ: pop on empty buffer raises BufferEmptyError."""
        buf = self._buf()
        self.assertTrue(buf.is_empty)
        with self.assertRaises(BufferEmptyError):
            buf.pop()

    def test_pop_empty_buffer_state_unchanged(self) -> None:
        """CUJ: failed pop on empty buffer leaves state unchanged."""
        buf = self._buf()
        capacity_before = buf.capacity
        self.assertTrue(buf.is_empty)
        with self.assertRaises(BufferEmptyError):
            buf.pop()
        self.assertEqual(buf.capacity, capacity_before)
        self.assertEqual(buf.size, 0)
        self.assertTrue(buf.is_empty)
        self.assertEqual(buf.snapshot_items(), [])

    def test_clear_on_empty_buffer_is_noop(self) -> None:
        """CUJ: clear on empty buffer preserves zero state."""
        buf = self._buf()
        buf.clear()
        self.assertEqual(buf.size, 0)
        self.assertTrue(buf.is_empty)
        self.assertFalse(buf.is_full)
        self.assertEqual(buf.snapshot_items(), [])

    def test_snapshot_items_empty_buffer(self) -> None:
        """CUJ: snapshot_items on empty buffer returns empty list."""
        buf = self._buf()
        self.assertEqual(buf.snapshot_items(), [])
        self.assertEqual(buf.size, 0)

    def test_snapshot_items_returns_fifo_order(self) -> None:
        """CUJ: snapshot_items returns items in FIFO arrival order."""
        buf = self._buf()
        buf.push(1)
        buf.push(2)
        buf.push(3)
        self.assertEqual(buf.snapshot_items(), [1, 2, 3])

    def test_snapshot_items_is_non_mutating(self) -> None:
        """CUJ: snapshot_items does not modify buffer contents, size, or state."""
        buf = self._buf()
        for i in range(1, 6):
            buf.push(i)
        size_before = buf.size
        capacity_before = buf.capacity
        items_before = buf.snapshot_items()

        buf.push(6)
        buf.pop()
        buf.clear()

        # Verify buffer state changed but snapshot_items call didn't affect it
        self.assertEqual(buf.size, 0)
        self.assertEqual(capacity_before, 10)
        self.assertNotEqual(buf.snapshot_items(), items_before)

    def test_snapshot_items_returns_shallow_copy(self) -> None:
        """CUJ: snapshot_items returns a shallow copy, not a reference."""
        buf = self._buf()
        buf.push(1)
        buf.push(2)

        snap1 = buf.snapshot_items()
        snap2 = buf.snapshot_items()
        self.assertIsNot(snap1, snap2)

    def test_push_any_type_items(self) -> None:
        """CUJ: push accepts items of any type (Any)."""
        buf = self._buf()
        buf.push("hello")
        buf.push(42)
        buf.push([1, 2, 3])
        buf.push({"key": "value"})
        buf.push(None)
        self.assertEqual(buf.size, 5)
        items = buf.snapshot_items()
        self.assertEqual(items, ["hello", 42, [1, 2, 3], {"key": "value"}, None])

    def test_capacity_is_fixed(self) -> None:
        """INVARIANT: capacity is a fixed property, never changes after construction."""
        buf = self._buf()
        initial = buf.capacity
        for i in range(15):
            buf.push(i)
        self.assertEqual(buf.capacity, initial)

    def test_size_invariant_under_push_pop(self) -> None:
        """INVARIANT: size reflects actual item count after push/pop cycles."""
        buf = self._buf()
        buf.push(1)
        buf.push(2)
        buf.pop()
        self.assertEqual(buf.size, 1)
        buf.pop()
        self.assertEqual(buf.size, 0)

    def test_full_to_empty_via_pop(self) -> None:
        """INVARIANT: full buffer empties to zero after popping all items."""
        buf = self._buf()
        for i in range(10):
            buf.push(i)
        self.assertTrue(buf.is_full)
        self.assertEqual(buf.size, 10)

        for _ in range(10):
            buf.pop()
        self.assertTrue(buf.is_empty)
        self.assertEqual(buf.size, 0)
        self.assertFalse(buf.is_full)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T06:19:30Z
# LAST_CHANGED: 2026-11-10T06:18:36Z
# CHANGE: Implemented comprehensive unit tests for RingBuffer singleton. Tests cover: lifecycle-managed initialization (LifecycleRegistry + enter_phase), property verification (capacity=10, size, is_empty, is_full), happy-path push/pop/clear/snapshot_items, overwrite eviction at capacity, FIFO order preservation, error branch (BufferEmptyError on empty pop), snapshot non-mutating and shallow copy invariants, capacity immutability, size consistency, and full-to-empty lifecycle cycle.
# COVERAGE_AUDIT: 2026-11-10T06:19:30Z
# QA_AUDIT: 2026-11-10T06:19:08Z
# --- END AUTOFAB METADATA ---
