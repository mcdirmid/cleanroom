"""Unit tests for runner_logger_impl aligned with grounding specifications."""

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.core.lib.runner_logger import LogEvent, RunnerLogger
from update_with_ai.parts.core.lib.runner_logger_impl import RunnerLogger as RunnerLoggerImpl, __initialize__


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
            os.remove("agent_loop.log")

    def test_log_event_dataclass(self) -> None:
        """CUJ: Instantiating structured log event records.

        Asserts LogEvent properties and values.
        """
        event = LogEvent(
            event_name="test_event",
            summary="short summary",
            transcript_representation="detailed transcript line",
        )
        self.assertEqual(event.event_name, "test_event")
        self.assertEqual(event.summary, "short summary")
        self.assertEqual(event.transcript_representation, "detailed transcript line")

    def test_log_unbuffered_disk_writes(self) -> None:
        """CUJ: Logging structured events to an unbuffered disk transcript file.

        Verifies that logging appends transcript entries directly to disk.
        """
        with enter_phase("system", registry=self.registry) as scope:
            logger = scope.get_singleton(RunnerLogger)
            # Requirement: Consuming a log event writes an unbuffered verbose record to the transcript log file.
            # Requirement: [RunnerLogger] The runner logger consumes log events, writing compact single-line summaries to standard output and full verbose records to a transcript log file.
            logger.consume(
                LogEvent(
                    event_name="start",
                    summary="Cleaning pass start",
                    transcript_representation="Full transcript line 1",
                )
            )
            logger.consume(
                LogEvent(
                    event_name="finish",
                    summary="Cleaning pass finish",
                    transcript_representation="Full transcript line 2",
                )
            )

        self.assertTrue(os.path.isfile(self.log_file))
        with open(self.log_file, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Full transcript line 1", content)
        self.assertIn("Full transcript line 2", content)

    def test_log_prints_summary_to_stdout(self) -> None:
        """CUJ: Emitting real-time progress summaries to standard output.

        Verifies that single-line compact event summaries are printed.
        """
        with enter_phase("system", registry=self.registry) as scope:
            logger = scope.get_singleton(RunnerLogger)
            event = LogEvent(
                event_name="step",
                summary="Executed step 1",
                transcript_representation="Detailed step 1 logs",
            )

            stdout_capture = io.StringIO()
            with contextlib.redirect_stdout(stdout_capture):
                # Requirement: Consuming a log event writes a single-line compact summary to standard output.
                # Requirement: [RunnerLogger] The runner logger consumes log events, writing compact single-line summaries to standard output and full verbose records to a transcript log file.
                logger.consume(event)

            output = stdout_capture.getvalue()
            self.assertIn("Executed step 1", output)

    def test_clears_existing_log_file_at_initialization(self) -> None:
        """CUJ: Resetting prior transcript logs upon session initialization.

        Verifies that initialize() clears pre-existing file content.
        """
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("Old previous run log content\n")
        with enter_phase("system", registry=self.registry) as scope:
            # Entering phase initializes singletons, clearing the file
            _ = scope.get_singleton(RunnerLogger)
        with open(self.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        # Requirement: The runner logger clears any existing transcript log file at initialization.
        self.assertEqual(content, "")

    def test_default_log_path(self) -> None:
        """CUJ: Resolving default transcript log file when environment variable is not set."""
        os.environ.pop("TRANSCRIPT_LOG_PATH", None)
        logger = RunnerLoggerImpl()
        # Requirement: The transcript log file destination defaults to `agent_loop.log` or is resolved from configured environment variables.
        self.assertEqual(logger.transcript_file_path, "agent_loop.log")


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - The runner logger intercepts termination signals to flush and close transcript log files.

