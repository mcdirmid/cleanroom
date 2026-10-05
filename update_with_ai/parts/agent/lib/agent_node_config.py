# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 1417bb1adc32
# --- END CLEANROOM METADATA ---

# Requirements specified in agent_node_config.pyi
from dataclasses import dataclass
from typing import Any, List, Mapping, NewType, Optional, Protocol, Sequence, Set, Tuple
from update_with_ai.parts.dag.lib import dag_storage
from . import agent_file_alias

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
    index: StepIndex
    title: StepTitle
    content: StepContent


@dataclass(frozen=True)
class NodeGuide:
    summary: GuideSummary
    sections: List[StepSection]
    verification_failure: Optional[VerificationFailureInstructions] = None


class VerificationCheck(Protocol):
    def verify(self) -> Tuple[bool, VerificationDiagnostic]: ...


@dataclass(frozen=True)
class PerNodeInfo:
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
    def role(self) -> RoleName: ...

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]: ...

    @property
    def version(self) -> ExecutionVersion: ...

    def set_role(self, role: RoleName) -> None: ...

    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None: ...


class NodeConfig(Protocol):
    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]: ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]: ...

    @property
    def allows_step_mode(self) -> bool: ...

    @property
    def is_step_mode(self) -> bool: ...

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]: ...

    @property
    def templates(
        self,
    ) -> Mapping[agent_file_alias.BoundFile, agent_file_alias.FileContent]: ...

    @property
    def template_parameters(self) -> Mapping[TemplateParamKey, Any]: ...

    @property
    def guide(self) -> Optional[NodeGuide]: ...

    @property
    def blame_targets_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]: ...

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]: ...

    @property
    def verification_checks_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Sequence[VerificationCheck]]: ...

    @property
    def src_file_alias_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, agent_file_alias.RelativePath]: ...

    @property
    def verification_success_message(
        self,
    ) -> Optional[VerificationSuccessMessage]: ...

    @property
    def feedback(self) -> Sequence[NodeFeedback]: ...

    @property
    def per_node_info_by_node(self) -> Mapping[dag_storage.DagNode, PerNodeInfo]: ...
