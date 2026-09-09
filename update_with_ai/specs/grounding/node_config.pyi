from typing import Optional, Protocol, Set, Tuple
from framework import singleton_type
import file_alias
import sandbox_guide_delivery

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
- The node config provides the session's read-only files restricted to inspection.
"""
        ...

    @property
    def read_write_files(self) -> Set[file_alias.BoundFile]:
        """
PURPOSE:
Bound files permitted for inspection and modification

FRESH_REQUIREMENTS:
- The node config provides the session's read-write files permitted for inspection and modification.
"""
        ...

    @property
    def guide_file(self) -> Optional[file_alias.UnboundFile]:
        """
PURPOSE:
Unbound file configured when progressive guidance is active

FRESH_REQUIREMENTS:
- The node config provides the session's guide file when progressive guidance is active, or absent if no guide file is configured.
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
    def guide(self) -> Optional[sandbox_guide_delivery.Guide]:
        """
PURPOSE:
Structured instructional text for progressive guidance

FRESH_REQUIREMENTS:
- The node config provides the session's guide for progressive guidance, or absent if no guide is configured.
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
