from typing import Any, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from framework import data_type, operation, poly_type, singleton_type
from dataclasses import dataclass
import agent_file_alias
import agent_config
import dag_storage

@dataclass(frozen=True)
@data_type
class StepSection:
    """
PURPOSE:
Discrete milestone section within a guide
"""

    def __init__(self, index: int, title: str, content: str) -> None:
        ...

    @property
    def index(self) -> int:
        """
PURPOSE:
Established as the sequential index of the step section
"""
        ...

    @property
    def title(self) -> str:
        """
PURPOSE:
Established as the heading or title of the step section
"""
        ...

    @property
    def content(self) -> str:
        """
PURPOSE:
Established as the instructional content of the step section
"""
        ...

@dataclass(frozen=True)
@data_type
class Guide:
    """
PURPOSE:
Structured instructional text containing a summary, sequential step sections, and verification failure instructions
"""

    def __init__(self, summary: str, sections: List[StepSection], verification_failure: Optional[str]=None) -> None:
        ...

    @property
    def summary(self) -> str:
        """
PURPOSE:
Established as the high-level overview of the guide
"""
        ...

    @property
    def sections(self) -> List[StepSection]:
        """
PURPOSE:
Established as the sequential milestone sections of the guide
"""
        ...

    @property
    def verification_failure(self) -> Optional[str]:
        """
PURPOSE:
Established as instructions delivered when verification fails
"""
        ...

@poly_type
class VerificationCheck(Protocol):
    """
PURPOSE:
Polymorphic service that validates session criteria
"""

    @operation
    def verify(self) -> Tuple[bool, str]:
        """
PURPOSE:
Validates session criteria, returning whether verification passed and diagnostic feedback
"""
        ...

@dataclass(frozen=True)
@data_type
class PerNodeInfo:
    """
PURPOSE:
Data describing configuration parameters for a node
"""

    def __init__(self, node: dag_storage.Node, read_only_files: Set[agent_file_alias.ReadOnlyFile], read_write_files: Set[agent_file_alias.ReadWriteFile], templates: Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]], template_parameters: Mapping[str, Any], allows_step_mode: bool, guide_file: Optional[agent_file_alias.UnboundFile], guide: Optional[Guide], blame_targets: Set[agent_file_alias.BoundFile], verification_checks: Sequence[VerificationCheck], src_file_alias: Optional[str], verification_success_message: Optional[str], feedback: Sequence[str]) -> None:
        ...

    @property
    def node(self) -> dag_storage.Node:
        """
PURPOSE:
Target node for the configuration parameters
"""
        ...

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """
PURPOSE:
Bound files restricted to inspection for the node
"""
        ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
PURPOSE:
Bound files permitted for inspection and modification for the node
"""
        ...

    @property
    def templates(self) -> Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]]:
        """
PURPOSE:
Mapping read-write files to initial file content for the node
"""
        ...

    @property
    def template_parameters(self) -> Mapping[str, Any]:
        """
PURPOSE:
Parameter bindings for template evaluation for the node
"""
        ...

    @property
    def allows_step_mode(self) -> bool:
        """
PURPOSE:
Whether the node allows guide step mode
"""
        ...

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """
PURPOSE:
Unbound guide file configured for the node
"""
        ...

    @property
    def guide(self) -> Optional[Guide]:
        """
PURPOSE:
Structured instructional text configured for the node
"""
        ...

    @property
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]:
        """
PURPOSE:
Bound files owned by upstream dependency nodes eligible for defect attribution for the node
"""
        ...

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        """
PURPOSE:
Verification checks evaluated for the node
"""
        ...

    @property
    def src_file_alias(self) -> Optional[str]:
        """
PURPOSE:
Relative path of the declared source file alias for the node
"""
        ...

    @property
    def verification_success_message(self) -> Optional[str]:
        """
PURPOSE:
Informative verification feedback configured for the node
"""
        ...

    @property
    def feedback(self) -> Sequence[str]:
        """
PURPOSE:
Incoming feedback delivered to the node
"""
        ...

@singleton_type('agent_session')
class RoleConfig(Protocol):
    """
PURPOSE:
Defined as an agent session service that provides the role, nodes, and version of the agent session
"""

    @property
    def role(self) -> str:
        """
PURPOSE:
Role of the agent session

FRESH_REQUIREMENTS:
- The role config provides the role of the session.
"""
        ...

    @property
    def nodes(self) -> Sequence[dag_storage.Node]:
        """
PURPOSE:
Sequence of nodes currently being cleaned in the agent session

FRESH_REQUIREMENTS:
- The role config provides the sequence of nodes currently being cleaned in the agent session.
"""
        ...

    @property
    def version(self) -> int:
        """
PURPOSE:
Execution version that increments whenever the cleaned nodes change

FRESH_REQUIREMENTS:
- The role config provides an execution version that increments whenever the cleaned nodes change.
"""
        ...

    @operation
    def set_nodes(self, nodes: Sequence[dag_storage.Node]) -> None:
        """
PURPOSE:
Configures the sequence of nodes currently being cleaned and increments the execution version

FRESH_REQUIREMENTS:
- The role config can set nodes to configure the nodes currently being cleaned in the agent session and increment the execution version.
"""
        ...

@singleton_type('agent_session')
class NodeConfig(Protocol):
    """
PURPOSE:
Defined as an agent session service exposing configuration parameters for the session environment
"""

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """
PURPOSE:
Bound files restricted to inspection

FRESH_REQUIREMENTS:
- The node config provides the session read-only files restricted to inspection.
"""
        ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        """
PURPOSE:
Bound files permitted for inspection and modification

FRESH_REQUIREMENTS:
- The node config provides the session read-write files permitted for inspection and modification.
"""
        ...

    @property
    def allows_step_mode(self) -> bool:
        """
PURPOSE:
Whether the node allows guide step mode

FRESH_REQUIREMENTS:
- The node config indicates whether the node allows step mode.
"""
        ...

    @property
    def is_step_mode(self) -> bool:
        """
PURPOSE:
Whether session step mode is active, enabled when agent config enables step mode, the session contains exactly one node, the node allows step mode, and session feedback is absent

FRESH_REQUIREMENTS:
- The node config indicates whether session step mode is active.
"""
        ...

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        """
PURPOSE:
Unbound file configured when guide step mode is active

FRESH_REQUIREMENTS:
- The node config provides the session guide file when step mode is active.
"""
        ...

    @property
    def templates(self) -> Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]]:
        """
PURPOSE:
Mapping read-write files to initial file content

FRESH_REQUIREMENTS:
- The node config provides templates mapping read-write files to initial file content.
"""
        ...

    @property
    def template_parameters(self) -> Mapping[str, Any]:
        """
PURPOSE:
Parameter bindings for template evaluation

FRESH_REQUIREMENTS:
- The node config provides the session template parameters, providing parameter bindings for template evaluation.
"""
        ...

    @property
    def guide(self) -> Optional[Guide]:
        """
PURPOSE:
Structured instructional text for guide step mode

FRESH_REQUIREMENTS:
- The node config provides the session guide, providing structured instructional text when step mode is active.
"""
        ...

    @property
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]:
        """
PURPOSE:
Bound files owned by upstream dependency nodes eligible for defect attribution

FRESH_REQUIREMENTS:
- The node config provides blame targets eligible for defect attribution.
"""
        ...

    @property
    def blame_targets_by_node(self) -> Mapping[dag_storage.Node, Set[agent_file_alias.BoundFile]]:
        """
PURPOSE:
Bound files owned by upstream dependency nodes eligible for defect attribution mapped by session node

FRESH_REQUIREMENTS:
- The node config provides the session blame targets mapped by session node.
"""
        ...

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        """
PURPOSE:
Session verification checks evaluated during session advancement

FRESH_REQUIREMENTS:
- The node config provides the session verification checks evaluated during session advancement.
"""
        ...

    @property
    def verification_checks_by_node(self) -> Mapping[dag_storage.Node, Sequence[VerificationCheck]]:
        """
PURPOSE:
Session verification checks mapped by session node

FRESH_REQUIREMENTS:
- The node config provides the session verification checks mapped by session node.
"""
        ...

    @property
    def src_file_alias_by_node(self) -> Mapping[dag_storage.Node, str]:
        """
PURPOSE:
Relative path of the declared source file alias mapped by session node

FRESH_REQUIREMENTS:
- The node config provides the source file alias relative path mapped by session node.
"""
        ...

    @property
    def verification_success_message(self) -> Optional[str]:
        """
PURPOSE:
Informative verification feedback when configured

FRESH_REQUIREMENTS:
- The node config provides the session verification success message when configured.
"""
        ...

    @property
    def feedback(self) -> Sequence[str]:
        """
PURPOSE:
Incoming feedback delivered to the node when present

FRESH_REQUIREMENTS:
- The node config provides the session feedback, exposing incoming feedback delivered to the node when present.
"""
        ...

    @property
    def per_node_info_by_node(self) -> Mapping[dag_storage.Node, PerNodeInfo]:
        """
PURPOSE:
Mapping each active node to its per node info

FRESH_REQUIREMENTS:
- The node config provides the session per node info by node, mapping each active node to its per node info.
"""
        ...
