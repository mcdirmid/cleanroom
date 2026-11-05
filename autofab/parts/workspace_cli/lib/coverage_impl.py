from __future__ import annotations

import ast
import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import trace
import types
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)
from . import coverage


def _extract_contracted_errors(file_path: Path | str) -> Set[str]:
    """Extracts contracted operational errors declared under 'Raises:' in companion low/*.pyi specifications."""
    try:
        p = Path(file_path).resolve()
    except Exception:
        return set()

    candidate_dirs: List[Path] = []
    if p.parent.name in ("lib", "tests", "pretense", "high", "planning", "scenarios"):
        low_dir = p.parent.parent / "low"
        if low_dir.is_dir():
            candidate_dirs.append(low_dir)

    curr = p.parent
    while curr != curr.parent:
        low_cand = curr / "low"
        if low_cand.is_dir() and low_cand not in candidate_dirs:
            candidate_dirs.append(low_cand)
        parts_dir = curr / "parts"
        if parts_dir.is_dir():
            for subpart in parts_dir.iterdir():
                low_sub = subpart / "low"
                if low_sub.is_dir() and low_sub not in candidate_dirs:
                    candidate_dirs.append(low_sub)
            if candidate_dirs:
                break
        if len(candidate_dirs) > 0:
            break
        curr = curr.parent

    contracted_errors: Set[str] = set()
    for l_dir in candidate_dirs:
        for pyi_file in l_dir.glob("*.pyi"):
            try:
                text = pyi_file.read_text(encoding="utf-8")
                for match in re.finditer(r"Raises:\s*\n((?:\s+.*?\n)+)", text):
                    block = match.group(1)
                    for line in block.splitlines():
                        line = line.strip()
                        m = re.match(r"^([A-Za-z0-9_.]*(?:Error|Exception))\b", line)
                        if m:
                            full_name = m.group(1)
                            contracted_errors.add(full_name)
                            if "." in full_name:
                                contracted_errors.add(full_name.split(".")[-1])
            except Exception:
                continue

    return contracted_errors


class CoverageEvaluator(coverage.CoverageEvaluator):
    """Realizes the system coverage evaluator as a system service providing AST analysis, traced unit test execution, and coverage report generation."""

    tier = system

    def __init__(self) -> None:
        pass

    # Contract: WHEN the supplied line numbers are empty, MUST return an empty string; group contiguous runs into 'start-end' and join with commas.
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

    # Contract: WHEN the supplied line numbers are empty, MUST return an empty list; group contiguous runs into single (start, end) tuples.
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

    # Contract: MUST strip leading '//' target prefixes and package specifiers; MUST strip '.py' file extensions from query string.
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

    # Contract: Classify an uncovered statement span by ownership ('lib' vs 'test') and required disposition.
    def classify_span(
        self, file_path: Path | str, start: int, end: int
    ) -> Tuple[str, str]:
        """Classifies an uncovered statement span by ownership ('lib' vs 'test') and required disposition."""
        src_path = Path(file_path)
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src, str(src_path))
        except Exception:
            return ("test", "TEST-COVERAGE-DEFICIT: missing unit test assertion")

        contracted_errors = _extract_contracted_errors(src_path)

        def _extract_error_name(exc: Any) -> Optional[str]:
            if isinstance(exc, ast.Call):
                fn = exc.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
                if name.endswith("Error") or name.endswith("Exception") or name == "unreachable":
                    return name
            elif isinstance(exc, (ast.Name, ast.Attribute)):
                name = exc.id if isinstance(exc, ast.Name) else getattr(exc, "attr", "")
                if name.endswith("Error") or name.endswith("Exception"):
                    return name
            return None

        error_names: List[str] = []
        has_precondition_guard = False

        for node in ast.walk(tree):
            n_start = getattr(node, "lineno", None)
            n_end = getattr(node, "end_lineno", n_start)
            if n_start is None:
                continue
            n_end = n_end or n_start
            if max(start, n_start) <= min(end, n_end):
                if isinstance(node, ast.Raise):
                    err = _extract_error_name(node.exc) if node.exc else None
                    if err:
                        error_names.append(err)
                    else:
                        error_names.append("Exception")
                elif isinstance(node, ast.Assert):
                    has_precondition_guard = True
                elif isinstance(node, ast.If):
                    for b_stmt in node.body:
                        if isinstance(b_stmt, ast.Raise):
                            err = _extract_error_name(b_stmt.exc) if b_stmt.exc else None
                            if err:
                                error_names.append(err)
                                if (
                                    err not in contracted_errors
                                    and err.split(".")[-1] not in contracted_errors
                                ):
                                    has_precondition_guard = True

        src_lines = src.splitlines()
        for ln in range(start, min(end + 1, len(src_lines) + 1)):
            line_text = src_lines[ln - 1] if 0 < ln <= len(src_lines) else ""
            m = re.search(r"\braise\s+([A-Za-z0-9_.]*(?:Error|Exception))\b", line_text)
            if m:
                error_names.append(m.group(1))
            if "unreachable(" in line_text:
                error_names.append("unreachable")

        if error_names:
            unique_errs = sorted(set(error_names))
            contracted_found = [
                e for e in unique_errs
                if e in contracted_errors or e.split(".")[-1] in contracted_errors
            ]
            uncontracted_found = [
                e for e in unique_errs
                if e not in contracted_errors and e.split(".")[-1] not in contracted_errors
            ]
            if contracted_found:
                err_str = ", ".join(contracted_found)
                return ("test", f"TEST-COVERAGE-DEFICIT: missing contracted error assertion for {err_str}")
            if uncontracted_found:
                err_str = ", ".join(uncontracted_found)
                return ("lib", f"LIB-PRAGMA-REQUIRED: raises {err_str}")
        if has_precondition_guard:
            return ("lib", "LIB-PRAGMA-REQUIRED: precondition guard")

        return ("test", "TEST-COVERAGE-DEFICIT: missing unit test assertion")

    # Contract: WHEN no missing spans remain, MUST return "All statements covered."; present each uncovered statement span with source lines, clamped by max_spans.
    def format_spans_report(
        self, cov: coverage.ModuleCoverage, max_spans: Optional[int] = None
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
            _, disposition = self.classify_span(cov.file_path, start, end)
            lines.append(f"\n  Span {idx} ({span_label}) [{disposition}]:")
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

    # Contract: Report unit test failure if test failed; report 100% success if no statements missed; report deficit metrics with ranges, spans, and agent guidance against threshold.
    def format_coverage_report(
        self,
        cov: coverage.ModuleCoverage,
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
            f"Missing Lines:   {cov.missing_ranges}\n"
            f"Total Spans:     {len(cov.missing_spans)} non-continuous span{'s' if len(cov.missing_spans) > 1 else ''}\n"
            f"--------------------------------------------------------------------------------\n"
            f"{spans_detail}\n"
            f"--------------------------------------------------------------------------------\n"
            f"AGENT GUIDANCE / COVERAGE ARBITER REMINDER [EXPLAIN FEEDBACK IN TERMS OF SPECIFICATION]:\n"
            f"• Differentiate contracted operational errors from uncontracted caller preconditions:\n"
            f"  - Contracted operational errors (documented under Raises: in low/*.pyi) are test-owned deficits ([TEST-COVERAGE-DEFICIT]). Tests MUST assert these error conditions.\n"
            f"  - Uncontracted caller precondition guards or unreachable defensive checks are library-owned ([LIB-PRAGMA-REQUIRED]). Instruct the library to prune dead code or annotate with '# pragma: no cover (assumption: precondition enforced by caller)'.\n"
            f"• Blame feedback MUST be provided in terms of how the file being blamed is not compliant with the common source of truth specification.\n"
            f"• Line numbers MAY be mentioned ONLY IF they reference the file being blamed.\n"
            f"• DO NOT expose details (line numbers, code snippets, or internal symbols) of other files.\n"
            f"• Translate contracted positive-path postconditions, invariants, or success branches into missing unit test cases.\n"
            f"• If an uncovered branch is an unreachable defensive check or caller assumption guaranteed by the specification, instruct the implementation author to prune it or mark it as unreachable (# pragma: no cover) according to the methodology.\n"
            f"• If an uncovered span persists after tests were updated or across multiple rounds, deeply examine the library implementation: trace control flow and invariants to determine whether the span is structurally or logically unreachable; if so, blame the library rather than repeating blame to tests.\n"
            f"• If 100% coverage appears unreachable without either testing an uncontracted precondition violation or deleting contracted behavior, use bin/fail — do not reinterpret an uncontracted *Error span as a test requirement.\n"
            f"================================================================================\n"
        )

    # Contract: MUST pair each discovered implementation source file with its companion test file.
    def get_available_targets(
        self, repo_root: Path | str
    ) -> Dict[str, Tuple[Path, Path]]:
        """Scans repository part packages for implementation files and companion test suites."""
        root = Path(repo_root)
        mapping: Dict[str, Tuple[Path, Path]] = {}
        parts_dirs = [root / "parts"]
        parts_dirs.extend(sorted(root.glob("*/parts")))
        for parts_dir in parts_dirs:
            if not parts_dir.is_dir():
                continue
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

    # Contract: MUST exclude docstring expression lines, function/class signature continuation lines, and pragma exclusion annotations with statement bodies.
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

        # Legitimate reflection: match_case is only present on ast in Python 3.10+
        block_types = (ast.stmt, ast.ExceptHandler, getattr(ast, "match_case", ()))
        for node in ast.walk(tree):
            if not isinstance(node, block_types):
                continue
            # Legitimate reflection: heterogeneous AST nodes lack uniform line and span attribute schemas
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

        def _is_error_stmt(stmt: ast.stmt) -> bool:
            if isinstance(stmt, ast.Raise):
                exc = stmt.exc
                if isinstance(exc, ast.Call):
                    fn = exc.func
                    name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
                    return name.endswith("Error") or name == "unreachable"
                elif isinstance(exc, (ast.Name, ast.Attribute)):
                    name = exc.id if isinstance(exc, ast.Name) else exc.attr
                    return name.endswith("Error")
            elif isinstance(stmt, ast.Assign):
                return True
            return False

        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and _is_error_stmt(node):
                start = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", start)
                if start is not None:
                    for ln in range(start, (end or start) + 1):
                        non_exec.add(ln)
            elif isinstance(node, ast.If) and not node.orelse and node.body and all(_is_error_stmt(s) for s in node.body):
                start = getattr(node.body[0], "lineno", None)
                end = getattr(node.body[-1], "end_lineno", start)
                if start is not None:
                    for ln in range(start, (end or start) + 1):
                        non_exec.add(ln)

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
                end = node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno is not None else node.lineno
                for ln in range(start, end + 1):
                    non_exec.add(ln)
        return non_exec

    # Contract: Extract candidate executable lines; determine covered statements by running unit test suite using unified pytest runner under coverage tracking; report missed statements, missing ranges, and missing spans; set test_passed=False on errors.
    def measure_single_target_coverage(
        self, impl_path: Path | str, test_path: Path | str
    ) -> coverage.ModuleCoverage:
        """Executes single target test suite under coverage tracking and calculates metrics."""
        ipath = Path(impl_path).resolve()
        tpath = Path(test_path).resolve()
        abs_impl = str(ipath)

        raw_exec: Set[int] = set()
        trace_mod: Any = trace
        if hasattr(trace_mod, "_find_executable_linenos"):
            exec_dict = trace_mod._find_executable_linenos(abs_impl)
            if isinstance(exec_dict, dict):
                raw_exec = {ln for ln in exec_dict.keys() if isinstance(ln, int) and ln > 0}
        non_exec = self.get_non_executable_lines(ipath)
        exec_lines = raw_exec - non_exec

        # Resolve workspace / root directory from test/impl path ancestors
        ws_root: Optional[Path] = None
        curr: Optional[Path] = tpath.parent
        while curr and curr != curr.parent:
            if any(
                (curr / marker).exists()
                for marker in (
                    "pyproject.toml",
                    "autofab.toml",
                    "cleanroom.toml",
                    ".role_descriptor.json",
                )
            ) or (curr / "parts").is_dir():
                ws_root = curr
                break
            curr = curr.parent
        if ws_root is None:
            ws_root = tpath.parent

        # Discover package/parts containers to construct canonical PYTHONPATH
        extra_dirs: List[Path] = [tpath.parent]
        is_cleanroom_part = False
        curr_p: Optional[Path] = ipath.parent
        while curr_p and curr_p != curr_p.parent:
            if curr_p.name == "parts":
                extra_dirs.append(curr_p)
                extra_dirs.append(curr_p.parent)
                is_cleanroom_part = True
                break
            curr_p = curr_p.parent

        if not is_cleanroom_part:
            extra_dirs.append(ipath.parent)

        env = dict(os.environ)
        env["BUILD_WORKSPACE_DIRECTORY"] = str(ws_root)
        try:
            from support.lib import app_info
        except Exception:
            import app_info  # type: ignore

        if hasattr(app_info, "assemble_pythonpath_str"):
            env["PYTHONPATH"] = app_info.assemble_pythonpath_str(
                repo_root=str(ws_root),
                ws_root=str(ws_root),
                extra_paths=[str(d) for d in extra_dirs],
                existing_pythonpath=env.get("PYTHONPATH"),
            )
        else:
            pypaths: List[str] = [str(ws_root)]
            pypaths.extend(str(d) for d in extra_dirs)
            if "PYTHONPATH" in env:
                pypaths.extend(
                    p for p in env["PYTHONPATH"].split(os.pathsep) if p and p not in pypaths
                )
            env["PYTHONPATH"] = os.pathsep.join(pypaths)

        env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")

        with tempfile.NamedTemporaryFile(suffix=".coverage", delete=False) as tmp_cov:
            cov_data_file = tmp_cov.name

        include_arg = f"{abs_impl},{Path(impl_path)}" if str(impl_path) != abs_impl else abs_impl
        cmd = [
            sys.executable,
            "-m",
            "coverage",
            "run",
            f"--data-file={cov_data_file}",
            f"--include={include_arg}",
            "-m",
            "pytest",
            str(tpath),
            "-q",
            "--timeout=10",
            "--timeout-method=thread",
        ]

        test_passed = True
        test_error: Optional[str] = None
        ran_subprocess = False

        cmd_timeout = getattr(app_info, "get_verify_timeout", lambda: 60.0)()
        try:
            res = subprocess.run(
                cmd,
                cwd=str(ws_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=cmd_timeout,
            )
            # If pytest failed because pytest-timeout option wasn't recognized, retry without it
            if res.returncode != 0 and (
                "unrecognized arguments: --timeout" in res.stderr
                or "unrecognized arguments: --timeout" in res.stdout
            ):
                cmd_fallback = [
                    sys.executable,
                    "-m",
                    "coverage",
                    "run",
                    f"--data-file={cov_data_file}",
                    f"--include={include_arg}",
                    "-m",
                    "pytest",
                    str(tpath),
                    "-q",
                ]
                res = subprocess.run(
                    cmd_fallback,
                    cwd=str(ws_root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=cmd_timeout,
                )

            ran_subprocess = True
            if res.returncode != 0:
                test_passed = False
                out_str = res.stdout.strip()
                err_str = res.stderr.strip()
                test_error = f"{out_str}\n{err_str}".strip() or "Test suite execution failed."
        except subprocess.TimeoutExpired:
            ran_subprocess = True
            test_passed = False
            test_error = f"Test suite execution timed out after {cmd_timeout:.1f} seconds."
        except (OSError, PermissionError):
            ran_subprocess = False

        covered_lines: Set[int] = set()

        if ran_subprocess:
            if os.path.exists(cov_data_file):
                try:
                    import coverage as cov_lib

                    c_data = cov_lib.Coverage(data_file=cov_data_file)
                    c_data.load()
                    cov_data = c_data.get_data()
                    lines = cov_data.lines(abs_impl) or cov_data.lines(str(Path(impl_path)))
                    if not lines:
                        for mf in cov_data.measured_files():
                            if os.path.realpath(mf) == abs_impl or Path(mf).name == ipath.name:
                                lines = cov_data.lines(mf)
                                if lines:
                                    break
                    if lines:
                        covered_lines = {ln for ln in lines if ln in exec_lines}
                except Exception:
                    pass
                finally:
                    try:
                        os.remove(cov_data_file)
                    except OSError:
                        pass
        else:
            try:
                os.remove(cov_data_file)
            except OSError:
                pass

            module_base = ipath.stem
            test_mod_name = tpath.stem

            for m in list(sys.modules.keys()):
                if (
                    m == module_base
                    or m.endswith(f".{module_base}")
                    or m == tpath.stem
                    or m.endswith(f".{tpath.stem}")
                    or m == "lib"
                    or m.startswith("lib.")
                    or m == "tests"
                    or m.startswith("tests.")
                    or m == "parts"
                    or m.startswith("parts.")
                ):
                    del sys.modules[m]

            tracer = trace.Trace(count=1, trace=0)
            test_load_error: Optional[str] = None
            test_failures_str: Optional[str] = None

            def run_suite() -> None:
                nonlocal test_load_error, test_failures_str, test_passed
                loader = unittest.TestLoader()
                try:
                    suite = loader.loadTestsFromName(test_mod_name)
                except (ImportError, AttributeError, SyntaxError, TypeError, ValueError, NameError) as e:
                    test_load_error = str(e)
                    test_passed = False
                    return

                if suite.countTestCases() == 0:
                    mod = sys.modules.get(test_mod_name)
                    if mod:
                        for attr_name in sorted(dir(mod)):
                            if attr_name.startswith("test_") and callable(getattr(mod, attr_name)):
                                fn = getattr(mod, attr_name)
                                suite.addTest(unittest.FunctionTestCase(fn))

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
                    test_failures_str = "\n".join(fail_lines)

            orig_sys_path = list(sys.path)
            try:
                for p in reversed([str(d) for d in extra_dirs]):
                    while p in sys.path:
                        sys.path.remove(p)
                    sys.path.insert(0, p)
                tracer.runfunc(run_suite)
            finally:
                sys.path[:] = orig_sys_path

            if not test_passed:
                test_error = (
                    test_load_error or test_failures_str or "Test suite execution failed."
                )

            results = tracer.results()
            for (fn, ln), _ in results.counts.items():
                if (
                    os.path.abspath(fn) == abs_impl or Path(fn).name == ipath.name
                ) and ln in exec_lines:
                    covered_lines.add(ln)

        missed_lines = sorted(list(exec_lines - covered_lines))
        total_exec = len(exec_lines)
        cov_pct = (len(covered_lines) / total_exec * 100) if total_exec else 100.0
        spans = self.group_into_spans(missed_lines)

        return coverage.ModuleCoverage(
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
            test_passed=test_passed,
            test_error=test_error,
        )

    # Contract: Resolve target if test_path omitted; evaluate coverage pct against threshold; write formatted report to update_log when specified.
    def evaluate_coverage(
        self,
        target_or_impl: str,
        test_path: Optional[Path | str] = None,
        repo_root: Optional[Path | str] = None,
        threshold: float = 0.0,
        update_log: Optional[Path | str] = None,
        max_spans: Optional[int] = None,
    ) -> coverage.ModuleCoverage:
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

        # Persist workspace coverage status buffer
        try:
            span_classifications = []
            has_test_spans = False
            has_lib_pragma = False
            for start, end in cov.missing_spans:
                owner, disp = self.classify_span(cov.file_path, start, end)
                span_classifications.append({
                    "span": [start, end],
                    "owner": owner,
                    "disposition": disp,
                })
                if owner == "test":
                    has_test_spans = True
                elif owner == "lib":
                    has_lib_pragma = True

            all_lib_pragma = bool(cov.missing_spans and not has_test_spans and has_lib_pragma)
            status_data = {
                "module_name": cov.module_name,
                "test_name": cov.test_name,
                "file_path": cov.file_path,
                "test_path": cov.test_path,
                "missing_spans": cov.missing_spans,
                "missing_lines": cov.missing_lines,
                "coverage_pct": cov.coverage_pct,
                "test_passed": cov.test_passed,
                "span_classifications": span_classifications,
                "all_lib_pragma_required": all_lib_pragma,
                "has_test_owned_spans": has_test_spans,
            }
            status_file = root / ".coverage_spans.json"
            with open(status_file, "w", encoding="utf-8") as sf:
                json.dump(status_data, sf, indent=2)
        except Exception:
            pass

        if update_log:
            log_p = Path(update_log)
            if not log_p.is_absolute():
                log_p = root / log_p
            log_p.parent.mkdir(parents=True, exist_ok=True)
            report = self.format_coverage_report(
                cov, threshold, max_spans=max_spans
            )
            with open(log_p, "w", encoding="utf-8") as f:
                f.write(report)

        return cov
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-11-03T23:45:00Z
# CHANGE: Instruct coverage auditor when uncovered spans persist to examine library implementation for unreachable code
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        CoverageEvaluator,
        keys=[CoverageEvaluator, coverage.CoverageEvaluator],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
