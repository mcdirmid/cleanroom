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

    def set_role(self, role: RoleName) -> None:
        ...

    # Contract: Configures nodes to clean and MUST increment execution version.
    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        ...


class NodeConfig(Protocol):
    @property
    def read_only_files(self) -> Set[file_alias.ReadOnlyFile]:
        ...

    @property
    def read_write_files(self) -> Set[file_alias.ReadWriteFile]:
        ...

    @property
    def allows_step_mode(self) -> bool:
        ...

    @property
    def is_step_mode(self) -> bool:
        ...

    @property
    def guide_file(self) -> Optional[file_alias.UnboundFile]:
        ...

    @property
    def templates(self) -> Mapping[file_alias.BoundFile, file_alias.FileContent]:
        ...

    @property
    def template_parameters(self) -> Mapping[TemplateParamKey, Any]:
        ...

    @property
    def guide(self) -> Optional[NodeGuide]:
        ...

    @property
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[file_alias.BoundFile]]:
        ...

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        ...

    @property
    def verification_checks_by_node(self) -> Mapping[dag_storage.DagNode, Sequence[VerificationCheck]]:
        ...

    @property
    def src_file_alias_by_node(self) -> Mapping[dag_storage.DagNode, file_alias.RelativePath]:
        ...

    @property
    def verification_success_message(self) -> Optional[VerificationSuccessMessage]:
        ...

    @property
    def feedback(self) -> Sequence[NodeFeedback]:
        ...

    @property
    def per_node_info_by_node(self) -> Mapping[dag_storage.DagNode, PerNodeInfo]:
        ...
