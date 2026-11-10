# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_194916_gemini-flash_ring_buffer
# Timestamp: 2026-11-08T19:49:16.812151+00:00
# Benchmark Task: ring_buffer
# Model: gemini-flash (Tier 2)
# Methodology: autofab
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 516,866
#   Cached Inbound Tokens:   1,919,061
#   Outbound Tokens:         49,380
#   Total Tokens:            2,485,307
#   Financial Cost ($USD):   $0.1194
#   Wall Clock Duration:     287.61s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 2, lib: 1, qa: 2, test: 1 (Total: 6)
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
# LAST_CLEANED: 2026-11-08T19:53:05Z
# LAST_CHANGED: 2026-11-08T19:53:05Z
# CHANGE: Implement ring_buffer interface protocols and exceptions
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
from __future__ import annotations

from collections import deque
from typing import Any, List, Optional
from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from . import ring_buffer


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque."""

    tier: str = "system"

    def __init__(self, capacity: int = 10) -> None:
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
        """Appends an item to the circular buffer with overwrite eviction on saturation."""
        if len(self._buffer) >= self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("Cannot pop from an empty ring buffer.")
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
# LAST_CLEANED: 2026-11-08T19:54:01Z
# LAST_CHANGED: 2026-11-08T19:53:12Z
# CHANGE: Implement RingBuffer concrete singleton realization using collections.deque
# COVERAGE_AUDIT: 2026-11-08T19:54:01Z
# QA_AUDIT: 2026-11-08T19:53:39Z
# --- END AUTOFAB METADATA ---
