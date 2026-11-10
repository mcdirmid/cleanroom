from __future__ import annotations

import unittest
from typing import Any

from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__
from ring_buffer.lib.ring_buffer import BufferEmptyError
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system


class RingBufferImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.buffer = self.phase_scope.get_singleton(RingBuffer)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_initial_state(self) -> None:
        """Verify initial capacity, size, and empty/full states."""
        self.assertEqual(self.buffer.capacity, 10)
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), [])

    def test_push_available_capacity(self) -> None:
        """Verify push when size < capacity."""
        evicted = self.buffer.push("item1")
        self.assertIsNone(evicted)
        self.assertEqual(self.buffer.size, 1)
        self.assertFalse(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), ["item1"])

    def test_push_overwrite_eviction(self) -> None:
        """Verify push when size == capacity."""
        for i in range(10):
            res = self.buffer.push(i)
            self.assertIsNone(res)
        
        self.assertTrue(self.buffer.is_full)
        self.assertEqual(self.buffer.size, 10)
        self.assertEqual(self.buffer.snapshot_items(), list(range(10)))

        evicted = self.buffer.push(10)
        self.assertEqual(evicted, 0)
        self.assertEqual(self.buffer.size, 10)
        self.assertTrue(self.buffer.is_full)
        self.assertEqual(self.buffer.snapshot_items(), list(range(1, 11)))

    def test_pop_non_empty(self) -> None:
        """Verify pop when size > 0."""
        self.buffer.push("a")
        self.buffer.push("b")
        self.assertEqual(self.buffer.size, 2)

        item = self.buffer.pop()
        self.assertEqual(item, "a")
        self.assertEqual(self.buffer.size, 1)
        self.assertEqual(self.buffer.snapshot_items(), ["b"])

    def test_pop_empty_buffer(self) -> None:
        """Verify pop when size == 0 raises BufferEmptyError."""
        with self.assertRaises(BufferEmptyError):
            self.buffer.pop()

    def test_clear(self) -> None:
        """Verify clear removes all items and resets size to zero."""
        self.buffer.push("a")
        self.buffer.push("b")
        self.assertEqual(self.buffer.size, 2)

        self.buffer.clear()
        self.assertEqual(self.buffer.size, 0)
        self.assertTrue(self.buffer.is_empty)
        self.assertEqual(self.buffer.snapshot_items(), [])


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T21:36:28Z
# LAST_CHANGED: 2026-11-08T21:35:23Z
# CHANGE: Implemented ring_buffer_impl unit test suite covering capacity, size, push, pop, clear, and snapshot operations.
# COVERAGE_AUDIT: 2026-11-08T21:36:28Z
# QA_AUDIT: 2026-11-08T21:36:16Z
# --- END AUTOFAB METADATA ---
