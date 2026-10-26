"""Pretense State Machine and Fake Synthesis for DagConfig."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from pretense.proto import StateMachine, StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.dag.lib import dag_config
from update_with_ai.parts.dag.lib.dag_config import BatchSize, DagConfig, NodeVisitLimit


@dataclass
class DagConfigState:
    """Canonical model state for graph configuration."""
    node_visit_limit: int = 3
    batch_size: int = 2


proto = StateMachineProto[DagConfigState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_limits(): pass

@seed_limits.arguments
def _(
    state: DagConfigState,
    this: Any,
    node_visit_limit: int | NotBoundType = NotBound,
    batch_size: int | NotBoundType = NotBound,
) -> Optional[Tuple[int, int]]:
    lim = 3 if isinstance(node_visit_limit, NotBoundType) else int(node_visit_limit)
    bs = 2 if isinstance(batch_size, NotBoundType) else int(batch_size)
    return (lim, bs)

@seed_limits.provide
def _(
    state: DagConfigState,
    this: Any,
    node_visit_limit: int,
    batch_size: int,
    result: None = None,
) -> None:
    state.node_visit_limit = node_visit_limit
    state.batch_size = batch_size


# ==============================================================================
# 2. DagConfig Interface Properties
# ==============================================================================

@proto.transition(name="node_visit_limit")
def node_visit_limit(): pass

@node_visit_limit.arguments
def _(
    state: DagConfigState,
    this: Any,
) -> Optional[Tuple[()]]:
    return ()

@node_visit_limit.returns
def _(
    state: DagConfigState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[NodeVisitLimit]]:
    expected = NodeVisitLimit(state.node_visit_limit)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(name="batch_size")
def batch_size(): pass

@batch_size.arguments
def _(
    state: DagConfigState,
    this: Any,
) -> Optional[Tuple[()]]:
    return ()

@batch_size.returns
def _(
    state: DagConfigState,
    this: Any,
    outcome: object = NotBound,
) -> Optional[Outcome[BatchSize]]:
    expected = BatchSize(state.batch_size)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


def make_dag_config_fake(
    node_visit_limit: int = 3,
    batch_size: int = 2,
) -> tuple[StateMachine[DagConfigState], DagConfig]:
    """Helper creating a configured DagConfig fake and its driving state machine."""
    sm = proto.make_state_machine(DagConfigState(node_visit_limit=node_visit_limit, batch_size=batch_size))
    fake = sm.as_fake(dag_config.DagConfig)
    return sm, fake
