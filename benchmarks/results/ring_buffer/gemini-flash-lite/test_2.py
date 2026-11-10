from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__
from ring_buffer.lib import ring_buffer


class RingBufferImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase("system", registry=self.registry)
        self.phase_scope.__enter__()
        self.buffer = self.phase_scope.get_singleton(RingBuffer)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_initial_state(self) -> None:
        self.assertTrue(self.buffer.is_empty)
        self.assertFalse(self.buffer.is_full)
        self.assertEqual(self.buffer.size, 0)
        self.assertEqual(self.buffer.capacity, 10)
        self.assertEqual(self.buffer.snapshot_items(), [])

    def test_push_available_capacity(self) -> None:
        res = self.buffer.push("item1")
        self.assertIsNone(res)
        self.assertFalse(self.buffer.is_empty)
        self.assertEqual(self.buffer.size, 1)
        self.assertEqual(self.buffer.snapshot_items(), ["item1"])

    def test_push_overwrite_eviction(self) -> None:
        for i in range(10):
            self.buffer.push(f"item{i}")
        self.assertTrue(self.buffer.is_full)
        self.assertEqual(self.buffer.size, 10)

        evicted = self.buffer.push("overflow")
        self.assertEqual(evicted, "item0")
        self.assertEqual(self.buffer.size, 10)
        self.assertEqual(self.buffer.snapshot_items()[-1], "overflow")

    def test_pop_non_empty(self) -> None:
        self.buffer.push("a")
        self.buffer.push("b")
        item = self.buffer.pop()
        self.assertEqual(item, "a")
        self.assertEqual(self.buffer.size, 1)
        self.assertEqual(self.buffer.snapshot_items(), ["b"])

    def test_pop_empty_buffer(self) -> None:
        with self.assertRaises(ring_buffer.BufferEmptyError):
            self.buffer.pop()

    def test_clear(self) -> None:
        self.buffer.push("a")
        self.buffer.push("b")
        self.buffer.clear()
        self.assertTrue(self.buffer.is_empty)
        self.assertEqual(self.buffer.size, 0)
        self.assertEqual(self.buffer.snapshot_items(), [])


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T21:51:16Z
# LAST_CHANGED: 2026-11-08T21:47:12Z
# CHANGE: Implemented unit test suite for RingBuffer singleton covering initialization, push operations, overwrite eviction, pop, clear, and snapshot observability.
# COVERAGE_AUDIT: 2026-11-08T21:51:16Z
# QA_AUDIT: 2026-11-08T21:51:04Z
# --- END AUTOFAB METADATA ---
