from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system
from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


class RingBufferImplTest(unittest.TestCase):
    """Unit tests for RingBuffer implementation."""

    registry: LifecycleRegistry
    phase_scope: LifecycleScope
    buffer: RingBuffer

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.buffer = self.phase_scope.get_singleton(RingBuffer)

    def tearDown(self) -> None:
        self.phase_scope.close()

    def test_initial_state(self) -> None:
        """Verify default capacity, zero size, and boundary indicators upon initialization."""
        self.assertEqual(self.buffer.capacity, 10)
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), [])

    def test_push_available_capacity(self) -> None:
        """Verify push stores item, increments size, and returns None when below capacity."""
        result = self.buffer.push("alpha")
        self.assertIsNone(result)
        self.assertEqual(self.buffer.size, 1)
        self.assertFalse(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), ["alpha"])

    def test_push_up_to_capacity(self) -> None:
        """Verify successive pushes fill the buffer and set is_full without eviction."""
        for i in range(10):
            res = self.buffer.push(f"item_{i}")
            self.assertIsNone(res)
            self.assertEqual(self.buffer.size, i + 1)

        self.assertTrue(self.buffer.is_full)
        self.assertFalse(self.buffer.is_empty)
        self.assertEqual(self.buffer.size, 10)
        expected = [f"item_{i}" for i in range(10)]
        self.assertEqual(self.buffer.snapshot_items(), expected)

    def test_push_overwrite_eviction(self) -> None:
        """Verify pushing to a saturated buffer evicts the oldest item and maintains capacity."""
        for i in range(10):
            self.buffer.push(f"item_{i}")

        evicted_1 = self.buffer.push("item_10")
        self.assertEqual(evicted_1, "item_0")
        self.assertEqual(self.buffer.size, 10)
        self.assertTrue(self.buffer.is_full)

        evicted_2 = self.buffer.push("item_11")
        self.assertEqual(evicted_2, "item_1")
        self.assertEqual(self.buffer.size, 10)
        self.assertTrue(self.buffer.is_full)

        expected = [f"item_{i}" for i in range(2, 12)]
        self.assertEqual(self.buffer.snapshot_items(), expected)

    def test_push_and_pop_none_item(self) -> None:
        """Verify buffer can store and retrieve None without ambiguity in return values."""
        ret = self.buffer.push(None)
        self.assertIsNone(ret)
        self.assertEqual(self.buffer.size, 1)
        self.assertEqual(self.buffer.snapshot_items(), [None])
        popped = self.buffer.pop()
        self.assertIsNone(popped)
        self.assertEqual(self.buffer.size, 0)

    def test_pop_non_empty(self) -> None:
        """Verify pop removes and returns oldest item, decrementing size."""
        self.buffer.push("first")
        self.buffer.push("second")
        self.assertEqual(self.buffer.size, 2)

        item = self.buffer.pop()
        self.assertEqual(item, "first")
        self.assertEqual(self.buffer.size, 1)
        self.assertFalse(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)

        item2 = self.buffer.pop()
        self.assertEqual(item2, "second")
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)

    def test_pop_empty_buffer_raises_error(self) -> None:
        """Verify pop on an empty buffer raises BufferEmptyError."""
        self.assertEqual(self.buffer.size, 0)
        with self.assertRaises(BufferEmptyError):
            self.buffer.pop()

    def test_pop_after_exhaustion_raises_error(self) -> None:
        """Verify pop raises BufferEmptyError after buffer is drained of all items."""
        self.buffer.push("solo")
        val = self.buffer.pop()
        self.assertEqual(val, "solo")
        self.assertEqual(self.buffer.size, 0)
        with self.assertRaises(BufferEmptyError):
            self.buffer.pop()

    def test_clear_resets_size_and_items(self) -> None:
        """Verify clear removes all stored items and resets size to zero."""
        self.buffer.push("one")
        self.buffer.push("two")
        self.buffer.push("three")
        self.assertEqual(self.buffer.size, 3)

        self.buffer.clear()
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), [])

    def test_clear_empty_buffer(self) -> None:
        """Verify clear on an already empty buffer leaves it in empty state."""
        self.buffer.clear()
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)

    def test_clear_then_pop_raises_error(self) -> None:
        """Verify popping after clear raises BufferEmptyError."""
        self.buffer.push("item")
        self.buffer.clear()
        with self.assertRaises(BufferEmptyError):
            self.buffer.pop()

    def test_snapshot_items_fifo_order(self) -> None:
        """Verify snapshot returns items in circular FIFO arrival order."""
        items = ["a", "b", "c", "d"]
        for x in items:
            self.buffer.push(x)

        self.assertEqual(self.buffer.snapshot_items(), ["a", "b", "c", "d"])

    def test_snapshot_items_non_mutating(self) -> None:
        """Verify snapshot does not mutate buffer state and list mutations do not leak."""
        self.buffer.push("fixed")
        snapshot = self.buffer.snapshot_items()
        self.assertEqual(snapshot, ["fixed"])
        self.assertEqual(self.buffer.size, 1)

        snapshot.append("tampered")
        self.assertEqual(self.buffer.size, 1)
        self.assertEqual(self.buffer.snapshot_items(), ["fixed"])

    def test_interleaved_push_and_pop_fifo_order(self) -> None:
        """Verify interleaved push and pop operations preserve circular FIFO ordering."""
        self.buffer.push("a")
        self.buffer.push("b")
        self.assertEqual(self.buffer.pop(), "a")

        self.buffer.push("c")
        self.assertEqual(self.buffer.pop(), "b")

        self.buffer.push("d")
        self.assertEqual(self.buffer.pop(), "c")
        self.assertEqual(self.buffer.pop(), "d")
        self.assertTrue(self.buffer.is_empty)

    def test_circular_wrap_around_cycles(self) -> None:
        """Verify circular buffer wrap-around across multiple fill and drain cycles."""
        for cycle in range(3):
            for i in range(10):
                self.buffer.push(f"cycle_{cycle}_{i}")
            self.assertTrue(self.buffer.is_full)
            for i in range(10):
                self.assertEqual(self.buffer.pop(), f"cycle_{cycle}_{i}")
            self.assertTrue(self.buffer.is_empty)

    def test_eviction_across_multiple_capacities(self) -> None:
        """Verify FIFO consistency after evicting multiple full buffer capacities."""
        for i in range(35):
            self.buffer.push(i)
        self.assertEqual(self.buffer.size, 10)
        self.assertEqual(self.buffer.snapshot_items(), list(range(25, 35)))
        for i in range(25, 35):
            self.assertEqual(self.buffer.pop(), i)
        self.assertTrue(self.buffer.is_empty)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T17:26:53Z
# LAST_CHANGED: 2026-11-10T17:24:55Z
# CHANGE: Implement comprehensive unit test suite for RingBuffer covering capacity, size, is_empty, is_full, push, pop, clear, and snapshot_items
# COVERAGE_AUDIT: 2026-11-10T17:26:53Z
# QA_AUDIT: 2026-11-10T17:26:21Z
# --- END AUTOFAB METADATA ---
