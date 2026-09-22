from framework import operation, singleton_type
from typing import List, Protocol, Sequence
import dag_storage

@singleton_type('system')
class DagSubgraph(Protocol):
    """
PURPOSE:
Models an active execution subgraph rooted at a target node in dag storage
"""

    @operation
    def set_target(self, root: dag_storage.Node) -> None:
        """
PURPOSE:
Sets the target node, collecting reachable nodes and computing dependency-first topological order

FRESH_REQUIREMENTS:
- Setting a target collects all reachable dependency nodes from the target node in dag storage and computes their dependency-first topological order.
"""
        ...

    @property
    def is_complete(self) -> bool:
        """
PURPOSE:
Reports whether all reachable nodes in the target subgraph are clean

FRESH_REQUIREMENTS:
- The target subgraph is complete if, but only if, all reachable nodes in the target subgraph are clean in dag storage.
"""
        ...

    @operation
    def next_ready_batch(self) -> List[dag_storage.Node]:
        """
PURPOSE:
Provides the next batch of ready dirty nodes to clean

FRESH_REQUIREMENTS:
- When obtaining the next ready batch, uncleaned dirty nodes prioritized by role tier precedence (upstream roles before downstream roles) whose dependencies in the target subgraph are clean in dag storage or present in the same ready batch are selected, grouped by role address up to a maximum batch size.
"""
        ...

    @operation
    def record_visit(self, nodes: Sequence[dag_storage.Node]) -> None:
        """
PURPOSE:
Records an execution visit for a batch of nodes being cleaned, enforcing iteration limits

FRESH_REQUIREMENTS:
- Recording a visit increments the visit count for each node in the batch and raises an unexpected failure if visiting any node exceeds the node visit limit.
"""
        ...
