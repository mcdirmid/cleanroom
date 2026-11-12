# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261111_041917_deepseek-flash_ring_buffer
# Timestamp: 2026-11-11T04:19:17.874163+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 75,827
#   Cached Inbound Tokens:   1,417,600
#   Outbound Tokens:         28,668
#   Total Tokens:            1,522,095
#   Financial Cost ($USD):   $0.0328
#   Wall Clock Duration:     193.83s
#   Step Latencies (s):      [121.8, 134.4, 10.0, 20.2]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
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
# LAST_CLEANED: 2026-11-11T04:21:41Z
# LAST_CHANGED: 2026-11-11T04:21:41Z
# CHANGE: Define interface module: BufferError/BufferEmptyError data types and RingBuffer protocol with push/pop/clear/snapshot_items stubs and test_only marker.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete realization of bounded circular ring buffer."""

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
    """Concrete realization of bounded circular buffer using collections.deque."""

    tier: str = "system"

    def __init__(self) -> None:
        # GROUNDING: initializes internal capacity and deque with default capacity 10.
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=self._capacity)

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
        # POSTCONDITION overwrite_eviction: full buffer evicts the oldest item first.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # POSTCONDITION available_capacity: room available stores item and returns None.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        # PRECONDITION empty_buffer: popping an empty buffer raises BufferEmptyError.
        if self.is_empty:
            raise ring_buffer.BufferEmptyError()
        # POSTCONDITION non_empty: removes and returns the oldest item.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero."""
        # POSTCONDITION reset_size: clears all stored items so size becomes zero.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in circular FIFO arrival order."""
        # POSTCONDITION fifo_order / non_mutating: shallow copy preserves arrival order.
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
# LAST_CLEANED: 2026-11-11T04:22:20Z
# LAST_CHANGED: 2026-11-11T04:21:47Z
# CHANGE: Implement RingBuffer singleton: deque-backed storage capacity 10, push with overwrite eviction, pop raising BufferEmptyError, clear, and FIFO snapshot_items.
# COVERAGE_AUDIT: 2026-11-11T04:22:20Z
# QA_AUDIT: 2026-11-11T04:22:06Z
# --- END AUTOFAB METADATA ---
