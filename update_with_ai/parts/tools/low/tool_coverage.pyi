# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T20:42:16Z
# LAST_CHANGED: 2026-10-11T03:37:04Z
# CHANGE: Declare coverage evaluator system tier and align record and executable line contracts
# CODE_HASH: 245d6d8e6a09
# SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for tool_coverage."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Sequence, Set, Tuple
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier


@data_type
@dataclass(frozen=True)
class ModuleCoverage:
    """Reports the test coverage metrics of a single library module.

    Args:
        module_name: Module name of the measured library module.
        test_name: Test name of the companion test suite.
        file_path: Path to the implementation file on disk.
        test_path: Path to the unit test file on disk.
        total_executable: Count of candidate executable statements.
        covered: Count of executable statements covered by the test suite.
        missed: Count of executable statements missed by the test suite.
        coverage_pct: Percentage of executable statements covered.
        missing_lines: Missing statement line numbers.
        missing_ranges: Compact comma-separated range representation of the missing lines.
        missing_spans: Contiguous (start, end) line number tuples of the missing lines.
        test_passed: Test passed status.
        test_error: Test error description when test execution fails.
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


@singleton_type("system")
class CoverageEvaluator(InTier[SystemTier], Protocol):
    """Coordinates statement coverage measurement and report generation for library modules."""

    @operation
    def format_ranges(self, lines: Sequence[int]) -> str:
        """Formats missing statement line numbers into compact comma-separated range strings.

        POSTCONDITIONS:
        - WHEN the supplied line numbers are empty, MUST return an empty string.
        - MUST group contiguous runs of line numbers into 'start-end' range strings.
        - MUST join distinct ranges and isolated line numbers with commas.
        """
        ...

    @operation
    def group_into_spans(self, lines: Sequence[int]) -> List[Tuple[int, int]]:
        """Groups sorted missing statement line numbers into contiguous span tuples.

        POSTCONDITIONS:
        - WHEN the supplied line numbers are empty, MUST return an empty list.
        - MUST group contiguous runs of line numbers into single (start, end) tuples.
        """
        ...

    @operation
    def normalize_target_query(self, raw_query: str) -> str:
        """Normalizes a target query string by stripping package target or path prefixes.

        POSTCONDITIONS:
        - MUST strip leading '//' target prefixes and package specifiers.
        - MUST strip '.py' file extensions from the query string.
        """
        ...

    @operation
    def format_spans_report(self, cov: ModuleCoverage, max_spans: Optional[int] = None) -> str:
        """Formats source snippet reports for uncovered statement spans with presentation span clamping.

        POSTCONDITIONS:
        - WHEN no missing spans remain, MUST return "All statements covered.".
        - MUST present each uncovered statement span together with its source lines.
        - WHEN a maximum span count is configured, MUST clamp the presented spans to that maximum.
        """
        ...

    @operation
    def format_coverage_report(
        self, cov: ModuleCoverage, threshold: float, max_spans: Optional[int] = None
    ) -> str:
        """Formats structured coverage reports with agent guidance and deficit metrics.

        POSTCONDITIONS:
        - WHEN the test suite did not pass, MUST report the unit test failure.
        - WHEN no statements are missed, MUST report a full coverage success notice.
        - MUST report deficit metrics for the uncovered statements against the threshold.
        - MUST include the compact missing ranges and the contiguous missing spans with their source context.
        - MUST include agent guidance for translating uncovered lines into grounding defects.
        """
        ...

    @operation
    def get_available_targets(self, repo_root: Path | str) -> Dict[str, Tuple[Path, Path]]:
        """Discovers available implementation and test file pairs across repository part packages.

        POSTCONDITIONS:
        - MUST pair each discovered implementation source file with its companion test file.
        """
        ...

    @operation
    def get_non_executable_lines(self, file_path: Path | str) -> Set[int]:
        """Extracts candidate executable lines from an implementation source file by filtering non-executable lines.

        POSTCONDITIONS:
        - MUST exclude docstring expression lines.
        - MUST exclude function and class signature continuation lines.
        - MUST exclude lines carrying pragma exclusion annotations together with their statement bodies.
        """
        ...

    @operation
    def measure_single_target_coverage(
        self, impl_path: Path | str, test_path: Path | str
    ) -> ModuleCoverage:
        """Measures single-target statement coverage by executing the companion test suite under execution tracing.

        POSTCONDITIONS:
        - WHEN the unit test suite raises errors, MUST return a coverage record whose test passed status is False.
        - MUST extract candidate executable lines from the implementation source file.
        - MUST determine covered statements by tracing the unit test suite over the candidate executable lines.
        - MUST report the missed statements as the candidate executable lines absent from the traced coverage.
        - MUST derive the missing ranges and missing spans from the missed statement line numbers.
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
        """Evaluates module coverage against a percentage threshold and updates coverage log files.

        POSTCONDITIONS:
        - WHEN the test path is omitted, MUST resolve the target name against the available implementation and test file pairs.
        - MUST evaluate the measured coverage percentage against the threshold percentage.
        - WHEN an update log path is specified, MUST write the formatted coverage report to that log file.
        """
        ...
