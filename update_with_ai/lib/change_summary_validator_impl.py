"""Change summary validator implementation checking net modifications."""

import difflib
from typing import Sequence, Optional
from .change_summary_validator import (
    ChangeValidator,
    DiffSummary,
    NetChange,
    ChangeSummary,
    ValidationFeedback,
)


class ChangeValidatorImpl(ChangeValidator):
    def __init__(self, max_diff_chars: int = 4000) -> None:
        self.max_diff_chars = max_diff_chars

    def validate_change_summary(
        self, summary: ChangeSummary, net_changes: Sequence[NetChange]
    ) -> Optional[ValidationFeedback]:
        actual_changes = [c for c in net_changes if c.initial_content != c.current_content]
        if not actual_changes and not summary:
            return None
        if not summary:
            return "Change summary is required when files are modified"
        if len(summary) > 4000:
            return "Change summary exceeds maximum length bound of 4,000 characters"
        for change in net_changes:
            if change.initial_content == change.current_content and change.file_name in summary:
                return f"File {change.file_name} has net-zero modifications and cannot be claimed as modified"
        for change in actual_changes:
            if change.file_name not in summary:
                return f"Modified file {change.file_name} is not described in change summary"
        return None

    def compute_diff_summary(
        self, net_changes: Sequence[NetChange]
    ) -> DiffSummary:
        diff_chunks = []
        for change in net_changes:
            from_lines = change.initial_content.splitlines(keepends=True)
            to_lines = change.current_content.splitlines(keepends=True)
            diff = difflib.unified_diff(
                from_lines,
                to_lines,
                fromfile=f"a/{change.file_name}",
                tofile=f"b/{change.file_name}",
            )
            diff_chunks.append("".join(diff))
        full_diff = "".join(diff_chunks)
        return full_diff[: self.max_diff_chars]
