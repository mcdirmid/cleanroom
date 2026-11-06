# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261106_200439_deepseek-flash_ring_buffer
# Timestamp: 2026-11-06T20:04:39.991069+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 49,805
#   Cached Inbound Tokens:   667,392
#   Outbound Tokens:         20,811
#   Total Tokens:            738,008
#   Financial Cost ($USD):   $0.0220
#   Wall Clock Duration:     147.81s
#   Step Latencies (s):      [75.5, 91.3, 10.3, 10.4]
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
        """Appends an item to the circular buffer with overwrite eviction on saturation.

        Args:
            item: Item to store into the buffer.

        Returns:
            The evicted oldest item if the buffer was full, or None if space was available.

        POSTCONDITIONS:
        - WHEN size is less than capacity, MUST store item, increment size by 1, and return None.
        - WHEN size equals capacity, MUST evict oldest item, store new item at most recent position, maintain size at capacity, and return the evicted item.
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
        - WHEN size is greater than zero, MUST remove oldest item, decrement size by 1, and return the removed item.
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
# LAST_CLEANED: 2026-11-06T20:06:16Z
# LAST_CHANGED: 2026-11-06T20:06:16Z
# CHANGE: Implement abstract interface: BufferError/BufferEmptyError @data_type exceptions, @poly_type RingBuffer protocol with contracted capacity/size/is_empty/is_full properties and push/pop/clear/snapshot_items operations; fix cross-part pretense import to full package path.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
from __future__ import annotations
from collections import deque
from typing import Any, List, Optional
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
from . import ring_buffer
from pretense.parts.pretense.lib.pretense import requires, test_only

# Requirements specified in ring_buffer_impl.pyi


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque."""

    tier: str = "system"

    def __init__(self) -> None:
        # GROUNDING: default capacity 10 with deque bounded to that capacity.
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        """Returns the configured maximum number of items."""
        return self._capacity

    @property
    @override
    def size(self) -> int:
        """Returns the number of items currently stored."""
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        """Returns True when zero items are stored."""
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        """Returns True when the stored item count reached capacity."""
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        # POSTCONDITIONS: when size equals capacity, the oldest item is evicted and
        # returned while the new item is stored at the most recent position.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        # POSTCONDITIONS: otherwise the item is stored without eviction.
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        # PRECONDITIONS: WHEN size equals zero, MUST raise BufferEmptyError.
        requires(not self.is_empty, ring_buffer.BufferEmptyError)
        # POSTCONDITIONS: WHEN size is greater than zero, remove and return the oldest item.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        # POSTCONDITIONS: all items are removed and size resets to zero.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        # POSTCONDITIONS: return a copy in FIFO arrival order without mutating state.
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
# LAST_CLEANED: 2026-11-06T20:07:01Z
# LAST_CHANGED: 2026-11-06T20:06:21Z
# CHANGE: Implement @singleton_type RingBuffer over collections.deque(maxlen=10): capacity/size/is_empty/is_full properties, push with overwrite eviction returning evicted oldest item, pop enforcing BufferEmptyError precondition via requires, clear, and non-destructive snapshot_items; fix pretense import path.
# COVERAGE_AUDIT: 2026-11-06T20:07:01Z
# QA_AUDIT: 2026-11-06T20:06:47Z
# --- END AUTOFAB METADATA ---
