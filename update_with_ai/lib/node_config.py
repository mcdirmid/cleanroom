"""Node configuration interface and types."""

from typing import Any, Mapping, Optional, Protocol, Sequence, Set, Tuple
from . import file_alias, sandbox_guide_delivery, sandbox_run_control


class NodeConfig(Protocol):
    @property
    def read_only_files(self) -> Set[file_alias.BoundFile]: ...

    @property
    def read_write_files(self) -> Set[file_alias.BoundFile]: ...

    @property
    def allows_step_mode(self) -> bool: ...

    @property
    def is_step_mode(self) -> bool: ...

    @property
    def guide_file(self) -> Optional[file_alias.UnboundFile]: ...

    @property
    def templates(self) -> Set[Tuple[file_alias.BoundFile, file_alias.FileContent]]: ...

    @property
    def template_parameters(self) -> Mapping[str, Any]: ...

    @property
    def guide(self) -> Optional[sandbox_guide_delivery.Guide]: ...

    @property
    def blame_targets(self) -> Set[file_alias.BoundFile]: ...

    @property
    def verification_checks(self) -> Sequence[sandbox_run_control.VerificationCheck]: ...

    @property
    def verification_success_message(self) -> Optional[str]: ...

    @property
    def feedback(self) -> Sequence[str]: ...
