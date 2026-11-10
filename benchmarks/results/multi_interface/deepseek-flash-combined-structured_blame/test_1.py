"""Unit tests for the consolidated stream buffer implementation."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleScope,
    enter_phase,
    system,
)
from multi_interface.lib import stream_reader, stream_writer
from multi_interface.lib.multi_interface_impl import (
    StreamBuffer,
    __initialize__,
)


class MultiInterfaceImplTest(unittest.TestCase):
    """Verifies StreamBuffer against stream reader and writer contracts."""

    registry: LifecycleRegistry
    phase_scope: LifecycleScope

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def _stream(self) -> StreamBuffer:
        """Resolves the stream buffer singleton within the active phase scope."""
        return self.phase_scope.get_singleton(StreamBuffer)

    def test_initial_buffer_state(self) -> None:
        """Happy path: a fresh buffer is empty with zeroed counters.

        Verifies that no payloads are buffered and no payloads were written
        after construction, and that reading an empty buffer yields None.
        """
        stream = self._stream()
        self.assertEqual(stream.unread_count, 0)
        self.assertFalse(stream.has_data)
        self.assertEqual(stream.written_count, 0)
        self.assertIsNone(stream.read())

    def test_write_then_read_fifo(self) -> None:
        """Happy path: writes are buffered and read back oldest-first.

        Verifies that writing buffers each payload and increments
        written_count, while reading pops the oldest unread item and
        decrements unread_count.
        """
        stream = self._stream()
        stream.write("alpha")
        stream.write("beta")
        self.assertEqual(stream.unread_count, 2)
        self.assertTrue(stream.has_data)
        self.assertEqual(stream.written_count, 2)
        self.assertEqual(stream.read(), "alpha")
        self.assertEqual(stream.unread_count, 1)
        self.assertEqual(stream.read(), "beta")
        self.assertEqual(stream.unread_count, 0)
        self.assertFalse(stream.has_data)
        self.assertEqual(stream.written_count, 2)

    def test_read_empty_buffer_returns_none(self) -> None:
        """Alternate: reading a drained buffer returns None.

        Verifies that reading with an unread count of zero yields None.
        """
        stream = self._stream()
        stream.write("payload")
        self.assertEqual(stream.read(), "payload")
        self.assertIsNone(stream.read())

    def test_write_empty_payload_raises(self) -> None:
        """Error: writing an empty payload raises PayloadEmptyError.

        Verifies the checked precondition that an empty payload is rejected and
        that the rejected payload is not buffered or counted.
        """
        stream = self._stream()
        with self.assertRaises(stream_writer.PayloadEmptyError):
            stream.write("")
        self.assertEqual(stream.unread_count, 0)
        self.assertFalse(stream.has_data)
        self.assertEqual(stream.written_count, 0)

    def test_clear_purges_payloads_and_resets_written_count(self) -> None:
        """Happy path: clear purges buffered payloads and resets written_count.

        Verifies that all buffered payloads are purged and the written count
        is reset to zero.
        """
        stream = self._stream()
        stream.write("one")
        stream.write("two")
        stream.clear()
        self.assertEqual(stream.unread_count, 0)
        self.assertFalse(stream.has_data)
        self.assertEqual(stream.written_count, 0)
        self.assertIsNone(stream.read())

    def test_written_count_is_cumulative_across_reads(self) -> None:
        """Happy path: written_count is independent of the unread payloads.

        Verifies that written_count keeps accumulating as payloads are written
        while reads only decrement the unread count.
        """
        stream = self._stream()
        stream.write("a")
        stream.write("b")
        self.assertEqual(stream.read(), "a")
        self.assertEqual(stream.written_count, 2)
        self.assertEqual(stream.unread_count, 1)
        self.assertEqual(stream.read(), "b")
        self.assertEqual(stream.written_count, 2)

    def test_singleton_available_via_reader_and_writer_protocols(self) -> None:
        """Happy path: the buffer singleton satisfies both interface keys."""
        stream = self._stream()
        reader: stream_reader.StreamReader = self.phase_scope.get_singleton(
            stream_reader.StreamReader
        )
        writer: stream_writer.StreamWriter = self.phase_scope.get_singleton(
            stream_writer.StreamWriter
        )
        self.assertIs(reader, stream)
        self.assertIs(writer, stream)


if __name__ == "__main__":
    unittest.main()

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:52:06Z
# LAST_CHANGED: 2026-11-08T17:49:45Z
# CHANGE: Implemented StreamBuffer unit tests: initial empty state, FIFO write/read with counters, read-on-empty returns None, empty-payload PayloadEmptyError rejection, clear purges and resets written_count, cumulative written_count across reads, and singleton resolution via reader/writer protocol keys within an active system phase scope.
# COVERAGE_AUDIT: 2026-11-08T17:52:06Z
# QA_AUDIT: 2026-11-08T17:51:52Z
# --- END AUTOFAB METADATA ---
