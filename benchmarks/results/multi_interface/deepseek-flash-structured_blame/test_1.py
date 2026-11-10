"""Unit tests for multi_interface_impl per its grounding specification."""

from __future__ import annotations

import unittest

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from multi_interface.lib.multi_interface_impl import StreamBuffer, __initialize__
from multi_interface.lib.stream_writer import PayloadEmptyError


class StreamBufferTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initial_state_is_empty_buffer(self) -> None:
        """A freshly constructed buffer is empty and reports a zero written count."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(StreamBuffer)
            self.assertEqual(buffer.unread_count, 0)
            self.assertFalse(buffer.has_data)
            self.assertEqual(buffer.written_count, 0)
            self.assertIsNone(buffer.read())

    def test_write_buffers_payload_and_increments_written_count(self) -> None:
        """Writing a non-empty payload buffers it and increments the written count."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(StreamBuffer)
            buffer.write("alpha")
            self.assertEqual(buffer.written_count, 1)
            self.assertEqual(buffer.unread_count, 1)
            self.assertTrue(buffer.has_data)
            buffer.write("beta")
            self.assertEqual(buffer.written_count, 2)
            self.assertEqual(buffer.unread_count, 2)

    def test_written_count_is_cumulative_across_reads(self) -> None:
        """The written count stays cumulative and is unaffected by consuming payloads."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(StreamBuffer)
            buffer.write("alpha")
            buffer.write("beta")
            self.assertEqual(buffer.read(), "alpha")
            self.assertEqual(buffer.written_count, 2)
            self.assertEqual(buffer.read(), "beta")
            self.assertEqual(buffer.written_count, 2)
            self.assertEqual(buffer.unread_count, 0)

    def test_read_pops_oldest_payload_and_decrements_unread_count(self) -> None:
        """Reading pops the oldest unread payload and decrements the unread count."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(StreamBuffer)
            buffer.write("first")
            buffer.write("second")
            self.assertEqual(buffer.read(), "first")
            self.assertEqual(buffer.unread_count, 1)
            self.assertEqual(buffer.read(), "second")
            self.assertEqual(buffer.unread_count, 0)
            self.assertFalse(buffer.has_data)

    def test_read_empty_stream_returns_none(self) -> None:
        """Reading from an empty stream returns None."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(StreamBuffer)
            self.assertEqual(buffer.unread_count, 0)
            self.assertIsNone(buffer.read())

    def test_read_after_draining_returns_none(self) -> None:
        """Draining all payloads leaves subsequent reads returning None."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(StreamBuffer)
            buffer.write("only")
            self.assertEqual(buffer.read(), "only")
            self.assertFalse(buffer.has_data)
            self.assertIsNone(buffer.read())

    def test_write_empty_payload_raises_payload_empty_error(self) -> None:
        """Writing an empty payload raises PayloadEmptyError."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(StreamBuffer)
            with self.assertRaises(PayloadEmptyError):
                buffer.write("")
            self.assertEqual(buffer.unread_count, 0)
            self.assertEqual(buffer.written_count, 0)

    def test_clear_purges_payloads(self) -> None:
        """Clearing purges all buffered payloads."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(StreamBuffer)
            buffer.write("alpha")
            buffer.write("beta")
            buffer.clear()
            self.assertEqual(buffer.unread_count, 0)
            self.assertFalse(buffer.has_data)
            self.assertIsNone(buffer.read())

    def test_clear_resets_written_count(self) -> None:
        """Clearing resets the written count to 0."""
        with enter_phase(system, registry=self.registry) as scope:
            buffer = scope.get_singleton(StreamBuffer)
            buffer.write("alpha")
            buffer.write("beta")
            self.assertEqual(buffer.written_count, 2)
            buffer.clear()
            self.assertEqual(buffer.written_count, 0)
            buffer.write("gamma")
            self.assertEqual(buffer.written_count, 1)
            self.assertEqual(buffer.read(), "gamma")


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:47:15Z
# LAST_CHANGED: 2026-11-08T17:45:50Z
# CHANGE: Authored contract-driven unit tests for the StreamBuffer singleton: isolated LifecycleRegistry setup with module initialization and system-tier phase scoping; coverage for initial empty state, FIFO read ordering with unread/has_data transitions, empty-stream read returning None, cumulative written count across reads, empty-payload PayloadEmptyError, and clear purging payloads plus resetting the written count. Fixed companion-module import paths and removed in-code contract references.
# COVERAGE_AUDIT: 2026-11-08T17:47:15Z
# QA_AUDIT: 2026-11-08T17:46:52Z
# --- END AUTOFAB METADATA ---
