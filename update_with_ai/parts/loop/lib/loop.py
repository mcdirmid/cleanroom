# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-11T04:57:55Z
# CHANGE: Align mark_dirty with the declared ChangeMessage parameter and prune the uncontracted broadcast_change member
# CODE_HASH: b0ee25671e8a
# --- END CLEANROOM METADATA ---

# Requirements specified in loop.pyi
from __future__ import annotations
from dataclasses import dataclass
from typing import NewType, Protocol
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
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None: ...

    def inject_feedback(
        self, target: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None: ...

    def record_change(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None: ...
