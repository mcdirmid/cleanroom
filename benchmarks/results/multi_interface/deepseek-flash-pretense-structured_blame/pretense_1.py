# === File: multi_interface_impl_pretense.py ===
"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for StreamBuffer."""

from __future__ import annotations

from typing import Any, Optional
import unittest

from pretense import (
    call_target,
    raises,
    require,
    sut,
    sut_state,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from benchmark_4.parts.multi_interface.lib.multi_interface_impl import (
    StreamBuffer,
    __initialize__,
)
from benchmark_4.parts.multi_interface.lib.stream_reader import StreamReader
from benchmark_4.parts.multi_interface.lib.stream_writer import (
    PayloadEmptyError,
    StreamWriter,
)
from benchmark_4.parts.multi_interface.pretense.stream_reader_pretense import (
    StreamReaderStateMachine,
)
from benchmark_4.parts.multi_interface.pretense.stream_writer_pretense import (
    StreamWriterState,
    StreamWriterStateMachine,
)


# ==============================================================================
# 1. Implementation Pseudo State Machine
# ==============================================================================
# NOTE: Implementation overrides observe and assert postconditions against the
# real SUT via call_target(target.method(...)); preconditions and model state
# mutations are inherited from the interface state machines.


class StreamBufferPseudoStateMachine(StreamReaderStateMachine, StreamWriterStateMachine):
    """Implementation pseudo-state machine for the consolidated stream buffer."""

    def __init__(
        self,
        state: Optional[StreamWriterState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or StreamWriterState(), singletons=singletons)

    @transition(StreamBuffer.read)
    def read(self) -> Optional[str]:
        """Read the oldest buffered payload and verify the unread count decrement."""
        target: StreamBuffer = sut(StreamBuffer)
        before: int = sut(StreamReader).unread_count
        ret = call_target(target.read())
        assert sut(StreamReader).unread_count == max(before - 1, 0)
        assert (ret is None) == (before == 0)
        return ret

    @transition(StreamBuffer.write)
    def write(self, payload: str) -> None:
        """Write a payload; an empty payload raises without buffering or counting."""
        target: StreamBuffer = sut(StreamBuffer)
        if len(payload) == 0:
            before_empty: int = sut(StreamWriter).written_count
            with raises(PayloadEmptyError):
                ret = call_target(target.write(payload))
            assert sut(StreamWriter).written_count == before_empty
            return None
        before: int = sut(StreamWriter).written_count
        ret = call_target(target.write(payload))
        assert sut(StreamWriter).written_count == before + 1
        return ret

    @transition(StreamBuffer.clear)
    def clear(self) -> None:
        """Clear the buffer and verify every observable count is reset."""
        target: StreamBuffer = sut(StreamBuffer)
        ret = call_target(target.clear())
        assert sut(StreamReader).unread_count == 0
        assert sut(StreamWriter).written_count == 0
        return ret

    @transition(name="unread_count")
    def unread_count(self) -> int:
        """Verify the unread count queried from the real SUT is non-negative."""
        target: StreamBuffer = sut(StreamBuffer)
        ret = call_target(target.unread_count)
        assert ret >= 0
        return ret

    @transition(name="has_data")
    def has_data(self) -> bool:
        """Verify that has_data agrees with the unread count on the real SUT."""
        target: StreamBuffer = sut(StreamBuffer)
        ret = call_target(target.has_data)
        assert ret == (sut(StreamReader).unread_count > 0)
        return ret

    @transition(name="written_count")
    def written_count(self) -> int:
        """Verify the written count queried from the real SUT is non-negative."""
        target: StreamBuffer = sut(StreamBuffer)
        ret = call_target(target.written_count)
        assert ret >= 0
        return ret


proto = StreamBufferPseudoStateMachine()


# ==============================================================================
# 2. Real Implementation Tests
# ==============================================================================

class TestStreamBufferImplReal(unittest.TestCase):
    """Verifies that the concrete stream buffer satisfies its contracts."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.phase_scope = enter_phase(system, registry=self.registry)
        self.phase_scope.__enter__()
        self.real = get_singleton(StreamBuffer)
        self.sm = StreamBufferPseudoStateMachine(
            singletons={
                StreamBuffer: self.real,
                StreamReader: self.real,
                StreamWriter: self.real,
            }
        )
        self.checked = self.sm.as_checked(StreamBuffer, self.real)

    def tearDown(self) -> None:
        self.phase_scope.__exit__(None, None, None)

    def test_read_empty_buffer_returns_none(self) -> None:
        assert self.checked.read() is None
        assert self.checked.unread_count == 0
        assert not self.checked.has_data

    def test_write_then_read_roundtrip(self) -> None:
        self.checked.write("alpha")
        self.checked.write("beta")
        assert self.checked.written_count == 2
        assert self.checked.unread_count == 2
        assert self.checked.has_data
        assert self.checked.read() == "alpha"
        assert self.checked.read() == "beta"
        assert self.checked.read() is None
        assert self.checked.unread_count == 0
        assert not self.checked.has_data
        assert self.checked.written_count == 2

    def test_clear_resets_buffer_and_counts(self) -> None:
        self.checked.write("alpha")
        self.checked.write("beta")
        assert self.checked.unread_count == 2
        self.checked.clear()
        assert self.checked.unread_count == 0
        assert self.checked.written_count == 0
        assert self.checked.read() is None

    def test_write_empty_payload_is_rejected_without_buffering(self) -> None:
        self.checked.write("alpha")
        assert self.checked.written_count == 1
        with self.assertRaises(PayloadEmptyError):
            self.checked.write("")
        assert self.checked.written_count == 1
        assert self.checked.unread_count == 1
        assert self.checked.read() == "alpha"


# ==============================================================================
# 3. Real Hypothesis Fuzzing
# ==============================================================================

def make_sut() -> StreamBuffer:
    registry = LifecycleRegistry()
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(StreamBuffer)


StreamBufferFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=StreamWriterState,
    name="StreamBufferFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T18:02:20Z
# LAST_CHANGED: 2026-11-08T18:01:56Z
# CHANGE: Resolved empty-payload rejection coverage starvation: TestStreamBufferImplReal now includes a fixed scenario test that drives an empty payload write through the checked oracle expecting PayloadEmptyError, then verifies the written count and unread count are unchanged and the previously written payload remains readable, exercising the transition's contracted empty-payload rejection branch.
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T18:02:20Z
# PRETENSE_QA_AUDIT: 2026-11-08T18:02:07Z
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
    raises,
    require,
    require_arg,
    sut,
    sut_state,
    synthesize_fake,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from benchmark_4.parts.multi_interface.lib.stream_reader import StreamReader


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches, parameter validation, and contracted exception handling
# live naturally inside the single transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real calls).


@dataclass
class StreamReaderState:
    """Canonical model state for StreamReader operations."""

    items: list[str] = field(default_factory=list)


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
        """Pop and return the oldest unread payload, or None when the stream is empty."""
        oldest: Optional[str] = (
            self.state.items.pop(0) if len(self.state.items) > 0 else None
        )
        ret: Optional[str] = self.inner_read()
        assert ret == oldest
        return ret

    @transition(name="unread_count")
    def unread_count(self) -> int:
        """Return the number of unread payloads remaining in the stream."""
        ret: int = self.inner_unread_count()
        assert ret == len(self.state.items)
        return ret

    @transition(name="has_data")
    def has_data(self) -> bool:
        """Return whether unread payloads remain available in the stream."""
        ret: bool = self.inner_has_data()
        assert ret == (len(self.state.items) > 0)
        return ret

    @transition.seeding
    def seed_payload(self, payload: str) -> None:
        """Seed an unread payload so non-empty stream states become reachable."""
        require_arg(payload, Domain.type(str))
        self.state.items.append(payload)


proto = StreamReaderStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeStreamReader = synthesize_fake(StreamReaderStateMachine)


def make_stream_reader_fake(
    state: Optional[StreamReaderState] = None,
) -> StreamReader:
    """Synthesizes fake instance for StreamReader."""
    return FakeStreamReader(state=state or StreamReaderState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestStreamReaderFake(unittest.TestCase):
    """Fixed scenarios exercising every StreamReader transition on the synthesized fake."""

    def setUp(self) -> None:
        self.model = StreamReaderState()
        self.fake = make_stream_reader_fake(self.model)
        self.sm = StreamReaderStateMachine(state=self.model)

    def test_read_empty_stream_returns_none(self) -> None:
        assert self.fake.read() is None
        assert self.fake.unread_count == 0
        assert not self.fake.has_data

    def test_seed_payload_makes_data_available(self) -> None:
        self.sm.seed_payload("alpha")
        assert self.fake.unread_count == 1
        assert self.fake.has_data

    def test_read_pops_oldest_payload_first(self) -> None:
        self.sm.seed_payload("alpha")
        self.sm.seed_payload("beta")
        assert self.fake.unread_count == 2
        assert self.fake.has_data
        assert self.fake.read() == "alpha"
        assert self.fake.read() == "beta"
        assert self.fake.read() is None
        assert self.fake.unread_count == 0
        assert not self.fake.has_data


# ==============================================================================
# 4. Fake Hypothesis Fuzzing
# ==============================================================================

StreamReaderFakeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=StreamReaderState,
    name="StreamReaderFakeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:53:47Z
# LAST_CHANGED: 2026-11-08T17:53:47Z
# CHANGE: Implemented StreamReader interface pretense: items-list model state with 1:1 read/unread_count/has_data transitions using pivots, seed_payload seeding transition, synthesized FakeStreamReader plus fixed TestStreamReaderFake covering all transitions/seeding, and StreamReaderFakeFuzzTest hypothesis suite; package-qualified imports.
# --- END AUTOFAB METADATA ---


# === File: stream_writer_pretense.py ===
"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for StreamWriter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import unittest

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
from benchmark_4.parts.multi_interface.lib.stream_writer import StreamWriter
from benchmark_4.parts.multi_interface.pretense.stream_reader_pretense import (
    StreamReaderState,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================
# NOTE: Transitions model target methods 1:1 (@transition(TargetClass.method)).
# Operational branches, parameter validation, and contracted exception handling
# live naturally inside the single transition body (multi-transition splitting is prohibited).
# require_arg defines the caller precondition contract (checked at runtime on real calls).


@dataclass
class StreamWriterState(StreamReaderState):
    """Canonical model state for StreamWriter operations.

    Extends the shared stream state so that a single model tracks both buffered
    payloads and the cumulative written payloads since the last clear.
    """

    written: list[str] = field(default_factory=list)


class StreamWriterStateMachine(StateMachine[StreamWriterState]):
    """Unified Pretense State Machine for StreamWriter."""

    def __init__(
        self,
        state: Optional[StreamWriterState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or StreamWriterState(), singletons=singletons)

    @transition(StreamWriter.write)
    def write(self, payload: str) -> None:
        """Buffer a non-empty payload; an empty payload is never buffered."""
        require_arg(payload, Domain.type(str))
        ret = self.inner_write(payload)
        assert ret is None
        if len(payload) == 0:
            return ret
        self.state.items.append(payload)
        self.state.written.append(payload)
        return ret

    @transition(StreamWriter.clear)
    def clear(self) -> None:
        """Purge all buffered payloads and reset the written payload count."""
        self.state.items.clear()
        self.state.written.clear()
        ret = self.inner_clear()
        assert ret is None
        return ret

    @transition(name="written_count")
    def written_count(self) -> int:
        """Return the cumulative count of payloads written since the last clear."""
        ret: int = self.inner_written_count()
        assert ret == len(self.state.written)
        return ret

    @transition.seeding
    def seed_written(self, payload: str) -> None:
        """Seed an already-written payload so non-empty writer states become reachable."""
        require_arg(payload, Domain.type(str))
        if len(payload) == 0:
            return
        self.state.items.append(payload)
        self.state.written.append(payload)


proto = StreamWriterStateMachine()


# ==============================================================================
# 2. State Machine Proto & Fakes
# ==============================================================================

FakeStreamWriter = synthesize_fake(StreamWriterStateMachine)


def make_stream_writer_fake(
    state: Optional[StreamWriterState] = None,
) -> StreamWriter:
    """Synthesizes fake instance for StreamWriter."""
    return FakeStreamWriter(state=state or StreamWriterState())


# ==============================================================================
# 3. Fixed Scenarios on Fake
# ==============================================================================

class TestStreamWriterFake(unittest.TestCase):
    """Fixed scenarios exercising every StreamWriter transition on the synthesized fake."""

    def setUp(self) -> None:
        self.model = StreamWriterState()
        self.fake = make_stream_writer_fake(self.model)
        self.sm = StreamWriterStateMachine(state=self.model)

    def test_write_increments_written_count(self) -> None:
        self.fake.write("alpha")
        assert self.fake.written_count == 1
        self.fake.write("beta")
        assert self.fake.written_count == 2

    def test_clear_resets_written_count(self) -> None:
        self.fake.write("alpha")
        assert self.fake.written_count == 1
        self.fake.clear()
        assert self.fake.written_count == 0

    def test_seed_written_buffers_payloads(self) -> None:
        self.sm.seed_written("alpha")
        self.sm.seed_written("beta")
        assert self.fake.written_count == 2


# ==============================================================================
# 4. Fake Hypothesis Fuzzing
# ==============================================================================

StreamWriterFakeFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    initial_state_factory=StreamWriterState,
    name="StreamWriterFakeFuzzTest",
)

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T17:58:47Z
# LAST_CHANGED: 2026-11-08T17:58:47Z
# CHANGE: Resolved empty-payload state-model feedback: StreamWriter.write now evaluates its inner_transition pivot and returns immediately for an empty payload so nothing is appended to the modeled items/written lists, keeping model state and derived written_count/unread_count/has_data/read observations consistent with the SUT for the contracted empty-payload branch; seed_written sibling transition audited and given the same empty-payload guard.
# --- END AUTOFAB METADATA ---
