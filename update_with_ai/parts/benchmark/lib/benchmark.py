from __future__ import annotations
from support.lib.lifecycle import Singleton, SystemTier

import dataclasses
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple


@dataclasses.dataclass(frozen=True)
class ModelSpec:
    """Describes an evaluated language model and its rate card."""
    identifier: str
    tier: int
    tier_label: str
    provider: str
    rate_uncached_in: float  # $ per 1M tokens
    rate_cached_in: float    # $ per 1M tokens
    rate_out: float          # $ per 1M tokens (includes reasoning tokens)
    endpoint: Optional[str] = None
    quantization: Optional[str] = None
    default_harness: str = "loop"

    def compute_cost(self, uncached_in: int, cached_in: int, out: int) -> float:
        cost = (
            (uncached_in / 1_000_000.0) * self.rate_uncached_in
            + (cached_in / 1_000_000.0) * self.rate_cached_in
            + (out / 1_000_000.0) * self.rate_out
        )
        return round(cost, 6)


@dataclasses.dataclass(frozen=True)
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


@dataclasses.dataclass
class FlightMeasurements:
    """Captures empirical telemetry measurements from a benchmark flight."""
    inbound_tokens_uncached: int = 0
    inbound_tokens_cached: int = 0
    outbound_tokens: int = 0
    total_tokens: int = 0
    financial_cost_usd: float = 0.0
    step_latencies_seconds: List[float] = dataclasses.field(default_factory=list)
    wall_clock_seconds: float = 0.0
    role_rounds: Dict[str, int] = dataclasses.field(default_factory=dict)

    def compute_totals(self, model: ModelSpec) -> None:
        self.total_tokens = (
            self.inbound_tokens_uncached + self.inbound_tokens_cached + self.outbound_tokens
        )
        self.financial_cost_usd = model.compute_cost(
            self.inbound_tokens_uncached, self.inbound_tokens_cached, self.outbound_tokens
        )


@dataclasses.dataclass
class VerificationOutcomes:
    """Summarizes quality gate outcomes for a benchmark flight."""
    spec_linter_pass: bool = False
    pyright_errors: int = 0
    unit_tests_passed: int = 0
    unit_tests_failed: int = 0
    line_coverage_pct: float = 0.0
    branch_coverage_pct: float = 0.0
    mutation_score_pct: float = 0.0


@dataclasses.dataclass
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flight_id": self.flight_id,
            "timestamp": self.timestamp,
            "rq": self.rq,
            "model": self.model,
            "benchmark_unit": self.benchmark_unit,
            "methodology": self.methodology,
            "stages_executed": self.stages_executed,
            "measurements": dataclasses.asdict(self.measurements),
            "verification_outcomes": dataclasses.asdict(self.verification_outcomes),
        }


class BenchmarkEvaluator(Singleton[SystemTier], Protocol):
    """Coordinates benchmark flight execution and report generation."""

    def get_suite_catalog(self) -> Mapping[str, Sequence[BenchmarkUnit]]:
        ...

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
        ...

    def archive_flight_artifacts(
        self,
        record: FlightRecord,
        unit: BenchmarkUnit,
        results_dir: Optional[str] = None,
    ) -> Optional[Tuple[str, str]]:
        ...

    def drain_unit_workspace(self, unit: BenchmarkUnit) -> None:
        ...

    def generate_report(self, records: Sequence[FlightRecord], output_path: Optional[str] = None) -> str:
        ...

    def save_flight_json(self, record: FlightRecord, logs_dir: str) -> str:
        ...

    def harvest_flight(
        self,
        flight_id: str,
        results_dir: Optional[str] = None,
        mutation_testing: bool = False,
    ) -> Optional[FlightRecord]:
        ...

    def run_cli(self, argv: Optional[Sequence[str]] = None) -> int:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-19T18:45:00Z
# LAST_CHANGED: 2026-10-20T22:34:00Z
# CHANGE: Expose get_suite_catalog and results_dir parameter on BenchmarkEvaluator
# --- END CLEANROOM METADATA ---



