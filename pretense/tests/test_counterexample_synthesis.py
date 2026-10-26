"""Test verifying counterexample shrinking and unit test synthesis."""

from pretense.proto import StateMachineProto
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType, Raised, Value


class BuggyTarget:
    def __init__(self) -> None:
        self.nodes: set[str] = set()

    def add_node(self, node_id: str) -> None:
        # BUG: Fails to detect duplicate nodes!
        self.nodes.add(node_id)


class DAGState:
    def __init__(self) -> None:
        self.nodes: set[str] = set()


proto = StateMachineProto[DAGState]()

@proto.transition(BuggyTarget.add_node)
def add_fresh_node(): pass

@add_fresh_node.arguments
def _(state: DAGState, this: object, node_id: str | NotBoundType = NotBound):
    if node_id is NotBound:
        node_id = f"node_{len(state.nodes)}"
    elif node_id in state.nodes:
        return None
    return (node_id,)

@add_fresh_node.returns
def _(state: DAGState, this, node_id: str, outcome=NotBound):
    return None

@add_fresh_node.provide
def _(state: DAGState, this, node_id: str, result: None):
    state.nodes.add(node_id)


# Transition: duplicate node expects ValueError!
@proto.transition(BuggyTarget.add_node)
def add_duplicate_node(): pass

@add_duplicate_node.require
def _(state: DAGState, this) -> bool:
    return len(state.nodes) > 0

@add_duplicate_node.arguments
def _(state: DAGState, this: object, node_id: str | NotBoundType = NotBound):
    if node_id is NotBound:
        node_id = next(iter(state.nodes))
    elif node_id not in state.nodes:
        return None
    return (node_id,)

@add_duplicate_node.returns
def _(state: DAGState, this, node_id: str, outcome=NotBound):
    if outcome is NotBound:
        raise ValueError(f"Duplicate node '{node_id}'")
    # SUT must raise ValueError!
    assert isinstance(outcome, Raised) and isinstance(outcome.exc, ValueError), (
        f"Expected SUT to raise ValueError, but SUT succeeded with outcome={outcome!r}"
    )
    return outcome


TestBuggyTargetFuzzing = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=lambda: BuggyTarget(),
    initial_state_factory=lambda: DAGState(),
    name="TestBuggyTargetFuzzing",
)
