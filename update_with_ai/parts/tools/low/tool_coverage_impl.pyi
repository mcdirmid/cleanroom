# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:03Z
# LAST_CHANGED: 2026-10-11T04:15:46Z
# CHANGE: State the coverage evaluator as a system service on the system tier
# CODE_HASH: 266ec49bb6f9
# SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for tool_coverage_impl."""

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import tool_coverage


@singleton_type("system")
class CoverageEvaluator(
    tool_coverage.CoverageEvaluator,
    InTier[SystemTier],
):
    """Realizes the system coverage evaluator as a system service.

    GROUNDING:
    - Provides the tool_coverage.CoverageEvaluator service realization registered within
      SystemTier, coordinating available target discovery,
      non-executable line extraction, traced unit test execution, and coverage report
      formatting for the system.
    - Projects every reported metric into the tool_coverage.ModuleCoverage fields
      (module_name, test_name, file_path, test_path, total_executable, covered, missed,
      coverage_pct, missing_lines, missing_ranges, missing_spans, test_passed, test_error)
      by mutating a per-invocation mapping of implementation file paths to executed line
      numbers built under tracing and never retained beyond the measurement operation.
    """

    @operation
    @override
    def format_ranges(self, lines: Sequence[int]) -> str:
        """Formats missing statement line numbers into compact comma-separated range strings.

        GROUNDING:
        - Projects tool_coverage.ModuleCoverage.missing_lines into
          tool_coverage.ModuleCoverage.missing_ranges by grouping sequential runs of line
          numbers and joining each range or isolated number with commas.
        """
        ...

    @operation
    @override
    def group_into_spans(self, lines: Sequence[int]) -> List[Tuple[int, int]]:
        """Groups sorted missing statement line numbers into contiguous span tuples.

        GROUNDING:
        - Projects tool_coverage.ModuleCoverage.missing_lines into
          tool_coverage.ModuleCoverage.missing_spans by aggregating consecutive line
          numbers into contiguous (start, end) bounds.
        """
        ...

    @operation
    @override
    def normalize_target_query(self, raw_query: str) -> str:
        """Normalizes a target query string by stripping package target or path prefixes.

        GROUNDING:
        - Truncates leading '//' target prefixes, package specifiers, and '.py' file
          extension suffixes so the normalized name resolves against the target name keys
          exposed by tool_coverage.CoverageEvaluator.get_available_targets.
        """
        ...

    @operation
    @override
    def format_spans_report(
        self, cov: tool_coverage.ModuleCoverage, max_spans: Optional[int] = None
    ) -> str:
        """Formats source snippet reports for uncovered statement spans with presentation span clamping.

        GROUNDING:
        - Reads the source text named by tool_coverage.ModuleCoverage.file_path through the
          pathlib filesystem operations declared by the filesystem_ext external boundary,
          indexes the lines of tool_coverage.ModuleCoverage.missing_spans against that
          source text, and clamps the presented spans when max_spans is configured.
        """
        ...

    @operation
    @override
    def format_coverage_report(
        self,
        cov: tool_coverage.ModuleCoverage,
        threshold: float,
        max_spans: Optional[int] = None,
    ) -> str:
        """Formats structured coverage reports with agent guidance and deficit metrics.

        GROUNDING:
        - Composes the report from tool_coverage.ModuleCoverage.coverage_pct,
          tool_coverage.ModuleCoverage.missed, tool_coverage.ModuleCoverage.test_passed,
          and tool_coverage.ModuleCoverage.test_error, delegates uncovered source span
          context to this evaluator's format_spans_report under the supplied threshold and
          max_spans, and appends agent guidance for translating uncovered lines into
          grounding defects.
        """
        ...

    @operation
    @override
    def get_available_targets(
        self, repo_root: Path | str
    ) -> Dict[str, Tuple[Path, Path]]:
        """Discovers available implementation and test file pairs across repository part packages.

        GROUNDING:
        - Globs part library implementation files and companion test files through the
          pathlib filesystem operations declared by the filesystem_ext external boundary,
          pairs each implementation file with its companion test file, and maps target
          names to the tool_coverage.ModuleCoverage.file_path and
          tool_coverage.ModuleCoverage.test_path path values recorded by the measurement
          operation.
        """
        ...

    @operation
    @override
    def get_non_executable_lines(self, file_path: Path | str) -> Set[int]:
        """Extracts candidate executable lines from an implementation source file by filtering non-executable lines.

        GROUNDING:
        - Reads the implementation source through the pathlib filesystem operations
          declared by the filesystem_ext external boundary, parses it with the ast.parse
          syntax tree operation, and walks statement nodes to detect docstring expression
          lines, function and class signature continuation lines, and pragma comment lines
          matched by regular expression patterns whose statement bodies are excluded,
          realizing the tool_coverage.CoverageEvaluator.get_non_executable_lines contract
          consumed by this evaluator's measure_single_target_coverage.
        """
        ...

    @operation
    @override
    def measure_single_target_coverage(
        self, impl_path: Path | str, test_path: Path | str
    ) -> tool_coverage.ModuleCoverage:
        """Measures single-target statement coverage by executing the companion test suite under execution tracing.

        GROUNDING:
        - Clears the sys.modules entries of the measured module and injects the local
          package directories of the implementation and test files into sys.path before
          execution, then runs the companion unittest suite under trace instrumentation
          through trace.Trace, mutating a per-invocation mapping of implementation file
          paths to executed line numbers from the trace callback and capturing suite import
          and execution failures into tool_coverage.ModuleCoverage.test_error with
          tool_coverage.ModuleCoverage.test_passed cleared.
        - Intersects the accumulated traced line numbers with the candidate executable
          lines extracted by this evaluator's get_non_executable_lines and populates
          tool_coverage.ModuleCoverage.total_executable,
          tool_coverage.ModuleCoverage.covered, tool_coverage.ModuleCoverage.missed,
          tool_coverage.ModuleCoverage.coverage_pct,
          tool_coverage.ModuleCoverage.missing_lines,
          tool_coverage.ModuleCoverage.missing_ranges through format_ranges, and
          tool_coverage.ModuleCoverage.missing_spans through group_into_spans.
        """
        ...

    @operation
    @override
    def evaluate_coverage(
        self,
        target_or_impl: str,
        test_path: Optional[Path | str] = None,
        repo_root: Optional[Path | str] = None,
        threshold: float = 0.0,
        update_log: Optional[Path | str] = None,
        max_spans: Optional[int] = None,
    ) -> tool_coverage.ModuleCoverage:
        """Evaluates module coverage against a percentage threshold and updates coverage log files.

        GROUNDING:
        - Resolves target_or_impl through normalize_target_query against the target name
          keys exposed by tool_coverage.CoverageEvaluator.get_available_targets when
          test_path is omitted, delegates measurement to measure_single_target_coverage,
          compares tool_coverage.ModuleCoverage.coverage_pct against the supplied
          threshold to derive the threshold exit status indication, and synchronizes the
          report produced by format_coverage_report to the update_log path through the
          pathlib filesystem operations declared by the filesystem_ext external boundary.
        """
        ...
