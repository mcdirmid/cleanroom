"""
Tests for lib/build_runner_impl.py (BuildRunnerImpl).
"""

import signal
import unittest
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, cast

from lib.build_runner_impl import BuildRunnerImpl
from lib.build_graph_storage import (
    BuildGraphStorage,
    GraphConfig,
    NodeDefinition,
    NodeId,
    PackageDirectory,
)
from lib.dag_cleaner import DagCleaner, CleaningResult
from lib.dag_clean_logic import (
    DagCleanLogic,
    CleanResult,
    NoChangeResult,
    FailureResult,
)
from lib.dag_storage import NodeMessage, MessageKind
from lib.runner_logger import RunnerLogger
from lib.sandbox import SandboxConfig


def msg(text: str, kind: str = "change") -> NodeMessage:
    return NodeMessage(kind=cast(MessageKind, kind), text=text)


NODE_LABEL = "//tests/example:sample_node_1"
UNKNOWN_LABEL = "//nope:missing"


class _MockRunnerLogger(RunnerLogger):
    def __init__(self, log_path: str = "/fake/agent_loop.log") -> None:
        self._log_path = log_path
        self.calls: List[tuple] = []
        self.emitted_events: List[tuple] = []
        self.closed = False

    def resolve_log_path(self) -> str:
        self.calls.append(("resolve_log_path", ()))
        return self._log_path

    def format_compact_log(self, event: Any, data: Dict[str, Any]) -> Optional[str]:
        return f"[compact] {event}"

    def format_full_log(self, event: Any, data: Dict[str, Any]) -> str:
        return f"[full] {event}"

    def create_agent_logger(self, log_path: str) -> Tuple[Any, Any]:
        self.calls.append(("create_agent_logger", log_path))
        def _logger(event: Any, data: Dict[str, Any]) -> None:
            self.emitted_events.append((event, data))
        def _closer() -> None:
            self.closed = True
        return _logger, _closer


class _MockGraphStorage(BuildGraphStorage):
    def __init__(
        self,
        nodes: Optional[Dict[NodeId, NodeDefinition]] = None,
        known_nodes: Optional[Set[NodeId]] = None,
        reverse_deps: Optional[Dict[NodeId, List[NodeId]]] = None,
    ) -> None:
        self.nodes = nodes or {}
        self.known_nodes = set(known_nodes) if known_nodes is not None else set(self.nodes.keys())
        self.reverse_deps = reverse_deps or {}
        self.messages: Dict[NodeId, List[NodeMessage]] = {}
        self.deleted_nodes: List[NodeId] = []
        self.calls: List[tuple] = []

    def resolve_package_directory(self, node_id: NodeId) -> PackageDirectory:
        self.calls.append(("resolve_package_directory", node_id))
        if node_id not in self.known_nodes:
            raise ValueError(f"Unknown node: {node_id}")
        return "/fake/pkg"

    def resolve_node_definition(self, node_id: NodeId) -> NodeDefinition:
        self.calls.append(("resolve_node_definition", node_id))
        if node_id not in self.known_nodes:
            raise ValueError(f"Unknown node: {node_id}")
        return self.nodes.get(
            node_id,
            NodeDefinition(
                prompt="prompt",
                sandbox_config=SandboxConfig(
                    file_mappings={},
                    readable_paths=[],
                    writable_paths=["target.py"],
                    blame_targets={},
                    search_result_limit=10,
                ),
            ),
        )

    def add_messages(self, node_id: NodeId, messages: List[NodeMessage]) -> None:
        self.calls.append(("add_messages", node_id, messages))
        if node_id not in self.known_nodes:
            raise ValueError(f"Unknown node: {node_id}")
        self.messages.setdefault(node_id, []).extend(messages)

    def get_pending_messages(self, node_id: NodeId) -> List[NodeMessage]:
        self.calls.append(("get_pending_messages", node_id))
        return list(self.messages.get(node_id, []))

    def clear_pending_messages(self, node_id: NodeId) -> None:
        self.calls.append(("clear_pending_messages", node_id))
        self.messages.pop(node_id, None)

    def delete_node_data(self, node_id: NodeId) -> None:
        self.calls.append(("delete_node_data", node_id))
        self.deleted_nodes.append(node_id)
        self.messages.pop(node_id, None)
        self.reverse_deps.pop(node_id, None)

    def get_known_reverse_dependencies(self, node_id: NodeId) -> List[NodeId]:
        self.calls.append(("get_known_reverse_dependencies", node_id))
        return list(self.reverse_deps.get(node_id, []))

    def get_node_dependencies(self, node_id: NodeId) -> List[NodeId]:
        return []

    def get_propagating_dependencies(self, node_id: NodeId) -> List[NodeId]:
        return []

    def get_subgraph(self, root_node: NodeId) -> List[NodeId]:
        return [root_node]


class _MockDagCleanLogic(DagCleanLogic):
    def clean(self, node_id: str, messages: Any) -> CleanResult:
        return NoChangeResult()

    def is_dirty(self, node_id: str, pending_messages: Any) -> bool:
        return False


class _MockDagCleaner(DagCleaner):
    def __init__(self, result: CleaningResult = (True, NoChangeResult())) -> None:
        self.result = result
        self.cleaned_subgraphs: List[str] = []

    def clean_subgraph(self, target_node: str) -> CleaningResult:
        self.cleaned_subgraphs.append(target_node)
        return self.result


class TestInjectFeedback(unittest.TestCase):
    def test_inject_feedback_delivers_messages(self) -> None:
        graph = _MockGraphStorage(known_nodes={NODE_LABEL})
        runner = BuildRunnerImpl(
            graph_factory=lambda cfg: graph,
            clean_logic_factory=lambda *_: _MockDagCleanLogic(),
            dag_factory=lambda *_: _MockDagCleaner(),
            runner_logger=_MockRunnerLogger(),
        )
        ok, res = runner.inject_feedback(NODE_LABEL, "/workspace", ["fix bug 1", "fix bug 2"])
        self.assertTrue(ok)
        self.assertIsInstance(res, NoChangeResult)
        self.assertEqual(
            graph.get_pending_messages(NODE_LABEL),
            [msg("fix bug 1", "feedback"), msg("fix bug 2", "feedback")],
        )

    def test_unknown_node_fails_without_mutating_state(self) -> None:
        graph = _MockGraphStorage(known_nodes={NODE_LABEL})
        runner = BuildRunnerImpl(
            graph_factory=lambda cfg: graph,
            clean_logic_factory=lambda *_: _MockDagCleanLogic(),
            dag_factory=lambda *_: _MockDagCleaner(),
            runner_logger=_MockRunnerLogger(),
        )
        ok, res = runner.inject_feedback(UNKNOWN_LABEL, "/workspace", ["feedback"])
        self.assertFalse(ok)
        self.assertIsInstance(res, FailureResult)
        self.assertEqual(graph.get_pending_messages(NODE_LABEL), [])


class TestAddChange(unittest.TestCase):
    def test_add_change_default_text(self) -> None:
        graph = _MockGraphStorage(known_nodes={NODE_LABEL})
        runner = BuildRunnerImpl(
            graph_factory=lambda cfg: graph,
            clean_logic_factory=lambda *_: _MockDagCleanLogic(),
            dag_factory=lambda *_: _MockDagCleaner(),
            runner_logger=_MockRunnerLogger(),
        )
        ok, res = runner.add_change(NODE_LABEL, "/workspace")
        self.assertTrue(ok)
        self.assertIsInstance(res, NoChangeResult)
        self.assertEqual(graph.get_pending_messages(NODE_LABEL), [msg("check", "change")])

    def test_add_change_custom_text(self) -> None:
        graph = _MockGraphStorage(known_nodes={NODE_LABEL})
        runner = BuildRunnerImpl(
            graph_factory=lambda cfg: graph,
            clean_logic_factory=lambda *_: _MockDagCleanLogic(),
            dag_factory=lambda *_: _MockDagCleaner(),
            runner_logger=_MockRunnerLogger(),
        )
        ok, res = runner.add_change(NODE_LABEL, "/workspace", "custom change")
        self.assertTrue(ok)
        self.assertIsInstance(res, NoChangeResult)
        self.assertEqual(graph.get_pending_messages(NODE_LABEL), [msg("custom change", "change")])

    def test_add_change_unknown_node_fails(self) -> None:
        graph = _MockGraphStorage(known_nodes={NODE_LABEL})
        runner = BuildRunnerImpl(
            graph_factory=lambda cfg: graph,
            clean_logic_factory=lambda *_: _MockDagCleanLogic(),
            dag_factory=lambda *_: _MockDagCleaner(),
            runner_logger=_MockRunnerLogger(),
        )
        ok, res = runner.add_change(UNKNOWN_LABEL, "/workspace")
        self.assertFalse(ok)
        self.assertIsInstance(res, FailureResult)


class TestBroadcastChange(unittest.TestCase):
    def test_broadcast_change_delivers_and_deletes_data(self) -> None:
        rdep = "//tests/example:rdep_1"
        graph = _MockGraphStorage(
            known_nodes={NODE_LABEL, rdep},
            reverse_deps={NODE_LABEL: [rdep]},
        )
        graph.messages[NODE_LABEL] = [msg("stale")]

        runner = BuildRunnerImpl(
            graph_factory=lambda cfg: graph,
            clean_logic_factory=lambda *_: _MockDagCleanLogic(),
            dag_factory=lambda *_: _MockDagCleaner(),
            runner_logger=_MockRunnerLogger(),
        )
        ok, res = runner.broadcast_change(NODE_LABEL, "/workspace", "changed foo")
        self.assertTrue(ok)
        self.assertIsInstance(res, NoChangeResult)
        self.assertIn(NODE_LABEL, graph.deleted_nodes)
        self.assertEqual(graph.get_pending_messages(NODE_LABEL), [])
        self.assertEqual(
            graph.get_pending_messages(rdep),
            [msg("target.py: changed foo", "change")],
        )

    def test_broadcast_change_unknown_node_fails(self) -> None:
        graph = _MockGraphStorage(known_nodes={NODE_LABEL})
        runner = BuildRunnerImpl(
            graph_factory=lambda cfg: graph,
            clean_logic_factory=lambda *_: _MockDagCleanLogic(),
            dag_factory=lambda *_: _MockDagCleaner(),
            runner_logger=_MockRunnerLogger(),
        )
        ok, res = runner.broadcast_change(UNKNOWN_LABEL, "/workspace", "change")
        self.assertFalse(ok)
        self.assertIsInstance(res, FailureResult)


class TestRunDag(unittest.TestCase):
    def test_run_dag_orchestration_flow(self) -> None:
        graph = _MockGraphStorage(known_nodes={NODE_LABEL})
        logger = _MockRunnerLogger()
        cleaner = _MockDagCleaner((True, NoChangeResult()))

        factory_calls: List[str] = []

        def graph_factory(cfg: GraphConfig) -> BuildGraphStorage:
            factory_calls.append("graph")
            return graph

        def clean_logic_factory(g: BuildGraphStorage, ws: str, cfg: Optional[str], l: Any) -> DagCleanLogic:
            factory_calls.append("clean_logic")
            return _MockDagCleanLogic()

        def dag_factory(g: BuildGraphStorage, cl: DagCleanLogic) -> DagCleaner:
            factory_calls.append("dag")
            return cleaner

        runner = BuildRunnerImpl(
            graph_factory=graph_factory,
            clean_logic_factory=clean_logic_factory,
            dag_factory=dag_factory,
            runner_logger=logger,
        )

        ok, res = runner.run_dag(NODE_LABEL, "/workspace", "//configs:agent")
        self.assertTrue(ok)
        self.assertIsInstance(res, NoChangeResult)
        self.assertEqual(factory_calls, ["graph", "clean_logic", "dag"])
        self.assertEqual(cleaner.cleaned_subgraphs, [NODE_LABEL])
        self.assertTrue(logger.closed)

    def test_run_dag_closes_logger_on_exception(self) -> None:
        graph = _MockGraphStorage(known_nodes={NODE_LABEL})
        logger = _MockRunnerLogger()

        class _FailingCleaner(DagCleaner):
            def clean_subgraph(self, target_node: str) -> CleaningResult:
                raise RuntimeError("DAG crashed")

        runner = BuildRunnerImpl(
            graph_factory=lambda cfg: graph,
            clean_logic_factory=lambda *_: _MockDagCleanLogic(),
            dag_factory=lambda *_: _FailingCleaner(),
            runner_logger=logger,
        )

        with self.assertRaises(RuntimeError):
            runner.run_dag(NODE_LABEL, "/workspace")
        self.assertTrue(logger.closed)


if __name__ == "__main__":
    unittest.main()
