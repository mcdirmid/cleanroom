# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261102_232304_deepseek-flash_ring_buffer_pretense
# Timestamp: 2026-11-02T23:23:04.501677+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 107,591
#   Cached Inbound Tokens:   5,012,096
#   Outbound Tokens:         106,586
#   Total Tokens:            5,226,273
#   Financial Cost ($USD):   $0.0951
#   Wall Clock Duration:     663.55s
#   Step Latencies (s):      [74.0, 332.6, 93.8, 195.8, 21.4, 30.9]
#   Role Execution Rounds:   lib: 1, pretense: 2, pretense_coverage: 1, pretense_qa: 2 (Total: 6)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Library interface specification for bounded circular ring buffer."""

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

        POSTCONDITIONS:
        - WHEN size is less than capacity, MUST store item, increment size by 1, and return None.
        - WHEN size equals capacity, MUST evict oldest item, store new item at most recent position, maintain size at capacity, and return the evicted item.
        """
        ...

    @operation
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer.

        Returns:
            The oldest item stored in the buffer.

        Raises:
            BufferEmptyError: If the circular buffer contains zero items.

        POSTCONDITIONS:
        - WHEN size is greater than zero, MUST remove oldest item, decrement size by 1, and return the removed item.
        - WHEN size equals zero, MUST raise BufferEmptyError.
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
# LAST_CLEANED: 2026-11-02T23:24:25Z
# LAST_CHANGED: 2026-11-02T23:24:25Z
# CHANGE: Initialize RingBuffer interface module: BufferError/BufferEmptyError data types and abstract RingBuffer protocol with capacity/size/is_empty/is_full properties plus push/pop/clear/snapshot_items operations, using full pretense package import path
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Library implementation for bounded circular ring buffer."""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, List, Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import ring_buffer


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque.

    GROUNDING:
    - Realizes bounded FIFO circular storage with default capacity 10 using collections.deque(maxlen=capacity).
    - Initializes internal _capacity to 10 and _buffer to collections.deque(maxlen=10).
    """

    tier: str = "system"

    def __init__(self) -> None:
        # GROUNDING: initialize bounded backing storage with the default capacity of 10.
        self._capacity: int = 10
        self._buffer: Deque[Any] = deque(maxlen=self._capacity)

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
        # POSTCONDITIONS: WHEN size equals capacity, MUST evict oldest item, store the
        # new item at the most recent position, and return the evicted item.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
        # POSTCONDITIONS: WHEN size is less than capacity, MUST store item, increment
        # size by 1, and return None; the bounded deque overwrites the oldest slot when full.
        self._buffer.append(item)
        return evicted

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        # POSTCONDITIONS: WHEN size equals zero, MUST raise BufferEmptyError.
        if len(self._buffer) == 0:
            raise ring_buffer.BufferEmptyError()
        # POSTCONDITIONS: WHEN size is greater than zero, MUST remove the oldest item,
        # decrement size by 1, and return the removed item.
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
        # POSTCONDITIONS: MUST return all currently stored items in FIFO arrival order
        # WITHOUT modifying buffer contents, size, capacity, or operational state.
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
# LAST_CLEANED: 2026-11-02T23:33:54Z
# LAST_CHANGED: 2026-11-02T23:24:28Z
# CHANGE: Initialize RingBuffer_impl: singleton system-tier class backed by collections.deque(maxlen=10) with working capacity/size/is_empty/is_full properties, overwrite-eviction push, BufferEmptyError-raising pop, clear, and non-destructive snapshot_items; full pretense package import path
# PRETENSE_COVERAGE_AUDIT: 2026-11-02T23:33:54Z
# PRETENSE_QA_AUDIT: 2026-11-02T23:33:33Z
# --- END AUTOFAB METADATA ---
