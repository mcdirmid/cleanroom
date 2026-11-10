# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_173049_deepseek-flash_ring_buffer_combined
# Timestamp: 2026-11-08T17:30:49.357797+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 159,734
#   Cached Inbound Tokens:   5,387,904
#   Outbound Tokens:         117,199
#   Total Tokens:            5,664,837
#   Financial Cost ($USD):   $0.1104
#   Wall Clock Duration:     789.47s
#   Step Latencies (s):      [114.6, 178.1, 173.7, 12.3, 22.5, 10.1, 53.0, 226.4, 122.3, 132.6, 20.3, 10.0]
#   Role Execution Rounds:   coverage: 1, lib: 1, pretense: 3, pretense_coverage: 2, pretense_qa: 3, qa: 1, test: 1 (Total: 12)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       11
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Interface specification for the bounded circular ring buffer."""

from __future__ import annotations

from typing import Any, List, Optional, Protocol

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type


@data_type
class BufferError(PretenseSpecificationError):
    """Base exception for all ring buffer operations."""

    pass


@data_type
class BufferEmptyError(BufferError):
    """Raised when attempting to pop or read from an empty ring buffer."""

    pass


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

        POSTCONDITIONS:
        - WHEN size is less than capacity, MUST store item, increment size by 1, and
          return None.
        - WHEN size equals capacity, MUST evict oldest item, store new item at most recent
          position, maintain size at capacity, and return the evicted item.
        """
        ...

    @operation
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer.

        Returns:
            The oldest item stored in the buffer.

        Raises:
            BufferEmptyError: If the circular buffer contains zero items.

        PRECONDITIONS:
        - WHEN size equals zero, MUST raise BufferEmptyError.

        POSTCONDITIONS:
        - WHEN size is greater than zero, MUST remove oldest item, decrement size by 1,
          and return the removed item.
        """
        ...

    @operation
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero.

        POSTCONDITIONS:
        - MUST remove all items from the buffer and reset size to zero.
        """
        ...

    @operation
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in circular FIFO arrival order.

        Returns:
            List containing active items ordered from oldest to newest arrival.

        POSTCONDITIONS:
        - MUST return a list containing all currently stored items in FIFO arrival order.
        - MUST NOT modify the buffer contents, size, capacity, or operational state.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:34:07Z
# LAST_CHANGED: 2026-11-08T17:34:07Z
# CHANGE: Implement bounded circular ring buffer interface: @data_type BufferError/BufferEmptyError exceptions, @poly_type RingBuffer Protocol with capacity/size/is_empty/is_full properties plus @operation push/pop/clear/snapshot_items (@test_only); fixed cross-part pretense import to full package path.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete implementation of the bounded circular ring buffer."""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import ring_buffer

# Requirements specified in ring_buffer_impl.pyi


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque.

    Realizes bounded FIFO circular storage with default capacity 10 using
    collections.deque(maxlen=capacity).
    """

    tier: str = "system"

    def __init__(self) -> None:
        # Default capacity is 10, backed by a bounded deque so that appends at
        # capacity automatically evict the oldest stored item.
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        # Exposes the fixed maximum number of items held by the buffer.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        # Current number of stored items, maintained by the bounded deque.
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        # Zero stored items indicates an empty buffer.
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        # The buffer is saturated once the stored item count reaches capacity.
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        # WHEN the buffer has available capacity, store the item and return None;
        # WHEN the buffer is saturated, the bounded deque evicts the oldest item,
        # the new item lands at the most recent position, size stays at capacity,
        # and the evicted item is returned.
        evicted: Optional[Any] = None
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
        self._buffer.append(item)
        return evicted

    @operation
    @override
    def pop(self) -> Any:
        # WHEN the buffer is empty, popping is a contracted precondition violation.
        if len(self._buffer) == 0:
            raise ring_buffer.BufferEmptyError(
                "Cannot pop from an empty ring buffer."
            )
        # WHEN the buffer is non-empty, remove and return the oldest item, which
        # decrements the size by 1 through the deque itself.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        # Removes every stored item and leaves the buffer with zero size.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        # Returns a shallow list copy in FIFO arrival order without mutating the
        # buffer contents, size, capacity, or operational state.
        return list(self._buffer)


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RingBuffer,
        keys=[RingBuffer, ring_buffer.RingBuffer],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:43:55Z
# LAST_CHANGED: 2026-11-08T17:34:13Z
# CHANGE: Implement concrete @singleton_type RingBuffer (tier system) over collections.deque(maxlen=10): capacity/size/is_empty/is_full properties, push with oldest-item eviction returning evicted value or None, pop raising BufferEmptyError on empty, clear resetting storage, and @test_only snapshot_items returning a non-mutating FIFO list copy; existing auto-generated __initialize__ registration preserved.
# COVERAGE_AUDIT: 2026-11-08T17:34:41Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:43:55Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:43:33Z
# QA_AUDIT: 2026-11-08T17:34:27Z
# --- END AUTOFAB METADATA ---
