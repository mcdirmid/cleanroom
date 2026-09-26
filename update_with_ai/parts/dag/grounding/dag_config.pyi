from typing import Protocol
from framework import data_type, singleton_type


@data_type
class NodeVisitLimit(int):
    """Bound on the maximum number of times any node can be visited during dag cleaning."""
    ...


@data_type
class BatchSize(int):
    """Bound on the maximum number of dirty nodes of the same role processed together in an agent session."""
    ...


@singleton_type("system")
class DagConfig(Protocol):
    """Defined as a system service providing operational parameters for dependency graph execution."""

    @property
    def node_visit_limit(self) -> NodeVisitLimit:
        """Bound on the maximum number of times any node can be visited during dag cleaning.

        REQUIREMENTS:
        - The dag config provides the node visit limit bounding node visits during graph cleaning.

        GROUNDING_PROVISIONS:
        - knows("system", NodeVisitLimit): Exposes the node visit limit to satisfy requirement 3.
        """
        ...

    @property
    def batch_size(self) -> BatchSize:
        """Bound on the maximum number of dirty nodes of the same role processed together in an agent session.

        REQUIREMENTS:
        - The dag config provides the batch size bounding dirty nodes processed together in an agent session.

        GROUNDING_PROVISIONS:
        - knows("system", BatchSize): Exposes the batch size to satisfy requirement 4.
        """
        ...
