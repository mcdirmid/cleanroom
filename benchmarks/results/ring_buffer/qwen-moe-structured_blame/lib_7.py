# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261110_075809_qwen-moe_ring_buffer
# Timestamp: 2026-11-10T07:58:09.788026+00:00
# Benchmark Task: ring_buffer
# Model: qwen-moe (Tier 1)
# Methodology: autofab
# Harness: dsh
# Run Index: 7
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 63,671
#   Cached Inbound Tokens:   916,256
#   Outbound Tokens:         22,294
#   Total Tokens:            1,002,221
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     314.75s
#   Step Latencies (s):      [223.5, 246.1, 20.2, 20.2]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       14
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Low-level interface specification for bounded circular ring buffer."""

from __future__ import annotations

from typing import Any, List, Optional, Protocol

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type


@data_type
class BufferError(PretenseSpecificationError):
    """Base exception for all ring buffer operations."""

    message: str

    def __str__(self) -> str:
        return self.message


@data_type
class BufferEmptyError(BufferError):
    """Raised when attempting to pop or read from an empty ring buffer."""

    message: str

    def __str__(self) -> str:
        return self.message


@poly_type
class RingBuffer(Protocol):
    """Bounded circular first-in first-out buffer with overwrite eviction."""

    @property
    def capacity(self) -> int:
        ...

    @property
    def size(self) -> int:
        ...

    @property
    def is_empty(self) -> bool:
        ...

    @property
    def is_full(self) -> bool:
        ...

    @operation
    def push(self, item: Any) -> Optional[Any]:
        ...

    @operation
    def pop(self) -> Any:
        ...

    @operation
    def clear(self) -> None:
        ...

    @operation
    @test_only
    def snapshot_items(self) -> List[Any]:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T08:02:17Z
# LAST_CHANGED: 2026-11-10T08:02:17Z
# CHANGE: Implemented interface module: BufferError and BufferEmptyError data types with __str__ methods, and RingBuffer Protocol with @poly_type decorator, @operation decorators on all methods, and @test_only on snapshot_items.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)

from . import ring_buffer


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque.

    Initializes internal _capacity to 10 and _buffer to deque(maxlen=10).
    """

    tier: str = "system"

    def __init__(self) -> None:
        self._capacity: int = 10
        self._buffer: deque = deque(maxlen=self._capacity)

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
        return self._buffer.__len__() == 0

    @property
    @override
    def is_full(self) -> bool:
        """Indicates whether the circular buffer has reached its capacity limit."""
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item to the circular buffer with overwrite eviction on saturation."""
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        else:
            self._buffer.append(item)
            return None

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("Cannot pop from an empty ring buffer")
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
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T08:03:11Z
# LAST_CHANGED: 2026-11-10T08:02:21Z
# CHANGE: Implemented concrete RingBuffer singleton with collections.deque(maxlen=10). Properties (capacity, size, is_empty, is_full) delegate to internal state. push returns evicted item when full, pop raises BufferEmptyError when empty, clear empties buffer, snapshot_items returns list copy.
# COVERAGE_AUDIT: 2026-11-10T08:03:11Z
# QA_AUDIT: 2026-11-10T08:02:48Z
# --- END AUTOFAB METADATA ---
