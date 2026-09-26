from framework import data_type, operation, singleton_type
from typing import Protocol
from dataclasses import dataclass
import dag_storage


@dataclass(frozen=True)
@data_type
class BuildResult:
    """Final outcome of a cleaning pass reporting overall success or failure."""

    def __init__(self, success: bool, summary: str) -> None:
        ...

    @property
    def success(self) -> bool:
        """Indicates whether the cleaning pass succeeded."""
        ...

    @property
    def summary(self) -> str:
        """Summary description of the build pass outcome."""
        ...


@singleton_type('system')
class Loop(Protocol):
    """System service executing topological build and cleaning passes across workspace nodes."""

    @operation
    def run_cleaning_pass(self, root: dag_storage.DagNode) -> BuildResult:
        """Executes a complete topological cleaning pass over the acyclic subgraph rooted at a target node.

        REQUIREMENTS:
        - The loop executes a cleaning pass over an acyclic subgraph rooted at a target node in graph storage.
        - The loop produces a build result upon pass completion.

        GROUNDING_PROVISIONS:
        - action("run_cleaning_pass", BuildResult): Runs topological cleaning pass.
        """
        ...

    @operation
    def mark_node_dirty(self, target: dag_storage.DagNode, change: dag_storage.ChangeMessage) -> None:
        """Marks a target node dirty by injecting a change message into its pending messages.

        REQUIREMENTS:
        - The loop marks a target node dirty by injecting a change message into its pending messages.

        GROUNDING_PROVISIONS:
        - action("mark_node_dirty", None): Marks node dirty.
        """
        ...

    @operation
    def inject_node_feedback(self, target: dag_storage.DagNode, feedback: dag_storage.FeedbackMessage) -> None:
        """Injects feedback into a target node message queue, marking it dirty for cleaning.

        REQUIREMENTS:
        - The loop injects a caller-supplied feedback message into a target node.

        GROUNDING_PROVISIONS:
        - action("inject_node_feedback", None): Injects feedback into target node.
        """
        ...

    @operation
    def broadcast_node_change(self, origin: dag_storage.DagNode, change: dag_storage.ChangeMessage) -> None:
        """Broadcasts a change message from an origin node to all of its reverse dependencies.

        REQUIREMENTS:
        - The loop broadcasts a caller-supplied change message from a node to all of its reverse dependencies.

        GROUNDING_PROVISIONS:
        - action("broadcast_node_change", None): Broadcasts change message.
        """
        ...
