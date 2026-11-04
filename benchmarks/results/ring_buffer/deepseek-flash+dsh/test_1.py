"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Companion modules are rooted at the Autofab parts directory (``<parts>/<unit>/lib``),
# so keep that root importable whether the suite is collected from the workspace or the parts tree.
_PARTS_ROOT = str(Path(__file__).resolve().parents[2])
if _PARTS_ROOT not in sys.path:
    sys.path.insert(0, _PARTS_ROOT)

from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

DEFAULT_CAPACITY = 10


class RingBufferImplTest(unittest.TestCase):
    """Verifies the RingBuffer singleton postconditions from ring_buffer.pyi.

    Primary flow: push items within capacity, inspect size/is_full, evict the
    oldest item once capacity is saturated, pop the oldest resident item, clear
    the buffer, and observe a non-destructive FIFO snapshot.
    """

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state_defaults(self) -> None:
        """Initial buffer is empty with the contracted default capacity of 10."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_push_within_capacity_returns_none_and_grows(self) -> None:
        """WHEN size < capacity, push stores the item, increments size, returns None."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertIsNone(buffer.push("first"))
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)

            self.assertIsNone(buffer.push("second"))
            self.assertIsNone(buffer.push("third"))
            self.assertEqual(buffer.size, 3)
            self.assertEqual(buffer.snapshot_items(), ["first", "second", "third"])

    def test_push_to_capacity_boundary_does_not_evict(self) -> None:
        """Filling exactly to capacity stores every item and reports is_full."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            items = list(range(DEFAULT_CAPACITY))
            for index, item in enumerate(items, start=1):
                self.assertIsNone(buffer.push(item))
                self.assertEqual(buffer.size, index)
                if index < DEFAULT_CAPACITY:
                    self.assertFalse(buffer.is_full)

            self.assertEqual(buffer.size, DEFAULT_CAPACITY)
            self.assertTrue(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), items)

    def test_push_at_capacity_evicts_oldest_and_returns_it(self) -> None:
        """WHEN size equals capacity, push evicts and returns the oldest stored item."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for item in range(DEFAULT_CAPACITY):
                buffer.push(item)

            evicted = buffer.push(DEFAULT_CAPACITY)

            self.assertEqual(evicted, 0)
            self.assertEqual(buffer.size, DEFAULT_CAPACITY)
            self.assertTrue(buffer.is_full)
            expected = list(range(1, DEFAULT_CAPACITY + 1))
            self.assertEqual(buffer.snapshot_items(), expected)

            # Successive saturation continues evicting in FIFO arrival order.
            self.assertEqual(buffer.push(DEFAULT_CAPACITY + 1), 1)
            self.assertEqual(buffer.size, DEFAULT_CAPACITY)

    def test_pop_returns_oldest_and_decrements_size(self) -> None:
        """WHEN size > 0, pop removes and returns the oldest item and decrements size."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("a")
            buffer.push("b")
            buffer.push("c")

            self.assertEqual(buffer.pop(), "a")
            self.assertEqual(buffer.size, 2)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), ["b", "c"])

            self.assertEqual(buffer.pop(), "b")
            self.assertEqual(buffer.pop(), "c")
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_clear_removes_all_items(self) -> None:
        """clear removes all items and resets size to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push(1)
            buffer.push(2)
            buffer.push(3)

            buffer.clear()

            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

            # The buffer remains usable after clearing.
            self.assertIsNone(buffer.push("after-clear"))
            self.assertEqual(buffer.snapshot_items(), ["after-clear"])

    def test_snapshot_items_is_non_destructive_fifo(self) -> None:
        """snapshot_items returns a FIFO copy without mutating buffer state."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("oldest")
            buffer.push("middle")
            buffer.push("newest")

            first = buffer.snapshot_items()
            second = buffer.snapshot_items()

            self.assertEqual(first, ["oldest", "middle", "newest"])
            self.assertEqual(second, ["oldest", "middle", "newest"])
            self.assertEqual(buffer.size, 3)
            self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)

            # The returned list is a copy, so mutating it cannot alter the buffer.
            first.append("appended-by-caller")
            self.assertEqual(buffer.size, 3)
            self.assertEqual(buffer.snapshot_items(), ["oldest", "middle", "newest"])


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T20:26:49Z
# LAST_CHANGED: 2026-11-04T20:26:14Z
# CHANGE: Author RingBuffer unit tests covering default capacity/initial emptiness, push growth without eviction, FIFO eviction on saturation, pop ordering and size decrement, clear reset, and non-destructive FIFO snapshot_items.
# COVERAGE_AUDIT: 2026-11-04T20:26:49Z
# QA_AUDIT: 2026-11-04T20:26:35Z
# --- END AUTOFAB METADATA ---
