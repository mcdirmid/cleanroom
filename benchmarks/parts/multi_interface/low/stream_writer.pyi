"""Low-level interface specification for stream writer."""

from __future__ import annotations

from typing import Protocol
from pretense import PretenseSpecificationError
from support.lib.framework import data_type, operation, poly_type


@data_type
class StreamWriterError(PretenseSpecificationError):
    """Base exception for all stream writer operations."""


@data_type
class PayloadEmptyError(StreamWriterError):
    """Raised when attempting to write an empty payload to the stream."""


@poly_type
class StreamWriter(Protocol):
    """Stream writer protocol for publishing sequential string payloads."""

    @property
    def written_count(self) -> int:
        """Cumulative count of payloads written to the stream."""
        ...

    @operation
    def write(self, payload: str) -> None:
        """Writes a string payload to the stream.

        Args:
            payload: Non-empty string payload to write.

        Raises:
            PayloadEmptyError: If payload is empty.

        PRECONDITIONS:
        - WHEN len(payload) == 0, MUST raise PayloadEmptyError.

        POSTCONDITIONS:
        - WHEN len(payload) > 0, MUST buffer payload and increment written_count by 1.
        """
        ...

    @operation
    def clear(self) -> None:
        """Purges all buffered payloads and resets written count to zero.

        POSTCONDITIONS:
        - MUST purge all buffered payloads.
        - MUST reset written_count to 0.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-11-03T23:55:00Z
# LAST_CHANGED: 2026-11-03T23:55:00Z
# CHANGE: Initial creation of stream_writer low-level specification
# SPEC_QA_AUDIT: 2026-11-03T23:55:00Z
# --- END CLEANROOM METADATA ---
