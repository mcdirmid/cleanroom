# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261110_183753_deepseek-flash_ring_buffer
# Timestamp: 2026-11-10T18:37:53.093264+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 71,690
#   Cached Inbound Tokens:   1,506,944
#   Outbound Tokens:         32,370
#   Total Tokens:            1,611,004
#   Financial Cost ($USD):   $0.0347
#   Wall Clock Duration:     227.21s
#   Step Latencies (s):      [122.0, 165.0, 10.0, 20.2]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       15
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Low-level interface for a bounded circular ring buffer."""

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
        """Appends an item, evicting the oldest item when the buffer is full."""
        ...

    @operation
    def pop(self) -> Any:
        """Removes and returns the oldest item, raising when the buffer is empty."""
        ...

    @operation
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero."""
        ...

    @operation
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns a non-destructive snapshot of items in FIFO arrival order."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T18:40:47Z
# LAST_CHANGED: 2026-11-10T18:40:47Z
# CHANGE: Implement RingBuffer interface: BufferError/BufferEmptyError exception types, concrete data type decorators, protocol with capacity/size/is_empty/is_full properties plus push/pop/clear/snapshot_items operations; use package-qualified pretense import.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete bounded circular ring buffer implementation."""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
from pretense.parts.pretense.lib.pretense import test_only

from . import ring_buffer


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque."""

    tier: str = "system"

    def __init__(self) -> None:
        # GROUNDING: initialize default capacity 10 backed by a bounded deque.
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        """Returns the maximum number of items permitted in the buffer."""
        return self._capacity

    @property
    @override
    def size(self) -> int:
        """Returns the current number of items stored in the buffer."""
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        """Indicates whether the buffer contains zero items."""
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        """Indicates whether the buffer has reached its capacity limit."""
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item, evicting the oldest item when the buffer is full."""
        # At capacity the oldest item is captured, the new item is stored, size
        # stays at capacity, and the evicted item is returned.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # With space available the item is stored, size increments by one, and
        # None is returned.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the buffer."""
        # Popping an empty buffer must raise the contracted BufferEmptyError.
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("cannot pop from an empty ring buffer")
        # Remove and return the oldest item from the non-empty buffer.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items from the buffer, resetting size to zero."""
        # Removing every stored item resets the buffer size to zero.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns a non-destructive snapshot of items in FIFO arrival order."""
        # A shallow list copy preserves oldest-to-newest order without mutating
        # the buffer contents, size, capacity, or operational state.
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
# LAST_CLEANED: 2026-11-10T18:41:27Z
# LAST_CHANGED: 2026-11-10T18:40:53Z
# CHANGE: Implement concrete RingBuffer singleton backed by collections.deque(maxlen=10): capacity/size/is_empty/is_full properties, push with overwrite eviction returning evicted item, pop raising BufferEmptyError when empty, clear resetting size, and non-mutating snapshot_items in FIFO order.
# COVERAGE_AUDIT: 2026-11-10T18:41:27Z
# QA_AUDIT: 2026-11-10T18:41:15Z
# --- END AUTOFAB METADATA ---
