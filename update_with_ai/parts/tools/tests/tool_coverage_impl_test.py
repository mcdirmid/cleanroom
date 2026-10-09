# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-06T15:15:00Z
# CHANGE: add tool_coverage_impl tests
# CODE_HASH: c4f3f0c98813
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

from pathlib import Path
import tempfile
import textwrap
import unittest

from support.lib.lifecycle import LifecycleRegistry
from update_with_ai.parts.tools.lib import tool_coverage, tool_coverage_impl


class ToolCoverageImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.evaluator = tool_coverage_impl.CoverageEvaluator()
        self.registry.register_instance(
            self.evaluator,
            keys=[
                tool_coverage.CoverageEvaluator,
                tool_coverage_impl.CoverageEvaluator,
            ],
        )

    def test_format_ranges(self) -> None:
        self.assertEqual(self.evaluator.format_ranges([]), "")
        self.assertEqual(self.evaluator.format_ranges([5]), "5")
        self.assertEqual(
            self.evaluator.format_ranges([1, 2, 3, 7, 8, 12]), "1-3, 7-8, 12"
        )
        self.assertEqual(
            self.evaluator.format_ranges([10, 11, 12, 13]), "10-13"
        )

    def test_group_into_spans(self) -> None:
        self.assertEqual(self.evaluator.group_into_spans([]), [])
        self.assertEqual(self.evaluator.group_into_spans([4]), [(4, 4)])
        self.assertEqual(
            self.evaluator.group_into_spans([1, 2, 3, 5, 8, 9]),
            [(1, 3), (5, 5), (8, 9)],
        )

    def test_normalize_target_query(self) -> None:
        self.assertEqual(
            self.evaluator.normalize_target_query("//parts/tools:tool_coverage_impl_test"),
            "tool_coverage_impl_test",
        )
        self.assertEqual(
            self.evaluator.normalize_target_query("update_with_ai/lib/foo_impl.py"),
            "foo_impl",
        )
        self.assertEqual(
            self.evaluator.normalize_target_query("bar_test"),
            "bar_test",
        )

    def test_get_non_executable_lines(self) -> None:
        src = textwrap.dedent(
            '''
            """Module docstring."""
            from typing import Optional

            def sample_function(
                arg1: int,
                arg2: Optional[str] = None,
            ) -> bool:
                """Function docstring."""
                if arg1 > 0:
                    return True
                else:  # pragma: no cover
                    return False
            '''
        ).strip()
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(src)
            temp_path = f.name
        try:
            non_exec = self.evaluator.get_non_executable_lines(temp_path)
            # Lines 1 (module docstring), 5-7 (signature continuation), 8 (function docstring), 11 (pragma)
            self.assertIn(1, non_exec)
            self.assertIn(5, non_exec)
            self.assertIn(6, non_exec)
            self.assertIn(7, non_exec)
            self.assertIn(8, non_exec)
            self.assertIn(11, non_exec)
            self.assertNotIn(9, non_exec)  # 'if arg1 > 0:' is executable
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_format_reports(self) -> None:
        cov = tool_coverage.ModuleCoverage(
            module_name="sample.py",
            test_name="sample_test.py",
            file_path="/fake/sample.py",
            test_path="/fake/sample_test.py",
            total_executable=10,
            covered=8,
            missed=2,
            coverage_pct=80.0,
            missing_lines=[5, 6],
            missing_ranges="5-6",
            missing_spans=[(5, 6)],
            test_passed=True,
        )
        report = self.evaluator.format_coverage_report(cov, threshold=100.0)
        self.assertIn("COVERAGE DEFICIT DETECTED: 80.0%", report)
        self.assertIn("sample.py", report)
        self.assertIn("sample_test.py", report)
        self.assertIn("AGENT GUIDANCE", report)

        cov_perfect = tool_coverage.ModuleCoverage(
            module_name="sample.py",
            test_name="sample_test.py",
            file_path="/fake/sample.py",
            test_path="/fake/sample_test.py",
            total_executable=10,
            covered=10,
            missed=0,
            coverage_pct=100.0,
            missing_lines=[],
            missing_ranges="",
            missing_spans=[],
            test_passed=True,
        )
        report_perfect = self.evaluator.format_coverage_report(cov_perfect, threshold=100.0)
        self.assertIn("100.0% coverage", report_perfect)

        cov_failed = tool_coverage.ModuleCoverage(
            module_name="sample.py",
            test_name="sample_test.py",
            file_path="/fake/sample.py",
            test_path="/fake/sample_test.py",
            total_executable=10,
            covered=0,
            missed=10,
            coverage_pct=0.0,
            missing_lines=[1, 2],
            missing_ranges="1-2",
            missing_spans=[(1, 2)],
            test_passed=False,
            test_error="AssertionError: expected True but got False",
        )
        report_failed = self.evaluator.format_coverage_report(cov_failed, threshold=100.0)
        self.assertIn("UNIT TEST FAILURE", report_failed)
        self.assertIn("AssertionError", report_failed)

    def test_measure_single_target_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            impl_file = td_path / "calc_impl.py"
            test_file = td_path / "calc_impl_test.py"

            impl_code = textwrap.dedent(
                """
                def add(a: int, b: int) -> int:
                    return a + b

                def unused_sub(a: int, b: int) -> int:
                    return a - b
                """
            )
            test_code = textwrap.dedent(
                """
                import unittest
                from calc_impl import add

                class CalcTest(unittest.TestCase):
                    def test_add(self):
                        self.assertEqual(add(2, 3), 5)
                """
            )

            impl_file.write_text(impl_code, encoding="utf-8")
            test_file.write_text(test_code, encoding="utf-8")

            cov = self.evaluator.measure_single_target_coverage(impl_file, test_file)
            self.assertTrue(cov.test_passed)
            self.assertGreater(cov.total_executable, 0)
            self.assertGreater(cov.covered, 0)
            self.assertGreater(cov.missed, 0)
            self.assertLess(cov.coverage_pct, 100.0)


if __name__ == "__main__":
    unittest.main()
