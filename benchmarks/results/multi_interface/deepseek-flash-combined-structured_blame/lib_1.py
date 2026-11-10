# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_174742_deepseek-flash_multi_interface_combined
# Timestamp: 2026-11-08T17:47:42.456081+00:00
# Benchmark Task: multi_interface
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 195,757
#   Cached Inbound Tokens:   11,581,312
#   Outbound Tokens:         171,961
#   Total Tokens:            11,949,030
#   Financial Cost ($USD):   $0.1673
#   Wall Clock Duration:     1126.10s
#   Step Latencies (s):      [104.8, 209.9, 10.1, 20.3, 601.6, 81.8, 125.1, 10.1, 63.4, 51.2, 125.0, 53.3, 10.1, 10.0]
#   Role Execution Rounds:   coverage: 1, lib: 1, pretense: 4, pretense_coverage: 2, pretense_qa: 4, qa: 1, test: 1 (Total: 14)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       8
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: multi_interface_impl.py ===
"""Library implementation of the consolidated stream buffer."""

from __future__ import annotations

from typing import Optional

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, get_default_registry, system

from . import stream_reader
from . import stream_writer


@singleton_type("system")
class StreamBuffer(stream_reader.StreamReader, stream_writer.StreamWriter):
    """Concrete realization of stream buffer implementing both reader and writer protocols.

    GROUNDING:
    - Realizes unified in-memory FIFO stream buffer.
    - Initializes _items to list() and _written_count to 0.
    """

    tier: str = "system"

    def __init__(self) -> None:
        # Backing FIFO storage and cumulative written counter.
        self._items: list[str] = []
        self._written_count: int = 0

    @property
    def unread_count(self) -> int:
        # Unread payloads are exactly the payloads still buffered.
        return len(self._items)

    @property
    def has_data(self) -> bool:
        # Data remains available while the buffer holds at least one payload.
        return len(self._items) > 0

    @property
    def written_count(self) -> int:
        # Cumulative payloads written since construction or last purge.
        return self._written_count

    @operation
    @override
    def read(self) -> Optional[str]:
        # While payloads remain, pop the oldest one and return it.
        if self._items:
            return self._items.pop(0)
        # With nothing buffered, the stream is empty.
        return None

    @operation
    @override
    def write(self, payload: str) -> None:
        # An empty payload is invalid and must raise PayloadEmptyError.
        if len(payload) == 0:
            raise stream_writer.PayloadEmptyError()
        # Buffer the payload and count it as written.
        self._items.append(payload)
        self._written_count += 1

    @operation
    @override
    def clear(self) -> None:
        # Drop every buffered payload.
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
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T18:06:24Z
# LAST_CHANGED: 2026-11-08T17:51:28Z
# CHANGE: Initialized StreamBuffer singleton realizing StreamReader+StreamWriter: FIFO list backing store with written counter, pop-oldest read, empty-payload PayloadEmptyError guard, count/purge clear; registered via auto-generated __initialize__ under @singleton_type('system').
# COVERAGE_AUDIT: 2026-11-08T17:52:06Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T18:06:24Z
# PRETENSE_QA_AUDIT: 2026-11-08T18:06:12Z
# QA_AUDIT: 2026-11-08T17:51:52Z
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

    pass


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
# LAST_CLEANED: 2026-11-08T17:51:16Z
# LAST_CHANGED: 2026-11-08T17:51:16Z
# CHANGE: Initialized stream_reader interface: StreamReaderError data type (non-dataclass exception) and @poly_type StreamReader protocol with unread_count/has_data properties plus @operation read stub; cross-part pretense import uses full package path.
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

    pass


@data_type
class PayloadEmptyError(StreamWriterError):
    """Raised when attempting to write an empty payload to the stream."""

    pass


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
# LAST_CLEANED: 2026-11-08T17:51:22Z
# LAST_CHANGED: 2026-11-08T17:51:22Z
# CHANGE: Initialized stream_writer interface: StreamWriterError and PayloadEmptyError exception data types (non-dataclass exceptions) and @poly_type StreamWriter protocol with written_count property plus @operation write/clear stubs; cross-part pretense import uses full package path.
# --- END AUTOFAB METADATA ---
