"""Low-level interface specification for benchmark."""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier


@data_type
@dataclass(frozen=True)
class ModelSpec:
    """Describes an evaluated language model and its rate card."""
    identifier: str
    tier: int
    tier_label: str
    provider: str
    rate_uncached_in: float
    rate_cached_in: float
    rate_out: float
    endpoint: Optional[str] = None
    quantization: Optional[str] = None
    default_harness: str = "loop"

    def compute_cost(self, uncached_in: int, cached_in: int, out: int) -> float: ...


@data_type
@dataclass(frozen=True)
class BenchmarkUnit:
    """Identifies an evaluation target in a benchmark suite."""
    suite: str
    task_id: str
    unit_dir: str
    target_address: str
    archetype: str = ""
    spec_loc: int = 0
    target_lib_loc: int = 0
    description: str = ""


@data_type
@dataclass
class FlightMeasurements:
    """Captures empirical telemetry measurements from a benchmark flight."""
    inbound_tokens_uncached: int = 0
    inbound_tokens_cached: int = 0
    outbound_tokens: int = 0
    total_tokens: int = 0
    financial_cost_usd: float = 0.0
    step_latencies_seconds: List[float] = ...
    wall_clock_seconds: float = 0.0
    role_rounds: Dict[str, int] = ...

    def compute_totals(self, model: ModelSpec) -> None: ...


@data_type
@dataclass
class VerificationOutcomes:
    """Summarizes quality gate outcomes for a benchmark flight."""
    spec_linter_pass: bool = False
    pyright_errors: int = 0
    unit_tests_passed: int = 0
    unit_tests_failed: int = 0
    line_coverage_pct: float = 0.0
    branch_coverage_pct: float = 0.0
    mutation_score_pct: float = 0.0


@data_type
@dataclass
class FlightRecord:
    """Records the complete empirical outcome of an evaluation run."""
    flight_id: str
    timestamp: str
    rq: str
    model: Dict[str, Any]
    benchmark_unit: Dict[str, Any]
    methodology: str
    stages_executed: List[str]
    measurements: FlightMeasurements
    verification_outcomes: VerificationOutcomes

    def to_dict(self) -> Dict[str, Any]: ...


@singleton_type("system")
class BenchmarkEvaluator(Singleton[SystemTier], Protocol):
    """Coordinates benchmark flight execution and report generation."""

    @operation
    def get_model_catalog(self) -> Mapping[str, ModelSpec]:
        """Provides access to the active model catalog loaded from declarative configuration.

        POSTCONDITIONS:
        - MUST return a mapping containing resolved model specifications.
        """
        ...

    @operation
    def get_suite_catalog(self) -> Mapping[str, Sequence[BenchmarkUnit]]:
        """Provides access to the active benchmark suites and units catalog.

        POSTCONDITIONS:
        - MUST return a mapping of suite names to sequences of benchmark units.
        """
        ...

    @operation
    def execute_flight(
        self,
        model: ModelSpec,
        unit: BenchmarkUnit,
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
    ) -> FlightRecord:
        """Executes a benchmark flight for a designated model and unit.

        POSTCONDITIONS:
        - MUST execute the flight under the requested harness or simulation mode.
        - WHEN baseline is True and harness is 'loop', MUST raise ValueError rejecting loop harness.
        - WHEN baseline is True, MUST provide the low-level specification and instruct the agent to consult it, implement the two-file library structure in lib/, test _impl.py, and achieve 100% test coverage with opt-outs.
        - WHEN baseline is True, MUST record exactly one execution round under baseline role.
        - MUST harvest telemetry and evaluate verification gates.
        - MUST return a flight record with complete empirical measurements.
        """
        ...

    @operation
    def archive_flight_artifacts(
        self,
        record: FlightRecord,
        unit: BenchmarkUnit,
        results_dir: Optional[str] = None,
    ) -> Optional[Tuple[str, str]]:
        """Archives synthesized library and test files into the results directory with embedded metrics.

        POSTCONDITIONS:
        - WHEN record.verification_outcomes indicates failure (unit_tests_failed > 0, unit_tests_passed == 0, pyright_errors > 0, or spec_linter_pass is False), MUST skip archival and return None.
        - WHEN verification gates pass and synthesized source files are present, MUST resolve directory under <results_dir>/<benchmark-id>/<model-name+harness-name>/.
        - MUST resolve the next sequential run index N and copy the library file as lib_<N>.py and the test file as test_<N>.py.
        - MUST prepend flight telemetry metrics, role execution rounds, and verification outcomes as comments to lib_<N>.py.
        - MUST archive Cleanroom event log when present as cleanroom_<N>.log.
        - MUST return paths to archived lib and test files or None if source files are absent or verification failed.
        """
        ...

    @operation
    def drain_unit_workspace(self, unit: BenchmarkUnit) -> None:
        """Purges synthesized library and test directories from the benchmark unit workspace.

        POSTCONDITIONS:
        - MUST remove all files and directories under unit.unit_dir/lib and unit.unit_dir/tests.
        - MUST mark specifications clean up to specification QA within the flight scope to isolate code and test generation.
        - MUST purge ephemeral role workspaces associated with the unit.
        - MUST remove ephemeral flight scopes when present.
        """
        ...

    @operation
    def generate_report(self, records: Sequence[FlightRecord], output_path: Optional[str] = None) -> str:
        """Formats flight records into a markdown summary report.

        POSTCONDITIONS:
        - MUST format a markdown summary table containing model tiers, token metrics, costs, and test results.
        - WHEN an output path is provided, MUST write the markdown report to disk.
        """
        ...

    @operation
    def save_flight_json(self, record: FlightRecord, logs_dir: str) -> str:
        """Serializes a flight record to a structured JSON file.

        POSTCONDITIONS:
        - MUST write a JSON trace matching the canonical schema under logs/benchmarks/.
        - MUST return the path to the written JSON file.
        """
        ...

    @operation
    def harvest_flight(
        self,
        flight_id: str,
        results_dir: Optional[str] = None,
        mutation_testing: bool = False,
    ) -> Optional[FlightRecord]:
        """Harvests telemetry and archives artifacts for a completed flight.

        POSTCONDITIONS:
        - MUST locate the flight record JSON by flight identifier.
        - MUST harvest telemetry and evaluate verification gates for the flight.
        - MUST return the updated flight record or None if the flight record is not found.
        """
        ...

    @operation
    def run_cli(self, argv: Optional[Sequence[str]] = None) -> int:
        """Parses arguments and runs the resolved benchmark matrix.

        POSTCONDITIONS:
        - MUST resolve models, suites, tiers, and limits from arguments.
        - MUST execute all resolved flights and print summary reports.
        - MUST return exit code 0 on success or 1 on failure.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-19T18:45:00Z
# LAST_CHANGED: 2026-10-22T23:10:00Z
# CHANGE: Make BenchmarkUnit descriptive metadata fields optional with defaults
# SPEC_QA_AUDIT: 2026-10-19T18:45:00Z
# --- END CLEANROOM METADATA ---
