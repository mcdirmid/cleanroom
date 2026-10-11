# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:03Z
# LAST_CHANGED: 2026-10-11T04:59:19Z
# CHANGE: Remove generated scaffold markers and carry the grounding specification's class and property contracts into the interface
# CODE_HASH: 33567465df66
# --- END CLEANROOM METADATA ---

from __future__ import annotations

from typing import NewType, Protocol

# Requirements specified in dag_config.pyi

NodeVisitLimit = NewType("NodeVisitLimit", int)

BatchSize = NewType("BatchSize", int)


class DagConfig(Protocol):
    """System service exposing operational limits governing graph node visit caps and dirty node batch sizes during cleaning passes."""

    @property
    def node_visit_limit(self) -> NodeVisitLimit:
        """Bound on the number of visits any node receives across dependency graph cleaning, enforced when a subgraph records the visits of a cleaned batch."""
        ...

    @property
    def batch_size(self) -> BatchSize:
        """Bound on the number of dirty nodes of the same role address collected into a single cleaning batch."""
        ...
