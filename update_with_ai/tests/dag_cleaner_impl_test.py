"""Tests for dag_cleaner_impl derived from LLS."""

import unittest
from typing import Sequence, Optional, Dict, List, Set
from lib.dag_storage import DagStorage, NodeId, DagMessage, PendingMessage, NodeData
from lib.dag_node_cleaner import NodeCleaner, NodeCleaningOutcome, ChangeMessage, FeedbackMessage
from lib.dag_cleaner_impl import DagCleanerImpl


class MockStorage(DagStorage):
    def __init__(self) -> None:
        self.deps: Dict[str, List[str]] = {}
        self.rdeps: Dict[str, List[str]] = {}
        self.pending: Dict[str, List[DagMessage]] = {}
        self.dirty: Set[str] = set()
        self.node_data: Dict[str, NodeData] = {}

    def get_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return self.deps.get(node, [])

    def get_reverse_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return self.rdeps.get(node, [])

    def get_pending_messages(self, node: NodeId) -> Sequence[PendingMessage]:
        return list(self.pending.get(node, []))

    def queue_pending_messages(self, node: NodeId, messages: Sequence[DagMessage]) -> None:
        if node not in self.pending:
            self.pending[node] = []
        self.pending[node].extend(messages)
        self.dirty.add(node)

    def clear_pending_messages(self, node: NodeId) -> None:
        self.pending[node] = []
        self.dirty.discard(node)

    def record_node_data(self, node: NodeId, data: NodeData) -> None:
        self.node_data[node] = data

    def get_node_data(self, node: NodeId) -> Optional[NodeData]:
        return self.node_data.get(node)

    def mark_dirty(self, node: NodeId) -> None:
        self.dirty.add(node)

    def is_dirty(self, node: NodeId) -> bool:
        return node in self.dirty


class RecordingNodeCleaner(NodeCleaner):
    def __init__(self) -> None:
        self.cleaned_calls: List[tuple[NodeId, List[PendingMessage]]] = []
        self.outcomes_by_node: Dict[NodeId, List[NodeCleaningOutcome]] = {}
        self.default_outcome: NodeCleaningOutcome = []

    def set_outcomes(self, node: NodeId, outcomes: List[NodeCleaningOutcome]) -> None:
        self.outcomes_by_node[node] = list(outcomes)

    def clean_node(self, node: NodeId, pending_messages: Sequence[PendingMessage]) -> NodeCleaningOutcome:
        self.cleaned_calls.append((node, list(pending_messages)))
        if node in self.outcomes_by_node and self.outcomes_by_node[node]:
            return self.outcomes_by_node[node].pop(0)
        return self.default_outcome


class TestDagCleanerTopologicalExecution(unittest.TestCase):
    """Tests CUJ for topological cleaning order and dependency-first invariants."""

    def test_single_node_clean_success(self) -> None:
        """Tests cleaning an isolated root node with no dependencies."""
        storage = MockStorage()
        storage.mark_dirty("//pkg:single")
        cleaner = RecordingNodeCleaner()
        cleaner.default_outcome = []

        dag_cleaner = DagCleanerImpl()
        dag_cleaner.clean_subgraph("//pkg:single", storage, cleaner)

        self.assertEqual(len(cleaner.cleaned_calls), 1)
        self.assertEqual(cleaner.cleaned_calls[0][0], "//pkg:single")
        self.assertFalse(storage.is_dirty("//pkg:single"))

    def test_linear_pipeline_topological_order(self) -> None:
        """Tests linear chain A -> B -> C executes in dependency-first order [C, B, A]."""
        storage = MockStorage()
        storage.deps["//pkg:a"] = ["//pkg:b"]
        storage.rdeps["//pkg:b"] = ["//pkg:a"]
        storage.deps["//pkg:b"] = ["//pkg:c"]
        storage.rdeps["//pkg:c"] = ["//pkg:b"]

        storage.mark_dirty("//pkg:a")
        storage.mark_dirty("//pkg:b")
        storage.mark_dirty("//pkg:c")

        cleaner = RecordingNodeCleaner()
        dag_cleaner = DagCleanerImpl()
        dag_cleaner.clean_subgraph("//pkg:a", storage, cleaner)

        visited_nodes = [call[0] for call in cleaner.cleaned_calls]
        self.assertEqual(visited_nodes, ["//pkg:c", "//pkg:b", "//pkg:a"])
        self.assertFalse(storage.is_dirty("//pkg:a"))
        self.assertFalse(storage.is_dirty("//pkg:b"))
        self.assertFalse(storage.is_dirty("//pkg:c"))

    def test_diamond_graph_topological_order(self) -> None:
        """Tests diamond DAG: root -> (left, right) -> bottom."""
        storage = MockStorage()
        storage.deps["//pkg:root"] = ["//pkg:left", "//pkg:right"]
        storage.rdeps["//pkg:left"] = ["//pkg:root"]
        storage.rdeps["//pkg:right"] = ["//pkg:root"]

        storage.deps["//pkg:left"] = ["//pkg:bottom"]
        storage.deps["//pkg:right"] = ["//pkg:bottom"]
        storage.rdeps["//pkg:bottom"] = ["//pkg:left", "//pkg:right"]

        storage.mark_dirty("//pkg:root")
        storage.mark_dirty("//pkg:left")
        storage.mark_dirty("//pkg:right")
        storage.mark_dirty("//pkg:bottom")

        cleaner = RecordingNodeCleaner()
        dag_cleaner = DagCleanerImpl()
        dag_cleaner.clean_subgraph("//pkg:root", storage, cleaner)

        visited_nodes = [call[0] for call in cleaner.cleaned_calls]
        self.assertEqual(visited_nodes[0], "//pkg:bottom")
        self.assertEqual(visited_nodes[-1], "//pkg:root")
        self.assertIn("//pkg:left", visited_nodes[1:3])
        self.assertIn("//pkg:right", visited_nodes[1:3])

    def test_only_dirty_nodes_are_cleaned(self) -> None:
        """Tests that clean nodes in the reachable subgraph are not cleaned."""
        storage = MockStorage()
        storage.deps["//pkg:root"] = ["//pkg:dep1", "//pkg:dep2"]
        storage.rdeps["//pkg:dep1"] = ["//pkg:root"]
        storage.rdeps["//pkg:dep2"] = ["//pkg:root"]

        # Only dep2 and root are dirty
        storage.mark_dirty("//pkg:dep2")
        storage.mark_dirty("//pkg:root")

        cleaner = RecordingNodeCleaner()
        dag_cleaner = DagCleanerImpl()
        dag_cleaner.clean_subgraph("//pkg:root", storage, cleaner)

        visited_nodes = [call[0] for call in cleaner.cleaned_calls]
        self.assertEqual(visited_nodes, ["//pkg:dep2", "//pkg:root"])
        self.assertNotIn("//pkg:dep1", visited_nodes)

    def test_unreachable_nodes_are_not_cleaned(self) -> None:
        """Tests that dirty nodes outside the root's dependency subgraph are ignored."""
        storage = MockStorage()
        storage.deps["//pkg:root"] = ["//pkg:dep"]
        storage.rdeps["//pkg:dep"] = ["//pkg:root"]

        storage.mark_dirty("//pkg:root")
        storage.mark_dirty("//pkg:dep")
        storage.mark_dirty("//pkg:unrelated")

        cleaner = RecordingNodeCleaner()
        dag_cleaner = DagCleanerImpl()
        dag_cleaner.clean_subgraph("//pkg:root", storage, cleaner)

        visited_nodes = [call[0] for call in cleaner.cleaned_calls]
        self.assertEqual(visited_nodes, ["//pkg:dep", "//pkg:root"])
        self.assertTrue(storage.is_dirty("//pkg:unrelated"))


class TestDagCleanerMessageRouting(unittest.TestCase):
    """Tests message routing postconditions for ChangeMessage and FeedbackMessage."""

    def test_change_message_routes_to_all_reverse_dependencies(self) -> None:
        """Tests that ChangeMessage instances produced by a node are routed to its reverse dependencies."""
        storage = MockStorage()
        storage.deps["//pkg:consumer1"] = ["//pkg:producer"]
        storage.deps["//pkg:consumer2"] = ["//pkg:producer"]
        storage.rdeps["//pkg:producer"] = ["//pkg:consumer1", "//pkg:consumer2"]

        storage.deps["//pkg:root"] = ["//pkg:consumer1", "//pkg:consumer2"]
        storage.rdeps["//pkg:consumer1"] = ["//pkg:root"]
        storage.rdeps["//pkg:consumer2"] = ["//pkg:root"]

        storage.mark_dirty("//pkg:producer")
        # Consumers start clean; producer changes will mark them dirty

        cleaner = RecordingNodeCleaner()
        change_msg = ChangeMessage(content="producer_output.txt updated")
        cleaner.set_outcomes("//pkg:producer", [[change_msg]])
        cleaner.set_outcomes("//pkg:consumer1", [[]])
        cleaner.set_outcomes("//pkg:consumer2", [[]])
        cleaner.set_outcomes("//pkg:root", [[]])

        dag_cleaner = DagCleanerImpl()
        dag_cleaner.clean_subgraph("//pkg:root", storage, cleaner)

        # Both consumers should have received the ChangeMessage
        consumer1_calls = [call for call in cleaner.cleaned_calls if call[0] == "//pkg:consumer1"]
        consumer2_calls = [call for call in cleaner.cleaned_calls if call[0] == "//pkg:consumer2"]
        self.assertTrue(len(consumer1_calls) > 0)
        self.assertTrue(len(consumer2_calls) > 0)
        self.assertIn(change_msg, consumer1_calls[0][1])
        self.assertIn(change_msg, consumer2_calls[0][1])

    def test_feedback_message_routes_upstream_to_dependencies(self) -> None:
        """Tests that FeedbackMessage instances produced by a node are routed to its dependencies."""
        storage = MockStorage()
        storage.deps["//pkg:consumer"] = ["//pkg:producer"]
        storage.rdeps["//pkg:producer"] = ["//pkg:consumer"]

        storage.mark_dirty("//pkg:consumer")

        cleaner = RecordingNodeCleaner()
        feedback_msg = FeedbackMessage(content="Blamed //pkg:producer: syntax error in header")
        # Consumer on pass 1 emits feedback, marking producer dirty
        cleaner.set_outcomes("//pkg:consumer", [[feedback_msg], []])
        # Producer on pass 2 fixes the issue and emits change
        cleaner.set_outcomes("//pkg:producer", [[ChangeMessage(content="fixed header")]])

        dag_cleaner = DagCleanerImpl(max_iterations=10)
        dag_cleaner.clean_subgraph("//pkg:consumer", storage, cleaner)

        # Producer must have been cleaned and received the FeedbackMessage
        producer_calls = [call for call in cleaner.cleaned_calls if call[0] == "//pkg:producer"]
        self.assertEqual(len(producer_calls), 1)
        self.assertIn(feedback_msg, producer_calls[0][1])

    def test_clears_pending_messages_when_cleaning_node(self) -> None:
        """Tests that pending messages are cleared when a node is cleaned."""
        storage = MockStorage()
        initial_msg = DagMessage(content="initial pending message")
        storage.queue_pending_messages("//pkg:node", [initial_msg])
        self.assertTrue(storage.is_dirty("//pkg:node"))

        cleaner = RecordingNodeCleaner()
        cleaner.set_outcomes("//pkg:node", [[]])

        dag_cleaner = DagCleanerImpl()
        dag_cleaner.clean_subgraph("//pkg:node", storage, cleaner)

        self.assertEqual(len(cleaner.cleaned_calls), 1)
        self.assertIn(initial_msg, cleaner.cleaned_calls[0][1])
        # Pending messages in storage must now be empty
        self.assertEqual(storage.get_pending_messages("//pkg:node"), [])


class TestDagCleanerFailureHandling(unittest.TestCase):
    """Tests failure handling and boundary conditions."""

    def test_node_cleaning_failure_outcome_leaves_node_dirty_and_halts(self) -> None:
        """Tests that when clean_node returns None (cleaning failure), the node is left dirty and pass halts."""
        storage = MockStorage()
        storage.deps["//pkg:root"] = ["//pkg:dep"]
        storage.rdeps["//pkg:dep"] = ["//pkg:root"]
        storage.mark_dirty("//pkg:dep")
        storage.mark_dirty("//pkg:root")

        cleaner = RecordingNodeCleaner()
        # Dep fails cleaning (returns None)
        cleaner.set_outcomes("//pkg:dep", [None])

        dag_cleaner = DagCleanerImpl()
        dag_cleaner.clean_subgraph("//pkg:root", storage, cleaner)

        # Dep was called, but root was never cleaned because dep failed
        visited_nodes = [call[0] for call in cleaner.cleaned_calls]
        self.assertEqual(visited_nodes, ["//pkg:dep"])
        self.assertTrue(storage.is_dirty("//pkg:dep"))

    def test_cycle_detection_raises_runtime_error(self) -> None:
        """Tests that a cyclic dependency graph raises RuntimeError."""
        storage = MockStorage()
        storage.deps["//pkg:a"] = ["//pkg:b"]
        storage.rdeps["//pkg:b"] = ["//pkg:a"]
        storage.deps["//pkg:b"] = ["//pkg:a"]
        storage.rdeps["//pkg:a"] = ["//pkg:b"]
        storage.mark_dirty("//pkg:a")

        cleaner = RecordingNodeCleaner()
        dag_cleaner = DagCleanerImpl()

        with self.assertRaises(RuntimeError):
            dag_cleaner.clean_subgraph("//pkg:a", storage, cleaner)

    def test_max_iterations_exceeded_raises_runtime_error(self) -> None:
        """Tests that oscillating ping-pong messages exceeding max_iterations raise RuntimeError."""
        storage = MockStorage()
        storage.deps["//pkg:b"] = ["//pkg:a"]
        storage.rdeps["//pkg:a"] = ["//pkg:b"]
        storage.mark_dirty("//pkg:a")

        class PingPongCleaner(NodeCleaner):
            def clean_node(self, node: NodeId, pending_messages: Sequence[PendingMessage]) -> NodeCleaningOutcome:
                if node == "//pkg:a":
                    return [ChangeMessage(content="change A")]
                elif node == "//pkg:b":
                    return [FeedbackMessage(content="Blamed //pkg:a: retry")]
                return []

        dag_cleaner = DagCleanerImpl(max_iterations=4)
        with self.assertRaises(RuntimeError):
            dag_cleaner.clean_subgraph("//pkg:b", storage, PingPongCleaner())

    def test_max_iterations_boundary_exact_success(self) -> None:
        """Tests boundary: convergence within exactly max_iterations succeeds."""
        storage = MockStorage()
        storage.deps["//pkg:b"] = ["//pkg:a"]
        storage.rdeps["//pkg:a"] = ["//pkg:b"]
        storage.mark_dirty("//pkg:a")

        class BoundedLoopCleaner(NodeCleaner):
            def __init__(self, limit: int) -> None:
                self.count = 0
                self.limit = limit

            def clean_node(self, node: NodeId, pending_messages: Sequence[PendingMessage]) -> NodeCleaningOutcome:
                self.count += 1
                if self.count >= self.limit:
                    return []
                if node == "//pkg:a":
                    return [ChangeMessage(content="change A")]
                elif node == "//pkg:b":
                    return [FeedbackMessage(content="Blamed //pkg:a: retry")]
                return []

        # 2 passes needed to converge
        cleaner = BoundedLoopCleaner(limit=2)
        dag_cleaner = DagCleanerImpl(max_iterations=3)
        dag_cleaner.clean_subgraph("//pkg:b", storage, cleaner)
        self.assertFalse(storage.is_dirty("//pkg:a"))
        self.assertFalse(storage.is_dirty("//pkg:b"))


if __name__ == "__main__":
    unittest.main()


