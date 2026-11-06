"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest

from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


class RingBufferImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state_exposes_default_capacity_and_zero_size(self) -> None:
        """POSTCONDITIONS: default capacity is 10 and a fresh buffer is empty."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buffer.capacity, 10)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_push_with_space_available_stores_item_and_returns_none(self) -> None:
        """POSTCONDITIONS: WHEN size is less than capacity, MUST store and return None."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertIsNone(buffer.push("first"))
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), ["first"])
            self.assertIsNone(buffer.push("second"))
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.snapshot_items(), ["first", "second"])

    def test_push_when_full_evicts_and_returns_oldest_item(self) -> None:
        """POSTCONDITIONS: WHEN size equals capacity, MUST evict oldest and return it."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(buffer.capacity):
                self.assertIsNone(buffer.push(index))
            self.assertTrue(buffer.is_full)
            self.assertEqual(buffer.size, buffer.capacity)

            # The oldest stored item is evicted and returned on saturation.
            self.assertEqual(buffer.push(10), 0)
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertTrue(buffer.is_full)
            # Newest item occupies the most recent position; FIFO order is intact.
            self.assertEqual(
                buffer.snapshot_items(), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
            )

            # A subsequent eviction removes the next oldest item.
            self.assertEqual(buffer.push(11), 1)
            self.assertEqual(
                buffer.snapshot_items(), [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
            )

    def test_pop_returns_oldest_item_and_decrements_size(self) -> None:
        """POSTCONDITIONS: WHEN size greater than zero, MUST remove and return oldest."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("alpha")
            buffer.push("beta")
            self.assertEqual(buffer.pop(), "alpha")
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), ["beta"])
            self.assertEqual(buffer.pop(), "beta")
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)

    def test_pop_when_empty_raises_buffer_empty_error(self) -> None:
        """PRECONDITIONS: WHEN size equals zero, MUST raise BufferEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertTrue(buffer.is_empty)
            with self.assertRaises(BufferEmptyError):
                buffer.pop()

    def test_clear_removes_all_items_and_resets_size(self) -> None:
        """POSTCONDITIONS: MUST remove all items and reset size to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("one")
            buffer.push("two")
            buffer.push("three")
            self.assertEqual(buffer.size, 3)

            buffer.clear()

            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_snapshot_items_preserves_fifo_order_without_mutating_state(self) -> None:
        """POSTCONDITIONS: MUST return FIFO snapshot and MUST NOT modify state."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("a")
            buffer.push("b")
            buffer.push("c")

            first_snapshot = buffer.snapshot_items()
            self.assertEqual(first_snapshot, ["a", "b", "c"])
            # State is unchanged: size, capacity, emptiness, and repeat snapshots.
            self.assertEqual(buffer.size, 3)
            self.assertEqual(buffer.capacity, 10)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), ["a", "b", "c"])
            # Oldest item is still the next to be popped.
            self.assertEqual(buffer.pop(), "a")


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T18:44:18Z
# LAST_CHANGED: 2026-11-06T18:44:18Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 1a2f95c1745d
# COVERAGE_AUDIT: 2026-11-06T18:44:18Z
# QA_AUDIT: 2026-11-06T18:44:18Z
# --- END AUTOFAB METADATA ---
