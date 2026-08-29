"""
Tests for lib/build_runner_impl.py (BuildRunnerImpl).

Asserts the behavioral contract from specs/low/build_runner_impl.md and its
dependencies (specs/low/build_runner.md, specs/low/dag_cleaner.md,
specs/low/dag_storage.md, specs/low/dag_clean_logic.md, specs/low/agent_loop.md):

- BuildRunnerImpl is constructed with the component factories (graph factory,
  clean-logic factory, DAG factory) and holds no component instances; the
  components are created per call through the factories (invariant: no shared
  state across calls, and each of inject_feedback / add_change /
  broadcast_change constructs a graph separate from run_dag's).
- inject_feedback returns (True, NoChangeResult()) on success and stores the
  messages in the node's pending message store; returns
  (False, FailureResult()) for a nonexistent node without mutating any state.
- add_change stores a change-kind message (defaulting to `check`).
- broadcast_change delivers `<declared source file>: <change text>` to each
  known reverse dependency and clears the target's data.
- run_dag drives a cleaning pass through the injected factories: it forwards
  (graph, workspace_root, config_target, logger) to the clean-logic factory
  and (graph, clean_logic) to the DAG factory, returns the DAG's CleaningResult,
  and writes/closes the agent log file (CLEANROOM_AGENT_LOG /
  BUILD_WORKSPACE_DIRECTORY / BUILD_WORKING_DIRECTORY priority); each log line
  is flushed immediately; a graph-factory failure propagates without a log file.
- _format_compact_log emits one-line summaries exactly for tool_called,
  api_response, run_terminated, and error events and None for all other
  events.
- _format_full_log produces a verbose line for every agent_loop LogEvent
  (message_added, message_stubbed, tool_called, tool_result, api_response,
  reminder_injected, run_terminated, error).
"""

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from unittest.mock import patch
from typing import cast

from lib.build_runner_impl import (
    BuildRunnerImpl,
    _format_compact_log,
    _format_full_log,
)
from lib.build_graph_storage import BuildGraphStorage, GraphConfig
from lib.build_graph_storage_impl import BuildGraphStorageFileImpl
from lib.dag_cleaner import CleaningResult
from lib.dag_clean_logic import (
    DagCleanLogic,
    CleanResult,
    NoChangeResult,
    FailureResult,
)
from lib.dag_storage import NodeMessage, MessageKind


def msg(text: str, kind: str = "change") -> NodeMessage:
    """Test helper: build a NodeMessage (per specs/low/dag_storage.md)."""
    return NodeMessage(kind=cast(MessageKind, kind), text=text)

NODE_LABEL = "//tests/example:sample_node_1"
UNKNOWN_LABEL = "//nope:missing"


def _write_manifest(
    pkg_dir: Path,
    label: str,
    src: Optional[str] = None,
    deps: Optional[List[str]] = None,
) -> None:
    """Write a minimal node manifest to pkg_dir (current manifest format)."""
    pkg_dir.mkdir(parents=True, exist_ok=True)
    name = label.split(":")[-1]
    manifest = {
        "label": label,
        "name": name,
        "prompt": "test prompt",
        "tools": [],
        "deps": deps or [],
        "silent_deps": [],
        "src": src or "",
        "template": None,
        "silent_srcs": [],
        "verify": None,
    }
    with open(pkg_dir / f"{name}_manifest.json", "w") as f:
        json.dump(manifest, f)


def _storage(workspace_root: str) -> BuildGraphStorageFileImpl:
    """A fresh graph storage over the workspace (message access via the API)."""
    return BuildGraphStorageFileImpl(GraphConfig(workspace_root=workspace_root))


def _seed_pending(workspace_root: str, label: str, messages: List[str]) -> None:
    """Mark a node dirty by adding pending messages through the dag_storage API."""
    _storage(workspace_root).add_messages(
        label,
        [NodeMessage(kind="change", text=m) for m in messages],
    )


def _read_pending(workspace_root: str, label: str) -> List[NodeMessage]:
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


class _FakeDagCleanLogic:
    """Stand-in for the DagCleanLogic interface: the runner only passes it to
    the DAG factory; it is never called by the runner itself."""

    def clean(self, node_id: str, messages: Any) -> CleanResult:
        raise NotImplementedError

    def is_dirty(self, node_id: str, pending_messages: Any) -> bool:
        return False


class _FakeDagCleaner:
    """Stand-in for the DagCleaner interface: records clean_subgraph calls and
    returns a scripted result."""

    def __init__(self, result: CleaningResult) -> None:
        self._result = result
        self.clean_subgraph_calls: List[str] = []

    def clean_subgraph(self, target_node: str) -> CleaningResult:
        self.clean_subgraph_calls.append(target_node)
        return self._result


class _RunDagHarness:
    """
    A BuildRunnerImpl with recorded factories over a real file-backed graph.

    Records every factory call: ("graph", graph) / ("clean_logic", graph,
    workspace_root, config_target, logger) / ("dag", graph, clean_logic).
    The clean-logic factory emits a fixed set of logger events (mirroring the
    events a real agent run reports), so log-content tests can assert the
    transcript without an agent loop.
    """

    def __init__(
        self,
        workspace_root: str,
        dag_result: CleaningResult = (True, NoChangeResult()),
        emit_events: bool = True,
    ) -> None:
        self.calls: List[Any] = []
        self.graph_instances: List[BuildGraphStorage] = []
        self.clean_logic_instances: List[Any] = []
        self.dag_cleaners: List[_FakeDagCleaner] = []
        self.clean_logic_config_targets: List[Optional[str]] = []
        self.loggers: List[Any] = []
        self._workspace_root = workspace_root
        self._dag_result = dag_result
        self._emit_events = emit_events

        def graph_factory(config: GraphConfig) -> BuildGraphStorage:
            inst = BuildGraphStorageFileImpl(config=config)
            self.graph_instances.append(inst)
            self.calls.append(("graph", config))
            return inst

        def clean_logic_factory(
            graph: BuildGraphStorage,
            workspace_root: str,
            config_target: Optional[str],
            logger: Any,
        ) -> DagCleanLogic:
            self.calls.append(("clean_logic", graph, workspace_root, config_target, logger))
            self.clean_logic_config_targets.append(config_target)
            self.loggers.append(logger)
            if logger is not None and self._emit_events:
                logger("message_added", {"message": {"role": "user", "content": "prompt"}})
                logger(
                    "tool_called",
                    {
                        "tool_calls": [
                            {"id": "c1", "type": "function",
                             "function": {"name": "replace", "arguments": "{}"}}
                        ]
                    },
                )
                logger(
                    "api_response",
                    {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
                )
                logger("reminder_injected", {"message": "You must signal termination to end the run."})
            clean_logic = _FakeDagCleanLogic()
            self.clean_logic_instances.append(clean_logic)
            return clean_logic

        def dag_factory(graph: BuildGraphStorage, clean_logic: DagCleanLogic) -> Any:
            dag = _FakeDagCleaner(self._dag_result)
            self.dag_cleaners.append(dag)
            self.calls.append(("dag", graph, clean_logic))
            return dag

        self.runner = BuildRunnerImpl(
            graph_factory=graph_factory,
            clean_logic_factory=clean_logic_factory,
            dag_factory=dag_factory,
        )


class _MessageOpRunner:
    """A BuildRunnerImpl for the message operations: real file-backed graph via
    the graph factory; the clean-logic and DAG factories are unused stubs."""

    def __init__(self) -> None:
        self.graph_instances: List[BuildGraphStorage] = []

        def graph_factory(config: GraphConfig) -> BuildGraphStorage:
            inst = BuildGraphStorageFileImpl(config=config)
            self.graph_instances.append(inst)
            return inst

        self.runner = BuildRunnerImpl(
            graph_factory=graph_factory,
            clean_logic_factory=lambda *_: _FakeDagCleanLogic(),
            dag_factory=lambda *_: _FakeDagCleaner((True, NoChangeResult())),
        )


class TestLogFormatters(unittest.TestCase):
    """
    _format_compact_log / _format_full_log behavior per the agent_loop
    LogEvent contract (specs/low/agent_loop.md, specs/low/build_runner.md).
    """

    NODE = "@@//tests/example:sample_node_1"
    USAGE: Dict[str, Any] = {
        "input_tokens": 10,
        "cached_input_tokens": 0,
        "non_cached_input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "duration_seconds": 1.2,
    }
    CUMULATIVE: Dict[str, Any] = {
        "input_tokens": 100,
        "cached_input_tokens": 80,
        "non_cached_input_tokens": 20,
        "output_tokens": 50,
        "total_tokens": 150,
        "request_count": 3,
        "total_duration_seconds": 3.6,
    }

    def test_compact_tool_called(self) -> None:
        """tool_called gets a one-line summary naming each tool."""
        line = _format_compact_log(
            "tool_called",
            {
                "node_id": self.NODE,
                "tool_calls": [
                    {"function": {"name": "replace", "arguments": "{}"}},
                    {"function": {"name": "read_file", "arguments": "{}"}},
                ],
            },
        )
        assert line is not None
        self.assertNotIn("\n", line)
        self.assertIn("sample_node_1", line)
        self.assertIn("replace", line)
        self.assertIn("read_file", line)

    def test_compact_api_response(self) -> None:
        """api_response is skipped on stdout."""
        line = _format_compact_log("api_response", {"node_id": self.NODE})
        assert line is None

    def test_compact_run_terminated(self) -> None:
        """run_terminated gets a one-line summary with session and cumulative token usage."""
        line = _format_compact_log(
            "run_terminated",
            {"node_id": self.NODE, "termination_value": "no_change", "cumulative_usage": self.CUMULATIVE},
        )
        assert line is not None
        self.assertNotIn("\n", line)
        self.assertIn("no_change", line)
        self.assertIn("input 100, input (cached) 80, output 50, total 150", line)
        self.assertIn("3 requests, 3.60s", line)

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
        """message_stubbed gets a transcript line showing the stub content."""
        line = _format_full_log(
            "message_stubbed",
            {
                "node_id": self.NODE,
                "stubbed_message": {"role": "tool", "content": "Content removed because newer version is available."},
            },
        )
        self.assertEqual(
            line,
            f"[{self.NODE}] message_stubbed: "
            "content='Content removed because newer version is available.'",
        )

    def test_full_tool_result(self) -> None:
        from lib.tool_provider import ToolResult

        line = _format_full_log(
            "tool_result",
            {
                "node_id": self.NODE,
                "results": [
                    ToolResult(content="ok", supersedes=True)
                ],
            },
        )
        self.assertIn("tool_result", line)
        self.assertIn("ok", line)
        self.assertIn("supersedes=True", line)

    def test_full_tool_called(self) -> None:
        line = _format_full_log(
            "tool_called",
            {
                "node_id": self.NODE,
                "tool_calls": [{"function": {"name": "replace", "arguments": "{}"}}],
            },
        )
        self.assertIn("tool_called", line)
        self.assertIn("replace", line)

    def test_full_api_response(self) -> None:
        line = _format_full_log("api_response", {"node_id": self.NODE})
        self.assertIn("api_response", line)

    def test_full_reminder_injected(self) -> None:
        line = _format_full_log(
            "reminder_injected", {"node_id": self.NODE, "message": "please finish"}
        )
        self.assertIn("reminder_injected", line)
        self.assertIn("please finish", line)

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
        self.assertIn("input 100, input (cached) 80, output 50, total 150", line)
        self.assertIn("context 10", line)

    def test_full_error(self) -> None:
        line = _format_full_log("error", {"node_id": self.NODE, "error": "boom"})
        self.assertIn("error", line)
        self.assertIn("boom", line)


class TestInjectFeedback(unittest.TestCase):
    """BuildRunnerImpl.inject_feedback per specs/low/build_runner.md / specs/low/build_runner_impl.md."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cleanroom_feedback_test_")
        self._root = Path(self._tmp)
        self._harness = _MessageOpRunner()
        self._runner = self._harness.runner

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_workspace(self) -> None:
        _write_manifest(self._root / "tests" / "example", NODE_LABEL)

    def test_delivers_feedback_to_node_itself(self) -> None:
        """Messages are stored in the node's pending message store."""
        self._write_workspace()
        with _patch_env():
            success, result = self._runner.inject_feedback(
                NODE_LABEL, self._tmp, ["my feedback to sample_node_1"]
            )
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)

        # The feedback landed in the node's pending message store (via the API),
        # as a feedback-kind message (when cleaned, the node must change,
        # blame, or fail).
        self.assertEqual(
            _read_pending(self._tmp, NODE_LABEL),
            [msg("my feedback to sample_node_1", "feedback")],
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

        self.assertEqual(
            _read_pending(self._tmp, NODE_LABEL),
            [msg("first", "feedback"), msg("second", "feedback")],
        )

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
        self.assertEqual(_read_pending(self._tmp, NODE_LABEL), [msg("pre-existing")])
        self.assertEqual(len(list(self._root.rglob(".testing.textproto"))), 1)

    def test_constructs_own_graph_no_shared_state_with_run_dag(self) -> None:
        """
        A fresh graph is constructed for each inject_feedback call and for
        run_dag separately (invariant: no shared state across calls).
        """
        self._write_workspace()
        with _patch_env():
            self._runner.inject_feedback(NODE_LABEL, self._tmp, ["one"])
            self._runner.inject_feedback(NODE_LABEL, self._tmp, ["two"])
        self.assertEqual(len(self._harness.graph_instances), 2)
        self.assertIsNot(self._harness.graph_instances[0], self._harness.graph_instances[1])

        # run_dag assembles its own graph, distinct from the feedback graphs.
        dag_harness = _RunDagHarness(self._tmp)
        with _patch_env(CLEANROOM_AGENT_LOG=str(self._root / "agent_loop.log")):
            success, result = dag_harness.runner.run_dag(NODE_LABEL, self._tmp)
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        self.assertEqual(len(dag_harness.graph_instances), 1)
        self.assertIsNot(self._harness.graph_instances[1], dag_harness.graph_instances[0])


class TestAddChange(unittest.TestCase):
    """BuildRunnerImpl.add_change (_dirty) per specs/low/build_runner.md / specs/low/build_runner_impl.md."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cleanroom_addchange_test_")
        self._root = Path(self._tmp)
        self._harness = _MessageOpRunner()
        self._runner = self._harness.runner

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_workspace(self) -> None:
        _write_manifest(self._root / "tests" / "example", NODE_LABEL)

    def test_add_change_stores_change_kind_message(self) -> None:
        """add_change adds a change-kind message (marking the node dirty);
        the node may succeed without changing when cleaned."""
        self._write_workspace()
        success, result = self._runner.add_change(NODE_LABEL, self._tmp, "check the behavior")
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        self.assertEqual(
            _read_pending(self._tmp, NODE_LABEL), [msg("check the behavior")]
        )

    def test_add_change_defaults_to_check(self) -> None:
        """With no change text, the change message defaults to `check`."""
        self._write_workspace()
        success, result = self._runner.add_change(NODE_LABEL, self._tmp)
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        self.assertEqual(_read_pending(self._tmp, NODE_LABEL), [msg("check")])

    def test_add_change_unknown_node_fails_without_mutating_state(self) -> None:
        """A nonexistent node returns (False, FailureResult()) and changes nothing."""
        self._write_workspace()
        _seed_pending(self._tmp, NODE_LABEL, ["pre-existing"])
        success, result = self._runner.add_change(UNKNOWN_LABEL, self._tmp, "hi")
        self.assertFalse(success)
        self.assertIsInstance(result, FailureResult)
        self.assertEqual(_read_pending(self._tmp, NODE_LABEL), [msg("pre-existing")])


class TestBroadcastChange(unittest.TestCase):
    """BuildRunnerImpl.broadcast_change (_change) per specs/low/build_runner.md / specs/low/build_runner_impl.md."""

    DEP_LABEL = "//tests/example:consumer"
    TARGET_SRC = "target.py"

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cleanroom_broadcast_test_")
        self._root = Path(self._tmp)
        self._harness = _MessageOpRunner()
        self._runner = self._harness.runner

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_workspace(self) -> None:
        _write_manifest(self._root / "tests" / "example", NODE_LABEL, src=self.TARGET_SRC)
        _write_manifest(
            self._root / "tests" / "consumer",
            self.DEP_LABEL,
            deps=[NODE_LABEL],
        )

    def _record_reverse_dependency(self) -> None:
        """Resolve the dependent's dependencies so it is recorded as a known
        reverse dependency of the target (per dag_storage)."""
        _storage(str(self._root)).get_node_dependencies(self.DEP_LABEL)

    def test_broadcast_change_delivers_to_reverse_dependencies_and_clears(self) -> None:
        """broadcast_change pretends the node was cleaned with changes: a
        change message `<src>: <change>` is delivered to each known reverse
        dependency, and the target's pending messages and known reverse
        dependencies are cleared."""
        self._write_workspace()
        # The dependent depends on the target (its manifest deps).
        self._record_reverse_dependency()

        success, result = self._runner.broadcast_change(NODE_LABEL, self._tmp, "changed hello world")
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)

        # The reverse dependency received "<src>: <change text>".
        self.assertEqual(
            _read_pending(self._tmp, self.DEP_LABEL),
            [msg("target.py: changed hello world")],
        )
        # The target's own data was cleared (messages + reverse deps).
        self.assertEqual(_read_pending(self._tmp, NODE_LABEL), [])
        self.assertEqual(
            _storage(str(self._root)).get_known_reverse_dependencies(NODE_LABEL),
            [],
        )

    def test_broadcast_change_unknown_node_fails_without_mutating_state(self) -> None:
        """A nonexistent node returns (False, FailureResult()) and changes nothing."""
        self._write_workspace()
        self._record_reverse_dependency()
        success, result = self._runner.broadcast_change(UNKNOWN_LABEL, self._tmp, "hi")
        self.assertFalse(success)
        self.assertIsInstance(result, FailureResult)
        # No message state appeared anywhere in the workspace.
        self.assertEqual(len(list(self._root.rglob(".testing.textproto"))), 1)


class TestRunDag(unittest.TestCase):
    """BuildRunnerImpl.run_dag per specs/low/build_runner.md / specs/low/build_runner_impl.md."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cleanroom_rundag_test_")
        self._root = Path(self._tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_workspace(self) -> None:
        _write_manifest(self._root / "tests" / "example", NODE_LABEL)

    def test_full_cleaning_pass_writes_and_closes_log(self) -> None:
        """
        run_dag drives the pass through the injected factories: returns the
        DAG's CleaningResult, the log file is written and closed, and the
        clean-logic factory received the graph, the workspace root, and the
        run logger.
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

        harness = _RunDagHarness(self._tmp)
        with _patch_env(CLEANROOM_AGENT_LOG=log_path), patch(
            "builtins.open", side_effect=_tracking_open
        ):
            success, result = harness.runner.run_dag(NODE_LABEL, self._tmp)

        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)

        # The DAG factory received (graph, clean_logic) and clean_subgraph ran.
        self.assertEqual(len(harness.dag_cleaners), 1)
        self.assertEqual(harness.dag_cleaners[0].clean_subgraph_calls, [NODE_LABEL])
        self.assertEqual([c[0] for c in harness.calls], ["graph", "clean_logic", "dag"])
        self.assertIs(harness.calls[2][1], harness.graph_instances[0])  # dag <- same graph
        self.assertIs(harness.calls[2][2], harness.clean_logic_instances[0])  # <- same clean logic

        # The clean-logic factory received the workspace root and a logger.
        self.assertEqual(harness.clean_logic_config_targets, [None])
        self.assertIsNotNone(harness.loggers[0])

        # Log file written at the CLEANROOM_AGENT_LOG path with transcript lines.
        log_file = Path(log_path)
        self.assertTrue(log_file.exists())
        content = log_file.read_text(encoding="utf-8")
        for fragment in ("message_added", "tool_called", "api_response", "reminder_injected"):
            self.assertIn(fragment, content)

        # The log file (a write-mode handle opened by the runner) is closed.
        self.assertIn(log_path, [getattr(h, "name", None) for h in opened_writers])
        self.assertTrue(all(h.closed for h in opened_writers))

    def test_log_writes_are_flushed_immediately(self) -> None:
        """
        LLS (specs/low/build_runner_impl.md): each event line is flushed to the log
        file immediately after it is written (log writes are unbuffered), so
        the transcript reflects the run in real time.
        """
        self._write_workspace()
        calls: List[Tuple[str, Any]] = []

        class _FakeLogFile:
            def __init__(self) -> None:
                self.closed = False
                self.name = "fake.log"

            def write(self, s: str) -> int:
                calls.append(("write", s))
                return len(s)

            def flush(self) -> None:
                calls.append(("flush", None))

            def close(self) -> None:
                self.closed = True

        fake = _FakeLogFile()
        real_open = open

        def _fake_open(*args: Any, **kwargs: Any) -> Any:
            mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
            # The runner's log open is the only write-mode open with an
            # explicit encoding (open(log_path, "w", encoding="utf-8"));
            # intercept it, pass everything else through to the real open.
            if "w" in str(mode) and "encoding" in kwargs:
                return fake
            return real_open(*args, **kwargs)

        harness = _RunDagHarness(self._tmp)
        with _patch_env(CLEANROOM_AGENT_LOG="fake.log"), patch(
            "builtins.open", side_effect=_fake_open
        ):
            success, result = harness.runner.run_dag(NODE_LABEL, self._tmp)

        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        writes = [c for c in calls if c[0] == "write"]
        flushes = [c for c in calls if c[0] == "flush"]
        # One line per harness-emitted event (message_added, tool_called,
        # api_response, reminder_injected) plus the compact summaries are
        # printed, not written.
        self.assertGreaterEqual(len(writes), 4)
        self.assertEqual(len(flushes), len(writes))
        # Every write is immediately followed by a flush (real-time log).
        for i, (kind, _) in enumerate(calls):
            if kind == "write":
                self.assertLess(i + 1, len(calls))
                self.assertEqual(calls[i + 1][0], "flush")
        self.assertTrue(fake.closed)

    def test_log_relative_name_resolved_against_workspace_dir(self) -> None:
        """
        CLEANROOM_AGENT_LOG relative names resolve against the
        BUILD_WORKSPACE_DIRECTORY log base directory.
        """
        base = self._root / "base"
        base.mkdir()
        self._write_workspace()

        harness = _RunDagHarness(self._tmp)
        with _patch_env(BUILD_WORKSPACE_DIRECTORY=str(base), CLEANROOM_AGENT_LOG="my_agent.log"):
            success, result = harness.runner.run_dag(NODE_LABEL, self._tmp)
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        log_file = base / "my_agent.log"
        self.assertTrue(log_file.exists())
        self.assertIn("reminder_injected", log_file.read_text(encoding="utf-8"))

    def test_log_defaults_to_workspace_dir_when_env_var_set(self) -> None:
        """Without CLEANROOM_AGENT_LOG, the log lands in BUILD_WORKSPACE_DIRECTORY."""
        base = self._root / "base"
        base.mkdir()
        self._write_workspace()

        harness = _RunDagHarness(self._tmp)
        with _patch_env(BUILD_WORKSPACE_DIRECTORY=str(base)):
            success, result = harness.runner.run_dag(NODE_LABEL, self._tmp)
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        log_file = base / "agent_loop.log"
        self.assertTrue(log_file.exists())
        self.assertIn("reminder_injected", log_file.read_text(encoding="utf-8"))

    def test_log_falls_back_to_working_directory_env_var(self) -> None:
        """BUILD_WORKING_DIRECTORY is the log base when BUILD_WORKSPACE_DIRECTORY is unset."""
        base = self._root / "base"
        base.mkdir()
        self._write_workspace()

        harness = _RunDagHarness(self._tmp)
        with _patch_env(BUILD_WORKING_DIRECTORY=str(base)):
            success, result = harness.runner.run_dag(NODE_LABEL, self._tmp)
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        log_file = base / "agent_loop.log"
        self.assertTrue(log_file.exists())
        self.assertIn("reminder_injected", log_file.read_text(encoding="utf-8"))

    def test_run_dag_forwards_config_target_to_clean_logic_factory(self) -> None:
        """
        run_dag forwards its config_target argument to the clean-logic factory
        (the factory resolves the agent configuration; the runner hardcodes
        nothing).
        """
        self._write_workspace()
        harness = _RunDagHarness(self._tmp)
        with _patch_env(CLEANROOM_AGENT_LOG=str(self._root / "agent_loop.log")):
            success, result = harness.runner.run_dag(
                NODE_LABEL, self._tmp, config_target="//agent_configs:custom"
            )
        self.assertTrue(success)
        self.assertIsInstance(result, NoChangeResult)
        self.assertEqual(harness.clean_logic_config_targets, ["//agent_configs:custom"])
        self.assertEqual(harness.calls[1][2], self._tmp)  # workspace_root forwarded

    def test_run_dag_constructs_fresh_graph_per_call(self) -> None:
        """
        Each run_dag constructs a fresh graph, clean logic, and DAG through
        the factories (invariant: components created per call).
        """
        self._write_workspace()
        harness = _RunDagHarness(self._tmp)
        with _patch_env(CLEANROOM_AGENT_LOG=str(self._root / "agent_loop.log")):
            success1, _ = harness.runner.run_dag(NODE_LABEL, self._tmp)
            success2, _ = harness.runner.run_dag(NODE_LABEL, self._tmp)
        self.assertTrue(success1)
        self.assertTrue(success2)
        self.assertEqual(len(harness.graph_instances), 2)
        self.assertEqual(len(harness.dag_cleaners), 2)
        self.assertIsNot(harness.graph_instances[0], harness.graph_instances[1])
        self.assertEqual(harness.dag_cleaners[0].clean_subgraph_calls, [NODE_LABEL])
        self.assertEqual(harness.dag_cleaners[1].clean_subgraph_calls, [NODE_LABEL])

    def test_run_dag_propagates_dag_failure_result(self) -> None:
        """A FailureResult from the DAG is returned as-is (expected failures
        are values)."""
        self._write_workspace()
        harness = _RunDagHarness(self._tmp, dag_result=(False, FailureResult()))
        with _patch_env(CLEANROOM_AGENT_LOG=str(self._root / "agent_loop.log")):
            success, result = harness.runner.run_dag(NODE_LABEL, self._tmp)
        self.assertFalse(success)
        self.assertIsInstance(result, FailureResult)
        # The log file is still written on failure.
        self.assertTrue((self._root / "agent_loop.log").exists())

    def test_graph_factory_failure_propagates_without_log(self) -> None:
        """
        A failure during graph construction (e.g. assembly failure) propagates
        and no log file is created (per specs/low/build_runner.md: the log is
        created after component assembly).
        """
        self._write_workspace()
        log_path = str(self._root / "logs" / "custom.log")

        def graph_factory(config: GraphConfig) -> BuildGraphStorage:
            raise RuntimeError("no workspace")

        runner = BuildRunnerImpl(
            graph_factory=graph_factory,
            clean_logic_factory=lambda *_: _FakeDagCleanLogic(),
            dag_factory=lambda *_: _FakeDagCleaner((True, NoChangeResult())),
        )
        with _patch_env(CLEANROOM_AGENT_LOG=log_path):
            with self.assertRaises(RuntimeError):
                runner.run_dag(NODE_LABEL, self._tmp)
        self.assertFalse(Path(log_path).exists())


class TestSigintHandling(unittest.TestCase):
    """LLS: SIGINT terminates the run promptly; the interrupt is never ignored."""

    def test_sigint_raises_keyboard_interrupt(self) -> None:
        """The handler installed at import honors SIGINT by raising
        KeyboardInterrupt (never ignoring the interrupt), so the run's
        cleanup unwinds and the process exits."""
        with self.assertRaises(KeyboardInterrupt):
            os.kill(os.getpid(), signal.SIGINT)

    def test_sigint_terminates_promptly(self) -> None:
        """A process importing the runner terminates promptly on SIGINT with
        the interruption status, not by continuing or hanging; the handler
        raises KeyboardInterrupt (the interrupt is never ignored)."""
        code = (
            "import sys, time\n"
            "import lib.build_runner_impl  # installs the SIGINT handler\n"
            "print('ready', flush=True)\n"
            "while True:\n"
            "    time.sleep(0.05)\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            line = proc.stdout.readline()
            self.assertEqual(line.strip(), "ready")
            proc.send_signal(signal.SIGINT)
            rc = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            self.fail("process did not terminate promptly on SIGINT")
        child_err = proc.stderr.read() if proc.stderr is not None else ""
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()
        # Interrupted: an unhandled KeyboardInterrupt exits 130 (128+SIGINT);
        # CPython 3.8+ re-raises the signal so the process is also reported as
        # killed by SIGINT (-2). Either is the interruption status.
        self.assertIn(rc, (-2, 130))
        self.assertIn("KeyboardInterrupt", child_err)


if __name__ == "__main__":
    unittest.main()
