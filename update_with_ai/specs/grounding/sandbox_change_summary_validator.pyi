from typing import Protocol, Tuple
from framework import data_type, operation, override, singleton_type
from dataclasses import dataclass
import file_alias
import sandbox_run_control

@dataclass(frozen=True)
@data_type
class NetChange:
    """
PURPOSE:
Observable difference between initial and current file content
"""

    def __init__(self, file: file_alias.ReadWriteFile, initial_content: file_alias.FileContent, current_content: file_alias.FileContent) -> None:
        ...

    @property
    def file(self) -> file_alias.ReadWriteFile:
        """
PURPOSE:
Modified file exhibiting net changes
"""
        ...

    @property
    def initial_content(self) -> file_alias.FileContent:
        """
PURPOSE:
Baseline content at session start
"""
        ...

    @property
    def current_content(self) -> file_alias.FileContent:
        """
PURPOSE:
Current content on disk
"""
        ...

@dataclass(frozen=True)
@data_type
class DiffSummary:
    """
PURPOSE:
Formatted representation of line changes across modified files
"""

    def __init__(self, summary_text: str) -> None:
        ...

    @property
    def summary_text(self) -> str:
        """
PURPOSE:
Formatted diff representation
"""
        ...

@singleton_type('agent_session')
class ChangeSummaryValidator(sandbox_run_control.VerificationCheck, Protocol):
    """
PURPOSE:
Defined as an agent session service verifying change summaries

INHERITANCE:
- sandbox_run_control.VerificationCheck: Implements verification check evaluated during session advancement
"""

    @operation
    @override
    def verify(self) -> Tuple[bool, str]:
        """
PURPOSE:
Verifies change summary accuracy against net changes

FRESH_REQUIREMENTS:
- The change summary validator verifies that a change summary describes all net changes across workspace files.
- The change summary validator rejects a change summary that claims changes for files with no net change.
- The change summary validator produces a diff summary of modified files.
- The change summary validator rejects a change summary exceeding configured length bounds with shortening guidance.
"""
        ...
