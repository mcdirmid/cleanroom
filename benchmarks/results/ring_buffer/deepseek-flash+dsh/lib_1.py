# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261104_202245_deepseek-flash_ring_buffer
# Timestamp: 2026-11-04T20:22:45.259113+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 54,777
#   Cached Inbound Tokens:   1,504,128
#   Outbound Tokens:         47,200
#   Total Tokens:            1,606,105
#   Financial Cost ($USD):   $0.0410
#   Wall Clock Duration:     249.72s
#   Step Latencies (s):      [140.7, 204.3, 10.3, 10.4]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
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
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol
from pretense.parts.pretense.lib.pretense import PretenseSpecificationError, test_only
from support.lib.framework import data_type, operation, poly_type

# Requirements specified in ring_buffer.pyi


@data_type
@dataclass
class BufferError(PretenseSpecificationError):
    """Base exception for all ring buffer operations."""

    message: str = ""

    def __str__(self) -> str:
        return self.message


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

        Raises:
            BufferEmptyError: If the circular buffer contains zero items.

        POSTCONDITIONS:
        - WHEN size is greater than zero, MUST remove oldest item, decrement size by 1,
          and return the removed item.
        - WHEN size equals zero, MUST raise BufferEmptyError.
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
# LAST_CLEANED: 2026-11-04T20:25:04Z
# LAST_CHANGED: 2026-11-04T20:25:04Z
# CHANGE: Implement ring_buffer interface: package-qualified pretense imports, mutable dataclass BufferError/BufferEmptyError with message and __str__, full RingBuffer protocol stubs for capacity/size/is_empty/is_full/push/pop/clear/snapshot_items
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
from __future__ import annotations
from collections import deque
from typing import Any, Deque, List, Optional
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
        # Grounding: bounded storage defaults to capacity 10.
        self._capacity: int = 10
        self._buffer: Deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        # Grounding: maximum items permitted in the buffer.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        # Grounding: current item count tracks backing deque length.
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        # Grounding: empty when the backing deque stores zero items.
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        # Grounding: full once the backing deque attains its capacity limit.
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        # POSTCONDITION: at capacity, evict the oldest item and return it.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # POSTCONDITION: with spare capacity, store item and return None.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        # POSTCONDITION: zero items, MUST raise BufferEmptyError.
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("Cannot pop from an empty ring buffer")
        # POSTCONDITION: remove and return the oldest item.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        # POSTCONDITION: all items removed and size reset to zero.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        # POSTCONDITION: shallow copy of active items in FIFO arrival order.
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
# LAST_CLEANED: 2026-11-04T20:26:49Z
# LAST_CHANGED: 2026-11-04T20:25:14Z
# CHANGE: Implement concrete RingBuffer singleton: deque(maxlen=10) backing state, capacity/size/is_empty/is_full properties, overflow-evicting push, BufferEmptyError-raising pop, clear, test-only snapshot_items, lifecycle registration preserved
# COVERAGE_AUDIT: 2026-11-04T20:26:49Z
# QA_AUDIT: 2026-11-04T20:26:35Z
# --- END AUTOFAB METADATA ---
