# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_195924_deepseek-flash_ring_buffer
# Timestamp: 2026-11-12T19:59:24.338592+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 5
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 138,752
#   Cached Inbound Tokens:   1,443,835
#   Outbound Tokens:         41,385
#   Total Tokens:            1,623,972
#   Financial Cost ($USD):   $0.0500
#   Wall Clock Duration:     223.37s
#   Step Latencies (s):      [137.0, 183.6, 10.1, 10.1]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       10
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Interface module for the bounded circular ring buffer.

Defines the passive error value types and the abstract ring buffer protocol that
concrete implementations realize.
"""

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
        """Appends an item, evicting the oldest item when the buffer is full.

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
        """Returns non-destructive snapshot of active items in FIFO arrival order.

        Returns:
            List containing active items ordered from oldest to newest arrival.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T20:01:30Z
# LAST_CHANGED: 2026-11-12T20:01:30Z
# CHANGE: Implement ring buffer interface module: BufferError and BufferEmptyError value types plus RingBuffer protocol with capacity, size, is_empty, is_full, push, pop, clear, and snapshot_items declarations aligned to low/ring_buffer.pyi.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete implementation module for the bounded circular ring buffer.

Realizes the ring buffer protocol with a bounded collections.deque that evicts
the oldest item automatically once capacity is reached.
"""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from . import ring_buffer


@singleton
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete bounded circular buffer using collections.deque.

    The buffer starts empty with a capacity of ten items and evicts the oldest
    stored item when a push occurs at full capacity.
    """

    tier: str = "system"

    def __init__(self) -> None:
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
        # At capacity the oldest item is evicted as the newest item is appended.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        # Removing from an empty buffer violates the pop precondition.
        if not self._buffer:
            raise ring_buffer.BufferEmptyError(
                "Cannot pop an item from an empty ring buffer."
            )
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        # A shallow copy preserves arrival order without mutating the buffer.
        return list(self._buffer)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T20:03:04Z
# LAST_CHANGED: 2026-11-12T20:01:35Z
# CHANGE: Implement RingBuffer singleton backed by collections.deque with default capacity 10: capacity/size/is_empty/is_full accessors, overwrite-eviction push, BufferEmptyError-raising pop, clear, and non-mutating snapshot_items per low/ring_buffer_impl.pyi.
# COVERAGE_AUDIT: 2026-11-12T20:03:04Z
# QA_AUDIT: 2026-11-12T20:02:50Z
# --- END AUTOFAB METADATA ---
