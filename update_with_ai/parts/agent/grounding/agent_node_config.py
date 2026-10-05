# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 929051fd4d82
# GROUNDING_QA_AUDIT: 2026-10-05T04:28:01Z
# --- END CLEANROOM METADATA ---

"""Agent node config grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List, Mapping, NewType, Optional, Protocol, Sequence, Set, Tuple
from support.lib.grounding_support import AgentSessionTier, InTier
from parts.agent.grounding import agent_file_alias
from parts.dag.grounding import dag_storage

StepIndex = NewType("StepIndex", int)
StepTitle = NewType("StepTitle", str)
StepContent = NewType("StepContent", str)
GuideSummary = NewType("GuideSummary", str)
VerificationFailureInstructions = NewType("VerificationFailureInstructions", str)
VerificationDiagnostic = NewType("VerificationDiagnostic", str)
VerificationSuccessMessage = NewType("VerificationSuccessMessage", str)
NodeFeedback = NewType("NodeFeedback", str)
RoleName = NewType("RoleName", str)
ExecutionVersion = NewType("ExecutionVersion", int)
TemplateParamKey = NewType("TemplateParamKey", str)


@dataclass(frozen=True)
class StepSection:
    """Discrete milestone section within a guide."""

    index: StepIndex
    title: StepTitle
    content: StepContent


@dataclass(frozen=True)
class NodeGuide:
    """Structured instructional text containing a summary, sequential step sections, and verification failure instructions."""

    summary: GuideSummary
    sections: List[StepSection]
    verification_failure: Optional[VerificationFailureInstructions] = None


class VerificationCheck(Protocol):
    """Polymorphic service that validates session criteria."""

    def verify(self) -> Tuple[bool, VerificationDiagnostic]:
        """
        COVERED:
        - MUST communicate whether verification passed.
          - Consequent knowledge: return boolean pass indicator.
        - WHEN verification fails, MUST communicate diagnostic feedback.
          - Consequent knowledge: return False and diagnostic string.
        """
        _failure_diagnostic: VerificationDiagnostic = VerificationDiagnostic(
            "Criterion check failed"
        )
        _result: Tuple[bool, VerificationDiagnostic] = (
            True,
            VerificationDiagnostic(""),
        )
        raise NotImplementedError


@dataclass(frozen=True)
class PerNodeInfo:
    """Cached configuration and metadata for a single session node."""

    read_only_files: Set[agent_file_alias.ReadOnlyFile]
    read_write_files: Set[agent_file_alias.ReadWriteFile]
    templates: Mapping[agent_file_alias.BoundFile, agent_file_alias.FileContent]
    template_parameters: Mapping[TemplateParamKey, Any]
    allows_step_mode: bool
    guide_file: Optional[agent_file_alias.UnboundFile]
    guide: Optional[NodeGuide]
    blame_targets: Set[agent_file_alias.BoundFile]
    verification_checks: Sequence[VerificationCheck]
    src_file_alias: Optional[agent_file_alias.RelativePath]
    verification_success_message: Optional[VerificationSuccessMessage]
    feedback: Sequence[NodeFeedback]


class RoleConfig(InTier[AgentSessionTier], Protocol):
    """Provides the role, nodes, and version of the agent session."""

    @property
    def role(self) -> RoleName:
        """
        DEFERRED:
        - The role of the agent session.
        """
        raise NotImplementedError

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        """
        DEFERRED:
        - Sequence of nodes currently being cleaned in the agent session.
        """
        raise NotImplementedError

    @property
    def version(self) -> ExecutionVersion:
        """
        DEFERRED:
        - Execution version that increments whenever the cleaned nodes change.
        """
        raise NotImplementedError

    def set_role(self, role: RoleName) -> None:
        """
        DEFERRED:
        - MUST set the role of the session.
        """
        raise NotImplementedError

    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """
        DEFERRED:
        - MUST set the sequence of nodes currently being cleaned in the session.
        - MUST increment the execution version.
        """
        raise NotImplementedError


class NodeConfig(InTier[AgentSessionTier], Protocol):
    """Provides resolved configuration parameters for the active session."""

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """
        DEFERRED:
        - The session read-only files, restricting bound files to read.
        """
        raise NotImplementedError

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
        DEFERRED:
        - The session read-write files representing the nodes in the session.
        """
        raise NotImplementedError

    @property
    def allows_step_mode(self) -> bool:
        """
        DEFERRED:
        - Whether the node allows guide step mode.
        """
        raise NotImplementedError

    @property
    def is_step_mode(self) -> bool:
        """
        DEFERRED:
        - Whether session step mode is active.
        """
        raise NotImplementedError

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """
        DEFERRED:
        - Unbound file configured when guide step mode is active.
        """
        raise NotImplementedError

    @property
    def templates(
        self,
    ) -> Mapping[agent_file_alias.BoundFile, agent_file_alias.FileContent]:
        """
        DEFERRED:
        - Templates mapping read-write files to initial file content.
        """
        raise NotImplementedError

    @property
    def template_parameters(self) -> Mapping[TemplateParamKey, Any]:
        """
        DEFERRED:
        - Parameter bindings for template evaluation.
        """
        raise NotImplementedError

    @property
    def guide(self) -> Optional[NodeGuide]:
        """
        DEFERRED:
        - Structured instructional text for guide step mode.
        """
        raise NotImplementedError

    @property
    def blame_targets_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        """
        DEFERRED:
        - Bound files owned by upstream dependency nodes mapped by session node.
        """
        raise NotImplementedError

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        """
        DEFERRED:
        - Session verification checks evaluated during session advancement.
        """
        raise NotImplementedError

    @property
    def verification_checks_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Sequence[VerificationCheck]]:
        """
        DEFERRED:
        - Session verification checks mapped by session node.
        """
        raise NotImplementedError

    @property
    def src_file_alias_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, agent_file_alias.RelativePath]:
        """
        DEFERRED:
        - Relative path of the declared source file alias mapped by session node.
        """
        raise NotImplementedError

    @property
    def verification_success_message(self) -> Optional[VerificationSuccessMessage]:
        """
        DEFERRED:
        - Informative verification feedback when configured.
        """
        raise NotImplementedError

    @property
    def feedback(self) -> Sequence[NodeFeedback]:
        """
        DEFERRED:
        - Incoming feedback delivered to the node when present.
        """
        raise NotImplementedError

    @property
    def per_node_info_by_node(self) -> Mapping[dag_storage.DagNode, PerNodeInfo]:
        """
        DEFERRED:
        - Mapping each active node to its per node info.
        """
        raise NotImplementedError
