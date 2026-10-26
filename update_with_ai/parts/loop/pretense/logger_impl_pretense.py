"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for RunnerLogger."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from support.lib.lifecycle import LifecycleRegistry
from update_with_ai.parts.loop.lib import logger, logger_impl
from update_with_ai.parts.loop.lib.logger import (
    EventName,
    EventSummary,
    EventTranscript,
    RunnerLogEvent,
    RunnerLogger,
)


@dataclass
class RunnerLoggerState:
    """Canonical model state for RunnerLogger."""
    events: List[RunnerLogEvent] = field(default_factory=list)


proto = StateMachineProto[RunnerLoggerState]()


# ==============================================================================
# 1. RunnerLogger Transitions
# ==============================================================================

@proto.transition(RunnerLogger.consume)
def consume(): pass

@consume.arguments
def _(
    state: RunnerLoggerState,
    this: Any,
    event: RunnerLogEvent | NotBoundType = NotBound,
) -> Optional[Tuple[RunnerLogEvent]]:
    if isinstance(event, NotBoundType):
        ev = RunnerLogEvent(
            event_name=EventName("step"),
            summary=EventSummary("Executed step 1"),
            transcript=EventTranscript("Tool invocation transcript"),
        )
    else:
        ev = event
    return (ev,)

@consume.provide
def _(
    state: RunnerLoggerState,
    this: Any,
    event: RunnerLogEvent,
    result: None = None,
) -> None:
    state.events.append(event)


# ==============================================================================
# 2. Helper Factory
# ==============================================================================

def make_runner_logger_fake(state: Optional[RunnerLoggerState] = None) -> RunnerLogger:
    """Instantiate a synthesized RunnerLogger fake."""
    st = state or RunnerLoggerState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(RunnerLogger)


# ==============================================================================
# 3. Unit Tests
# ==============================================================================

class TestRunnerLoggerUnit(unittest.TestCase):
    """Unit tests for synthesized RunnerLogger fake."""

    def test_consume_records_event(self) -> None:
        state = RunnerLoggerState()
        fake = make_runner_logger_fake(state)

        event = RunnerLogEvent(
            event_name=EventName("tool_start"),
            summary=EventSummary("Reading file"),
            transcript=EventTranscript("details"),
        )
        fake.consume(event)
        self.assertEqual(len(state.events), 1)
        self.assertEqual(state.events[0], event)


class TestRunnerLoggerReal(unittest.TestCase):
    """Direct verification of the real RunnerLogger implementation."""

    def test_real_consume_and_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            log_file = os.path.join(td, "test.log")
            old_env = os.environ.get("RUNNER_LOG_FILE")
            try:
                os.environ["RUNNER_LOG_FILE"] = log_file
                real_logger = logger_impl.RunnerLogger()

                event = RunnerLogEvent(
                    event_name=EventName("step_start"),
                    summary=EventSummary("Starting step 1"),
                    transcript=EventTranscript("Detailed trace"),
                )
                real_logger.consume(event)

                self.assertTrue(os.path.isfile(log_file))
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("Detailed trace", content)

                # Initialize
                reg = LifecycleRegistry()
                logger_impl.__initialize__(reg)
            finally:
                if old_env is not None:
                    os.environ["RUNNER_LOG_FILE"] = old_env
                else:
                    os.environ.pop("RUNNER_LOG_FILE", None)


# ==============================================================================
# 4. Hypothesis Fuzz Testing
# ==============================================================================

class TestRunnerLoggerFuzz(unittest.TestCase):
    """Property fuzz testing for RunnerLogger."""

    @settings(max_examples=30)
    @given(
        events=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz_"),
                st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz0123456789 "),
                st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz0123456789 \n"),
            ),
            min_size=1,
            max_size=10,
        )
    )
    def test_event_consumption_invariants(self, events: list[tuple[str, str, str]]) -> None:
        state = RunnerLoggerState()
        fake = make_runner_logger_fake(state)

        for name, summary, transcript in events:
            ev = RunnerLogEvent(
                event_name=EventName(name),
                summary=EventSummary(summary),
                transcript=EventTranscript(transcript),
            )
            fake.consume(ev)

        self.assertEqual(len(state.events), len(events))
        for i, (name, summary, transcript) in enumerate(events):
            self.assertEqual(state.events[i].event_name, name)
            self.assertEqual(state.events[i].summary, summary)
            self.assertEqual(state.events[i].transcript, transcript)
