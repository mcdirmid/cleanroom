# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:59:26Z
# CHANGE: Drop the dead tier import and the generated scaffold markers from the node configuration interface
# CODE_HASH: ba825866b221
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, List, Mapping, NewType, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
from . import file_alias
import update_with_ai.parts.dag.lib.dag_storage as dag_storage

# Requirements specified in node_config.pyi

StepIndex = NewType('StepIndex', int)

StepTitle = NewType('StepTitle', str)

StepContent = NewType('StepContent', str)

GuideSummary = NewType('GuideSummary', str)

VerificationFailureInstructions = NewType('VerificationFailureInstructions', str)

VerificationDiagnostic = NewType('VerificationDiagnostic', str)

VerificationSuccessMessage = NewType('VerificationSuccessMessage', str)

NodeFeedback = NewType('NodeFeedback', str)

RoleName = NewType('RoleName', str)

ExecutionVersion = NewType('ExecutionVersion', int)

TemplateParamKey = NewType('TemplateParamKey', str)

@dataclass(frozen=True)
class StepSection:
    index: StepIndex
    title: StepTitle
    content: StepContent


@dataclass(frozen=True)
class NodeGuide:
    summary: GuideSummary
    sections: List[StepSection]
    verification_failure: Optional[VerificationFailureInstructions] = None


class VerificationCheck(Protocol):
    # Contract: MUST communicate whether verification passed, and diagnostic feedback describing failure.
    def verify(self) -> Tuple[bool, VerificationDiagnostic]:
        ...


@dataclass(frozen=True)
class PerNodeInfo:
    read_only_files: Set[file_alias.ReadOnlyFile]
    read_write_files: Set[file_alias.ReadWriteFile]
    templates: Mapping[file_alias.BoundFile, file_alias.FileContent]
    template_parameters: Mapping[TemplateParamKey, Any]
    allows_step_mode: bool
    guide_file: Optional[file_alias.UnboundFile]
    guide: Optional[NodeGuide]
    blame_targets: Set[file_alias.BoundFile]
    verification_checks: Sequence[VerificationCheck]
    src_file_alias: Optional[file_alias.RelativePath]
    verification_success_message: Optional[VerificationSuccessMessage]
    feedback: Sequence[NodeFeedback]


class RoleConfig(Protocol):
    # Contract: The role of the agent session.
    @property
    def role(self) -> RoleName:
        ...

    # Contract: Sequence of nodes currently being cleaned in the agent session.
    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        ...

    # Contract: Execution version that increments whenever the cleaned nodes change.
    @property
    def version(self) -> ExecutionVersion:
        ...

    # Contract: Configures the role of the agent session.
    def set_role(self, role: RoleName) -> None:
        ...

    # Contract: Configures nodes to clean and MUST increment execution version.
    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        ...


class NodeConfig(Protocol):
    # Contract: The session read-only files restricting bound files to read access.
    @property
    def read_only_files(self) -> Set[file_alias.ReadOnlyFile]:
        ...

    # Contract: The session read-write files permitting bound files for read and write access.
    @property
    def read_write_files(self) -> Set[file_alias.ReadWriteFile]:
        ...

    # Contract: Whether the node allows guide step mode.
    @property
    def allows_step_mode(self) -> bool:
        ...

    # Contract: Whether session step mode is active.
    @property
    def is_step_mode(self) -> bool:
        ...

    # Contract: Unbound file configured when guide step mode is active.
    @property
    def guide_file(self) -> Optional[file_alias.UnboundFile]:
        ...

    # Contract: Session templates mapping read-write files to initial file content.
    @property
    def templates(self) -> Mapping[file_alias.BoundFile, file_alias.FileContent]:
        ...

    # Contract: Session template parameters for template evaluation.
    @property
    def template_parameters(self) -> Mapping[TemplateParamKey, Any]:
        ...

    # Contract: The session guide provided when step mode is active.
    @property
    def guide(self) -> Optional[NodeGuide]:
        ...

    # Contract: Session blame targets per session node, mapping read-write files to the read-only bound files eligible for blame.
    @property
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[file_alias.BoundFile]]:
        ...

    # Contract: Session verification checks evaluated during verification.
    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        ...

    # Contract: Session verification checks mapped by session node.
    @property
    def verification_checks_by_node(self) -> Mapping[dag_storage.DagNode, Sequence[VerificationCheck]]:
        ...

    # Contract: Relative path of the declared source file alias mapped by session node.
    @property
    def src_file_alias_by_node(self) -> Mapping[dag_storage.DagNode, file_alias.RelativePath]:
        ...

    # Contract: The session verification success message when configured.
    @property
    def verification_success_message(self) -> Optional[VerificationSuccessMessage]:
        ...

    # Contract: Incoming session messages explaining why a read-write file requires cleaning.
    @property
    def feedback(self) -> Sequence[NodeFeedback]:
        ...

    # Contract: Mapping each active node to its per node info.
    @property
    def per_node_info_by_node(self) -> Mapping[dag_storage.DagNode, PerNodeInfo]:
        ...
