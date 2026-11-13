# === File: multi_interface_impl_pretense.py ===
from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    Env,
    StateMachine,
    raises,
    require,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
)

from support.lib.lifecycle import LifecycleTestCase, fake, get_singleton, system

from multi_interface_deepseek_flash_1.parts.multi_interface.lib.multi_interface_impl import (
    StreamBuffer,
)
from multi_interface_deepseek_flash_1.parts.multi_interface.lib.stream_reader import (
    StreamReader,
    StreamReaderError,
)
from multi_interface_deepseek_flash_1.parts.multi_interface.lib.stream_writer import (
    PayloadEmptyError,
    StreamWriter,
    StreamWriterError,
)
from multi_interface_deepseek_flash_1.parts.multi_interface.pretense.stream_reader_pretense import (
    StreamReaderStateMachine,
)
from multi_interface_deepseek_flash_1.parts.multi_interface.pretense.stream_writer_pretense import (
    StreamWriterState,
    StreamWriterStateMachine,
)

# ==============================================================================
# 4. Implementation Pseudo State Machine (Implementation Components)
# ==============================================================================


class StreamBufferImplPseudoStateMachine(StreamWriterStateMachine, StreamReaderStateMachine):
    """Implementation pseudo-state machine binding the concrete StreamBuffer SUT."""

    def inner_unread_count(self) -> int:
        target: StreamReader = sut(StreamReader)
        ret = target.unread_count
        assert ret >= 0
        return ret

    def inner_has_data(self) -> bool:
        target: StreamReader = sut(StreamReader)
        ret = target.has_data
        assert ret == (target.unread_count > 0)
        return ret

    def inner_read(self) -> Optional[str]:
        target: StreamReader = sut(StreamReader)
        old_count = target.unread_count
        ret = target.read()
        if old_count > 0:
            assert ret is not None
            assert target.unread_count == old_count - 1
        else:
            assert ret is None
        return ret

    def inner_written_count(self) -> int:
        target: StreamWriter = sut(StreamWriter)
        ret = target.written_count
        assert ret >= 0
        return ret

    def inner_write(self, payload: str) -> None:
        target: StreamWriter = sut(StreamWriter)
        old_count = target.written_count
        target.write(payload)
        assert target.written_count == old_count + 1
        return None

    def inner_clear(self) -> None:
        writer: StreamWriter = sut(StreamWriter)
        writer.clear()
        reader: StreamReader = sut(StreamReader)
        assert writer.written_count == 0
        assert reader.unread_count == 0
        assert reader.has_data is False
        return None


# ==============================================================================
# 5. Real Implementation Tests (Implementation Components)
# ==============================================================================


class TestStreamBufferImplReal(LifecycleTestCase):
    """Verifies that the concrete StreamBuffer implementation satisfies its contracts."""

    target = StreamBuffer

    def setUp(self) -> None:
        super().setUp()
        self.real = self.sut
        self.sm = StreamBufferImplPseudoStateMachine(
            singletons={StreamReader: self.real, StreamWriter: self.real}
        )
        self.reader = self.sm.as_checked(StreamReader, self.real)
        self.writer = self.sm.as_checked(StreamWriter, self.real)

    def test_read_from_empty_buffer(self) -> None:
        assert self.reader.unread_count == 0
        assert self.reader.has_data is False
        assert self.reader.read() is None

    def test_write_then_read_round_trip(self) -> None:
        self.writer.write("alpha")
        self.writer.write("beta")
        assert self.writer.written_count == 2
        assert self.reader.unread_count == 2
        assert self.reader.has_data is True
        assert self.reader.read() == "alpha"
        assert self.reader.unread_count == 1
        assert self.reader.read() == "beta"
        assert self.reader.has_data is False
        assert self.writer.written_count == 2

    def test_clear_resets_buffer(self) -> None:
        self.writer.write("alpha")
        self.writer.write("beta")
        self.writer.clear()
        assert self.writer.written_count == 0
        assert self.reader.unread_count == 0
        assert self.reader.has_data is False

    def test_write_empty_payload_violates_contract(self) -> None:
        self.writer.violating(PayloadEmptyError).write("")

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:25:04Z
# LAST_CHANGED: 2026-11-13T00:24:31Z
# CHANGE: Implemented StreamBuffer implementation pseudo state machine inheriting both StreamReader/StreamWriter state machines (single shared model state, no state dataclasses or require_arg), overriding inner transitions to drive the concrete SUT via sut(StreamReader)/sut(StreamWriter) and assert SUT differentials, plus TestStreamBufferImplReal covering read/write/clear/counts and the final violating() PayloadEmptyError scenario.
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T00:25:04Z
# PRETENSE_QA_AUDIT: 2026-11-13T00:24:50Z
# --- END AUTOFAB METADATA ---


# === File: stream_reader_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from multi_interface_deepseek_flash_1.parts.multi_interface.lib.stream_reader import (
    StreamReader,
    StreamReaderError,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class StreamReaderState:
    """Abstract model state of a stream: the FIFO queue of unread payloads.

    The cumulative written count is tracked alongside the queue so that a concrete
    multi-interface stream buffer can share this single model state with a writer.
    """

    payloads: list[str] = field(default_factory=list)
    written_count: int = 0


class StreamReaderStateMachine(StateMachine[StreamReaderState]):
    """Pretense state machine modelling the StreamReader interface contract."""

    def __init__(
        self,
        state: Optional[StreamReaderState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> StreamReaderState:
        """Constructs the blank initial model state."""
        return StreamReaderState()

    @transition(name="unread_count")
    def unread_count(self) -> int:
        """Number of unread payloads currently retained by the stream."""
        ret = self.inner_unread_count()
        assert ret == len(self.state.payloads)
        return ret

    def inner_unread_count(self) -> int:
        """Computes the fake return value strictly from model state."""
        return len(self.state.payloads)

    @transition(name="has_data")
    def has_data(self) -> bool:
        """Whether any unread payload remains in the stream."""
        ret = self.inner_has_data()
        assert ret == bool(self.state.payloads)
        return ret

    def inner_has_data(self) -> bool:
        """Computes the fake return value strictly from model state."""
        return bool(self.state.payloads)

    @transition(StreamReader.read)
    def read(self) -> Optional[str]:
        """Pops and returns the oldest unread payload, or None when empty."""
        old_count = len(self.state.payloads)
        ret = self.inner_read()
        if old_count > 0:
            payload = self.state.payloads.pop(0)
            assert ret == payload
            assert len(self.state.payloads) == old_count - 1
        else:
            assert ret is None
            assert len(self.state.payloads) == 0
        return ret

    def inner_read(self) -> Optional[str]:
        """Computes the fake return value strictly from model state."""
        if self.state.payloads:
            return self.state.payloads[0]
        return None

    @transition.seeding
    def seed_payloads(self) -> None:
        """Seeds the stream with a non-empty sample of unread payloads."""
        self.state.payloads.clear()
        self.state.payloads.extend(["alpha", "beta"])
        assert len(self.state.payloads) == 2


proto = StreamReaderStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeStreamReader = synthesize_fake(StreamReaderStateMachine)


def make_stream_reader_fake(state: Optional[StreamReaderState] = None) -> StreamReader:
    """Synthesizes a StreamReader fake backed by the supplied model state."""
    return FakeStreamReader(state=state or StreamReaderState())


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestStreamReaderFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies the StreamReader contracts."""

    def setUp(self) -> None:
        self.fake = make_stream_reader_fake()
        self.sm = StreamReaderStateMachine(singletons={StreamReader: self.fake})

    def test_empty_stream(self) -> None:
        assert self.fake.unread_count == 0
        assert self.fake.has_data is False
        assert self.fake.read() is None
        assert self.sm.read() is None

    def test_seeded_stream(self) -> None:
        self.sm.seed_payloads()
        seeded = make_stream_reader_fake(StreamReaderState(payloads=["alpha", "beta"]))
        assert seeded.unread_count == 2
        assert seeded.has_data is True
        assert seeded.read() == "alpha"
        assert seeded.unread_count == 1
        assert seeded.has_data is True
        assert seeded.read() == "beta"
        assert seeded.has_data is False
        assert seeded.read() is None
        assert seeded.unread_count == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake (Interface Components)
# ==============================================================================

FakeStreamReaderFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeStreamReaderFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:24:18Z
# LAST_CHANGED: 2026-11-13T00:24:18Z
# CHANGE: Implemented StreamReader pretense state machine: shared FIFO payload model state, 1:1 transitions for unread_count/has_data/read plus a seeding transition, synthesized fake with make_stream_reader_fake, fixed fake conformance tests covering every transition, and Hypothesis fake fuzzing.
# --- END AUTOFAB METADATA ---


# === File: stream_writer_pretense.py ===
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
    Env,
    StateMachine,
    raises,
    require,
    require_arg,
    require_env,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case

from multi_interface_deepseek_flash_1.parts.multi_interface.lib.stream_writer import (
    PayloadEmptyError,
    StreamWriter,
    StreamWriterError,
)
from multi_interface_deepseek_flash_1.parts.multi_interface.pretense.stream_reader_pretense import (
    StreamReaderState,
)

# ==============================================================================
# 1. State Machine Specification (Model & 1:1 Transitions — Interface Components)
# ==============================================================================


@dataclass
class StreamWriterState(StreamReaderState):
    """Writer view of the shared stream model state: shared payload buffer plus write count."""


class StreamWriterStateMachine(StateMachine[StreamReaderState]):
    """Pretense state machine modelling the StreamWriter interface contract."""

    def __init__(
        self,
        state: Optional[StreamWriterState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or self.make_initial_state(), singletons=singletons)

    def make_initial_state(self) -> StreamWriterState:
        """Constructs the blank initial model state."""
        return StreamWriterState()

    @transition(name="written_count")
    def written_count(self) -> int:
        """Cumulative count of payloads written to the stream."""
        ret = self.inner_written_count()
        assert ret == self.state.written_count
        return ret

    def inner_written_count(self) -> int:
        """Computes the fake return value strictly from model state."""
        return self.state.written_count

    @transition(StreamWriter.write)
    def write(self, payload: str) -> None:
        """Buffers a non-empty payload and increments the written count."""
        require_arg(
            payload,
            Domain.text(min_size=1),
            error=PayloadEmptyError,
            preferred=["alpha", "beta"],
        )
        ret = self.inner_write(payload)
        self.state.payloads.append(payload)
        self.state.written_count += 1
        assert self.state.payloads[-1] == payload
        assert self.state.written_count >= 1
        return ret

    def inner_write(self, payload: str) -> None:
        """Computes the fake return value strictly from model state."""
        return None

    @transition(StreamWriter.clear)
    def clear(self) -> None:
        """Purges all buffered payloads and resets the written count to zero."""
        ret = self.inner_clear()
        self.state.payloads.clear()
        self.state.written_count = 0
        assert self.state.written_count == 0
        assert len(self.state.payloads) == 0
        return ret

    def inner_clear(self) -> None:
        """Computes the fake return value strictly from model state."""
        return None

    @transition.seeding
    def seed_written(self) -> None:
        """Seeds the stream with a non-empty sample of buffered payloads."""
        self.state.payloads.clear()
        self.state.payloads.extend(["alpha", "beta"])
        self.state.written_count = 2
        assert self.state.written_count == 2


proto = StreamWriterStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes (Interface Components)
# ==============================================================================

FakeStreamWriter = synthesize_fake(StreamWriterStateMachine)


def make_stream_writer_fake(state: Optional[StreamWriterState] = None) -> StreamWriter:
    """Synthesizes a StreamWriter fake backed by the supplied model state."""
    return FakeStreamWriter(state=state or StreamWriterState())


# ==============================================================================
# 3. Fixed Scenarios on Fake (Interface Components)
# ==============================================================================


class TestStreamWriterFake(unittest.TestCase):
    """Verifies that the synthesized fake satisfies the StreamWriter contracts."""

    def setUp(self) -> None:
        self.fake = make_stream_writer_fake()
        self.sm = StreamWriterStateMachine(singletons={StreamWriter: self.fake})

    def test_blank_stream(self) -> None:
        assert self.fake.written_count == 0
        self.fake.clear()
        assert self.fake.written_count == 0

    def test_write_and_clear(self) -> None:
        self.sm.seed_written()
        self.fake.write("alpha")
        assert self.fake.written_count == 1
        self.fake.write("beta")
        assert self.fake.written_count == 2
        self.fake.clear()
        assert self.fake.written_count == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing on Fake (Interface Components)
# ==============================================================================

FakeStreamWriterFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=proto.make_initial_state,
    name="FakeStreamWriterFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T00:24:24Z
# LAST_CHANGED: 2026-11-13T00:24:24Z
# CHANGE: Implemented StreamWriter pretense state machine: shared buffer model state with written_count, 1:1 transitions for written_count/write (PayloadEmptyError domain gate)/clear plus a seeding transition, synthesized fake with make_stream_writer_fake, fixed fake conformance tests covering every transition, and Hypothesis fake fuzzing.
# --- END AUTOFAB METADATA ---
