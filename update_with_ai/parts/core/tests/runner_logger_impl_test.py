"""Unit tests for runner_logger_impl per its grounding specification."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.core.lib.runner_logger import (
    EventName,
    EventSummary,
    EventTranscript,
    RunnerLogEvent,
)
from update_with_ai.parts.core.lib.runner_logger_impl import (
    RunnerLogger,
    __initialize__,
)


class RunnerLoggerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "events.log")
        self.orig_log_path = os.environ.get("TRANSCRIPT_LOG_PATH")
        os.environ["TRANSCRIPT_LOG_PATH"] = self.log_file
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def tearDown(self) -> None:
        if self.orig_log_path is not None:
            os.environ["TRANSCRIPT_LOG_PATH"] = self.orig_log_path
        else:
            os.environ.pop("TRANSCRIPT_LOG_PATH", None)
        shutil.rmtree(self.test_dir, ignore_errors=True)
        if os.path.isfile("agent_loop.log"):
            try:
                os.remove("agent_loop.log")
            except OSError:
                pass

    def test_log_event_dataclass(self) -> None:
        """CUJ: Instantiate structured log event records with all attributes."""
        event = RunnerLogEvent(
            event_name=EventName("test_event"),
            summary=EventSummary("short summary"),
            transcript=EventTranscript("detailed transcript line"),
        )
        self.assertEqual(event.event_name, "test_event")
        self.assertEqual(event.summary, "short summary")
        self.assertEqual(event.transcript, "detailed transcript line")

    def test_log_unbuffered_disk_writes(self) -> None:
        """CUJ: Logging structured events to an unbuffered disk transcript file."""
        with enter_phase(system, registry=self.registry) as scope:
            logger = scope.get_singleton(RunnerLogger)
            # Requirement: Consuming a runner log event writes an unbuffered verbose record to the transcript log file.
            # Requirement: MUST write unbuffered verbose entries to the transcript log file.
            logger.consume(
                RunnerLogEvent(
                    event_name=EventName("start"),
                    summary=EventSummary("Cleaning pass start"),
                    transcript=EventTranscript("Full transcript line 1"),
                )
            )
            logger.consume(
                RunnerLogEvent(
                    event_name=EventName("finish"),
                    summary=EventSummary("Cleaning pass finish"),
                    transcript=EventTranscript("Full transcript line 2"),
                )
            )

        self.assertTrue(os.path.isfile(self.log_file))
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Full transcript line 1", content)
        self.assertIn("Full transcript line 2", content)

    def test_log_prints_summary_to_stdout(self) -> None:
        """CUJ: Emitting real-time progress summaries to standard output."""
        with enter_phase(system, registry=self.registry) as scope:
            logger = scope.get_singleton(RunnerLogger)
            event = RunnerLogEvent(
                event_name=EventName("step"),
                summary=EventSummary("Executed step 1"),
                transcript=EventTranscript("Detailed step 1 logs"),
            )

            stdout_capture = io.StringIO()
            with contextlib.redirect_stdout(stdout_capture):
                # Requirement: Consuming a runner log event writes a single-line compact summary to standard output.
                # Requirement: MUST write a single-line summary to standard output.
                logger.consume(event)

            output = stdout_capture.getvalue()
            self.assertIn("Executed step 1", output)

    def test_clears_existing_log_file_at_initialization(self) -> None:
        """CUJ: Resetting prior transcript logs upon session initialization."""
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("Old previous run log content\n")
        with enter_phase(system, registry=self.registry) as scope:
            # Requirement: MUST clear any existing transcript log file at initialization.
            # Requirement: The runner logger clears any existing transcript log file at initialization.
            logger = scope.get_singleton(RunnerLogger)
            logger.initialize()
        with open(self.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, "")

    def test_default_log_path(self) -> None:
        """CUJ: Resolving default transcript log file when environment variable is not set."""
        os.environ.pop("TRANSCRIPT_LOG_PATH", None)
        default_file = "agent_loop.log"
        with open(default_file, "w", encoding="utf-8") as f:
            f.write("Stale content\n")

        registry = LifecycleRegistry()
        __initialize__(registry)
        with enter_phase(system, registry=registry) as scope:
            logger = scope.get_singleton(RunnerLogger)
            # Requirement: MUST resolve the transcript log destination from configured environment variables when present, defaulting to 'agent_loop.log'.
            # Requirement: The transcript log file destination defaults to `agent_loop.log` or is resolved from configured environment variables.
            logger.initialize()

        with open(default_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, "")


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
