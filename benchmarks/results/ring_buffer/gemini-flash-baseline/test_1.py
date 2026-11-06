from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from ring_buffer.lib.ring_buffer import BufferEmptyError, BufferError
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__


class RingBufferImplTest(unittest.TestCase):
    """Unit tests for RingBuffer implementation verifying contract postconditions."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.scope = enter_phase("system", registry=self.registry)
        self.buffer = self.scope.get_singleton(RingBuffer)

    def tearDown(self) -> None:
        self.scope.close()

    def test_initial_state(self) -> None:
        """Verify initial state of newly initialized ring buffer."""
        self.assertEqual(self.buffer.capacity, 10)
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), [])

    def test_pop_empty_buffer_raises_error(self) -> None:
        """Verify popping an empty buffer raises BufferEmptyError."""
        self.assertTrue(self.buffer.is_empty)
        with self.assertRaises(BufferEmptyError):
            self.buffer.pop()

    def test_push_below_capacity(self) -> None:
        """Verify push stores items and returns None when size is less than capacity."""
        evicted = self.buffer.push("first")
        self.assertIsNone(evicted)
        self.assertEqual(self.buffer.size, 1)
        self.assertFalse(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), ["first"])

        evicted2 = self.buffer.push("second")
        self.assertIsNone(evicted2)
        self.assertEqual(self.buffer.size, 2)
        self.assertEqual(self.buffer.snapshot_items(), ["first", "second"])

    def test_push_reaches_capacity(self) -> None:
        """Verify buffer reaches capacity and becomes full without eviction until saturated."""
        for i in range(10):
            evicted = self.buffer.push(i)
            self.assertIsNone(evicted)

        self.assertEqual(self.buffer.size, 10)
        self.assertTrue(self.buffer.is_full)
        self.assertFalse(self.buffer.is_empty)
        self.assertEqual(self.buffer.snapshot_items(), list(range(10)))

    def test_push_at_capacity_evicts_oldest(self) -> None:
        """Verify push at capacity evicts the oldest item and stores the new item."""
        for i in range(10):
            self.buffer.push(f"item_{i}")

        self.assertTrue(self.buffer.is_full)

        # Evict item_0 by pushing item_10
        evicted = self.buffer.push("item_10")
        self.assertEqual(evicted, "item_0")
        self.assertEqual(self.buffer.size, 10)
        self.assertTrue(self.buffer.is_full)

        expected = [f"item_{i}" for i in range(1, 11)]
        self.assertEqual(self.buffer.snapshot_items(), expected)

        # Evict item_1 by pushing item_11
        evicted2 = self.buffer.push("item_11")
        self.assertEqual(evicted2, "item_1")
        self.assertEqual(self.buffer.size, 10)
        expected2 = [f"item_{i}" for i in range(2, 12)]
        self.assertEqual(self.buffer.snapshot_items(), expected2)

    def test_pop_non_empty_buffer(self) -> None:
        """Verify pop removes and returns the oldest item in FIFO order."""
        self.buffer.push("alpha")
        self.buffer.push("beta")
        self.buffer.push("gamma")

        self.assertEqual(self.buffer.size, 3)

        removed = self.buffer.pop()
        self.assertEqual(removed, "alpha")
        self.assertEqual(self.buffer.size, 2)
        self.assertEqual(self.buffer.snapshot_items(), ["beta", "gamma"])

        removed2 = self.buffer.pop()
        self.assertEqual(removed2, "beta")
        self.assertEqual(self.buffer.size, 1)

        removed3 = self.buffer.pop()
        self.assertEqual(removed3, "gamma")
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)

        # Popping again now raises BufferEmptyError
        with self.assertRaises(BufferEmptyError):
            self.buffer.pop()

    def test_clear_resets_buffer(self) -> None:
        """Verify clear removes all items and resets size to zero."""
        self.buffer.push(1)
        self.buffer.push(2)
        self.buffer.push(3)
        self.assertEqual(self.buffer.size, 3)

        self.buffer.clear()
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), [])

        # Buffer functions normally after clear
        evicted = self.buffer.push("fresh")
        self.assertIsNone(evicted)
        self.assertEqual(self.buffer.size, 1)
        self.assertEqual(self.buffer.pop(), "fresh")

    def test_snapshot_items_does_not_modify_state(self) -> None:
        """Verify snapshot_items is non-destructive and preserves operational state."""
        self.buffer.push("x")
        self.buffer.push("y")

        items1 = self.buffer.snapshot_items()
        self.assertEqual(items1, ["x", "y"])

        # Mutating the returned snapshot does not affect buffer
        items1.append("z")
        self.assertEqual(self.buffer.snapshot_items(), ["x", "y"])
        self.assertEqual(self.buffer.size, 2)

    def test_exception_inheritance(self) -> None:
        """Verify BufferEmptyError is a subclass of BufferError."""
        self.assertTrue(issubclass(BufferEmptyError, BufferError))


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:10:03Z
# LAST_CHANGED: 2026-11-06T20:10:03Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 32d235c0d1ad
# COVERAGE_AUDIT: 2026-11-06T20:10:03Z
# QA_AUDIT: 2026-11-06T20:10:03Z
# --- END AUTOFAB METADATA ---
