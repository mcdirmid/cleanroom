#!/usr/bin/env python3
"""run_cross_tests.py - Differential Cross-Testing Runner for Cleanroom Benchmarks

Executes pairwise cross-evaluation of synthesized libraries against independent and
baseline test suites to identify Soundness Gaps, Coupling Gaps, and Contract Ambiguities.
Produces structured cross-soundness matrices, strictness rankings, and defect root-cause analyses.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class FailureDetail:
    """Structured details of an individual failing test in a cross-test run."""

    test_name: str
    error_type: str
    message: str
    category: str  # [SOUNDNESS GAP], [COUPLING GAP], [API MISMATCH], [TYPE ERROR], [ERROR]
    file_line: str = ""
    snippet: str = ""


@dataclass
class CrossTestResult:
    """Structured outcome of running a test suite against a library implementation."""

    target_lib: str
    test_suite: str
    passed: int
    failed: int
    output: str
    failures: List[FailureDetail] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.passed + self.failed

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100.0) if self.total > 0 else 0.0

    @property
    def is_pass(self) -> bool:
        return self.failed == 0 and self.passed > 0

    def __iter__(self):
        """Maintains backward compatibility with (passed, failed, output) tuple unpacking."""
        return iter((self.passed, self.failed, self.output))


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


def classify_error_detail(err_type: str, message: str, body: str) -> str:
    """Classifies individual error details into precise Cleanroom failure taxonomies."""
    full = f"{err_type}: {message}\n{body}"
    if re.search(r"(?:ImportError|AttributeError):.*(?:cannot import name|has no attribute) '_", full):
        return "[COUPLING GAP]"
    if "AssertionError" in err_type or "assert" in message:
        return "[SOUNDNESS GAP]"
    if "AttributeError" in err_type or "ImportError" in err_type:
        return "[API MISMATCH]"
    if "TypeError" in err_type:
        return "[TYPE ERROR]"
    return "[ERROR]"


def classify_failure(output: str) -> str:
    """Classifies overall test run failures into Coupling Gap, Soundness Gap, or Runtime Error."""
    if re.search(r"(?:ImportError|AttributeError):.*(?:cannot import name|has no attribute) '_", output):
        return "[COUPLING GAP]"
    if "AssertionError" in output or re.search(r"\bassert\b", output):
        return "[SOUNDNESS GAP]"
    return "[ERROR]"


def abbreviate_run_name(name: str) -> str:
    """Produces compact column headers for wide differential cross-testing tables."""
    s = name
    s = re.sub(r"gemini[-_]?3\.8[-_]?flash", "Gemini-Flash", s, flags=re.I)
    s = re.sub(r"gemini[-_]?flash", "Gemini-Flash", s, flags=re.I)
    s = re.sub(r"deepseek[-_]?flash", "DeepSeek-Flash", s, flags=re.I)
    s = re.sub(r"deepseek[-_]?v3", "DeepSeek-V3", s, flags=re.I)
    s = re.sub(r"qwen[-_]?moe", "Qwen-MoE", s, flags=re.I)
    s = re.sub(r"qwen[-_]?3\.6", "Qwen", s, flags=re.I)
    s = re.sub(r"[+_](?:antigravity|dsh)[-_]pretense[-_]baseline", " Base", s, flags=re.I)
    s = re.sub(r"[+_](?:antigravity|dsh)[-_]pretense", " Clean", s, flags=re.I)
    s = re.sub(r"[+_]baseline", " Base", s, flags=re.I)
    return s


def parse_failures(output: str) -> List[FailureDetail]:
    """Parses pytest stdout to extract structured FailureDetail objects."""
    failures: List[FailureDetail] = []
    failures_section = re.search(
        r"=+\s*(?:FAILURES|ERRORS)\s*=+\n(.*?)(?:=+\s*short test summary info\s*=+|\Z)",
        output,
        re.DOTALL,
    )
    if not failures_section:
        for line in output.splitlines():
            if line.startswith("FAILED ") or line.startswith("ERROR "):
                failures.append(
                    FailureDetail(
                        test_name=line.strip(),
                        error_type="Error",
                        message=line.strip(),
                        category="[ERROR]",
                    )
                )
        return failures

    text = failures_section.group(1)
    # Blocks are delimited by pytest test case headers like:
    # ____ TestClass.test_name ____
    blocks = re.split(r"^_{1,}\s+(.+?)\s+_{1,}$", text, flags=re.MULTILINE)
    for i in range(1, len(blocks), 2):
        test_id = blocks[i].strip()
        body = blocks[i + 1]

        loc_match = re.search(r"([\w\-./\\]+\.py):(\d+): in\s+([^\n]+)", body)
        file_line = f"{Path(loc_match.group(1)).name}:{loc_match.group(2)}" if loc_match else ""

        e_lines = [
            l[4:].strip() if l.startswith("E   ") else l[2:].strip()
            for l in body.splitlines()
            if l.startswith("E   ") or l.startswith("E ")
        ]

        # Extract exception type and message from the first matching E line
        err_type = "AssertionError" if "AssertionError" in body else "Error"
        msg_text = ""
        for el in e_lines:
            m = re.match(r"^([\w\.]+Error|[\w\.]+Exception):\s*(.*)", el)
            if m:
                err_type = m.group(1)
                msg_text = m.group(2)
                break
        if not msg_text and e_lines:
            msg_text = e_lines[0]

        category = classify_error_detail(err_type, msg_text, body)
        short_name = test_id.split(".")[-1] if "." in test_id else test_id

        failures.append(
            FailureDetail(
                test_name=short_name,
                error_type=err_type,
                message=msg_text or err_type,
                category=category,
                file_line=file_line,
                snippet="\n".join(e_lines[:3]),
            )
        )

    return failures


def extract_file_index(p: Path) -> int:
    """Extracts integer index from file stem for stable numerical sorting."""
    m = re.search(r"\d+", p.stem)
    return int(m.group(0)) if m else 0


def run_cross_test(
    lib_dir: Path,
    test_dir: Path,
    suite_name: str,
    label: str,
    eval_base: Path,
    test_kind: str = "auto",
    include_fuzz: bool = False,
) -> CrossTestResult:
    """Runs test suite from test_dir against library implementation from lib_dir."""
    sandbox = eval_base / label.replace("+", "_").replace("/", "_")
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True, exist_ok=True)

    # 1. Unpack library files
    lib_candidates = sorted(lib_dir.glob("lib_*.py"), key=extract_file_index)
    if not lib_candidates:
        return CrossTestResult(
            target_lib=lib_dir.name,
            test_suite=test_dir.name,
            passed=0,
            failed=1,
            output=f"Missing lib file in {lib_dir}",
            failures=[
                FailureDetail(
                    test_name="missing_lib",
                    error_type="FileNotFoundError",
                    message=f"Missing lib file in {lib_dir}",
                    category="[ERROR]",
                )
            ],
        )
    lib_archive = lib_candidates[-1]

    lib_files = parse_bundled_file(lib_archive)
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
        normalized = re.sub(r"benchmark_\d+", "benchmark_1", normalized)
        if fname == f"{suite_name}_impl.py" and "__initialize__" not in normalized:
            normalized += f"""

def __initialize__(registry=None) -> None:
    from support.lib.lifecycle import get_default_registry
    reg = get_default_registry() if registry is None else registry
    for attr_name in ("DAG", "WaveScheduler", "DAGRunner", "VersionEngine", "PackageRepository", "DependencySolver"):
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

    # 2. Scope Aliasing: Symlink any flight scopes (benchmark_2, benchmark_5, benchmark_8, etc.) to benchmark_1
    for fcontent in lib_files.values():
        for alias_match in set(re.findall(r"benchmark_\d+", fcontent)):
            if alias_match != "benchmark_1":
                alias_path = sandbox / alias_match
                if not alias_path.exists():
                    os.symlink("benchmark_1", alias_path)

    # 3. Detect and unpack test suite (pretense or unit)
    is_pretense = False
    has_pretense = bool(list(test_dir.glob("pretense_*.py")))
    if test_kind == "pretense" or (test_kind == "auto" and has_pretense):
        is_pretense = True
        pretense_candidates = sorted(test_dir.glob("pretense_*.py"), key=extract_file_index)
        test_source = pretense_candidates[-1]
        target_test_dir = sandbox / "benchmark_1" / "parts" / suite_name / "pretense"
        test_file = target_test_dir / f"{suite_name}_impl_pretense.py"
    else:
        test_candidates = sorted(test_dir.glob("test_*.py"), key=extract_file_index)
        if not test_candidates:
            return CrossTestResult(
                target_lib=lib_dir.name,
                test_suite=test_dir.name,
                passed=0,
                failed=1,
                output=f"Missing test file in {test_dir}",
                failures=[
                    FailureDetail(
                        test_name="missing_test",
                        error_type="FileNotFoundError",
                        message=f"Missing test file in {test_dir}",
                        category="[ERROR]",
                    )
                ],
            )
        test_source = test_candidates[-1]
        target_test_dir = sandbox / "benchmark_1" / "parts" / suite_name / "tests"
        test_file = target_test_dir / f"{suite_name}_impl_test.py"

    if not test_source.exists():
        return CrossTestResult(
            target_lib=lib_dir.name,
            test_suite=test_dir.name,
            passed=0,
            failed=1,
            output=f"Missing test file {test_source}",
            failures=[
                FailureDetail(
                    test_name="missing_test",
                    error_type="FileNotFoundError",
                    message=f"Missing test file {test_source}",
                    category="[ERROR]",
                )
            ],
        )

    test_raw = test_source.read_text(encoding="utf-8")
    # Normalize flight scope imports so tests consistently import from benchmark_1
    test_normalized = re.sub(r"benchmark_\d+", "benchmark_1", test_raw)
    # Ensure any scope references are aliased to benchmark_1
    for alias_match in set(re.findall(r"benchmark_\d+", test_raw)):
        if alias_match != "benchmark_1":
            alias_path = sandbox / alias_match
            if not alias_path.exists():
                os.symlink("benchmark_1", alias_path)
    # Strip dangerous in-module sys.modules deletion and path tampering
    test_normalized = re.sub(
        r"for\s+_k\s+in\s+\[[^\n]+\]:\s+del\s+sys\.modules\[_k\]",
        "# sys.modules clearing removed\npass",
        test_normalized,
    )
    test_normalized = re.sub(r"del\s+sys\.modules\[_k\]", "pass", test_normalized)
    test_normalized = re.sub(r"benchmark_1\.__path__\s*=.*", "# benchmark_1.__path__ normalized", test_normalized)

    target_test_dir.mkdir(parents=True, exist_ok=True)
    (target_test_dir / "__init__.py").write_text("", encoding="utf-8")
    test_file.write_text(test_normalized, encoding="utf-8")

    # 4. Inject pytest conftest in test directory to harmonize sys.modules and singleton registration
    conftest_path = target_test_dir / "conftest.py"
    conftest_content = f"""
import sys
import importlib

# Force identical module identity between unqualified and qualified imports
_pkg_mod = importlib.import_module("benchmark_1.parts.{suite_name}.lib.{suite_name}")
sys.modules["{suite_name}"] = _pkg_mod
for b in ("benchmark_1", "benchmark_2", "benchmark_3", "benchmark_4"):
    sys.modules[f"{{b}}.parts.{suite_name}.lib.{suite_name}"] = _pkg_mod

try:
    _pkg_impl = importlib.import_module("benchmark_1.parts.{suite_name}.lib.{suite_name}_impl")
    sys.modules["{suite_name}_impl"] = _pkg_impl
    for b in ("benchmark_1", "benchmark_2", "benchmark_3", "benchmark_4"):
        sys.modules[f"{{b}}.parts.{suite_name}.lib.{suite_name}_impl"] = _pkg_impl
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

    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short"]
    if is_pretense and not include_fuzz:
        cmd.extend(["-k", "Real or Unit"])
    cmd.append(str(test_file))

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
    if failed == 0 and passed == 0 and res.returncode != 0:
        failed = 1

    failures = parse_failures(output)
    if failed > 0 and not failures:
        first_err = "Test execution failed"
        for line in output.splitlines():
            if "Error:" in line or "FAILED" in line:
                first_err = line.strip()
                break
        failures.append(
            FailureDetail(
                test_name="runtime_error",
                error_type="Error",
                message=first_err,
                category="[ERROR]",
                file_line=str(test_file.name),
                snippet=output[-500:],
            )
        )

    return CrossTestResult(
        target_lib=lib_dir.name,
        test_suite=test_dir.name,
        passed=passed,
        failed=failed,
        output=output,
        failures=failures,
    )


def generate_markdown_report(
    suite_name: str,
    mode: str,
    runs: Dict[str, Path],
    self_results: Dict[str, CrossTestResult],
    cross_results: Dict[str, Dict[str, CrossTestResult]],
    target_filter: Optional[List[str]] = None,
    test_filter: Optional[List[str]] = None,
) -> str:
    """Formats full differential cross-testing evaluation as an artifact-ready Markdown document."""
    eval_targets = target_filter if target_filter else list(runs.keys())
    eval_tests = test_filter if test_filter else list(runs.keys())

    lines: List[str] = []
    lines.append(f"# Differential Cross-Evaluation Matrix: `{suite_name}`\n")
    lines.append(f"- **Mode**: `{mode}`")
    lines.append(f"- **Evaluated Targets**: `{len(eval_targets)}`")
    lines.append(f"- **Evaluated Test Suites**: `{len(eval_tests)}`\n")

    # 1. Implementation Robustness Matrix
    lines.append("## 1. Cross-Implementation Robustness Matrix ($T_{\\text{suite}} \\to L_{\\text{impl}}$)\n")
    lines.append(
        "Evaluates each synthesized library implementation ($L$) against foreign test suites ($T$).\n"
    )

    headers = ["Target Implementation", "Self Pass"]
    for t_name in eval_tests:
        headers.append(f"`{abbreviate_run_name(t_name)}`")
    headers.extend(["Foreign Total", "Cross Pass %", "Soundness Status"])

    lines.append("| " + " | ".join(headers) + " |")
    alignments = [":---", ":---:"] + [":---:"] * len(eval_tests) + [":---:", ":---:", ":---"]
    lines.append("| " + " | ".join(alignments) + " |")

    for target_name in eval_targets:
        row = [f"**`{target_name}`**"]
        self_res = self_results.get(target_name)
        if self_res:
            row.append(f"{self_res.passed}/{self_res.total} ({self_res.pass_rate:.1f}%)")
        else:
            row.append("—")

        foreign_passed = 0
        foreign_total = 0

        for test_name in eval_tests:
            if test_name == target_name:
                row.append("—")
            else:
                c_res = cross_results.get(target_name, {}).get(test_name)
                if c_res:
                    foreign_passed += c_res.passed
                    foreign_total += c_res.total
                    marker = " ⚠️" if c_res.failed > 0 else ""
                    row.append(f"{c_res.passed}/{c_res.total} ({c_res.pass_rate:.1f}%){marker}")
                else:
                    row.append("N/A")

        cross_pct = (foreign_passed / foreign_total * 100.0) if foreign_total > 0 else 0.0
        row.append(f"{foreign_passed}/{foreign_total}")
        row.append(f"**{cross_pct:.1f}%**")

        if foreign_total > 0 and foreign_passed == foreign_total:
            status = "🟢 SOUND (100%)"
        elif cross_pct >= 95.0:
            status = "🟡 HIGH (>=95%)"
        else:
            status = "🔴 DEFICIENT (<95%)"
        row.append(status)

        lines.append("| " + " | ".join(row) + " |")

    lines.append("")

    # 2. Test Suite Strictness Matrix
    lines.append("## 2. Test Suite Strictness & Bug Hunting Power ($T_{\\text{suite}}$)\n")
    lines.append(
        "Measures the diagnostic ability of each test suite to uncover defects across foreign implementations.\n"
    )

    strict_headers = [
        "Test Suite",
        "Self Pass",
        "Foreign Targets Run",
        "Foreign Tests Executed",
        "Foreign Bugs Caught",
        "Defect Detection Rate",
        "Diagnostic Rigor",
    ]
    lines.append("| " + " | ".join(strict_headers) + " |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :--- |")

    for test_name in eval_tests:
        self_res = self_results.get(test_name)
        self_str = f"{self_res.passed}/{self_res.total} ({self_res.pass_rate:.1f}%)" if self_res else "—"

        f_targets = 0
        f_tests = 0
        f_bugs = 0

        for target_name in eval_targets:
            if target_name == test_name:
                continue
            c_res = cross_results.get(target_name, {}).get(test_name)
            if c_res:
                f_targets += 1
                f_tests += c_res.total
                f_bugs += c_res.failed

        det_rate = (f_bugs / f_tests * 100.0) if f_tests > 0 else 0.0
        if f_bugs >= 20:
            rigor = "🔴 High Rigor (Uncovers subtle contract violations)"
        elif f_bugs > 0:
            rigor = "🟡 Moderate Rigor (Catches standard edge cases)"
        else:
            rigor = "⚪ Permissive / Standard (Zero defects exposed)"

        lines.append(
            f"| **`{test_name}`** | {self_str} | {f_targets} | {f_tests} | **{f_bugs}** | {det_rate:.2f}% | {rigor} |"
        )

    lines.append("")

    # 3. Soundness Gaps & Specification Divergence Root Causes
    lines.append("## 3. Cross-Implementation Soundness Gaps & Defect Root Causes\n")

    all_failures: Dict[str, Dict] = {}
    for target_name, suite_dict in cross_results.items():
        for test_suite_name, c_res in suite_dict.items():
            for f in c_res.failures:
                key = f"{f.test_name}::{f.error_type}"
                if key not in all_failures:
                    all_failures[key] = {
                        "test_name": f.test_name,
                        "error_type": f.error_type,
                        "message": f.message,
                        "category": f.category,
                        "origin_suite": test_suite_name,
                        "file_line": f.file_line,
                        "snippet": f.snippet,
                        "failed_targets": set(),
                    }
                all_failures[key]["failed_targets"].add(target_name)

    if not all_failures:
        lines.append("🎉 **No cross-testing defects detected across evaluated runs.**\n")
    else:
        lines.append(
            f"Discovered **{len(all_failures)} unique cross-testing defect patterns** across evaluated implementations:\n"
        )
        for key, info in sorted(all_failures.items()):
            test_func = info["test_name"]
            cat = info["category"]
            msg = info["message"]
            suite = info["origin_suite"]
            loc = f" (`{info['file_line']}`)" if info["file_line"] else ""
            targets_str = ", ".join(f"`{t}`" for t in sorted(info["failed_targets"]))

            lines.append(f"### `{test_func}` {cat}")
            lines.append(f"- **Contract / Error**: `{msg}`")
            lines.append(f"- **Originating Test Suite**: `{suite}`{loc}")
            lines.append(f"- **Failing Implementation(s)**: {targets_str}")
            if info["snippet"]:
                lines.append(f"- **Traceback Excerpt**:\n```\n{info['snippet']}\n```")
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Differential Cross-Testing Protocol Runner for Cleanroom Benchmarks."
    )
    parser.add_argument(
        "--suite",
        default="semver_solver",
        help="Benchmark suite identifier (default: semver_solver)",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "pretense", "unit"],
        default="auto",
        help="Test mode to cross-evaluate (auto, pretense, unit)",
    )
    parser.add_argument(
        "--fuzz",
        action="store_true",
        help="Include full property fuzzing in pretense cross-testing (slower)",
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
        help="Optional specific target model directory to cross-check against test suites",
    )
    parser.add_argument(
        "--test-model",
        default=None,
        help="Optional specific test suite model to run against target implementations",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Display full failing assertion details, line numbers, and tracebacks",
    )
    parser.add_argument(
        "--output-markdown",
        default=None,
        help="Optional file path to write generated Markdown report",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Quiet mode: suppress per-test execution progress and only display final matrices",
    )
    parser.add_argument(
        "--no-matrix",
        action="store_true",
        help="Skip outputting the Markdown summary tables at the end",
    )
    args = parser.parse_args()

    results_path = Path(args.results_dir) / args.suite
    if not results_path.is_dir():
        print(f"Error: Results directory not found: {results_path}", file=sys.stderr)
        return 1

    runs: Dict[str, Path] = {}
    for p in sorted(results_path.iterdir()):
        if not p.is_dir():
            continue
        has_lib = (p / "lib_1.py").exists() or bool(list(p.glob("lib_*.py")))
        has_test = (p / "test_1.py").exists()
        has_pretense = (p / "pretense_1.py").exists()

        if args.mode == "pretense" and has_lib and has_pretense:
            runs[p.name] = p
        elif args.mode == "unit" and has_lib and has_test:
            runs[p.name] = p
        elif args.mode == "auto" and has_lib and (has_pretense or has_test):
            runs[p.name] = p

    print(f"=== Cleanroom Differential Cross-Testing Runner [{args.suite}] ===")
    print(f"Mode: {args.mode} (fuzz={args.fuzz})")
    print(f"Discovered {len(runs)} benchmark runs: {list(runs.keys())}\n")

    if not runs:
        print("No matching benchmark runs found.")
        return 0

    eval_base = Path(args.eval_base)
    eval_base.mkdir(parents=True, exist_ok=True)

    self_results: Dict[str, CrossTestResult] = {}
    cross_results: Dict[str, Dict[str, CrossTestResult]] = {}

    # 1. Self-Consistency Gate
    if not args.summary_only:
        print("=" * 80)
        print("1. SELF-CONSISTENCY GATE (V_self -> P_self)")
        print("=" * 80)

    for name, p in runs.items():
        res = run_cross_test(
            p, p, args.suite, f"self_{name}", eval_base, test_kind=args.mode, include_fuzz=args.fuzz
        )
        self_results[name] = res
        if not args.summary_only:
            status = "PASS" if res.failed == 0 and res.passed > 0 else "FAIL"
            gap = f" {classify_failure(res.output)}" if res.failed > 0 else ""
            pct = f"({res.pass_rate:.1f}%)"
            print(f"  [{status}]{gap} {name:44s} -> {res.passed:2d} passed, {res.failed:2d} failed {pct}")

    # 2. Pairwise Cross-Evaluation
    targets = [args.target_model] if args.target_model and args.target_model in runs else list(runs.keys())
    test_filter = [args.test_model] if args.test_model and args.test_model in runs else list(runs.keys())

    for target_name in targets:
        target_path = runs[target_name]
        cross_results[target_name] = {}
        if not args.summary_only:
            print("\n" + "=" * 80)
            print(f"2. CROSS-EVALUATION: TARGET IMPLEMENTATION [{target_name}]")
            print("=" * 80)

        for test_name in test_filter:
            if test_name == target_name:
                continue
            test_path = runs[test_name]
            c_res = run_cross_test(
                target_path,
                test_path,
                args.suite,
                f"{test_name}_on_{target_name}",
                eval_base,
                test_kind=args.mode,
                include_fuzz=args.fuzz,
            )
            cross_results[target_name][test_name] = c_res

            if not args.summary_only:
                status = "PASS" if c_res.failed == 0 and c_res.passed > 0 else "FAIL"
                gap = f" {classify_failure(c_res.output)}" if c_res.failed > 0 else ""
                pct = f"({c_res.pass_rate:.1f}%)"
                print(f"  [{status}]{gap} Test: {test_name:40s} on Lib -> {c_res.passed:2d} passed, {c_res.failed:2d} failed {pct}")
                if c_res.failed > 0:
                    max_display = len(c_res.failures) if args.detailed else 5
                    for f in c_res.failures[:max_display]:
                        loc_str = f" [{f.file_line}]" if f.file_line and args.detailed else ""
                        print(f"       * {f.test_name}{loc_str}: {f.message}")
                        if args.detailed and f.snippet:
                            for s_line in f.snippet.splitlines()[:2]:
                                print(f"           {s_line}")
                    if not args.detailed and len(c_res.failures) > max_display:
                        remaining = len(c_res.failures) - max_display
                        print(f"       ... and {remaining} more failing test(s) (use --detailed to display all)")

    # 3. Generate and display Markdown Summary Matrix
    if not args.no_matrix:
        print("\n" + "=" * 80)
        print("3. DIFFERENTIAL CROSS-EVALUATION SUMMARY REPORT")
        print("=" * 80 + "\n")
        md_report = generate_markdown_report(
            suite_name=args.suite,
            mode=args.mode,
            runs=runs,
            self_results=self_results,
            cross_results=cross_results,
            target_filter=targets,
            test_filter=test_filter,
        )
        print(md_report)

        if args.output_markdown:
            out_path = Path(args.output_markdown)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md_report, encoding="utf-8")
            print(f"\n[OK] Markdown report written to {out_path}")

    print("\nCross-evaluation completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
