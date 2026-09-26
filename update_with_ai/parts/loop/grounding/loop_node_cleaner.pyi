from framework import operation, poly_type
from typing import Protocol, Sequence
import dag_storage


@poly_type
class NodeCleaner(Protocol):
    """Polymorphic service that cleans nodes sharing a role."""

    @operation
    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool:
        """Cleans dirty nodes, communicating whether processing should continue.

        REQUIREMENTS:
        - A node cleaner can clean dirty nodes, communicating whether processing should continue.
        - Processing cannot continue only if a failure occurs while cleaning the nodes that cannot be handled by cleaning any other node; otherwise, processing continues.

        GROUNDING_PROVISIONS:
        - action("clean", bool): Cleans dirty nodes batch.
        """
        ...
