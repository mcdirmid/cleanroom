"""Loop node cleaner implementation low-level specification."""

from typing import Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import dag_storage
import loop_node_cleaner


@singleton_type("system")
class NodeCleaner(loop_node_cleaner.NodeCleaner, InTier[SystemTier]):
    """Realizes node clean execution, session seeding, and message dispatch."""

    @operation
    @override
    def clean(self, nodes: Sequence[dag_storage.DagNode]) -> bool:
        """Cleans dirty nodes within an agent session phase.

        Args:
            nodes: The sequence of dirty nodes sharing a role to clean.

        Returns:
            True if processing should continue, or False if an unhandleable failure occurred.

        POSTCONDITIONS:
        - MUST clean dirty nodes within an agent session phase presenting the node role.
        - MUST retry the session phase once upon encountering an unexpected failure before propagating.
        - WHEN the outcome signals advancement with file modifications, MUST deliver change messages to downstream dependents.
        - WHEN the outcome signals blame attributed to a configured blame target, MUST deliver feedback messages strictly to the declared feedback dependency node owning the blamed file.
        - WHEN the outcome signals blame attributed to a target failing to match a configured blame target, MUST produce no propagating messages and leave nodes dirty.
        - MUST NOT deliver feedback messages to non-feedback dependencies, guides, or fixed node specifications.
        - WHEN the outcome signals run failure, MUST leave nodes dirty and return false.
        - WHEN dirty nodes define no task prompt, MUST resolve pass-through changes without establishing an agent session.
        """
        ...
