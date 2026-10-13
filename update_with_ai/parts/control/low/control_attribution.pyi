# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:36Z
# LAST_CHANGED: 2026-10-11T03:36:57Z
# CHANGE: Add source attribution marking and file-level blame contracts; drop return-type restatements
# CODE_HASH: 263ee70a3e6f
# SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
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
        - WHEN the blame target is not a declared upstream dependency, MUST reject blame.
        - WHEN the source node role is not configured to deliver feedback to the blame target role, MUST reject blame.
        - WHEN the explanation contains newline characters, MUST reject blame.
        - WHEN an in-batch dependency of the source node is not clean, MUST reject blame.
        - WHEN blame is accepted, MUST record the feedback message on the culprit node in graph storage.
        - WHEN blame is accepted, MUST mark the culprit node dirty in graph storage.
        - WHEN blame is accepted, MUST mark the source target node as attributed.
        - WHEN blame is accepted, MUST mark in-batch dependent nodes as failed.
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
        - MUST preserve dirty status on the target node in graph storage.
        - MUST record the failure diagnostic on the target node in graph storage.
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
        - WHEN the critique contains newline characters, MUST reject blame.
        - WHEN the culprit file cannot be resolved, MUST reject blame.
        - WHEN the caller role is not configured to deliver feedback to the culprit role, MUST reject blame.
        - WHEN blame is accepted, MUST execute build blame targets or mutate in-band metadata to record feedback and dirty status, and MUST synchronize the affected files.
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
        - WHEN the target file cannot be resolved, MUST reject failure recording.
        - WHEN failure recording is accepted, MUST append the failure diagnostic and mark dirty status on the target file.
        - WHEN failure recording is accepted, MUST synchronize the affected files.
        """
        ...

    @operation
    def match_blame_target(
        self, node: dag_storage.DagNode, val: Any, val_str: str
    ) -> Optional[agent_file_alias.BoundFile]:
        """Matches a blame target value against configured blame targets for a node."""
        ...
