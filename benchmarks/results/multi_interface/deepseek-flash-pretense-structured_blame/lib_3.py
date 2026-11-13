# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_001756_deepseek-flash_multi_interface_pretense
# Timestamp: 2026-11-13T00:17:56.335713+00:00
# Benchmark Task: multi_interface
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 83,209
#   Cached Inbound Tokens:   2,565,888
#   Outbound Tokens:         72,689
#   Total Tokens:            2,721,786
#   Financial Cost ($USD):   $0.0638
#   Wall Clock Duration:     430.86s
#   Step Latencies (s):      [137.9, 403.8, 10.1, 10.0]
#   Role Execution Rounds:   lib: 1, pretense: 1, pretense_coverage: 1, pretense_qa: 1 (Total: 4)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       2
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: multi_interface_impl.py ===
"""Concrete realization of a unified in-memory FIFO stream buffer."""

from __future__ import annotations

from typing import Optional
from support.lib.framework import operation, override
from support.lib.lifecycle import singleton
from . import stream_reader, stream_writer


@singleton
class StreamBuffer(stream_reader.StreamReader, stream_writer.StreamWriter):
    """In-memory FIFO buffer implementing both the reader and writer protocols."""

    tier: str = "system"

    def __init__(self) -> None:
        self._items: list[str] = []
        self._written_count: int = 0

    @property
    @override
    def unread_count(self) -> int:
        # Remaining buffered payloads are exactly the unread payloads.
        return len(self._items)

    @property
    @override
    def has_data(self) -> bool:
        # Data is available whenever at least one payload remains buffered.
        return len(self._items) > 0

    @property
    @override
    def written_count(self) -> int:
        # Cumulative writes are tracked independently of pending reads.
        return self._written_count

    @operation
    @override
    def read(self) -> Optional[str]:
        # Remove and return the oldest buffered payload; an empty buffer yields nothing.
        if self._items:
            return self._items.pop(0)
        return None

    @operation
    @override
    def write(self, payload: str) -> None:
        # Reject empty payloads before buffering a non-empty payload.
        if len(payload) == 0:
            raise stream_writer.PayloadEmptyError("Cannot write an empty payload to the stream.")
        self._items.append(payload)
        self._written_count += 1

    @operation
    @override
    def clear(self) -> None:
        # Drop all buffered payloads and reset the cumulative write count.
        self._items.clear()
        self._written_count = 0

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:25:04Z
# LAST_CHANGED: 2026-11-13T00:20:14Z
# CHANGE: Implemented StreamBuffer as a system-tier singleton realizing both reader and writer protocols: FIFO read/pop, empty-payload rejection with PayloadEmptyError, unread/written counters, and clear resetting buffer and write count.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:25:04Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:24:50Z
# --- END AUTOFAB METADATA ---


# === File: stream_reader.py ===
"""Library interface for consuming sequential string payloads."""

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

        Returns the oldest unread payload string, or None when the stream is empty.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:20:02Z
# LAST_CHANGED: 2026-11-13T00:20:02Z
# CHANGE: Implemented stream_reader interface: StreamReaderError data type and StreamReader protocol with unread_count, has_data, and read members matching the low-level specification.
# --- END AUTOFAB METADATA ---


# === File: stream_writer.py ===
"""Library interface for publishing sequential string payloads."""

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

        Raises a payload-empty error when the payload is empty.
        """
        ...

    @operation
    def clear(self) -> None:
        """Purges all buffered payloads and resets the written count to zero."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:20:08Z
# LAST_CHANGED: 2026-11-13T00:20:08Z
# CHANGE: Implemented stream_writer interface: StreamWriterError and PayloadEmptyError data types plus StreamWriter protocol with written_count, write, and clear members matching the low-level specification.
# --- END AUTOFAB METADATA ---
