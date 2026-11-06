"""Unit tests for ring_buffer_impl per its low-level specification.

Verifies the contracted invariants, preconditions, and postconditions of the
bounded circular ring buffer singleton declared in
``low/ring_buffer_impl.pyi`` and its supertype protocol ``low/ring_buffer.pyi``.
"""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


class RingBufferImplTest(unittest.TestCase):
    """Contract tests for the bounded circular ring buffer singleton."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state_is_empty_with_default_capacity(self) -> None:
        """INVARIANT/GROUNDING: initial capacity is 10 with zero stored items."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buffer.capacity, 10)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_push_into_available_space_returns_none(self) -> None:
        """POSTCONDITION: WHEN size < capacity, store item, size += 1, return None."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertIsNone(buffer.push("alpha"))
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), ["alpha"])
            self.assertIsNone(buffer.push("beta"))
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.snapshot_items(), ["alpha", "beta"])

    def test_push_preserves_fifo_arrival_order(self) -> None:
        """INVARIANT: active items retain oldest-to-newest arrival order."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            items = [1, 2, 3, 4]
            for item in items:
                self.assertIsNone(buffer.push(item))
            self.assertEqual(buffer.size, len(items))
            self.assertEqual(buffer.snapshot_items(), items)
            self.assertFalse(buffer.is_full)

    def test_push_at_capacity_evicts_oldest_item(self) -> None:
        """POSTCONDITION: WHEN size == capacity, evict oldest, keep size, return evicted."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(buffer.capacity):
                buffer.push(value)
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertTrue(buffer.is_full)

            evicted = buffer.push("newest")
            self.assertEqual(evicted, 0)
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertTrue(buffer.is_full)
            self.assertEqual(
                buffer.snapshot_items(),
                list(range(1, buffer.capacity)) + ["newest"],
            )

    def test_push_repeated_overwrite_keeps_capacity_and_order(self) -> None:
        """POSTCONDITION: successive overwrites evict each oldest item in order."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(buffer.capacity):
                buffer.push(value)
            for offset in range(3):
                evicted = buffer.push(100 + offset)
                self.assertEqual(evicted, offset)
                self.assertEqual(buffer.size, buffer.capacity)
                self.assertTrue(buffer.is_full)
            self.assertEqual(
                buffer.snapshot_items(),
                list(range(3, buffer.capacity)) + [100, 101, 102],
            )

    def test_pop_returns_oldest_item_and_decrements_size(self) -> None:
        """POSTCONDITION: WHEN size > 0, remove oldest, size -= 1, return it."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("first")
            buffer.push("second")
            buffer.push("third")

            self.assertEqual(buffer.pop(), "first")
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.snapshot_items(), ["second", "third"])
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)

            self.assertEqual(buffer.pop(), "second")
            self.assertEqual(buffer.pop(), "third")
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_pop_on_empty_buffer_raises_buffer_empty_error(self) -> None:
        """PRECONDITION: WHEN size == 0, pop MUST raise BufferEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertTrue(buffer.is_empty)
            with self.assertRaises(BufferEmptyError):
                buffer.pop()
            self.assertEqual(buffer.size, 0)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_pop_after_emptying_raises_buffer_empty_error(self) -> None:
        """PRECONDITION: pop MUST raise BufferEmptyError once all items are drained."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("only")
            self.assertEqual(buffer.pop(), "only")
            self.assertTrue(buffer.is_empty)
            with self.assertRaises(BufferEmptyError):
                buffer.pop()
            self.assertEqual(buffer.size, 0)

    def test_clear_removes_all_items(self) -> None:
        """POSTCONDITION: clear MUST remove all items and reset size to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(3):
                buffer.push(value)
            self.assertEqual(buffer.size, 3)

            buffer.clear()
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])
            self.assertEqual(buffer.capacity, 10)

    def test_clear_on_full_buffer_restores_available_space(self) -> None:
        """POSTCONDITION: clear on a saturated buffer frees all capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for value in range(buffer.capacity):
                buffer.push(value)
            self.assertTrue(buffer.is_full)

            buffer.clear()
            self.assertEqual(buffer.size, 0)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.capacity, 10)
            self.assertIsNone(buffer.push("after-clear"))
            self.assertEqual(buffer.snapshot_items(), ["after-clear"])

    def test_snapshot_returns_active_items_without_mutating_buffer(self) -> None:
        """POSTCONDITION: snapshot is a non-destructive FIFO copy of active items."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("a")
            buffer.push("b")

            snapshot = buffer.snapshot_items()
            self.assertIsInstance(snapshot, list)
            self.assertEqual(snapshot, ["a", "b"])
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.capacity, 10)

            snapshot.append("tampered")
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.snapshot_items(), ["a", "b"])

    def test_capacity_remains_constant_across_operations(self) -> None:
        """INVARIANT: capacity is fixed at construction regardless of operations."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buffer.capacity, 10)
            for value in range(12):
                buffer.push(value)
            self.assertEqual(buffer.capacity, 10)
            buffer.pop()
            self.assertEqual(buffer.capacity, 10)
            buffer.clear()
            self.assertEqual(buffer.capacity, 10)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T04:28:31Z
# LAST_CHANGED: 2026-11-06T04:26:30Z
# CHANGE: Author full contract tests for RingBuffer singleton: initial capacity/size/empty/full state, push with and without eviction, pop ordering and BufferEmptyError precondition, clear behavior, non-destructive snapshot_items FIFO copies, and capacity invariance under an active system phase scope.
# COVERAGE_AUDIT: 2026-11-06T04:28:31Z
# QA_AUDIT: 2026-11-06T04:27:48Z
# --- END AUTOFAB METADATA ---
