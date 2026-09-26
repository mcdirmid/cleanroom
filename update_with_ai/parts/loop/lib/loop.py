# Requirements specified in loop.pyi
from dataclasses import dataclass
from typing import Protocol
from update_with_ai.parts.dag.lib import dag_storage


@dataclass(frozen=True)
class BuildResult:
    success: bool
    summary: str


class Loop(Protocol):
    def run_cleaning_pass(self, root: dag_storage.DagNode) -> BuildResult: ...

    def mark_node_dirty(
        self, target: dag_storage.DagNode, change: dag_storage.ChangeMessage
    ) -> None: ...

    def inject_node_feedback(
        self, target: dag_storage.DagNode, feedback: dag_storage.FeedbackMessage
    ) -> None: ...

    def broadcast_node_change(
        self, origin: dag_storage.DagNode, change: dag_storage.ChangeMessage
    ) -> None: ...
