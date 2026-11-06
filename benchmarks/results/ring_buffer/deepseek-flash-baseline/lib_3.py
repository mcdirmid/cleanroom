# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261106_200448_deepseek-flash_ring_buffer_baseline
# Timestamp: 2026-11-06T20:04:48.616885+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: baseline
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 37,285
#   Cached Inbound Tokens:   905,856
#   Outbound Tokens:         17,202
#   Total Tokens:            960,343
#   Financial Cost ($USD):   $0.0186
#   Wall Clock Duration:     130.61s
#   Step Latencies (s):      [120.8]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       8
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Bounded circular ring buffer interface specification."""

from __future__ import annotations

from typing import Any, List, Optional, Protocol

from pretense.parts.pretense.lib.pretense import (
    PretenseSpecificationError,
    test_only,
)
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

        Returns the evicted oldest item if the buffer was full, or None if space was available.
        """
        ...

    @operation
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer.

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
        """Returns non-destructive snapshot of active items in circular FIFO arrival order."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T20:06:59Z
# LAST_CHANGED: 2026-11-06T20:06:59Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: f7f0a1b47c0a
# COVERAGE_AUDIT: 2026-11-06T20:06:59Z
# QA_AUDIT: 2026-11-06T20:06:59Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Bounded circular ring buffer implementation."""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

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
        # Initializes internal bounded storage: _capacity of 10 and
        # _buffer to collections.deque(maxlen=10).
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        """Maximum number of items permitted in the circular buffer."""
        # GROUNDING: Returns self._capacity.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        """Current number of items stored in the circular buffer."""
        # GROUNDING: Returns len(self._buffer).
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        """Indicates whether the circular buffer contains zero items."""
        # GROUNDING: Evaluates len(self._buffer) == 0.
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        """Indicates whether the circular buffer has reached its capacity limit."""
        # GROUNDING: Evaluates len(self._buffer) >= self._capacity.
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item to the circular buffer with overwrite eviction on saturation."""
        # POSTCONDITION: WHEN size equals capacity, MUST evict oldest item, store
        # new item at most recent position, maintain size at capacity, and return
        # the evicted item.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # POSTCONDITION: WHEN size is less than capacity, MUST store item,
        # increment size by 1, and return None.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        # PRECONDITION: WHEN size equals zero, MUST raise BufferEmptyError.
        if self.is_empty:
            raise ring_buffer.BufferEmptyError()
        # POSTCONDITION: WHEN size is greater than zero, MUST remove oldest item,
        # decrement size by 1, and return the removed item.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero."""
        # POSTCONDITION: MUST remove all items from the buffer and reset size to zero.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in circular FIFO arrival order."""
        # POSTCONDITION: MUST return a list containing all currently stored items in
        # FIFO arrival order without modifying buffer contents or state.
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
# LAST_CLEANED: 2026-11-06T20:06:59Z
# LAST_CHANGED: 2026-11-06T20:06:59Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 0cf420571046
# COVERAGE_AUDIT: 2026-11-06T20:06:59Z
# QA_AUDIT: 2026-11-06T20:06:59Z
# --- END AUTOFAB METADATA ---
