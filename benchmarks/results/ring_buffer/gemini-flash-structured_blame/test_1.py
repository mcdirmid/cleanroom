from __future__ import annotations

from typing import Any, List
import unittest

from ring_buffer.lib.ring_buffer import BufferEmptyError
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__
from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, enter_phase, system


class RingBufferImplTest(unittest.TestCase):
    """Unit test suite for RingBuffer implementation."""

    registry: LifecycleRegistry
    phase_scope: LifecycleScope
    scope: LifecycleScope
    buffer: RingBuffer

    def setUp(self) -> None:
        """Sets up isolated lifecycle registry and activates system scope."""
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.scope = self.phase_scope.__enter__()
        self.buffer = self.scope.get_singleton(RingBuffer)

    def tearDown(self) -> None:
        """Tears down active lifecycle scope."""
        self.phase_scope.__exit__(None, None, None)

    def test_initial_state(self) -> None:
        """Verifies default initial properties of empty circular buffer."""
        self.assertEqual(self.buffer.capacity, 10)
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), [])

    def test_push_available_capacity(self) -> None:
        """Verifies push behavior when size is less than capacity."""
        result1 = self.buffer.push("first")
        self.assertIsNone(result1)
        self.assertEqual(self.buffer.size, 1)
        self.assertFalse(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), ["first"])

        result2 = self.buffer.push("second")
        self.assertIsNone(result2)
        self.assertEqual(self.buffer.size, 2)
        self.assertFalse(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), ["first", "second"])

    def test_push_until_full(self) -> None:
        """Verifies buffer reaches capacity and reports is_full as True."""
        for i in range(10):
            res = self.buffer.push(i)
            self.assertIsNone(res)

        self.assertEqual(self.buffer.size, 10)
        self.assertEqual(self.buffer.capacity, 10)
        self.assertFalse(self.buffer.is_empty)
        self.assertTrue(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), list(range(10)))

    def test_push_overwrite_eviction(self) -> None:
        """Verifies push evicts oldest item when buffer is saturated."""
        for i in range(10):
            self.buffer.push(f"item_{i}")

        evicted1 = self.buffer.push("item_10")
        self.assertEqual(evicted1, "item_0")
        self.assertEqual(self.buffer.size, 10)
        self.assertTrue(self.buffer.is_full)
        self.assertEqual(
            self.buffer.snapshot_items(),
            [f"item_{i}" for i in range(1, 11)],
        )

        evicted2 = self.buffer.push("item_11")
        self.assertEqual(evicted2, "item_1")
        self.assertEqual(self.buffer.size, 10)
        self.assertTrue(self.buffer.is_full)
        self.assertEqual(
            self.buffer.snapshot_items(),
            [f"item_{i}" for i in range(2, 12)],
        )

    def test_pop_empty_buffer_raises_error(self) -> None:
        """Verifies pop on empty buffer raises BufferEmptyError."""
        with self.assertRaises(BufferEmptyError):
            self.buffer.pop()

    def test_pop_non_empty(self) -> None:
        """Verifies pop removes and returns oldest item in FIFO order."""
        self.buffer.push("a")
        self.buffer.push("b")
        self.buffer.push("c")

        val1 = self.buffer.pop()
        self.assertEqual(val1, "a")
        self.assertEqual(self.buffer.size, 2)
        self.assertEqual(self.buffer.snapshot_items(), ["b", "c"])

        val2 = self.buffer.pop()
        self.assertEqual(val2, "b")
        self.assertEqual(self.buffer.size, 1)
        self.assertEqual(self.buffer.snapshot_items(), ["c"])

        val3 = self.buffer.pop()
        self.assertEqual(val3, "c")
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), [])

        with self.assertRaises(BufferEmptyError):
            self.buffer.pop()

    def test_pop_after_eviction(self) -> None:
        """Verifies pop removes correct oldest remaining item after evictions."""
        for i in range(10):
            self.buffer.push(i)

        self.buffer.push(10)
        popped = self.buffer.pop()
        self.assertEqual(popped, 1)
        self.assertEqual(self.buffer.size, 9)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), list(range(2, 11)))

    def test_clear_resets_size(self) -> None:
        """Verifies clear removes all items and resets size to zero."""
        self.buffer.push("x")
        self.buffer.push("y")
        self.assertEqual(self.buffer.size, 2)

        self.buffer.clear()
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), [])

        with self.assertRaises(BufferEmptyError):
            self.buffer.pop()

    def test_clear_empty_buffer(self) -> None:
        """Verifies clear on already empty buffer maintains empty state."""
        self.buffer.clear()
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), [])

    def test_snapshot_items_fifo_order_and_non_mutating(self) -> None:
        """Verifies snapshot returns items in FIFO order without mutating buffer."""
        self.buffer.push(100)
        self.buffer.push(200)
        self.buffer.push(300)

        snapshot: List[Any] = self.buffer.snapshot_items()
        self.assertEqual(snapshot, [100, 200, 300])

        snapshot.append(999)
        self.assertEqual(self.buffer.snapshot_items(), [100, 200, 300])
        self.assertEqual(self.buffer.size, 3)
        self.assertFalse(self.buffer.is_empty)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T19:54:01Z
# LAST_CHANGED: 2026-11-08T19:53:16Z
# CHANGE: Implement unit test suite for RingBuffer lifecycle singleton verifying all specification contracts
# COVERAGE_AUDIT: 2026-11-08T19:54:01Z
# QA_AUDIT: 2026-11-08T19:53:39Z
# --- END AUTOFAB METADATA ---
