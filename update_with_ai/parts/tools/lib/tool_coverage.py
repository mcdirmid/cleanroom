# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:20:45Z
# CHANGE: Remove the undeclared module-level delegation API and its cached evaluator global so the interface holds only the declared coverage record and evaluator protocol
# CODE_HASH: 0bd1d982431a
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
