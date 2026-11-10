# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261110_055146_qwen-moe_ring_buffer
# Timestamp: 2026-11-10T05:51:46.863021+00:00
# Benchmark Task: ring_buffer
# Model: qwen-moe (Tier 1)
# Methodology: autofab
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 127,860
#   Cached Inbound Tokens:   1,405,318
#   Outbound Tokens:         16,845
#   Total Tokens:            1,550,023
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     402.00s
#   Step Latencies (s):      [205.6, 203.1, 60.8, 60.7, 20.2, 20.2]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 2, test: 2 (Total: 6)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       20
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


# Requirements specified in ring_buffer.pyi


@data_type
class BufferError(PretenseSpecificationError):
    # TODO_BufferError_body
    pass


@data_type
class BufferEmptyError(BufferError):
    # TODO_BufferEmptyError_body
    pass


@poly_type
class RingBuffer(Protocol):
    @property
    def capacity(self) -> int:
        # TODO_capacity_body
        ...

    @property
    def size(self) -> int:
        # TODO_size_body
        ...

    @property
    def is_empty(self) -> bool:
        # TODO_is_empty_body
        ...

    @property
    def is_full(self) -> bool:
        # TODO_is_full_body
        ...

    @operation
    def push(self, item: Any) -> Optional[Any]:
        # TODO_push_body
        ...

    @operation
    def pop(self) -> Any:
        # TODO_pop_body
        ...

    @operation
    def clear(self) -> None:
        # TODO_clear_body
        ...

    @operation
    @test_only
    def snapshot_items(self) -> List[Any]:
        # TODO_snapshot_items_body
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T05:55:13Z
# LAST_CHANGED: 2026-11-10T05:55:13Z
# CHANGE: Implemented ring_buffer interface module: added @data_type/@poly_type decorators, fixed pretense import to full package path, added @operation/@test_only decorators, completed RingBuffer Protocol stubs with correct signatures from low/ring_buffer.pyi.
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
    system,
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
        # GROUNDING: If full, capture oldest item, append new item, return evicted
        # Otherwise append new item and return None.
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
        # Enforces precondition: buffer must not be empty
        if self.is_empty:
            raise ring_buffer.BufferEmptyError("Cannot pop from empty ring buffer")
        # Otherwise returns the oldest item via popleft
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
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T05:58:15Z
# LAST_CHANGED: 2026-11-10T05:55:18Z
# CHANGE: Implemented ring_buffer_impl concrete class: fixed pretense import, resolved all TODO stubs, implemented RingBuffer using collections.deque(maxlen=10) with proper push/pop/clear/snapshot_items per low/ring_buffer_impl.pyi spec.
# COVERAGE_AUDIT: 2026-11-10T05:58:15Z
# QA_AUDIT: 2026-11-10T05:57:53Z
# --- END AUTOFAB METADATA ---
