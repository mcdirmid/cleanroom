"""
Interface LLS: dag_cleaner

Defines the DagCleaner protocol and CleaningResult type alias for cleaning
a DAG subgraph rooted at a target node.
"""

from __future__ import annotations

from typing import Protocol, TypeAlias
from .dag_storage import NodeId
from .dag_clean_logic import CleanResult

CleaningResult: TypeAlias = tuple[bool, CleanResult]


class DagCleaner(Protocol):
    """Protocol for cleaning all dirty nodes in a DAG subgraph."""

    def clean_subgraph(self, target_node: NodeId) -> CleaningResult:
        """Clean all dirty nodes in the subgraph rooted at target_node.

        Returns (True, CleanResult) on success, (False, FailureResult) on failure.
        """
        ...
