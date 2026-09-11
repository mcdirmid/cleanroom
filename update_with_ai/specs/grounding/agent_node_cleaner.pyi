from typing import Protocol, Set
from framework import operation, override, singleton_type
import dag_node_cleaner
import dag_storage

@singleton_type('system')
class AgentNodeCleaner(dag_node_cleaner.NodeCleaner, Protocol):
    """
PURPOSE:
Defined as a system service cleaning nodes via agent runs

INHERITANCE:
- dag_node_cleaner.NodeCleaner: Implements node cleaner to execute dirty nodes
"""

    @operation
    def clean_node(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        """
PURPOSE:
Cleans a dirty node within an agent session phase

FRESH_REQUIREMENTS:
- An agent node cleaner cleans a dirty node within an agent session phase.
- When workspace file modifications occur and task verification passes, the agent node cleaner produces change messages.
- When blame is signaled, the agent node cleaner produces feedback messages containing the blame explanation and addressed to the blamed dependency node.
- When cleaning succeeds without workspace file modifications, no messages are produced.
"""
        ...

    @operation
    @override
    def clean(self, node: dag_storage.Node) -> bool:
        """
PURPOSE:
Cleans a dirty node, interacting with dag storage to deliver messages and manage dirty state, communicating whether processing should continue

INHERITED_REQUIREMENTS:
- [NodeCleaner] After a dirty node is cleaned, the node is registered as a dependent to its non-silent dependencies.
- [NodeCleaner] Delivering messages delivers change messages to dependents when modifications are made, or feedback messages to dependencies when defects require revision.
- [NodeCleaner] Cleaning a dirty node communicates whether processing should continue.
- [NodeCleaner] Processing cannot continue only if a failure occurs while cleaning the node that cannot be handled by cleaning any other node.
"""
        ...
