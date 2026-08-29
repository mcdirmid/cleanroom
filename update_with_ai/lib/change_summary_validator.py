# lib/change_summary_validator.py
"""
Interface LLS: change_summary_validator
"""
from typing import Any, Dict, List, Optional, Protocol, TypeAlias
from .tool_provider import ToolFailure

ClaimedChanges: TypeAlias = Optional[List[Dict[str, str]]]
ValidationOutcome: TypeAlias = Optional[ToolFailure[str]]


class ChangeSummaryValidator(Protocol):
    def compute_diff_summary(self) -> str:
        ...

    def get_effective_changes(self) -> List[str]:
        ...

    def validate_change_summaries(self, changes: ClaimedChanges) -> ValidationOutcome:
        ...

    def reset_validator_state(self) -> None:
        ...
