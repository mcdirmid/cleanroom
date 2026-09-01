"""Build runner interface for cleaning passes."""

from typing import Protocol, TypeAlias
from dataclasses import dataclass
from .dag_storage import NodeId, MessageContent

ResultSummary: TypeAlias = str


@dataclass(frozen=True)
class BuildResult:
    success: bool
    summary: ResultSummary


class BuildRunner(Protocol):
    def run_cleaning_pass(self, root: NodeId) -> BuildResult:
        ...

    def mark_node_dirty(self, target: NodeId, message: MessageContent) -> None:
        ...

    def inject_node_feedback(self, target: NodeId, feedback: MessageContent) -> None:
        ...

    def broadcast_node_change(self, origin: NodeId, change: MessageContent) -> None:
        ...
