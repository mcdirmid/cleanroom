"""Unit tests for the concrete RingBuffer singleton and its contracted behavior."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


class RingBufferTest(unittest.TestCase):
    """Verifies the ring buffer contracts declared in low/ring_buffer.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase("system", registry=self.registry)
        self.phase_scope.open()

    def tearDown(self) -> None:
        self.phase_scope.close()

    def _buffer(self) -> RingBuffer:
        return self.phase_scope.get_singleton(RingBuffer)

    def test_initial_state(self) -> None:
        """CUJ: A freshly resolved buffer is empty, not full, and has capacity 10."""
        buffer = self._buffer()
        self.assertEqual(buffer.capacity, 10)
        self.assertEqual(buffer.size, 0)
        self.assertTrue(buffer.is_empty)
        self.assertFalse(buffer.is_full)
        self.assertEqual(buffer.snapshot_items(), [])

    def test_push_available_capacity(self) -> None:
        """Pushing with free space stores the item, grows the size, and returns None."""
        buffer = self._buffer()
        self.assertIsNone(buffer.push("alpha"))
        self.assertIsNone(buffer.push("beta"))
        self.assertEqual(buffer.size, 2)
        self.assertFalse(buffer.is_empty)
        self.assertFalse(buffer.is_full)
        self.assertEqual(buffer.snapshot_items(), ["alpha", "beta"])

    def test_push_overwrite_eviction(self) -> None:
        """Pushing into a full buffer evicts and returns the oldest item, keeping size at capacity."""
        buffer = self._buffer()
        capacity = buffer.capacity
        for index in range(capacity):
            self.assertIsNone(buffer.push(index))
        self.assertTrue(buffer.is_full)
        self.assertEqual(buffer.size, capacity)
        evicted = buffer.push("overflow")
        self.assertEqual(evicted, 0)
        self.assertEqual(buffer.size, capacity)
        expected = list(range(1, capacity)) + ["overflow"]
        self.assertEqual(buffer.snapshot_items(), expected)
        # A subsequent pop frees one slot, so the next push does not evict.
        self.assertEqual(buffer.pop(), 1)
        self.assertFalse(buffer.is_full)
        self.assertIsNone(buffer.push("after-pop"))
        self.assertEqual(buffer.size, capacity)

    def test_pop_non_empty(self) -> None:
        """Popping a non-empty buffer removes and returns the oldest item and shrinks the size."""
        buffer = self._buffer()
        buffer.push("first")
        buffer.push("second")
        self.assertEqual(buffer.pop(), "first")
        self.assertEqual(buffer.size, 1)
        self.assertEqual(buffer.snapshot_items(), ["second"])
        self.assertEqual(buffer.pop(), "second")
        self.assertEqual(buffer.size, 0)
        self.assertTrue(buffer.is_empty)

    def test_pop_empty_raises_buffer_empty_error(self) -> None:
        """Popping an empty buffer raises BufferEmptyError."""
        buffer = self._buffer()
        with self.assertRaises(BufferEmptyError):
            buffer.pop()

    def test_pop_empty_after_draining_raises_buffer_empty_error(self) -> None:
        """Popping a buffer drained by previous pops raises BufferEmptyError."""
        buffer = self._buffer()
        buffer.push("only")
        self.assertEqual(buffer.pop(), "only")
        with self.assertRaises(BufferEmptyError):
            buffer.pop()

    def test_clear_resets_size(self) -> None:
        """Clearing removes all items and resets the size to zero."""
        buffer = self._buffer()
        buffer.push("one")
        buffer.push("two")
        buffer.clear()
        self.assertEqual(buffer.size, 0)
        self.assertTrue(buffer.is_empty)
        self.assertFalse(buffer.is_full)
        self.assertEqual(buffer.snapshot_items(), [])
        # Space is available again, so a push after clear does not evict.
        self.assertIsNone(buffer.push("fresh"))
        self.assertEqual(buffer.snapshot_items(), ["fresh"])

    def test_snapshot_fifo_order_and_non_mutating(self) -> None:
        """Snapshots list items in FIFO arrival order without mutating the buffer."""
        buffer = self._buffer()
        buffer.push("oldest")
        buffer.push("middle")
        buffer.push("newest")
        snapshot = buffer.snapshot_items()
        self.assertEqual(snapshot, ["oldest", "middle", "newest"])
        # Taking a snapshot preserves contents, size, capacity, and operational state.
        self.assertEqual(buffer.size, 3)
        self.assertEqual(buffer.capacity, 10)
        self.assertEqual(buffer.snapshot_items(), snapshot)
        self.assertEqual(buffer.pop(), "oldest")
        self.assertEqual(buffer.snapshot_items(), ["middle", "newest"])

    def test_lifecycle_resolves_same_singleton_instance(self) -> None:
        """The registered RingBuffer resolves to one shared singleton instance."""
        self.assertIs(self._buffer(), self._buffer())


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:28:07Z
# LAST_CHANGED: 2026-11-08T17:27:19Z
# CHANGE: Authored RingBuffer unit tests covering initial state, push available-capacity and overwrite-eviction paths, pop non-empty and empty BufferEmptyError, clear reset, FIFO non-mutating snapshots, and singleton resolution within an active lifecycle phase scope.
# COVERAGE_AUDIT: 2026-11-08T17:28:07Z
# QA_AUDIT: 2026-11-08T17:27:44Z
# --- END AUTOFAB METADATA ---
