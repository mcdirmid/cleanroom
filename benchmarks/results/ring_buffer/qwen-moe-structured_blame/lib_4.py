# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261110_061529_qwen-moe_ring_buffer
# Timestamp: 2026-11-10T06:15:29.587651+00:00
# Benchmark Task: ring_buffer
# Model: qwen-moe (Tier 1)
# Methodology: autofab
# Harness: dsh
# Run Index: 4
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 61,461
#   Cached Inbound Tokens:   494,109
#   Outbound Tokens:         13,821
#   Total Tokens:            569,391
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     253.96s
#   Step Latencies (s):      [172.7, 185.1, 20.2, 20.2]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
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
# LAST_CLEANED: 2026-11-10T06:18:39Z
# LAST_CHANGED: 2026-11-10T06:18:39Z
# CHANGE: Implemented interface module with data types (BufferError, BufferEmptyError), poly_type protocol (RingBuffer), and fixed pretense import to full package path. Added framework decorators (data_type, operation, poly_type) matching low spec contracts.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    get_default_registry,
    get_singleton,
)

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
        # GROUNDING: Initialize _capacity to 10 and _buffer as deque with maxlen=10
        self._capacity: int = 10
        self._buffer: deque = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        # GROUNDING: Returns self._capacity
        return self._capacity

    @property
    @override
    def size(self) -> int:
        # GROUNDING: Returns len(self._buffer)
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        # GROUNDING: Evaluates len(self._buffer) == 0
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        # GROUNDING: Evaluates len(self._buffer) >= self._capacity
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        # GROUNDING: On overflow, captures evicted item before appending; otherwise returns None
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        else:
            self._buffer.append(item)
            return None

    @operation
    @override
    def pop(self) -> Any:
        # GROUNDING: Enforces precondition requires(not self.is_empty, ring_buffer.BufferEmptyError)
        # Then calls and returns self._buffer.popleft()
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("Cannot pop from empty ring buffer")
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        # GROUNDING: Invokes self._buffer.clear()
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        # GROUNDING: Returns a shallow list copy of self._buffer
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
# LAST_CLEANED: 2026-11-10T06:19:30Z
# LAST_CHANGED: 2026-11-10T06:18:43Z
# CHANGE: Implemented concrete RingBuffer singleton using collections.deque(maxlen=capacity). Realized all operations: push with overwrite eviction, pop with BufferEmptyError guard, clear, and snapshot_items. Added proper tier attribute, lifecycle registration, and framework decorators. Fixed pretense import to full package path.
# COVERAGE_AUDIT: 2026-11-10T06:19:30Z
# QA_AUDIT: 2026-11-10T06:19:08Z
# --- END AUTOFAB METADATA ---
