"""Low-level interface specification for bounded circular ring buffer."""

from __future__ import annotations

from typing import Any, List, Optional, Protocol
from pretense import PretenseSpecificationError, test_only
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

        Args:
            item: Item to store into the buffer.

        Returns:
            The evicted oldest item if the buffer was full, or None if space was available.

        POSTCONDITIONS:
        - [slug:ring_buffer.push.available_capacity]: WHEN size is less than capacity, MUST store item, increment size by 1, and return None.
        - [slug:ring_buffer.push.overwrite_eviction]: WHEN size equals capacity, MUST evict oldest item, store new item at most recent position, maintain size at capacity, and return the evicted item.
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
        - [slug:ring_buffer.pop.empty_buffer]: WHEN size equals zero, MUST raise BufferEmptyError.

        POSTCONDITIONS:
        - [slug:ring_buffer.pop.non_empty]: WHEN size is greater than zero, MUST remove oldest item, decrement size by 1, and return the removed item.
        """
        ...

    @operation
    def clear(self) -> None:
        """Removes all items from the circular buffer, resetting size to zero.

        POSTCONDITIONS:
        - [slug:ring_buffer.clear.reset_size]: MUST remove all items from the buffer and reset size to zero.
        """
        ...

    @operation
    @test_only
    def snapshot_items(self) -> List[Any]:
        """Returns non-destructive snapshot of active items in circular FIFO arrival order.

        Returns:
            List containing active items ordered from oldest to newest arrival.

        POSTCONDITIONS:
        - [slug:ring_buffer.snapshot.fifo_order]: MUST return a list containing all currently stored items in FIFO arrival order.
        - [slug:ring_buffer.snapshot.non_mutating]: MUST NOT modify the buffer contents, size, capacity, or operational state.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-30T19:25:00Z
# LAST_CHANGED: 2026-11-02T19:50:00Z
# CHANGE: Add snapshot_items @test_only observability query to RingBuffer
# CODE_HASH: 000000000000
# SPEC_QA_AUDIT: 2026-10-30T19:25:00Z
# --- END CLEANROOM METADATA ---
