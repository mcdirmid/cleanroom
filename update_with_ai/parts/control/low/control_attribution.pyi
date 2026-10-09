# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 712fdf002958
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for control_attribution."""

from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import dag_storage
import src_metadata


@data_type
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


@singleton_type("agent_session")
class AttributionCoordinator(InTier[AgentSessionTier], Protocol):
    """Coordinator that routes defect feedback and records failure states."""

    @operation
    def blame_target(
        self,
        source_node: dag_storage.DagNode,
        blame_target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> AttributionOutcome:
        """Attributes defect to an upstream dependency node.

        POSTCONDITIONS:
        - When blame target is not an upstream dependency, MUST reject blame.
        - When source node role is not configured to deliver feedback to blame target role, MUST reject blame.
        - When explanation contains newline characters, MUST reject blame.
        - When in-batch dependency is not clean, MUST reject blame.
        - When accepted, MUST record feedback message on culprit node in graph storage.
        - When accepted, MUST mark culprit node dirty in graph storage.
        - When accepted, MUST mark in-batch dependent nodes as failed.
        """
        ...

    @operation
    def fail_target(
        self,
        target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> AttributionOutcome:
        """Records task failure for a target node.

        POSTCONDITIONS:
        - MUST preserve dirty status on target node in graph storage.
        - MUST record failure message on target node.
        - MUST mark in-batch dependent nodes as failed.
        """
        ...

    @operation
    def blame_culprit_file(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        caller_role: Optional[str] = None,
    ) -> AttributionOutcome:
        """Attributes defect blame to an upstream culprit file.

        POSTCONDITIONS:
        - When critique contains newline characters, MUST reject blame.
        - When culprit file cannot be resolved, MUST reject blame.
        - When caller role is not configured to deliver feedback to culprit role, MUST reject blame.
        - When accepted, MUST record in-band feedback and dirty status via direct metadata mutation in canonical repository.
        - MUST return AttributionOutcome indicating acceptance status and message.
        """
        ...

    @operation
    def fail_target_file(
        self,
        target_file: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
    ) -> AttributionOutcome:
        """Records task failure for a target file.

        POSTCONDITIONS:
        - When target file cannot be resolved, MUST reject failure recording.
        - When accepted, MUST mark target file dirty and record failure diagnostics in canonical repository.
        - MUST return AttributionOutcome indicating acceptance status and message.
        """
        ...

    @operation
    def match_blame_target(
        self, node: dag_storage.DagNode, val: Any, val_str: str
    ) -> Optional[agent_file_alias.BoundFile]:
        """Matches a blame target value against configured blame targets for a node."""
        ...

