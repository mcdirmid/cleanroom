# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261110_192746_deepseek-flash_ring_buffer_pretense
# Timestamp: 2026-11-10T19:27:46.717111+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 91,105
#   Cached Inbound Tokens:   2,200,832
#   Outbound Tokens:         56,634
#   Total Tokens:            2,348,571
#   Financial Cost ($USD):   $0.0542
#   Wall Clock Duration:     411.69s
#   Step Latencies (s):      [103.9, 276.6, 20.3, 52.8, 40.5, 10.1]
#   Role Execution Rounds:   lib: 2, pretense: 1, pretense_coverage: 2, pretense_qa: 1 (Total: 6)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: ring_buffer.py ===
"""Interface specification for a bounded circular ring buffer."""

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
        """Appends an item with overwrite eviction on saturation."""
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
        """Returns non-destructive snapshot of active items in FIFO arrival order."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T19:34:12Z
# LAST_CHANGED: 2026-11-10T19:34:12Z
# CHANGE: Resolve pretense_coverage feedback: removed unsanctioned, uncoverable BufferError.__str__ exception string rendering; exception data_types now match the specification exactly with no uncontracted members, so pop's BufferEmptyError raise path is reachable and fully contracted.
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete implementation of a bounded circular ring buffer."""

from __future__ import annotations

from collections import deque
from typing import Any, List, Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import ring_buffer


@singleton_type("system")
class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque."""

    tier: str = "system"

    def __init__(self) -> None:
        # GROUNDING: default capacity of 10 backed by a bounded deque.
        self._capacity: int = 10
        self._buffer: deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        """Maximum number of items permitted in the circular buffer."""
        # GROUNDING: exposes the configured capacity.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        """Current number of items stored in the circular buffer."""
        # GROUNDING: number of items currently retained by the deque.
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        """Indicates whether the circular buffer contains zero items."""
        # GROUNDING: true when the buffer holds no items.
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        """Indicates whether the circular buffer has reached its capacity limit."""
        # GROUNDING: true once the buffer has reached the capacity limit.
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        """Appends an item with overwrite eviction on saturation."""
        # POSTCONDITIONS: available capacity stores the item and returns None.
        if len(self._buffer) < self._capacity:
            self._buffer.append(item)
            return None
        # POSTCONDITIONS: saturation evicts the oldest item, which is returned.
        evicted = self._buffer[0]
        self._buffer.append(item)
        return evicted

    @operation
    @override
    def pop(self) -> Any:
        """Removes and returns the oldest item from the circular buffer."""
        # PRECONDITIONS: popping an empty buffer raises BufferEmptyError.
        if self.is_empty:
            raise ring_buffer.BufferEmptyError()
        # POSTCONDITIONS: remove and return the oldest item.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero."""
        # POSTCONDITIONS: drop every item, leaving size at zero.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in FIFO arrival order."""
        # POSTCONDITIONS: shallow copy in oldest-to-newest order without mutation.
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
# LAST_CLEANED: 2026-11-10T19:34:34Z
# LAST_CHANGED: 2026-11-10T19:29:46Z
# CHANGE: Implement singleton RingBuffer on collections.deque(maxlen=10): capacity/size/is_empty/is_full properties, push with overwrite eviction returning evicted item, pop raising BufferEmptyError when empty, clear, and snapshot_items FIFO copy.
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T19:34:34Z
# PRETENSE_QA_AUDIT: 2026-11-10T19:32:48Z
# --- END AUTOFAB METADATA ---
