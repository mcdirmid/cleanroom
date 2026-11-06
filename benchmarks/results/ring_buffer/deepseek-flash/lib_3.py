# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261106_191928_deepseek-flash_ring_buffer
# Timestamp: 2026-11-06T19:19:28.945235+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 79,979
#   Cached Inbound Tokens:   1,055,360
#   Outbound Tokens:         29,626
#   Total Tokens:            1,164,965
#   Financial Cost ($USD):   $0.0329
#   Wall Clock Duration:     202.88s
#   Step Latencies (s):      [71.0, 163.7, 10.0, 10.0]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       11
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Library interface for bounded circular ring buffer."""

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
# LAST_CLEANED: 2026-11-06T19:22:09Z
# LAST_CHANGED: 2026-11-06T19:22:09Z
# CHANGE: Formalized low/ring_buffer.pyi as interface module: @data_type BufferError/BufferEmptyError extending PretenseSpecificationError, and @poly_type RingBuffer Protocol with capacity/size/is_empty/is_full properties plus operation stubs push, pop, clear, and @test_only snapshot_items; imports use package-qualified pretense path.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Library implementation for bounded circular ring buffer."""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, List, Optional

from pretense.parts.pretense.lib.pretense import requires, test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import ring_buffer


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque."""

    tier: str = "system"

    def __init__(self) -> None:
        # GROUNDING: default capacity of 10 backed by a bounded deque(maxlen=capacity)
        # so that saturation overwrites the oldest item automatically.
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
        """Appends an item to the circular buffer with overwrite eviction on saturation."""
        # POSTCONDITION: WHEN size equals capacity, MUST evict oldest item, store the
        # new item at the most recent position, keep size at capacity, and return the
        # evicted (oldest) item.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # POSTCONDITION: WHEN size is less than capacity, MUST store item, increment
        # size by 1, and return None.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        # PRECONDITION: WHEN size equals zero, MUST raise BufferEmptyError.
        requires(not self.is_empty, ring_buffer.BufferEmptyError)
        # POSTCONDITION: WHEN size is greater than zero, MUST remove the oldest item,
        # decrement size by 1, and return the removed item.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero."""
        # POSTCONDITION: MUST remove all items and reset size to zero.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in circular FIFO arrival order."""
        # POSTCONDITION: MUST return all currently stored items in FIFO arrival order
        # without modifying buffer contents, size, capacity, or operational state.
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
# LAST_CLEANED: 2026-11-06T19:22:47Z
# LAST_CHANGED: 2026-11-06T19:22:14Z
# CHANGE: Implemented RingBuffer singleton over deque(maxlen=capacity) with capacity 10: backing _capacity/_buffer state, capacity/size/is_empty/is_full getters, push with oldest-item eviction returning the evicted item when full (else None), pop guarded by requires(not is_empty, BufferEmptyError) returning popleft(), clear, and non-destructive snapshot_items in FIFO order; declares tier system and keeps the auto-generated __initialize__ registration untouched.
# COVERAGE_AUDIT: 2026-11-06T19:22:47Z
# QA_AUDIT: 2026-11-06T19:22:35Z
# --- END AUTOFAB METADATA ---
