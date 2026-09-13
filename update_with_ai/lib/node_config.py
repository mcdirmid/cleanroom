"""Node configuration interface and types."""

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Protocol, Sequence, Set, Tuple
from . import file_alias


@dataclass(frozen=True)
class StepSection:
    index: int
    title: str
    content: str


@dataclass(frozen=True)
class Guide:
    summary: str
    sections: List[StepSection]
    verification_failure: Optional[str] = None


class VerificationCheck(Protocol):
    def verify(self) -> Tuple[bool, str]: ...


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
    def guide(self) -> Optional[Guide]: ...

    @property
    def blame_targets(self) -> Set[file_alias.BoundFile]: ...

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]: ...

    @property
    def verification_success_message(self) -> Optional[str]: ...

    @property
    def feedback(self) -> Sequence[str]: ...
