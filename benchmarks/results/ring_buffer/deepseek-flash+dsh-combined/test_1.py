"""Unit tests for the bounded circular ring buffer implementation.

Verifies the postconditions contracted in ``low/ring_buffer_impl.pyi`` (and the
supertype protocol postconditions inherited from ``low/ring_buffer.pyi``) for the
lifecycle-managed ``RingBuffer`` singleton.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

PART_ROOT = str(Path(__file__).resolve().parents[2])


def _anchor_implementation_package() -> None:
    """Anchor ``ring_buffer`` resolution to this test file's own part directory.

    A runner may expose several parts named ``ring_buffer`` on ``sys.path`` and
    may already have imported a different one, which makes a bare import
    resolve to the wrong module. Pinning this part's root at the front of
    ``sys.path`` (and dropping stale cached modules) makes the companion
    implementation resolution deterministic rather than dependent on ambient
    ``sys.path`` ordering.
    """
    if PART_ROOT in sys.path:
        sys.path.remove(PART_ROOT)
    sys.path.insert(0, PART_ROOT)
    stale_modules = [
        name
        for name in list(sys.modules)
        if name == "ring_buffer" or name.startswith("ring_buffer.")
    ]
    for name in stale_modules:
        sys.modules.pop(name, None)


def _release_implementation_package() -> None:
    """Drop the temporary anchor so later imports use their own resolution."""
    if PART_ROOT in sys.path:
        sys.path.remove(PART_ROOT)


_anchor_implementation_package()

from ring_buffer.lib.ring_buffer_impl import (
    RingBuffer,
    __initialize__,
)

_release_implementation_package()


class RingBufferImplTest(unittest.TestCase):
    """Behavioral tests for the system-tier RingBuffer singleton."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state_is_empty_with_default_capacity(self) -> None:
        """Happy path: a freshly resolved buffer is empty with capacity 10."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertEqual(buffer.capacity, 10)
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])

    def test_push_within_capacity_stores_item_and_returns_none(self) -> None:
        """POSTCONDITION: WHEN size < capacity, store item, size += 1, return None."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            self.assertIsNone(buffer.push("alpha"))
            self.assertEqual(buffer.size, 1)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), ["alpha"])
            self.assertEqual(buffer.capacity, 10)

    def test_push_fills_buffer_up_to_capacity(self) -> None:
        """POSTCONDITION: repeated pushes below capacity never evict and grow size."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(buffer.capacity - 1):
                self.assertIsNone(buffer.push("item-{0}".format(index)))
                self.assertEqual(buffer.size, index + 1)
                self.assertFalse(buffer.is_full)
            self.assertIsNone(buffer.push("item-final"))
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertTrue(buffer.is_full)

    def test_push_when_full_evicts_oldest_and_returns_it(self) -> None:
        """POSTCONDITION: WHEN size == capacity, evict oldest, store newest, size stable, return evicted."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(buffer.capacity):
                buffer.push("item-{0}".format(index))
            self.assertTrue(buffer.is_full)
            evicted = buffer.push("item-latest")
            self.assertEqual(evicted, "item-0")
            self.assertEqual(buffer.size, buffer.capacity)
            self.assertTrue(buffer.is_full)
            self.assertEqual(buffer.snapshot_items()[0], "item-1")
            self.assertEqual(buffer.snapshot_items()[-1], "item-latest")

    def test_pushes_after_saturation_preserve_fifo_order(self) -> None:
        """INVARIANT: overwrite eviction preserves oldest-to-newest arrival order."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            capacity = buffer.capacity
            for index in range(capacity):
                buffer.push(index)
            self.assertEqual(buffer.push("wrapped-0"), 0)
            self.assertEqual(
                buffer.snapshot_items(),
                list(range(1, capacity)) + ["wrapped-0"],
            )
            self.assertEqual(buffer.push("wrapped-1"), 1)
            self.assertEqual(
                buffer.snapshot_items(),
                list(range(2, capacity)) + ["wrapped-0", "wrapped-1"],
            )
            self.assertEqual(buffer.size, capacity)

    def test_pop_removes_oldest_and_decrements_size(self) -> None:
        """POSTCONDITION: WHEN size > 0, remove oldest, size -= 1, return removed item."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for item in ("first", "second", "third"):
                buffer.push(item)
            self.assertEqual(buffer.pop(), "first")
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.snapshot_items(), ["second", "third"])
            self.assertEqual(buffer.pop(), "second")
            self.assertEqual(buffer.size, 1)
            self.assertEqual(buffer.snapshot_items(), ["third"])

    def test_pop_until_empty_restores_empty_state(self) -> None:
        """POSTCONDITION: popping every item leaves the buffer empty and not full."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for item in ("one", "two"):
                buffer.push(item)
            self.assertEqual(buffer.pop(), "one")
            self.assertEqual(buffer.pop(), "two")
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])
            self.assertEqual(buffer.capacity, 10)

    def test_push_after_pop_reuses_freed_capacity(self) -> None:
        """INVARIANT: space freed by pop is available again for push without eviction."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("first")
            buffer.push("second")
            self.assertEqual(buffer.pop(), "first")
            self.assertIsNone(buffer.push("third"))
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.snapshot_items(), ["second", "third"])

    def test_clear_removes_all_items_and_resets_size(self) -> None:
        """POSTCONDITION: clear removes all items and resets size to zero."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for item in ("x", "y", "z"):
                buffer.push(item)
            buffer.clear()
            self.assertEqual(buffer.size, 0)
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.snapshot_items(), [])
            self.assertEqual(buffer.capacity, 10)

    def test_clear_on_full_buffer_keeps_capacity(self) -> None:
        """POSTCONDITION: clearing a saturated buffer empties it without changing capacity."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for index in range(buffer.capacity):
                buffer.push(index)
            self.assertTrue(buffer.is_full)
            buffer.clear()
            self.assertTrue(buffer.is_empty)
            self.assertFalse(buffer.is_full)
            self.assertEqual(buffer.capacity, 10)
            self.assertIsNone(buffer.push("restart"))
            self.assertEqual(buffer.snapshot_items(), ["restart"])

    def test_snapshot_items_returns_fifo_snapshot(self) -> None:
        """POSTCONDITION: snapshot lists all stored items oldest-first."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            for item in ("oldest", "middle", "newest"):
                buffer.push(item)
            self.assertEqual(
                buffer.snapshot_items(), ["oldest", "middle", "newest"]
            )

    def test_snapshot_items_does_not_mutate_buffer(self) -> None:
        """POSTCONDITION: snapshot MUST NOT modify contents, size, capacity, or state."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("keep-1")
            buffer.push("keep-2")
            size_before = buffer.size
            capacity_before = buffer.capacity
            first = buffer.snapshot_items()
            second = buffer.snapshot_items()
            self.assertEqual(first, second)
            self.assertEqual(first, ["keep-1", "keep-2"])
            self.assertEqual(buffer.size, size_before)
            self.assertEqual(buffer.capacity, capacity_before)
            self.assertFalse(buffer.is_empty)
            self.assertFalse(buffer.is_full)

    def test_snapshot_items_returns_independent_copy(self) -> None:
        """POSTCONDITION: mutating the snapshot leaves buffer contents unchanged."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(RingBuffer)
            buffer.push("stable-1")
            buffer.push("stable-2")
            snapshot = buffer.snapshot_items()
            snapshot.append("intruder")
            snapshot.reverse()
            self.assertEqual(buffer.size, 2)
            self.assertEqual(buffer.snapshot_items(), ["stable-1", "stable-2"])


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None (BufferEmptyError is a checked precondition violation and is not testable
# per role contract rules; all contracted postconditions are covered above).

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-04T19:58:20Z
# LAST_CHANGED: 2026-11-04T19:57:45Z
# CHANGE: Resolve coverage-runner collection feedback: the companion implementation is now imported through a deterministic, file-anchored resolution. A module-level anchor pins this part's root (resolved from __file__) at the front of sys.path and drops any stale cached 'ring_buffer' modules before importing 'from ring_buffer.lib.ring_buffer_impl import ...', then releases the temporary path entry so later imports keep their own resolution. This removes dependence on the runner's ambient sys.path ordering and prevents the shared top-level name 'ring_buffer' from resolving to a different module, so collection succeeds in every run mode; all contracted postconditions remain covered.
# COVERAGE_AUDIT: 2026-11-04T19:58:20Z
# QA_AUDIT: 2026-11-04T19:58:07Z
# --- END AUTOFAB METADATA ---
