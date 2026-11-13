# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_204832_deepseek-flash_ring_buffer_pretense
# Timestamp: 2026-11-12T20:48:32.097536+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 5
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 116,806
#   Cached Inbound Tokens:   5,027,328
#   Outbound Tokens:         114,934
#   Total Tokens:            5,259,068
#   Financial Cost ($USD):   $0.1016
#   Wall Clock Duration:     646.76s
#   Step Latencies (s):      [136.9, 377.3, 165.7, 83.7, 10.3, 10.1]
#   Role Execution Rounds:   lib: 1, pretense: 2, pretense_coverage: 1, pretense_qa: 2 (Total: 6)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       2
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Library interface for the bounded circular ring buffer."""

from __future__ import annotations

from typing import Any, List, Optional, Protocol

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type


@data_type
class BufferError(PretenseSpecificationError):
    """Base exception for all ring buffer operations."""


@data_type
class BufferEmptyError(BufferError):
    """Raised when attempting to pop or read from an empty ring buffer."""


@poly_type
class RingBuffer(Protocol):
    """Bounded circular first-in first-out buffer with overwrite eviction."""

    @property
    def capacity(self) -> int:
        """Maximum number of items permitted in the circular buffer."""
        ...

    @property
    def size(self) -> int:
        """Current number of items stored in the circular buffer."""
        ...

    @property
    def is_empty(self) -> bool:
        """Indicates whether the circular buffer contains zero items."""
        ...

    @property
    def is_full(self) -> bool:
        """Indicates whether the circular buffer has reached its capacity limit."""
        ...

    @operation
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item to the circular buffer with overwrite eviction on saturation.

        Args:
            item: Item to store into the buffer.

        Returns:
            The evicted oldest item if the buffer was full, or None if space was available.
        """
        ...

    @operation
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer.

        Returns:
            The oldest item stored in the buffer.

        Raises:
            BufferEmptyError: If the circular buffer contains zero items.
        """
        ...

    @operation
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero."""
        ...

    @operation
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns a non-destructive snapshot of active items in FIFO arrival order.

        Returns:
            List containing active items ordered from oldest to newest arrival.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T20:50:37Z
# LAST_CHANGED: 2026-11-12T20:50:37Z
# CHANGE: Implement ring buffer interface module: BufferError/BufferEmptyError data-type exceptions and abstract RingBuffer protocol with capacity, size, is_empty, is_full properties and push/pop/clear/snapshot_items operations per low-level spec.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete realization of the bounded circular ring buffer."""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from . import ring_buffer


@singleton
class RingBuffer(ring_buffer.RingBuffer):
    """Bounded circular first-in first-out buffer with overwrite eviction."""

    tier: str = "system"

    def __init__(self) -> None:
        # Default capacity of ten items with a deque that enforces the bound.
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        """Maximum number of items permitted in the circular buffer."""
        return self._capacity

    @property
    @override
    def size(self) -> int:
        """Current number of items stored in the circular buffer."""
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        """Indicates whether the circular buffer contains zero items."""
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        """Indicates whether the circular buffer has reached its capacity limit."""
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item to the circular buffer with overwrite eviction on saturation.

        Args:
            item: Item to store into the buffer.

        Returns:
            The evicted oldest item if the buffer was full, or None if space was available.
        """
        # Only a saturated buffer evicts its oldest item when making room.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # Available capacity simply stores the item without eviction.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer.

        Returns:
            The oldest item stored in the buffer.

        Raises:
            BufferEmptyError: If the circular buffer contains zero items.
        """
        # An empty buffer has no oldest item to remove.
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("Cannot pop from an empty ring buffer")
        # Removing from the left preserves first-in first-out arrival order.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero."""
        # Discard every stored item while preserving the configured bound.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns a non-destructive snapshot of active items in FIFO arrival order.

        Returns:
            List containing active items ordered from oldest to newest arrival.
        """
        # Iterating the deque yields arrival order without mutating buffer state.
        return list(self._buffer)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T20:59:14Z
# LAST_CHANGED: 2026-11-12T20:50:42Z
# CHANGE: Implement RingBuffer singleton over collections.deque(maxlen=10): capacity/size/is_empty/is_full accessors, push with oldest-item eviction on saturation, pop raising BufferEmptyError on empty, clear, and non-mutating snapshot_items in FIFO order.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T20:59:14Z
# PRETENSE_QA_AUDIT: 2026-11-12T20:59:00Z
# --- END AUTOFAB METADATA ---
