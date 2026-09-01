"""Tests for change_summary_validator_impl derived from LLS."""

import unittest
from lib.change_summary_validator import NetChange
from lib.change_summary_validator_impl import ChangeValidatorImpl


class ChangeSummaryValidatorImplTest(unittest.TestCase):
    def test_net_change_dataclass(self) -> None:
        """Tests Data Types: NetChange dataclass instantiation and field values."""
        change = NetChange(
            file_name="module.py",
            initial_content="def old(): pass",
            current_content="def new(): pass",
        )
        self.assertEqual(change.file_name, "module.py")
        self.assertEqual(change.initial_content, "def old(): pass")
        self.assertEqual(change.current_content, "def new(): pass")

    def test_default_constructor(self) -> None:
        """Tests Config: ChangeValidatorImpl default constructor."""
        validator = ChangeValidatorImpl()
        self.assertIsNotNone(validator)

    def test_validate_change_summary_all_sides_of_boundary(self) -> None:
        """Tests all sides of boundary for validating change summary:
        1. Empty net changes -> None (no summary required)
        2. Populated net changes + matching summary -> None
        3. Populated net changes + empty summary -> Error string
        4. Populated net changes + missing file summary -> Error string
        """
        validator = ChangeValidatorImpl()
        changes = [NetChange(file_name="foo.py", initial_content="a", current_content="b")]

        # Side 1: empty net changes
        self.assertIsNone(validator.validate_change_summary("summary", []))

        # Side 2: matching summary
        self.assertIsNone(validator.validate_change_summary("Updated foo.py", changes))

        # Side 3: empty summary with changes
        self.assertIsNotNone(validator.validate_change_summary("", changes))

        # Side 4: non-matching summary
        self.assertIsNotNone(validator.validate_change_summary("Updated bar.py", changes))

    def test_validate_change_summary_length_bounds(self) -> None:
        """Tests summary length bound behavior:
        1. Valid summary under 2,000 chars -> None.
        2. Summary exceeding hard bound (4,000 chars) -> returns ValidationFeedback.
        """
        validator = ChangeValidatorImpl()
        changes = [NetChange(file_name="foo.py", initial_content="a", current_content="b")]

        # Under 2000 chars
        summary_short = "Updated foo.py with new implementation details."
        self.assertIsNone(validator.validate_change_summary(summary_short, changes))

        # Exceeding hard bound (4000 chars)
        summary_long = "Updated foo.py " + ("x" * 4001)
        self.assertIsNotNone(validator.validate_change_summary(summary_long, changes))

    def test_compute_diff_summary_truncation_boundary(self) -> None:
        """Tests all sides of diff truncation boundary:
        1. Short diff within max_diff_chars -> full diff returned
        2. Large diff exceeding max_diff_chars -> truncated at max_diff_chars
        """
        validator = ChangeValidatorImpl(max_diff_chars=50)
        short_change = [NetChange(file_name="f.py", initial_content="1", current_content="2")]
        diff_short = validator.compute_diff_summary(short_change)
        self.assertLessEqual(len(diff_short), 50)

        long_change = [NetChange(file_name="long_file_name_with_extra_details.py", initial_content="x" * 100, current_content="y" * 100)]
        diff_long = validator.compute_diff_summary(long_change)
        self.assertLessEqual(len(diff_long), 50)

    def test_validate_change_summary_rejects_net_zero_modifications(self) -> None:
        """Tests Invariants: rejects change summaries claiming changes on files with net-zero modifications."""
        validator = ChangeValidatorImpl()
        net_zero = [NetChange(file_name="same.py", initial_content="hello", current_content="hello")]
        # Claiming modification on net-zero modified file returns error string
        err = validator.validate_change_summary("Modified same.py", net_zero)
        self.assertIsNotNone(err)


if __name__ == "__main__":
    unittest.main()
