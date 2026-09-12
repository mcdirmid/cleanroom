from framework import operation, override, singleton_type
import dag_cleaner
import dag_node_cleaner
import dag_storage
import model_config

@singleton_type('system')
class DagCleaner(dag_cleaner.DagCleaner):
    """
PURPOSE:
Implements dag cleaner to execute iterative topological graph cleaning

FRESH_REQUIREMENTS:
- The node visit limit is obtained from the model config.

GROUNDING_ARGUMENT:
- As a system singleton, DagCleaner orchestrates topological traversal and node cleaning passes, interacting with imported dag_storage and model_config in the same system lifecycle tier and the polymorphic dag_node_cleaner.NodeCleaner.
"""

    @property
    def node_visit_limit(self) -> int:
        """
PURPOSE:
Established as the node visit limit bounding the maximum times any node can be visited

GROUNDING_ARGUMENT:
- Obtained from imported model_config.ModelConfig in the same system lifecycle tier to bound node visits.
"""
        ...

    @operation
    @override
    def clean(self, node: dag_storage.Node, cleaner: dag_node_cleaner.NodeCleaner) -> None:
        """
PURPOSE:
Implements clean to execute dirty nodes in topological order with node visit limits

INHERITED_ASSUMPTIONS:
- [DagCleaner] The target node roots an acyclic subgraph in dag storage.

FRESH_REQUIREMENTS:
- Cleaning a target node collects all reachable dependencies from the node.
- In each cleaning iteration, reachable nodes are visited in topological order.
- Visiting a node checks whether the node is dirty, not whether it is cleaned.
- A node is cleaned only if it is dirty and all of its dependencies are clean.
- When cleaning a dirty node, the node cleaner is invoked to clean the node.
- If the node cleaner communicates that processing cannot continue, cleaning halts.
- If visiting any node exceeds the node visit limit, the dag cleaner halts with an unexpected failure.
- Cleaning succeeds when all reachable nodes in the subgraph are clean.

INHERITED_REQUIREMENTS:
- [DagCleaner] Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned.
- [DagCleaner] When cleaning a dirty node using the node cleaner, cleaning delegates to the node cleaner.
- [DagCleaner] If the node cleaner communicates that processing cannot continue, cleaning halts.
- [DagCleaner] Cleaning concludes when all nodes in the subgraph rooted at the node are clean.

GROUNDING_ARGUMENT:
- Receives node and cleaner as parameters, traverses reachable dependencies in topological order using imported dag_storage in the same system lifecycle tier, queries node dirty status, invokes cleaner.clean on dirty nodes, and enforces self.node_visit_limit bounds.
"""
        ...
