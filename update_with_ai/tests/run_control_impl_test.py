"""Tests for run_control_impl derived from LLS."""

import unittest
from typing import Optional, Sequence
from lib.tool_provider import ToolFailure, TerminationOutcome
from lib.run_control import RunControlConfig
from lib.change_summary_validator import ChangeValidator, NetChange
from lib.run_control_impl import RunControlFactoryImpl


class MockChangeValidator(ChangeValidator):
    def __init__(self, reject: bool = False, feedback: str = "Invalid summary") -> None:
        self.reject = reject
        self.feedback = feedback

    def validate_change_summary(
        self, summary: str, net_changes: Sequence[NetChange]
    ) -> Optional[str]:
        if self.reject or not summary:
            return self.feedback
        return None

    def compute_diff_summary(self, net_changes: Sequence[NetChange]) -> str:
        return ""


class RunControlImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = RunControlFactoryImpl()

    def test_tool_metadata(self) -> None:
        """Tests that advance, fail, and blame tools declare proper metadata."""
        controller = self.factory.create_run_control(
            config=RunControlConfig(blame_targets={"dep.py": "//pkg:dep"})
        )
        advance_meta = controller.get_advance_tool().get_metadata()
        self.assertEqual(advance_meta.name, "advance")

        fail_meta = controller.get_fail_tool().get_metadata()
        self.assertEqual(fail_meta.name, "fail")
        self.assertTrue("explanation" in fail_meta.parameters_schema or "explanation" in fail_meta.parameters_schema.get("properties", {}) or "reason" in fail_meta.parameters_schema)

        blame_tool = controller.get_blame_tool()
        self.assertIsNotNone(blame_tool)
        assert blame_tool is not None
        blame_meta = blame_tool.get_metadata()
        self.assertEqual(blame_meta.name, "blame")
        self.assertTrue("target" in blame_meta.parameters_schema or "target" in blame_meta.parameters_schema.get("properties", {}) or "file_name" in blame_meta.parameters_schema)
        self.assertTrue("explanation" in blame_meta.parameters_schema or "explanation" in blame_meta.parameters_schema.get("properties", {}) or "reason" in blame_meta.parameters_schema)

    def test_advance_with_change_validator(self) -> None:
        """Tests advance tool validation via ChangeValidator:
        1. Valid change summary with passing validator -> emits TerminationOutcome.
        2. Invalid change summary -> emits ToolFailure with feedback.
        """
        valid_validator = MockChangeValidator(reject=False)
        controller_pass = self.factory.create_run_control(
            config=RunControlConfig(change_summary_required=True),
            change_validator=valid_validator,
        )
        res_pass = controller_pass.get_advance_tool().execute({"change_summary": "Fixed bug in lib"})
        self.assertIsInstance(res_pass, TerminationOutcome)

        invalid_validator = MockChangeValidator(reject=True, feedback="Summary too short")
        controller_fail = self.factory.create_run_control(
            config=RunControlConfig(change_summary_required=True),
            change_validator=invalid_validator,
        )
        res_fail = controller_fail.get_advance_tool().execute({"change_summary": "bad"})
        self.assertIsInstance(res_fail, ToolFailure)
        self.assertTrue(bool(res_fail.feedback))

    def test_fail_tool_terminates_session(self) -> None:
        """Tests fail tool terminates run with failure TerminationOutcome."""
        controller = self.factory.create_run_control(config=RunControlConfig())
        fail_tool = controller.get_fail_tool()
        res = fail_tool.execute({"explanation": "Cannot resolve dependency"})
        self.assertIsInstance(res, TerminationOutcome)

    def test_blame_tool_routing_and_validation(self) -> None:
        """Tests blame tool behavior:
        1. Valid blame target emits TerminationOutcome for owning dependency node.
        2. Invalid blame target produces ToolFailure listing valid targets.
        3. No blame targets configured -> get_blame_tool returns None.
        """
        controller = self.factory.create_run_control(
            config=RunControlConfig(blame_targets={"dep_file.py": "//pkg:dep"})
        )
        blame_tool = controller.get_blame_tool()
        self.assertIsNotNone(blame_tool)
        assert blame_tool is not None

        # Valid blame with target and explanation
        res_valid = blame_tool.execute({"target": "dep_file.py", "explanation": "broken API"})
        self.assertIsInstance(res_valid, TerminationOutcome)

        # Invalid blame target produces ToolFailure
        res_inv = blame_tool.execute({"target": "non_existent.py", "explanation": "broken"})
        self.assertIsInstance(res_inv, ToolFailure)

        # No blame targets configured
        no_blame = self.factory.create_run_control(config=RunControlConfig(blame_targets=None))
        self.assertIsNone(no_blame.get_blame_tool())

    def test_get_tools_composition(self) -> None:
        """Tests get_tools returns advance and fail tools, plus blame tool only when configured."""
        controller_without_blame = self.factory.create_run_control(config=RunControlConfig(blame_targets=None))
        tools = controller_without_blame.get_tools()
        names = [t.get_metadata().name for t in tools]
        self.assertEqual(names, ["advance", "fail"])

        controller_with_blame = self.factory.create_run_control(
            config=RunControlConfig(blame_targets={"dep.py": "//pkg:dep"})
        )
        tools_with_blame = controller_with_blame.get_tools()
        names_with_blame = [t.get_metadata().name for t in tools_with_blame]
        self.assertEqual(names_with_blame, ["advance", "fail", "blame"])


if __name__ == "__main__":
    unittest.main()
