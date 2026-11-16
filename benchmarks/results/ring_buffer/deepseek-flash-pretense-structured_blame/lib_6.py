# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261114_175104_deepseek-flash_ring_buffer_pretense
# Timestamp: 2026-11-14T17:51:04.873497+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 6
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 105,688
#   Cached Inbound Tokens:   2,594,304
#   Outbound Tokens:         54,508
#   Total Tokens:            2,754,500
#   Financial Cost ($USD):   $0.0563
#   Wall Clock Duration:     432.41s
#   Step Latencies (s):      [85.8, 275.3, 10.1, 40.6, 63.1, 10.1, 20.2]
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
"""Interface specification for the bounded circular ring buffer."""

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

        Returns the evicted oldest item when full, otherwise None.
        """
        ...

    @operation
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer.

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
        """Returns a non-destructive snapshot of active items in FIFO arrival order."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T17:52:25Z
# LAST_CHANGED: 2026-11-14T17:52:25Z
# CHANGE: Implement RingBuffer interface protocol with BufferError/BufferEmptyError data types and @test_only snapshot_items query
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete realization of the bounded circular ring buffer."""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import get_singleton, singleton

from . import ring_buffer


@singleton
class RingBuffer(ring_buffer.RingBuffer):
    """Bounded first-in first-out circular buffer backed by a deque."""

    tier: str = "system"

    def __init__(self) -> None:
        # Default bounded capacity of ten items backed by a circular deque.
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        return self._capacity

    @property
    @override
    def size(self) -> int:
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        # A saturated buffer evicts its oldest item before accepting the new one.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # Spare capacity simply appends without any eviction.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        # Reading from an empty buffer is invalid and reports the contracted error.
        if self.is_empty:
            raise ring_buffer.BufferEmptyError()
        # Otherwise the oldest stored item is removed and returned.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        # Discard every stored item, restoring the buffer to an empty state.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        # Shallow copy preserves FIFO order without mutating the buffer.
        return list(self._buffer)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-14T17:58:04Z
# LAST_CHANGED: 2026-11-14T17:52:29Z
# CHANGE: Implement concrete RingBuffer singleton with deque(maxlen=10), overwrite eviction on push, BufferEmptyError on empty pop, clear, and non-mutating FIFO snapshot
# PRETENSE_COVERAGE_AUDIT: 2026-11-14T17:58:04Z
# PRETENSE_QA_AUDIT: 2026-11-14T17:57:51Z
# --- END AUTOFAB METADATA ---
