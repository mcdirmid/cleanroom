# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:50:00Z
# CHANGE: Test WorkspaceToolRunner CLI parsing and delegation to WorkspaceCommandHandler
# CODE_HASH: 8e8a67c5da24
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Unit tests for workspace_tool_impl."""

import io
import unittest
from contextlib import redirect_stdout
from typing import Any, List, Optional, Tuple

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_default_registry
from update_with_ai.parts.agent.lib import agent_session
from update_with_ai.parts.tools.lib import (
    workspace_commands,
    workspace_tool,
    workspace_tool_impl,
)


class FakeWorkspaceCommandHandler:
    """Test double implementing WorkspaceCommandHandler interface."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Any]] = []

    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> int:
        self.calls.append(("get_work", (dir_scope, repo_root, force, batch_size)))
        return 0

    def run_check_files(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        self.calls.append(("check_files", (target, repo_root)))
        if target == "error_target":
            return 1
        return 0

    def run_submit(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        no_verify: bool = False,
    ) -> int:
        self.calls.append(("submit", (target, summary, repo_root, no_verify)))
        return 0

    def run_blame(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
    ) -> int:
        self.calls.append(("blame", (culprit_file, critique, repo_root)))
        return 0

    def run_fail(
        self,
        file_path: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        self.calls.append(("fail", (file_path, reason, repo_root)))
        return 0

    def run_coverage(
        self,
        target: Optional[str] = None,
        impl: Optional[str] = None,
        test: Optional[str] = None,
        threshold: float = 0.0,
        update_log: Optional[str] = None,
        max_spans: Optional[int] = None,
        json_output: bool = False,
        repo_root: Optional[str] = None,
    ) -> int:
        self.calls.append(
            (
                "coverage",
                (
                    target,
                    impl,
                    test,
                    threshold,
                    update_log,
                    max_spans,
                    json_output,
                    repo_root,
                ),
            )
        )
        return 0

    def run_commission(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        custom_dest: Optional[str] = None,
        repo_root: Optional[str] = None,
        all_roles: bool = False,
        reset: bool = False,
        model: Optional[str] = None,
    ) -> int:
        self.calls.append(
            (
                "commission",
                (role_name, dir_scope, custom_dest, repo_root, all_roles, reset, model),
            )
        )
        return 0

    def run_refresh_sys(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        self.calls.append(("refresh_sys", (role_name, dir_scope, repo_root)))
        return 0


class WorkspaceToolImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.fake_cmds = FakeWorkspaceCommandHandler()
        self.registry.register_instance(
            self.fake_cmds,
            keys=[workspace_commands.WorkspaceCommandHandler],
            tier=agent_session.agent_session,
        )
        self.runner = workspace_tool_impl.WorkspaceToolRunner()
        self.registry.register_instance(
            self.runner,
            keys=[
                workspace_tool.WorkspaceToolRunner,
                workspace_tool_impl.WorkspaceToolRunner,
            ],
            tier=agent_session.agent_session,
        )
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_runner_execute_command_help(self) -> None:
        with self.assertRaises(SystemExit):
            self.runner.execute_command(["invalid_cmd"])

    def test_runner_get_work(self) -> None:
        ret = self.runner.execute_command(
            ["get_work", "staging", "--force", "--batch-size", "5"]
        )
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, args = self.fake_cmds.calls[0]
        self.assertEqual(name, "get_work")
        self.assertEqual(args[0], "staging")
        self.assertTrue(args[2])  # force
        self.assertEqual(args[3], 5)  # batch_size

    def test_runner_check_files(self) -> None:
        ret = self.runner.execute_command(["check_files", "lib/foo.py"])
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, args = self.fake_cmds.calls[0]
        self.assertEqual(name, "check_files")
        self.assertEqual(args[0], "lib/foo.py")

        ret_err = self.runner.execute_command(["check_files", "error_target"])
        self.assertEqual(ret_err, 1)

    def test_runner_submit(self) -> None:
        ret = self.runner.execute_command(
            ["submit", "lib/foo.py", "Implemented feature", "--no-verify"]
        )
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, args = self.fake_cmds.calls[0]
        self.assertEqual(name, "submit")
        self.assertEqual(args[0], "lib/foo.py")
        self.assertEqual(args[1], "Implemented feature")
        self.assertTrue(args[3])  # no_verify

    def test_runner_blame(self) -> None:
        ret = self.runner.execute_command(
            ["blame", "low/foo.pyi", "Spec missing parameter"]
        )
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, args = self.fake_cmds.calls[0]
        self.assertEqual(name, "blame")
        self.assertEqual(args[0], "low/foo.pyi")
        self.assertEqual(args[1], "Spec missing parameter")

    def test_runner_feedback_alias(self) -> None:
        ret = self.runner.execute_command(
            ["feedback", "low/foo.pyi", "Feedback critique"]
        )
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, args = self.fake_cmds.calls[0]
        self.assertEqual(name, "blame")
        self.assertEqual(args[0], "low/foo.pyi")
        self.assertEqual(args[1], "Feedback critique")

    def test_runner_fail(self) -> None:
        ret = self.runner.execute_command(
            ["fail", "lib/foo.py", "Compilation error"]
        )
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, args = self.fake_cmds.calls[0]
        self.assertEqual(name, "fail")
        self.assertEqual(args[0], "lib/foo.py")
        self.assertEqual(args[1], "Compilation error")

    def test_runner_coverage(self) -> None:
        ret = self.runner.execute_command(
            ["coverage", "lib/foo.py", "--threshold", "85.0"]
        )
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, args = self.fake_cmds.calls[0]
        self.assertEqual(name, "coverage")
        self.assertEqual(args[0], "lib/foo.py")
        self.assertEqual(args[3], 85.0)

    def test_runner_commission(self) -> None:
        ret = self.runner.execute_command(
            ["commission", "lib", "staging", "--reset", "--model", "gpt-4"]
        )
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, args = self.fake_cmds.calls[0]
        self.assertEqual(name, "commission")
        self.assertEqual(args[0], "lib")
        self.assertEqual(args[1], "staging")
        self.assertFalse(args[4])  # all_roles
        self.assertTrue(args[5])  # reset
        self.assertEqual(args[6], "gpt-4")

    def test_runner_refresh_sys(self) -> None:
        ret = self.runner.execute_command(["refresh-sys"])
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, _ = self.fake_cmds.calls[0]
        self.assertEqual(name, "refresh_sys")

    def test_runner_blame_with_repo_root(self) -> None:
        ret = self.runner.execute_command(
            ["blame", "low/foo.pyi", "Spec missing parameter", "--repo-root", "/repo"]
        )
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, args = self.fake_cmds.calls[0]
        self.assertEqual(name, "blame")
        self.assertEqual(args[0], "low/foo.pyi")
        self.assertEqual(args[1], "Spec missing parameter")
        self.assertEqual(args[2], "/repo")

    def test_runner_fail_with_repo_root(self) -> None:
        ret = self.runner.execute_command(
            ["fail", "lib/foo.py", "Compilation error", "--repo-root", "/repo"]
        )
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, args = self.fake_cmds.calls[0]
        self.assertEqual(name, "fail")
        self.assertEqual(args[0], "lib/foo.py")
        self.assertEqual(args[1], "Compilation error")
        self.assertEqual(args[2], "/repo")

    def test_runner_coverage_with_repo_root(self) -> None:
        ret = self.runner.execute_command(
            ["coverage", "lib/foo.py", "--threshold", "85.0", "--repo-root", "/repo"]
        )
        self.assertEqual(ret, 0)
        self.assertEqual(len(self.fake_cmds.calls), 1)
        name, args = self.fake_cmds.calls[0]
        self.assertEqual(name, "coverage")
        self.assertEqual(args[0], "lib/foo.py")
        self.assertEqual(args[7], "/repo")

    def test_main_entry_point(self) -> None:
        ret = workspace_tool_impl.main(["get_work"])
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
