# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261116_014202_gemini-flash_ring_buffer
# Timestamp: 2026-11-16T01:42:02.667989+00:00
# Benchmark Task: ring_buffer
# Model: gemini-flash (Tier 2)
# Methodology: autofab
# Harness: antigravity
# Run Index: 5
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 235,388
#   Cached Inbound Tokens:   1,609,531
#   Outbound Tokens:         38,930
#   Total Tokens:            1,883,849
#   Financial Cost ($USD):   $0.0793
#   Wall Clock Duration:     275.71s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       13
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Low-level interface specification for bounded circular ring buffer."""

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
        """Returns non-destructive snapshot of active items in circular FIFO arrival order.

        Returns:
            List containing active items ordered from oldest to newest arrival.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-16T01:45:37Z
# LAST_CHANGED: 2026-11-16T01:45:37Z
# CHANGES:
# - [2026-11-16T01:45:37Z] [kind:new] [Lines: 1-2, 5-7, 9-81] [Scope: RingBuffer,BufferError,BufferEmptyError] Delta: Initial implementation of RingBuffer interface protocol and BufferError exceptions | Why: Fulfill low/ring_buffer.pyi interface contract
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Bounded circular ring buffer implementation."""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from . import ring_buffer


@singleton
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque."""

    tier: str = "system"

    def __init__(self, capacity: int = 10) -> None:
        """Initializes internal circular buffer backing state.

        Args:
            capacity: Maximum number of items the buffer can hold. Defaults to 10.
        """
        self._capacity: int = capacity
        self._buffer: deque[Any] = deque(maxlen=capacity)

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
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
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
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("Circular buffer contains zero items.")
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
        """Returns non-destructive snapshot of active items in circular FIFO arrival order.

        Returns:
            List containing active items ordered from oldest to newest arrival.
        """
        return list(self._buffer)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-16T01:46:36Z
# LAST_CHANGED: 2026-11-16T01:45:47Z
# CHANGES:
# - [2026-11-16T01:45:47Z] [kind:new] [Lines: 1-2, 5-6, 8-102] [Scope: RingBuffer] Delta: Initial implementation of RingBuffer using collections.deque with overwrite eviction and snapshot query | Why: Fulfill low/ring_buffer_impl.pyi implementation contract
# COVERAGE_AUDIT: 2026-11-16T01:46:36Z
# QA_AUDIT: 2026-11-16T01:46:07Z
# --- END AUTOFAB METADATA ---
