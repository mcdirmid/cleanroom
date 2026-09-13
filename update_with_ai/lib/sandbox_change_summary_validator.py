from typing import Protocol, Tuple
from dataclasses import dataclass
from . import file_alias
from . import node_config

@dataclass(frozen=True)
class NetChange:
    file: file_alias.ReadWriteFile
    initial_content: file_alias.FileContent
    current_content: file_alias.FileContent

@dataclass(frozen=True)
class DiffSummary:
    summary_text: str

class ChangeSummaryValidator(node_config.VerificationCheck, Protocol):
    def verify(self) -> Tuple[bool, str]:
        ...
