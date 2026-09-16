from dataclasses import dataclass
from typing import Protocol
from update_with_ai.parts.dag.lib import dag_storage


@dataclass(frozen=True)
class BuildResult:
    success: bool
    summary: str


class Loop(Protocol):
    def run_cleaning_pass(self, root: dag_storage.Node) -> BuildResult: ...

    def mark_node_dirty(
        self, target: dag_storage.Node, change: dag_storage.Change
    ) -> None: ...

    def inject_node_feedback(
        self, target: dag_storage.Node, feedback: dag_storage.Feedback
    ) -> None: ...

    def broadcast_node_change(
        self, origin: dag_storage.Node, change: dag_storage.Change
    ) -> None: ...
