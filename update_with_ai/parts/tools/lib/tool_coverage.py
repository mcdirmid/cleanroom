# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T15:15:00Z
# CHANGE: define tool_coverage interface and public helpers
# CODE_HASH: 58a5055c607b
# --- END CLEANROOM METADATA ---

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Sequence, Set, Tuple


@dataclass(frozen=True)
class ModuleCoverage:
    """Encapsulates test coverage metrics for a single library module.

    Args:
        module_name: Implementation file stem or module name.
        test_name: Companion test file stem or test suite name.
        file_path: Path to implementation file on disk.
        test_path: Path to unit test file on disk.
        total_executable: Count of candidate executable statements.
        covered: Count of executable statements executed by tests.
        missed: Count of executable statements missed by tests.
        coverage_pct: Percentage of executable statements executed.
        missing_lines: Sorted list of line numbers not executed.
        missing_ranges: Compact comma-separated range representation of missed lines.
        missing_spans: List of contiguous (start, end) line number tuples for missed lines.
        test_passed: Whether the test suite passed successfully.
        test_error: Optional error message or traceback when test execution fails.
    """

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


class CoverageEvaluator(Protocol):
    """Protocol for single-target statement test coverage evaluation and report generation."""

    def format_ranges(self, lines: Sequence[int]) -> str: ...

    def group_into_spans(self, lines: Sequence[int]) -> List[Tuple[int, int]]: ...

    def normalize_target_query(self, raw_query: str) -> str: ...

    def format_spans_report(
        self, cov: ModuleCoverage, max_spans: Optional[int] = None
    ) -> str: ...

    def format_coverage_report(
        self, cov: ModuleCoverage, threshold: float, max_spans: Optional[int] = None
    ) -> str: ...

    def get_available_targets(
        self, repo_root: Path | str
    ) -> Dict[str, Tuple[Path, Path]]: ...

    def get_non_executable_lines(self, file_path: Path | str) -> Set[int]: ...

    def measure_single_target_coverage(
        self, impl_path: Path | str, test_path: Path | str
    ) -> ModuleCoverage: ...

    def evaluate_coverage(
        self,
        target_or_impl: str,
        test_path: Optional[Path | str] = None,
        repo_root: Optional[Path | str] = None,
        threshold: float = 0.0,
        update_log: Optional[Path | str] = None,
        max_spans: Optional[int] = None,
    ) -> ModuleCoverage: ...


_evaluator_instance: Optional[CoverageEvaluator] = None


def get_coverage_evaluator() -> CoverageEvaluator:
    """Returns active coverage evaluator instance from registry or fallback."""
    global _evaluator_instance
    if _evaluator_instance is not None:
        return _evaluator_instance
    try:
        from support.lib import lifecycle

        try:
            return lifecycle.get_singleton(CoverageEvaluator)
        except lifecycle.LifecycleError:
            pass
    except (ImportError, LookupError, RuntimeError, TypeError):
        pass

    from . import tool_coverage_impl

    return tool_coverage_impl.CoverageEvaluator()


def set_coverage_evaluator(evaluator: Optional[CoverageEvaluator]) -> None:
    """Sets override coverage evaluator instance."""
    global _evaluator_instance
    _evaluator_instance = evaluator


def format_ranges(lines: Sequence[int]) -> str:
    """Formats a sorted sequence of line numbers into compact comma-separated ranges."""
    return get_coverage_evaluator().format_ranges(lines)


def group_into_spans(lines: Sequence[int]) -> List[Tuple[int, int]]:
    """Groups sorted line numbers into contiguous (start, end) span tuples."""
    return get_coverage_evaluator().group_into_spans(lines)


def normalize_target_query(raw_query: str) -> str:
    """Normalizes query string by stripping Bazel target or path prefixes."""
    return get_coverage_evaluator().normalize_target_query(raw_query)


def format_spans_report(cov: ModuleCoverage, max_spans: Optional[int] = None) -> str:
    """Formats uncovered statement spans with source code lines and optional clamping."""
    return get_coverage_evaluator().format_spans_report(cov, max_spans=max_spans)


def format_coverage_report(
    cov: ModuleCoverage, threshold: float, max_spans: Optional[int] = None
) -> str:
    """Formats structured coverage report suitable for console output and log files."""
    return get_coverage_evaluator().format_coverage_report(
        cov, threshold, max_spans=max_spans
    )


def get_available_targets(repo_root: Path | str) -> Dict[str, Tuple[Path, Path]]:
    """Scans repository for implementation files and companion test suites."""
    return get_coverage_evaluator().get_available_targets(repo_root)


def get_non_executable_lines(file_path: Path | str) -> Set[int]:
    """Analyzes AST to identify lines that are not executable statements."""
    return get_coverage_evaluator().get_non_executable_lines(file_path)


def measure_single_target_coverage(
    impl_path: Path | str, test_path: Path | str
) -> ModuleCoverage:
    """Executes single target test suite under trace instrumentation and calculates metrics."""
    return get_coverage_evaluator().measure_single_target_coverage(impl_path, test_path)


def evaluate_coverage(
    target_or_impl: str,
    test_path: Optional[Path | str] = None,
    repo_root: Optional[Path | str] = None,
    threshold: float = 0.0,
    update_log: Optional[Path | str] = None,
    max_spans: Optional[int] = None,
) -> ModuleCoverage:
    """Measures target coverage, validates threshold, and optionally writes coverage log."""
    return get_coverage_evaluator().evaluate_coverage(
        target_or_impl,
        test_path=test_path,
        repo_root=repo_root,
        threshold=threshold,
        update_log=update_log,
        max_spans=max_spans,
    )
