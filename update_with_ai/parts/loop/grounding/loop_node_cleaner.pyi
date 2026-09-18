from framework import operation, poly_type
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
- A node cleaner can clean dirty nodes, communicating whether processing should continue.
- Processing cannot continue only if a failure occurs while cleaning the nodes that cannot be handled by cleaning any other node; otherwise, processing continues.
"""
        ...
