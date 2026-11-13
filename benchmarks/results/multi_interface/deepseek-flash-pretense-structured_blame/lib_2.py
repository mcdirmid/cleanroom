# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261112_210009_deepseek-flash_multi_interface_pretense
# Timestamp: 2026-11-12T21:00:09.336309+00:00
# Benchmark Task: multi_interface
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 89,053
#   Cached Inbound Tokens:   3,944,192
#   Outbound Tokens:         80,280
#   Total Tokens:            4,113,525
#   Financial Cost ($USD):   $0.0734
#   Wall Clock Duration:     493.18s
#   Step Latencies (s):      [148.4, 465.5, 10.1, 10.0]
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
"""Concrete realization of the consolidated in-memory stream buffer."""

from __future__ import annotations

from typing import Optional

from support.lib.framework import operation, override
from support.lib.lifecycle import singleton

from . import stream_reader, stream_writer


@singleton
class StreamBuffer(stream_reader.StreamReader, stream_writer.StreamWriter):
    """Concrete FIFO stream buffer implementing both reader and writer protocols."""

    tier: str = "system"

    def __init__(self) -> None:
        self._items: list[str] = []
        self._written_count: int = 0

    @property
    @override
    def unread_count(self) -> int:
        """Current number of unread payloads remaining in the buffer."""
        return len(self._items)

    @property
    @override
    def has_data(self) -> bool:
        """Indicates whether unread payloads remain available in the buffer."""
        return len(self._items) > 0

    @property
    @override
    def written_count(self) -> int:
        """Cumulative count of payloads written to the buffer."""
        return self._written_count

    @operation
    @override
    def read(self) -> Optional[str]:
        """Reads and extracts the oldest unread payload from the buffer."""
        # An empty buffer has nothing left to consume.
        if len(self._items) == 0:
            return None
        # Consuming the head of the FIFO queue decrements the unread count.
        return self._items.pop(0)

    @operation
    @override
    def write(self, payload: str) -> None:
        """Writes a string payload to the buffer.

        Raises:
            PayloadEmptyError: If the payload is empty.
        """
        # Reject empty payloads before touching the buffered state.
        if len(payload) == 0:
            raise stream_writer.PayloadEmptyError("payload must not be empty")
        # Append the payload to the FIFO queue and track the cumulative total.
        self._items.append(payload)
        self._written_count += 1

    @operation
    @override
    def clear(self) -> None:
        """Purges all buffered payloads and resets the written count to zero."""
        # Drop every buffered payload and reset the writing statistics.
        self._items.clear()
        self._written_count = 0

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:08:18Z
# LAST_CHANGED: 2026-11-12T21:02:35Z
# CHANGE: Implement StreamBuffer singleton realizing StreamReader and StreamWriter as a FIFO buffer with write validation raising PayloadEmptyError and counter tracking matching low/multi_interface_impl.pyi.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T21:08:18Z
# PRETENSE_QA_AUDIT: 2026-11-12T21:08:04Z
# --- END AUTOFAB METADATA ---


# === File: stream_reader.py ===
"""Interface protocols for consuming sequential string payloads."""

from __future__ import annotations

from typing import Optional, Protocol

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError
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
            Oldest unread payload string, or None if the stream is empty.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:02:26Z
# LAST_CHANGED: 2026-11-12T21:02:26Z
# CHANGE: Implement StreamReader interface protocol with error base, unread_count/has_data properties, and read operation stub matching low/stream_reader.pyi.
# --- END AUTOFAB METADATA ---


# === File: stream_writer.py ===
"""Interface protocols for publishing sequential string payloads."""

from __future__ import annotations

from typing import Protocol

from pretense.parts.pretense.lib.pretense import PretenseSpecificationError
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
            PayloadEmptyError: If the payload is empty.
        """
        ...

    @operation
    def clear(self) -> None:
        """Purges all buffered payloads and resets the written count to zero."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:02:30Z
# LAST_CHANGED: 2026-11-12T21:02:30Z
# CHANGE: Implement StreamWriter interface protocol with error hierarchy and written_count/write/clear operation stubs matching low/stream_writer.pyi.
# --- END AUTOFAB METADATA ---
