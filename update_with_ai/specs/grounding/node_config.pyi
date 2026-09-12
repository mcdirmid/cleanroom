from typing import Any, Mapping, Optional, Protocol, Sequence, Set, Tuple
from framework import singleton_type
import file_alias
import model_config
import sandbox_guide_delivery
import sandbox_run_control

@singleton_type('agent_session')
class NodeConfig(Protocol):
    """
PURPOSE:
Defined as an agent session service exposing configuration parameters for the session environment
"""

    @property
    def read_only_files(self) -> Set[file_alias.BoundFile]:
        """
PURPOSE:
Bound files restricted to inspection

FRESH_REQUIREMENTS:
- The node config provides the session read-only files restricted to inspection.
"""
        ...

    @property
    def read_write_files(self) -> Set[file_alias.BoundFile]:
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
Whether session step mode is active, enabled when model config enables step mode, the node allows step mode, and session feedback is absent

FRESH_REQUIREMENTS:
- The node config indicates whether session step mode is active.
"""
        ...

    @property
    def guide_file(self) -> Optional[file_alias.UnboundFile]:
        """
PURPOSE:
Unbound file configured when guide step mode is active

FRESH_REQUIREMENTS:
- The node config provides the session guide file when step mode is active.
"""
        ...

    @property
    def templates(self) -> Set[Tuple[file_alias.BoundFile, file_alias.FileContent]]:
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
    def guide(self) -> Optional[sandbox_guide_delivery.Guide]:
        """
PURPOSE:
Structured instructional text for guide step mode

FRESH_REQUIREMENTS:
- The node config provides the session guide, providing structured instructional text when step mode is active.
"""
        ...

    @property
    def blame_targets(self) -> Set[file_alias.BoundFile]:
        """
PURPOSE:
Bound files owned by upstream dependency nodes eligible for defect attribution

FRESH_REQUIREMENTS:
- The node config provides blame targets eligible for defect attribution.
"""
        ...

    @property
    def verification_checks(self) -> Sequence[sandbox_run_control.VerificationCheck]:
        """
PURPOSE:
Session verification checks evaluated during session advancement

FRESH_REQUIREMENTS:
- The node config provides the session verification checks evaluated during session advancement.
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
