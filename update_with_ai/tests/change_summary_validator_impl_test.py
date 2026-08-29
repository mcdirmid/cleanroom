"""
Tests for ChangeSummaryValidatorImpl.
"""

import unittest
from typing import Dict, List, Optional, Set

from lib.change_summary_validator_impl import (
    ChangeSummaryValidatorImpl,
    HARD_CHANGE_SUMMARY_LENGTH,
    SOFT_CHANGE_SUMMARY_LENGTH,
    SUMMARY_LENGTH_GRACE,
)
from lib.file_editor import FileEditor
from lib.tool_provider import ToolDefinition, ToolCallOutcome, ToolFailure


class _MockFileEditor(FileEditor):
    def __init__(
        self,
        files: Optional[Dict[str, str]] = None,
        snapshots: Optional[Dict[str, str]] = None,
        changed_files: Optional[List[str]] = None,
    ) -> None:
        self.files = dict(files or {})
        self.snapshots = dict(snapshots or {})
        self.changed_files = list(changed_files or [])

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return []

    def replace(self, file_path: str, old_str: str, new_str: str, expect_multiple: bool = False) -> ToolCallOutcome:
        return ToolFailure[str]("not implemented")

    def update_lines(self, file_path: str, start_line: int, end_line: int, new_str: str) -> ToolCallOutcome:
        return ToolFailure[str]("not implemented")

    def get_write_occurred(self) -> bool:
        return bool(self.changed_files)

    def get_changed_files(self) -> List[str]:
        return list(self.changed_files)

    def get_run_start_snapshot(self, file_path: str) -> Optional[str]:
        return self.snapshots.get(file_path)

    def get_current_content(self, file_path: str) -> Optional[str]:
        return self.files.get(file_path)

    def is_writable(self, file_path: str) -> bool:
        return True


class TestChangeSummaryValidatorImpl(unittest.TestCase):
    def test_effective_changes_detects_modified_files(self) -> None:
        editor = _MockFileEditor(
            files={"a.txt": "new content", "b.txt": "same"},
            snapshots={"a.txt": "old content", "b.txt": "same"},
            changed_files=["a.txt", "b.txt"],
        )
        validator = ChangeSummaryValidatorImpl(file_editor=editor)
        self.assertEqual(validator.get_effective_changes(), ["a.txt"])

    def test_compute_diff_summary_formats_diff(self) -> None:
        editor = _MockFileEditor(
            files={"a.txt": "line 1\nline 2 new\n"},
            snapshots={"a.txt": "line 1\nline 2 old\n"},
            changed_files=["a.txt"],
        )
        validator = ChangeSummaryValidatorImpl(file_editor=editor, diff_size_limit=500)
        diff = validator.compute_diff_summary()
        self.assertIn("-line 2 old", diff)
        self.assertIn("+line 2 new", diff)

    def test_validate_no_changes_when_net_unchanged_succeeds(self) -> None:
        editor = _MockFileEditor(
            files={"a.txt": "same"},
            snapshots={"a.txt": "same"},
            changed_files=["a.txt"],
        )
        validator = ChangeSummaryValidatorImpl(file_editor=editor)
        self.assertIsNone(validator.validate_change_summaries([]))

    def test_validate_claims_when_net_unchanged_fails(self) -> None:
        editor = _MockFileEditor(
            files={"a.txt": "same"},
            snapshots={"a.txt": "same"},
            changed_files=["a.txt"],
        )
        validator = ChangeSummaryValidatorImpl(file_editor=editor)
        result = validator.validate_change_summaries([{"file": "a.txt", "summary": "changed"}])
        self.assertIsInstance(result, ToolFailure)
        assert isinstance(result, ToolFailure)
        self.assertIn("net-changed nothing", result.value)

    def test_validate_missing_changes_when_files_modified_fails(self) -> None:
        editor = _MockFileEditor(
            files={"a.txt": "new"},
            snapshots={"a.txt": "old"},
            changed_files=["a.txt"],
        )
        validator = ChangeSummaryValidatorImpl(file_editor=editor)
        result = validator.validate_change_summaries([])
        self.assertIsInstance(result, ToolFailure)
        assert isinstance(result, ToolFailure)
        self.assertIn("Cannot advance: the run changed files", result.value)

    def test_validate_missing_or_extra_claimed_files_fails(self) -> None:
        editor = _MockFileEditor(
            files={"a.txt": "new", "b.txt": "new"},
            snapshots={"a.txt": "old", "b.txt": "old"},
            changed_files=["a.txt", "b.txt"],
        )
        validator = ChangeSummaryValidatorImpl(file_editor=editor)
        # Missing b.txt
        res1 = validator.validate_change_summaries([{"file": "a.txt", "summary": "changed a"}])
        self.assertIsInstance(res1, ToolFailure)
        assert isinstance(res1, ToolFailure)
        self.assertIn("missing entries for changed files: b.txt", res1.value)

        # Extra c.txt
        res2 = validator.validate_change_summaries([
            {"file": "a.txt", "summary": "changed a"},
            {"file": "b.txt", "summary": "changed b"},
            {"file": "c.txt", "summary": "changed c"},
        ])
        self.assertIsInstance(res2, ToolFailure)
        assert isinstance(res2, ToolFailure)
        self.assertIn("claims changes for files that did not net-change: c.txt", res2.value)

    def test_validate_soft_limit_grace_period(self) -> None:
        editor = _MockFileEditor(
            files={"a.txt": "new"},
            snapshots={"a.txt": "old"},
            changed_files=["a.txt"],
        )
        validator = ChangeSummaryValidatorImpl(file_editor=editor)
        long_summary = "x" * (SOFT_CHANGE_SUMMARY_LENGTH + 10)

        # Soft rejections up to grace count
        for _ in range(SUMMARY_LENGTH_GRACE):
            res = validator.validate_change_summaries([{"file": "a.txt", "summary": long_summary}])
            self.assertIsInstance(res, ToolFailure)
            assert isinstance(res, ToolFailure)
            self.assertIn("verbose", res.value)

        # Next attempt accepted
        accepted = validator.validate_change_summaries([{"file": "a.txt", "summary": long_summary}])
        self.assertIsNone(accepted)

    def test_validate_hard_limit_raises_runtime_error_after_grace(self) -> None:
        editor = _MockFileEditor(
            files={"a.txt": "new"},
            snapshots={"a.txt": "old"},
            changed_files=["a.txt"],
        )
        validator = ChangeSummaryValidatorImpl(file_editor=editor)
        very_long = "x" * (HARD_CHANGE_SUMMARY_LENGTH + 10)

        for _ in range(SUMMARY_LENGTH_GRACE):
            res = validator.validate_change_summaries([{"file": "a.txt", "summary": very_long}])
            self.assertIsInstance(res, ToolFailure)
            assert isinstance(res, ToolFailure)
            self.assertIn("too long", res.value)

        with self.assertRaises(RuntimeError):
            validator.validate_change_summaries([{"file": "a.txt", "summary": very_long}])


if __name__ == "__main__":
    unittest.main()
