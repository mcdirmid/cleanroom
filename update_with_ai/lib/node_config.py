"""Node configuration interface and types."""

from typing import Optional, Protocol, Set, Tuple
from . import file_alias, sandbox_guide_delivery


class NodeConfig(Protocol):
    @property
    def read_only_files(self) -> Set[file_alias.BoundFile]: ...

    @property
    def read_write_files(self) -> Set[file_alias.BoundFile]: ...

    @property
    def guide_file(self) -> Optional[file_alias.UnboundFile]: ...

    @property
    def templates(self) -> Set[Tuple[file_alias.BoundFile, file_alias.FileContent]]: ...

    @property
    def guide(self) -> Optional[sandbox_guide_delivery.Guide]: ...

    @property
    def blame_targets(self) -> Set[file_alias.BoundFile]: ...
