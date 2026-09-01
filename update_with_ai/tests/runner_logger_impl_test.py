"""Tests for runner_logger_impl derived from LLS."""

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from lib.runner_logger import LogEvent
from lib.runner_logger_impl import RunnerLoggerImpl


class RunnerLoggerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "events.log")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)
        # Cleanup default log file if created in current working directory
        if os.path.isfile("agent_loop.log"):
            try:
                os.remove("agent_loop.log")
            except OSError:
                pass

    def test_log_event_dataclass(self) -> None:
        """Tests Data Types: LogEvent dataclass instantiation and fields."""
        event = LogEvent(
            name="test_event",
            summary="short summary",
            transcript="detailed transcript line",
        )
        self.assertEqual(event.name, "test_event")
        self.assertEqual(event.summary, "short summary")
        self.assertEqual(event.transcript, "detailed transcript line")

    def test_log_unbuffered_disk_writes(self) -> None:
        """Tests CUJ for logging structured events to an unbuffered disk transcript file.

        Checks postconditions: writes full transcript entries immediately to disk.
        """
        logger = RunnerLoggerImpl(transcript_file_path=self.log_file)
        logger.log(LogEvent(name="start", summary="Cleaning pass start", transcript="Full transcript line 1"))
        logger.log(LogEvent(name="finish", summary="Cleaning pass finish", transcript="Full transcript line 2"))

        self.assertTrue(os.path.isfile(self.log_file))
        with open(self.log_file) as f:
            content = f.read()
        self.assertIn("Full transcript line 1", content)
        self.assertIn("Full transcript line 2", content)

    def test_log_prints_summary_to_stdout(self) -> None:
        """Tests that logger prints single-line compact event summary directly to standard output."""
        logger = RunnerLoggerImpl(transcript_file_path=self.log_file)
        event = LogEvent(name="step", summary="Executed step 1", transcript="Detailed step 1 logs")

        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            logger.log(event)

        output = stdout_capture.getvalue()
        self.assertIn("Executed step 1", output)

    def test_clears_existing_log_file_at_initialization(self) -> None:
        """Tests that RunnerLoggerImpl clears pre-existing transcript log file content upon initialization."""
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("Old previous run log content\n")
        _ = RunnerLoggerImpl(transcript_file_path=self.log_file)
        with open(self.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, "")

    def test_default_initialization_logs_event(self) -> None:
        """Tests initializing RunnerLoggerImpl without explicit transcript_file_path logs events successfully."""
        logger = RunnerLoggerImpl()
        logger.log(LogEvent(name="info", summary="Default summary", transcript="Default transcript line"))


if __name__ == "__main__":
    unittest.main()
