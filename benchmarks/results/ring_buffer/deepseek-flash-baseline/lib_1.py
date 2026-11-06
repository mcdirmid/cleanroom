# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261106_184159_deepseek-flash_ring_buffer_baseline
# Timestamp: 2026-11-06T18:41:59.944340+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 34,017
#   Cached Inbound Tokens:   1,184,000
#   Outbound Tokens:         17,342
#   Total Tokens:            1,235,359
#   Financial Cost ($USD):   $0.0191
#   Wall Clock Duration:     138.97s
#   Step Latencies (s):      [130.8]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       7
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Interface module for bounded circular ring buffer.

Realizes the abstract protocol, data types, and error hierarchy declared in
``low/ring_buffer.pyi``. This module contains no concrete state or behavior:
the polymorphic ``RingBuffer`` protocol is purely abstract, and the error
records carry no additional fields.
"""

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

        POSTCONDITIONS:
        - WHEN size is less than capacity, MUST store item, increment size by 1,
          and return None.
        - WHEN size equals capacity, MUST evict oldest item, store new item at most
          recent position, maintain size at capacity, and return the evicted item.
        """
        ...

    @operation
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer.

        Raises:
            BufferEmptyError: If the circular buffer contains zero items.

        PRECONDITIONS:
        - WHEN size equals zero, MUST raise BufferEmptyError.

        POSTCONDITIONS:
        - WHEN size is greater than zero, MUST remove oldest item, decrement size
          by 1, and return the removed item.
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

        POSTCONDITIONS:
        - MUST return a list containing all currently stored items in FIFO arrival order.
        - MUST NOT modify the buffer contents, size, capacity, or operational state.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-06T18:44:18Z
# LAST_CHANGED: 2026-11-06T18:44:18Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: ad97a9040049
# COVERAGE_AUDIT: 2026-11-06T18:44:18Z
# QA_AUDIT: 2026-11-06T18:44:18Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete realization of the bounded circular ring buffer.

Implements ``low/ring_buffer_impl.pyi`` as a system-tier singleton backed by
``collections.deque(maxlen=capacity)``, which supplies overwrite eviction of
the oldest item once the configured capacity is saturated.
"""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense.parts.pretense.lib.pretense import requires, test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import ring_buffer


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque."""

    tier: str = "system"

    def __init__(self) -> None:
        # Grounding: default capacity of 10 realized as a bounded deque.
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        # Postcondition: expose the maximum number of items permitted.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        # Postcondition: expose the current number of stored items.
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        # Postcondition: buffer contains zero items exactly when its length is 0.
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        # Postcondition: saturation reached once the length meets capacity.
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        # WHEN size equals capacity, MUST evict the oldest item and return it.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # WHEN size is less than capacity, MUST store item and return None.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        # PRECONDITION: WHEN size equals zero, MUST raise BufferEmptyError.
        requires(not self.is_empty, ring_buffer.BufferEmptyError)
        # Postcondition: remove and return the oldest item, decrementing size.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        # Postcondition: remove all items, resetting size to zero.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        # Postcondition: non-destructive FIFO-ordered snapshot of active items.
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
# LAST_CLEANED: 2026-11-06T18:44:18Z
# LAST_CHANGED: 2026-11-06T18:44:18Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 6bf67775d251
# COVERAGE_AUDIT: 2026-11-06T18:44:18Z
# QA_AUDIT: 2026-11-06T18:44:18Z
# --- END AUTOFAB METADATA ---
