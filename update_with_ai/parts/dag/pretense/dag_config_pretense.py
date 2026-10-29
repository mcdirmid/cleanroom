"""Pretense State Machine and Fake Synthesis for DagConfig."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from pretense import Domain, StateMachine, TransitionContext, transition
from update_with_ai.parts.dag.lib import dag_config
from update_with_ai.parts.dag.lib.dag_config import BatchSize, DagConfig, NodeVisitLimit


@dataclass
class DagConfigState:
    """Canonical model state for graph configuration."""
    node_visit_limit: int = 3
    batch_size: int = 2


class DagConfigStateMachine(StateMachine[DagConfigState]):
    """State machine for graph configuration."""

    def __init__(
        self,
        state: Optional[DagConfigState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DagConfigState(), singletons=singletons)

    @transition.seeding(name="seed_limits")
    def seed_limits(self, ctx: TransitionContext[Any, [int, int], None]) -> None:
        ctx.arguments(
                    node_visit_limit=Domain(strategy=lambda: 3),
                    batch_size=Domain(strategy=lambda: 2),
                )
        ctx.returns(lambda node_visit_limit=3, batch_size=2: None)
        ctx.update(lambda res, node_visit_limit=3, batch_size=2: (
            setattr(self.state, "node_visit_limit", int(node_visit_limit)),
            setattr(self.state, "batch_size", int(batch_size)),
        ))

    @transition(name="node_visit_limit")
    def node_visit_limit(self, ctx: TransitionContext[DagConfig, [], NodeVisitLimit]) -> None:
        ctx.arguments()
        ctx.returns(lambda: NodeVisitLimit(self.state.node_visit_limit))
        ctx.update(lambda res: None)

    @transition(name="batch_size")
    def batch_size(self, ctx: TransitionContext[DagConfig, [], BatchSize]) -> None:
        ctx.arguments()
        ctx.returns(lambda: BatchSize(self.state.batch_size))
        ctx.update(lambda res: None)


proto = DagConfigStateMachine()


def make_dag_config_fake(
    node_visit_limit: int = 3,
    batch_size: int = 2,
) -> tuple[StateMachine[DagConfigState], DagConfig]:
    """Helper creating a configured DagConfig fake and its driving state machine."""
    sm = DagConfigStateMachine(state=DagConfigState(node_visit_limit=node_visit_limit, batch_size=batch_size))
    fake = sm.as_fake(dag_config.DagConfig)
    return sm, fake
