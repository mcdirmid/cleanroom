"""Low-level implementation specification for benchmark_impl."""

from typing import Mapping, Optional, Sequence, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton, SystemTier
import benchmark


@singleton_type("system")
class BenchmarkEvaluator(benchmark.BenchmarkEvaluator):
    """Realizes model efficiency evaluation, flight execution, telemetry harvesting, and report generation.

    GROUNDING:
    - Realizes benchmark.BenchmarkEvaluator as the benchmark_evaluation_service knowledge provision by
      loading model catalogs and rate cards via model_config_ext and app_info_ext, maintaining suite
      catalogs, dispatching flights across harnesses or simulation, harvesting step and round log metrics,
      evaluating two-pass verification gates, and serializing traces.
    """

    @operation
    def get_model_catalog(self) -> Mapping[str, benchmark.ModelSpec]:
        """Provides access to the active model catalog loaded from declarative configuration.

        Returns:
            Mapping of model identifiers and aliases to ModelSpec instances.

        GROUNDING:
        - Resolves model configurations and rate cards via model_config_ext and app_info_ext.

        POSTCONDITIONS:
        - MUST return a mapping containing resolved model specifications.
        """
        ...

    @operation
    @override
    def get_suite_catalog(self) -> Mapping[str, Sequence[benchmark.BenchmarkUnit]]:
        """Provides access to the active benchmark suites and units catalog.

        Returns:
            Mapping of suite names to sequences of benchmark units.

        GROUNDING:
        - Exposes the canonical suite catalog mapping suite identifiers to evaluation targets.

        POSTCONDITIONS:
        - MUST return a mapping containing resolved suite specifications.
        """
        ...

    @operation
    @override
    def execute_flight(
        self,
        model: benchmark.ModelSpec,
        unit: benchmark.BenchmarkUnit,
        rq: str,
        harness: str,
        dry_run: bool = False,
        simulate: bool = False,
        mutation_testing: bool = False,
        results_dir: Optional[str] = None,
        wait_for_convergence: bool = True,
        timeout: Optional[float] = None,
        antigravity_dispatch: str = "message",
        baseline: bool = False,
    ) -> benchmark.FlightRecord:
        """Executes a benchmark flight for a designated model and unit.

        Returns:
            The completed flight record with empirical telemetry and verification outcomes.

        GROUNDING:
        - Coordinates flight execution over subprocess dispatch or simulation, parses step and round log files
          or subagent session transcripts modified during execution, computes rate card costs, and evaluates two-pass quality gates with dynamically assembled package and support environments.

        POSTCONDITIONS:
        - MUST execute the flight under the requested harness or simulation mode.
        - WHEN baseline is True and harness is 'loop', MUST raise ValueError rejecting loop harness.
        - WHEN baseline is True, MUST record exactly one execution round under baseline role.
        - WHEN baseline is True, MUST provide the low-level specification and instruct the developer agent to consult it, implement the two-file library structure in lib/, test _impl.py, and achieve 100% test coverage with opt-outs.
        - MUST harvest telemetry and evaluate verification gates.
        - MUST return a flight record with complete empirical measurements.
        - MUST skip artifact archival and workspace draining when dry_run is True.
        """
        ...

    @operation
    @override
    def archive_flight_artifacts(
        self,
        record: benchmark.FlightRecord,
        unit: benchmark.BenchmarkUnit,
        results_dir: Optional[str] = None,
    ) -> Optional[Tuple[str, str]]:
        """Archives synthesized library and test files into the results directory with embedded metrics.

        Returns:
            Tuple of archived library and test file paths, or None if files are missing.

        GROUNDING:
        - Resolves target directory under benchmarks/results/<benchmark-id>/<model-name+harness-name>/ or results_dir.
        - Scans directory to resolve next sequential run index N.
        - Writes test file as test_<N>.py and library file as lib_<N>.py with embedded flight metrics comment block.

        POSTCONDITIONS:
        - WHEN record.verification_outcomes indicates failure (unit_tests_failed > 0, unit_tests_passed == 0, pyright_errors > 0, or spec_linter_pass is False), MUST skip archival and return None.
        - WHEN verification gates pass and synthesized source files are present, MUST resolve directory under <results_dir>/<benchmark-id>/<model-name+harness-name>/ (or appending -baseline for baseline methodology).
        - MUST resolve the next sequential run index N and copy the library file as lib_<N>.py and the test file as test_<N>.py.
        - MUST prepend flight telemetry metrics, role execution rounds, and verification outcomes as comments to lib_<N>.py.
        - MUST preserve multi-file library implementations within lib_<N>.py.
        - MUST archive Cleanroom event log when present as cleanroom_<N>.log.
        - MUST return paths to archived lib and test files or None if source files are absent or verification failed.
        """
        ...

    @operation
    @override
    def drain_unit_workspace(self, unit: benchmark.BenchmarkUnit) -> None:
        """Purges synthesized library and test directories from the benchmark unit workspace.

        GROUNDING:
        - Removes lib and tests directories from unit.unit_dir and purges matching role workspaces.

        POSTCONDITIONS:
        - MUST remove all files and directories under unit.unit_dir/lib and unit.unit_dir/tests.
        - MUST mark specifications clean up to specification QA within the flight scope to isolate code and test generation.
        - MUST purge ephemeral role workspaces associated with the unit.
        - MUST remove ephemeral flight scopes when present.
        """
        ...

    @operation
    @override
    def generate_report(self, records: Sequence[benchmark.FlightRecord], output_path: Optional[str] = None) -> str:
        """Formats flight records into a markdown summary report.

        Returns:
            The formatted markdown summary report string.

        GROUNDING:
        - Iterates flight records to construct a markdown results matrix and cross-tier efficiency
          analysis, writing to output_path when provided.

        POSTCONDITIONS:
        - MUST format a markdown summary table containing model tiers, token metrics, costs, and test results.
        - WHEN an output path is provided, MUST write the markdown report to disk.
        """
        ...

    @operation
    @override
    def save_flight_json(self, record: benchmark.FlightRecord, logs_dir: str) -> str:
        """Serializes a flight record to a structured JSON file.

        Returns:
            The path to the persisted JSON flight trace.

        GROUNDING:
        - Creates a benchmarks directory under logs_dir and serializes the flight record dictionary
          as formatted JSON matching Section 7 schema.

        POSTCONDITIONS:
        - MUST write a JSON trace matching the canonical schema under logs/benchmarks/.
        - MUST return the path to the written JSON file.
        """
        ...

    @operation
    @override
    def harvest_flight(
        self,
        flight_id: str,
        results_dir: Optional[str] = None,
        mutation_testing: bool = False,
    ) -> Optional[benchmark.FlightRecord]:
        """Harvests telemetry and archives artifacts for a completed flight.

        Returns:
            The updated flight record or None if the flight record is not found.

        GROUNDING:
        - Locates the flight record JSON, harvests telemetry from subagent transcripts or runner logs,
          evaluates verification gates, updates the flight record, and archives artifacts.

        POSTCONDITIONS:
        - MUST locate the flight record JSON by flight identifier.
        - MUST harvest telemetry and evaluate verification gates for the flight.
        - MUST return the updated flight record or None if the flight record is not found.
        """
        ...

    @operation
    @override
    def run_cli(self, argv: Optional[Sequence[str]] = None) -> int:
        """Parses arguments and runs the resolved benchmark matrix.

        Returns:
            Process exit code (0 for success, 1 for failure).

        GROUNDING:
        - Parses CLI flags, resolves target models and suites, executes flights, persists JSON traces,
          and prints summary reports.

        POSTCONDITIONS:
        - MUST resolve models, suites, tiers, and limits from arguments.
        - MUST execute all resolved flights and print summary reports.
        - MUST return exit code 0 on success or 1 on failure.
        """
        ...


def __orphan__() -> None:
    """Orphan contracts for benchmark suite catalogs, telemetry log harvesting, and CLI execution.

    POSTCONDITIONS:
    - MUST provide benchmark evaluation suites categorized by suite identifiers derived from benchmark part directories.
    - MUST harvest empirical measurements including token counts, step latencies, and role execution rounds from runner log files and transcripts.
    - MUST tally role execution rounds exclusively across target role workers based on worker dispatch waves while excluding coordinator sessions from role rounds.
    - MUST provision a concise sequential ephemeral flight scope directory (e.g. benchmark_1), rewrite copied benchmark imports, disallow bare parts imports, mark specifications clean up to specification QA, and copy scope methodology configuration.
    - WHEN an evaluated flight scope index does not exist in the repository root, MUST purge any orphaned role workspaces matching that index to permit sequential reuse.
    - MUST clean up orphaned flight scope directories and associated role workspaces from prior flights.
    - MUST tear down the ephemeral flight scope directory and associated provisioned role workspaces upon flight completion.
    - MUST execute the benchmark evaluator command-line runner within the system lifecycle tier.
    """
    ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-19T18:45:00Z
# LAST_CHANGED: 2026-10-22T23:10:00Z
# CHANGE: Ground deriving benchmark suites from benchmark part directories
# SPEC_QA_AUDIT: 2026-10-19T19:35:00Z
# --- END CLEANROOM METADATA ---
