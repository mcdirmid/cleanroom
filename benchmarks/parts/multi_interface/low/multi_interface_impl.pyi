"""Low-level implementation specification for consolidated stream buffer."""

from __future__ import annotations

from typing import Optional
from support.lib.framework import operation, override, singleton_type
import stream_reader
import stream_writer


@singleton_type("system")
class StreamBuffer(stream_reader.StreamReader, stream_writer.StreamWriter):
    """Concrete realization of stream buffer implementing both reader and writer protocols.

    GROUNDING:
    - Realizes unified in-memory FIFO stream buffer.
    - Initializes _items to list() and _written_count to 0.
    """

    tier: str = "system"

    @property
    @override
    def unread_count(self) -> int:
        """Current number of unread payloads remaining in the buffer.

        GROUNDING:
        - Returns len(self._items).
        """
        ...

    @property
    @override
    def has_data(self) -> bool:
        """Indicates whether unread payloads remain available in the buffer.

        GROUNDING:
        - Returns len(self._items) > 0.
        """
        ...

    @property
    @override
    def written_count(self) -> int:
        """Cumulative count of payloads written to the buffer.

        GROUNDING:
        - Returns self._written_count.
        """
        ...

    @operation
    @override
    def read(self) -> Optional[str]:
        """Reads and extracts the oldest unread payload from the buffer.

        Returns:
            Oldest unread payload string, or None if buffer is empty.

        GROUNDING:
        - Pops and returns self._items[0] if self._items is non-empty, otherwise returns None.
        """
        ...

    @operation
    @override
    def write(self, payload: str) -> None:
        """Writes a string payload to the buffer.

        Args:
            payload: Non-empty string payload to write.

        Raises:
            stream_writer.PayloadEmptyError: If payload is empty.

        GROUNDING:
        - Validates len(payload) > 0, raising stream_writer.PayloadEmptyError otherwise.
        - Appends payload to self._items.
        - Increments self._written_count by 1.
        """
        ...

    @operation
    @override
    def clear(self) -> None:
        """Purges all buffered payloads and resets written count to zero.

        GROUNDING:
        - Clears self._items.
        - Resets self._written_count to 0.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-11-03T23:55:00Z
# LAST_CHANGED: 2026-11-03T23:55:00Z
# CHANGE: Initial creation of multi_interface_impl low-level specification
# SPEC_QA_AUDIT: 2026-11-03T23:55:00Z
# --- END CLEANROOM METADATA ---
