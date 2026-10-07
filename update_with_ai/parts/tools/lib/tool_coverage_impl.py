# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T15:00:00Z
# CHANGE: new file
# CODE_HASH: 93aa0091b544
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations

import ast
import contextlib
import io
import os
from pathlib import Path
import sys
import trace
import types
from typing import Dict, List, Optional, Sequence, Set, Tuple
import unittest

from support.lib.lifecycle import Singleton
from update_with_ai.parts.agent.lib import agent_session
from . import tool_coverage


class CoverageEvaluator(tool_coverage.CoverageEvaluator, Singleton):
    """Implementation of coverage evaluator providing AST analysis, test tracing, and report generation."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    def format_ranges(self, lines: Sequence[int]) -> str:
        """Formats a sorted sequence of line numbers into compact comma-separated ranges."""
        sorted_lines = sorted(lines)
        if not sorted_lines:
            return ""
        ranges: List[str] = []
        start = sorted_lines[0]
        end = sorted_lines[0]
        for n in sorted_lines[1:]:
            if n == end + 1:
                end = n
            else:
                ranges.append(f"{start}" if start == end else f"{start}-{end}")
                start = end = n
        ranges.append(f"{start}" if start == end else f"{start}-{end}")
        return ", ".join(ranges)

    def group_into_spans(self, lines: Sequence[int]) -> List[Tuple[int, int]]:
        """Groups sorted line numbers into contiguous (start, end) span tuples."""
        sorted_lines = sorted(lines)
        if not sorted_lines:
            return []
        spans: List[Tuple[int, int]] = []
        start = sorted_lines[0]
        end = sorted_lines[0]
        for n in sorted_lines[1:]:
            if n == end + 1:
                end = n
            else:
                spans.append((start, end))
                start = end = n
        spans.append((start, end))
        return spans

    def normalize_target_query(self, raw_query: str) -> str:
        """Normalizes query string by stripping Bazel target or path prefixes."""
        q = raw_query.strip()
        if q.startswith("//"):
            q = q.split(":")[-1]
        elif ":" in q:
            q = q.split(":")[-1]
        if "/" in q:
            q = q.split("/")[-1]
        if q.endswith(".py"):
            q = q[:-3]
        return q

    def format_spans_report(
        self, cov: tool_coverage.ModuleCoverage, max_spans: Optional[int] = None
    ) -> str:
        """Formats uncovered statement spans with source code lines and optional clamping."""
        if not cov.missing_spans:
            return "All statements covered."
        try:
            with open(cov.file_path, "r", encoding="utf-8") as f:
                src_lines = f.readlines()
        except OSError:
            src_lines = []

        shown_spans = (
            cov.missing_spans[:max_spans] if max_spans is not None else cov.missing_spans
        )
        lines: List[str] = []
        lines.append(f"Uncovered statement spans in {cov.module_name}:")
        for idx, (start, end) in enumerate(shown_spans, 1):
            span_label = f"line {start}" if start == end else f"lines {start}-{end}"
            lines.append(f"\n  Span {idx} ({span_label}):")
            for ln in range(start, end + 1):
                if ln in cov.missing_lines:
                    text = (
                        src_lines[ln - 1].rstrip("\r\n")
                        if 0 < ln <= len(src_lines)
                        else ""
                    )
                    lines.append(f"    {ln:4d}: {text}")

        if max_spans is not None:
            omitted = len(cov.missing_spans) - len(shown_spans)
            if omitted > 0:
                lines.append(
                    f"\nNote: Clamped presentation to first {max_spans} non-continuous spans ({omitted} additional uncovered span{'s' if omitted > 1 else ''} omitted)."
                )
        return "\n".join(lines)

    def format_coverage_report(
        self,
        cov: tool_coverage.ModuleCoverage,
        threshold: float,
        max_spans: Optional[int] = None,
    ) -> str:
        """Formats structured coverage report suitable for console output and log files."""
        if not cov.test_passed:
            return (
                f"================================================================================\n"
                f"UNIT TEST FAILURE in {cov.test_name}\n"
                f"================================================================================\n"
                f"Coverage cannot be evaluated because the unit test suite failed:\n\n"
                f"{cov.test_error}\n"
            )

        if cov.missed == 0:
            return f"✓ 100.0% coverage - all {cov.total_executable} executable statements executed by {cov.test_name}. All code covered; call finish() to conclude the session.\n"

        spans_detail = self.format_spans_report(cov, max_spans=max_spans)
        return (
            f"================================================================================\n"
            f"COVERAGE DEFICIT DETECTED: {cov.coverage_pct:.1f}% (Threshold: {threshold:.1f}%)\n"
            f"================================================================================\n"
            f"Test Suite:      {cov.test_name}\n"
            f"Implementation:  {cov.module_name}\n"
            f"Statements:      {cov.total_executable} executable, {cov.covered} covered, {cov.missed} missed\n"
            f"Total Spans:     {len(cov.missing_spans)} non-continuous span{'s' if len(cov.missing_spans) > 1 else ''}\n"
            f"--------------------------------------------------------------------------------\n"
            f"{spans_detail}\n"
            f"--------------------------------------------------------------------------------\n"
            f"AGENT GUIDANCE:\n"
            f"1. Read the library implementation file with line numbers enabled to analyze uncovered cases.\n"
            f"2. Translate each uncovered statement into missing requirements with respect to the grounding specification.\n"
            f"3. Deliver blame feedback to the test agent exclusively using the language of the grounding specification.\n"
            f"   DO NOT cite library file names, file paths, or line numbers in the feedback.\n"
            f"4. If an uncovered line represents an impossible case or caller assumption guaranteed by the grounding contract,\n"
            f"   the ONLY permitted blame feedback to the library implementation is to mark the line with:\n"
            f"   # pragma: no cover (assumption: <reason>)\n"
            f"================================================================================\n"
        )

    def get_available_targets(
        self, repo_root: Path | str
    ) -> Dict[str, Tuple[Path, Path]]:
        """Scans repository for implementation files and companion test suites."""
        root = Path(repo_root)
        mapping: Dict[str, Tuple[Path, Path]] = {}
        parts_dir = root / "update_with_ai" / "parts"
        if parts_dir.is_dir():
            for impl_path in sorted(parts_dir.glob("*/lib/*_impl.py")):
                domain = impl_path.parent.parent.name
                test_file = parts_dir / domain / "tests" / f"{impl_path.stem}_test.py"
                if test_file.is_file():
                    base_name = (
                        impl_path.stem[:-5]
                        if impl_path.stem.endswith("_impl")
                        else impl_path.stem
                    )
                    mapping[impl_path.name] = (impl_path, test_file)
                    mapping[impl_path.stem] = (impl_path, test_file)
                    mapping[test_file.name] = (impl_path, test_file)
                    mapping[test_file.stem] = (impl_path, test_file)
                    mapping[base_name] = (impl_path, test_file)
        return mapping

    def get_non_executable_lines(self, file_path: Path | str) -> Set[int]:
        """Analyzes AST to identify lines that are not executable statements."""
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src, str(path))

        non_exec: Set[int] = set()

        lines = src.splitlines()
        pragma_lines: Set[int] = set()
        for idx, line in enumerate(lines, 1):
            if "# pragma: no cover" in line or "# no cover" in line:
                pragma_lines.add(idx)

        block_types = (ast.stmt, ast.ExceptHandler, getattr(ast, "match_case", ()))
        for node in ast.walk(tree):
            if not isinstance(node, block_types):
                continue
            start = getattr(node, "lineno", None)
            pattern = getattr(node, "pattern", None)
            if start is None and pattern is not None:
                start = getattr(pattern, "lineno", None)
            if start is not None and start in pragma_lines:
                end = getattr(node, "end_lineno", None)
                body = getattr(node, "body", None)
                if end is None and body:
                    last_stmt = body[-1]
                    end = getattr(
                        last_stmt,
                        "end_lineno",
                        getattr(last_stmt, "lineno", start),
                    )
                end = end if end is not None else start
                for ln in range(start, end + 1):
                    non_exec.add(ln)

        non_exec.update(pragma_lines)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.body:
                    first_body = node.body[0]
                    for ln in range(node.lineno + 1, first_body.lineno):
                        non_exec.add(ln)
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                start = node.lineno
                end = getattr(node, "end_lineno", node.lineno)
                for ln in range(start, end + 1):
                    non_exec.add(ln)
        return non_exec

    def measure_single_target_coverage(
        self, impl_path: Path | str, test_path: Path | str
    ) -> tool_coverage.ModuleCoverage:
        """Executes single target test suite under trace instrumentation and calculates metrics."""
        ipath = Path(impl_path).resolve()
        tpath = Path(test_path).resolve()

        find_exec = getattr(trace, "_find_executable_linenos", None)
        raw_exec: Set[int] = set()
        if callable(find_exec):
            exec_dict = find_exec(str(ipath))
            if isinstance(exec_dict, dict):
                raw_exec = {ln for ln in exec_dict.keys() if isinstance(ln, int) and ln > 0}
        non_exec = self.get_non_executable_lines(ipath)
        exec_lines = raw_exec - non_exec

        module_base = ipath.stem
        lib_mod_name = f"lib.{module_base}"
        test_mod_name = f"tests.{tpath.stem}"

        for m in list(sys.modules.keys()):
            if m.startswith(lib_mod_name) or m.startswith(test_mod_name):
                del sys.modules[m]

        if "lib" not in sys.modules or not getattr(sys.modules["lib"], "__path__", None):
            lib_pkg = types.ModuleType("lib")
            lib_pkg.__path__ = [str(ipath.parent)]
            sys.modules["lib"] = lib_pkg
        else:
            lib_dir_str = str(ipath.parent)
            if lib_dir_str not in sys.modules["lib"].__path__:
                sys.modules["lib"].__path__.insert(0, lib_dir_str)

        if "tests" not in sys.modules or not getattr(
            sys.modules["tests"], "__path__", None
        ):
            tests_pkg = types.ModuleType("tests")
            tests_pkg.__path__ = [str(tpath.parent)]
            sys.modules["tests"] = tests_pkg
        else:
            test_dir_str = str(tpath.parent)
            if test_dir_str not in sys.modules["tests"].__path__:
                sys.modules["tests"].__path__.insert(0, test_dir_str)

        tracer = trace.Trace(count=1, trace=0)

        test_load_error: Optional[str] = None
        test_failures_str: Optional[str] = None
        test_passed = True

        def run_suite() -> None:
            nonlocal test_load_error, test_failures_str, test_passed
            loader = unittest.TestLoader()
            try:
                suite = loader.loadTestsFromName(test_mod_name)
            except (ImportError, AttributeError, SyntaxError, TypeError, ValueError, NameError) as e:
                test_load_error = str(e)
                test_passed = False
                return

            runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                res = runner.run(suite)
            if res.errors:
                for _test_case, err_trace in res.errors:
                    if "Failed to import test module" in err_trace:
                        test_load_error = err_trace
                        test_passed = False
                        return
            if not res.wasSuccessful():
                test_passed = False
                fail_lines = []
                for test_case, err in res.failures + res.errors:
                    fail_lines.append(f"{test_case}:\n{err}")
        orig_sys_path = list(sys.path)
        try:
            if str(ipath.parent) not in sys.path:
                sys.path.insert(0, str(ipath.parent))
            if str(tpath.parent) not in sys.path:
                sys.path.insert(0, str(tpath.parent))
            tracer.runfunc(run_suite)
        finally:
            sys.path[:] = orig_sys_path

        if not test_passed:
            err_msg = (
                test_load_error or test_failures_str or "Test suite execution failed."
            )
            return tool_coverage.ModuleCoverage(
                module_name=ipath.name,
                test_name=tpath.name,
                file_path=str(ipath),
                test_path=str(tpath),
                total_executable=len(exec_lines),
                covered=0,
                missed=len(exec_lines),
                coverage_pct=0.0,
                missing_lines=sorted(list(exec_lines)),
                missing_ranges=self.format_ranges(sorted(list(exec_lines))),
                missing_spans=self.group_into_spans(sorted(list(exec_lines))),
                test_passed=False,
                test_error=err_msg,
            )

        results = tracer.results()
        abs_impl = str(ipath.resolve())
        covered_lines: Set[int] = set()
        for (fn, ln), _ in results.counts.items():
            if (
                os.path.abspath(fn) == abs_impl or Path(fn).name == ipath.name
            ) and ln in exec_lines:
                covered_lines.add(ln)

        missed_lines = sorted(list(exec_lines - covered_lines))
        total_exec = len(exec_lines)
        cov_pct = (len(covered_lines) / total_exec * 100) if total_exec else 100.0
        spans = self.group_into_spans(missed_lines)

        return tool_coverage.ModuleCoverage(
            module_name=ipath.name,
            test_name=tpath.name,
            file_path=str(ipath),
            test_path=str(tpath),
            total_executable=total_exec,
            covered=len(covered_lines),
            missed=len(missed_lines),
            coverage_pct=cov_pct,
            missing_lines=missed_lines,
            missing_ranges=self.format_ranges(missed_lines),
            missing_spans=spans,
            test_passed=True,
        )

    def evaluate_coverage(
        self,
        target_or_impl: str,
        test_path: Optional[Path | str] = None,
        repo_root: Optional[Path | str] = None,
        threshold: float = 0.0,
        update_log: Optional[Path | str] = None,
        max_spans: Optional[int] = None,
    ) -> tool_coverage.ModuleCoverage:
        """Measures target coverage, validates threshold, and optionally writes coverage log."""
        root = Path(repo_root) if repo_root else Path.cwd()
        if test_path is not None:
            ipath = Path(target_or_impl)
            if not ipath.is_absolute():
                ipath = (root / ipath).resolve()
            tpath = Path(test_path)
            if not tpath.is_absolute():
                tpath = (root / tpath).resolve()
        else:
            target_map = self.get_available_targets(root)
            query = self.normalize_target_query(target_or_impl)
            if query not in target_map:
                raise ValueError(
                    f"Unrecognized target '{target_or_impl}'. Available: {sorted(target_map.keys())}"
                )
            ipath, tpath = target_map[query]

        cov = self.measure_single_target_coverage(ipath, tpath)

        if update_log:
            log_p = Path(update_log)
            if not log_p.is_absolute():
                log_p = root / log_p
            log_p.parent.mkdir(parents=True, exist_ok=True)
            report = self.format_coverage_report(
                cov, threshold, max_spans=max_spans
            )
            if cov.test_passed and cov.missed == 0:
                with open(log_p, "w", encoding="utf-8") as f:
                    pass
            else:
                with open(log_p, "w", encoding="utf-8") as f:
                    f.write(report)

        return cov
