from typing import Protocol
from framework import data_type, singleton_type

@data_type
class NodeVisitLimit(int):
    """
PURPOSE:
Bound on the maximum number of times any node can be visited during dag cleaning
"""
    ...

@data_type
class BatchSize(int):
    """
PURPOSE:
Bound on the maximum number of dirty nodes of the same role processed together in an agent session
"""
    ...

@singleton_type('system')
class DagConfig(Protocol):
    """
PURPOSE:
Defined as a system service providing operational parameters for dependency graph execution
"""

    @property
    def node_visit_limit(self) -> NodeVisitLimit:
        """
PURPOSE:
Bound on the maximum number of times any node can be visited during dag cleaning

FRESH_REQUIREMENTS:
- The dag config provides the node visit limit bounding node visits during graph cleaning.
"""
        ...

    @property
    def batch_size(self) -> BatchSize:
        """
PURPOSE:
Bound on the maximum number of dirty nodes of the same role processed together in an agent session

FRESH_REQUIREMENTS:
- The dag config provides the batch size bounding dirty nodes processed together in an agent session.
"""
        ...
