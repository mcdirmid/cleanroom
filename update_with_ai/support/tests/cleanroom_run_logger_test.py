#!/usr/bin/env python3
"""cleanroom_run_logger_test.py — Unit tests for cleanroom_run_logger.py."""

import json
import os
import shutil
import tempfile
import unittest

from update_with_ai.support.lib import cleanroom_run_logger


class CleanroomRunLoggerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.workspace_root = os.path.join(self.test_dir, "workspace")
        os.makedirs(self.workspace_root, exist_ok=True)
        self.cleanroom_dir = os.path.join(self.workspace_root, ".cleanroom")
        os.environ["CLEANROOM_DIR_OVERRIDE"] = self.cleanroom_dir

    def tearDown(self) -> None:
        if "CLEANROOM_DIR_OVERRIDE" in os.environ:
            del os.environ["CLEANROOM_DIR_OVERRIDE"]
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sanitize_helpers(self) -> None:
        # Pipe escaping and newline handling
        raw = "Line 1|col\nLine 2"
        sanitized = cleanroom_run_logger.sanitize_table_cell(raw)
        self.assertEqual(sanitized, r"Line 1\|col <br> Line 2")

        # Slug generation
        slug = cleanroom_run_logger.sanitize_slug("//testing/parts/sandbox:sandbox_asm_qa")
        self.assertEqual(slug, "testing_parts_sandbox_sandbox_asm_qa")

    def test_get_or_create_active_run(self) -> None:
        run = cleanroom_run_logger.get_or_create_active_run(
            target="//testing/parts/sandbox:sandbox_asm_qa",
            workspace_root=self.workspace_root,
        )
        self.assertIsNotNone(run)
        self.assertTrue(os.path.isdir(run["run_dir"]))
        self.assertTrue(os.path.isdir(run["transcripts_dir"]))
        self.assertTrue(os.path.isfile(run["timeline_md"]))
        self.assertTrue(os.path.isfile(run["timeline_log"]))

        # Check 'latest' symlink
        runs_dir = os.path.join(self.cleanroom_dir, "runs")
        latest_link = os.path.join(runs_dir, "latest")
        self.assertTrue(os.path.islink(latest_link))
        self.assertEqual(os.path.realpath(latest_link), os.path.realpath(run["run_dir"]))

        # Check timeline.md header
        with open(run["timeline_md"], "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Cleanroom Convergence Run", content)
            self.assertIn("//testing/parts/sandbox:sandbox_asm_qa", content)
            self.assertIn("| Time | Agent | Event | Details |", content)

        # Calling again returns the active run
        run2 = cleanroom_run_logger.get_or_create_active_run(workspace_root=self.workspace_root)
        self.assertEqual(run["run_id"], run2["run_id"])

    def test_log_event(self) -> None:
        run = cleanroom_run_logger.get_or_create_active_run(
            target="//pkg:target",
            workspace_root=self.workspace_root,
        )
        cleanroom_run_logger.log_event(
            event_type="SPAWN",
            agent="coordinator",
            details="Spawned Worker s_1 for role //update_python_with_ai:lib",
            links="[transcript](transcripts/01_lib.jsonl)",
            workspace_root=self.workspace_root,
        )

        with open(run["timeline_md"], "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("| `coordinator` | `SPAWN` | Spawned Worker s_1", content)
            self.assertIn("[transcript](transcripts/01_lib.jsonl)", content)

        with open(run["timeline_log"], "r", encoding="utf-8") as f:
            log_content = f.read()
            self.assertIn("[coordinator] SPAWN: Spawned Worker s_1", log_content)

    def test_register_transcript_symlink(self) -> None:
        run = cleanroom_run_logger.get_or_create_active_run(
            target="//pkg:target",
            workspace_root=self.workspace_root,
        )
        # Create fake brain transcript
        fake_brain = os.path.join(self.test_dir, "brain")
        conv_id = "test-conv-uuid-1234"
        logs_dir = os.path.join(fake_brain, conv_id, ".system_generated", "logs")
        os.makedirs(logs_dir, exist_ok=True)
        transcript_file = os.path.join(logs_dir, "transcript.jsonl")
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write('{"step": 1}\n')

        rel_link = cleanroom_run_logger.register_transcript(
            conversation_id=conv_id,
            label="01_wave1_lib",
            workspace_root=self.workspace_root,
            brain_roots=[fake_brain],
        )
        self.assertEqual(rel_link, "transcripts/01_wave1_lib.jsonl")

        symlink_path = os.path.join(run["transcripts_dir"], "01_wave1_lib.jsonl")
        self.assertTrue(os.path.islink(symlink_path))
        self.assertEqual(os.path.realpath(symlink_path), os.path.realpath(transcript_file))

    def test_finish_run(self) -> None:
        run = cleanroom_run_logger.get_or_create_active_run(
            target="//pkg:target",
            workspace_root=self.workspace_root,
        )
        summary = {
            "total_turns": 55,
            "waves": 2,
            "is_complete": True,
        }
        res = cleanroom_run_logger.finish_run(
            status="CONVERGED",
            summary=summary,
            workspace_root=self.workspace_root,
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["status"], "CONVERGED")
        self.assertEqual(res["total_turns"], 55)

        # Check summary.json
        summary_path = os.path.join(run["run_dir"], "summary.json")
        self.assertTrue(os.path.isfile(summary_path))
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["status"], "CONVERGED")
            self.assertEqual(data["waves"], 2)

        # Check timeline.md closing note
        with open(run["timeline_md"], "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Run Finalized: `CONVERGED`", content)

        # active_run.json removed
        self.assertIsNone(cleanroom_run_logger.get_active_run(self.workspace_root))


if __name__ == "__main__":
    unittest.main()
