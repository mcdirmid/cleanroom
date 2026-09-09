from framework import operation, poly_type, singleton_type
from typing import Protocol
import dag_storage

@poly_type
class NodeCleaner(Protocol):
    """
PURPOSE:
Defined as a polymorphic system service that cleans an individual node in a dag storage
"""

    @operation
    def clean(self, node: dag_storage.Node) -> bool:
        """
PURPOSE:
Cleans a dirty node, interacting with dag storage to deliver messages and manage dirty state, communicating whether processing should continue

FRESH_REQUIREMENTS:
- When cleaning a dirty node, a node cleaner interacts with dag storage to deliver messages and manages whether the node remains dirty.
- Delivering messages delivers change messages to dependents when modifications are made, or feedback messages to dependencies when defects require revision.
- Cleaning a dirty node communicates whether processing should continue.
- Processing cannot continue only if a failure occurs while cleaning the node that cannot be handled by cleaning any other node.
"""
        ...

@singleton_type('agent_session')
class CleanedNode(Protocol):
    """
PURPOSE:
Defined as an agent session service that presents the node currently being cleaned
"""

    @property
    def node(self) -> dag_storage.Node:
        """
PURPOSE:
Target node currently being cleaned in the agent session

FRESH_REQUIREMENTS:
- The cleaned node presents the node currently being cleaned in the agent session.
"""
        ...
