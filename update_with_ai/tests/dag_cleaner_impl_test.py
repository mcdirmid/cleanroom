"""
Tests for the DagCleanerImpl implementation.

Asserts the behavioral contract of specs/dag_cleaner_impl-low.md (with its
dependencies specs/dag_cleaner-low.md, specs/dag_storage-low.md, and
specs/dag_clean_logic-low.md) against lib/dag_cleaner_impl.py, using mock
DagStorage and DagCleanLogic implementations. All state is driven through
the mocks so the tests observe exactly what the implementation reads and
writes.
"""

import unittest
from typing import Dict, List, Tuple

from update_with_ai.lib.dag_storage import (
    NodeId,
    NodeMessage,
    MessageKind,
    PendingMessages,
    NodeDependencies,
    KnownReverseDependencies,
    DagStorage,
)
from update_with_ai.lib.dag_clean_logic import (
    CleanResult,
    DagCleanLogic,
    ChangeResult,
    FeedbackResult,
    NoChangeResult,
    FailureResult,
)
from update_with_ai.lib.dag_cleaner import CleaningResult
from update_with_ai.lib.dag_cleaner_impl import DagCleanerImpl
from typing import cast


def msg(text: str, kind: str = "change") -> NodeMessage:
    """Test helper: build a NodeMessage (per dag_storage-low.md)."""
    return NodeMessage(kind=cast(MessageKind, kind), text=text)


class MockDagStorage(DagStorage):
    """In-memory DagStorage that records every read/write for assertions.

    Implements the dag_storage-low.md contract: get_node_dependencies returns
    the node's dependencies AND records the node as a known reverse dependency
    of each dependency (at most once); get_known_reverse_dependencies returns
    the recorded list. All reads/writes go through the protocol operations;
    nothing is cached by the implementation under test.
    """

    def __init__(self, nodes: List[NodeId], deps: Dict[NodeId, NodeDependencies]):
        self._messages: Dict[NodeId, List[NodeMessage]] = {n: [] for n in nodes}
        self._deps: Dict[NodeId, NodeDependencies] = deps
        self._reverse_deps: Dict[NodeId, List[NodeId]] = {n: [] for n in nodes}
        self.get_calls: List[NodeId] = []
        self.add_calls: List[Tuple[NodeId, List[NodeMessage]]] = []
        self.clear_calls: List[NodeId] = []
        self.delete_calls: List[NodeId] = []
        self.deps_calls: List[NodeId] = []
        self.reverse_calls: List[NodeId] = []

    def get_pending_messages(self, node_id: NodeId) -> PendingMessages:
        self.get_calls.append(node_id)
        return list(self._messages[node_id])

    def seed_messages(self, node_id: NodeId, messages: List[NodeMessage]) -> None:
        """Test-harness seeding that is not recorded as implementation I/O."""
        self._messages[node_id] = list(messages)

    def seed_reverse_dependency(self, dependency: NodeId, dependent: NodeId) -> None:
        """Pre-record a known reverse dependency (simulating prior resolution)."""
        if dependent not in self._reverse_deps[dependency]:
            self._reverse_deps[dependency].append(dependent)

    def add_messages(self, node_id: NodeId, messages: List[NodeMessage]) -> None:
        self.add_calls.append((node_id, list(messages)))
        if node_id not in self._messages:
            raise ValueError(f"precondition violated: unknown node {node_id}")
        self._messages[node_id].extend(messages)

    def clear_pending_messages(self, node_id: NodeId) -> None:
        """dag_storage-low.md: clearing removes only the node's pending
        messages; its known reverse dependencies remain."""
        self.clear_calls.append(node_id)
        self._messages[node_id] = []

    def delete_node_data(self, node_id: NodeId) -> None:
        """dag_storage-low.md: deleting removes the node's data — its pending
        messages and its known reverse dependencies."""
        self.delete_calls.append(node_id)
        self._messages[node_id] = []
        self._reverse_deps[node_id] = []

    def get_node_dependencies(self, node_id: NodeId) -> NodeDependencies:
        self.deps_calls.append(node_id)
        if node_id not in self._deps:
            raise ValueError(f"precondition violated: unknown node {node_id}")
        deps = self._deps[node_id]
        # dag_storage-low.md postcondition: records the node as a known reverse
        # dependency of each dependency it provides, at most once per dependency.
        for dep in deps:
            if node_id not in self._reverse_deps[dep]:
                self._reverse_deps[dep].append(node_id)
        return list(deps)

    def get_known_reverse_dependencies(self, node_id: NodeId) -> KnownReverseDependencies:
        self.reverse_calls.append(node_id)
        return list(self._reverse_deps[node_id])

    def get_messages(self, node_id: NodeId) -> List[NodeMessage]:
        return list(self._messages[node_id])


class MockDagCleanLogic(DagCleanLogic):
    """DagCleanLogic that returns scripted per-node results.

    A node is dirty iff it has pending messages, unless it is in
    ``forced_dirty`` or ``always_dirty`` is set (matching the dirtiness
    signals the LLS describes: pending messages or custom conditions).
    """

    def __init__(self):
        self.results: Dict[NodeId, List[CleanResult]] = {}
        self.forced_dirty: set = set()
        self.always_dirty = False
        self.clean_calls: List[Tuple[NodeId, PendingMessages]] = []
        self.is_dirty_calls: List[Tuple[NodeId, PendingMessages]] = []

    def set_result(self, node_id: NodeId, result: CleanResult) -> None:
        """Script a result that repeats for every clean of the node."""
        self.results[node_id] = [result]

    def set_results(self, node_id: NodeId, results: List[CleanResult]) -> None:
        """Script a sequence of results, consumed one clean at a time."""
        self.results[node_id] = list(results)

    def force_dirty(self, node_id: NodeId) -> None:
        self.forced_dirty.add(node_id)

    def clean(self, node_id: NodeId, messages: PendingMessages) -> CleanResult:
        self.clean_calls.append((node_id, list(messages)))
        queue = self.results.get(node_id)
        if not queue:
            return NoChangeResult()
        if len(queue) > 1:
            return queue.pop(0)
        return queue[0]

    def is_dirty(self, node_id: NodeId, pending_messages: PendingMessages) -> bool:
        self.is_dirty_calls.append((node_id, list(pending_messages)))
        return (
            self.always_dirty
            or node_id in self.forced_dirty
            or len(pending_messages) > 0
        )


def make_dag(
    graph: Dict[NodeId, NodeDependencies], nodes: List[NodeId]
) -> Tuple[MockDagStorage, MockDagCleanLogic, DagCleanerImpl]:
    """Build storage + clean logic + DagCleanerImpl over the given graph.

    The dag_cleaner_impl implementation is configured with dag_storage (message
    persistence and graph access) and dag_clean_logic only; there is no
    separate topology configuration.
    """
    storage = MockDagStorage(nodes, deps=graph)
    logic = MockDagCleanLogic()
    impl = DagCleanerImpl(storage=storage, clean_logic=logic)
    return storage, logic, impl


class TestCleanSubgraphSuccess(unittest.TestCase):
    """LLS: returns (True, CleanResult) with NoChange/Change/Feedback routing."""

    def test_nothing_dirty_returns_no_change(self):
        storage, logic, impl = make_dag({"A": []}, ["A"])
        result = impl.clean_subgraph("A")
        self.assertEqual(result, (True, NoChangeResult()))
        self.assertEqual(logic.clean_calls, [])  # nothing was cleaned

    def test_no_change_result_cleans_and_clears(self):
        # dag_clean_logic LLS: NoChangeResult = cleaned successfully, no messages.
        storage, logic, impl = make_dag({"A": []}, ["A"])
        storage.seed_messages("A", [msg("m1"), msg("m2")])
        logic.set_result("A", NoChangeResult())

        result = impl.clean_subgraph("A")

        self.assertEqual(result, (True, NoChangeResult()))
        self.assertEqual(logic.clean_calls, [("A", [msg("m1"), msg("m2")])])
        # On success all pending messages were processed (cleared from storage);
        # a no-change clean clears only messages — no data is deleted.
        self.assertEqual(storage.get_messages("A"), [])
        self.assertEqual(storage.clear_calls, ["A"])
        self.assertEqual(storage.delete_calls, [])

    def test_no_change_result_keeps_known_reverse_dependencies(self):
        # dag_cleaner LLS: a node cleaned without producing messages retains its known
        # reverse dependencies; only its pending messages are cleared.
        storage, logic, impl = make_dag({"A": ["B"], "B": []}, ["A", "B"])
        storage.seed_reverse_dependency("B", "C")
        storage.seed_messages("B", [msg("m")])
        logic.set_result("B", NoChangeResult())

        result = impl.clean_subgraph("A")

        self.assertTrue(result[0])
        self.assertEqual(storage.get_messages("B"), [])
        # B's entry was cleared, not deleted: C (seeded) and A (recorded during
        # traversal) are still known reverse dependencies of B — a later change
        # broadcast reaches them.
        self.assertEqual(storage.get_known_reverse_dependencies("B"), ["C", "A"])

    def test_change_routed_to_all_known_reverse_dependencies(self):
        # dag_cleaner LLS: change messages delivered to all KNOWN reverse dependencies
        # (as provided by dag_storage); nodes outside the subgraph may receive
        # messages but are not cleaned. B is depended on by A (in subgraph) and
        # C (outside subgraph); C was recorded earlier (its dependencies were
        # resolved in a prior run), so C is a known reverse dependency of B.
        storage, logic, impl = make_dag(
            {"A": ["B"], "C": ["B"], "B": []}, ["A", "B", "C"]
        )
        storage.seed_reverse_dependency("B", "C")
        storage.seed_messages("B", [msg("m")])
        logic.set_result("B", ChangeResult(messages=[msg("x")]))

        ok, res = impl.clean_subgraph("A")

        self.assertTrue(ok)
        self.assertIsInstance(res, NoChangeResult)
        # Every known reverse dependency of B (A and C) received the broadcast.
        self.assertIn(("A", [msg("x")]), storage.add_calls)
        self.assertIn(("C", [msg("x")]), storage.add_calls)
        # C is outside the subgraph: it received the message but was not cleaned.
        self.assertEqual(storage.get_messages("C"), [msg("x")])
        # A received it and was cleaned; B's change deleted B's data.
        self.assertEqual(storage.get_messages("A"), [])
        self.assertEqual(storage.get_messages("B"), [])

    def test_change_not_routed_to_unrecorded_reverse_dependency(self):
        # dag_cleaner LLS: change messages are delivered only to KNOWN reverse
        # dependencies. C depends on B but has never had its dependencies
        # resolved (never recorded), so C does not receive B's broadcast.
        storage, logic, impl = make_dag(
            {"A": ["B"], "C": ["B"], "B": []}, ["A", "B", "C"]
        )
        storage.seed_messages("B", [msg("m")])
        logic.set_result("B", ChangeResult(messages=[msg("x")]))

        ok, res = impl.clean_subgraph("A")

        self.assertTrue(ok)
        self.assertIsInstance(res, NoChangeResult)
        # Only A (recorded during traversal) received the broadcast.
        self.assertEqual(storage.add_calls, [("A", [msg("x")])])
        self.assertEqual(storage.get_messages("C"), [])

    def test_change_routing_skips_known_reverse_dependency_outside_graph(self):
        # dag_cleaner_impl LLS: change messages are broadcast to known reverse
        # dependencies present in the graph; a known reverse dependency not in
        # the graph (cannot be resolved) is skipped. X is a recorded reverse
        # dependency of B (from a prior run) but is not in this run's graph.
        storage, logic, impl = make_dag({"A": ["B"], "B": []}, ["A", "B"])
        storage.seed_reverse_dependency("B", "X")
        storage.seed_messages("B", [msg("m")])
        logic.set_result("B", ChangeResult(messages=[msg("x")]))

        ok, res = impl.clean_subgraph("A")

        self.assertTrue(ok)
        self.assertIsInstance(res, NoChangeResult)
        # X (outside the graph) was attempted but skipped (no exception
        # propagated); A, which is in the graph, received the broadcast.
        self.assertIn(("X", [msg("x")]), storage.add_calls)
        self.assertIn(("A", [msg("x")]), storage.add_calls)
        self.assertEqual(storage.get_messages("A"), [])

    def test_feedback_routed_to_specified_dependencies(self):
        # dag_cleaner LLS: feedback messages delivered to specified dependencies
        # (within the subgraph), not broadcast. B cleans and feeds back to its
        # dependency C, which is then cleaned; B is cleaned again after C
        # (a feedback clean keeps B's messages — it cannot succeed without
        # change — so B re-cleans and this time succeeds).
        storage, logic, impl = make_dag({"A": ["B"], "B": ["C"], "C": []}, ["A", "B", "C"])
        storage.seed_messages("B", [msg("m")])
        logic.set_results("B", [
            FeedbackResult(messages=[("C", msg("fb", "feedback"))]),
            NoChangeResult(),
        ])
        logic.set_result("C", NoChangeResult())

        ok, res = impl.clean_subgraph("A")

        self.assertTrue(ok)
        self.assertIsInstance(res, NoChangeResult)
        # Feedback went only to the specified target C.
        self.assertEqual(storage.add_calls, [("C", [msg("fb", "feedback")])])
        # B cleaned (feedback), then C cleaned, then B cleaned again (its
        # pending messages were retained by the feedback clean) and cleared.
        self.assertEqual(
            [node for node, _ in logic.clean_calls], ["B", "C", "B"]
        )
        self.assertEqual(storage.get_messages("B"), [])
        self.assertEqual(storage.get_messages("C"), [])
        # The feedback clean removed no stored data for B: only the final
        # no-change clean cleared B's messages.
        self.assertEqual(storage.delete_calls, [])
        self.assertEqual(storage.clear_calls, ["C", "B"])

    def test_returns_last_clean_result(self):
        # LLS: on success the returned CleanResult is a NoChangeResult,
        # ChangeResult, or FeedbackResult (here: the last clean's ChangeResult).
        storage, logic, impl = make_dag({"A": []}, ["A"])
        storage.seed_messages("A", [msg("m")])
        change = ChangeResult(messages=[msg("broadcast")])
        logic.set_result("A", change)

        result = impl.clean_subgraph("A")

        self.assertEqual(result, (True, change))
        # No reverse dependencies, so nothing to route; A's change deleted A's
        # data (messages and known reverse dependencies).
        self.assertEqual(storage.get_messages("A"), [])
        self.assertEqual(storage.delete_calls, ["A"])

    def test_clean_receives_exactly_the_pending_messages(self):
        # dag_clean_logic LLS: clean processes the node's pending messages.
        storage, logic, impl = make_dag({"A": ["B"], "B": []}, ["A", "B"])
        storage.seed_messages("B", [msg("a"), msg("b")])
        logic.set_result("B", NoChangeResult())

        impl.clean_subgraph("A")

        self.assertEqual(logic.clean_calls, [("B", [msg("a"), msg("b")])])


class TestCleanSubgraphFailure(unittest.TestCase):
    """LLS failure handling: halt, keep the offending node's messages."""

    def test_clean_failure_halts_and_keeps_messages(self):
        # dag_cleaner LLS: on failure, the offending node's messages remain unchanged,
        # previously cleaned nodes retain changes, and processing halts.
        storage, logic, impl = make_dag({"A": ["B"], "B": ["C"], "C": []}, ["A", "B", "C"])
        storage.seed_messages("C", [msg("mc")])
        storage.seed_messages("B", [msg("mb")])
        storage.seed_messages("A", [msg("ma")])
        logic.set_result("C", NoChangeResult())
        logic.set_result("B", FailureResult())

        result = impl.clean_subgraph("A")

        self.assertEqual(result, (False, FailureResult()))
        # C (topologically first) was cleaned before the failure at B.
        self.assertEqual([node for node, _ in logic.clean_calls], ["C", "B"])
        # Failed node B's messages remain unchanged; A was never cleaned (halt).
        self.assertEqual(storage.get_messages("B"), [msg("mb")])
        self.assertEqual(storage.get_messages("A"), [msg("ma")])
        # C's messages were cleared (previously cleaned node retains its change).
        self.assertEqual(storage.get_messages("C"), [])

    def test_failure_does_not_delete_or_route_anything(self):
        # dag_clean_logic LLS: on failure no messages are produced; the
        # failed node's pending messages remain.
        storage, logic, impl = make_dag({"A": ["B"], "B": []}, ["A", "B"])
        storage.seed_messages("B", [msg("m")])
        logic.set_result("B", FailureResult())

        result = impl.clean_subgraph("A")

        self.assertEqual(result, (False, FailureResult()))
        self.assertEqual(storage.get_messages("B"), [msg("m")])
        self.assertEqual(storage.delete_calls, [])
        self.assertEqual(storage.clear_calls, [])
        self.assertEqual(storage.add_calls, [])

    def test_feedback_outside_subgraph_fails(self):
        # dag_cleaner LLS: feedback targeting a node outside the subgraph returns
        # (False, FailureResult); the offending node's messages remain
        # unchanged and processing halts. C exists in the graph but is not in
        # the subgraph rooted at A.
        storage, logic, impl = make_dag({"A": ["B"], "B": [], "C": []}, ["A", "B", "C"])
        storage.seed_messages("B", [msg("m")])
        logic.set_result("B", FeedbackResult(messages=[("C", msg("out", "feedback"))]))

        result = impl.clean_subgraph("A")

        self.assertEqual(result, (False, FailureResult()))
        # Nothing was deleted or routed; B's messages are unchanged.
        self.assertEqual(storage.get_messages("B"), [msg("m")])
        self.assertEqual(storage.delete_calls, [])
        self.assertEqual(storage.clear_calls, [])
        self.assertEqual(storage.add_calls, [])

    def test_cycle_returns_failure_state_unchanged(self):
        # dag_cleaner LLS: a cyclic topology returns (False, FailureResult) with state
        # unchanged (no messages deleted or routed).
        storage, logic, impl = make_dag({"A": ["B"], "B": ["A"]}, ["A", "B"])
        storage.seed_messages("A", [msg("ma")])
        storage.seed_messages("B", [msg("mb")])

        result = impl.clean_subgraph("A")

        self.assertEqual(result, (False, FailureResult()))
        self.assertEqual(storage.get_messages("A"), [msg("ma")])
        self.assertEqual(storage.get_messages("B"), [msg("mb")])
        # No message reads, writes, or deletes: the cycle is detected during
        # the topological sort, before any cleaning begins (dependencies were
        # read through dag_storage, but no pending messages were touched).
        self.assertEqual(storage.get_calls, [])
        self.assertEqual(storage.add_calls, [])
        self.assertEqual(storage.delete_calls, [])
        self.assertEqual(storage.clear_calls, [])

    def test_self_loop_returns_failure(self):
        # dag_cleaner_impl LLS: self-loops (cycles of length 1) are detected during
        # cycle detection and produce a FailureResult.
        storage, logic, impl = make_dag({"A": ["A"]}, ["A"])
        storage.seed_messages("A", [msg("m")])

        result = impl.clean_subgraph("A")

        self.assertEqual(result, (False, FailureResult()))
        self.assertEqual(storage.get_messages("A"), [msg("m")])
        self.assertEqual(storage.delete_calls, [])

    def test_self_feedback_recleans_until_cap_then_fails(self):
        # dag_cleaner LLS: a feedback (blame) result is not a successful cleaning — the
        # node keeps its pending messages and known reverse dependencies, so it
        # stays dirty and is re-cleaned. A clean logic that keeps blaming
        # re-routes the same feedback and never clears the node: the run hits
        # the termination cap and fails (1 node -> cap 1 * 2 = 2 cleans).
        storage, logic, impl = make_dag({"A": []}, ["A"])
        storage.seed_messages("A", [msg("init")])
        logic.set_result("A", FeedbackResult(messages=[("A", msg("self", "feedback"))]))

        result = impl.clean_subgraph("A")

        self.assertEqual(result, (False, FailureResult()))
        # The node was cleaned twice (the cap); the routed self-feedback was
        # added to the retained messages on the second clean.
        self.assertEqual(
            logic.clean_calls,
            [
                ("A", [msg("init")]),
                ("A", [msg("init"), msg("self", "feedback")]),
            ],
        )
        # No data was deleted (feedback removes no stored data).
        self.assertEqual(storage.delete_calls, [])

    def test_termination_cap_always_dirty(self):
        # An is_dirty() that never clears must also hit the cap rather than
        # loop forever. 3-node chain -> cap is 3 * 4 = 12 cleans.
        storage, logic, impl = make_dag({"A": ["B"], "B": ["C"], "C": []}, ["A", "B", "C"])
        logic.always_dirty = True

        result = impl.clean_subgraph("A")

        self.assertEqual(result, (False, FailureResult()))
        self.assertEqual(len(logic.clean_calls), 12)

    def test_cap_reached_exactly_when_clean_completes_succeeds(self):
        # dag_cleaner LLS: failure is signaled when cleaning would otherwise continue
        # without bound (the bound is exceeded). If the cap is reached exactly
        # as the final dirty node is cleaned (a fully-clean state), the run
        # completes successfully.
        storage, logic, impl = make_dag({"A": []}, ["A"])

        calls = {"n": 0}

        def scripted_is_dirty(node_id, pending_messages):
            calls["n"] += 1
            # Dirty for the first two probes, then clean: the cap (1 * 2) is
            # reached exactly as the second clean completes.
            return calls["n"] <= 2

        logic.is_dirty = scripted_is_dirty  # type: ignore[method-assign]

        result = impl.clean_subgraph("A")

        self.assertEqual(result, (True, NoChangeResult()))
        self.assertEqual(len(logic.clean_calls), 2)


class TestCleanSubgraphOrdering(unittest.TestCase):
    """LLS: topological order (dependencies before dependents), determinism."""

    def test_topological_order_chain(self):
        storage, logic, impl = make_dag({"A": ["B"], "B": ["C"], "C": []}, ["A", "B", "C"])
        for node in ["A", "B", "C"]:
            storage.seed_messages(node, [msg("m")])
            logic.set_result(node, NoChangeResult())

        result = impl.clean_subgraph("A")

        self.assertTrue(result[0])
        self.assertEqual([node for node, _ in logic.clean_calls], ["C", "B", "A"])

    def test_node_not_cleaned_while_dependency_dirty(self):
        # dag_cleaner LLS: a node is not cleaned while any dependency is dirty.
        storage, logic, impl = make_dag({"A": ["B"], "B": []}, ["A", "B"])
        storage.seed_messages("A", [msg("ma")])
        storage.seed_messages("B", [msg("mb")])
        logic.set_result("A", NoChangeResult())
        logic.set_result("B", NoChangeResult())

        result = impl.clean_subgraph("A")

        self.assertTrue(result[0])
        self.assertEqual([node for node, _ in logic.clean_calls], ["B", "A"])

    def test_deterministic_ordering(self):
        # dag_cleaner_impl LLS: any deterministic ordering of same-level nodes is
        # acceptable as long as dependencies precede dependents. Two runs over
        # identical state must produce identical clean orders.
        def run() -> List[NodeId]:
            storage, logic, impl = make_dag(
                {"A": ["B", "C"], "B": [], "C": []}, ["A", "B", "C"]
            )
            for node in ["A", "B", "C"]:
                storage.seed_messages(node, [msg("m")])
                logic.set_result(node, NoChangeResult())
            impl.clean_subgraph("A")
            return [node for node, _ in logic.clean_calls]

        first = run()
        second = run()
        self.assertEqual(first, second)
        self.assertEqual(first, ["B", "C", "A"])  # B, C same level: sorted order


class TestCleanSubgraphAtomicityAndStorage(unittest.TestCase):
    """LLS: atomic cleaning and no caching (all state through storage)."""

    def test_success_clean_is_atomic(self):
        # dag_cleaner LLS: each node's cleaning is atomic: on success the node's
        # messages are processed exactly once and its result routed; on failure
        # neither happens (tested separately below). A change result deletes
        # the node's data; a no-change result clears only its messages.
        storage, logic, impl = make_dag({"A": ["B"], "B": []}, ["A", "B"])
        storage.seed_messages("B", [msg("m")])
        logic.set_result("B", ChangeResult(messages=[msg("x")]))

        result = impl.clean_subgraph("A")

        self.assertTrue(result[0])
        # B changed -> its data deleted; A received B's change and was cleaned
        # with a no-change result -> only A's messages were cleared.
        self.assertEqual(storage.delete_calls, ["B"])
        self.assertEqual(storage.clear_calls, ["A"])
        # B's change routed exactly once, to its only reverse dependency A.
        self.assertEqual(storage.add_calls, [("A", [msg("x")])])
        self.assertEqual(storage.get_messages("A"), [])
        self.assertEqual(storage.get_messages("B"), [])

    def test_failure_clean_is_atomic(self):
        # A failing clean must not delete or route anything for that node.
        storage, logic, impl = make_dag({"A": ["B"], "B": []}, ["A", "B"])
        storage.seed_messages("B", [msg("m")])
        logic.set_result("B", FailureResult())

        result = impl.clean_subgraph("A")

        self.assertEqual(result, (False, FailureResult()))
        self.assertEqual(storage.delete_calls, [])
        self.assertEqual(storage.clear_calls, [])
        self.assertEqual(storage.add_calls, [])
        self.assertEqual(storage.get_messages("B"), [msg("m")])

    def test_no_caching_all_reads_through_storage(self):
        # dag_cleaner_impl LLS: no caching; all state reads/writes go through storage.
        # Every dirtiness probe must perform a fresh storage read, and every
        # clean must read the node's pending messages from storage.
        storage, logic, impl = make_dag({"A": ["B"], "B": []}, ["A", "B"])
        storage.seed_messages("B", [msg("m")])
        logic.set_result("B", NoChangeResult())

        impl.clean_subgraph("A")

        reads = len(storage.get_calls)
        probes = len(logic.is_dirty_calls)
        cleans = len(logic.clean_calls)
        # reads = one per is_dirty probe + one per clean invocation.
        self.assertEqual(reads, probes + cleans)
        self.assertEqual(cleans, 1)
        # After the clear, the follow-up dirtiness check observed the empty
        # state through storage, so B was not cleaned a second time.
        self.assertEqual(storage.get_messages("B"), [])


if __name__ == "__main__":
    unittest.main()
