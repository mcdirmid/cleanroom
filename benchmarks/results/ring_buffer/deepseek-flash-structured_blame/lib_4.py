# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261111_051028_deepseek-flash_ring_buffer
# Timestamp: 2026-11-11T05:10:28.213226+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 67,917
#   Cached Inbound Tokens:   1,875,707
#   Outbound Tokens:         37,047
#   Total Tokens:            1,980,671
#   Financial Cost ($USD):   $0.0380
#   Wall Clock Duration:     252.44s
#   Step Latencies (s):      [111.6, 207.5, 20.2, 10.0]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       9
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
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
        """Returns non-destructive snapshot of active items in circular FIFO arrival order.

        Returns:
            List containing active items ordered from oldest to newest arrival.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T05:13:46Z
# LAST_CHANGED: 2026-11-11T05:13:46Z
# CHANGE: Initialize ring buffer interface module: BufferError/BufferEmptyError data types and @poly_type RingBuffer protocol with capacity, size, is_empty, is_full, push, pop, clear, and test-only snapshot_items stubs matching low/ring_buffer.pyi.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Library implementation for the bounded circular ring buffer."""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional
from pretense.parts.pretense.lib.pretense import test_only
from . import ring_buffer
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque."""

    tier: str = "system"

    def __init__(self) -> None:
        """Initializes the default bounded backing storage."""
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=10)

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
        """Appends an item to the circular buffer with overwrite eviction on saturation."""
        evicted: Optional[Any] = None
        # When the buffer has reached capacity, the oldest item is evicted by the
        # bounded deque and returned to the caller.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
        self._buffer.append(item)
        return evicted

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        # Popping from an empty buffer violates the caller-visible contract.
        if len(self._buffer) == 0:
            raise ring_buffer.BufferEmptyError()
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
        """Returns non-destructive snapshot of active items in circular FIFO arrival order."""
        return list(self._buffer)


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RingBuffer,
        keys=[RingBuffer, ring_buffer.RingBuffer],
        tier=RingBuffer.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T05:14:37Z
# LAST_CHANGED: 2026-11-11T05:13:51Z
# CHANGE: Initialize ring buffer implementation: @singleton_type(system) RingBuffer backed by collections.deque(maxlen=10) implementing capacity/size/is_empty/is_full, FIFO push with overwrite eviction, pop raising BufferEmptyError when empty, clear, non-mutating snapshot_items, and auto-generated __initialize__ registration.
# COVERAGE_AUDIT: 2026-11-11T05:14:37Z
# QA_AUDIT: 2026-11-11T05:14:15Z
# --- END AUTOFAB METADATA ---
