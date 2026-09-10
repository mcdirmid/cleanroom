#!/usr/bin/env python3
"""Evaluate test coverage of a single Cleanroom _impl.py library module.

Measures statement and line coverage for a single *_impl.py file in
update_with_ai/lib/ when exercised by its corresponding *_impl_test.py
test suite in update_with_ai/tests/.

Specifically evaluates only one test at a time, strictly excluding lifecycle.py
and non-implementation modules.

Can be run directly via:
    python3 update_with_ai/tool/evaluate_coverage.py <target>
or via Bazel:
    bazel run //update_with_ai/tool:evaluate_coverage -- <target>
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


def find_repo_root() -> Path:
    """Find the root workspace directory containing update_with_ai."""
    # Bazel run sets BUILD_WORKSPACE_DIRECTORY
    if "BUILD_WORKSPACE_DIRECTORY" in os.environ:
        p = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
        if (p / "update_with_ai" / "lib").is_dir():
            return p

    current = Path(__file__).resolve().parent
    for p in [current, current.parent, current.parent.parent, current.parent.parent.parent]:
        if (p / "update_with_ai" / "lib").is_dir():
            return p

    cwd = Path.cwd()
    if (cwd / "update_with_ai" / "lib").is_dir():
        return cwd
    if (cwd / "lib").is_dir() and cwd.name == "update_with_ai":
        return cwd.parent

    raise RuntimeError("Could not locate repository root containing update_with_ai/lib.")


def get_available_targets(lib_dir: Path, tests_dir: Path) -> Dict[str, Tuple[Path, Path]]:
    """Return a mapping of normalized target names to (impl_path, test_path)."""
    mapping: Dict[str, Tuple[Path, Path]] = {}
    impl_files = sorted(
        [f for f in lib_dir.iterdir() if f.is_file() and f.name.endswith("_impl.py")]
    )
    for impl_path in impl_files:
        test_file = tests_dir / f"{impl_path.stem}_test.py"
        if test_file.is_file():
            base_name = impl_path.stem[:-5] if impl_path.stem.endswith("_impl") else impl_path.stem
            # Register aliases for easy command line lookup
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
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
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


def measure_single_target_coverage(
    impl_path: Path, test_path: Path
) -> ModuleCoverage:
    """Run the unit test for a single _impl module and evaluate coverage."""
    raw_exec = {
        ln
        for ln in trace._find_executable_linenos(str(impl_path)).keys()  # type: ignore[attr-defined]
        if isinstance(ln, int) and ln > 0
    }
    non_exec = get_non_executable_lines(impl_path)
    exec_lines = raw_exec - non_exec

    module_base = impl_path.stem  # e.g. dag_cleaner_impl
    lib_mod_name = f"lib.{module_base}"
    test_mod_name = f"tests.{module_base}_test"

    # Clean sys.modules of target and test to ensure clean import under tracer
    for m in list(sys.modules.keys()):
        if m.startswith(lib_mod_name) or m.startswith(test_mod_name):
            del sys.modules[m]

    # Ensure 'lib' package in sys.modules points to update_with_ai/lib
    import types
    if "lib" not in sys.modules or not getattr(sys.modules["lib"], "__path__", None):
        lib_pkg = types.ModuleType("lib")
        lib_pkg.__path__ = [str(impl_path.parent)]
        sys.modules["lib"] = lib_pkg
    else:
        lib_dir_str = str(impl_path.parent)
        if lib_dir_str not in sys.modules["lib"].__path__:
            sys.modules["lib"].__path__.insert(0, lib_dir_str)

    tracer = trace.Trace(count=1, trace=0)

    test_load_error: Optional[str] = None

    def run_suite() -> None:
        nonlocal test_load_error
        import contextlib
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(test_mod_name)
        runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            res = runner.run(suite)
        if res.errors:
            # Check for module load failures
            for test_case, err_trace in res.errors:
                if "Failed to import test module" in err_trace:
                    test_load_error = err_trace
                    return

    tracer.runfunc(run_suite)
    if test_load_error:
        print(f"Error loading test suite '{test_mod_name}':\n{test_load_error}", file=sys.stderr)
        sys.exit(1)

    results = tracer.results()

    abs_impl = str(impl_path.resolve())
    covered_lines: Set[int] = set()
    for (fn, ln), _ in results.counts.items():
        # Match either exact path or basename to handle Bazel runfiles symlinks
        if (os.path.abspath(fn) == abs_impl or Path(fn).name == impl_path.name) and ln in exec_lines:
            covered_lines.add(ln)

    missed_lines = sorted(list(exec_lines - covered_lines))
    total_exec = len(exec_lines)
    cov_pct = (len(covered_lines) / total_exec * 100) if total_exec else 100.0

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
    )


def print_detail(coverage: ModuleCoverage) -> None:
    """Print source code snippets for missing lines."""
    if not coverage.missing_lines:
        return
    with open(coverage.file_path, "r", encoding="utf-8") as f:
        src_lines = f.readlines()

    print(f"\nUncovered lines in {coverage.module_name}:")
    for ln in coverage.missing_lines:
        idx = ln - 1
        if 0 <= idx < len(src_lines):
            line_text = src_lines[idx].rstrip("\r\n")
            print(f"  Line {ln:4d}: {line_text}")


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
        "--no-snippets",
        action="store_true",
        help="Suppress printing source snippets for missed lines.",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.0,
        help="Minimum coverage percentage required to exit successfully (e.g. 90.0).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output coverage metrics in JSON format.",
    )

    args = parser.parse_args()

    repo_root = find_repo_root()
    lib_dir = repo_root / "update_with_ai" / "lib"
    tests_dir = repo_root / "update_with_ai" / "tests"

    # Configure sys.path and explicitly bind 'lib' and 'tests' packages
    update_with_ai_dir = str(repo_root / "update_with_ai")
    if update_with_ai_dir not in sys.path:
        sys.path.insert(0, update_with_ai_dir)

    import types
    lib_pkg = types.ModuleType("lib")
    lib_pkg.__path__ = [str(lib_dir)]
    sys.modules["lib"] = lib_pkg

    tests_pkg = types.ModuleType("tests")
    tests_pkg.__path__ = [str(tests_dir)]
    sys.modules["tests"] = tests_pkg

    target_map = get_available_targets(lib_dir, tests_dir)
    distinct_targets = sorted(
        list({impl.stem: (impl, test) for impl, test in target_map.values()}.items())
    )

    if not args.target:
        print("Error: Please specify exactly one test or implementation target.\n", file=sys.stderr)
        print("Usage: evaluate_coverage <target_test_or_module> [options]\n", file=sys.stderr)
        print(f"Available targets ({len(distinct_targets)}):", file=sys.stderr)
        for idx, (stem, (impl, test)) in enumerate(distinct_targets, 1):
            print(f"  {idx:2d}. {test.stem:<42} -> {impl.name}", file=sys.stderr)
        return 1

    query = normalize_target_query(args.target)
    if query not in target_map:
        print(f"Error: Unrecognized target '{args.target}'.\n", file=sys.stderr)
        print(f"Available targets ({len(distinct_targets)}):", file=sys.stderr)
        for idx, (stem, (impl, test)) in enumerate(distinct_targets, 1):
            print(f"  {idx:2d}. {test.stem:<42} -> {impl.name}", file=sys.stderr)
        return 1

    impl_path, test_path = target_map[query]
    cov = measure_single_target_coverage(impl_path, test_path)

    if args.json_output:
        print(json.dumps(asdict(cov), indent=2))
        return 0 if cov.coverage_pct >= args.threshold else 2

    print(f"\nEvaluating single test coverage: {cov.test_name} -> {cov.module_name}")
    print("=" * 85)
    print(f"Test Suite:      update_with_ai/tests/{cov.test_name}")
    print(f"Implementation:  update_with_ai/lib/{cov.module_name}")
    print("-" * 85)
    print(
        f"Total Statements: {cov.total_executable:<5} | "
        f"Covered: {cov.covered:<5} | "
        f"Missed: {cov.missed:<5} | "
        f"Coverage: {cov.coverage_pct:.1f}%"
    )
    print("-" * 85)

    if cov.missed == 0:
        print("✓ 100.0% coverage - all statements executed by test suite.")
    else:
        print(f"Missed lines: {cov.missing_ranges}")
        if not args.no_snippets:
            print_detail(cov)

    print("=" * 85)

    if cov.coverage_pct < args.threshold:
        print(
            f"\nCoverage check FAILED: {cov.coverage_pct:.1f}% is below threshold {args.threshold:.1f}%",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
