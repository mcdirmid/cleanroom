# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 8f61f3b833e7
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for tool_coverage."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Sequence, Set, Tuple
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


@data_type
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


@singleton_type("agent_session")
class CoverageEvaluator(InTier[AgentSessionTier], Protocol):
    """Protocol for single-target statement test coverage evaluation and report generation."""

    @operation
    def format_ranges(self, lines: Sequence[int]) -> str:
        """Formats a sorted sequence of line numbers into compact comma-separated ranges.

        POSTCONDITIONS:
        - MUST return empty string when lines is empty.
        - MUST group contiguous sequences of integers into 'start-end' strings.
        - MUST join distinct ranges or isolated numbers with commas.
        """
        ...

    @operation
    def group_into_spans(self, lines: Sequence[int]) -> List[Tuple[int, int]]:
        """Groups sorted line numbers into contiguous (start, end) span tuples.

        POSTCONDITIONS:
        - MUST return empty list when lines is empty.
        - MUST group contiguous runs of line numbers into single (start, end) tuples.
        """
        ...

    @operation
    def normalize_target_query(self, raw_query: str) -> str:
        """Normalizes query string by stripping Bazel target or path prefixes.

        POSTCONDITIONS:
        - MUST strip leading '//' prefixes and package specifiers.
        - MUST strip '.py' file extensions from query string.
        """
        ...

    @operation
    def format_spans_report(self, cov: ModuleCoverage, max_spans: Optional[int] = None) -> str:
        """Formats uncovered statement spans with source code lines and optional clamping.

        POSTCONDITIONS:
        - MUST return 'All statements covered.' when missing_spans is empty.
        - MUST clamp output to at most max_spans when specified.
        """
        ...

    @operation
    def format_coverage_report(
        self, cov: ModuleCoverage, threshold: float, max_spans: Optional[int] = None
    ) -> str:
        """Formats structured coverage report suitable for console output and log files.

        POSTCONDITIONS:
        - MUST report unit test failures prominently when test_passed is False.
        - MUST report 100% coverage success notice when missed count is zero.
        - MUST include agent guidance for translating uncovered lines into grounding defects.
        """
        ...

    @operation
    def get_available_targets(self, repo_root: Path | str) -> Dict[str, Tuple[Path, Path]]:
        """Scans repository for implementation files and companion test suites.

        POSTCONDITIONS:
        - MUST return mapping of target names to (impl_path, test_path) tuples.
        """
        ...

    @operation
    def get_non_executable_lines(self, file_path: Path | str) -> Set[int]:
        """Analyzes AST to identify lines that are not executable statements.

        POSTCONDITIONS:
        - MUST exclude docstring expression lines.
        - MUST exclude signature continuation lines between def and first body statement.
        - MUST exclude lines marked with pragma no cover comments and their statement bodies.
        """
        ...

    @operation
    def measure_single_target_coverage(
        self, impl_path: Path | str, test_path: Path | str
    ) -> ModuleCoverage:
        """Executes single target test suite under trace instrumentation and calculates metrics.

        POSTCONDITIONS:
        - MUST return ModuleCoverage with test_passed False when suite raises errors.
        - MUST calculate covered lines by intersecting trace hits with executable lines.
        """
        ...

    @operation
    def evaluate_coverage(
        self,
        target_or_impl: str,
        test_path: Optional[Path | str] = None,
        repo_root: Optional[Path | str] = None,
        threshold: float = 0.0,
        update_log: Optional[Path | str] = None,
        max_spans: Optional[int] = None,
    ) -> ModuleCoverage:
        """Measures target coverage, validates threshold, and optionally writes coverage log.

        POSTCONDITIONS:
        - MUST resolve target names against available targets when test_path is omitted.
        - MUST write formatted report to update_log when specified.
        """
        ...
