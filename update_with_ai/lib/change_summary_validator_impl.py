# lib/change_summary_validator_impl.py
"""
Implementation LLS: change_summary_validator_impl
"""
import difflib
from typing import Any, Dict, List, Optional

from .change_summary_validator import (
    ChangeSummaryValidator,
    ClaimedChanges,
    ValidationOutcome,
)
from .file_editor import FileEditor
from .tool_provider import ToolFailure

SOFT_CHANGE_SUMMARY_LENGTH = 300
HARD_CHANGE_SUMMARY_LENGTH = 500
SUMMARY_LENGTH_GRACE = 4


class ChangeSummaryValidatorImpl(ChangeSummaryValidator):
    """
    Concrete implementation of ChangeSummaryValidator.
    """

    def __init__(self, file_editor: FileEditor, diff_size_limit: int = 1000) -> None:
        self.file_editor = file_editor
        self.diff_size_limit = diff_size_limit
        self._soft_rejections: Dict[str, int] = {}
        self._hard_rejections: Dict[str, int] = {}

    def get_effective_changes(self) -> List[str]:
        effectively_changed: List[str] = []
        for file_path in self.file_editor.get_changed_files():
            current = self.file_editor.get_current_content(file_path)
            if current != self.file_editor.get_run_start_snapshot(file_path):
                effectively_changed.append(file_path)
        return effectively_changed

    def compute_diff_summary(self) -> str:
        diff_chunks: List[str] = []
        for file_path in self.file_editor.get_changed_files():
            snapshot = self.file_editor.get_run_start_snapshot(file_path)
            current = self.file_editor.get_current_content(file_path)
            if snapshot == current:
                continue
            orig_lines = snapshot.splitlines(keepends=True) if snapshot is not None else []
            new_lines = current.splitlines(keepends=True) if current is not None else []
            diff = list(
                difflib.unified_diff(
                    orig_lines,
                    new_lines,
                    fromfile=f"a/{file_path}",
                    tofile=f"b/{file_path}",
                )
            )
            diff_chunks.append(f"### diff for {file_path}\n" + "".join(diff))

        diff_text = "\n".join(diff_chunks)
        if len(diff_text) > self.diff_size_limit:
            total_chars = len(diff_text)
            diff_text = (
                diff_text[: self.diff_size_limit]
                + f"\n... [diff truncated: showing {self.diff_size_limit} of {total_chars} characters]"
            )
        return diff_text

    def validate_change_summaries(self, changes: ClaimedChanges) -> ValidationOutcome:
        changes = changes or []
        effectively_changed = self.get_effective_changes()

        if not effectively_changed:
            if changes:
                return ToolFailure[str](
                    "Cannot advance: the run wrote files but net-changed "
                    "nothing — each file's current content equals its content "
                    "at run start. Call advance() with no changes to report "
                    "no change."
                )
            return None

        if not changes:
            failure_message = (
                f"Cannot advance: the run changed files ({', '.join(effectively_changed)}). Call "
                "advance(changes=[{file, summary}, ...]) with one entry "
                "per changed file — each summary one short sentence on "
                "what changed in that file (not how it was done) — so the "
                "change message can be broadcast to dependent nodes."
            )
            diff_text = self.compute_diff_summary()
            if diff_text:
                failure_message += "\n\nDiff of run changes:\n" + diff_text
            return ToolFailure[str](failure_message)

        claimed_files = [c.get("file", "") for c in changes]

        missing = [f for f in effectively_changed if f not in claimed_files]
        if missing:
            return ToolFailure[str](
                f"Cannot advance: changes list is missing entries for changed files: {', '.join(missing)}"
            )

        extra = [f for f in claimed_files if f not in effectively_changed]
        if extra:
            return ToolFailure[str](
                f"Cannot advance: changes list claims changes for files that did not net-change: {', '.join(extra)}"
            )

        for entry in changes:
            file_name = entry.get("file", "")
            summary = entry.get("summary", "")
            length = len(summary)

            if length > HARD_CHANGE_SUMMARY_LENGTH:
                grace = self._hard_rejections.get(file_name, 0)
                if grace >= SUMMARY_LENGTH_GRACE:
                    raise RuntimeError(
                        f"Change summary for {file_name} persistently exceeds hard length bound ({length} > {HARD_CHANGE_SUMMARY_LENGTH})"
                    )
                self._hard_rejections[file_name] = grace + 1
                return ToolFailure[str](
                    f"Cannot advance: change summary for {file_name} is too long ({length} chars). "
                    f"Must be under {HARD_CHANGE_SUMMARY_LENGTH} characters. Make it a single short sentence."
                )

            if length > SOFT_CHANGE_SUMMARY_LENGTH:
                grace = self._soft_rejections.get(file_name, 0)
                if grace < SUMMARY_LENGTH_GRACE:
                    self._soft_rejections[file_name] = grace + 1
                    return ToolFailure[str](
                        f"Cannot advance: change summary for {file_name} is verbose ({length} chars). "
                        f"Please shorten to under {SOFT_CHANGE_SUMMARY_LENGTH} characters (one concise sentence)."
                    )

        return None

    def reset_validator_state(self) -> None:
        self._soft_rejections.clear()
        self._hard_rejections.clear()
