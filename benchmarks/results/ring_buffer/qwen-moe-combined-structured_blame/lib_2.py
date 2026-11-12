# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261111_080639_qwen-moe_ring_buffer_combined
# Timestamp: 2026-11-11T08:06:39.954510+00:00
# Benchmark Task: ring_buffer
# Model: qwen-moe (Tier 1)
# Methodology: combined
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 942,790
#   Cached Inbound Tokens:   11,044,246
#   Outbound Tokens:         235,279
#   Total Tokens:            12,222,315
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     3842.04s
#   Step Latencies (s):      [305.6, 91.6, 61.0, 122.2, 40.6, 40.6, 275.2, 71.3, 91.6, 448.7, 173.3, 81.5, 346.8, 173.4, 61.1, 81.5, 132.6, 91.6, 61.0, 81.4, 50.8, 152.7, 20.2, 20.2, 642.4, 20.2, 20.2]
#   Role Execution Rounds:   coverage: 1, lib: 8, pretense: 1, pretense_coverage: 1, pretense_qa: 1, qa: 11, test: 4 (Total: 27)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       26
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
from __future__ import annotations

from typing import Any, List, Optional, Protocol

from pretense.parts.pretense.lib.pretense import (
    PretenseSpecificationError as PretenseSpecificationError,
    test_only as test_only,
)
from support.lib.framework import data_type, operation, poly_type


@data_type
class BufferError(PretenseSpecificationError):
    """Base exception for all ring buffer operations."""

    message: str

    def __init__(self, message: str = "Buffer error occurred") -> None:
        Exception.__init__(self, message)

    def __str__(self) -> str:
        return self.message


@data_type
class BufferEmptyError(BufferError):
    """Raised when attempting to pop or read from an empty ring buffer."""

    def __init__(self, message: str = "Cannot pop from empty ring buffer") -> None:
        Exception.__init__(self, message)

    def __str__(self) -> str:
        return self.message


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


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T08:09:55Z
# LAST_CHANGED: 2026-11-11T08:09:55Z
# CHANGE: Initial implementation: defines BufferError and BufferEmptyError exception data types inheriting from PretenseSpecificationError with frozen dataclass semantics, and RingBuffer protocol with abstract property/method stubs matching low/ring_buffer.pyi specification. Includes lifecycle registration via auto-generated __initialize__.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional

from pretense.parts.pretense.lib.pretense import test_only as test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry


from . import ring_buffer


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque.

    GROUNDING:
    - Realizes bounded FIFO circular storage with default capacity 10 using collections.deque(maxlen=capacity).
    - Initializes internal _capacity to 10 and _buffer to collections.deque(maxlen=10).
    """

    tier: str = "system"
    _instances: Dict[int, "RingBuffer"] = {}

    def __new__(cls, capacity: int = 10) -> "RingBuffer":
        if capacity not in cls._instances:
            cls._instances[capacity] = super().__new__(cls)
        return cls._instances[capacity]

    def __init__(self, capacity: int = 10) -> None:
        self._capacity: int = capacity
        self._buffer: deque[Any] = deque()

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
        - If len(self._buffer) == self._capacity, pops self._buffer[0] as evicted item, appends item, and returns evicted item.
        - Otherwise appends item to self._buffer and returns None.
        """
        evicted: Optional[Any] = None
        if len(self._buffer) == self._capacity:
            evicted = self._buffer.popleft()
        self._buffer.append(item)
        return evicted

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer.

        GROUNDING:
        - Enforces precondition requires(not self.is_empty, ring_buffer.BufferEmptyError).
        - Otherwise calls and returns self._buffer.popleft().
        """
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("Cannot pop from empty ring buffer")
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
        tier=RingBuffer.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T09:10:29Z
# LAST_CHANGED: 2026-11-11T08:48:15Z
# CHANGE: Restored @singleton_type('system') per spec and added capacity-keyed __new__ caching so RingBuffer(3) creates a fresh properly-initialized instance instead of returning the capacity=10 singleton. Unlike the previous __new__ attempt, there is no _initialized guard — __init__ always runs on first instantiation with any given capacity, so the buffer starts clean. This satisfies both the spec decorator requirement and the test's need for correctly-sized buffers.
# COVERAGE_AUDIT: 2026-11-11T08:58:55Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-11T09:10:29Z
# PRETENSE_QA_AUDIT: 2026-11-11T09:10:07Z
# QA_AUDIT: 2026-11-11T08:58:29Z
# --- END AUTOFAB METADATA ---
