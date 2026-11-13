# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_161920_deepseek-flash_ring_buffer_pretense
# Timestamp: 2026-11-12T16:19:20.119056+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 82,244
#   Cached Inbound Tokens:   2,185,728
#   Outbound Tokens:         53,971
#   Total Tokens:            2,321,943
#   Financial Cost ($USD):   $0.0513
#   Wall Clock Duration:     374.74s
#   Step Latencies (s):      [106.1, 350.0, 10.1, 10.1]
#   Role Execution Rounds:   lib: 1, pretense: 1, pretense_coverage: 1, pretense_qa: 1 (Total: 4)
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
"""Abstract ring buffer protocol and domain error types."""

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
        """Returns non-destructive snapshot of active items in circular FIFO arrival order.

        Returns:
            List containing active items ordered from oldest to newest arrival.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T16:20:50Z
# LAST_CHANGED: 2026-11-12T16:20:50Z
# CHANGE: Define ring buffer interface protocol, data-type error hierarchy, and operation stubs mirroring the low-level specification.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete bounded circular ring buffer implementation."""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense.parts.pretense.lib.pretense import test_only

from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from . import ring_buffer


@singleton
class RingBuffer(ring_buffer.RingBuffer):
    """Bounded circular buffer backed by a fixed-length deque.

    The buffer keeps at most ten items by default; once saturated, each push
    evicts and returns the oldest item before storing the newest one.
    """

    tier: str = "system"

    def __init__(self) -> None:
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
        """Appends an item, evicting and returning the oldest item when saturated."""
        # A saturated buffer discards its oldest item as the newest one arrives.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # Available capacity stores the item without any eviction.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        # Popping an empty buffer is a contracted violation.
        if self.is_empty:
            raise ring_buffer.BufferEmptyError(
                "Cannot pop from an empty ring buffer"
            )
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
        """Returns a non-destructive snapshot of items in FIFO arrival order."""
        # Copying preserves the buffer contents while exposing oldest-first order.
        return list(self._buffer)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T16:25:31Z
# LAST_CHANGED: 2026-11-12T16:20:55Z
# CHANGE: Implement system-tier ring buffer singleton with deque-backed bounded storage, overwrite eviction, empty-pop error, clear, and non-destructive FIFO snapshot.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T16:25:31Z
# PRETENSE_QA_AUDIT: 2026-11-12T16:25:17Z
# --- END AUTOFAB METADATA ---
