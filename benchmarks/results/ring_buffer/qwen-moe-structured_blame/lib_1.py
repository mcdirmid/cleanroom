# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261110_052235_qwen-moe_ring_buffer
# Timestamp: 2026-11-10T05:22:35.504939+00:00
# Benchmark Task: ring_buffer
# Model: qwen-moe (Tier 1)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 70,962
#   Cached Inbound Tokens:   822,847
#   Outbound Tokens:         15,676
#   Total Tokens:            909,485
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     285.85s
#   Step Latencies (s):      [154.7, 172.7, 40.5, 20.2, 20.2]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 2 (Total: 5)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       19
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
from __future__ import annotations

from typing import Any, List, Optional, Protocol

from dataclasses import dataclass

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
# LAST_CLEANED: 2026-11-10T05:25:02Z
# LAST_CHANGED: 2026-11-10T05:25:02Z
# CHANGE: Implement interface module: data_type-decorated BufferError/BufferEmptyError exceptions, poly_type-decorated RingBuffer Protocol with typed stubs matching low/ring_buffer.pyi. Fixed pretense import path to full package qualified import.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton, system
from support.lib.framework import operation, override, singleton_type
from pretense.parts.pretense.lib.pretense import test_only
from . import ring_buffer


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque.

    GROUNDING:
    - Realizes bounded FIFO circular storage with default capacity 10 using collections.deque(maxlen=capacity).
    - Initializes internal _capacity to 10 and _buffer to collections.deque(maxlen=10).
    """

    tier: str = "system"

    def __init__(self) -> None:
        # GROUNDING: Initialize with default capacity 10 and empty deque
        self._capacity: int = 10
        self._buffer: deque = deque(maxlen=self._capacity)

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
        - If len(self._buffer) == self._capacity, captures self._buffer[0] as evicted item, appends item, and returns evicted item.
        - Otherwise appends item to self._buffer and returns None.
        """
        if self.size == self._capacity:
            # Postcondition: overwrite_eviction - buffer is full, evict oldest
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        else:
            # Postcondition: available_capacity - space available, store and return None
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
        # Precondition: empty_buffer - MUST raise BufferEmptyError when size is zero
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("Cannot pop from empty ring buffer")
        # Postcondition: non_empty - remove oldest, decrement size, return it
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero.

        GROUNDING:
        - Invokes self._buffer.clear().
        """
        # Postcondition: reset_size - remove all items and reset size to zero
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in circular FIFO arrival order.

        GROUNDING:
        - Returns a shallow list copy of self._buffer.
        """
        # Postcondition: fifo_order - return items in FIFO arrival order
        # Postcondition: non_mutating - do not modify buffer contents
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
# LAST_CLEANED: 2026-11-10T05:27:09Z
# LAST_CHANGED: 2026-11-10T05:25:06Z
# CHANGE: Implement concrete RingBuffer singleton: uses collections.deque(maxlen=capacity) with default capacity 10. Realizes push (overwrite eviction), pop (BufferEmptyError on empty), clear, and snapshot_items. Registers singleton via __initialize__ under auto-generated block.
# COVERAGE_AUDIT: 2026-11-10T05:27:09Z
# QA_AUDIT: 2026-11-10T05:26:46Z
# --- END AUTOFAB METADATA ---
