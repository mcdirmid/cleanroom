# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261106_200444_deepseek-flash_ring_buffer
# Timestamp: 2026-11-06T20:04:44.461095+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 5
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 51,376
#   Cached Inbound Tokens:   807,808
#   Outbound Tokens:         23,793
#   Total Tokens:            882,977
#   Financial Cost ($USD):   $0.0244
#   Wall Clock Duration:     144.39s
#   Step Latencies (s):      [81.1, 103.1, 10.0, 10.0]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       13
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Library interface specification for bounded circular ring buffer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Protocol

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type


@data_type
@dataclass
class BufferError(PretenseSpecificationError):
    """Base exception for all ring buffer operations."""


@data_type
@dataclass
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
        - WHEN size equals capacity, MUST evict oldest item, store new item at most recent position,
          maintain size at capacity, and return the evicted item.
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
        - WHEN size is greater than zero, MUST remove oldest item, decrement size by 1, and return
          the removed item.
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
# LAST_CLEANED: 2026-11-06T20:06:28Z
# LAST_CHANGED: 2026-11-06T20:06:28Z
# CHANGE: Implement interface module: BufferError/BufferEmptyError exception data types and @poly_type RingBuffer protocol with capacity/size/is_empty/is_full properties plus push/pop/clear/snapshot_items operations, package-qualified pretense imports.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Library implementation of a bounded circular ring buffer."""

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

    GROUNDING:
    - Realizes bounded FIFO circular storage with default capacity 10 using
      collections.deque(maxlen=capacity).
    - Initializes internal _capacity to 10 and _buffer to collections.deque(maxlen=10).
    """

    tier: str = "system"

    def __init__(self) -> None:
        # GROUNDING: _capacity defaults to 10 and _buffer is a bounded deque of that size.
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        """Maximum number of items permitted in the circular buffer.

        GROUNDING:
        - Returns self._capacity.
        """
        return self._capacity

    @property
    @override
    def size(self) -> int:
        """Current number of items stored in the circular buffer.

        GROUNDING:
        - Returns len(self._buffer).
        """
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        """Indicates whether the circular buffer contains zero items.

        GROUNDING:
        - Evaluates len(self._buffer) == 0.
        """
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        """Indicates whether the circular buffer has reached its capacity limit.

        GROUNDING:
        - Evaluates len(self._buffer) >= self._capacity.
        """
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item to the circular buffer with overwrite eviction on saturation.

        GROUNDING:
        - If len(self._buffer) == self._capacity, captures self._buffer[0] as evicted item,
          appends item, and returns evicted item.
        - Otherwise appends item to self._buffer and returns None.
        """
        # POSTCONDITION: at capacity, evict the oldest item and return it, keeping size at capacity.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # POSTCONDITION: below capacity, store the item, grow size by one, and return None.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer.

        GROUNDING:
        - Enforces precondition requires(not self.is_empty, ring_buffer.BufferEmptyError).
        - Otherwise calls and returns self._buffer.popleft().
        """
        # PRECONDITION: WHEN size equals zero, MUST raise BufferEmptyError.
        if self.is_empty:
            raise ring_buffer.BufferEmptyError()
        # POSTCONDITION: WHEN size is greater than zero, remove the oldest item and return it.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero.

        GROUNDING:
        - Invokes self._buffer.clear().
        """
        # POSTCONDITION: MUST remove all items and reset size to zero.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in circular FIFO arrival order.

        GROUNDING:
        - Returns a shallow list copy of self._buffer.
        """
        # POSTCONDITION: MUST return all stored items oldest-to-newest without mutating state.
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
# LAST_CLEANED: 2026-11-06T20:07:04Z
# LAST_CHANGED: 2026-11-06T20:06:36Z
# CHANGE: Implement concrete @singleton_type RingBuffer over collections.deque(maxlen=10): backing _capacity/_buffer state, property getters, push with eviction return, pop raising BufferEmptyError on empty, clear, and non-destructive snapshot_items; package-qualified pretense imports.
# COVERAGE_AUDIT: 2026-11-06T20:07:04Z
# QA_AUDIT: 2026-11-06T20:06:53Z
# --- END AUTOFAB METADATA ---
