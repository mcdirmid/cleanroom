# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
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


# Contract: BuildResult represents the final outcome of a cleaning pass.
@dataclass(frozen=True)
class BuildResult:
    success: bool
    summary: BuildSummary


# Contract: Loop system service executes topological build and cleaning passes across workspace nodes.
class Loop(Protocol):
    # Contract: Loop.clean_subgraph - executes a cleaning pass over the acyclic subgraph rooted at a target node.
    def clean_subgraph(self, target: dag_storage.DagNode) -> BuildResult: ...

    # Contract: Loop.mark_subgraph_clean - marks all nodes in an acyclic subgraph clean, materializing missing templates and clearing unacted feedback.
    def mark_subgraph_clean(self, target: dag_storage.DagNode) -> None: ...

    # Contract: Loop.mark_dirty - marks a target node dirty by removing its last cleaned timestamp from in-band source metadata.
    def mark_dirty(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None: ...

    # Contract: Loop.inject_feedback - injects a feedback message into a target node.
    def inject_feedback(
        self, target: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None: ...

    # Contract: Loop.record_change - records a change message on a target node and dynamically invalidates downstream dependencies.
    def record_change(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None: ...

