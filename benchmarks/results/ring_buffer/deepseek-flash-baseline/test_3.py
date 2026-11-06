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
    """Verifies contracted ring buffer behavior within an active system phase."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initialization(self) -> None:
        """CUJ: Verify initial component presence and default bounded capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertIsNotNone(buffer)
            # POSTCONDITION: default capacity of 10 with zero stored items.
            self.assertEqual(buffer.capacity, 10)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_push_below_capacity_stores_item_and_returns_none(self) -> None:
        """POSTCONDITION: WHEN size is less than capacity, MUST store item,
        increment size by 1, and return None.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            result = buffer.push("alpha")
            self.assertIsNone(result)
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), ["alpha"])

    def test_push_at_capacity_evicts_oldest_and_returns_it(self) -> None:
        """POSTCONDITION: WHEN size equals capacity, MUST evict oldest item,
        store new item at most recent position, maintain size at capacity, and
        return the evicted item.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(buffer.capacity):
                self.assertIsNone(buffer.push(index))
            self.assertTrue(buffer.is_full)

            evicted = buffer.push(buffer.capacity)

            self.assertEqual(evicted, 0)
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertTrue(buffer.is_full)
            self.assertEqual(
                buffer.snapshot_items(),
                [index for index in range(1, buffer.capacity)] + [buffer.capacity],
            )

    def test_pop_returns_oldest_item_and_decrements_size(self) -> None:
        """POSTCONDITION: WHEN size is greater than zero, MUST remove oldest
        item, decrement size by 1, and return the removed item.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("first")
            buffer.push("second")

            self.assertEqual(buffer.pop(), "first")
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), ["second"])

    def test_pop_when_empty_raises_buffer_empty_error(self) -> None:
        """PRECONDITION: WHEN size equals zero, MUST raise BufferEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertTrue(buffer.is_empty)

            with self.assertRaises(BufferEmptyError):
                buffer.pop()

            self.assertEqual(buffer.size, 0)

    def test_clear_removes_all_items_and_resets_size(self) -> None:
        """POSTCONDITION: MUST remove all items from the buffer and reset size
        to zero.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("first")
            buffer.push("second")
            buffer.push("third")

            buffer.clear()

            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_snapshot_items_returns_fifo_snapshot_without_modification(self) -> None:
        """POSTCONDITION: MUST return a list containing all currently stored
        items in FIFO arrival order and MUST NOT modify buffer state.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("oldest")
            buffer.push("middle")
            buffer.push("newest")

            snapshot = buffer.snapshot_items()

            self.assertEqual(snapshot, ["oldest", "middle", "newest"])
            self.assertEqual(buffer.size, 3)
            self.assertEqual(
                buffer.snapshot_items(), ["oldest", "middle", "newest"]
            )

    def test_wraparound_preserves_fifo_order(self) -> None:
        """INVARIANT: active items remain retrievable oldest to newest across
        push/pop wraparound at capacity.
        """
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("a")
            buffer.push("b")
            buffer.push("c")

            self.assertEqual(buffer.pop(), "a")
            self.assertIsNone(buffer.push("d"))

            self.assertEqual(buffer.snapshot_items(), ["b", "c", "d"])
            self.assertEqual(buffer.pop(), "b")
            self.assertEqual(buffer.pop(), "c")
            self.assertEqual(buffer.pop(), "d")
            self.assertTrue(buffer.is_empty)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:06:59Z
# LAST_CHANGED: 2026-11-06T20:06:59Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 3c36397b7cf6
# COVERAGE_AUDIT: 2026-11-06T20:06:59Z
# QA_AUDIT: 2026-11-06T20:06:59Z
# --- END AUTOFAB METADATA ---
