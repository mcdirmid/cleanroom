"""Dag config grounding specification module."""

from __future__ import annotations
from typing import NewType, Protocol
from support.lib.grounding_support import InTier, SystemTier

NodeVisitLimit = NewType("NodeVisitLimit", int)
BatchSize = NewType("BatchSize", int)


class DagConfig(InTier[SystemTier], Protocol):
    """System service providing graph traversal and batching limits."""

    @property
    def node_visit_limit(self) -> NodeVisitLimit:
        """
        DEFERRED:
        - Bound on the maximum number of times any node can be visited.
        """
        raise NotImplementedError

    @property
    def batch_size(self) -> BatchSize:
        """
        DEFERRED:
        - Bound on the maximum number of dirty nodes of the same role processed together.
        """
        raise NotImplementedError
