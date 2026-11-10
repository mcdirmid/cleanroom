# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_174638_deepseek-flash_multi_interface_pretense
# Timestamp: 2026-11-08T17:46:38.367334+00:00
# Benchmark Task: multi_interface
# Model: deepseek-flash (Tier 2)
# Methodology: pretense
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 168,338
#   Cached Inbound Tokens:   9,503,744
#   Outbound Tokens:         118,757
#   Total Tokens:            9,790,839
#   Financial Cost ($USD):   $0.1250
#   Wall Clock Duration:     944.95s
#   Step Latencies (s):      [145.0, 430.6, 50.9, 124.4, 50.8, 112.2, 10.0, 42.8, 104.3, 10.1, 10.1]
#   Role Execution Rounds:   lib: 1, pretense: 4, pretense_coverage: 2, pretense_qa: 4 (Total: 11)
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

# === File: multi_interface_impl.py ===
"""Library implementation for the consolidated stream buffer."""

from __future__ import annotations

from typing import List, Optional

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import stream_reader
from . import stream_writer


@singleton_type("system")
class StreamBuffer(stream_reader.StreamReader, stream_writer.StreamWriter):
    """Concrete realization of stream buffer implementing both reader and writer protocols."""

    tier: str = "system"

    def __init__(self) -> None:
        """Initializes empty item storage and a zero written count."""
        self._items: List[str] = []
        self._written_count: int = 0

    @property
    @override
    def unread_count(self) -> int:
        """Current number of unread payloads remaining in the buffer."""
        # Postcondition: unread payload count tracks the currently buffered items.
        return len(self._items)

    @property
    @override
    def has_data(self) -> bool:
        """Indicates whether unread payloads remain available in the buffer."""
        # Postcondition: available data is reported only for a non-empty buffer.
        return len(self._items) > 0

    @property
    @override
    def written_count(self) -> int:
        """Cumulative count of payloads written to the buffer."""
        # Postcondition: the cumulative write counter is exposed unchanged.
        return self._written_count

    @operation
    @override
    def read(self) -> Optional[str]:
        """Reads and extracts the oldest unread payload from the buffer.

        Returns:
            Oldest unread payload string, or None if buffer is empty.
        """
        # When unread payloads remain, pop the oldest one and return it.
        if len(self._items) > 0:
            return self._items.pop(0)
        # Otherwise the buffer is empty, so there is nothing to read.
        return None

    @operation
    @override
    def write(self, payload: str) -> None:
        """Writes a string payload to the buffer.

        Args:
            payload: Non-empty string payload to write.

        Raises:
            stream_writer.PayloadEmptyError: If payload is empty.
        """
        # Precondition guard: an empty payload is rejected before any mutation.
        if len(payload) == 0:
            raise stream_writer.PayloadEmptyError("payload must not be empty")
        # Buffer the payload at the tail to preserve FIFO ordering.
        self._items.append(payload)
        # Track the cumulative number of successfully buffered payloads.
        self._written_count += 1

    @operation
    @override
    def clear(self) -> None:
        """Purges all buffered payloads and resets written count to zero."""
        # Purge every buffered payload.
        self._items.clear()
        # Reset the cumulative written counter.
        self._written_count = 0


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        StreamBuffer,
        keys=[StreamBuffer, stream_reader.StreamReader, stream_writer.StreamWriter],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T18:02:20Z
# LAST_CHANGED: 2026-11-08T17:49:19Z
# CHANGE: Implemented StreamBuffer singleton: backing _items FIFO list and _written_count initialized in __init__; unread_count/has_data/written_count properties; read pops oldest or returns None; write rejects empty payload with stream_writer.PayloadEmptyError before buffering and increments written count; clear purges items and resets counter. Auto-generated __initialize__ untouched.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T18:02:20Z
# PRETENSE_QA_AUDIT: 2026-11-08T18:02:07Z
# --- END AUTOFAB METADATA ---


# === File: stream_reader.py ===
"""Library interface specification for stream reader."""

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
# LAST_CLEANED: 2026-11-08T17:49:08Z
# LAST_CHANGED: 2026-11-08T17:49:08Z
# CHANGE: Fleshed out stream_reader interface: imported PretenseSpecificationError via package-qualified path, applied data_type/poly_type/operation decorators, and added unread_count/has_data/read stubs with contract docstrings.
# --- END AUTOFAB METADATA ---


# === File: stream_writer.py ===
"""Library interface specification for stream writer."""

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
# LAST_CLEANED: 2026-11-08T17:49:13Z
# LAST_CHANGED: 2026-11-08T17:49:13Z
# CHANGE: Fleshed out stream_writer interface: package-qualified PretenseSpecificationError import, data_type error hierarchy (StreamWriterError, PayloadEmptyError), and poly_type StreamWriter protocol with written_count/write/clear operations.
# --- END AUTOFAB METADATA ---
