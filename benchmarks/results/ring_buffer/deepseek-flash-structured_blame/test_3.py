"""Unit tests for the concrete RingBuffer bounded circular buffer implementation.

Covers the operational postconditions and checked preconditions contracted in
``low/ring_buffer.pyi`` and ``low/ring_buffer_impl.pyi``: push with available
capacity, push with overwrite eviction, pop precondition/postcondition,
clear reset, and the test-only FIFO snapshot query.
"""

from __future__ import annotations

import unittest
from typing import Any, Iterable, List

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


DEFAULT_CAPACITY = 10


class RingBufferImplTest(unittest.TestCase):
    """Exercises RingBuffer within an active system lifecycle phase scope."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def _push_many(self, buffer: RingBuffer, items: Iterable[Any]) -> None:
        """Pushes each item into the active buffer through its public contract."""
        for item in items:
            buffer.push(item)

    def test_initial_state(self) -> None:
        """GROUNDING: new buffer has capacity 10, size 0, empty and not full."""
        with enter_phase("system", registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_push_with_available_capacity(self) -> None:
        """Pushing while space remains stores the item, grows size by one, and
        returns None instead of evicting anything."""
        with enter_phase("system", registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)

            self.assertIsNone(buffer.push("alpha"))
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)

            self.assertIsNone(buffer.push("beta"))
            self.assertEqual(buffer.size, 2)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), ["alpha", "beta"])

    def test_push_fills_to_capacity(self) -> None:
        """INVARIANT: filling with exactly `capacity` items yields size == capacity,
        is_full True, is_empty False, and preserves push order."""
        with enter_phase("system", registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)

            self._push_many(buffer, range(DEFAULT_CAPACITY - 1))
            self.assertEqual(buffer.size, DEFAULT_CAPACITY - 1)
            self.assertFalse(buffer.is_full)

            # The push that occupies the last free slot stores without eviction.
            self.assertIsNone(buffer.push(DEFAULT_CAPACITY - 1))
            self.assertEqual(buffer.size, DEFAULT_CAPACITY)
            self.assertTrue(buffer.is_full)
            self.assertFalse(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), list(range(DEFAULT_CAPACITY)))

    def test_push_overwrite_eviction(self) -> None:
        """Pushing onto a saturated buffer evicts the oldest item, stores the new
        item at the most recent position, keeps size at capacity, and returns the
        evicted item."""
        with enter_phase("system", registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self._push_many(buffer, range(DEFAULT_CAPACITY))

            evicted = buffer.push("newest")

            self.assertEqual(evicted, 0)
            self.assertEqual(buffer.size, DEFAULT_CAPACITY)
            self.assertTrue(buffer.is_full)
            self.assertEqual(
                buffer.snapshot_items(),
                list(range(1, DEFAULT_CAPACITY)) + ["newest"],
            )

            # Consecutive pushes keep evicting in FIFO arrival order.
            self.assertEqual(buffer.push("latest"), 1)
            self.assertEqual(buffer.size, DEFAULT_CAPACITY)
            self.assertEqual(
                buffer.snapshot_items(),
                list(range(2, DEFAULT_CAPACITY)) + ["newest", "latest"],
            )

    def test_pop_empty_buffer_raises(self) -> None:
        """Popping an empty buffer raises BufferEmptyError and leaves it empty."""
        with enter_phase("system", registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)

            with self.assertRaises(BufferEmptyError):
                buffer.pop()

            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)

    def test_pop_returns_oldest_item(self) -> None:
        """Popping a non-empty buffer removes the oldest item, decrements size by
        one, and returns the removed item."""
        with enter_phase("system", registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self._push_many(buffer, ["first", "second", "third"])

            self.assertEqual(buffer.pop(), "first")
            self.assertEqual(buffer.size, 2)
            self.assertFalse(buffer.is_empty)

            self.assertEqual(buffer.pop(), "second")
            self.assertEqual(buffer.size, 1)

            self.assertEqual(buffer.pop(), "third")
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)

    def test_pop_after_eviction_returns_oldest_retained(self) -> None:
        """POSTCONDITION: eviction removes the oldest item, so the next pop returns
        the oldest retained arrival."""
        with enter_phase("system", registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self._push_many(buffer, range(DEFAULT_CAPACITY + 2))

            self.assertEqual(buffer.pop(), 2)
            self.assertEqual(buffer.size, DEFAULT_CAPACITY - 1)
            self.assertFalse(buffer.is_full)
            self.assertEqual(
                buffer.snapshot_items(),
                list(range(3, DEFAULT_CAPACITY + 2)),
            )

    def test_clear_resets_size(self) -> None:
        """Clearing removes every item, resets size to zero, and keeps the buffer
        usable for subsequent pushes."""
        with enter_phase("system", registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self._push_many(buffer, ["a", "b", "c"])
            self.assertFalse(buffer.is_empty)

            buffer.clear()

            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.capacity, DEFAULT_CAPACITY)
            self.assertEqual(buffer.snapshot_items(), [])

            # The buffer remains usable after being cleared.
            self.assertIsNone(buffer.push("fresh"))
            self.assertEqual(buffer.snapshot_items(), ["fresh"])

    def test_snapshot_fifo_order(self) -> None:
        """Snapshot returns every stored item in FIFO arrival order, including
        after wraparound eviction."""
        with enter_phase("system", registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self._push_many(buffer, ["a", "b", "c"])
            self.assertEqual(buffer.snapshot_items(), ["a", "b", "c"])

            # Wraparound: 13 pushes into capacity 10 retain the newest 10.
            self._push_many(buffer, range(DEFAULT_CAPACITY))
            self.assertEqual(buffer.snapshot_items(), list(range(DEFAULT_CAPACITY)))

    def test_snapshot_non_mutating(self) -> None:
        """Taking a snapshot neither changes buffer contents, size, capacity, nor
        operational state, and returns an independent copy."""
        with enter_phase("system", registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self._push_many(buffer, ["x", "y"])
            size_before = buffer.size
            capacity_before = buffer.capacity

            snapshot: List[Any] = buffer.snapshot_items()

            self.assertEqual(snapshot, ["x", "y"])
            self.assertEqual(buffer.size, size_before)
            self.assertEqual(buffer.capacity, capacity_before)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)

            # The returned snapshot is a copy: mutating it leaves the buffer intact.
            snapshot.append("z")
            self.assertEqual(buffer.snapshot_items(), ["x", "y"])
            self.assertEqual(buffer.size, 2)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T04:22:20Z
# LAST_CHANGED: 2026-11-11T04:21:31Z
# CHANGE: Initial unittest suite for RingBuffer singleton: lifecycle-scoped instantiation, capacity/size/empty/full invariants, push with available capacity (returns None), push overwrite eviction returning oldest item, pop empty raising BufferEmptyError, FIFO pop ordering, clear reset, and snapshot_items FIFO order plus non-mutating copy semantics.
# COVERAGE_AUDIT: 2026-11-11T04:22:20Z
# QA_AUDIT: 2026-11-11T04:22:06Z
# --- END AUTOFAB METADATA ---
