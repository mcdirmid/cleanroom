# === File: multi_interface_impl_pretense.py ===
"""Pretense implementation pseudo state machine, real tests, and property fuzzing for StreamBuffer."""

from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    StateMachine,
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_1.parts.multi_interface.pretense.stream_reader_pretense import (
    StreamReaderStateMachine,
)
from benchmark_1.parts.multi_interface.pretense.stream_writer_pretense import (
    StreamWriterState,
    StreamWriterStateMachine,
)
from benchmark_1.parts.multi_interface.lib.stream_writer import PayloadEmptyError
from benchmark_1.parts.multi_interface.lib.multi_interface_impl import (
    StreamBuffer,
    __initialize__,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine
# ==============================================================================

class MultiInterfacePseudoStateMachine(StreamWriterStateMachine, StreamReaderStateMachine):
    """Implementation pseudo state machine observing the real StreamBuffer SUT."""

    def __init__(
        self,
        state: Optional[StreamWriterState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or StreamWriterState(), singletons=singletons)

    @transition(StreamBuffer.read)
    def read(self) -> Optional[str]:
        target: StreamBuffer = sut(StreamBuffer)
        ret: Optional[str] = call_target(target.read())
        assert target.unread_count == len(self.state.items)
        assert target.has_data == (len(self.state.items) > 0)
        return ret

    @transition(StreamBuffer.write)
    def write(self, payload: str) -> None:
        target: StreamBuffer = sut(StreamBuffer)
        if len(payload) == 0:
            with raises(PayloadEmptyError):
                call_target(target.write(payload))
            assert target.written_count == self.state.written_count
            assert target.unread_count == len(self.state.items)
            return None
        ret = call_target(target.write(payload))
        assert target.written_count == self.state.written_count
        assert target.unread_count == len(self.state.items)
        return ret

    @transition(StreamBuffer.clear)
    def clear(self) -> None:
        target: StreamBuffer = sut(StreamBuffer)
        ret = call_target(target.clear())
        assert target.written_count == self.state.written_count
        assert target.unread_count == len(self.state.items)
        return ret

    @transition(name="unread_count")
    def unread_count(self) -> int:
        target: StreamBuffer = sut(StreamBuffer)
        ret: int = call_target(target.unread_count)
        assert ret == len(self.state.items)
        return ret

    @transition(name="has_data")
    def has_data(self) -> bool:
        target: StreamBuffer = sut(StreamBuffer)
        ret: bool = call_target(target.has_data)
        assert ret == (len(self.state.items) > 0)
        return ret

    @transition(name="written_count")
    def written_count(self) -> int:
        target: StreamBuffer = sut(StreamBuffer)
        ret: int = call_target(target.written_count)
        assert ret == self.state.written_count
        return ret


proto = MultiInterfacePseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestMultiInterfaceImplReal(unittest.TestCase):
    """Verifies that the concrete StreamBuffer satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(StreamBuffer)
        self.sm = MultiInterfacePseudoStateMachine(singletons={StreamBuffer: self.real})
        self.checked = self.sm.as_checked(StreamBuffer, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_stream_buffer_lifecycle(self) -> None:
        assert self.checked.written_count == 0
        assert self.checked.unread_count == 0
        assert not self.checked.has_data
        assert self.checked.read() is None
        self.checked.write("alpha")
        self.checked.write("beta")
        assert self.checked.written_count == 2
        assert self.checked.unread_count == 2
        assert self.checked.has_data
        assert self.checked.read() == "alpha"
        assert self.checked.read() == "beta"
        assert self.checked.unread_count == 0
        assert not self.checked.has_data
        self.checked.write("gamma")
        self.checked.clear()
        assert self.checked.written_count == 0
        assert self.checked.unread_count == 0
        assert not self.checked.has_data

    def test_empty_payload_is_rejected(self) -> None:
        assert self.checked.written_count == 0
        assert self.checked.unread_count == 0
        assert not self.checked.has_data
        with self.assertRaises(PayloadEmptyError):
            self.checked.write("")
        assert self.checked.written_count == 0
        assert self.checked.unread_count == 0
        assert not self.checked.has_data


# ==============================================================================
# 3. Real Hypothesis Fuzzing
# ==============================================================================

def make_sut() -> StreamBuffer:
    registry = LifecycleRegistry()
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(StreamBuffer)


MultiInterfaceFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=StreamWriterState,
    name="MultiInterfaceFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T18:06:24Z
# LAST_CHANGED: 2026-11-08T18:05:56Z
# CHANGE: Resolved empty-payload rejection-observation feedback: test_empty_payload_is_rejected now observes the contracted rejection at the checked interface with with self.assertRaises(PayloadEmptyError): self.checked.write(''), so the expected exception no longer escapes unhandled and aborts the scenario, and only after observing it verifies written_count == 0, unread_count == 0, and has_data is False; the pseudo state machine's empty-payload expectation remains modeled via with raises(PayloadEmptyError) around the call_target pivot.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T18:06:24Z
# PRETENSE_QA_AUDIT: 2026-11-08T18:06:12Z
# --- END AUTOFAB METADATA ---


# === File: stream_reader_pretense.py ===
"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for StreamReader."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_1.parts.multi_interface.lib.stream_reader import StreamReader


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================

@dataclass
class StreamReaderState:
    """Canonical model state for the shared stream buffer consumed by StreamReader."""

    initialized: bool = True
    items: list[str] = field(default_factory=list)
    written_count: int = 0


class StreamReaderStateMachine(StateMachine[StreamReaderState]):
    """Unified Pretense State Machine for StreamReader."""

    def __init__(
        self,
        state: Optional[StreamReaderState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or StreamReaderState(), singletons=singletons)

    @transition(StreamReader.read)
    def read(self) -> Optional[str]:
        require(self.state.initialized)
        expected: Optional[str] = self.state.items[0] if self.state.items else None
        if self.state.items:
            self.state.items.pop(0)
        ret: Optional[str] = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="unread_count")
    def unread_count(self) -> int:
        require(self.state.initialized)
        expected: int = len(self.state.items)
        ret: int = make_return_value(expected)
        assert ret == expected
        return ret

    @transition(name="has_data")
    def has_data(self) -> bool:
        require(self.state.initialized)
        expected: bool = len(self.state.items) > 0
        ret: bool = make_return_value(expected)
        assert ret == expected
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the model into its initialized operating state."""
        self.state.initialized = True


proto = StreamReaderStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeStreamReader = synthesize_fake(StreamReaderStateMachine)


def make_stream_reader_fake(
    state: Optional[StreamReaderState] = None,
) -> StreamReader:
    """Synthesizes a StreamReader fake double over model state."""
    return FakeStreamReader(state=state or StreamReaderState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestStreamReaderFake(unittest.TestCase):
    """Fixed scenarios exercising the synthesized StreamReader fake double."""

    def setUp(self) -> None:
        self.sm = StreamReaderStateMachine()
        self.fake = make_stream_reader_fake()
        self.checked = self.sm.as_checked(StreamReader, self.fake)

    def test_empty_stream_observations(self) -> None:
        self.sm.seed_initial()
        assert self.checked.unread_count == 0
        assert not self.checked.has_data
        assert self.checked.read() is None


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing
# ==============================================================================

FakeStreamReaderFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=StreamReaderState,
    name="FakeStreamReaderFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:57:53Z
# LAST_CHANGED: 2026-11-08T17:57:53Z
# CHANGE: Implemented StreamReader interface pretense: FIFO model state, 1:1 read/unread_count/has_data transitions with make_return_value pivots, synthesized fake + factory, TestStreamReaderFake covering all transitions incl. seed_initial, and FakeStreamReaderFuzzTest compiled from the proto; fixed package-qualified imports and removed the real-SUT test class.
# --- END AUTOFAB METADATA ---


# === File: stream_writer_pretense.py ===
"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for StreamWriter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import unittest

from pretense import (
    Domain,
    StateMachine,
    make_return_value,
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_1.parts.multi_interface.pretense.stream_reader_pretense import (
    StreamReaderState,
)
from benchmark_1.parts.multi_interface.lib.stream_writer import StreamWriter


# ==============================================================================
# 1. Model State & 1:1 Transitions
# ==============================================================================

@dataclass
class StreamWriterState(StreamReaderState):
    """Writer-facing model state for the shared stream buffer.

    Inherits the shared buffer contents and write accounting modeled by
    ``StreamReaderState``; the state machine specializes the buffer protocol.
    """


class StreamWriterStateMachine(StateMachine[StreamReaderState]):
    """Unified Pretense State Machine for StreamWriter."""

    def __init__(
        self,
        state: Optional[StreamWriterState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or StreamWriterState(), singletons=singletons)

    @transition(StreamWriter.write)
    def write(self, payload: str) -> None:
        require(self.state.initialized)
        require_arg(payload, Domain.type(str), preferred=["alpha", "beta", "gamma"])
        if len(payload) > 0:
            self.state.items.append(payload)
            self.state.written_count += 1
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(StreamWriter.clear)
    def clear(self) -> None:
        require(self.state.initialized)
        self.state.items.clear()
        self.state.written_count = 0
        ret = make_return_value()
        assert ret is None
        return ret

    @transition(name="written_count")
    def written_count(self) -> int:
        require(self.state.initialized)
        expected: int = self.state.written_count
        ret: int = make_return_value(expected)
        assert ret == expected
        return ret

    @transition.seeding
    def seed_initial(self) -> None:
        """Seeds the model into its initialized operating state."""
        self.state.initialized = True


proto = StreamWriterStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeStreamWriter = synthesize_fake(StreamWriterStateMachine)


def make_stream_writer_fake(
    state: Optional[StreamWriterState] = None,
) -> StreamWriter:
    """Synthesizes a StreamWriter fake double over model state."""
    return FakeStreamWriter(state=state or StreamWriterState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestStreamWriterFake(unittest.TestCase):
    """Fixed scenarios exercising the synthesized StreamWriter fake double."""

    def setUp(self) -> None:
        self.sm = StreamWriterStateMachine()
        self.fake = make_stream_writer_fake()
        self.checked = self.sm.as_checked(StreamWriter, self.fake)

    def test_write_and_clear_cycle(self) -> None:
        self.sm.seed_initial()
        assert self.checked.written_count == 0
        self.checked.write("alpha")
        self.checked.write("beta")
        assert self.checked.written_count == 2
        self.checked.clear()
        assert self.checked.written_count == 0


# ==============================================================================
# 4. Hypothesis Stateful Fuzzing
# ==============================================================================

FakeStreamWriterFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=StreamWriterState,
    name="FakeStreamWriterFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:57:59Z
# LAST_CHANGED: 2026-11-08T17:57:59Z
# CHANGE: Implemented StreamWriter interface pretense: shared buffer model state, 1:1 write/clear/written_count transitions with empty-payload precondition gated via require_arg and make_return_value pivots, synthesized fake + factory, TestStreamWriterFake covering all transitions incl. seed_initial, and FakeStreamWriterFuzzTest; fixed package-qualified imports and removed the real-SUT test class.
# --- END AUTOFAB METADATA ---
