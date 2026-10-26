#!/usr/bin/env python3
"""run_cross_tests.py - Differential Cross-Testing Runner for Cleanroom Benchmarks

Executes pairwise cross-evaluation of synthesized libraries against independent and
baseline test suites to identify Soundness Gaps, Coupling Gaps, and Contract Ambiguities.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_bundled_file(archive_file: Path) -> Dict[str, str]:
    """Splits bundled lib_N.py or test_N.py files based on '# === File: <name> ==='."""
    content = archive_file.read_text(encoding="utf-8")
    files: Dict[str, str] = {}
    current_file: Optional[str] = None
    current_lines: List[str] = []

    for line in content.splitlines(keepends=True):
        match = re.match(r"^# === File:\s+([^\s]+)\s+===", line)
        if match:
            if current_file:
                files[current_file] = "".join(current_lines)
            current_file = match.group(1)
            current_lines = []
        elif current_file:
            current_lines.append(line)

    if current_file:
        files[current_file] = "".join(current_lines)

    # Fallback if no delimiter was present
    if not files:
        files[archive_file.name] = content

    return files


def run_cross_test(
    lib_dir: Path,
    test_dir: Path,
    suite_name: str,
    label: str,
    eval_base: Path,
) -> Tuple[int, int, str]:
    """Runs test suite from test_dir against library implementation from lib_dir."""
    sandbox = eval_base / label.replace("+", "_").replace("/", "_")
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True, exist_ok=True)

    # 1. Unpack library files
    lib_files = parse_bundled_file(lib_dir / "lib_1.py")
    target_lib_dir = sandbox / "benchmark_1" / "parts" / suite_name / "lib"
    target_lib_dir.mkdir(parents=True, exist_ok=True)

    for fname, fcontent in lib_files.items():
        # Normalize relative imports to be resilient to package and top-level execution
        normalized = re.sub(
            rf"^from \. import {suite_name}",
            f"try:\n    from . import {suite_name}\nexcept (ImportError, ValueError):\n    import {suite_name}",
            fcontent,
            flags=re.MULTILINE,
        )
        if fname == f"{suite_name}_impl.py" and "__initialize__" not in normalized:
            normalized += f"""

def __initialize__(registry=None) -> None:
    from support.lib.lifecycle import get_default_registry
    reg = get_default_registry() if registry is None else registry
    for attr_name in ("DAG", "WaveScheduler", "DAGRunner"):
        cls = globals().get(attr_name)
        proto = getattr({suite_name}, attr_name, None)
        if cls is not None and proto is not None:
            tier = getattr(cls, "tier", "system")
            reg.register_singleton(cls, keys=[cls, proto], tier=tier)

_initialize_ = __initialize__
"""
        (target_lib_dir / fname).write_text(normalized, encoding="utf-8")

    # Ensure package hierarchy
    (sandbox / "benchmark_1" / "__init__.py").write_text("", encoding="utf-8")
    (sandbox / "benchmark_1" / "parts" / "__init__.py").write_text("", encoding="utf-8")
    (sandbox / "benchmark_1" / "parts" / suite_name / "__init__.py").write_text("", encoding="utf-8")
    (target_lib_dir / "__init__.py").write_text("", encoding="utf-8")

    # 2. Scope Aliasing: Symlink alternate flight scopes (benchmark_2, benchmark_3) to benchmark_1
    for alias in ("benchmark_2", "benchmark_3"):
        alias_path = sandbox / alias
        if not alias_path.exists():
            os.symlink("benchmark_1", alias_path)

    # 3. Unpack test suite
    test_raw = (test_dir / "test_1.py").read_text(encoding="utf-8")
    # Normalize flight scope imports so tests consistently import from benchmark_1
    test_normalized = re.sub(r"benchmark_[23]", "benchmark_1", test_raw)
    target_test_dir = sandbox / "benchmark_1" / "parts" / suite_name / "tests"
    target_test_dir.mkdir(parents=True, exist_ok=True)
    (target_test_dir / "__init__.py").write_text("", encoding="utf-8")

    test_file = target_test_dir / f"{suite_name}_impl_test.py"
    test_file.write_text(test_normalized, encoding="utf-8")

    # 4. Inject pytest conftest in test directory to harmonize sys.modules and singleton registration
    conftest_path = target_test_dir / "conftest.py"
    conftest_content = f"""
import sys
import importlib

# Force identical module identity between unqualified and qualified imports
_pkg_mod = importlib.import_module("benchmark_1.parts.{suite_name}.lib.{suite_name}")
sys.modules["{suite_name}"] = _pkg_mod
sys.modules["benchmark_2.parts.{suite_name}.lib.{suite_name}"] = _pkg_mod
sys.modules["benchmark_3.parts.{suite_name}.lib.{suite_name}"] = _pkg_mod

try:
    _pkg_impl = importlib.import_module("benchmark_1.parts.{suite_name}.lib.{suite_name}_impl")
    sys.modules["{suite_name}_impl"] = _pkg_impl
    sys.modules["benchmark_2.parts.{suite_name}.lib.{suite_name}_impl"] = _pkg_impl
    sys.modules["benchmark_3.parts.{suite_name}.lib.{suite_name}_impl"] = _pkg_impl
except ImportError:
    pass
"""
    conftest_path.write_text(conftest_content, encoding="utf-8")

    # 5. Execute pytest
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        f"{target_lib_dir}:{sandbox}:{REPO_ROOT}:"
        f"{REPO_ROOT / 'update_with_ai'}:{REPO_ROOT / 'update_python_with_ai'}"
    )

    cmd = ["pytest", "-q", "--tb=short", str(test_file)]
    res = subprocess.run(cmd, cwd=sandbox, env=env, capture_output=True, text=True)
    output = res.stdout + "\n" + res.stderr

    passed = 0
    failed = 0
    p_match = re.search(r"(\d+) passed", output)
    if p_match:
        passed = int(p_match.group(1))
    f_match = re.search(r"(\d+) failed", output)
    if f_match:
        failed = int(f_match.group(1))

    return passed, failed, output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Differential Cross-Testing Protocol Runner for Cleanroom Benchmarks."
    )
    parser.add_argument(
        "--suite",
        default="dag_engine_lite",
        help="Benchmark suite identifier (default: dag_engine_lite)",
    )
    parser.add_argument(
        "--results-dir",
        default=str(REPO_ROOT / "benchmarks" / "results"),
        help="Path to archived benchmark results directory",
    )
    parser.add_argument(
        "--eval-base",
        default="/tmp/cross_eval_matrix",
        help="Temporary evaluation directory for test sandboxes",
    )
    parser.add_argument(
        "--target-model",
        default=None,
        help="Optional specific model directory to cross-check against all others",
    )
    args = parser.parse_args()

    results_path = Path(args.results_dir) / args.suite
    if not results_path.is_dir():
        print(f"Error: Results directory not found: {results_path}", file=sys.stderr)
        return 1

    runs: Dict[str, Path] = {}
    for p in sorted(results_path.iterdir()):
        if p.is_dir() and (p / "lib_1.py").exists() and (p / "test_1.py").exists():
            runs[p.name] = p

    print(f"=== Cleanroom Differential Cross-Testing Runner [{args.suite}] ===")
    print(f"Discovered {len(runs)} benchmark runs: {list(runs.keys())}\n")

    eval_base = Path(args.eval_base)
    eval_base.mkdir(parents=True, exist_ok=True)

    # 1. Self-Consistency Gate
    print("=" * 80)
    print("1. SELF-CONSISTENCY GATE (V_self -> P_self)")
    print("=" * 80)
    for name, p in runs.items():
        passed, failed, out = run_cross_test(p, p, args.suite, f"self_{name}", eval_base)
        status = "PASS" if failed == 0 and passed > 0 else "FAIL"
        print(f"  [{status}] {name:42s} -> {passed:2d} passed, {failed:2d} failed")

    # 2. Pairwise Cross-Evaluation
    targets = [args.target_model] if args.target_model and args.target_model in runs else list(runs.keys())

    for target_name in targets:
        target_path = runs[target_name]
        print("\n" + "=" * 80)
        print(f"2. CROSS-EVALUATION: TARGET IMPLEMENTATION [{target_name}]")
        print("=" * 80)
        for test_name, test_path in runs.items():
            if test_name == target_name:
                continue
            passed, failed, out = run_cross_test(target_path, test_path, args.suite, f"{test_name}_on_{target_name}", eval_base)
            status = "PASS" if failed == 0 and passed > 0 else "FAIL"
            print(f"  [{status}] Test: {test_name:38s} on Lib -> {passed:2d} passed, {failed:2d} failed")
            if failed > 0:
                for line in [l for l in out.splitlines() if "FAILED" in l][:3]:
                    print(f"       * {line.strip()}")

    print("\nCross-evaluation completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
