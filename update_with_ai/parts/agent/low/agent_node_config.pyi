# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 002081f1371d
# --- END CLEANROOM METADATA ---

"""Agent node config low-level interface specification."""

from dataclasses import dataclass
from typing import Any, List, Mapping, NewType, Optional, Protocol, Sequence, Set, Tuple
from framework import data_type, operation, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import dag_storage

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
@data_type
class StepSection:
    """Discrete milestone section within a guide.

    Args:
        index: The sequential index of the step section.
        title: The heading or title of the step section.
        content: The instructional content of the step section.
    """
    index: StepIndex
    title: StepTitle
    content: StepContent


@dataclass(frozen=True)
@data_type
class NodeGuide:
    """Structured instructional text containing a summary, sequential step sections, and verification failure instructions.

    Args:
        summary: The high-level overview of the guide.
        sections: The sequential milestone sections of the guide.
        verification_failure: Instructions delivered when verification fails.
    """
    summary: GuideSummary
    sections: List[StepSection]
    verification_failure: Optional[VerificationFailureInstructions] = ...


@poly_type
class VerificationCheck(Protocol):
    """Polymorphic service that validates session criteria."""

    @operation
    def verify(self) -> Tuple[bool, VerificationDiagnostic]:
        """Validates session criteria, returning whether verification passed and diagnostic feedback.

        Returns:
            A tuple of boolean pass status and diagnostic feedback string.

        POSTCONDITIONS:
        - MUST communicate whether verification passed.
        - WHEN verification fails, MUST communicate diagnostic feedback.
        """
        ...


@dataclass(frozen=True)
@data_type
class PerNodeInfo:
    """Cached configuration and metadata for a single session node.

    Args:
        read_only_files: Session read-only files.
        read_write_files: Session read-write files.
        templates: Boilerplate templates.
        template_parameters: Parameter bindings for template evaluation.
        allows_step_mode: Whether step mode is allowed.
        guide_file: Unbound guide file.
        guide: Structured node guide.
        blame_targets: Upstream blame target files.
        verification_checks: Verification checks.
        src_file_alias: Declared source file alias path.
        verification_success_message: Verification success message.
        feedback: Incoming node feedback.
    """
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


@singleton_type("agent_session")
class RoleConfig(InTier[AgentSessionTier], Protocol):
    """Provides the role, nodes, and version of the agent session."""

    @property
    def role(self) -> RoleName:
        """The role of the agent session."""
        ...

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        """Sequence of nodes currently being cleaned in the agent session."""
        ...

    @property
    def version(self) -> ExecutionVersion:
        """Execution version that increments whenever the cleaned nodes change."""
        ...

    @operation
    def set_role(self, role: RoleName) -> None:
        """Configures the role of the agent session.

        Args:
            role: The role of the agent session.

        POSTCONDITIONS:
        - MUST set the role of the session.
        """
        ...

    @operation
    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """Configures the sequence of nodes currently being cleaned and increments the execution version.

        Args:
            nodes: The sequence of nodes to clean.

        POSTCONDITIONS:
        - MUST set the sequence of nodes currently being cleaned in the session.
        - MUST increment the execution version.
        """
        ...


@singleton_type("agent_session")
class NodeConfig(InTier[AgentSessionTier], Protocol):
    """Provides resolved configuration parameters for the active session."""

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """The session read-only files, restricting bound files to read."""
        ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """The session read-write files representing the nodes in the session, permitting bound files for read and write."""
        ...

    @property
    def allows_step_mode(self) -> bool:
        """Whether the node allows guide step mode."""
        ...

    @property
    def is_step_mode(self) -> bool:
        """Whether session step mode is active."""
        ...

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """Unbound file configured when guide step mode is active."""
        ...

    @property
    def templates(self) -> Mapping[agent_file_alias.BoundFile, agent_file_alias.FileContent]:
        """Templates mapping read-write files to initial file content."""
        ...

    @property
    def template_parameters(self) -> Mapping[TemplateParamKey, Any]:
        """Parameter bindings for template evaluation."""
        ...

    @property
    def guide(self) -> Optional[NodeGuide]:
        """Structured instructional text for guide step mode."""
        ...

    @property
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        """Bound files owned by upstream dependency nodes mapped by session node."""
        ...

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        """Session verification checks evaluated during session advancement."""
        ...

    @property
    def verification_checks_by_node(self) -> Mapping[dag_storage.DagNode, Sequence[VerificationCheck]]:
        """Session verification checks mapped by session node."""
        ...

    @property
    def src_file_alias_by_node(self) -> Mapping[dag_storage.DagNode, agent_file_alias.RelativePath]:
        """Relative path of the declared source file alias mapped by session node."""
        ...

    @property
    def verification_success_message(self) -> Optional[VerificationSuccessMessage]:
        """Informative verification feedback when configured."""
        ...

    @property
    def feedback(self) -> Sequence[NodeFeedback]:
        """Incoming feedback delivered to the node when present."""
        ...

    @property
    def per_node_info_by_node(self) -> Mapping[dag_storage.DagNode, PerNodeInfo]:
        """Mapping each active node to its per node info."""
        ...
