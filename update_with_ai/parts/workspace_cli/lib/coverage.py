from __future__ import annotations
from support.lib.lifecycle import Singleton, SystemTier

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Sequence, Set, Tuple


# Contract: ModuleCoverage encapsulates test coverage metrics for a single library module.
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


# Contract: CoverageEvaluator protocol coordinates statement coverage measurement and report generation.
class CoverageEvaluator(Singleton[SystemTier], Protocol):
    """Protocol for single-target statement test coverage evaluation and report generation."""

    # Contract: Formats missing statement line numbers into compact comma-separated range strings.
    def format_ranges(self, lines: Sequence[int]) -> str: ...

    # Contract: Groups sorted missing statement line numbers into contiguous span tuples.
    def group_into_spans(self, lines: Sequence[int]) -> List[Tuple[int, int]]: ...

    # Contract: Normalizes a target query string by stripping package target or path prefixes.
    def normalize_target_query(self, raw_query: str) -> str: ...

    # Contract: Formats source snippet reports for uncovered statement spans with presentation span clamping.
    def format_spans_report(
        self, cov: ModuleCoverage, max_spans: Optional[int] = None
    ) -> str: ...

    # Contract: Formats structured coverage reports with agent guidance and deficit metrics.
    def format_coverage_report(
        self, cov: ModuleCoverage, threshold: float, max_spans: Optional[int] = None
    ) -> str: ...

    # Contract: Discovers available implementation and test file pairs across repository part packages.
    def get_available_targets(
        self, repo_root: Path | str
    ) -> Dict[str, Tuple[Path, Path]]: ...

    # Contract: Extracts candidate executable lines from an implementation source file by filtering non-executable lines.
    def get_non_executable_lines(self, file_path: Path | str) -> Set[int]: ...

    # Contract: Measures single-target statement coverage by executing the companion test suite under execution tracing.
    def measure_single_target_coverage(
        self, impl_path: Path | str, test_path: Path | str
    ) -> ModuleCoverage: ...

    # Contract: Evaluates module coverage against a percentage threshold and updates coverage log files.
    def evaluate_coverage(
        self,
        target_or_impl: str,
        test_path: Optional[Path | str] = None,
        repo_root: Optional[Path | str] = None,
        threshold: float = 0.0,
        update_log: Optional[Path | str] = None,
        max_spans: Optional[int] = None,
    ) -> ModuleCoverage: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:20:45Z
# CHANGE: Remove the undeclared module-level delegation API and its cached evaluator global so the interface holds only the declared coverage record and evaluator protocol
# --- END CLEANROOM METADATA ---
