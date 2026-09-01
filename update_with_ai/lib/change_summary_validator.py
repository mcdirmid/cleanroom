"""Change summary validator interface and diff summaries."""

from typing import Protocol, TypeAlias, Sequence, Optional
from dataclasses import dataclass
from .virtual_file_name import VirtualFileName

ChangeSummary: TypeAlias = str
DiffSummary: TypeAlias = str
FileContent: TypeAlias = str
ValidationFeedback: TypeAlias = str


@dataclass(frozen=True)
class NetChange:
    file_name: VirtualFileName
    initial_content: FileContent
    current_content: FileContent


class ChangeValidator(Protocol):
    def validate_change_summary(
        self, summary: ChangeSummary, net_changes: Sequence[NetChange]
    ) -> Optional[ValidationFeedback]:
        ...

    def compute_diff_summary(
        self, net_changes: Sequence[NetChange]
    ) -> DiffSummary:
        ...
