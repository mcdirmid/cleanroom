# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_231536_gemini-flash-lite_ring_buffer_pretense
# Timestamp: 2026-11-08T23:15:36.182276+00:00
# Benchmark Task: ring_buffer
# Model: gemini-flash-lite (Tier 1)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 1,203,142
#   Cached Inbound Tokens:   7,486,149
#   Outbound Tokens:         49,945
#   Total Tokens:            8,739,236
#   Financial Cost ($USD):   $0.2456
#   Wall Clock Duration:     573.89s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 7, pretense: 6, pretense_coverage: 12, pretense_qa: 12 (Total: 37)
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
"""Bounded circular ring buffer interface."""

from __future__ import annotations

from typing import Any, List, Optional, Protocol
from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type


@data_type
class BufferError(PretenseSpecificationError):
    """Base exception for all ring buffer operations."""

    def __str__(self) -> str:
        msg = getattr(self, "message", None)
        return str(msg) if msg is not None else super().__str__()


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
# LAST_CLEANED: 2026-11-08T23:22:49Z
# LAST_CHANGED: 2026-11-08T23:17:06Z
# CHANGE: Implemented ring_buffer interface protocol and exceptions
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete realization of bounded circular ring buffer."""

from __future__ import annotations

from support.lib.lifecycle import LifecycleRegistry, get_default_registry
from typing import Any, List, Optional
from collections import deque
from support.lib.framework import operation, override, singleton_type
from pretense.parts.pretense.lib.pretense import test_only
from . import ring_buffer


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque."""

    tier: str = "system"

    def __init__(self, capacity: int = 10) -> None:
        self._capacity = capacity
        self._buffer: deque[Any] = deque(maxlen=capacity)

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
        evicted = None
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
        self._buffer.append(item)
        return evicted

    @operation
    @override
    def pop(self) -> Any:
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("Buffer is empty")
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
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
# LAST_CLEANED: 2026-11-08T23:25:05Z
# LAST_CHANGED: 2026-11-08T23:21:16Z
# CHANGE: Removed pragma no cover on eviction line as requested by feedback
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T23:25:05Z
# PRETENSE_QA_AUDIT: 2026-11-08T23:24:54Z
# --- END AUTOFAB METADATA ---
