# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_174404_deepseek-flash_multi_interface
# Timestamp: 2026-11-08T17:44:04.359984+00:00
# Benchmark Task: multi_interface
# Model: deepseek-flash (Tier 2)
# Methodology: autofab
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 52,777
#   Cached Inbound Tokens:   1,200,000
#   Outbound Tokens:         22,693
#   Total Tokens:            1,275,470
#   Financial Cost ($USD):   $0.0251
#   Wall Clock Duration:     204.16s
#   Step Latencies (s):      [91.7, 134.6, 20.2, 20.2]
#   Role Execution Rounds:   coverage: 1, lib: 1, qa: 1, test: 1 (Total: 4)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       9
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: multi_interface_impl.py ===
"""Library implementation of the consolidated in-memory stream buffer."""

from __future__ import annotations

from typing import List, Optional

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry

from . import stream_reader
from . import stream_writer


@singleton_type("system")
class StreamBuffer(stream_reader.StreamReader, stream_writer.StreamWriter):
    """Concrete realization of stream buffer implementing both reader and writer protocols."""

    tier: str = "system"

    def __init__(self) -> None:
        # Backing FIFO storage for buffered payloads.
        self._items: List[str] = []
        # Cumulative count of payloads written since the last clear.
        self._written_count: int = 0

    @property
    @override
    def unread_count(self) -> int:
        # Number of unread payloads remaining in the buffer.
        return len(self._items)

    @property
    @override
    def has_data(self) -> bool:
        # Unread payloads are available exactly when the buffer is non-empty.
        return len(self._items) > 0

    @property
    @override
    def written_count(self) -> int:
        # Cumulative count of payloads written to the buffer.
        return self._written_count

    @operation
    @override
    def read(self) -> Optional[str]:
        # Non-empty buffer: pop and return the oldest unread payload.
        if len(self._items) > 0:
            return self._items.pop(0)
        # Empty buffer: nothing to read.
        return None

    @operation
    @override
    def write(self, payload: str) -> None:
        # Empty payloads are rejected.
        if len(payload) == 0:
            raise stream_writer.PayloadEmptyError(
                "cannot write an empty payload to the stream"
            )
        # Buffer the payload and account for it.
        self._items.append(payload)
        self._written_count += 1

    @operation
    @override
    def clear(self) -> None:
        # Purge all buffered payloads.
        self._items.clear()
        # Reset the cumulative written count.
        self._written_count = 0


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        StreamBuffer,
        keys=[StreamBuffer, stream_reader.StreamReader, stream_writer.StreamWriter],
        tier='system',
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:47:15Z
# LAST_CHANGED: 2026-11-08T17:46:31Z
# CHANGE: Implemented StreamBuffer singleton (@singleton_type('system'), tier='system') realizing StreamReader+StreamWriter: FIFO _items and _written_count backing state, read() pops oldest or returns None when empty, write() raises PayloadEmptyError on empty payload and buffers/increments otherwise, clear() purges and resets count; removed duplicate tier and NotImplementedError stubs, preserved auto-generated __initialize__.
# COVERAGE_AUDIT: 2026-11-08T17:47:15Z
# QA_AUDIT: 2026-11-08T17:46:52Z
# --- END AUTOFAB METADATA ---


# === File: stream_reader.py ===
"""Library interface for stream reader."""

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
            Oldest unread payload string, or None if stream is empty.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:46:19Z
# LAST_CHANGED: 2026-11-08T17:46:19Z
# CHANGE: Implemented StreamReader interface: @data_type StreamReaderError base exception and @poly_type StreamReader Protocol with unread_count, has_data, and read() stubs; fixed cross-part pretense import to full package path.
# --- END AUTOFAB METADATA ---


# === File: stream_writer.py ===
"""Library interface for stream writer."""

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
            PayloadEmptyError: If payload is empty.
        """
        ...

    @operation
    def clear(self) -> None:
        """Purges all buffered payloads and resets written count to zero."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:46:25Z
# LAST_CHANGED: 2026-11-08T17:46:25Z
# CHANGE: Implemented StreamWriter interface: @data_type StreamWriterError and PayloadEmptyError exceptions plus @poly_type StreamWriter Protocol with written_count, write(payload), and clear() stubs; fixed cross-part pretense import to full package path.
# --- END AUTOFAB METADATA ---
