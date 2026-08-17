"""
Tests for lib/bazel_runner_impl.py (BazRunnerImpl).

Asserts the behavioral contract from specs/bazel_runner_impl-low.md and its
dependencies (bazel_runner-low.md, dag-low.md, dag_storage-low.md,
dag_clean_logic-low.md, agent_loop-low.md):

- inject_feedback returns (True, NoChangeResult()) on success and stores the
  messages in the node's pending message store (.bazelharness.json in the package
  directory); returns (False, FailureResult()) for a nonexistent node without
  mutating any state.
- inject_feedback builds its own graph per call, and run_dag builds its own
  graph separately (no shared state across calls).
- run_dag drives a full cleaning pass: returns (True, NoChangeResult()) when
  the node cleans with no changes, consumes the node's pending messages, and
  writes/closes the agent log file. The log path follows the
  CLEANROOM_AGENT_LOG / BUILD_WORKSPACE_DIRECTORY / BUILD_WORKING_DIRECTORY
  priority; a root node with no manifest makes run_dag raise rather than
  return a result.
- run_dag forwards its config_target argument to the BazelAgentConfig
  component and constructs the agent loop from the returned AgentLoopConfig
  (no hardcoded model/URL/key in the runner). The component itself is tested
  separately in bazel_agent_config_impl_test.
- _format_compact_log emits one-line summaries exactly for tool_called,
  api_response, final_answer, run_terminated, and error events and None for
  all other events.
- _format_full_log produces a verbose line for every agent_loop LogEvent
  (message_added, message_stubbed, tool_called, tool_result, api_response,
  reminder_injected, final_answer, run_terminated, error).
"""

import contextlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from unittest.mock import patch

from update_with_ai.lib import bazel_runner_impl
from update_with_ai.lib.bazel_runner_impl import (
    BazRunnerImpl,
    _format_compact_log,
    _format_full_log,
)
from update_with_ai.lib.bazel_agent_config_impl import BazelAgentConfigImpl
from update_with_ai.lib.bazel_graph_storage import GraphConfig
from update_with_ai.lib.bazel_graph_storage_impl import BazelGraphStorageFileImpl
from update_with_ai.lib.agent_loop import AgentLoopConfig, FinalAnswer
from update_with_ai.lib.dag_clean_logic import NoChangeResult, FailureResult
from update_with_ai.lib.tool_provider import ToolResult

NODE_LABEL = "//tests/example:sample_node_1"
UNKNOWN_LABEL = "//nope:missing"


def _write_manifest(pkg_dir: Path, label: str, srcs: Optional[List[str]] = None) -> None:
    """Write a minimal node manifest to pkg_dir (current manifest format)."""
    pkg_dir.mkdir(parents=True, exist_ok=True)
    name = label.split(":")[-1]
    manifest = {
        "label": label,
        "name": name,
        "prompt": "test prompt",
        "tools": [],
        "deps": [],
        "silent_deps": [],
        "srcs": srcs or [],
        "silent_srcs": [],
        "verify": None,
    }
    with open(pkg_dir / f"{name}_manifest.json", "w") as f:
        json.dump(manifest, f)


def _storage(workspace_root: str) -> BazelGraphStorageFileImpl:
    """A fresh graph storage over the workspace (message access via the API)."""
    return BazelGraphStorageFileImpl(GraphConfig(workspace_root=workspace_root))


def _seed_pending(workspace_root: str, label: str, messages: List[str]) -> None:
    """Mark a node dirty by adding pending messages through the dag_storage API."""
    _storage(workspace_root).add_messages(label, messages)


def _read_pending(workspace_root: str, label: str) -> List[str]:
    """Read a node's pending messages through the dag_storage API."""
    return _storage(workspace_root).get_pending_messages(label)


@contextlib.contextmanager
def _patch_env(**set_vars: str) -> Iterator[None]:
    """
    Isolate the runner's log-path environment for a test.

    Clears CLEANROOM_AGENT_LOG, BUILD_WORKSPACE_DIRECTORY, and
    BUILD_WORKING_DIRECTORY, applies set_vars on top, and restores the
    original values on exit.
    """
    keys = ("CLEANROOM_AGENT_LOG", "BUILD_WORKSPACE_DIRECTORY", "BUILD_WORKING_DIRECTORY")
    saved: Dict[str, Optional[str]] = {k: os.environ.get(k) for k in keys}
    try:
        for k in keys:
            os.environ.pop(k, None)
        for k, v in set_vars.items():
            os.environ[k] = v
        yield
    finally:
        for k in keys:
            os.environ.pop(k, None)
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def _patch_agent_config() -> Any:
    """
    Point the runner at a fixed agent config so run_dag tests don't need real
    Bazel agent_config targets. (The component itself is tested separately in
    bazel_agent_config_impl_test.py.)
    """
    return patch.object(
        BazelAgentConfigImpl,
        "build_agent_loop_config",
        return_value=AgentLoopConfig(
            base_url="http://test.local/v1",
            api_key="test-key",
            model="test-model",
            max_iterations=10,
            temperature=0.0,
            timeout=60.0,
        ),
    )


class _StubAgentLoop:
    """
    Stand-in for AgentLoopImpl: records instances, emits logger events, and
    returns a FinalAnswer (so the clean maps to a NoChangeResult).
    """

    instances: List["_StubAgentLoop"] = []

    def __init__(self, config: AgentLoopConfig) -> None:
        self._config = config
        self.run_count = 0
        _StubAgentLoop.instances.append(self)

    def run_agent(self, prompt, tools, tool_executor, logger=None):
        self.run_count += 1
        if logger is not None:
            logger("message_added", {"message": {"role": "user", "content": prompt}})
            logger(
                "tool_called",
                {
                    "tool_calls": [
                        {"id": "c1", "type": "function",
                         "function": {"name": "write_file", "arguments": "{}"}}
                    ]
                },
            )
            logger(
                "api_response",
                {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
            )
            logger(
                "final_answer",
                {
                    "answer": "done",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                    "cumulative_usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                        "request_count": 1,
                    },
                    "final_context_size": 10,
                },
            )
        return FinalAnswer(answer="done", history=[])


class TestLogFormatters(unittest.TestCase):
    """
    _format_compact_log / _format_full_log behavior per the agent_loop
    LogEvent contract (specs/agent_loop-low.md, specs/bazel_runner-low.md).
    """

    NODE = "@@//tests/example:sample_node_1"
    USAGE: Dict[str, int] = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    CUMULATIVE: Dict[str, int] = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "request_count": 3,
    }

    def test_compact_tool_called(self) -> None:
        """tool_called gets a one-line summary naming each tool."""
        line = _format_compact_log(
            "tool_called",
            {
                "node_id": self.NODE,
                "tool_calls": [
                    {"function": {"name": "write_file", "arguments": "{}"}},
                    {"function": {"name": "read_file", "arguments": "{}"}},
                ],
            },
        )
        assert line is not None
        self.assertNotIn("\n", line)
        self.assertIn("sample_node_1", line)
        self.assertIn("write_file", line)
        self.assertIn("read_file", line)

    def test_compact_api_response(self) -> None:
        """api_response gets a one-line token-usage summary."""
        line = _format_compact_log("api_response", {"node_id": self.NODE, "usage": self.USAGE})
        assert line is not None
        self.assertNotIn("\n", line)
        self.assertIn("prompt 10", line)
        self.assertIn("completion 5", line)
        self.assertIn("total 15", line)

    def test_compact_final_answer(self) -> None:
        """final_answer gets a one-line summary with cumulative usage."""
        line = _format_compact_log(
            "final_answer", {"node_id": self.NODE, "cumulative_usage": self.CUMULATIVE}
        )
        assert line is not None
        self.assertNotIn("\n", line)
        self.assertIn("final answer", line)
        self.assertIn("total 150", line)
        self.assertIn("3 requests", line)

    def test_compact_run_terminated(self) -> None:
        """run_terminated gets a one-line summary with the termination value."""
        line = _format_compact_log(
            "run_terminated",
            {"node_id": self.NODE, "termination_value": "no_change", "cumulative_usage": self.CUMULATIVE},
        )
        assert line is not None
        self.assertNotIn("\n", line)
        self.assertIn("no_change", line)
        self.assertIn("3 requests", line)

    def test_compact_error(self) -> None:
        """error gets a one-line summary with the error text."""
        line = _format_compact_log("error", {"node_id": self.NODE, "error": "boom"})
        assert line is not None
        self.assertNotIn("\n", line)
        self.assertIn("boom", line)

    def test_compact_returns_none_for_other_events(self) -> None:
        """Events outside the summary list are skipped (None)."""
        for event in ("message_added", "message_stubbed", "tool_result", "reminder_injected"):
            self.assertIsNone(_format_compact_log(event, {"node_id": self.NODE}))

    def test_full_message_added_with_content(self) -> None:
        line = _format_full_log(
            "message_added",
            {"node_id": self.NODE, "message": {"role": "user", "content": "hello world"}},
        )
        self.assertIn("message_added", line)
        self.assertIn("user", line)
        self.assertIn("hello world", line)

    def test_full_message_added_with_tool_calls(self) -> None:
        line = _format_full_log(
            "message_added",
            {
                "node_id": self.NODE,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"function": {"name": "read_file"}}],
                },
            },
        )
        self.assertIn("message_added", line)
        self.assertIn("read_file", line)

    def test_full_message_stubbed(self) -> None:
        line = _format_full_log(
            "message_stubbed",
            {
                "node_id": self.NODE,
                "content_id": "foo.txt",
                "stubbed_message": {"content": "old content"},
                "replacement_message": {"content": "new content"},
            },
        )
        self.assertIn("message_stubbed", line)
        self.assertIn("foo.txt", line)
        self.assertIn("old content", line)
        self.assertIn("new content", line)

    def test_full_tool_called(self) -> None:
        line = _format_full_log(
            "tool_called",
            {
                "node_id": self.NODE,
                "tool_calls": [{"function": {"name": "write_file", "arguments": "{}"}}],
            },
        )
        self.assertIn("tool_called", line)
        self.assertIn("write_file", line)

    def test_full_tool_result(self) -> None:
        line = _format_full_log(
            "tool_result",
            {
                "node_id": self.NODE,
                "results": [ToolResult(content="ok", content_id="foo.txt", stub_previous=True)],
            },
        )
        self.assertIn("tool_result", line)
        self.assertIn("foo.txt", line)
        self.assertIn("ok", line)

    def test_full_api_response(self) -> None:
        line = _format_full_log("api_response", {"node_id": self.NODE, "usage": self.USAGE})
        self.assertIn("api_response", line)
        self.assertIn("prompt 10", line)
        self.assertIn("total 15", line)

    def test_full_reminder_injected(self) -> None:
        line = _format_full_log(
            "reminder_injected", {"node_id": self.NODE, "message": "please finish"}
        )
        self.assertIn("reminder_injected", line)
        self.assertIn("please finish", line)

    def test_full_final_answer(self) -> None:
        line = _format_full_log(
            "final_answer",
            {
                "node_id": self.NODE,
                "answer": "done",
                "usage": self.USAGE,
                "cumulative_usage": self.CUMULATIVE,
                "final_context_size": 10,
            },
        )
        self.assertIn("final_answer", line)
        self.assertIn("done", line)
        self.assertIn("total 150", line)
        self.assertIn("3 requests", line)
        self.assertIn("context 10", line)

    def test_full_run_terminated(self) -> None:
        line = _format_full_log(
            "run_terminated",
            {
                "node_id": self.NODE,
                "termination_value": "no_change",
                "cumulative_usage": self.CUMULATIVE,
                "final_context_size": 10,
            },
        )
        self.assertIn("run_terminated", line)
        self.assertIn("no_change", line)

    def test_full_error(self) -> None:
        line = _format_full_log("error", {"node_id": self.NODE, "error": "boom"})
        self.assertIn("error", line)
        self.assertIn("boom", line)


class TestInjectFeedback(unittest.TestCase):
    """BazRunnerImpl.inject_feedback per bazel_runner-low.md / bazel_runner_impl-low.md."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cleanroom_feedback_test_")
        self._root = Path(self._tmp)
        self._runner = BazRunnerImpl()
        _StubAgentLoop.instances.clear()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_workspace(self) -> None:
        _write_manifest(self._root / "tests" / "example", NODE_LABEL)

    def test_delivers_feedback_to_node_itself(self) -> None:
        """Messages are stored in the node's pending message store (.bazelharness.json)."""
        self._write_workspace()
        with _patch_env():
            success, result = self._runner.inject_feedback(
                NODE_LABEL, self._tmp, ["my feedback to sample_node_1"]
            )
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)

        # The feedback landed in the node's pending message store (via the API).
        self.assertEqual(
            _read_pending(self._tmp, NODE_LABEL), ["my feedback to sample_node_1"]
        )

    def test_multiple_messages_preserved_in_order(self) -> None:
        """Multiple feedback messages are all delivered, in order."""
        self._write_workspace()
        with _patch_env():
            success, result = self._runner.inject_feedback(
                NODE_LABEL, self._tmp, ["first", "second"]
            )
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)

        self.assertEqual(_read_pending(self._tmp, NODE_LABEL), ["first", "second"])

    def test_unknown_node_fails_without_mutating_state(self) -> None:
        """A nonexistent node returns (False, FailureResult()) and changes nothing."""
        self._write_workspace()
        _seed_pending(self._tmp, NODE_LABEL, ["pre-existing"])

        with _patch_env():
            success, result = self._runner.inject_feedback(
                UNKNOWN_LABEL, self._tmp, ["hi"]
            )
        self.assertFalse(success)
        self.assertIsInstance(result, FailureResult)
        # No state was mutated: the node's pending messages are unchanged and
        # no new message state appeared anywhere in the workspace.
        self.assertEqual(_read_pending(self._tmp, NODE_LABEL), ["pre-existing"])
        self.assertEqual(len(list(self._root.rglob(".bazelharness.json"))), 1)

    def test_constructs_own_graph_no_shared_state_with_run_dag(self) -> None:
        """
        A fresh graph is constructed for each inject_feedback call and for
        run_dag separately (invariant: no shared state across calls).
        """
        self._write_workspace()
        instances: List[Any] = []
        original_graph_cls = bazel_runner_impl.BazelGraphStorageFileImpl

        def _factory(config: Any) -> Any:
            inst = original_graph_cls(config)
            instances.append(inst)
            return inst

        with _patch_env(), patch(
            "update_with_ai.lib.bazel_runner_impl.BazelGraphStorageFileImpl", side_effect=_factory
        ):
            self._runner.inject_feedback(NODE_LABEL, self._tmp, ["one"])
            self._runner.inject_feedback(NODE_LABEL, self._tmp, ["two"])
        self.assertEqual(len(instances), 2)
        self.assertIsNot(instances[0], instances[1])

        # run_dag assembles its own graph, distinct from the feedback graphs.
        with _patch_env(CLEANROOM_AGENT_LOG=str(self._root / "agent_loop.log")), patch(
            "update_with_ai.lib.bazel_runner_impl.BazelGraphStorageFileImpl", side_effect=_factory
        ), patch("update_with_ai.lib.bazel_runner_impl.AgentLoopImpl", _StubAgentLoop), _patch_agent_config():
            success, result = self._runner.run_dag(NODE_LABEL, self._tmp)
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        self.assertEqual(len(instances), 3)
        self.assertIsNot(instances[1], instances[2])

    def test_marks_node_dirty_for_subsequent_run_dag(self) -> None:
        """Feedback is seen by a later run_dag, which re-processes the node."""
        self._write_workspace()
        with _patch_env():
            success, result = self._runner.inject_feedback(
                NODE_LABEL, self._tmp, ["make it better"]
            )
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)

        with _patch_env(CLEANROOM_AGENT_LOG=str(self._root / "agent_loop.log")), patch(
            "update_with_ai.lib.bazel_runner_impl.AgentLoopImpl", _StubAgentLoop
        ), _patch_agent_config():
            success, result = self._runner.run_dag(NODE_LABEL, self._tmp)
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        # The dirty node was cleaned exactly once: the agent ran and its
        # pending messages were consumed (no longer pending).
        self.assertEqual(_StubAgentLoop.instances[0].run_count, 1)
        self.assertEqual(_read_pending(self._tmp, NODE_LABEL), [])


class TestRunDag(unittest.TestCase):
    """BazRunnerImpl.run_dag per bazel_runner-low.md / bazel_runner_impl-low.md."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cleanroom_rundag_test_")
        self._root = Path(self._tmp)
        self._runner = BazRunnerImpl()
        _StubAgentLoop.instances.clear()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_workspace(self, srcs: Optional[List[str]] = None,
                         seed_messages: bool = False) -> None:
        _write_manifest(self._root / "tests" / "example", NODE_LABEL, srcs=srcs)
        if seed_messages:
            _seed_pending(str(self._root), NODE_LABEL, ["pending change"])

    def test_full_cleaning_pass_writes_and_closes_log(self) -> None:
        """
        A dirty node (pending messages) is cleaned through the assembled
        components: returns (True, NoChangeResult()), the log file is written
        and closed, and the pending messages are consumed.
        """
        self._write_workspace()
        log_path = str(self._root / "logs" / "custom.log")
        (self._root / "logs").mkdir()

        opened_writers: List[Any] = []
        real_open = open

        def _tracking_open(*args: Any, **kwargs: Any) -> Any:
            handle = real_open(*args, **kwargs)
            mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
            if "w" in str(mode):
                opened_writers.append(handle)
            return handle

        with _patch_env(CLEANROOM_AGENT_LOG=log_path), patch(
            "update_with_ai.lib.bazel_runner_impl.AgentLoopImpl", _StubAgentLoop
        ), patch("builtins.open", side_effect=_tracking_open), _patch_agent_config():
            # A pending message marks the node dirty; the clean pass consumes it.
            _seed_pending(self._tmp, NODE_LABEL, ["pending change"])
            success, result = self._runner.run_dag(NODE_LABEL, self._tmp)

        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        # The agent loop actually ran (the node was dirty and got cleaned).
        self.assertEqual(_StubAgentLoop.instances[0].run_count, 1)

        # Log file written at the CLEANROOM_AGENT_LOG path with transcript lines.
        log_file = Path(log_path)
        self.assertTrue(log_file.exists())
        content = log_file.read_text(encoding="utf-8")
        for fragment in ("message_added", "tool_called", "api_response", "final_answer"):
            self.assertIn(fragment, content)

        # The log file (a write-mode handle opened by the runner) is closed.
        self.assertIn(log_path, [getattr(h, "name", None) for h in opened_writers])
        self.assertTrue(all(h.closed for h in opened_writers))

        # The clean pass consumed the node's pending messages.
        self.assertEqual(_read_pending(self._tmp, NODE_LABEL), [])

    def test_log_relative_name_resolved_against_workspace_dir(self) -> None:
        """
        CLEANROOM_AGENT_LOG relative names resolve against the
        BUILD_WORKSPACE_DIRECTORY log base directory.
        """
        base = self._root / "base"
        base.mkdir()
        # Mirror the package directory under the base: the graph maps package
        # directories onto the BUILD_WORKSPACE_DIRECTORY tree (the "real
        # source root"), where the message store reads/writes .bazelharness.json.
        (base / "tests" / "example").mkdir(parents=True)
        self._write_workspace()

        with _patch_env(
            BUILD_WORKSPACE_DIRECTORY=str(base), CLEANROOM_AGENT_LOG="my_agent.log"
        ), patch("update_with_ai.lib.bazel_runner_impl.AgentLoopImpl", _StubAgentLoop), _patch_agent_config():
            # A pending message marks the node dirty (written under the base,
            # where package directories map); the clean pass consumes it.
            _seed_pending(self._tmp, NODE_LABEL, ["pending change"])
            success, result = self._runner.run_dag(NODE_LABEL, self._tmp)
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        log_file = base / "my_agent.log"
        self.assertTrue(log_file.exists())
        self.assertIn("final_answer", log_file.read_text(encoding="utf-8"))

    def test_log_defaults_to_workspace_dir_when_env_var_set(self) -> None:
        """Without CLEANROOM_AGENT_LOG, the log lands in BUILD_WORKSPACE_DIRECTORY."""
        base = self._root / "base"
        base.mkdir()
        # Mirror the package directory under the base (see above).
        (base / "tests" / "example").mkdir(parents=True)
        self._write_workspace()

        with _patch_env(BUILD_WORKSPACE_DIRECTORY=str(base)), patch(
            "update_with_ai.lib.bazel_runner_impl.AgentLoopImpl", _StubAgentLoop
        ), _patch_agent_config():
            # A pending message marks the node dirty (written under the base);
            # the clean pass consumes it.
            _seed_pending(self._tmp, NODE_LABEL, ["pending change"])
            success, result = self._runner.run_dag(NODE_LABEL, self._tmp)
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        log_file = base / "agent_loop.log"
        self.assertTrue(log_file.exists())
        self.assertIn("final_answer", log_file.read_text(encoding="utf-8"))

    def test_log_falls_back_to_working_directory_env_var(self) -> None:
        """BUILD_WORKING_DIRECTORY is the log base when BUILD_WORKSPACE_DIRECTORY is unset."""
        base = self._root / "base"
        base.mkdir()
        # Only the log base is BUILD_WORKING_DIRECTORY; package dirs still map
        # to the workspace root (BUILD_WORKSPACE_DIRECTORY is unset), so seed
        # the pending message there.
        self._write_workspace()

        with _patch_env(BUILD_WORKING_DIRECTORY=str(base)), patch(
            "update_with_ai.lib.bazel_runner_impl.AgentLoopImpl", _StubAgentLoop
        ), _patch_agent_config():
            _seed_pending(self._tmp, NODE_LABEL, ["pending change"])
            success, result = self._runner.run_dag(NODE_LABEL, self._tmp)
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        log_file = base / "agent_loop.log"
        self.assertTrue(log_file.exists())
        self.assertIn("final_answer", log_file.read_text(encoding="utf-8"))

    def test_run_dag_raises_when_root_node_has_no_manifest(self) -> None:
        """
        A workspace with no manifest for the root node: run_dag raises rather
        than returning a result (the failure propagates out of the cleaning
        pass; bazel_runner-low.md only guarantees a returned result for valid
        root nodes).
        """
        # Clean workspace (no manifests at all). The log env is pinned to a
        # writable path so any failure is not masked by a log-open error, and
        # the agent config is patched so the raised error is the missing
        # manifest (not a config-resolution error).
        with _patch_env(CLEANROOM_AGENT_LOG=str(self._root / "agent_loop.log")), _patch_agent_config():
            with self.assertRaises(Exception):
                self._runner.run_dag(NODE_LABEL, self._tmp)

    def test_run_dag_passes_config_target_through(self) -> None:
        """
        run_dag forwards config_target to the BazelAgentConfig component and
        constructs the agent loop with the resulting AgentLoopConfig.
        """
        self._write_workspace()
        captured: Dict[str, Any] = {}

        def _fake_build(config_target: Optional[str], workspace_root: str) -> AgentLoopConfig:
            captured["target"] = config_target
            captured["root"] = workspace_root
            return AgentLoopConfig(
                base_url="http://resolved/v1",
                api_key="resolved-key",
                model="resolved-model",
                max_iterations=5,
                temperature=0.4,
                timeout=30.0,
            )

        with _patch_env(CLEANROOM_AGENT_LOG=str(self._root / "agent_loop.log")), patch.object(
            BazelAgentConfigImpl, "build_agent_loop_config", side_effect=_fake_build
        ), patch("update_with_ai.lib.bazel_runner_impl.AgentLoopImpl", _StubAgentLoop):
            success, result = self._runner.run_dag(
                NODE_LABEL, self._tmp, config_target="//agent_configs:custom"
            )

        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        self.assertEqual(captured["target"], "//agent_configs:custom")
        self.assertEqual(captured["root"], self._tmp)
        # The agent loop was built from the resolved config, not hardcoded values.
        self.assertEqual(_StubAgentLoop.instances[-1]._config.model, "resolved-model")
        self.assertEqual(_StubAgentLoop.instances[-1]._config.api_key, "resolved-key")
        self.assertEqual(_StubAgentLoop.instances[-1]._config.max_iterations, 5)


if __name__ == "__main__":
    unittest.main()
