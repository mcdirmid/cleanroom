"""Low-level interface specification for stream reader."""

from __future__ import annotations

from typing import Optional, Protocol
from pretense import PretenseSpecificationError
from support.lib.framework import data_type, operation, poly_type


@data_type
class StreamReaderError(PretenseSpecificationError):
    """Base exception for all stream reader operations."""


@poly_type
class StreamReader(Protocol):
    """Stream reader protocol for consuming sequential string payloads."""

    @property
    def unread_count(self) -> int:
        """Current number of unread payloads remaining in the stream."""
        ...

    @property
    def has_data(self) -> bool:
        """Indicates whether unread payloads remain available in the stream."""
        ...

    @operation
    def read(self) -> Optional[str]:
        """Reads and extracts the oldest unread payload from the stream.

        Returns:
            Oldest unread payload string, or None if stream is empty.

        POSTCONDITIONS:
        - [slug:stream_reader.read.pop_payload]: WHEN unread_count is greater than 0, MUST pop oldest unread item, decrement unread_count by 1, and return item.
        - [slug:stream_reader.read.empty_stream]: WHEN unread_count equals 0, MUST return None.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-11-03T23:55:00Z
# LAST_CHANGED: 2026-11-03T23:55:00Z
# CHANGE: Initial creation of stream_reader low-level specification
# SPEC_QA_AUDIT: 2026-11-03T23:55:00Z
# --- END CLEANROOM METADATA ---
