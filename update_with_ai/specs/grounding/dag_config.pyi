from typing import Protocol
from framework import data_type, singleton_type

@data_type
class NodeVisitLimit(int):
    """
PURPOSE:
Bound on the maximum number of times any node can be visited during dag cleaning
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
