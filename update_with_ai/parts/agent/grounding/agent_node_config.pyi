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

@singleton_type('agent_session')
class NodeConfig(Protocol):
    """
PURPOSE:
Defined as an agent session service exposing configuration parameters for the session environment
"""

    @property
    def read_only_files(self) -> Set[agent_file_alias.BoundFile]:
        """
PURPOSE:
Bound files restricted to inspection

FRESH_REQUIREMENTS:
- The node config provides the session read-only files restricted to inspection.
"""
        ...

    @property
    def read_write_files(self) -> Set[agent_file_alias.BoundFile]:
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
Short name of the declared source file alias mapped by session node

FRESH_REQUIREMENTS:
- The node config provides the source file alias short name mapped by session node.
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
