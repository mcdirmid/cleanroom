# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:02Z
# LAST_CHANGED: 2026-10-11T03:48:23Z
# CHANGE: Declare the inherited dirty evaluation explicitly for in-band metadata and non-silent dependency changes
# CODE_HASH: cac5a8cbb49a
# SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
# --- END CLEANROOM METADATA ---

"""Agent storage low-level interface specification."""

from dataclasses import dataclass
from typing import NewType, Protocol
from framework import data_type, operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import dag_storage

TaskPrompt = NewType("TaskPrompt", str)


@dataclass(frozen=True)
@data_type
class NodeDefinition:
    """Encapsulates the execution configuration and task prompt a declared target carries.

    Args:
        task_prompt: The instruction describing the work required to clean the node.
    """
    task_prompt: TaskPrompt


@singleton_type("system")
class AgentStorage(dag_storage.DagStorage, InTier[SystemTier], Protocol):
    """System service acting as dag storage backed by workspace target manifests that configure node execution and dependency structure, maintaining nodes and dependencies declared by workspace targets."""

    @operation
    def get_node_definition(self, node: dag_storage.DagNode) -> NodeDefinition:
        """Provides the node definition encapsulating the execution configuration and task prompt for a declared node.

        Args:
            node: The graph node to query.

        Returns:
            The node definition metadata record.

        PRECONDITIONS:
        - A caller supplies a dag node.
        """
        ...

    @operation
    def get_task_prompt(self, node: dag_storage.DagNode) -> TaskPrompt:
        """Provides the task prompt instruction describing the work required to clean a declared node.

        Args:
            node: The graph node to query.

        Returns:
            The task prompt instruction.

        PRECONDITIONS:
        - A caller supplies a dag node.
        """
        ...

    @operation
    @override
    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        """Evaluates whether a node is dirty from the in-band source file metadata of the node and the change state of its non-silent dependencies.

        Args:
            node: The node whose dirty status is evaluated.

        Returns:
            True if the node needs to be cleaned.

        POSTCONDITIONS:
        - WHEN the in-band source file metadata of the node is missing, invalid, or uncleaned with a change description, MUST return true.
        - WHEN any non-silent dependency of the node was changed after the node was last cleaned, MUST return true.
        """
        ...
