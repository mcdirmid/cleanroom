# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T18:41:10Z
# CHANGE: Set default value of verification_failure to None instead of ellipsis
# CODE_HASH: ae4901f3e1cf
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Any, List, Mapping, NewType, Optional, Protocol, Sequence, Set, Tuple
from dataclasses import dataclass
from .agent_session import AgentSessionTier
from . import agent_file_alias
import update_with_ai.parts.dag.lib.dag_storage as dag_storage

# Requirements specified in agent_node_config.pyi

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
    # TODO_StepSection_body
    index: StepIndex
    title: StepTitle
    content: StepContent


@dataclass(frozen=True)
class NodeGuide:
    # TODO_NodeGuide_body
    summary: GuideSummary
    sections: List[StepSection]
    verification_failure: Optional[VerificationFailureInstructions] = None


class VerificationCheck(Protocol):
    def verify(self) -> Tuple[bool, VerificationDiagnostic]:
        # TODO_verify_body
        ...


@dataclass(frozen=True)
class PerNodeInfo:
    # TODO_PerNodeInfo_body
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


class RoleConfig(Protocol):
    @property
    def role(self) -> RoleName:
        # TODO_role_body
        ...

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        # TODO_nodes_body
        ...

    @property
    def version(self) -> ExecutionVersion:
        # TODO_version_body
        ...

    def set_role(self, role: RoleName) -> None:
        # TODO_set_role_body
        ...

    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        # TODO_set_nodes_body
        ...


class NodeConfig(Protocol):
    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        # TODO_read_only_files_body
        ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        # TODO_read_write_files_body
        ...

    @property
    def allows_step_mode(self) -> bool:
        # TODO_allows_step_mode_body
        ...

    @property
    def is_step_mode(self) -> bool:
        # TODO_is_step_mode_body
        ...

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        # TODO_guide_file_body
        ...

    @property
    def templates(self) -> Mapping[agent_file_alias.BoundFile, agent_file_alias.FileContent]:
        # TODO_templates_body
        ...

    @property
    def template_parameters(self) -> Mapping[TemplateParamKey, Any]:
        # TODO_template_parameters_body
        ...

    @property
    def guide(self) -> Optional[NodeGuide]:
        # TODO_guide_body
        ...

    @property
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        # TODO_blame_targets_by_node_body
        ...

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        # TODO_verification_checks_body
        ...

    @property
    def verification_checks_by_node(self) -> Mapping[dag_storage.DagNode, Sequence[VerificationCheck]]:
        # TODO_verification_checks_by_node_body
        ...

    @property
    def src_file_alias_by_node(self) -> Mapping[dag_storage.DagNode, agent_file_alias.RelativePath]:
        # TODO_src_file_alias_by_node_body
        ...

    @property
    def verification_success_message(self) -> Optional[VerificationSuccessMessage]:
        # TODO_verification_success_message_body
        ...

    @property
    def feedback(self) -> Sequence[NodeFeedback]:
        # TODO_feedback_body
        ...

    @property
    def per_node_info_by_node(self) -> Mapping[dag_storage.DagNode, PerNodeInfo]:
        # TODO_per_node_info_by_node_body
        ...
