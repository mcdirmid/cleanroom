from framework import data_type, operation, singleton_type
from typing import Protocol
from dataclasses import dataclass
import dag_storage

@dataclass(frozen=True)
@data_type
class BuildResult:
    """
PURPOSE:
Final outcome of a cleaning pass reporting overall success or failure
"""

    def __init__(self, success: bool, summary: str) -> None:
        ...

    @property
    def success(self) -> bool:
        """
PURPOSE:
Indicates whether the cleaning pass succeeded
"""
        ...

    @property
    def summary(self) -> str:
        """
PURPOSE:
Summary description of the build pass outcome
"""
        ...

@singleton_type('system')
class DagRunner(Protocol):
    """
PURPOSE:
Defined as a system service executing topological build and cleaning passes across workspace nodes
"""

    @operation
    def run_cleaning_pass(self, root: dag_storage.Node) -> BuildResult:
        """
PURPOSE:
Executes a complete topological cleaning pass over the acyclic subgraph rooted at a target node

FRESH_REQUIREMENTS:
- A dag runner executes a cleaning pass over an acyclic subgraph rooted at a target node in dag storage.
- A dag runner produces a build result upon pass completion.
"""
        ...

    @operation
    def mark_node_dirty(self, target: dag_storage.Node, message: dag_storage.Change) -> None:
        """
PURPOSE:
Marks a target node dirty by injecting a change message into its pending messages

FRESH_REQUIREMENTS:
- A dag runner marks a target node dirty by injecting a change message into its pending messages in dag storage.
"""
        ...

    @operation
    def inject_node_feedback(self, target: dag_storage.Node, feedback: dag_storage.Feedback) -> None:
        """
PURPOSE:
Injects feedback into a target node message queue, marking it dirty for cleaning

FRESH_REQUIREMENTS:
- A dag runner injects a caller-supplied feedback message into a target node.
"""
        ...

    @operation
    def broadcast_node_change(self, origin: dag_storage.Node, change: dag_storage.Change) -> None:
        """
PURPOSE:
Broadcasts a change message from an origin node to all of its reverse dependencies

FRESH_REQUIREMENTS:
- A dag runner broadcasts a caller-supplied change message from a node to all of its reverse dependencies.
"""
        ...
