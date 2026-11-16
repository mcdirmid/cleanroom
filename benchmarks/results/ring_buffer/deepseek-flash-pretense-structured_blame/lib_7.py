# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261114_201746_deepseek-flash_ring_buffer_pretense
# Timestamp: 2026-11-14T20:17:46.175197+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 7
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 98,716
#   Cached Inbound Tokens:   3,339,904
#   Outbound Tokens:         90,896
#   Total Tokens:            3,529,516
#   Financial Cost ($USD):   $0.0794
#   Wall Clock Duration:     626.44s
#   Step Latencies (s):      [85.8, 448.8, 10.1, 63.1, 61.2, 10.1, 20.3]
#   Role Execution Rounds:   lib: 1, pretense: 2, pretense_coverage: 2, pretense_qa: 2 (Total: 7)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       3
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Interface definitions for a bounded circular first-in first-out ring buffer."""

from __future__ import annotations

from typing import Any, List, Optional, Protocol

from pretense import PretenseSpecificationError, test_only
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
# LAST_CLEANED: 2026-11-14T20:19:07Z
# LAST_CHANGED: 2026-11-14T20:19:07Z
# CHANGE: Implement bounded circular ring buffer interface: BufferError/BufferEmptyError value types and RingBuffer poly-type protocol with capacity, size, is_empty, is_full properties plus push (overwrite eviction), pop (empty raises BufferEmptyError), clear, and snapshot_items FIFO observability query.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete bounded circular first-in first-out ring buffer service."""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from . import ring_buffer


@singleton
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of a bounded circular buffer using a bounded deque."""

    tier: str = "system"

    def __init__(self) -> None:
        # A deque with a fixed maximum length provides the circular storage, and the
        # matching capacity is retained for direct inspection by clients.
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
        # A saturated buffer discards its oldest item before the new item is appended.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # Available space means the item is stored without any eviction.
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
        # Reading from an empty buffer is an invalid operation.
        if self.is_empty:
            raise ring_buffer.BufferEmptyError(
                "Cannot pop an item from an empty ring buffer."
            )
        # The oldest item sits at the head of the storage.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero."""
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns a non-destructive snapshot of active items in FIFO arrival order.

        Returns:
            List containing active items ordered from oldest to newest arrival.
        """
        # Copy into a plain list so callers cannot mutate the live buffer.
        return list(self._buffer)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T20:27:59Z
# LAST_CHANGED: 2026-11-14T20:19:12Z
# CHANGE: Implement concrete @singleton RingBuffer service backed by collections.deque(maxlen=10): default capacity 10, push returns None with space or evicts/returns oldest when full, pop raises BufferEmptyError when empty else popleft, clear empties storage, and snapshot_items returns a non-mutating FIFO list copy.
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T20:27:59Z
# PRETENSE_QA_AUDIT: 2026-11-14T20:27:46Z
# --- END AUTOFAB METADATA ---
