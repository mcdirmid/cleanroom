from __future__ import annotations
from update_with_ai.parts.agent.lib.session import AgentSessionTier
from support.lib.lifecycle import Singleton
from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence
from update_with_ai.parts.agent.lib import file_alias
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


class AttributionCoordinator(Singleton[AgentSessionTier], Protocol):
    """Routes defect feedback to culprits and records failure states."""

    # Contract: Attributes defect to upstream dependency; rejects if not upstream, role disallowed, has newlines, or in-batch dependencies not clean; records feedback, marks dirty and failed.
    def blame_target(
        self,
        source_node: dag_storage.DagNode,
        blame_target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> AttributionOutcome: ...

    # Contract: Records task failure diagnostic for target node, preserves dirty status, and marks in-batch dependent nodes as failed.
    def fail_target(
        self,
        target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> AttributionOutcome: ...

    # Contract: Attributes defect blame to upstream culprit file; rejects if has newlines, exceeds limit, unresolved, or role disallowed; mutates metadata and synchronizes affected files.
    def blame_culprit_file(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        caller_role: Optional[str] = None,
    ) -> AttributionOutcome: ...

    # Contract: Records task failure for target file; appends diagnostic, marks dirty, and synchronizes affected files.
    def fail_target_file(
        self,
        target_file: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
    ) -> AttributionOutcome: ...

    # Contract: Matches a blame target value against configured blame targets for a node.
    def match_blame_target(
        self, node: dag_storage.DagNode, val: Any, val_str: str
    ) -> Optional[file_alias.BoundFile]: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-06T10:45:00Z
# CHANGE: new file
# --- END CLEANROOM METADATA ---
