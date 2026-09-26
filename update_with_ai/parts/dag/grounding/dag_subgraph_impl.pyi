from typing import List, Sequence, Self
from framework import operation, override, singleton_type
import dag_config
import dag_storage
import dag_subgraph


@singleton_type("system")
class DagSubgraph(dag_subgraph.DagSubgraph):
    """Coordinates topological subgraph queries and visit bounds across dag storage.

    GROUNDING_ARGUMENT:
    - As a system singleton, DagSubgraph manages target subgraph indexing and ready batch calculation, accessing imported dag_storage and dag_config in the same system lifecycle tier.
    """

    @operation
    @override
    def set_target(self, root: dag_storage.DagNode) -> None:
        """Sets the target node, scoping the target subgraph and establishing dependency-first topological order.

        Args:
            root: Root target node in dag storage.

        REQUIREMENTS:
        - Setting a target node scopes the target subgraph to all reachable dependency nodes rooted at the target node in dag storage, arranged in dependency-first topological order, breaking ties by role tier depth first, then by unit address.

        GROUNDING_PROVISIONS:
        - action("set_target", dag_storage.DagNode): Sets active target subgraph to satisfy requirement 1.

        GROUNDING_ARGUMENT:
        - action("set_target", Self) :- action("get_dependencies", dag_storage.DagStorage), action("order_nodes_topologically", Self).
        """
        ...

    @property
    @override
    def is_complete(self) -> bool:
        """Reports whether all reachable nodes in the target subgraph are clean.

        REQUIREMENTS:
        - The target subgraph is complete if, but only if, all reachable nodes in the target subgraph are clean in dag storage.

        GROUNDING_PROVISIONS:
        - knows("subgraph_complete", bool): Reports whether target subgraph is complete to satisfy requirement 2.

        GROUNDING_ARGUMENT:
        - knows("subgraph_complete", Self) :- knows("cleaning_required", dag_storage.DagStorage).
        """
        ...

    @operation
    @override
    def next_ready_batch(self) -> List[dag_storage.DagNode]:
        """Provides the next batch of ready dirty nodes to clean.

        REQUIREMENTS:
        - The next ready batch consists of contiguous dirty nodes in topological order that share the same role address, prioritized by role tier precedence (prioritizing lib before test, and test before qa) and having all their dependencies in the target subgraph clean in dag storage or present in the same ready batch, starting from the earliest ready dirty node in topological order and bounded by the batch size obtained from dag config.
        - If no dirty node in the target subgraph has all its dependencies in the target subgraph clean in dag storage, the next ready batch is an empty sequence.

        GROUNDING_PROVISIONS:
        - action("next_ready_batch", List[dag_storage.DagNode]): Provides next ready batch to satisfy requirements 3 and 4.

        GROUNDING_ARGUMENT:
        - action("next_ready_batch", Self) :- knows("cleaning_required", dag_storage.DagStorage), knows("system", dag_config.DagConfig).
        """
        ...

    @operation
    @override
    def record_visit(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """Records an execution visit for a batch of nodes being cleaned, enforcing iteration limits.

        Args:
            nodes: The batch of nodes visited.

        REQUIREMENTS:
        - Recording a visit for a batch of nodes advances the visit count for each node in the batch, raising an unexpected failure if any node exceeds the node visit limit obtained from dag config.

        GROUNDING_PROVISIONS:
        - action("record_visit", Sequence[dag_storage.DagNode]): Enforces visit limits to satisfy requirement 5.

        GROUNDING_ARGUMENT:
        - action("record_visit", Self) :- knows("system", dag_config.DagConfig), action("advance_visit_count", Self).
        """
        ...
