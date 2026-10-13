# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-13T09:50:00Z
# CHANGE: author goose_harness_impl unit tests
# CODE_HASH: 308a52283e87
# COVERAGE_AUDIT: 2026-10-13T20:42:16Z
# QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Unit tests for goose_harness_impl."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Sequence

from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.goose.lib import goose_harness
from update_with_ai.parts.goose.lib.goose_harness_impl import (
    GooseHarnessAdapter,
    GooseHarnessManager,
    GooseTelemetryParser,
    __initialize__,
)
from update_with_ai.parts.subagent.lib import subagent_coordinator
from update_with_ai.parts.workspace.lib import workspace_work


class FakeWorkspaceWorkManager:
    """Test double implementing WorkspaceWorkManager for goose harness tests."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.pending: Dict[str, List[str]] = {}

    def get_pending_work(self, workspace_dir: str) -> List[str]:
        return list(self.pending.get(workspace_dir, []))

    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        self.pending[workspace_dir] = list(targets)

    def clear_pending_work(self, workspace_dir: str) -> None:
        self.pending.pop(workspace_dir, None)

    def remove_pending_target(self, workspace_dir: str, target: str) -> bool:
        items = self.pending.get(workspace_dir, [])
        if target in items:
            items.remove(target)
            return True
        return False


def _create_mock_sessions_db(db_path: str) -> None:
    """Creates a mock SQLite sessions database conforming to goose_ext."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                working_dir TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cache_read_tokens INTEGER,
                accumulated_cost REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE usage_ledger (
                session_id TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cache_read_tokens INTEGER,
                cost REAL
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO sessions (id, name, working_dir, input_tokens, output_tokens, cache_read_tokens, accumulated_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("sess_test_1", "turn_1", "/tmp/ws", 1200, 300, 400, 0.045),
        )
        cursor.execute(
            """
            INSERT INTO usage_ledger (session_id, input_tokens, output_tokens, cache_read_tokens, cost)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("sess_test_1", 1200, 300, 400, 0.045),
        )
        conn.commit()


class GooseHarnessImplTest(unittest.TestCase):
    """Test cases for GooseTelemetryParser, GooseHarnessAdapter, and GooseHarnessManager."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.work_mgr = FakeWorkspaceWorkManager()
        self.registry.register_instance(
            self.work_mgr,
            keys=[workspace_work.WorkspaceWorkManager],
            tier=agent_session.agent_session,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_session_db(self) -> None:
        """Requirement: MUST query sessions and usage_ledger tables for recorded tokens and cost."""
        db_path = os.path.join(self.test_dir, "sessions.db")
        _create_mock_sessions_db(db_path)

        parser = GooseTelemetryParser()
        metrics = parser.parse_session_db(
            sessions_db_path=db_path,
            session_name="turn_1",
            model_name="claude-3-5-sonnet",
        )

        self.assertEqual(metrics.input_tokens, 1200)
        self.assertEqual(metrics.cached_tokens, 400)
        self.assertEqual(metrics.output_tokens, 300)
        self.assertEqual(metrics.total_tokens, 1900)
        self.assertAlmostEqual(metrics.cost_usd, 0.045, places=3)
        self.assertEqual(metrics.model_name, "claude-3-5-sonnet")

    def test_parse_log_text(self) -> None:
        """Requirement: MUST parse token counts from log text and calculate cost_usd."""
        log_sample = (
            "Starting agent run...\n"
            "Input tokens: 2500\n"
            "Cached tokens: 1000\n"
            "Output tokens: 500\n"
            "Cost: $0.035\n"
            "Finished run cleanly."
        )
        parser = GooseTelemetryParser()
        metrics = parser.parse_log_text(log_sample, model_name="gpt-4o")

        self.assertEqual(metrics.input_tokens, 2500)
        self.assertEqual(metrics.cached_tokens, 1000)
        self.assertEqual(metrics.output_tokens, 500)
        self.assertEqual(metrics.total_tokens, 4000)
        self.assertAlmostEqual(metrics.cost_usd, 0.035, places=3)

    def test_dispatch_and_await_clean(self) -> None:
        """Requirement: MUST initiate turn and return role turn result with submitted targets upon clean execution."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = GooseHarnessAdapter(simulation_mode=True)
            self.work_mgr.set_pending_work(self.test_dir, ["lib/a.py", "lib/b.py"])

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="update_with_ai/parts/goose",
                ready_targets=("lib/a.py", "lib/b.py"),
            )
            handle = adapter.dispatch_role(dispatch)
            self.assertTrue(handle.startswith("goose_lib_"))

            # Simulate subagent completing lib/a.py
            self.work_mgr.set_pending_work(self.test_dir, ["lib/b.py"])

            result = adapter.await_role(handle)
            self.assertEqual(result.status, "clean")
            self.assertEqual(result.role, "lib")
            self.assertEqual(result.submitted_targets, ("lib/a.py",))
            self.assertEqual(result.blamed_targets, ())

    def test_await_blamed_target(self) -> None:
        """Requirement: MUST inspect blame buffer and mark turn as blamed with blamed targets."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = GooseHarnessAdapter(simulation_mode=True)
            self.work_mgr.set_pending_work(self.test_dir, ["lib/a.py"])

            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="update_with_ai/parts/goose",
                ready_targets=("lib/a.py",),
            )
            handle = adapter.dispatch_role(dispatch)

            # Write blame buffer record
            blame_file = os.path.join(self.test_dir, ".cleanroom_blame_buffer.json")
            with open(blame_file, "w", encoding="utf-8") as f:
                json.dump([{"culprit_target": "low/a.pyi", "reason": "Missing contract"}], f)

            result = adapter.await_role(handle)
            self.assertEqual(result.status, "blamed")
            self.assertEqual(result.blamed_targets, ("low/a.pyi",))

    def test_process_failure(self) -> None:
        """Requirement: MUST handle execution failure and return failed status."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = GooseHarnessAdapter(
                custom_cmd="exit 42",
                simulation_mode=False,
            )
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="update_with_ai/parts/goose",
                ready_targets=(),
            )
            handle = adapter.dispatch_role(dispatch)
            result = adapter.await_role(handle)

            self.assertEqual(result.status, "failed")
            self.assertIsNotNone(result.failure_reason)
            self.assertIn("42", str(result.failure_reason))

    def test_process_timeout(self) -> None:
        """Requirement: MUST enforce execution timeout, terminate process, and return failed status."""
        with enter_phase(agent_session.agent_session, registry=self.registry):
            adapter = GooseHarnessAdapter(
                custom_cmd="sleep 5",
                timeout_seconds=0.1,
                simulation_mode=False,
            )
            dispatch = subagent_coordinator.RoleDispatch(
                role_name="lib",
                workspace_dir=self.test_dir,
                dir_scope="update_with_ai/parts/goose",
                ready_targets=(),
            )
            handle = adapter.dispatch_role(dispatch)
            result = adapter.await_role(handle)

            self.assertEqual(result.status, "failed")
            self.assertIsNotNone(result.failure_reason)
            self.assertIn("timed out", str(result.failure_reason))

    def test_harness_manager(self) -> None:
        """Requirement: MUST create configured Goose harness adapter and telemetry parser."""
        with enter_phase(agent_session.agent_session, registry=self.registry) as scope:
            manager = scope.get_singleton(goose_harness.GooseHarnessManager)
            adapter = manager.create_harness_adapter(
                model_name="claude-3-5-sonnet",
                timeout_seconds=300.0,
            )
            self.assertIsInstance(adapter, GooseHarnessAdapter)
            parser = manager.get_telemetry_parser()
            self.assertIsInstance(parser, GooseTelemetryParser)


if __name__ == "__main__":
    unittest.main()
