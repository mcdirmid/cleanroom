#!/usr/bin/env python3
"""Evaluate test coverage of a single Cleanroom _impl.py library module.

Measures statement and line coverage for a single *_impl.py file in
update_with_ai/lib/ when exercised by its corresponding *_impl_test.py
test suite in update_with_ai/tests/.

Evaluates one test at a time, strictly excluding lifecycle.py and non-implementation
modules. Formats uncovered lines into contiguous spans without throttling (or clamped
if specified). Updates coverage logs with structured guidance for agents.
"""

import argparse
import ast
import contextlib
import io
import json
import os
import sys
import trace
import unittest
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class ModuleCoverage:
    module_name: str
    test_name: str
    file_path: str
    test_path: str
    total_executable: int
    covered: int
    missed: int
    coverage_pct: float
    missing_lines: List[int]
    missing_ranges: str
    missing_spans: List[Tuple[int, int]]
    test_passed: bool = True
    test_error: Optional[str] = None


def find_repo_root() -> Path:
    """Find the root workspace directory containing update_with_ai."""
    # Bazel run sets BUILD_WORKSPACE_DIRECTORY
    if "BUILD_WORKSPACE_DIRECTORY" in os.environ:
        p = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
        if (p / "update_with_ai").is_dir():
            return p

    current = Path(__file__).resolve().parent
    for p in [
        current,
        current.parent,
        current.parent.parent,
        current.parent.parent.parent,
    ]:
        if (p / "update_with_ai").is_dir():
            return p

    cwd = Path.cwd()
    if (cwd / "update_with_ai").is_dir():
        return cwd
    if cwd.name == "update_with_ai":
        return cwd.parent

    for p in [current] + list(current.parents):
        if (p / "WORKSPACE").exists() or (p / "MODULE.bazel").exists():
            return p

    raise RuntimeError("Could not locate repository root containing update_with_ai.")


def get_available_targets(repo_root: Path) -> Dict[str, Tuple[Path, Path]]:
    """Return a mapping of normalized target names to (impl_path, test_path)."""
    mapping: Dict[str, Tuple[Path, Path]] = {}
    parts_dir = repo_root / "update_with_ai" / "parts"
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


def get_non_executable_lines(file_path: Path) -> Set[int]:
    """Identify lines in AST that are not executable statements.

    Filters out function/class definition signature continuation lines,
    type annotation continuation lines, docstrings, and lines marked
    with '# pragma: no cover' or '# no cover'.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src, str(file_path))

    non_exec: Set[int] = set()

    # Lines marked with pragma comments
    lines = src.splitlines()
    pragma_lines: Set[int] = set()
    for idx, line in enumerate(lines, 1):
        if "# pragma: no cover" in line or "# no cover" in line:
            pragma_lines.add(idx)

    # Exclude pragma lines and entire statement blocks starting on them
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and node.lineno in pragma_lines:
            start = node.lineno
            end = getattr(node, "end_lineno", node.lineno)
            for l in range(start, end + 1):
                non_exec.add(l)

    non_exec.update(pragma_lines)

    for node in ast.walk(tree):
        # Class or Function definition: signature continuation lines between def and first body statement
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.body:
                first_body = node.body[0]
                for l in range(node.lineno + 1, first_body.lineno):
                    non_exec.add(l)
        # Docstrings at any level
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            start = node.lineno
            end = getattr(node, "end_lineno", node.lineno)
            for l in range(start, end + 1):
                non_exec.add(l)
    return non_exec


def format_ranges(lines: List[int]) -> str:
    """Format a list of sorted integers into compact comma-separated ranges."""
    if not lines:
        return ""
    ranges: List[str] = []
    start = lines[0]
    end = lines[0]
    for n in lines[1:]:
        if n == end + 1:
            end = n
        else:
            ranges.append(f"{start}" if start == end else f"{start}-{end}")
            start = end = n
    ranges.append(f"{start}" if start == end else f"{start}-{end}")
    return ", ".join(ranges)


def group_into_spans(lines: List[int]) -> List[Tuple[int, int]]:
    """Group sorted integer line numbers into contiguous (start, end) span tuples."""
    if not lines:
        return []
    spans: List[Tuple[int, int]] = []
    start = lines[0]
    end = lines[0]
    for n in lines[1:]:
        if n == end + 1:
            end = n
        else:
            spans.append((start, end))
            start = end = n
    spans.append((start, end))
    return spans


def normalize_target_query(raw_query: str) -> str:
    """Normalize input query string by removing Bazel target or path prefixes."""
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


def measure_single_target_coverage(impl_path: Path, test_path: Path) -> ModuleCoverage:
    """Run the unit test for a single _impl module and evaluate coverage."""
    raw_exec = {
        ln
        for ln in trace._find_executable_linenos(str(impl_path)).keys()  # type: ignore[attr-defined]
        if isinstance(ln, int) and ln > 0
    }
    non_exec = get_non_executable_lines(impl_path)
    exec_lines = raw_exec - non_exec

    module_base = impl_path.stem
    lib_mod_name = f"lib.{module_base}"
    test_mod_name = f"tests.{test_path.stem}"

    # Clean sys.modules of target and test to ensure clean import under tracer
    for m in list(sys.modules.keys()):
        if m.startswith(lib_mod_name) or m.startswith(test_mod_name):
            del sys.modules[m]

    # Ensure 'lib' and 'tests' packages in sys.modules point to target directories
    import types

    if "lib" not in sys.modules or not getattr(sys.modules["lib"], "__path__", None):
        lib_pkg = types.ModuleType("lib")
        lib_pkg.__path__ = [str(impl_path.parent)]
        sys.modules["lib"] = lib_pkg
    else:
        lib_dir_str = str(impl_path.parent)
        if lib_dir_str not in sys.modules["lib"].__path__:
            sys.modules["lib"].__path__.insert(0, lib_dir_str)

    if "tests" not in sys.modules or not getattr(
        sys.modules["tests"], "__path__", None
    ):
        tests_pkg = types.ModuleType("tests")
        tests_pkg.__path__ = [str(test_path.parent)]
        sys.modules["tests"] = tests_pkg
    else:
        test_dir_str = str(test_path.parent)
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
        except Exception as e:
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
            for test_case, err_trace in res.errors:
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

    tracer.runfunc(run_suite)

    if not test_passed:
        err_msg = test_load_error or test_failures_str or "Test suite execution failed."
        return ModuleCoverage(
            module_name=impl_path.name,
            test_name=test_path.name,
            file_path=str(impl_path),
            test_path=str(test_path),
            total_executable=len(exec_lines),
            covered=0,
            missed=len(exec_lines),
            coverage_pct=0.0,
            missing_lines=sorted(list(exec_lines)),
            missing_ranges=format_ranges(sorted(list(exec_lines))),
            missing_spans=group_into_spans(sorted(list(exec_lines))),
            test_passed=False,
            test_error=err_msg,
        )

    results = tracer.results()

    abs_impl = str(impl_path.resolve())
    covered_lines: Set[int] = set()
    for (fn, ln), _ in results.counts.items():
        if (
            os.path.abspath(fn) == abs_impl or Path(fn).name == impl_path.name
        ) and ln in exec_lines:
            covered_lines.add(ln)

    missed_lines = sorted(list(exec_lines - covered_lines))
    total_exec = len(exec_lines)
    cov_pct = (len(covered_lines) / total_exec * 100) if total_exec else 100.0
    spans = group_into_spans(missed_lines)

    return ModuleCoverage(
        module_name=impl_path.name,
        test_name=test_path.name,
        file_path=str(impl_path),
        test_path=str(test_path),
        total_executable=total_exec,
        covered=len(covered_lines),
        missed=len(missed_lines),
        coverage_pct=cov_pct,
        missing_lines=missed_lines,
        missing_ranges=format_ranges(missed_lines),
        missing_spans=spans,
        test_passed=True,
    )


def format_spans_report(cov: ModuleCoverage, max_spans: Optional[int] = None) -> str:
    """Format uncovered spans clamping presentation to at most max_spans if specified."""
    if not cov.missing_spans:
        return "All statements covered."
    with open(cov.file_path, "r", encoding="utf-8") as f:
        src_lines = f.readlines()

    shown_spans = cov.missing_spans[:max_spans] if max_spans is not None else cov.missing_spans
    lines: List[str] = []
    lines.append(f"Uncovered statement spans in {cov.module_name}:")
    for idx, (start, end) in enumerate(shown_spans, 1):
        span_label = f"line {start}" if start == end else f"lines {start}-{end}"
        lines.append(f"\n  Span {idx} ({span_label}):")
        for ln in range(start, end + 1):
            if ln in cov.missing_lines:
                text = (
                    src_lines[ln - 1].rstrip("\r\n") if 0 < ln <= len(src_lines) else ""
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
    cov: ModuleCoverage, threshold: float, max_spans: Optional[int] = None
) -> str:
    """Format full structured report suitable for console and log file."""
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

    spans_detail = format_spans_report(cov, max_spans=max_spans)
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate test coverage of a single Cleanroom _impl.py library module."
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="The single test or implementation target to evaluate (e.g. dag_cleaner, agent_runner_impl_test).",
    )
    parser.add_argument(
        "--impl",
        help="Path to implementation file (e.g. update_with_ai/lib/foo_impl.py)",
    )
    parser.add_argument(
        "--test",
        help="Path to test file (e.g. update_with_ai/tests/foo_impl_test.py)",
    )
    parser.add_argument(
        "--update-log",
        help="Path to coverage log file to update (e.g. update_with_ai/logs/foo_impl_coverage.log)",
    )
    parser.add_argument(
        "--no-snippets",
        action="store_true",
        help="Suppress printing source snippets for missed lines.",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.0,
        help="Minimum coverage percentage required to exit successfully (e.g. 100.0).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output coverage metrics in JSON format.",
    )
    parser.add_argument(
        "--max-spans",
        type=int,
        default=None,
        help="Maximum non-continuous spans to present (default: unlimited).",
    )

    args = parser.parse_args()

    repo_root = find_repo_root()

    # Configure sys.path so update_python_with_ai and update_with_ai are resolvable
    for p in [
        repo_root,
        repo_root / "update_with_ai",
        repo_root / "update_python_with_ai",
    ]:
        ps = str(p)
        if ps not in sys.path:
            sys.path.insert(0, ps)

    support_dir = str((repo_root / "update_python_with_ai" / "support").resolve())
    if "support" in sys.modules and getattr(sys.modules["support"], "__path__", None):
        if support_dir not in sys.modules["support"].__path__:
            sys.modules["support"].__path__.append(support_dir)

    if args.impl and args.test:
        impl_path = Path(args.impl)
        if not impl_path.is_absolute():
            impl_path = (repo_root / impl_path).resolve()
        test_path = Path(args.test)
        if not test_path.is_absolute():
            test_path = (repo_root / test_path).resolve()
        if not impl_path.is_file():
            print(f"Error: Implementation file not found: {impl_path}", file=sys.stderr)
            return 1
        if not test_path.is_file():
            print(f"Error: Test file not found: {test_path}", file=sys.stderr)
            return 1
    elif args.target:
        target_map = get_available_targets(repo_root)
        distinct_targets = sorted(
            list(
                {impl.stem: (impl, test) for impl, test in target_map.values()}.items()
            )
        )
        query = normalize_target_query(args.target)
        if query not in target_map:
            print(f"Error: Unrecognized target '{args.target}'.\n", file=sys.stderr)
            print(f"Available targets ({len(distinct_targets)}):", file=sys.stderr)
            for idx, (stem, (impl, test)) in enumerate(distinct_targets, 1):
                print(f"  {idx:2d}. {test.stem:<42} -> {impl.name}", file=sys.stderr)
            return 1
        impl_path, test_path = target_map[query]
    else:
        target_map = get_available_targets(repo_root)
        distinct_targets = sorted(
            list(
                {impl.stem: (impl, test) for impl, test in target_map.values()}.items()
            )
        )
        print(
            "Error: Please specify --impl and --test, or target name.\n",
            file=sys.stderr,
        )
        print(
            "Usage: evaluate_coverage --impl <path> --test <path> [--update-log <path>] [--threshold 100.0]\n",
            file=sys.stderr,
        )
        print(f"Available targets ({len(distinct_targets)}):", file=sys.stderr)
        for idx, (stem, (impl, test)) in enumerate(distinct_targets, 1):
            print(f"  {idx:2d}. {test.stem:<42} -> {impl.name}", file=sys.stderr)
        return 1

    cov = measure_single_target_coverage(impl_path, test_path)

    if args.json_output:
        print(json.dumps(asdict(cov), indent=2))
        return 0 if (cov.test_passed and cov.coverage_pct >= args.threshold) else 1

    report = format_coverage_report(cov, args.threshold, max_spans=args.max_spans)

    if args.update_log:
        log_path = Path(args.update_log)
        if not log_path.is_absolute():
            log_path = repo_root / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if cov.test_passed and cov.missed == 0:
            with open(log_path, "w", encoding="utf-8") as f:
                pass
        else:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(report)

    print(report)

    if not cov.test_passed:
        return 1

    if cov.coverage_pct < args.threshold:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
