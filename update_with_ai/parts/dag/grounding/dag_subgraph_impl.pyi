from framework import operation, override, singleton_type
from typing import List, Sequence
import dag_config
import dag_storage
import dag_subgraph

@singleton_type('system')
class DagSubgraph(dag_subgraph.DagSubgraph):
    """
PURPOSE:
Coordinates topological subgraph queries and visit bounds across dag storage

GROUNDING_ARGUMENT:
- As a system singleton, DagSubgraph manages target subgraph indexing and ready batch calculation, accessing imported dag_storage and dag_config in the same system lifecycle tier.
"""

    @operation
    @override
    def set_target(self, root: dag_storage.Node) -> None:
        """
PURPOSE:
Sets the target node, scoping the target subgraph and establishing dependency-first topological order

FRESH_REQUIREMENTS:
- Setting a target node scopes the target subgraph to all reachable dependency nodes rooted at the target node in dag storage, arranged in dependency-first topological order.

INHERITED_REQUIREMENTS:
- [DagSubgraph] Setting a target collects all reachable dependency nodes from the target node in dag storage and computes their dependency-first topological order.

GROUNDING_ARGUMENT:
- Receives root as a parameter, traverses reachable dependency relationships using imported dag_storage in the same system lifecycle tier, orders nodes topologically, and resets node visit counters.
"""
        ...

    @property
    @override
    def is_complete(self) -> bool:
        """
PURPOSE:
Reports whether all reachable nodes in the target subgraph are clean

INHERITED_REQUIREMENTS:
- [DagSubgraph] The target subgraph is complete if, but only if, all reachable nodes in the target subgraph are clean in dag storage.

GROUNDING_ARGUMENT:
- Queries is_dirty on imported dag_storage in the same system lifecycle tier across all reachable nodes collected for the active target subgraph.
"""
        ...

    @operation
    @override
    def next_ready_batch(self) -> List[dag_storage.Node]:
        """
PURPOSE:
Provides the next batch of ready dirty nodes to clean

FRESH_REQUIREMENTS:
- The next ready batch consists of contiguous dirty nodes in topological order that share the same role address and have all their dependencies in the target subgraph clean in dag storage, starting from the earliest ready dirty node and bounded by the batch size obtained from dag config.
- If no dirty node in the target subgraph has all its dependencies in the target subgraph clean in dag storage, the next ready batch is an empty sequence.

INHERITED_REQUIREMENTS:
- [DagSubgraph] When obtaining the next ready batch, uncleaned dirty nodes in topological order whose dependencies in the target subgraph are clean in dag storage are selected, grouped by role address up to a maximum batch size.

GROUNDING_ARGUMENT:
- Scans topologically ordered nodes for the target subgraph using imported dag_storage to evaluate dependency cleanliness, groups contiguous matching candidates by role up to batch_size from imported dag_config, and returns the batch.
"""
        ...

    @operation
    @override
    def record_visit(self, nodes: Sequence[dag_storage.Node]) -> None:
        """
PURPOSE:
Records an execution visit for a batch of nodes being cleaned, enforcing iteration limits

FRESH_REQUIREMENTS:
- Recording a visit for a batch of nodes advances the visit count for each node in the batch, raising an unexpected failure if any node exceeds the node visit limit obtained from dag config.

INHERITED_REQUIREMENTS:
- [DagSubgraph] Recording a visit increments the visit count for each node in the batch and raises an unexpected failure if visiting any node exceeds the node visit limit.

GROUNDING_ARGUMENT:
- Receives nodes as a parameter, increments the per-node visit counter, queries node_visit_limit from imported dag_config in the same system lifecycle tier, and raises RuntimeError if exceeded.
"""
        ...
