from pathlib import Path
import tempfile
import textwrap
import unittest

from support.lib.lifecycle import LifecycleRegistry
from autofab.parts.workspace_cli.lib import coverage, coverage_impl


class ToolCoverageImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.evaluator = coverage_impl.CoverageEvaluator()
        self.registry.register_instance(
            self.evaluator,
            keys=[
                coverage.CoverageEvaluator,
                coverage_impl.CoverageEvaluator,
            ],
        )

    def test_format_ranges(self) -> None:
        self.assertEqual(self.evaluator.format_ranges([]), "")
        self.assertEqual(self.evaluator.format_ranges([5]), "5")
        self.assertEqual(
            self.evaluator.format_ranges([1, 2, 3, 7, 8, 12]), "1-3, 7-8, 12"
        )
        self.assertEqual(self.evaluator.format_ranges([10, 11, 12, 13]), "10-13")

    def test_group_into_spans(self) -> None:
        self.assertEqual(self.evaluator.group_into_spans([]), [])
        self.assertEqual(self.evaluator.group_into_spans([4]), [(4, 4)])
        self.assertEqual(
            self.evaluator.group_into_spans([1, 2, 3, 5, 8, 9]),
            [(1, 3), (5, 5), (8, 9)],
        )

    def test_normalize_target_query(self) -> None:
        self.assertEqual(
            self.evaluator.normalize_target_query(
                "//parts/tools:tool_coverage_impl_test"
            ),
            "tool_coverage_impl_test",
        )
        self.assertEqual(
            self.evaluator.normalize_target_query("autofab/lib/foo_impl.py"),
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
                with unreachable:
                    return False
            '''
        ).strip()
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(src)
            temp_path = f.name
        try:
            non_exec = self.evaluator.get_non_executable_lines(temp_path)
            # Lines 1 (module docstring), 5-7 (signature continuation), 8 (function docstring), 11-12 (with unreachable)
            self.assertIn(1, non_exec)
            self.assertIn(5, non_exec)
            self.assertIn(6, non_exec)
            self.assertIn(7, non_exec)
            self.assertIn(8, non_exec)
            self.assertIn(11, non_exec)
            self.assertIn(12, non_exec)
            self.assertNotIn(9, non_exec)  # 'if arg1 > 0:' is executable
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_format_reports(self) -> None:
        cov = coverage.ModuleCoverage(
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

        cov_perfect = coverage.ModuleCoverage(
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
        report_perfect = self.evaluator.format_coverage_report(
            cov_perfect, threshold=100.0
        )
        self.assertIn("100.0% coverage", report_perfect)

        cov_failed = coverage.ModuleCoverage(
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
        report_failed = self.evaluator.format_coverage_report(
            cov_failed, threshold=100.0
        )
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

    def test_measure_single_target_coverage_failing_suite(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            impl_file = td_path / "calc_impl.py"
            test_file = td_path / "calc_impl_test.py"

            impl_code = textwrap.dedent(
                """
                def add(a: int, b: int) -> int:
                    return a + b
                """
            )
            test_code = textwrap.dedent(
                """
                import unittest
                from calc_impl import add

                class CalcTest(unittest.TestCase):
                    def test_add(self):
                        self.assertEqual(add(2, 3), 999)
                """
            )

            impl_file.write_text(impl_code, encoding="utf-8")
            test_file.write_text(test_code, encoding="utf-8")

            cov = self.evaluator.measure_single_target_coverage(impl_file, test_file)
            self.assertFalse(cov.test_passed)
            self.assertIsNotNone(cov.test_error)
            self.assertIn("AssertionError", str(cov.test_error))
            # Executed line 2 (def add) was executed before the assertion in test
            self.assertGreater(cov.covered, 0)

    def test_measure_single_target_coverage_package_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pyproject.toml").write_text(
                "[project]\nname='test'\n", encoding="utf-8"
            )
            pkg_dir = root / "parts" / "widget_box"
            (pkg_dir / "lib").mkdir(parents=True)
            (pkg_dir / "tests").mkdir(parents=True)
            (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
            (pkg_dir / "lib" / "__init__.py").write_text("", encoding="utf-8")
            # Same stem in lib as the package name (the shadowing pitfall)
            (pkg_dir / "lib" / "widget_box.py").write_text(
                "class WidgetBox:\n    pass\n", encoding="utf-8"
            )
            impl_file = pkg_dir / "lib" / "widget_box_impl.py"
            impl_file.write_text(
                "from . import widget_box\nclass WidgetBoxImpl(widget_box.WidgetBox):\n    def size(self):\n        return 1\n",
                encoding="utf-8",
            )
            (pkg_dir / "tests" / "__init__.py").write_text("", encoding="utf-8")
            test_file = pkg_dir / "tests" / "widget_box_impl_test.py"
            test_file.write_text(
                "import unittest\nfrom widget_box.lib.widget_box_impl import WidgetBoxImpl\nclass WTest(unittest.TestCase):\n    def test_size(self):\n        self.assertEqual(WidgetBoxImpl().size(), 1)\n",
                encoding="utf-8",
            )

            cov = self.evaluator.measure_single_target_coverage(impl_file, test_file)
            self.assertTrue(cov.test_passed)
            self.assertIsNone(cov.test_error)
            self.assertEqual(cov.coverage_pct, 100.0)

    def test_classify_span_and_status_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            impl_file = td_path / "sample_service_impl.py"
            test_file = td_path / "sample_service_impl_test.py"

            impl_code = textwrap.dedent(
                """
                class ServiceConfigError(Exception):
                    pass

                def execute_task(port: int, flag: bool) -> str:
                    if port < 0:
                        raise ServiceConfigError("Port must be positive")
                    if flag:
                        return "active"
                    return "inactive"
                """
            ).strip()

            test_code = textwrap.dedent(
                """
                import unittest
                from sample_service_impl import execute_task

                class ServiceTest(unittest.TestCase):
                    def test_execute(self):
                        self.assertEqual(execute_task(80, True), "active")
                """
            ).strip()

            impl_file.write_text(impl_code, encoding="utf-8")
            test_file.write_text(test_code, encoding="utf-8")

            # Lines 5-6 raise ServiceConfigError
            owner_err, disp_err = self.evaluator.classify_span(impl_file, 5, 6)
            self.assertEqual(owner_err, "lib")
            self.assertIn("LIB-PRAGMA-REQUIRED: raises ServiceConfigError", disp_err)

            # Line 9 returns "inactive" (untested success branch)
            owner_test, disp_test = self.evaluator.classify_span(impl_file, 9, 9)
            self.assertEqual(owner_test, "test")
            self.assertIn("TEST-COVERAGE-DEFICIT", disp_test)

            cov = self.evaluator.evaluate_coverage(
                target_or_impl=str(impl_file),
                test_path=str(test_file),
                repo_root=td_path,
                threshold=100.0,
            )
            self.assertFalse(cov.coverage_pct >= 100.0)

            status_path = td_path / ".coverage_spans.json"
            self.assertTrue(status_path.is_file())
            import json

            with open(status_path, "r", encoding="utf-8") as sf:
                data = json.load(sf)
            self.assertIn("span_classifications", data)
            self.assertFalse(data.get("all_lib_pragma_required"))
            self.assertTrue(data.get("has_test_owned_spans"))

            # Now add companion low specification with Raises: ServiceConfigError
            part_low = td_path / "low"
            part_low.mkdir(parents=True, exist_ok=True)
            spec_file = part_low / "sample_service_impl.pyi"
            spec_file.write_text(
                "def execute_task(port: int, flag: bool) -> str:\n"
                '    """Executes task.\n'
                "\n"
                "    Raises:\n"
                "        ServiceConfigError: If port is negative.\n"
                '    """\n'
                "    ...\n",
                encoding="utf-8",
            )
            # Re-classify lines 5-6: now should be test-owned deficit!
            owner_contracted, disp_contracted = self.evaluator.classify_span(
                impl_file, 5, 6
            )
            self.assertEqual(owner_contracted, "test")
            self.assertIn(
                "TEST-COVERAGE-DEFICIT: missing contracted error assertion for ServiceConfigError",
                disp_contracted,
            )


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-11-04T12:15:00Z
# CHANGE: add tests for unified pytest execution under coverage, failing suite, and package resolution
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
