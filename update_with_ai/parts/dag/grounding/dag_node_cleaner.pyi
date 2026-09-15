from framework import operation, poly_type, singleton_type
from typing import Protocol, Sequence
import dag_storage

@poly_type
class NodeCleaner(Protocol):
    """
PURPOSE:
Polymorphic service that cleans nodes sharing a role
"""

    @operation
    def clean(self, nodes: Sequence[dag_storage.Node]) -> bool:
        """
PURPOSE:
Cleans dirty nodes, communicating whether processing should continue

FRESH_REQUIREMENTS:
- Cleaning dirty nodes communicates whether processing should continue.
- Processing cannot continue only if a failure occurs while cleaning the nodes that cannot be handled by cleaning any other node.
"""
        ...

@singleton_type('agent_session')
class CleanedNodes(Protocol):
    """
PURPOSE:
Defined as an agent session service that presents the nodes currently being cleaned in the agent session
"""

    @property
    def nodes(self) -> Sequence[dag_storage.Node]:
        """
PURPOSE:
Sequence of nodes currently being cleaned in the agent session

FRESH_REQUIREMENTS:
- The cleaned nodes service presents the sequence of nodes currently being cleaned in the agent session.
"""
        ...

    @property
    def primary_node(self) -> dag_storage.Node:
        """
PURPOSE:
Primary target node currently being cleaned in the agent session

FRESH_REQUIREMENTS:
- The cleaned nodes service presents the primary target node currently being cleaned in the agent session.
"""
        ...
