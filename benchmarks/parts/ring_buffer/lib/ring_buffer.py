from __future__ import annotations

from typing import Any, Optional, Protocol

from pretense import PretenseSpecificationError
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
