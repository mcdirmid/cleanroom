# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261111_231912_deepseek-flash_ring_buffer_pretense
# Timestamp: 2026-11-11T23:19:12.267809+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 79,177
#   Cached Inbound Tokens:   2,564,736
#   Outbound Tokens:         74,682
#   Total Tokens:            2,718,595
#   Financial Cost ($USD):   $0.0644
#   Wall Clock Duration:     428.05s
#   Step Latencies (s):      [106.7, 401.4, 10.1, 10.1]
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
"""Library interface declaration for the bounded circular ring buffer."""

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
        """Appends an item to the circular buffer with overwrite eviction on saturation."""
        ...

    @operation
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        ...

    @operation
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero."""
        ...

    @operation
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in circular FIFO arrival order."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T23:20:44Z
# LAST_CHANGED: 2026-11-11T23:20:44Z
# CHANGE: Implement ring buffer interface: BufferError/BufferEmptyError data types and RingBuffer poly_type Protocol with capacity/size/is_empty/is_full properties, push/pop/clear operations, and test_only snapshot_items stub.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete bounded circular ring buffer implementation."""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from ring_buffer_deepseek_flash_3.parts.ring_buffer.lib import ring_buffer


@singleton
class RingBuffer(ring_buffer.RingBuffer):
    """Bounded circular FIFO buffer backed by collections.deque(maxlen=capacity)."""

    tier = "system"

    def __init__(self) -> None:
        # GROUNDING: default capacity of 10 with a bounded deque of the same length.
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        """Maximum number of items permitted in the circular buffer."""
        # GROUNDING: returns self._capacity.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        """Current number of items stored in the circular buffer."""
        # GROUNDING: returns len(self._buffer).
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        """Indicates whether the circular buffer contains zero items."""
        # GROUNDING: evaluates len(self._buffer) == 0.
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        """Indicates whether the circular buffer has reached its capacity limit."""
        # GROUNDING: evaluates len(self._buffer) >= self._capacity.
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item to the circular buffer with overwrite eviction on saturation."""
        evicted: Optional[Any] = None
        # POSTCONDITIONS: WHEN size equals capacity, MUST evict the oldest item,
        # store the new item, maintain size at capacity, and return the evicted item.
        if len(self._buffer) == self._capacity:
            # POSTCONDITIONS: oldest item is the head of the bounded deque.
            evicted = self._buffer[0]
        # POSTCONDITIONS: WHEN size is less than capacity, MUST store the item,
        # increment size by 1, and return None; saturation overwrites the oldest.
        self._buffer.append(item)
        return evicted

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        # PRECONDITIONS: WHEN size equals zero, MUST raise BufferEmptyError.
        if len(self._buffer) == 0:
            raise ring_buffer.BufferEmptyError(
                "Cannot pop from an empty ring buffer."
            )
        # POSTCONDITIONS: WHEN size is greater than zero, MUST remove the oldest
        # item, decrement size by 1, and return the removed item.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero."""
        # POSTCONDITIONS: MUST remove all items from the buffer and reset size to zero.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in circular FIFO arrival order."""
        # POSTCONDITIONS: MUST return all stored items in FIFO arrival order while
        # MUST NOT modifying buffer contents, size, capacity, or operational state.
        return list(self._buffer)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T23:26:17Z
# LAST_CHANGED: 2026-11-11T23:20:50Z
# CHANGE: Implement RingBuffer singleton: deque-backed capacity-10 bounded FIFO, capacity/size/is_empty/is_full properties, push with overwrite eviction returning evicted oldest item, pop raising BufferEmptyError when empty, clear, and non-mutating snapshot_items.
# PRETENSE_COVERAGE_AUDIT: 2026-11-11T23:26:17Z
# PRETENSE_QA_AUDIT: 2026-11-11T23:26:04Z
# --- END AUTOFAB METADATA ---
