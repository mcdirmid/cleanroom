"""Dag config low-level interface specification."""

from typing import NewType, Protocol
from framework import singleton_type
from support.lib.lifecycle import InTier, SystemTier

NodeVisitLimit = NewType("NodeVisitLimit", int)
BatchSize = NewType("BatchSize", int)


@singleton_type("system")
class DagConfig(InTier[SystemTier], Protocol):
    """System service providing graph traversal and batching limits."""

    @property
    def node_visit_limit(self) -> NodeVisitLimit:
        """Bound on the maximum number of times any node can be visited."""
        ...

    @property
    def batch_size(self) -> BatchSize:
        """Bound on the maximum number of dirty nodes of the same role processed together."""
        ...
