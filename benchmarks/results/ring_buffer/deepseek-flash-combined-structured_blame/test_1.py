"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleScope,
    enter_phase,
    system,
)
from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)

DEFAULT_CAPACITY = 10


class RingBufferImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope: LifecycleScope = enter_phase(
            system, registry=self.registry
        )
        self.phase_scope.__enter__()

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _buffer(self) -> RingBuffer:
        return self.phase_scope.get_singleton(RingBuffer)

    def _fill_to_capacity(self, buffer: RingBuffer) -> None:
        for index in range(DEFAULT_CAPACITY):
            self.assertIsNone(buffer.push(index))
        self.assertEqual(buffer.size, DEFAULT_CAPACITY)

    def test_initial_state_empty_with_default_capacity(self) -> None:
        """CUJ: fresh buffer exposes default capacity and empty state."""
        buffer = self._buffer()
        # Grounding: initializes _capacity to 10 over an empty deque(maxlen=10).
        self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
        self.assertEqual(buffer.size, 0)
        self.assertTrue(buffer.is_empty)
        self.assertFalse(buffer.is_full)
        self.assertEqual(buffer.snapshot_items(), [])

    def test_push_with_available_capacity(self) -> None:
        """CUJ: pushing below capacity stores the item and reports no eviction."""
        buffer = self._buffer()
        self.assertIsNone(buffer.push("alpha"))
        self.assertEqual(buffer.size, 1)
        self.assertFalse(buffer.is_empty)
        self.assertFalse(buffer.is_full)
        self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
        self.assertEqual(buffer.snapshot_items(), ["alpha"])
        # size stays below capacity, so further pushes still return None.
        self.assertIsNone(buffer.push("beta"))
        self.assertEqual(buffer.size, 2)
        self.assertEqual(buffer.snapshot_items(), ["alpha", "beta"])

    def test_push_overwrite_eviction(self) -> None:
        """CUJ: pushing onto a full buffer evicts and returns the oldest item."""
        buffer = self._buffer()
        self._fill_to_capacity(buffer)
        self.assertTrue(buffer.is_full)
        # Pushing onto a saturated buffer evicts and returns the oldest item.
        self.assertEqual(buffer.push("alpha"), 0)
        self.assertEqual(buffer.size, DEFAULT_CAPACITY)
        self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
        self.assertTrue(buffer.is_full)
        self.assertEqual(
            buffer.snapshot_items(),
            [1, 2, 3, 4, 5, 6, 7, 8, 9, "alpha"],
        )
        # Repeated saturation continues to evict in FIFO arrival order.
        self.assertEqual(buffer.push("beta"), 1)
        self.assertEqual(buffer.size, DEFAULT_CAPACITY)
        self.assertEqual(
            buffer.snapshot_items(),
            [2, 3, 4, 5, 6, 7, 8, 9, "alpha", "beta"],
        )

    def test_pop_returns_oldest_item(self) -> None:
        """CUJ: popping a non-empty buffer removes and returns the oldest item."""
        buffer = self._buffer()
        buffer.push("alpha")
        buffer.push("beta")
        buffer.push("gamma")
        self.assertEqual(buffer.pop(), "alpha")
        self.assertEqual(buffer.size, 2)
        self.assertEqual(buffer.snapshot_items(), ["beta", "gamma"])
        self.assertEqual(buffer.pop(), "beta")
        self.assertEqual(buffer.pop(), "gamma")
        self.assertEqual(buffer.size, 0)
        self.assertTrue(buffer.is_empty)
        self.assertEqual(buffer.snapshot_items(), [])

    def test_pop_empty_buffer_raises_buffer_empty_error(self) -> None:
        """CUJ: popping an empty buffer raises BufferEmptyError."""
        buffer = self._buffer()
        self.assertTrue(buffer.is_empty)
        with self.assertRaises(BufferEmptyError):
            buffer.pop()
        # The failed pop must not corrupt buffer state.
        self.assertEqual(buffer.size, 0)
        self.assertTrue(buffer.is_empty)
        # Popping everything out returns to the contracted failure state.
        buffer.push("alpha")
        self.assertEqual(buffer.pop(), "alpha")
        self.assertTrue(buffer.is_empty)
        with self.assertRaises(BufferEmptyError):
            buffer.pop()

    def test_clear_removes_all_items(self) -> None:
        """CUJ: clearing a buffer removes all items and resets the size."""
        buffer = self._buffer()
        buffer.push("alpha")
        buffer.push("beta")
        buffer.clear()
        self.assertEqual(buffer.size, 0)
        self.assertTrue(buffer.is_empty)
        self.assertFalse(buffer.is_full)
        self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
        self.assertEqual(buffer.snapshot_items(), [])
        # A cleared buffer accepts new items without eviction.
        self.assertIsNone(buffer.push("gamma"))
        self.assertEqual(buffer.size, 1)
        self.assertEqual(buffer.snapshot_items(), ["gamma"])

    def test_clear_saturated_buffer(self) -> None:
        """CUJ: clearing a saturated buffer releases all item slots."""
        buffer = self._buffer()
        self._fill_to_capacity(buffer)
        self.assertTrue(buffer.is_full)
        buffer.clear()
        self.assertEqual(buffer.size, 0)
        self.assertTrue(buffer.is_empty)
        self.assertFalse(buffer.is_full)
        self.assertEqual(buffer.snapshot_items(), [])
        for index in range(DEFAULT_CAPACITY):
            self.assertIsNone(buffer.push(index))
        self.assertEqual(buffer.size, DEFAULT_CAPACITY)
        self.assertTrue(buffer.is_full)

    def test_snapshot_items_fifo_order(self) -> None:
        """CUJ: snapshots report stored items from oldest to newest."""
        buffer = self._buffer()
        for item in ["alpha", "beta", "gamma", "delta"]:
            buffer.push(item)
        self.assertEqual(
            buffer.snapshot_items(), ["alpha", "beta", "gamma", "delta"]
        )
        buffer.pop()
        self.assertEqual(buffer.snapshot_items(), ["beta", "gamma", "delta"])
        buffer.push("epsilon")
        self.assertEqual(
            buffer.snapshot_items(), ["beta", "gamma", "delta", "epsilon"]
        )

    def test_snapshot_items_non_mutating(self) -> None:
        """CUJ: taking a snapshot leaves buffer state untouched."""
        buffer = self._buffer()
        buffer.push("alpha")
        buffer.push("beta")
        buffer.push("gamma")
        before_size = buffer.size
        before_capacity = buffer.capacity
        before_is_empty = buffer.is_empty
        before_is_full = buffer.is_full
        first_snapshot = buffer.snapshot_items()
        second_snapshot = buffer.snapshot_items()
        self.assertEqual(first_snapshot, ["alpha", "beta", "gamma"])
        self.assertEqual(second_snapshot, ["alpha", "beta", "gamma"])
        self.assertEqual(buffer.size, before_size)
        self.assertEqual(buffer.capacity, before_capacity)
        self.assertEqual(buffer.is_empty, before_is_empty)
        self.assertEqual(buffer.is_full, before_is_full)
        # The snapshot is a shallow copy, so mutating it cannot alter the buffer.
        first_snapshot.append("delta")
        self.assertEqual(buffer.snapshot_items(), ["alpha", "beta", "gamma"])
        # Operational state is intact: pop still yields the oldest stored item.
        self.assertEqual(buffer.pop(), "alpha")
        self.assertEqual(buffer.snapshot_items(), ["beta", "gamma"])

    def test_snapshot_items_of_saturated_buffer(self) -> None:
        """CUJ: snapshots of a saturated buffer report FIFO order."""
        buffer = self._buffer()
        self._fill_to_capacity(buffer)
        snapshot = buffer.snapshot_items()
        self.assertEqual(snapshot, list(range(DEFAULT_CAPACITY)))
        self.assertEqual(len(snapshot), buffer.size)
        self.assertEqual(buffer.size, DEFAULT_CAPACITY)
        self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
        self.assertTrue(buffer.is_full)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:34:41Z
# LAST_CHANGED: 2026-11-08T17:32:59Z
# CHANGE: Author full unit test suite for RingBuffer singleton: lifecycle-scoped resolution via LifecycleRegistry + enter_phase(system); verify default capacity 10 and empty initial state, push available-capacity returns None, push overwrite eviction returns oldest and keeps size/capacity with FIFO order, pop returns oldest and decrements size, pop on empty raises BufferEmptyError, clear resets size/empty/full for partial and saturated buffers, snapshot_items FIFO order, and snapshot non-mutation including shallow-copy isolation.
# COVERAGE_AUDIT: 2026-11-08T17:34:41Z
# QA_AUDIT: 2026-11-08T17:34:27Z
# --- END AUTOFAB METADATA ---
