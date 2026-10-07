# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T10:45:00Z
# CHANGE: new file
# CODE_HASH: 464c0c94162f
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from update_with_ai.parts.dag.lib import dag_storage


@dataclass(frozen=True)
class AttributionOutcome:
    """Outcome of blame attribution or failure.

    Args:
        accepted: True if blame or failure was accepted and recorded.
        message: Diagnostic explanation or acceptance notice.
        affected_nodes: Sequence of nodes affected by failure propagation.
    """

    accepted: bool
    message: str
    affected_nodes: Sequence[dag_storage.DagNode]


class AttributionCoordinator(Protocol):
    """Routes defect feedback to culprits and records failure states."""

    def blame_target(
        self,
        source_node: dag_storage.DagNode,
        blame_target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> AttributionOutcome: ...

    def fail_target(
        self,
        target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> AttributionOutcome: ...
