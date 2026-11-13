# === File: multi_interface_impl_pretense.py ===
from __future__ import annotations

from typing import Optional

from pretense import sut
from support.lib.lifecycle import LifecycleTestCase

from multi_interface_deepseek_flash_1.parts.multi_interface.lib.multi_interface_impl import StreamBuffer
from multi_interface_deepseek_flash_1.parts.multi_interface.lib.stream_writer import PayloadEmptyError
from multi_interface_deepseek_flash_1.parts.multi_interface.pretense.stream_reader_pretense import (
    StreamReaderStateMachine,
)
from multi_interface_deepseek_flash_1.parts.multi_interface.pretense.stream_writer_pretense import (
    StreamWriterState,
    StreamWriterStateMachine,
)

# ==============================================================================
# 1. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================

class StreamBufferImplPseudoStateMachine(StreamReaderStateMachine, StreamWriterStateMachine):
    """Implementation pseudo-state machine binding the concrete StreamBuffer to both stream interfaces."""

    def make_initial_state(self) -> StreamWriterState:
        """Specializes the shared model state to the superset tracking buffered payloads and writes."""
        return StreamWriterState()

    def inner_unread_count(self) -> int:
        """Reads the concrete buffer's unread count."""
        target: StreamBuffer = sut(StreamBuffer)
        return target.unread_count

    def inner_has_data(self) -> bool:
        """Reads the concrete buffer's availability flag."""
        target: StreamBuffer = sut(StreamBuffer)
        return target.has_data

    def inner_read(self) -> Optional[str]:
        """Pops the oldest unread payload from the concrete buffer."""
        target: StreamBuffer = sut(StreamBuffer)
        return target.read()

    def inner_written_count(self) -> int:
        """Reads the concrete buffer's cumulative write count."""
        target: StreamBuffer = sut(StreamBuffer)
        return target.written_count

    def inner_write(self, payload: str) -> None:
        """Writes a payload into the concrete buffer."""
        target: StreamBuffer = sut(StreamBuffer)
        target.write(payload)

    def inner_clear(self) -> None:
        """Purges the concrete buffer."""
        target: StreamBuffer = sut(StreamBuffer)
        target.clear()


# ==============================================================================
# 2. Real Implementation Tests (Implementation Components)
# ==============================================================================

class TestStreamBufferImplReal(LifecycleTestCase):
    """Verifies that the concrete StreamBuffer implementation satisfies both stream contracts."""

    def setUp(self) -> None:
        super().setUp()
        self.real = self.sut
        self.sm = StreamBufferImplPseudoStateMachine(singletons={StreamBuffer: self.real})
        self.checked = self.sm.as_checked(StreamBuffer, self.real)

    def test_write_then_read_roundtrip(self) -> None:
        """Written payloads become readable and are reported by the interface properties."""
        self.checked.write("payload_alpha")
        assert self.checked.written_count == 1
        assert self.checked.unread_count == 1
        assert self.checked.has_data
        assert self.checked.read() == "payload_alpha"
        assert self.checked.unread_count == 0
        assert not self.checked.has_data

    def test_read_empty_buffer_returns_none(self) -> None:
        """A blank buffer reports no data and reads None."""
        assert self.checked.unread_count == 0
        assert not self.checked.has_data
        assert self.checked.read() is None

    def test_clear_purges_buffer_and_resets_written_count(self) -> None:
        """Clear purges buffered payloads and resets the cumulative write count."""
        self.checked.write("payload_alpha")
        self.checked.write("payload_beta")
        assert self.checked.written_count == 2
        self.checked.clear()
        assert self.checked.written_count == 0
        assert self.checked.unread_count == 0
        assert not self.checked.has_data

    def test_write_empty_payload_violates_contract(self) -> None:
        """Empty payloads violate the write precondition with PayloadEmptyError."""
        self.checked.violating(PayloadEmptyError).write("")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:08:18Z
# LAST_CHANGED: 2026-11-12T21:07:46Z
# CHANGE: Implement consolidated StreamBuffer pretense module: single multi-interface pseudo-state machine inheriting StreamReaderStateMachine and StreamWriterStateMachine, specialized shared model state, inner_* overrides binding the concrete SUT via sut(StreamBuffer), and real scenario tests covering read/write/clear/properties plus PayloadEmptyError violation.
# PRETENSE_COVERAGE_AUDIT: 2026-11-12T21:08:18Z
# PRETENSE_QA_AUDIT: 2026-11-12T21:08:04Z
# --- END AUTOFAB METADATA ---


# === File: stream_reader_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from multi_interface_deepseek_flash_1.parts.multi_interface.lib.stream_reader import StreamReader

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class StreamReaderState:
    """Canonical model state tracking the buffered payload queue of a stream reader."""
    unread_payloads: list[str] = field(default_factory=list)


class StreamReaderStateMachine(StateMachine):
    """Pretense State Machine for the StreamReader protocol."""

    def __init__(
        self,
        state: Optional[StreamReaderState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> StreamReaderState:
        """Constructs a blank initial model state with no buffered payloads."""
        return StreamReaderState()

    @transition.seeding
    def seed_payload(self, payload: str) -> None:
        """Seeds an unread payload into the buffered stream."""
        require_arg(payload, Domain.type(str), preferred=["payload_alpha", "payload_beta"])
        self.state.unread_payloads.append(payload)

    @transition(name="unread_count")
    def unread_count(self) -> int:
        """Reports the current number of unread payloads remaining in the stream."""
        count = self.inner_unread_count()
        assert count == len(self.state.unread_payloads)
        return count

    def inner_unread_count(self) -> int:
        """Computes the fake unread count strictly from model state."""
        return len(self.state.unread_payloads)

    @transition(name="has_data")
    def has_data(self) -> bool:
        """Reports whether unread payloads remain available in the stream."""
        available = self.inner_has_data()
        assert available == (len(self.state.unread_payloads) > 0)
        return available

    def inner_has_data(self) -> bool:
        """Computes the fake availability flag strictly from model state."""
        return len(self.state.unread_payloads) > 0

    @transition(StreamReader.read)
    def read(self) -> Optional[str]:
        """Pops and returns the oldest unread payload, or None when the stream is empty."""
        ret = self.inner_read()
        if ret is None:
            assert len(self.state.unread_payloads) == 0
        else:
            assert self.state.unread_payloads[0] == ret
            self.state.unread_payloads.pop(0)
        return ret

    def inner_read(self) -> Optional[str]:
        """Computes the fake read result strictly from model state."""
        if len(self.state.unread_payloads) > 0:
            return self.state.unread_payloads[0]
        return None


proto = StreamReaderStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeStreamReader = synthesize_fake(StreamReaderStateMachine)


def make_stream_reader_fake(state: Optional[StreamReaderState] = None) -> StreamReader:
    """Synthesizes a fake stream reader backed by the model state machine."""
    return FakeStreamReader(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestStreamReaderFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all stream reader transitions."""

    def setUp(self) -> None:
        state = proto.make_initial_state()
        self.fake = make_stream_reader_fake(state)
        self.sm = StreamReaderStateMachine(state=state, singletons={StreamReader: self.fake})

    def test_seeded_stream_read_pops_oldest_payload(self) -> None:
        """Seeding populates the stream and reads drain it oldest-first."""
        self.sm.seed_payload("payload_alpha")
        self.sm.seed_payload("payload_beta")
        assert self.sm.unread_count() == 2
        assert self.sm.has_data()
        assert self.fake.read() == "payload_alpha"
        assert self.sm.unread_count() == 1
        assert self.fake.read() == "payload_beta"
        assert not self.sm.has_data()

    def test_empty_stream_read_returns_none(self) -> None:
        """A blank stream exposes zero unread payloads and reads None."""
        assert self.sm.unread_count() == 0
        assert not self.sm.has_data()
        assert self.fake.read() is None


FakeStreamReaderFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeStreamReaderFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:07:34Z
# LAST_CHANGED: 2026-11-12T21:07:34Z
# CHANGE: Implement StreamReader pretense module: model state with buffered payload queue and seeding transition, 1:1 read/unread_count/has_data transitions with model postcondition asserts, synthesized fake factory, fixed fake transition-coverage tests, and Hypothesis fake fuzzing.
# --- END AUTOFAB METADATA ---


# === File: stream_writer_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import unittest

from hypothesis import given, settings, strategies as st

from pretense import (
    Domain,
    StateMachine,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from multi_interface_deepseek_flash_1.parts.multi_interface.lib.stream_writer import (
    PayloadEmptyError,
    StreamWriter,
)
from multi_interface_deepseek_flash_1.parts.multi_interface.pretense.stream_reader_pretense import (
    StreamReaderState,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================

@dataclass
class StreamWriterState(StreamReaderState):
    """Canonical model state extending the buffered stream with the cumulative write count."""
    written: int = 0


class StreamWriterStateMachine(StateMachine):
    """Pretense State Machine for the StreamWriter protocol."""

    def __init__(
        self,
        state: Optional[StreamWriterState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> StreamWriterState:
        """Constructs a blank initial model state with no buffered payloads."""
        return StreamWriterState()

    @transition.seeding
    def seed_payload(self, payload: str) -> None:
        """Seeds an already written payload into the buffered stream."""
        require_arg(payload, Domain.not_in([""]), preferred=["payload_alpha", "payload_beta"])
        self.state.unread_payloads.append(payload)
        self.state.written = self.state.written + 1

    @transition(name="written_count")
    def written_count(self) -> int:
        """Reports the cumulative count of payloads written to the stream."""
        count = self.inner_written_count()
        assert count == self.state.written
        return count

    def inner_written_count(self) -> int:
        """Computes the fake written count strictly from model state."""
        return self.state.written

    @transition(StreamWriter.write)
    def write(self, payload: str) -> None:
        """Buffers a non-empty payload and increments the cumulative write count."""
        require_arg(payload, Domain.not_in([""]), preferred=["payload_alpha", "payload_beta"], error=PayloadEmptyError)
        self.inner_write(payload)
        assert len(payload) > 0
        self.state.unread_payloads.append(payload)
        self.state.written = self.state.written + 1
        assert self.state.unread_payloads[-1] == payload

    def inner_write(self, payload: str) -> None:
        """Fake write is a no-op; the model state mutation happens in the transition."""
        return None

    @transition(StreamWriter.clear)
    def clear(self) -> None:
        """Purges all buffered payloads and resets the cumulative write count to zero."""
        self.inner_clear()
        self.state.unread_payloads.clear()
        self.state.written = 0
        assert len(self.state.unread_payloads) == 0
        assert self.state.written == 0

    def inner_clear(self) -> None:
        """Fake clear is a no-op; the model state mutation happens in the transition."""
        return None


proto = StreamWriterStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeStreamWriter = synthesize_fake(StreamWriterStateMachine)


def make_stream_writer_fake(state: Optional[StreamWriterState] = None) -> StreamWriter:
    """Synthesizes a fake stream writer backed by the model state machine."""
    return FakeStreamWriter(state=state or proto.make_initial_state())


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================

class TestStreamWriterFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies all stream writer transitions."""

    def setUp(self) -> None:
        state = proto.make_initial_state()
        self.fake = make_stream_writer_fake(state)
        self.sm = StreamWriterStateMachine(state=state, singletons={StreamWriter: self.fake})

    def test_seeded_writes_report_written_count(self) -> None:
        """Seeding records written payloads and increments the cumulative count."""
        self.sm.seed_payload("payload_alpha")
        assert self.sm.written_count() == 1

    def test_write_and_clear_reset_written_count(self) -> None:
        """Writes increment the cumulative count while clear purges and resets it."""
        self.fake.write("payload_alpha")
        assert self.sm.written_count() == 1
        self.fake.write("payload_beta")
        assert self.sm.written_count() == 2
        self.fake.clear()
        assert self.sm.written_count() == 0


FakeStreamWriterFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeStreamWriterFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-12T21:07:41Z
# LAST_CHANGED: 2026-11-12T21:07:41Z
# CHANGE: Implement StreamWriter pretense module: model state extending the buffered queue with cumulative write count, seeding transition, 1:1 write/written_count/clear transitions, non-empty payload domain gating PayloadEmptyError, synthesized fake factory, fixed fake tests, and Hypothesis fake fuzzing.
# --- END AUTOFAB METADATA ---
