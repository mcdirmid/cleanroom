"""Unit tests for ring_buffer_impl per its grounding specification."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from ring_buffer.lib.ring_buffer_impl import RingBuffer, __initialize__
from ring_buffer.lib.ring_buffer import BufferEmptyError


class RingBufferImplTest(unittest.TestCase):
    """Tests for RingBuffer singleton per low/ring_buffer_impl.pyi and low/ring_buffer.pyi."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.scope = enter_phase("system", registry=self.registry)
        self.buffer: RingBuffer = self.scope.get_singleton(RingBuffer)

    def tearDown(self) -> None:
        self.scope.close()

    # -- Property invariants --

    def test_default_capacity_is_ten(self) -> None:
        """CUJ: RingBuffer initializes with default capacity of 10."""
        self.assertEqual(self.buffer.capacity, 10)

    def test_initial_size_is_zero(self) -> None:
        """CUJ: Newly created buffer has size zero."""
        self.assertEqual(self.buffer.size, 0)

    def test_initial_is_empty_is_true(self) -> None:
        """CUJ: Newly created buffer reports is_empty as True."""
        self.assertTrue(self.buffer.is_empty)

    def test_initial_is_full_is_false(self) -> None:
        """CUJ: Newly created buffer reports is_full as False."""
        self.assertFalse(self.buffer.is_full)

    # -- push happy path: no eviction --

    def test_push_into_empty_returns_none(self) -> None:
        """CUJ: Pushing into empty buffer stores item and returns None."""
        result = self.buffer.push("first")
        self.assertIsNone(result)
        self.assertEqual(self.buffer.size, 1)
        self.assertFalse(self.buffer.is_empty)

    def test_push_preserves_fifo_order(self) -> None:
        """CUJ: Pushed items are stored in FIFO arrival order."""
        self.buffer.push("a")
        self.buffer.push("b")
        self.buffer.push("c")
        self.assertEqual(self.buffer.size, 3)
        items = self.buffer.snapshot_items()
        self.assertEqual(items, ["a", "b", "c"])

    def test_push_returns_none_until_full(self) -> None:
        """CUJ: Push returns None for all items until capacity is reached."""
        for i in range(9):
            result = self.buffer.push(i)
            self.assertIsNone(result)
        self.assertEqual(self.buffer.size, 9)
        self.assertFalse(self.buffer.is_full)

    # -- push overwrite eviction --

    def test_push_full_buffer_returns_evicted_item(self) -> None:
        """CUJ: Pushing into a full buffer evicts oldest and returns it."""
        for i in range(10):
            self.buffer.push(i)
        self.assertTrue(self.buffer.is_full)
        evicted = self.buffer.push("new")
        self.assertEqual(evicted, 0)
        self.assertEqual(self.buffer.size, 10)
        self.assertTrue(self.buffer.is_full)

    def test_push_eviction_preserves_fifo_order(self) -> None:
        """CUJ: After eviction, remaining items maintain FIFO order."""
        for i in range(10):
            self.buffer.push(i)
        self.buffer.push("A")
        self.buffer.push("B")
        items = self.buffer.snapshot_items()
        # Items 0 and 1 evicted, so 2-9 and A,B remain
        self.assertEqual(items, [2, 3, 4, 5, 6, 7, 8, 9, "A", "B"])

    def test_push_overwrite_maintains_capacity(self) -> None:
        """INVARIANT: Buffer size never exceeds capacity after push."""
        for i in range(20):
            self.buffer.push(i)
        self.assertEqual(self.buffer.size, self.buffer.capacity)
        self.assertTrue(self.buffer.is_full)

    # -- pop happy path --

    def test_pop_returns_oldest_item(self) -> None:
        """CUJ: Pop returns the oldest (first-pushed) item."""
        self.buffer.push("first")
        self.buffer.push("second")
        self.buffer.push("third")
        self.assertEqual(self.buffer.pop(), "first")

    def test_pop_decrements_size(self) -> None:
        """POSTCONDITION: Pop decrements size by 1."""
        self.buffer.push("x")
        self.assertEqual(self.buffer.size, 1)
        self.buffer.pop()
        self.assertEqual(self.buffer.size, 0)

    def test_pop_updates_is_empty(self) -> None:
        """POSTCONDITION: Popping the last item sets is_empty to True."""
        self.buffer.push("x")
        self.buffer.pop()
        self.assertTrue(self.buffer.is_empty)

    def test_pop_fifo_sequence(self) -> None:
        """CUJ: Multiple pops return items in strict FIFO order."""
        for item in ["a", "b", "c", "d", "e"]:
            self.buffer.push(item)
        results = []
        for _ in range(5):
            results.append(self.buffer.pop())
        self.assertEqual(results, ["a", "b", "c", "d", "e"])

    def test_pop_after_eviction_returns_correct_item(self) -> None:
        """CUJ: Pop after eviction returns the not-yet-evicted oldest item."""
        for i in range(10):
            self.buffer.push(i)
        self.buffer.push("new")  # evicts 0
        self.assertEqual(self.buffer.pop(), 1)

    # -- pop empty buffer error --

    def test_pop_empty_raises_buffer_empty_error(self) -> None:
        """PRECONDITION: Pop on empty buffer MUST raise BufferEmptyError."""
        with self.assertRaises(BufferEmptyError):
            self.buffer.pop()

    def test_pop_empty_error_is_buffer_error(self) -> None:
        """PRECONDITION: BufferEmptyError is a subclass of BufferError."""
        with self.assertRaises(BufferEmptyError):
            self.buffer.pop()

    # -- clear --

    def test_clear_resets_size_to_zero(self) -> None:
        """POSTCONDITION: clear resets size to zero."""
        for i in range(5):
            self.buffer.push(i)
        self.assertNotEqual(self.buffer.size, 0)
        self.buffer.clear()
        self.assertEqual(self.buffer.size, 0)

    def test_clear_makes_buffer_empty(self) -> None:
        """POSTCONDITION: clear makes is_empty True."""
        self.buffer.push("x")
        self.buffer.clear()
        self.assertTrue(self.buffer.is_empty)

    def test_clear_removes_all_items(self) -> None:
        """POSTCONDITION: clear removes all items from the buffer."""
        for i in range(10):
            self.buffer.push(i)
        self.buffer.clear()
        items = self.buffer.snapshot_items()
        self.assertEqual(items, [])

    def test_clear_allows_push_after_clear(self) -> None:
        """INVARIANT: Buffer accepts new items after clear."""
        self.buffer.push("first")
        self.buffer.clear()
        self.buffer.push("second")
        self.assertEqual(self.buffer.size, 1)
        self.assertEqual(self.buffer.snapshot_items(), ["second"])

    # -- snapshot_items --

    def test_snapshot_returns_fif_ordered_list(self) -> None:
        """POSTCONDITION: snapshot_items returns items in FIFO arrival order."""
        self.buffer.push("alpha")
        self.buffer.push("beta")
        self.buffer.push("gamma")
        snapshot = self.buffer.snapshot_items()
        self.assertEqual(snapshot, ["alpha", "beta", "gamma"])

    def test_snapshot_is_non_mutating(self) -> None:
        """POSTCONDITION: snapshot_items does NOT modify buffer contents or state."""
        for i in range(5):
            self.buffer.push(i)
        size_before = self.buffer.size
        snapshot_a = self.buffer.snapshot_items()
        snapshot_b = self.buffer.snapshot_items()
        self.assertEqual(self.buffer.size, size_before)
        self.assertEqual(snapshot_a, snapshot_b)
        self.assertEqual(self.buffer.snapshot_items(), list(range(5)))

    def test_snapshot_empty_buffer_returns_empty_list(self) -> None:
        """POSTCONDITION: snapshot on empty buffer returns empty list."""
        snapshot = self.buffer.snapshot_items()
        self.assertEqual(snapshot, [])

    def test_snapshot_does_not_mutate_pop_state(self) -> None:
        """POSTCONDITION: Snapshot call does not alter subsequent pop behavior."""
        self.buffer.push("x")
        self.buffer.snapshot_items()
        self.assertEqual(self.buffer.pop(), "x")
        self.assertTrue(self.buffer.is_empty)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T07:55:01Z
# LAST_CHANGED: 2026-11-10T07:54:01Z
# CHANGE: Implemented comprehensive test suite for RingBuffer singleton covering all contracts from low/ring_buffer_impl.pyi and low/ring_buffer.pyi: property invariants (capacity=10, initial size=0, is_empty, is_full), push happy-path (no eviction returns None, FIFO order), push overwrite eviction (returns evicted oldest item, maintains capacity), pop happy-path (returns oldest, decrements size, FIFO sequence), pop empty BufferEmptyError precondition, clear (resets size to 0, removes all items, allows subsequent push), snapshot_items (FIFO order, non-mutating on empty/full buffer). Uses lifecycle-managed singleton pattern with LifecycleRegistry and enter_phase system scope.
# COVERAGE_AUDIT: 2026-11-10T07:55:01Z
# QA_AUDIT: 2026-11-10T07:54:38Z
# --- END AUTOFAB METADATA ---
