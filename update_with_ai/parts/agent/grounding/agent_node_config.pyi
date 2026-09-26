from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from framework import data_type, operation, poly_type, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import dag_storage


@dataclass(frozen=True)
@data_type
class StepSection:
    """Discrete milestone section within a guide.

    Args:
        index: The sequential index of the step section.
        title: The heading or title of the step section.
        content: The instructional content of the step section.
    """
    index: int
    title: str
    content: str


@dataclass(frozen=True)
@data_type
class NodeGuide:
    """Structured instructional text containing a summary, sequential step sections, and verification failure instructions.

    Args:
        summary: The high-level overview of the guide.
        sections: The sequential milestone sections of the guide.
        verification_failure: Instructions delivered when verification fails.
    """
    summary: str
    sections: List[StepSection]
    verification_failure: Optional[str] = ...

@poly_type
class VerificationCheck(Protocol):
    """Polymorphic service that validates session criteria."""

    @operation
    def verify(self) -> Tuple[bool, str]:
        """Validates session criteria, returning whether verification passed and diagnostic feedback.

        Returns:
            A tuple of boolean pass status and diagnostic feedback string.
        """
        ...


@dataclass(frozen=True)
@data_type
class PerNodeInfo:
    """Cached configuration and metadata for a single session node."""
    read_only_files: Set[agent_file_alias.ReadOnlyFile]
    read_write_files: Set[agent_file_alias.ReadWriteFile]
    templates: Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]]
    template_parameters: Mapping[str, Any]
    allows_step_mode: bool
    guide_file: Optional[agent_file_alias.UnboundFile]
    guide: Optional[NodeGuide]
    blame_targets: Set[agent_file_alias.BoundFile]
    verification_checks: Sequence[VerificationCheck]
    src_file_alias: Optional[str]
    verification_success_message: Optional[str]
    feedback: Sequence[str]


@singleton_type("agent_session")
class RoleConfig(InTier[AgentSessionTier], Protocol):
    """Provides the role, nodes, and version of the agent session."""

    @property
    def role(self) -> str:
        """The role of the agent session.

        GROUNDING_PROVISIONS:
        - knows("session_role", str): Exposes the agent session role.
        """
        ...

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        """Sequence of nodes currently being cleaned in the agent session.

        GROUNDING_PROVISIONS:
        - knows("cleaned_nodes", Sequence[dag_storage.DagNode]): Exposes the sequence of nodes being cleaned.
        """
        ...

    @property
    def version(self) -> int:
        """Execution version that increments whenever the cleaned nodes change.

        GROUNDING_PROVISIONS:
        - knows("execution_version", int): Exposes the execution version.
        """
        ...

    @operation
    def set_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """Configures the sequence of nodes currently being cleaned and increments the execution version.

        Args:
            nodes: The sequence of nodes to clean.

        REQUIREMENTS:
        - The role config can set nodes to configure the nodes currently being cleaned in the agent session and increment the execution version.

        GROUNDING_PROVISIONS:
        - action("set_nodes", Sequence[dag_storage.DagNode]): Configures cleaned nodes and increments version.
        """
        ...


@singleton_type("agent_session")
class NodeConfig(InTier[AgentSessionTier], Protocol):
    """Provides resolved configuration parameters for the active session."""

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """The session read-only files, restricting bound files to read.

        REQUIREMENTS:
        - The node config provides the session read-only files restricted to inspection.

        GROUNDING_PROVISIONS:
        - knows("read_only_files", Set[agent_file_alias.ReadOnlyFile]): Exposes read-only files.
        """
        ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """The session read-write files representing the nodes in the session, permitting bound files for read and write.

        REQUIREMENTS:
        - The node config provides the session read-write files permitted for inspection and modification.

        GROUNDING_PROVISIONS:
        - knows("read_write_files", Set[agent_file_alias.ReadWriteFile]): Exposes read-write files.
        """
        ...

    @property
    def allows_step_mode(self) -> bool:
        """Whether the node allows guide step mode.

        REQUIREMENTS:
        - The node config indicates whether the node allows step mode.

        GROUNDING_PROVISIONS:
        - knows("allows_step_mode", bool): Exposes whether step mode is allowed.
        """
        ...

    @property
    def is_step_mode(self) -> bool:
        """Whether session step mode is active.

        REQUIREMENTS:
        - The node config indicates whether session step mode is active.

        GROUNDING_PROVISIONS:
        - knows("is_step_mode", bool): Exposes whether step mode is active.
        """
        ...

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """Unbound file configured when guide step mode is active.

        REQUIREMENTS:
        - The node config provides the session guide file when step mode is active.

        GROUNDING_PROVISIONS:
        - knows("guide_file", Optional[agent_file_alias.UnboundFile]): Exposes guide file.
        """
        ...

    @property
    def templates(self) -> Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]]:
        """Templates mapping read-write files to initial file content.

        REQUIREMENTS:
        - The node config provides templates mapping read-write files to initial file content.

        GROUNDING_PROVISIONS:
        - knows("templates", Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]]): Exposes session templates.
        """
        ...

    @property
    def template_parameters(self) -> Mapping[str, Any]:
        """Parameter bindings for template evaluation.

        REQUIREMENTS:
        - The node config provides the session template parameters, providing parameter bindings for template evaluation.

        GROUNDING_PROVISIONS:
        - knows("template_parameters", Mapping[str, Any]): Exposes template parameters.
        """
        ...

    @property
    def guide(self) -> Optional[NodeGuide]:
        """Structured instructional text for guide step mode.

        REQUIREMENTS:
        - The node config provides the session guide, providing structured instructional text when step mode is active.

        GROUNDING_PROVISIONS:
        - knows("guide", Optional[NodeGuide]): Exposes task guide.
        """
        ...


    @property
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        """Bound files owned by upstream dependency nodes mapped by session node.

        REQUIREMENTS:
        - The node config provides the session blame targets mapped by session node.

        GROUNDING_PROVISIONS:
        - knows("blame_targets_by_node", Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]): Exposes blame targets by node.
        """
        ...

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        """Session verification checks evaluated during session advancement.

        REQUIREMENTS:
        - The node config provides the session verification checks evaluated during session advancement.

        GROUNDING_PROVISIONS:
        - knows("verification_checks", Sequence[VerificationCheck]): Exposes verification checks.
        """
        ...

    @property
    def verification_checks_by_node(self) -> Mapping[dag_storage.DagNode, Sequence[VerificationCheck]]:
        """Session verification checks mapped by session node.

        REQUIREMENTS:
        - The node config provides the session verification checks mapped by session node.

        GROUNDING_PROVISIONS:
        - knows("verification_checks_by_node", Mapping[dag_storage.DagNode, Sequence[VerificationCheck]]): Exposes verification checks by node.
        """
        ...

    @property
    def src_file_alias_by_node(self) -> Mapping[dag_storage.DagNode, str]:
        """Relative path of the declared source file alias mapped by session node.

        REQUIREMENTS:
        - The node config provides the source file alias relative path mapped by session node.

        GROUNDING_PROVISIONS:
        - knows("src_file_alias_by_node", Mapping[dag_storage.DagNode, str]): Exposes source file aliases by node.
        """
        ...

    @property
    def verification_success_message(self) -> Optional[str]:
        """Informative verification feedback when configured.

        REQUIREMENTS:
        - The node config provides the session verification success message when configured.

        GROUNDING_PROVISIONS:
        - knows("verification_success_message", Optional[str]): Exposes verification success feedback.
        """
        ...

    @property
    def feedback(self) -> Sequence[str]:
        """Incoming feedback delivered to the node when present.

        REQUIREMENTS:
        - The node config provides the session feedback, exposing incoming feedback delivered to the node when present.

        GROUNDING_PROVISIONS:
        - knows("feedback", Sequence[str]): Exposes incoming feedback.
        """
        ...

    @property
    def per_node_info_by_node(self) -> Mapping[dag_storage.DagNode, PerNodeInfo]:
        """Mapping each active node to its per node info.

        REQUIREMENTS:
        - The node config provides the session per node info by node, mapping each active node to its per node info.

        GROUNDING_PROVISIONS:
        - knows("per_node_info_by_node", Mapping[dag_storage.DagNode, PerNodeInfo]): Exposes per-node info.
        """
        ...
