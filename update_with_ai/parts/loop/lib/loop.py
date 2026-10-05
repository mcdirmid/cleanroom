# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: fc1e1e63497b
# --- END CLEANROOM METADATA ---

# Requirements specified in loop.pyi
from dataclasses import dataclass
from typing import NewType, Optional, Protocol
from update_with_ai.parts.dag.lib import dag_storage

BuildSummary = NewType("BuildSummary", str)


@dataclass(frozen=True)
class BuildResult:
    success: bool
    summary: BuildSummary


class Loop(Protocol):
    def clean_subgraph(self, target: dag_storage.DagNode) -> BuildResult: ...

    def mark_subgraph_clean(self, target: dag_storage.DagNode) -> None: ...

    def mark_dirty(
        self,
        target: dag_storage.DagNode,
        message: Optional[dag_storage.ChangeMessage] = None,
    ) -> None: ...

    def inject_feedback(
        self, target: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None: ...

    def broadcast_change(
        self, source: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None: ...

    def record_change(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None: ...
