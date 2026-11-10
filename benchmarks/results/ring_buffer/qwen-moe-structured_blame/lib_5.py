# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261110_063953_qwen-moe_ring_buffer
# Timestamp: 2026-11-10T06:39:53.397245+00:00
# Benchmark Task: ring_buffer
# Model: qwen-moe (Tier 1)
# Methodology: autofab
# Harness: dsh
# Run Index: 5
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 83,896
#   Cached Inbound Tokens:   1,260,207
#   Outbound Tokens:         19,929
#   Total Tokens:            1,364,032
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     359.27s
#   Step Latencies (s):      [162.5, 185.1, 73.3, 40.5, 20.2, 20.2]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 2, test: 2 (Total: 6)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       17
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


# Requirements specified in ring_buffer.pyi

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
# LAST_CLEANED: 2026-11-10T06:43:01Z
# LAST_CHANGED: 2026-11-10T06:43:01Z
# CHANGE: Implemented interface module: added @data_type decorators for BufferError/BufferEmptyError, @poly_type for RingBuffer Protocol, @operation/@test_only decorators on methods, all stub bodies with '...'. Fixed pretense import to use full package path.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, get_singleton
from . import ring_buffer


# Requirements specified in ring_buffer_impl.pyi

@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque.

    GROUNDING:
    - Realizes bounded FIFO circular storage with default capacity 10 using collections.deque(maxlen=capacity).
    - Initializes internal _capacity to 10 and _buffer to collections.deque(maxlen=10).
    """

    tier: str = "system"

    def __init__(self) -> None:
        # GROUNDING: Initialize private backing state with default capacity 10
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
        if len(self._buffer) == self._capacity:
            # Buffer is full, evict oldest item before storing new one
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        else:
            # Space available, store item and return None
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
        # Precondition check: raise on empty buffer
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("Cannot pop from an empty ring buffer")
        # Remove and return oldest item
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero.

        GROUNDING:
        - Invokes self._buffer.clear().
        """
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in circular FIFO arrival order.

        GROUNDING:
        - Returns a shallow list copy of self._buffer.
        """
        return list(self._buffer)


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        RingBuffer,
        keys=[RingBuffer, ring_buffer.RingBuffer],
        tier='system',
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T06:45:40Z
# LAST_CHANGED: 2026-11-10T06:43:08Z
# CHANGE: Implemented concrete RingBuffer singleton using collections.deque(maxlen=capacity) with default capacity 10. Realized push with overwrite eviction (returns evicted item when full), pop with BufferEmptyError on empty, clear, and snapshot_items. Added @singleton_type/@override/@operation/@test_only decorators, fixed pretense import, removed contract slug references from comments.
# COVERAGE_AUDIT: 2026-11-10T06:45:40Z
# QA_AUDIT: 2026-11-10T06:45:17Z
# --- END AUTOFAB METADATA ---
