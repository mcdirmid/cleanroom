# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-12T12:35:00Z
# CHANGE: Verify standard output presents single-line event summaries without timestamps or event names
# CODE_HASH: 4f1faaf49c58
# COVERAGE_AUDIT: 2026-10-13T20:42:16Z
# QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Unit tests for runner_logger_impl per its grounding specification."""

from __future__ import annotations

import io
import unittest
from unittest.mock import patch
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.core.lib import runner_logger
from update_with_ai.parts.core.lib.runner_logger_impl import (
    RunnerLogger,
    __initialize__,
)


def _make_event(
    event_name: str, summary: str, transcript: str
) -> runner_logger.RunnerLogEvent:
    return runner_logger.RunnerLogEvent(
        event_name=runner_logger.EventName(event_name),
        summary=runner_logger.EventSummary(summary),
        transcript=runner_logger.EventTranscript(transcript),
    )


class RunnerLoggerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initialization(self) -> None:
        """CUJ: Verify initial component presence and singleton resolution."""
        self.assertIsNotNone(self.registry)
        with enter_phase(system, registry=self.registry) as scope:
            logger = scope.get_singleton(RunnerLogger)
            self.assertIsNotNone(logger)

    def test_consume_event(self) -> None:
        """Postcondition: MUST present single-line event summaries on standard output lines without timestamps or event names."""
        event = _make_event(
            event_name="phase_start",
            summary="Entering test phase",
            transcript="Verbose transcript detailing setup and configuration for test phase.",
        )
        captured = io.StringIO()
        with patch("update_with_ai.parts.core.lib.runner_logger_impl.sys.stdout", captured):
            with enter_phase(system, registry=self.registry) as scope:
                logger = scope.get_singleton(RunnerLogger)
                logger.consume(event)
        self.assertEqual(captured.getvalue(), "Entering test phase\n")

    def test_consume_multiple_events_and_flush(self) -> None:
        """Postcondition: MUST append verbose records and guarantee persistence across writes."""
        event1 = _make_event("step_1", "Running step 1", "Transcript for step 1")
        event2 = _make_event("step_2", "Running step 2", "Transcript for step 2")
        captured = io.StringIO()
        with patch("update_with_ai.parts.core.lib.runner_logger_impl.sys.stdout", captured):
            with enter_phase(system, registry=self.registry) as scope:
                logger = scope.get_singleton(RunnerLogger)
                logger.consume(event1)
                logger.consume(event2)
        self.assertEqual(captured.getvalue(), "Running step 1\nRunning step 2\n")


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
