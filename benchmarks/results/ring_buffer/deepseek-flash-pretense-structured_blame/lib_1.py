# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_172829_deepseek-flash_ring_buffer_pretense
# Timestamp: 2026-11-08T17:28:29.518227+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 129,096
#   Cached Inbound Tokens:   6,077,184
#   Outbound Tokens:         105,472
#   Total Tokens:            6,311,752
#   Financial Cost ($USD):   $0.1009
#   Wall Clock Duration:     804.00s
#   Step Latencies (s):      [144.4, 246.0, 20.2, 52.9, 286.6, 52.8, 134.4, 10.1, 20.2]
#   Role Execution Rounds:   lib: 1, pretense: 3, pretense_coverage: 2, pretense_qa: 3 (Total: 9)
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
"""Abstract interface specification for a bounded circular ring buffer."""

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
        """Appends an item to the circular buffer, evicting the oldest item when full.

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
# LAST_CLEANED: 2026-11-08T17:30:58Z
# LAST_CHANGED: 2026-11-08T17:30:58Z
# CHANGE: Author concrete RingBuffer interface: @data_type BufferError/BufferEmptyError deriving from PretenseSpecificationError, @poly_type Protocol with capacity/size/is_empty/is_full properties and operation stubs (push, pop, clear, @test_only snapshot_items); use package-qualified pretense import.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete implementation of a bounded circular ring buffer."""

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

    Realizes bounded FIFO circular storage with default capacity 10 using
    collections.deque(maxlen=capacity).
    """

    tier: str = "system"

    def __init__(self) -> None:
        # Initialize internal _capacity to 10 and _buffer to collections.deque(maxlen=10).
        self._capacity: int = 10
        self._buffer: Deque[Any] = deque(maxlen=self._capacity)

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
        # Saturated buffer: capture the oldest item before it is evicted by appending.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # Available capacity: store the item and report that nothing was evicted.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item, rejecting empty buffers."""
        # Empty buffer precondition: refuse to pop and signal the contracted error.
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("cannot pop from an empty ring buffer")
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items, resetting the buffer to zero size."""
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns a shallow copy of active items in FIFO arrival order."""
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
# LAST_CLEANED: 2026-11-08T17:41:40Z
# LAST_CHANGED: 2026-11-08T17:31:03Z
# CHANGE: Implement RingBuffer singleton on collections.deque(maxlen=10): capacity/size/is_empty/is_full accessors, push with overwrite eviction returning evicted oldest item or None, pop raising BufferEmptyError when empty, clear emptying buffer, and @test_only snapshot_items returning FIFO list copy.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T17:41:40Z
# PRETENSE_QA_AUDIT: 2026-11-08T17:41:28Z
# --- END AUTOFAB METADATA ---
