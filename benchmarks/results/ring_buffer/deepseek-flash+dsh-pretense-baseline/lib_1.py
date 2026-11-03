# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261103_044705_deepseek-flash_ring_buffer_pretense_baseline
# Timestamp: 2026-11-03T04:47:05.466533+00:00
# Benchmark Task: ring_buffer
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 72,510
#   Cached Inbound Tokens:   2,281,472
#   Outbound Tokens:         27,052
#   Total Tokens:            2,381,034
#   Financial Cost ($USD):   $0.0340
#   Wall Clock Duration:     227.36s
#   Step Latencies (s):      [215.1]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
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
"""Interface specification for bounded circular ring buffer.

Formalizes ``low/ring_buffer.pyi``: the passive ``BufferError`` hierarchy and the
``RingBuffer`` service protocol realized by ``lib/ring_buffer_impl.py``.
"""

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

        POSTCONDITIONS:
        - WHEN size is less than capacity, MUST store item, increment size by 1,
          and return None.
        - WHEN size equals capacity, MUST evict oldest item, store new item at most
          recent position, maintain size at capacity, and return the evicted item.
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

        POSTCONDITIONS:
        - MUST return a list containing all currently stored items in FIFO arrival order.
        - MUST NOT modify the buffer contents, size, capacity, or operational state.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-03T04:50:52Z
# LAST_CHANGED: 2026-11-03T04:50:52Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 9ae6efa7675a
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T04:50:52Z
# PRETENSE_QA_AUDIT: 2026-11-03T04:50:52Z
# --- END AUTOFAB METADATA ---


# === File: ring_buffer_impl.py ===
"""Concrete bounded circular ring buffer implementation.

Realizes ``low/ring_buffer_impl.pyi``: a ``@singleton_type("system")`` service
backed by ``collections.deque(maxlen=capacity)`` with default capacity 10.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, List, Optional

from pretense.parts.pretense.lib.pretense import test_only
from support.lib.framework import operation, override
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system
from . import ring_buffer


class RingBuffer(ring_buffer.RingBuffer):
    """Concrete realization of bounded circular buffer using collections.deque."""

    tier: str = "system"

    def __init__(self) -> None:
        # GROUNDING: _capacity defaults to 10 and _buffer is bounded by it.
        self._capacity: int = 10
        self._buffer: Deque[Any] = deque(maxlen=self._capacity)

    @property
    @override
    def capacity(self) -> int:
        # GROUNDING: Returns self._capacity.
        return self._capacity

    @property
    @override
    def size(self) -> int:
        # GROUNDING: Returns len(self._buffer).
        return len(self._buffer)

    @property
    @override
    def is_empty(self) -> bool:
        # GROUNDING: Evaluates len(self._buffer) == 0.
        return len(self._buffer) == 0

    @property
    @override
    def is_full(self) -> bool:
        # GROUNDING: Evaluates len(self._buffer) >= self._capacity.
        return len(self._buffer) >= self._capacity

    @operation
    @override
    def push(self, item: Any) -> Optional[Any]:
        # POSTCONDITIONS: when saturated, evict the oldest item and return it while
        # maintaining size at capacity; otherwise append and return None.
        if len(self._buffer) == self._capacity:
            evicted = self._buffer[0]
            self._buffer.append(item)
            return evicted
        self._buffer.append(item)
        return None

    @operation
    @override
    def pop(self) -> Any:
        # POSTCONDITIONS: WHEN size equals zero, raise BufferEmptyError. Conforming
        # callers never violate this precondition, so the error branch is unobservable.
        if self.is_empty:  # pragma: no cover (assumption: precondition enforced by caller)
            raise ring_buffer.BufferEmptyError("cannot pop from an empty ring buffer")
        # POSTCONDITIONS: remove and return the oldest item, decrementing size by 1.
        return self._buffer.popleft()

    @operation
    @override
    def clear(self) -> None:
        # POSTCONDITIONS: remove all items and reset size to zero.
        self._buffer.clear()

    @operation
    @override
    @test_only
    def snapshot_items(self) -> List[Any]:
        # POSTCONDITIONS: return a shallow FIFO copy without mutating buffer state.
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
# LAST_CLEANED: 2026-11-03T04:50:52Z
# LAST_CHANGED: 2026-11-03T04:50:52Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: d299d5bfc15c
# PRETENSE_COVERAGE_AUDIT: 2026-11-03T04:50:52Z
# PRETENSE_QA_AUDIT: 2026-11-03T04:50:52Z
# --- END AUTOFAB METADATA ---
