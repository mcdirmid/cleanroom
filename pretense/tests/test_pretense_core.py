"""Comprehensive tests for Pretense core engine."""

import pytest
from typing import Set, Tuple, Optional

from pretense.collections import PretenseDict, PretenseSet, make_tup
from pretense.context import with_draw
from pretense.fake import FakeAdapter
from pretense.compiler import compile_hypothesis_test_case
from pretense.proto import StateMachineProto
from pretense.sentinels import (
    AmbiguousTransitionError,
    NoMatchingTransitionError,
    NotBound,
    NotBoundType,
    Raised,
)


class DummyTarget:
    def add_item(self, item_id: str, tags: Set[str] = set()) -> None:
        pass

    def get_count(self) -> int:
        return 0


class DummyState:
    def __init__(self) -> None:
        self.items: PretenseSet[str] = PretenseSet()
        self.tags: PretenseDict[str, Set[str]] = PretenseDict()


def test_pretense_set_helpers():
    s = PretenseSet[str](["a", "b"])
    assert s.get_in("a") == "a"
    assert s.get_in("c") is None
    assert s.get_in(NotBound) in {"a", "b"}

    assert s.get_not_in("c") == "c"
    assert s.get_not_in("a") is None

    # Fallback sequential generation
    fresh = s.get_not_in(NotBound, prefix="node_")
    assert fresh is not None and fresh not in s

    # Tombstone ring buffer
    s.remove("a")
    assert "a" in s._tombstones


def test_make_tup_composition():
    chooser = make_tup(
        lambda state, this, x: x if x > 0 else None,
        lambda state, this, y: y * 2 if y > 0 else None,
    )
    assert chooser(None, None, 5, 10) == (5, 20)
    assert chooser(None, None, -1, 10) is None
    assert chooser(None, None, 5, -1) is None


def test_fake_zero_ambiguity_and_dispatch():
    proto = StateMachineProto[DummyState]()

    @proto.transition(DummyTarget.add_item)
    def add_fresh_item(): pass

    @add_fresh_item.require
    def _(state: DummyState, this) -> bool:
        return len(state.items) < 100

    @add_fresh_item.arguments
    def _(state: DummyState, this: object, item_id: str | NotBoundType = NotBound, tags: Set[str] | NotBoundType = NotBound) -> Optional[Tuple[str, Set[str]]]:
        if isinstance(item_id, NotBoundType):
            resolved_id = "fresh_item"
        elif item_id in state.items:
            return None
        else:
            resolved_id = item_id

        if isinstance(tags, NotBoundType):
            resolved_tags: Set[str] = set()
        else:
            resolved_tags = tags
        return resolved_id, resolved_tags

    @add_fresh_item.returns
    def _(state: DummyState, this: object, item_id: str, tags: Set[str], outcome: object = NotBound):
        return None

    @add_fresh_item.provide
    def _(state: DummyState, this: object, item_id: str, tags: Set[str], result: None) -> None:
        state.items.add(item_id)

    # 1. Success dispatch
    state = DummyState()
    fake = proto.make_fake(DummyTarget, state)
    fake.add_item("item_1")
    assert "item_1" in state.items

    # 2. No matching transition error (duplicate rejected by arguments)
    with pytest.raises(NoMatchingTransitionError):
        fake.add_item("item_1")


def test_fake_ambiguity_detection():
    proto = StateMachineProto[DummyState]()

    # Two transitions with identical match profiles
    @proto.transition(DummyTarget.add_item)
    def branch_one(): pass

    @branch_one.arguments
    def _(state, this, item_id=NotBound, tags=NotBound):
        return "x", set()

    @proto.transition(DummyTarget.add_item)
    def branch_two(): pass

    @branch_two.arguments
    def _(state, this, item_id=NotBound, tags=NotBound):
        return "x", set()

    fake = proto.make_fake(DummyTarget, DummyState())
    # Must fail with AmbiguousTransitionError
    with pytest.raises(AmbiguousTransitionError):
        fake.add_item("x")


def test_fake_exception_handling_bypasses_provide():
    proto = StateMachineProto[DummyState]()
    provide_executed = False

    @proto.transition(DummyTarget.add_item)
    def fail_transition(): pass

    @fail_transition.returns
    def _(state, this, *args, outcome=NotBound):
        raise ValueError("Invalid item!")

    @fail_transition.provide
    def _(state, this, *args, result=None):
        nonlocal provide_executed
        provide_executed = True

    fake = proto.make_fake(DummyTarget, DummyState())
    with pytest.raises(ValueError, match="Invalid item!"):
        fake.add_item("bad_item")

    # Provide MUST NOT execute on domain exceptions!
    assert not provide_executed


def test_hypothesis_compilation_and_execution():
    class RealTarget:
        def __init__(self) -> None:
            self.items: set[str] = set()

        def add_item(self, item_id: str, tags: Set[str] = set()) -> None:
            if item_id in self.items:
                raise ValueError("Duplicate")
            self.items.add(item_id)

    proto = StateMachineProto[DummyState]()

    @proto.transition(RealTarget.add_item)
    def add_fresh(): pass

    @add_fresh.arguments
    def _(state: DummyState, this: object, item_id: str | NotBoundType = NotBound, tags: Set[str] | NotBoundType = NotBound):
        if item_id is NotBound:
            item_id = f"item_{len(state.items)}"
        return item_id, set()

    @add_fresh.returns
    def _(state: DummyState, this, item_id: str, tags: Set[str], outcome=NotBound):
        if isinstance(outcome, Raised):
            raise AssertionError(f"Unexpected exception: {outcome.exc}")
        return None

    @add_fresh.provide
    def _(state: DummyState, this, item_id: str, tags: Set[str], result: None):
        state.items.add(item_id)

    TestClass = compile_hypothesis_test_case(
        proto=proto,
        sut_factory=lambda: RealTarget(),
        initial_state_factory=lambda: DummyState(),
        name="TestRealTargetFuzzing",
    )

    tc = TestClass.TestCase("runTest")
    tc.runTest()


def test_active_step_diagnostic_formatting():
    from pretense.synthesis import TraceStep
    from pretense.compiler import format_active_step_diagnostic, get_active_step
    import pretense.compiler as comp

    assert format_active_step_diagnostic() is None
    assert get_active_step() is None

    step1 = TraceStep("init_node", "init_node", True, ("node_1",), {}, None)
    step2 = TraceStep("execute_task", "run", False, ("task_a", 10), {}, None)

    comp._ACTIVE_TRACE = [step1, step2]
    comp._ACTIVE_STEP = step2

    diag = format_active_step_diagnostic()
    assert diag is not None
    assert "Active Pretense Transition: 'execute_task' (method: run)" in diag
    assert "Arguments: ('task_a', 10)" in diag
    assert "Preceding Steps (1):" in diag
    assert "1. init_node('node_1')" in diag

    comp._ACTIVE_STEP = None
    comp._ACTIVE_TRACE = []


def test_pretense_cli_target_timeout(tmp_path):
    import subprocess
    import sys

    test_file = tmp_path / "hang_test_pretense.py"
    test_file.write_text(
        "import unittest, time\n\n"
        "class HangTest(unittest.TestCase):\n"
        "    def test_infinite_loop(self):\n"
        "        while True:\n"
        "            time.sleep(0.01)\n"
    )

    proc = subprocess.run(
        [sys.executable, "-m", "pretense.cli", str(test_file), "--timeout", "0.5"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "execution timed out after 0.5s" in proc.stderr
    assert "infinite loop or deadlock detected" in proc.stderr
    assert "Thread stack trace at timeout" in proc.stderr


