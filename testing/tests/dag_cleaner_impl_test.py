"""Tests for DagCleanerImpl per its implementation LLS (dag_cleaner_impl.md).

Written from the LLS alone; the implementation Python file is not consulted.
"""

import unittest
from dag_storage import (
    NodeId, NodeMessage, PendingMessages,
    NodeDependencies, KnownReverseDependencies
)
from dag_clean_logic import (
    CleanResult, ChangeResult,
    FeedbackResult, NoChangeResult, FailureResult
)


class MockDagStorage:
    """Mock DagStorage implementing the DagStorage protocol from dag_storage.md."""

    def __init__(self) -> None:
        self._pending_messages: dict[NodeId, PendingMessages] = {}
        self._node_dependencies: dict[NodeId, NodeDependencies] = {}
        self._known_reverse_deps: dict[NodeId, KnownReverseDependencies] = {}
        self._existing_nodes: set[NodeId] = set()
        self.added_messages: list[tuple[NodeId, list[NodeMessage]]] = []
        self.cleared_messages: list[NodeId] = []
        self.deleted_nodes: list[NodeId] = []
        self.get_pending_calls: list[NodeId] = []
        self.get_deps_calls: list[NodeId] = []
        self.get_rev_deps_calls: list[NodeId] = []

    def _assert_node_exists(self, node_id: NodeId) -> None:
        if node_id not in self._existing_nodes:
            raise KeyError(f"Node {node_id} does not exist in the graph")

    def set_node(self, node_id: NodeId, dependencies: NodeDependencies,
                 reverse_dependencies: KnownReverseDependencies,
                 pending_messages: PendingMessages | None = None) -> None:
        self._existing_nodes.add(node_id)
        self._node_dependencies[node_id] = dependencies
        self._known_reverse_deps[node_id] = list(reverse_dependencies)
        self._pending_messages[node_id] = list(pending_messages) if pending_messages else []

    def get_pending_messages(self, node_id: NodeId) -> PendingMessages:
        self._assert_node_exists(node_id)
        self.get_pending_calls.append(node_id)
        return list(self._pending_messages.get(node_id, []))

    def add_messages(self, node_id: NodeId, messages: list[NodeMessage]) -> None:
        self._assert_node_exists(node_id)
        self.added_messages.append((node_id, list(messages)))

    def clear_pending_messages(self, node_id: NodeId) -> None:
        self._assert_node_exists(node_id)
        self.cleared_messages.append(node_id)

    def delete_node_data(self, node_id: NodeId) -> None:
        self._assert_node_exists(node_id)
        self.deleted_nodes.append(node_id)

    def get_node_dependencies(self, node_id: NodeId) -> NodeDependencies:
        self._assert_node_exists(node_id)
        self.get_deps_calls.append(node_id)
        return list(self._node_dependencies.get(node_id, []))

    def get_known_reverse_dependencies(self, node_id: NodeId) -> KnownReverseDependencies:
        self._assert_node_exists(node_id)
        self.get_rev_deps_calls.append(node_id)
        return list(self._known_reverse_deps.get(node_id, []))


class MockCleanLogic:
    """Mock DagCleanLogic implementing the DagCleanLogic protocol from dag_clean_logic.md."""

    def __init__(self) -> None:
        self.clean_calls: list[tuple[NodeId, PendingMessages]] = []
        self.is_dirty_calls: list[tuple[NodeId, PendingMessages]] = []
        self._clean_results: dict[NodeId, CleanResult] = {}
        self._dirty_results: dict[NodeId, bool] = {}

    def set_clean_result(self, node_id: NodeId, result: CleanResult) -> None:
        self._clean_results[node_id] = result

    def set_dirty_result(self, node_id: NodeId, is_dirty: bool) -> None:
        self._dirty_results[node_id] = is_dirty

    def clean(self, node_id: NodeId, messages: PendingMessages) -> CleanResult:
        self.clean_calls.append((node_id, messages))
        return self._clean_results.get(node_id, NoChangeResult())

    def is_dirty(self, node_id: NodeId, pending_messages: PendingMessages) -> bool:
        self.is_dirty_calls.append((node_id, pending_messages))
        return self._dirty_results.get(node_id, len(pending_messages) > 0)


class DagCleanerImplConstructionTest(unittest.TestCase):
    """Tests for DagCleanerImpl construction per dag_cleaner_impl.md."""

    def test_construction_accepts_storage_and_logic(self) -> None:
        """DagCleanerImpl is constructed with dag_storage and dag_clean_logic."""
        from dag_cleaner_impl import DagCleanerImpl
        storage = MockDagStorage()
        logic = MockCleanLogic()
        cleaner = DagCleanerImpl(storage, logic)
        self.assertIsNotNone(cleaner)

    def test_construction_returns_dag_cleaner_instance(self) -> None:
        """DagCleanerImpl is an instance of DagCleaner protocol."""
        from dag_cleaner_impl import DagCleanerImpl
        from dag_cleaner import DagCleaner
        storage = MockDagStorage()
        logic = MockCleanLogic()
        cleaner = DagCleanerImpl(storage, logic)
        self.assertIsInstance(cleaner, DagCleaner)


class DagCleanerImplResultDiscriminatorTest(unittest.TestCase):
    """Tests for result Literal discriminators per dag_clean_logic.md."""

    def test_change_result_type_discriminator(self) -> None:
        """ChangeResult has type='change'."""
        result = ChangeResult(messages=[])
        self.assertEqual(result.type, "change")

    def test_feedback_result_type_discriminator(self) -> None:
        """FeedbackResult has type='feedback'."""
        result = FeedbackResult(messages=[])
        self.assertEqual(result.type, "feedback")

    def test_nochange_result_type_discriminator(self) -> None:
        """NoChangeResult has type='no_change'."""
        result = NoChangeResult()
        self.assertEqual(result.type, "no_change")

    def test_failure_result_type_discriminator(self) -> None:
        """FailureResult has type='failure'."""
        result = FailureResult()
        self.assertEqual(result.type, "failure")



class DagCleanerImplCleanSubgraphResultTest(unittest.TestCase):
    """Tests for clean_subgraph return values per dag_cleaner_impl.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_clean_subgraph_returns_true_on_nochange(self) -> None:
        """A node with NoChangeResult returns (True, NoChangeResult)."""
        self.storage.set_node("A", dependencies=[], reverse_dependencies=[])
        self.logic.set_clean_result("A", NoChangeResult())
        self.logic.set_dirty_result("A", False)
        result = self.cleaner.clean_subgraph("A")
        self.assertTrue(result[0])
        self.assertIsInstance(result[1], NoChangeResult)

    def test_clean_subgraph_returns_true_on_change(self) -> None:
        """A node that produces ChangeResult returns (True, ChangeResult)."""
        self.storage.set_node("A", dependencies=[], reverse_dependencies=[])
        messages = [NodeMessage(kind="change", text="data updated")]
        self.logic.set_clean_result("A", ChangeResult(messages=messages))
        self.logic.set_dirty_result("A", True)
        result = self.cleaner.clean_subgraph("A")
        self.assertTrue(result[0])
        self.assertIsInstance(result[1], ChangeResult)

    def test_clean_subgraph_returns_true_on_feedback(self) -> None:
        """A node that produces FeedbackResult returns (True, FeedbackResult)."""
        self.storage.set_node("A", dependencies=[], reverse_dependencies=[])
        messages = [("B", NodeMessage(kind="feedback", text="update needed"))]
        self.logic.set_clean_result("A", FeedbackResult(messages=messages))
        self.logic.set_dirty_result("A", True)
        result = self.cleaner.clean_subgraph("A")
        self.assertTrue(result[0])
        self.assertIsInstance(result[1], FeedbackResult)

    def test_clean_subgraph_returns_false_on_failure(self) -> None:
        """A node that produces FailureResult returns (False, FailureResult)."""
        self.storage.set_node("A", dependencies=[], reverse_dependencies=[])
        self.logic.set_clean_result("A", FailureResult())
        self.logic.set_dirty_result("A", True)
        result = self.cleaner.clean_subgraph("A")
        self.assertFalse(result[0])
        self.assertIsInstance(result[1], FailureResult)


class DagCleanerImplNodeDataHandlingTest(unittest.TestCase):
    """Tests for node data handling after cleaning per dag_cleaner_impl.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_change_result_deletes_node_data(self) -> None:
        """After ChangeResult, the node's pending messages and known reverse dependencies are deleted."""
        self.storage.set_node(
            "A",
            dependencies=[],
            reverse_dependencies=["B", "C"],
            pending_messages=[NodeMessage(kind="change", text="msg")]
        )
        self.logic.set_clean_result("A", ChangeResult(messages=[]))
        self.logic.set_dirty_result("A", True)
        self.cleaner.clean_subgraph("A")
        self.assertIn("A", self.storage.deleted_nodes)

    def test_nochange_result_clears_pending_messages(self) -> None:
        """After NoChangeResult, the node's pending messages are cleared but reverse deps remain."""
        self.storage.set_node(
            "A",
            dependencies=[],
            reverse_dependencies=["B"],
            pending_messages=[NodeMessage(kind="change", text="msg")]
        )
        self.logic.set_clean_result("A", NoChangeResult())
        self.logic.set_dirty_result("A", False)
        self.cleaner.clean_subgraph("A")
        self.assertIn("A", self.storage.cleared_messages)
        self.assertNotIn("A", self.storage.deleted_nodes)

    def test_feedback_result_removes_no_stored_data(self) -> None:
        """After FeedbackResult, no stored data is removed."""
        self.storage.set_node(
            "A",
            dependencies=[],
            reverse_dependencies=["B"],
            pending_messages=[NodeMessage(kind="feedback", text="msg")]
        )
        self.logic.set_clean_result("A", FeedbackResult(messages=[]))
        self.logic.set_dirty_result("A", True)
        self.cleaner.clean_subgraph("A")
        self.assertNotIn("A", self.storage.deleted_nodes)
        self.assertNotIn("A", self.storage.cleared_messages)


class DagCleanerImplMessageRoutingTest(unittest.TestCase):
    """Tests for message routing after cleaning per dag_cleaner_impl.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_change_messages_routed_to_reverse_dependencies(self) -> None:
        """ChangeResult messages are added to all known reverse dependencies."""
        self.storage.set_node(
            "A",
            dependencies=[],
            reverse_dependencies=["B", "C"],
            pending_messages=[]
        )
        messages = [NodeMessage(kind="change", text="data updated")]
        self.logic.set_clean_result("A", ChangeResult(messages=messages))
        self.logic.set_dirty_result("A", True)
        self.cleaner.clean_subgraph("A")
        b_msgs = [call for call in self.storage.added_messages if call[0] == "B"]
        c_msgs = [call for call in self.storage.added_messages if call[0] == "C"]
        self.assertEqual(len(b_msgs), 1)
        self.assertEqual(len(c_msgs), 1)

    def test_feedback_messages_routed_to_specified_dependencies(self) -> None:
        """FeedbackResult messages are added only to the specified dependency nodes."""
        self.storage.set_node(
            "A",
            dependencies=["B"],
            reverse_dependencies=[],
            pending_messages=[]
        )
        self.storage.set_node(
            "B",
            dependencies=[],
            reverse_dependencies=["A"],
            pending_messages=[]
        )
        messages = [("B", NodeMessage(kind="feedback", text="update needed"))]
        self.logic.set_clean_result("A", FeedbackResult(messages=messages))
        self.logic.set_dirty_result("A", True)
        self.cleaner.clean_subgraph("A")
        b_msgs = [call for call in self.storage.added_messages if call[0] == "B"]
        self.assertEqual(len(b_msgs), 1)

    def test_change_messages_have_change_kind(self) -> None:
        """ChangeResult messages carry kind='change' when delivered to reverse deps."""
        self.storage.set_node(
            "A",
            dependencies=[],
            reverse_dependencies=["B"],
            pending_messages=[]
        )
        messages = [NodeMessage(kind="change", text="data updated")]
        self.logic.set_clean_result("A", ChangeResult(messages=messages))
        self.logic.set_dirty_result("A", True)
        self.cleaner.clean_subgraph("A")
        delivered = self.storage.added_messages[0][1]
        self.assertTrue(all(m.kind == "change" for m in delivered))

    def test_feedback_messages_have_feedback_kind(self) -> None:
        """FeedbackResult messages carry kind='feedback' when delivered."""
        self.storage.set_node(
            "A",
            dependencies=["B"],
            reverse_dependencies=[],
            pending_messages=[]
        )
        self.storage.set_node(
            "B",
            dependencies=[],
            reverse_dependencies=["A"],
            pending_messages=[]
        )
        messages = [("B", NodeMessage(kind="feedback", text="update needed"))]
        self.logic.set_clean_result("A", FeedbackResult(messages=messages))
        self.logic.set_dirty_result("A", True)
        self.cleaner.clean_subgraph("A")
        delivered = self.storage.added_messages[0][1]
        self.assertTrue(all(m.kind == "feedback" for m in delivered))

    def test_clean_logic_receives_pending_messages(self) -> None:
        """clean logic receives the node's pending messages from storage."""
        pending = [NodeMessage(kind="change", text="msg1"), NodeMessage(kind="feedback", text="msg2")]
        self.storage.set_node(
            "A",
            dependencies=[],
            reverse_dependencies=[],
            pending_messages=pending
        )
        self.logic.set_clean_result("A", NoChangeResult())
        self.logic.set_dirty_result("A", True)
        self.cleaner.clean_subgraph("A")
        self.assertEqual(len(self.logic.clean_calls), 1)
        self.assertEqual(self.logic.clean_calls[0][0], "A")
        self.assertEqual(self.logic.clean_calls[0][1], pending)

class DagCleanerImplTopologicalOrderTest(unittest.TestCase):
    """Tests for topological ordering per dag_cleaner_impl.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_clean_subgraph_processes_dependencies_first(self) -> None:
        """Dependencies are cleaned before dependents (topological order)."""
        self.storage.set_node(
            "A",
            dependencies=["B"],
            reverse_dependencies=[],
            pending_messages=[NodeMessage(kind="change", text="a_msg")]
        )
        self.storage.set_node(
            "B",
            dependencies=[],
            reverse_dependencies=["A"],
            pending_messages=[NodeMessage(kind="change", text="b_msg")]
        )
        self.logic.set_clean_result("B", NoChangeResult())
        self.logic.set_clean_result("A", NoChangeResult())
        self.logic.set_dirty_result("B", True)
        self.logic.set_dirty_result("A", False)
        self.cleaner.clean_subgraph("A")
        clean_order = [call[0] for call in self.logic.clean_calls]
        self.assertEqual(clean_order, ["B", "A"])

    def test_clean_subgraph_with_empty_pending_messages(self) -> None:
        """clean can be invoked with empty pending messages when dirty by custom conditions."""
        self.storage.set_node(
            "A",
            dependencies=[],
            reverse_dependencies=[],
            pending_messages=[]
        )
        self.logic.set_clean_result("A", NoChangeResult())
        self.logic.set_dirty_result("A", True)
        result = self.cleaner.clean_subgraph("A")
        self.assertTrue(result[0])
        self.assertIsInstance(result[1], NoChangeResult)


class DagCleanerImplFailureHandlingTest(unittest.TestCase):
    """Tests for failure handling per dag_cleaner_impl.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_clean_subgraph_halt_on_failure(self) -> None:
        """On failure, processing halts immediately without deleting node data."""
        self.storage.set_node(
            "A",
            dependencies=["B"],
            reverse_dependencies=[],
            pending_messages=[NodeMessage(kind="change", text="a_msg")]
        )
        self.storage.set_node(
            "B",
            dependencies=[],
            reverse_dependencies=["A"],
            pending_messages=[NodeMessage(kind="change", text="b_msg")]
        )
        self.logic.set_clean_result("B", FailureResult())
        self.logic.set_clean_result("A", NoChangeResult())
        self.logic.set_dirty_result("B", True)
        self.logic.set_dirty_result("A", False)
        result = self.cleaner.clean_subgraph("A")
        self.assertFalse(result[0])
        a_clean_calls = [call for call in self.logic.clean_calls if call[0] == "A"]
        self.assertEqual(len(a_clean_calls), 0)
        self.assertNotIn("B", self.storage.deleted_nodes)


class DagCleanerImplCycleDetectionTest(unittest.TestCase):
    """Tests for cycle detection per dag_cleaner_impl.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_self_loop_detected_as_cycle(self) -> None:
        """A node that depends on itself (self-loop) is detected as a cycle."""
        self.storage.set_node(
            "A",
            dependencies=["A"],
            reverse_dependencies=["A"],
            pending_messages=[]
        )
        self.logic.set_dirty_result("A", False)
        result = self.cleaner.clean_subgraph("A")
        self.assertFalse(result[0])
        self.assertIsInstance(result[1], FailureResult)

    def test_multi_node_cycle_detected(self) -> None:
        """A cycle among multiple nodes is detected and returns FailureResult."""
        self.storage.set_node(
            "A",
            dependencies=["B"],
            reverse_dependencies=["C"],
            pending_messages=[]
        )
        self.storage.set_node(
            "B",
            dependencies=["C"],
            reverse_dependencies=["A"],
            pending_messages=[]
        )
        self.storage.set_node(
            "C",
            dependencies=["A"],
            reverse_dependencies=["B"],
            pending_messages=[]
        )
        for node in ["A", "B", "C"]:
            self.logic.set_dirty_result(node, False)
        result = self.cleaner.clean_subgraph("A")
        self.assertFalse(result[0])
        self.assertIsInstance(result[1], FailureResult)

    def test_no_cycle_returns_success(self) -> None:
        """A DAG without cycles returns success."""
        self.storage.set_node(
            "A",
            dependencies=["B"],
            reverse_dependencies=[],
            pending_messages=[]
        )
        self.storage.set_node(
            "B",
            dependencies=["C"],
            reverse_dependencies=["A"],
            pending_messages=[]
        )
        self.storage.set_node(
            "C",
            dependencies=[],
            reverse_dependencies=["A", "B"],
            pending_messages=[]
        )
        for node in ["A", "B", "C"]:
            self.logic.set_clean_result(node, NoChangeResult())
            self.logic.set_dirty_result(node, False)
        result = self.cleaner.clean_subgraph("A")
        self.assertTrue(result[0])


class DagCleanerImplFeedbackValidationTest(unittest.TestCase):
    """Tests for feedback target validation per dag_cleaner_impl.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_feedback_to_node_outside_subgraph_returns_failure(self) -> None:
        """Feedback targeting a node outside the subgraph returns FailureResult."""
        self.storage.set_node(
            "A",
            dependencies=["B"],
            reverse_dependencies=[],
            pending_messages=[NodeMessage(kind="feedback", text="needs update")]
        )
        self.storage.set_node(
            "B",
            dependencies=[],
            reverse_dependencies=["A"],
            pending_messages=[]
        )
        messages = [("C", NodeMessage(kind="feedback", text="update needed"))]
        self.logic.set_clean_result("A", FeedbackResult(messages=messages))
        self.logic.set_dirty_result("A", True)
        self.logic.set_dirty_result("B", False)
        result = self.cleaner.clean_subgraph("A")
        self.assertFalse(result[0])
        self.assertIsInstance(result[1], FailureResult)

    def test_feedback_to_node_inside_subgraph_succeeds(self) -> None:
        """Feedback targeting a node inside the subgraph succeeds."""
        self.storage.set_node(
            "A",
            dependencies=["B"],
            reverse_dependencies=[],
            pending_messages=[NodeMessage(kind="feedback", text="needs update")]
        )
        self.storage.set_node(
            "B",
            dependencies=[],
            reverse_dependencies=["A"],
            pending_messages=[]
        )
        messages = [("B", NodeMessage(kind="feedback", text="update needed"))]
        self.logic.set_clean_result("A", FeedbackResult(messages=messages))
        self.logic.set_dirty_result("A", True)
        self.logic.set_dirty_result("B", False)
        result = self.cleaner.clean_subgraph("A")
        self.assertTrue(result[0])
        self.assertIsInstance(result[1], FeedbackResult)
        self.assertEqual(len(self.storage.added_messages), 1)
        self.assertEqual(self.storage.added_messages[0][0], "B")


class DagCleanerImplSubgraphScopeTest(unittest.TestCase):
    """Tests for subgraph scoping per dag_cleaner_impl.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_only_subgraph_nodes_are_cleaned(self) -> None:
        """Only nodes in the subgraph are cleaned; nodes outside are not."""
        # A depends on B; C is not in subgraph of A
        self.storage.set_node(
            "A",
            dependencies=["B"],
            reverse_dependencies=[],
            pending_messages=[NodeMessage(kind="change", text="a_msg")]
        )
        self.storage.set_node(
            "B",
            dependencies=[],
            reverse_dependencies=["A"],
            pending_messages=[NodeMessage(kind="change", text="b_msg")]
        )
        self.storage.set_node(
            "C",
            dependencies=[],
            reverse_dependencies=[],
            pending_messages=[NodeMessage(kind="change", text="c_msg")]
        )
        self.logic.set_clean_result("B", NoChangeResult())
        self.logic.set_clean_result("A", NoChangeResult())
        self.logic.set_clean_result("C", NoChangeResult())
        self.logic.set_dirty_result("B", True)
        self.logic.set_dirty_result("A", False)
        self.logic.set_dirty_result("C", True)
        self.cleaner.clean_subgraph("A")
        # C should not have been cleaned
        c_clean_calls = [call for call in self.logic.clean_calls if call[0] == "C"]
        self.assertEqual(len(c_clean_calls), 0)


class DagCleanerImplMultipleFeedbackTest(unittest.TestCase):
    """Tests for multiple feedback messages per dag_clean_logic.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_multiple_feedback_messages_delivered(self) -> None:
        """Multiple feedback messages from a single cleaning are delivered individually."""
        self.storage.set_node(
            "A",
            dependencies=["B", "C"],
            reverse_dependencies=[],
            pending_messages=[NodeMessage(kind="feedback", text="needs update")]
        )
        self.storage.set_node(
            "B",
            dependencies=[],
            reverse_dependencies=["A"],
            pending_messages=[]
        )
        self.storage.set_node(
            "C",
            dependencies=[],
            reverse_dependencies=["A"],
            pending_messages=[]
        )
        messages = [
            ("B", NodeMessage(kind="feedback", text="update B")),
            ("C", NodeMessage(kind="feedback", text="update C")),
        ]
        self.logic.set_clean_result("A", FeedbackResult(messages=messages))
        self.logic.set_dirty_result("A", True)
        self.logic.set_dirty_result("B", False)
        self.logic.set_dirty_result("C", False)
        self.cleaner.clean_subgraph("A")
        # Both B and C should receive a feedback message
        b_msgs = [call for call in self.storage.added_messages if call[0] == "B"]
        c_msgs = [call for call in self.storage.added_messages if call[0] == "C"]
        self.assertEqual(len(b_msgs), 1)
        self.assertEqual(len(c_msgs), 1)


class DagCleanerImplNoChangeResultDataHandlingTest(unittest.TestCase):
    """Tests for NoChangeResult data handling per dag_cleaner_impl.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_nochange_result_clears_pending_messages(self) -> None:
        """After NoChangeResult, the node's pending messages are cleared."""
        self.storage.set_node(
            "A",
            dependencies=[],
            reverse_dependencies=["B"],
            pending_messages=[NodeMessage(kind="change", text="msg")]
        )
        self.logic.set_clean_result("A", NoChangeResult())
        self.logic.set_dirty_result("A", False)
        self.cleaner.clean_subgraph("A")
        self.assertIn("A", self.storage.cleared_messages)


class DagCleanerImplChangeResultDataHandlingTest(unittest.TestCase):
    """Tests for ChangeResult data handling per dag_cleaner_impl.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_change_result_deletes_node_data(self) -> None:
        """After ChangeResult, the node's pending messages and known reverse dependencies are deleted."""
        self.storage.set_node(
            "A",
            dependencies=[],
            reverse_dependencies=["B"],
            pending_messages=[NodeMessage(kind="change", text="msg")]
        )
        self.logic.set_clean_result("A", ChangeResult(messages=[]))
        self.logic.set_dirty_result("A", True)
        self.cleaner.clean_subgraph("A")
        self.assertIn("A", self.storage.deleted_nodes)


class DagCleanerImplIsDirtyTest(unittest.TestCase):
    """Tests for is_dirty usage per dag_clean_logic.md."""

    def setUp(self) -> None:
        from dag_cleaner_impl import DagCleanerImpl
        self.storage = MockDagStorage()
        self.logic = MockCleanLogic()
        self.cleaner = DagCleanerImpl(self.storage, self.logic)

    def test_is_dirty_called_before_clean(self) -> None:
        """is_dirty is called to determine if a node requires cleaning."""
        self.storage.set_node(
            "A",
            dependencies=[],
            reverse_dependencies=[],
            pending_messages=[]
        )
        self.logic.set_clean_result("A", NoChangeResult())
        self.logic.set_dirty_result("A", True)
        self.cleaner.clean_subgraph("A")
        self.assertGreater(len(self.logic.is_dirty_calls), 0)


if __name__ == "__main__":
    unittest.main()
