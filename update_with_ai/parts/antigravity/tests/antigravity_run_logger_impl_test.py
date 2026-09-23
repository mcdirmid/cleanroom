from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from update_with_ai.parts.antigravity.lib.antigravity_run_logger_impl import AntigravityRunLogger


class AntigravityRunLoggerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.logger = AntigravityRunLogger()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_sanitize_slug(self) -> None:
        # Requirement: The antigravity run logger converts a role label into a safe identifier string.
        # Requirement: Sanitizing a slug transforms a role label into a safe identifier by stripping invalid characters and replacing whitespace with underscores.
        self.assertEqual(self.logger.sanitize_slug("Cleanroom Role Worker - qa"), "cleanroom_role_worker_qa")
        self.assertEqual(self.logger.sanitize_slug("//pkg:unit@name"), "pkg_unit_name")

    @patch.dict(os.environ, {}, clear=False)
    def test_log_event(self) -> None:
        # Requirement: The antigravity run logger records an event name, a source, and a summary for an execution action.
        # Requirement: Logging an event records an event name, a source, and a summary.
        # Requirement: The run logger formats the event record with an ISO timestamp and appends the entry to an active log file in the cleanroom directory.
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.tmpdir
        self.logger.log_event("SPAWN", "coordinator", "Spawning worker s_1")
        log_file = os.path.join(self.tmpdir, ".cleanroom", "run_events.log")
        self.assertTrue(os.path.exists(log_file))
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("[SPAWN]", content)
        self.assertIn("[coordinator]", content)
        self.assertIn("Spawning worker s_1", content)

    @patch.dict(os.environ, {}, clear=False)
    def test_register_transcript(self) -> None:
        # Requirement: The antigravity run logger associates a conversation identifier with a role slug.
        # Requirement: Registering a transcript links a conversation identifier with a role slug.
        # Requirement: The run logger creates a symbolic link or records the mapping to enable downstream telemetry collection across subagent runs.
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.tmpdir
        self.logger.register_transcript("conv-123", "worker_qa")
        map_file = os.path.join(self.tmpdir, ".cleanroom", "transcripts_map.json")
        self.assertTrue(os.path.exists(map_file))
        with open(map_file, "r", encoding="utf-8") as f:
            data = f.read()
        self.assertIn("conv-123", data)
        self.assertIn("worker_qa", data)


if __name__ == "__main__":
    unittest.main()
