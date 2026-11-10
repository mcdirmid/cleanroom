"""Unit tests for benchmark_impl aligned with grounding specifications."""

import importlib
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock
from pathlib import Path
from typing import Any

from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from support.lib import app_info, experiments
from autofab.parts.benchmark.lib import benchmark
from autofab.parts.benchmark.lib.benchmark_impl import (  # cleanroom: allow-private-import
    BenchmarkEvaluator,
    main,
    _provision_flight_scope,
    _teardown_flight_scope,
)


class BenchmarkImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()

    def test_model_spec_cost_computation(self) -> None:
        """CUJ: Computing financial cost across local, budget, and mid-tier rate cards."""
        evaluator = BenchmarkEvaluator()
        catalog = evaluator.get_model_catalog()

        # Tier 1 Local: $0
        qwen = catalog["qwen-moe-q6"]
        cost_qwen = qwen.compute_cost(uncached_in=50000, cached_in=150000, out=20000)
        self.assertEqual(cost_qwen, 0.0)

        # Tier 2 Budget: DeepSeek V4.1 ($0.15 uncached, $0.003 cached, $0.60 out per 1M)
        deepseek = catalog["deepseek-v41-flash"]
        # 1M uncached ($0.15) + 2M cached ($0.006) + 1M out ($0.60) = $0.756
        cost_ds = deepseek.compute_cost(
            uncached_in=1000000, cached_in=2000000, out=1000000
        )
        self.assertAlmostEqual(cost_ds, 0.756, places=4)

        # Tier 3 Mid-Tier: o3-mini ($1.10 uncached, $0.55 cached, $4.40 out per 1M)
        o3 = catalog["o3-mini"]
        cost_o3 = o3.compute_cost(uncached_in=1000000, cached_in=1000000, out=1000000)
        self.assertAlmostEqual(cost_o3, 6.05, places=4)

    def test_catalog_discovery(self) -> None:
        """CUJ: Resolving models and suites across capability tiers and archetypes."""
        evaluator = BenchmarkEvaluator()
        cat = evaluator.get_model_catalog()
        self.assertIn("qwen-moe-q6", cat)
        self.assertIn("deepseek-v41-flash", cat)
        self.assertIn("claude-3.7-sonnet", cat)
        self.assertIn("o3-mini", cat)
        self.assertIn("gemini-4-argon", cat)
        self.assertEqual(cat["qwen-moe-q6"].tier, 1)
        self.assertEqual(cat["deepseek-v41-flash"].tier, 2)
        self.assertEqual(cat["o3-mini"].tier, 3)
        self.assertEqual(cat["gemini-4-argon"].tier, 4)

        suite_cat = evaluator.get_suite_catalog()
        self.assertIn("dag_engine", suite_cat)
        self.assertIn("dag_engine_lite", suite_cat)
        self.assertIn("semver_solver", suite_cat)
        self.assertIn("dag-engine", suite_cat)
        self.assertIn("cpython", suite_cat)

        dag_units = suite_cat["dag_engine"]
        self.assertTrue(any(u.task_id == "dag_engine" for u in dag_units))

    def test_simulation_flight_execution(self) -> None:
        """CUJ: Executing a simulated benchmark flight and validating the trace schema."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            with patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": str(repo_root)}):
                evaluator = BenchmarkEvaluator()
                catalog = evaluator.get_model_catalog()
                model = catalog["qwen-moe-q6"]
                unit = evaluator.get_suite_catalog()["cpython"][0]

                record = evaluator.execute_flight(
                    model=model,
                    unit=unit,
                    rq="rq1",
                    harness="simulation",
                    simulate=True,
                )

                self.assertTrue(record.flight_id.startswith("flight_"))
                self.assertEqual(record.rq, "RQ1")
                self.assertEqual(record.model["identifier"], model.identifier)
                self.assertEqual(record.benchmark_unit["task_id"], unit.task_id)
                self.assertEqual(record.measurements.financial_cost_usd, 0.0)
                self.assertEqual(
                    record.measurements.role_rounds,
                    {"lib": 1, "test": 1, "qa": 1, "coverage": 1},
                )
                self.assertTrue(record.verification_outcomes.spec_linter_pass)
                self.assertGreater(record.verification_outcomes.unit_tests_passed, 0)

                # Test JSON trace serialization
                json_file_path = evaluator.save_flight_json(
                    record, str(repo_root / "logs")
                )
                json_file = Path(json_file_path)
                self.assertTrue(json_file.is_file())
                data = json.loads(json_file.read_text(encoding="utf-8"))
                self.assertEqual(data["flight_id"], record.flight_id)
                self.assertEqual(
                    data["measurements"]["outbound_tokens"],
                    record.measurements.outbound_tokens,
                )
                self.assertEqual(
                    data["measurements"]["role_rounds"],
                    {"lib": 1, "test": 1, "qa": 1, "coverage": 1},
                )

                # Test report generation
                report_md = evaluator.generate_report(
                    [record], output_path=str(repo_root / "reports" / "test.md")
                )
                self.assertIn(
                    f"{app_info.APP_TITLE} Empirical Benchmark Flight Report", report_md
                )
                self.assertIn(record.flight_id, report_md)
                self.assertIn("| Rounds |", report_md)
                self.assertIn("4 (coverage:1, lib:1, qa:1, test:1)", report_md)
                self.assertTrue((repo_root / "reports" / "test.md").is_file())

    def test_evaluator_singleton(self) -> None:
        """CUJ: Coordinating benchmark execution and CLI through the system service singleton."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            with patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": str(repo_root)}):
                with enter_phase(system, registry=self.registry) as scope:
                    evaluator = BenchmarkEvaluator()
                    cat = evaluator.get_model_catalog()
                    model = cat["deepseek-v41-flash"]
                    unit = evaluator.get_suite_catalog()["cpython"][0]

                    flight = evaluator.execute_flight(
                        model=model,
                        unit=unit,
                        rq="rq1",
                        harness="simulation",
                        simulate=True,
                    )
                    self.assertIsNotNone(flight)
                    self.assertEqual(flight.model["identifier"], model.identifier)

                    report = evaluator.generate_report([flight])
                    self.assertIn(model.identifier, report)

                    json_path = evaluator.save_flight_json(
                        flight, str(repo_root / "logs")
                    )
                    self.assertTrue(os.path.isfile(json_path))

                    # Test dry-run CLI execution
                    exit_code = evaluator.run_cli(
                        [
                            "--dry-run",
                            "--suite=cpython",
                            "--models=qwen-moe-q6",
                            "--units=1",
                        ]
                    )
                    self.assertEqual(exit_code, 0)

    def test_main_lifecycle_phase_execution(self) -> None:
        """CUJ: Executing CLI entrypoint through system lifecycle phase initialization."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            old_bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            try:
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = str(repo_root)
                exit_code = main(
                    argv=[
                        "--dry-run",
                        "--suite=cpython",
                        "--models=qwen-moe-q6",
                        "--units=1",
                    ],
                )
                self.assertEqual(exit_code, 0)
            finally:
                if old_bwd is None:
                    os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)
                else:
                    os.environ["BUILD_WORKSPACE_DIRECTORY"] = old_bwd

    def test_archive_flight_artifacts_and_drain(self) -> None:
        """CUJ: Archiving synthesized flight files to lib_<N>.py / test_<N>.py and draining unit workspaces."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            with patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": str(repo_root)}):
                evaluator = BenchmarkEvaluator()
                unit_dir = repo_root / "benchmarks" / "parts" / "dag_engine"
                lib_dir = unit_dir / "lib"
                tests_dir = unit_dir / "tests"
                lib_dir.mkdir(parents=True, exist_ok=True)
                tests_dir.mkdir(parents=True, exist_ok=True)

                (lib_dir / "dag_engine_impl.py").write_text(
                    "class DAG: pass\n", encoding="utf-8"
                )
                (tests_dir / "dag_engine_impl_test.py").write_text(
                    "def test_dag(): pass\n", encoding="utf-8"
                )

                results_dir = repo_root / "benchmarks" / "results"
                model = evaluator.get_model_catalog()["qwen-moe-q6"]
            unit = benchmark.BenchmarkUnit(
                suite="dag-engine",
                task_id="dag_engine",
                archetype="Graph Traversal / Wave Execution Engine",
                spec_loc=350,
                target_lib_loc=500,
                unit_dir="benchmarks/parts/dag_engine",
                target_address="//benchmarks/parts/dag_engine#dag_engine_impl",
                description="Generalized Concurrent DAG Wave Execution Engine",
            )
            measurements = benchmark.FlightMeasurements(
                inbound_tokens_uncached=1000,
                inbound_tokens_cached=2000,
                outbound_tokens=500,
                total_tokens=3500,
                financial_cost_usd=0.0,
                wall_clock_seconds=5.25,
                role_rounds={"lib": 2, "test": 1, "qa": 2, "coverage": 1},
            )
            outcomes = benchmark.VerificationOutcomes(
                spec_linter_pass=True,
                pyright_errors=0,
                unit_tests_passed=10,
                unit_tests_failed=0,
                line_coverage_pct=95.0,
                branch_coverage_pct=90.0,
            )
            record1 = benchmark.FlightRecord(
                flight_id="flight_test_001",
                timestamp="2026-10-19T20:00:00Z",
                rq="RQ1",
                model={
                    "identifier": model.identifier,
                    "tier": model.tier,
                    "provider": model.provider,
                    "default_harness": "omlx",
                },
                benchmark_unit={"task_id": unit.task_id, "suite": unit.suite},
                methodology=app_info.APP_NAME,
                stages_executed=["lib", "test"],
                measurements=measurements,
                verification_outcomes=outcomes,
            )

            # First run: should produce lib_1.py and test_1.py
            archived1 = evaluator.archive_flight_artifacts(
                record1, unit, results_dir=str(results_dir)
            )
            self.assertIsNotNone(archived1)
            assert archived1 is not None
            lib_p1, test_p1 = archived1
            self.assertTrue(os.path.isfile(lib_p1))
            self.assertTrue(os.path.isfile(test_p1))
            self.assertTrue(lib_p1.endswith("lib_1.py"))
            self.assertTrue(test_p1.endswith("test_1.py"))

            # Verify metrics comments in lib_1.py
            lib_content1 = Path(lib_p1).read_text(encoding="utf-8")
            self.assertIn(
                f"{app_info.APP_TITLE} Empirical Benchmark Flight Metrics", lib_content1
            )
            self.assertIn("Run Index: 1", lib_content1)
            self.assertIn("Flight ID: flight_test_001", lib_content1)
            self.assertIn(
                "Role Execution Rounds:   coverage: 1, lib: 2, qa: 2, test: 1 (Total: 6)",
                lib_content1,
            )
            self.assertIn("class DAG: pass", lib_content1)

            # Second run: should produce lib_2.py and test_2.py
            record2 = benchmark.FlightRecord(
                flight_id="flight_test_002",
                timestamp="2026-10-19T20:05:00Z",
                rq="RQ1",
                model=record1.model,
                benchmark_unit=record1.benchmark_unit,
                methodology=app_info.APP_NAME,
                stages_executed=["lib", "test"],
                measurements=measurements,
                verification_outcomes=outcomes,
            )
            archived2 = evaluator.archive_flight_artifacts(
                record2, unit, results_dir=str(results_dir)
            )
            self.assertIsNotNone(archived2)
            assert archived2 is not None
            lib_p2, test_p2 = archived2
            self.assertTrue(lib_p2.endswith("lib_2.py"))
            self.assertTrue(test_p2.endswith("test_2.py"))

            # Test draining: both lib and tests should be wiped clean
            self.assertTrue(lib_dir.is_dir())
            evaluator.drain_unit_workspace(unit)
            self.assertFalse(lib_dir.is_dir())
            self.assertFalse(tests_dir.is_dir())

    def test_dry_run_skips_archival(self) -> None:
        """CUJ: Verifying that dry-run mode skips writing to the results directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            old_bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            try:
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = str(repo_root)
                evaluator = BenchmarkEvaluator()
                cat = evaluator.get_model_catalog()
                model = cat["qwen-moe-q6"]
                unit = evaluator.get_suite_catalog()["cpython"][0]
                results_dir = repo_root / "benchmarks" / "results"

                record = evaluator.execute_flight(
                    model=model,
                    unit=unit,
                    rq="rq1",
                    harness="simulation",
                    dry_run=True,
                    results_dir=str(results_dir),
                )
                self.assertIsNotNone(record)
                self.assertFalse(results_dir.exists())
            finally:
                if old_bwd is None:
                    os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)
                else:
                    os.environ["BUILD_WORKSPACE_DIRECTORY"] = old_bwd

    def test_antigravity_transcript_harvesting(self) -> None:
        """CUJ: Harvesting telemetry and role rounds from Antigravity subagent session transcripts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            brain_dir = Path(tmp_dir) / "brain"
            coord_id = "11111111-1111-1111-1111-111111111111"
            worker1_id = "22222222-2222-2222-2222-222222222222"
            worker2_id = "33333333-3333-3333-3333-333333333333"

            coord_log_dir = brain_dir / coord_id / ".system_generated" / "logs"
            coord_log_dir.mkdir(parents=True, exist_ok=True)
            coord_transcript = coord_log_dir / "transcript.jsonl"
            coord_lines = [
                json.dumps(
                    {
                        "source": "USER",
                        "type": "USER_INPUT",
                        "content": f"Clean all dirty nodes in benchmarks using {app_info.APP_NAME}_coordinator.",
                    }
                ),
                json.dumps(
                    {
                        "source": "MODEL",
                        "type": "GENERIC",
                        "content": json.dumps(
                            [
                                {
                                    "role": f"{app_info.APP_TITLE} lib Worker",
                                    "conversationId": worker1_id,
                                },
                                {
                                    "role": f"{app_info.APP_TITLE} test Worker",
                                    "conversationId": worker2_id,
                                },
                            ]
                        ),
                    }
                ),
                json.dumps(
                    {
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 1000,
                        "cache_read_tokens": 5000,
                        "output_tokens": 200,
                    }
                ),
            ]
            coord_transcript.write_text("\n".join(coord_lines) + "\n", encoding="utf-8")

            w1_log_dir = brain_dir / worker1_id / ".system_generated" / "logs"
            w1_log_dir.mkdir(parents=True, exist_ok=True)
            # Worker 1 executes 3 PLANNER_RESPONSE steps across 2 dispatch waves (Round 1 and Round 2)
            w1_lines = [
                json.dumps(
                    {
                        "source": "SYSTEM",
                        "type": "SYSTEM_MESSAGE",
                        "content": f"You are an autonomous {app_info.APP_TITLE} 'lib' worker. Immediately run bin/get_work.",
                    }
                ),
                json.dumps(
                    {
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 1000,
                        "cache_read_tokens": 5000,
                        "output_tokens": 250,
                    }
                ),
                json.dumps(
                    {
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 1000,
                        "cache_read_tokens": 5000,
                        "output_tokens": 250,
                    }
                ),
                json.dumps(
                    {
                        "source": "SYSTEM",
                        "type": "SYSTEM_MESSAGE",
                        "content": "Ready nodes detected in global DAG. Immediately run bin/get_work.",
                    }
                ),
                json.dumps(
                    {
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 1000,
                        "cache_read_tokens": 5000,
                        "output_tokens": 250,
                    }
                ),
            ]
            (w1_log_dir / "transcript.jsonl").write_text(
                "\n".join(w1_lines) + "\n", encoding="utf-8"
            )

            w2_log_dir = brain_dir / worker2_id / ".system_generated" / "logs"
            w2_log_dir.mkdir(parents=True, exist_ok=True)
            w2_lines = [
                json.dumps(
                    {
                        "source": "SYSTEM",
                        "type": "SYSTEM_MESSAGE",
                        "content": f"You are an autonomous {app_info.APP_TITLE} 'test' worker for scope 'benchmarks'. Immediately run bin/get_work.",
                    }
                ),
                json.dumps(
                    {
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 1500,
                        "cache_read_tokens": 8000,
                        "output_tokens": 300,
                    }
                ),
            ]
            w2_transcript = w2_log_dir / "transcript.jsonl"
            w2_transcript.write_text("\n".join(w2_lines) + "\n", encoding="utf-8")
            # Ensure worker transcript has a newer mtime than coordinator transcript to verify coordinator prioritization
            os.utime(w2_transcript, (time.time() + 10.0, time.time() + 10.0))

            # Also create a parent caller conversation with a newer mtime containing the directive
            parent_id = "00000000-0000-0000-0000-000000000000"
            parent_log_dir = brain_dir / parent_id / ".system_generated" / "logs"
            parent_log_dir.mkdir(parents=True, exist_ok=True)
            parent_transcript = parent_log_dir / "transcript.jsonl"
            parent_lines = [
                json.dumps(
                    {
                        "source": "SYSTEM",
                        "type": "SYSTEM_MESSAGE",
                        "content": f"AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE for scope 'benchmarks': Clean all dirty nodes in benchmarks using {app_info.APP_NAME}_coordinator.",
                    }
                ),
                json.dumps(
                    {
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 99999,
                        "cache_read_tokens": 99999,
                        "output_tokens": 99999,
                    }
                ),
            ]
            parent_transcript.write_text(
                "\n".join(parent_lines) + "\n", encoding="utf-8"
            )
            os.utime(parent_transcript, (time.time() + 20.0, time.time() + 20.0))

            repo_root = Path(tmp_dir) / "repo"
            logs_dir = repo_root / "logs" / "benchmarks"
            logs_dir.mkdir(parents=True, exist_ok=True)
            flight_id = "flight_test_harvest_antigravity"
            flight_json = {
                "flight_id": flight_id,
                "timestamp": "2026-10-20T20:00:00+00:00",
                "rq": "RQ1",
                "model": {
                    "identifier": "qwen-moe-q6",
                    "tier": 1,
                    "provider": "ollama",
                    "default_harness": "antigravity",
                },
                "benchmark_unit": {
                    "suite": "test",
                    "task_id": "cpython_datetime",
                    "archetype": "cpython",
                    "spec_loc": 10,
                    "target_lib_loc": 10,
                    "unit_dir": "benchmarks/sample",
                },
                "methodology": app_info.APP_NAME,
                "stages_executed": ["lib", "test"],
                "measurements": {"wall_clock_seconds": 12.0},
                "verification_outcomes": {},
            }
            (logs_dir / f"{flight_id}.json").write_text(
                json.dumps(flight_json), encoding="utf-8"
            )

            with (
                patch.dict(
                    os.environ,
                    {
                        "BUILD_WORKSPACE_DIRECTORY": str(repo_root),
                        "ANTIGRAVITY_APP_DATA_DIR": str(tmp_dir),
                    },
                ),
                patch(
                    "autofab.parts.benchmark.lib.benchmark_impl.subprocess.run"
                ) as mock_run,
            ):
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "0 errors, 0 warnings"
                evaluator = BenchmarkEvaluator()
                record = evaluator.harvest_flight(flight_id)
                self.assertIsNotNone(record)
                assert record is not None
                m = record.measurements
                self.assertEqual(m.inbound_tokens_uncached, 5500)
                self.assertEqual(m.inbound_tokens_cached, 28000)
                self.assertEqual(m.outbound_tokens, 1250)
                self.assertEqual(m.role_rounds, {"lib": 2, "test": 1})
                self.assertNotIn("coordinator", m.role_rounds)

    def test_harvest_flight(self) -> None:
        """CUJ: Harvesting previously executed flight record and updating JSON and archived artifacts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            with patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": str(repo_root)}):
                evaluator = BenchmarkEvaluator()
                logs_dir = repo_root / "logs" / "benchmarks"
                logs_dir.mkdir(parents=True, exist_ok=True)

                unit = evaluator.get_suite_catalog()["cpython"][0]
                model = evaluator.get_model_catalog()["qwen-moe-q6"]

                flight_id = "flight_test_harvest_001"
                initial_json = {
                    "flight_id": flight_id,
                    "timestamp": "2026-10-20T20:00:00+00:00",
                    "rq": "RQ1",
                    "model": {
                        "identifier": model.identifier,
                        "tier": model.tier,
                        "provider": model.provider,
                        "default_harness": "loop",
                    },
                    "benchmark_unit": {
                        "suite": unit.suite,
                        "task_id": unit.task_id,
                        "archetype": unit.archetype,
                        "spec_loc": unit.spec_loc,
                        "target_lib_loc": unit.target_lib_loc,
                        "unit_dir": unit.unit_dir,
                    },
                    "methodology": app_info.APP_NAME,
                    "stages_executed": ["lib", "test"],
                    "measurements": {
                        "inbound_tokens_uncached": 0,
                        "inbound_tokens_cached": 0,
                        "outbound_tokens": 0,
                        "total_tokens": 0,
                        "financial_cost_usd": 0.0,
                        "wall_clock_seconds": 10.0,
                        "role_rounds": {},
                    },
                    "verification_outcomes": {
                        "spec_linter_pass": False,
                        "pyright_errors": 0,
                        "unit_tests_passed": 0,
                        "unit_tests_failed": 0,
                    },
                }
                (logs_dir / f"{flight_id}.json").write_text(
                    json.dumps(initial_json), encoding="utf-8"
                )

                record = evaluator.harvest_flight(flight_id)
                self.assertIsNotNone(record)
                assert record is not None
                self.assertEqual(record.flight_id, flight_id)

    def test_verification_gate_dynamic_pythonpath(self) -> None:
        """Scenario 5: Verification gate evaluates with dynamically assembled package and support paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            unit_dir = root / "parts" / "sample"
            lib_dir = unit_dir / "lib"
            lib_dir.mkdir(parents=True)
            (lib_dir / "sample.py").write_text(
                "def sample_func() -> int:\n    return 42\n", encoding="utf-8"
            )

            # Create a mock support directory under a constituent package
            sup_dir = root / "mock_pkg" / "support" / "lib"
            sup_dir.mkdir(parents=True)
            (sup_dir / "mock_mod.py").write_text("X = 1\n", encoding="utf-8")

            unit = benchmark.BenchmarkUnit(
                suite="test",
                task_id="sample",
                archetype="sample",
                spec_loc=10,
                target_lib_loc=10,
                unit_dir="parts/sample",
                target_address="//parts/sample#sample",
                description="Sample unit for testing",
            )

            flight_id = "flight_test_gate_eval"
            logs_dir = root / "logs" / "benchmarks"
            logs_dir.mkdir(parents=True, exist_ok=True)
            flight_json = {
                "flight_id": flight_id,
                "timestamp": "2026-10-20T20:00:00+00:00",
                "rq": "RQ1",
                "model": {
                    "identifier": "qwen-moe-q6",
                    "tier": 1,
                    "provider": "ollama",
                    "default_harness": "loop",
                },
                "benchmark_unit": {
                    "suite": unit.suite,
                    "task_id": unit.task_id,
                    "archetype": unit.archetype,
                    "spec_loc": unit.spec_loc,
                    "target_lib_loc": unit.target_lib_loc,
                    "unit_dir": unit.unit_dir,
                },
                "methodology": app_info.APP_NAME,
                "stages_executed": ["lib", "test"],
                "measurements": {"wall_clock_seconds": 5.0},
                "verification_outcomes": {},
            }
            (logs_dir / f"{flight_id}.json").write_text(
                json.dumps(flight_json), encoding="utf-8"
            )

            with patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": str(root)}):
                with patch(
                    "autofab.parts.benchmark.lib.benchmark_impl.subprocess.run"
                ) as mock_run:
                    mock_run.return_value.returncode = 0
                    mock_run.return_value.stdout = "0 errors, 0 warnings"
                    evaluator = BenchmarkEvaluator()
                    record = evaluator.harvest_flight(flight_id)
                    self.assertIsNotNone(record)
                    assert record is not None
                    outcomes = record.verification_outcomes
                    self.assertEqual(outcomes.pyright_errors, 0)
                    self.assertTrue(mock_run.called)
                    _, kwargs = mock_run.call_args
                    env = kwargs.get("env", {})
                    self.assertIn("PYTHONPATH", env)
                    self.assertIn(str(sup_dir), env["PYTHONPATH"])

    def test_flight_scope_provision_and_teardown(self) -> None:
        """CUJ: Provisioning an ephemeral flight scope directory and tearing it down after execution."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            orig_scope_dir = repo_root / "benchmarks" / "parts"
            orig_scope_dir.mkdir(parents=True, exist_ok=True)
            (orig_scope_dir / app_info.DEFAULT_CONFIG_FILE).write_text(
                'methodology = "//autofab_py"\n', encoding="utf-8"
            )
            (repo_root / "benchmarks" / "__init__.py").write_text("", encoding="utf-8")

            unit_dir = orig_scope_dir / "sample_part"
            (unit_dir / "high").mkdir(parents=True, exist_ok=True)
            (unit_dir / "high" / "sample.md").write_text("# sample", encoding="utf-8")
            (unit_dir / "lib").mkdir(parents=True, exist_ok=True)
            (unit_dir / "lib" / "sample.py").write_text("old code", encoding="utf-8")
            (unit_dir / "tests").mkdir(parents=True, exist_ok=True)
            (unit_dir / "tests" / "sample_test.py").write_text(
                "old test", encoding="utf-8"
            )

            unit = benchmark.BenchmarkUnit(
                suite="benchmarks",
                task_id="sample_part",
                archetype="sample",
                spec_loc=10,
                target_lib_loc=10,
                unit_dir="benchmarks/parts/sample_part",
                target_address="//benchmarks/parts/sample_part#sample",
                description="Sample unit for flight scope test",
            )

            flight_id = "flight_20261021_sample_part"
            (unit_dir / "high" / "sample.md").write_text(
                "import benchmarks.parts.foo\nfrom parts.foo import bar\n",
                encoding="utf-8",
            )
            flight_scope, flight_unit_dir = _provision_flight_scope(
                repo_root, unit, flight_id
            )

            self.assertEqual(flight_scope, "benchmark_1")
            self.assertTrue(flight_unit_dir.is_dir())
            self.assertTrue((repo_root / flight_scope / ".env").is_file())
            env_text = (repo_root / flight_scope / ".env").read_text(encoding="utf-8")
            self.assertIn("PYTHONFAULTHANDLER=1", env_text)
            self.assertIn("PRETENSE_TIMEOUT=90.0", env_text)
            self.assertTrue(
                (
                    repo_root / flight_scope / "parts" / app_info.DEFAULT_CONFIG_FILE
                ).is_file()
            )
            self.assertTrue((flight_unit_dir / "high" / "sample.md").is_file())
            rewritten_md = (flight_unit_dir / "high" / "sample.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("import benchmark_1.parts.foo", rewritten_md)
            self.assertIn("from benchmark_1.parts.foo import bar", rewritten_md)
            self.assertNotIn("benchmarks.", rewritten_md)
            self.assertNotIn("from parts.", rewritten_md)

            # Sequential allocation for concurrent flight: must allocate benchmark_2
            scope2, _ = _provision_flight_scope(repo_root, unit, "flight_2")
            self.assertEqual(scope2, "benchmark_2")

            # Pristine start: lib and tests in flight scope must be drained clean
            self.assertFalse((flight_unit_dir / "lib").is_dir())
            self.assertFalse((flight_unit_dir / "tests").is_dir())
            # Canonical original unit must NOT be touched or drained
            self.assertTrue((unit_dir / "lib" / "sample.py").is_file())
            self.assertTrue((unit_dir / "tests" / "sample_test.py").is_file())

            # Mock role workspace for this flight scope
            role_ws = (
                repo_root
                / app_info.DEFAULT_ROLE_WORKSPACES_CONTAINER
                / f"{app_info.APP_NAME}_lib_{flight_scope}"
            )
            role_ws.mkdir(parents=True, exist_ok=True)
            (role_ws / "dummy.txt").write_text("dummy", encoding="utf-8")

            # Teardown
            _teardown_flight_scope(repo_root, flight_scope)
            _teardown_flight_scope(repo_root, scope2)
            self.assertFalse((repo_root / flight_scope).is_dir())
            self.assertFalse((repo_root / scope2).is_dir())
            self.assertFalse(role_ws.is_dir())

            # Provision without any config in orig_scope_dir: guarantees configuration creation
            orig_no_cfg = repo_root / "unconfigured_scope" / "parts" / "sample"
            orig_no_cfg.mkdir(parents=True, exist_ok=True)
            (orig_no_cfg / "high").mkdir(parents=True, exist_ok=True)
            (orig_no_cfg / "high" / "sample.md").write_text(
                "# sample", encoding="utf-8"
            )
            unit_no_cfg = benchmark.BenchmarkUnit(
                suite="unconfigured_scope",
                task_id="sample",
                archetype="sample",
                spec_loc=10,
                target_lib_loc=10,
                unit_dir="unconfigured_scope/parts/sample",
                target_address="//unconfigured_scope/parts/sample#sample",
                description="Unit with no prior config",
            )
            scope3, _ = _provision_flight_scope(
                repo_root, unit_no_cfg, "flight_3", pretense=False
            )
            self.assertTrue(
                (repo_root / scope3 / app_info.DEFAULT_CONFIG_FILE).is_file()
            )
            self.assertTrue(
                (repo_root / scope3 / "parts" / app_info.DEFAULT_CONFIG_FILE).is_file()
            )
            _teardown_flight_scope(repo_root, scope3)

    def test_flight_scope_teardown_on_failure(self) -> None:
        """CUJ: Preserving failed flight scope as .failed with associated role workspaces on flight failure."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            flight_scope = "benchmark_1"
            flight_scope_dir = repo_root / flight_scope
            flight_scope_dir.mkdir(parents=True, exist_ok=True)
            (flight_scope_dir / "dirty_code.py").write_text(
                "print('failed')", encoding="utf-8"
            )

            # Mock role workspace in repo_root / DEFAULT_ROLE_WORKSPACES_CONTAINER
            role_ws = (
                repo_root
                / app_info.DEFAULT_ROLE_WORKSPACES_CONTAINER
                / f"{app_info.APP_NAME}_lib_{flight_scope}"
            )
            role_ws.mkdir(parents=True, exist_ok=True)
            (role_ws / "worker.log").write_text("traceback...", encoding="utf-8")

            # Mock role workspace in repo_root.parent / DEFAULT_ROLE_WORKSPACES_CONTAINER
            parent_role_ws = (
                repo_root.parent
                / app_info.DEFAULT_ROLE_WORKSPACES_CONTAINER
                / f"{app_info.APP_NAME}_pretense_{flight_scope}"
            )
            parent_role_ws.mkdir(parents=True, exist_ok=True)
            (parent_role_ws / "pretense_worker.log").write_text(
                "pretense error...", encoding="utf-8"
            )

            try:
                # Teardown with failure
                _teardown_flight_scope(repo_root, flight_scope, success=False)

                # Original flight scope directory must be relocated, not deleted
                self.assertFalse(flight_scope_dir.is_dir())
                failed_dir = repo_root / f"{flight_scope}.failed"
                self.assertTrue(failed_dir.is_dir())
                self.assertTrue((failed_dir / "dirty_code.py").is_file())

                # Role workspaces must be relocated under failed_dir / DEFAULT_ROLE_WORKSPACES_CONTAINER, NOT deleted
                failed_ws = (
                    failed_dir
                    / app_info.DEFAULT_ROLE_WORKSPACES_CONTAINER
                    / f"{app_info.APP_NAME}_lib_{flight_scope}"
                )
                self.assertTrue(failed_ws.is_dir())
                self.assertTrue((failed_ws / "worker.log").is_file())

                parent_failed_ws = (
                    failed_dir
                    / app_info.DEFAULT_ROLE_WORKSPACES_CONTAINER
                    / f"{app_info.APP_NAME}_pretense_{flight_scope}"
                )
                self.assertTrue(parent_failed_ws.is_dir())
                self.assertTrue((parent_failed_ws / "pretense_worker.log").is_file())
            finally:
                if parent_role_ws.is_dir():
                    shutil.rmtree(parent_role_ws, ignore_errors=True)

    def test_flight_scope_marks_clean_up_to_spec_qa(self) -> None:
        """CUJ: Provisioning an ephemeral flight scope marks specifications clean up to spec_qa."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            orig_scope_dir = repo_root / "benchmarks" / "parts"
            orig_scope_dir.mkdir(parents=True, exist_ok=True)
            (orig_scope_dir / app_info.DEFAULT_CONFIG_FILE).write_text(
                'methodology = "//autofab_py"\n', encoding="utf-8"
            )

            unit_dir = orig_scope_dir / "sample_part"
            (unit_dir / "high").mkdir(parents=True, exist_ok=True)
            (unit_dir / "high" / "sample.md").write_text("# sample", encoding="utf-8")

            unit = benchmark.BenchmarkUnit(
                suite="benchmarks",
                task_id="sample_part",
                archetype="sample",
                spec_loc=10,
                target_lib_loc=10,
                unit_dir="benchmarks/parts/sample_part",
                target_address="//benchmarks/parts/sample_part#sample",
                description="Sample unit for flight scope test",
            )

            with patch("subprocess.run") as mock_run:
                flight_id = "flight_20261021_sample_part"
                flight_scope, flight_unit_dir = _provision_flight_scope(
                    repo_root, unit, flight_id
                )
                mock_run.assert_called_once()
                args, kwargs = mock_run.call_args
                cmd = args[0]
                self.assertEqual(cmd[:4], ["uv", "run", "autofab", "mark-clean"])
                self.assertEqual(cmd[4], flight_scope)
                self.assertIn("--up-to-role", cmd)
                self.assertIn("spec_qa", cmd)

    def test_archive_autofab_event_log(self) -> None:
        """CUJ: Archiving Autofab event log alongside synthesized flight artifacts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            with patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": str(repo_root)}):
                evaluator = BenchmarkEvaluator()
                unit_dir = repo_root / "benchmarks" / "parts" / "dag_engine"
                lib_dir = unit_dir / "lib"
                tests_dir = unit_dir / "tests"
                lib_dir.mkdir(parents=True, exist_ok=True)
                tests_dir.mkdir(parents=True, exist_ok=True)
                (lib_dir / "dag_engine.py").write_text(
                    "class DAG: pass\n", encoding="utf-8"
                )
                (tests_dir / "dag_engine_test.py").write_text(
                    "def test_dag(): pass\n", encoding="utf-8"
                )

                # Create event log in the unit parent (parts directory)
                (repo_root / "benchmarks" / app_info.DEFAULT_LOG_FILE).write_text(
                    "[CHANGE] lib/dag_engine.py: Implemented DAG\n", encoding="utf-8"
                )

                results_dir = repo_root / "benchmarks" / "results"
                model = evaluator.get_model_catalog()["qwen-moe-q6"]
                unit = benchmark.BenchmarkUnit(
                    suite="dag-engine",
                    task_id="dag_engine",
                    archetype="Graph Traversal",
                    spec_loc=350,
                    target_lib_loc=500,
                    unit_dir="benchmarks/parts/dag_engine",
                    target_address="//benchmarks/parts/dag_engine#dag_engine",
                    description="DAG Engine",
                )
                record = benchmark.FlightRecord(
                    flight_id="flight_test_log_archive",
                    timestamp="2026-10-21T21:00:00Z",
                    rq="RQ1",
                    model={
                        "identifier": model.identifier,
                        "tier": model.tier,
                        "provider": model.provider,
                        "default_harness": "loop",
                    },
                    benchmark_unit={"task_id": unit.task_id, "suite": unit.suite},
                    methodology=app_info.APP_NAME,
                    stages_executed=["lib", "test"],
                    measurements=benchmark.FlightMeasurements(),
                    verification_outcomes=benchmark.VerificationOutcomes(
                        spec_linter_pass=True,
                        pyright_errors=0,
                        unit_tests_passed=10,
                        unit_tests_failed=0,
                    ),
                )

                archived = evaluator.archive_flight_artifacts(
                    record, unit, results_dir=str(results_dir)
                )
                self.assertIsNotNone(archived)
                log_archive = (
                    results_dir
                    / unit.task_id
                    / f"{model.identifier.replace('/', '_')}"
                    / f"{app_info.APP_NAME}_1.log"
                )
                self.assertTrue(log_archive.is_file())
                self.assertIn("[CHANGE]", log_archive.read_text(encoding="utf-8"))

    def test_archive_flight_artifacts_skips_on_failure(self) -> None:
        """CUJ: Archiving must skip when flight verification fails or files are missing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            with patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": str(repo_root)}):
                evaluator = BenchmarkEvaluator()
                unit = benchmark.BenchmarkUnit(
                    suite="cpython",
                    task_id="dag_engine",
                    archetype="Graph",
                    spec_loc=200,
                    target_lib_loc=500,
                    unit_dir="benchmarks/parts/dag_engine",
                    target_address="//benchmarks/parts/dag_engine#lib",
                    description="DAG Engine",
                )
                results_dir = repo_root / "results"

                # Case 1: Missing source files
                record = benchmark.FlightRecord(
                    flight_id="flight_fail_1",
                    timestamp="2026-10-21T21:00:00Z",
                    rq="RQ1",
                    model={
                        "identifier": "test-model",
                        "tier": 1,
                        "default_harness": "loop",
                    },
                    benchmark_unit={"task_id": unit.task_id, "suite": unit.suite},
                    methodology=app_info.APP_NAME,
                    stages_executed=["lib", "test"],
                    measurements=benchmark.FlightMeasurements(),
                    verification_outcomes=benchmark.VerificationOutcomes(
                        spec_linter_pass=True,
                        unit_tests_passed=10,
                        unit_tests_failed=0,
                        pyright_errors=0,
                    ),
                )
                self.assertIsNone(
                    evaluator.archive_flight_artifacts(
                        record, unit, results_dir=str(results_dir)
                    )
                )
                self.assertFalse(results_dir.exists())

                # Populate source files
                lib_dir = repo_root / "benchmarks" / "parts" / "dag_engine" / "lib"
                tests_dir = repo_root / "benchmarks" / "parts" / "dag_engine" / "tests"
                lib_dir.mkdir(parents=True, exist_ok=True)
                tests_dir.mkdir(parents=True, exist_ok=True)
                (lib_dir / "dag_engine.py").write_text("# lib", encoding="utf-8")
                (tests_dir / "dag_engine_test.py").write_text(
                    "# test", encoding="utf-8"
                )

                # Case 2: Unit tests failed
                record.verification_outcomes.unit_tests_failed = 1
                self.assertIsNone(
                    evaluator.archive_flight_artifacts(
                        record, unit, results_dir=str(results_dir)
                    )
                )
                self.assertFalse(results_dir.exists())

                # Case 3: Pyright errors
                record.verification_outcomes.unit_tests_failed = 0
                record.verification_outcomes.pyright_errors = 2
                self.assertIsNone(
                    evaluator.archive_flight_artifacts(
                        record, unit, results_dir=str(results_dir)
                    )
                )
                self.assertFalse(results_dir.exists())

                # Case 4: Zero passing unit tests
                record.verification_outcomes.pyright_errors = 0
                record.verification_outcomes.unit_tests_passed = 0
                self.assertIsNone(
                    evaluator.archive_flight_artifacts(
                        record, unit, results_dir=str(results_dir)
                    )
                )
                self.assertFalse(results_dir.exists())

    def test_antigravity_flight_active_flight_and_dispatch(self) -> None:
        """Verifies Antigravity flight passes --antigravity-dispatch and manages active_flight.json."""
        from unittest.mock import patch, MagicMock

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / "parts" / app_info.DEFAULT_CONFIG_FILE).parent.mkdir(
                parents=True, exist_ok=True
            )
            (repo_root / "parts" / app_info.DEFAULT_CONFIG_FILE).write_text(
                f'methodology = "{app_info.APP_NAME}"\n', encoding="utf-8"
            )
            (repo_root / "autofab" / "parts" / "dag_engine" / "high").mkdir(
                parents=True, exist_ok=True
            )
            (repo_root / "autofab" / "parts" / "dag_engine" / "lib").mkdir(
                parents=True, exist_ok=True
            )
            (repo_root / "autofab" / "parts" / "dag_engine" / "tests").mkdir(
                parents=True, exist_ok=True
            )
            (
                repo_root
                / "autofab"
                / "parts"
                / "dag_engine"
                / "high"
                / "dag_engine.md"
            ).write_text("# Spec\n", encoding="utf-8")

            evaluator = BenchmarkEvaluator()
            evaluator._repo_root = repo_root

            model = evaluator.get_model_catalog()["gemini-flash"]
            unit = benchmark.BenchmarkUnit(
                suite="dag-engine",
                task_id="dag_engine",
                archetype="dag_engine",
                spec_loc=200,
                target_lib_loc=300,
                unit_dir=str(repo_root / "autofab" / "parts" / "dag_engine"),
                target_address="//autofab/parts/dag_engine:dag_engine",
                description="Generalized DAG engine",
            )

            dispatched_cmds = []

            def fake_subprocess_run(cmd, *args, **kwargs):
                dispatched_cmds.append(cmd)
                return MagicMock(
                    returncode=0,
                    stdout="AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE\n",
                    stderr="",
                )

            with patch("subprocess.run", side_effect=fake_subprocess_run):
                record = evaluator.execute_flight(
                    model=model,
                    unit=unit,
                    rq="rq1",
                    harness="antigravity",
                    wait_for_convergence=False,
                    antigravity_dispatch="message",
                )
                self.assertIsNotNone(record)
                clean_cmd = next(
                    (c for c in dispatched_cmds if len(c) > 1 and "clean" in c), None
                )
                self.assertIsNotNone(clean_cmd)
                assert clean_cmd is not None
                self.assertIn("--antigravity-dispatch", clean_cmd)
                self.assertIn("message", clean_cmd)
                self.assertFalse(
                    (
                        Path(app_info.resolve_state_dir(str(repo_root)))
                        / "active_flight.json"
                    ).exists()
                )

    def test_baseline_flight_simulation(self) -> None:
        """CUJ: Executing a simulated baseline flight and validating single-round metadata."""
        evaluator = BenchmarkEvaluator()
        catalog = evaluator.get_model_catalog()
        model = catalog["gemini-flash"]
        unit = evaluator.get_suite_catalog()["dag_engine"][0]

        record = evaluator.execute_flight(
            model=model,
            unit=unit,
            rq="rq1",
            harness="antigravity",
            simulate=True,
            baseline=True,
        )

        self.assertTrue(record.flight_id.endswith("_baseline"))
        self.assertEqual(record.methodology, "baseline")
        self.assertEqual(record.stages_executed, ["baseline"])
        self.assertEqual(record.measurements.role_rounds, {"baseline": 1})
        self.assertTrue(record.verification_outcomes.spec_linter_pass)
        self.assertGreater(record.verification_outcomes.unit_tests_passed, 0)

    def test_baseline_rejects_loop_harness(self) -> None:
        """CUJ: Enforcing rejection of loop harness for baseline benchmark flights."""
        evaluator = BenchmarkEvaluator()
        catalog = evaluator.get_model_catalog()
        model = catalog["gemini-flash"]
        unit = evaluator.get_suite_catalog()["dag_engine"][0]

        with self.assertRaises(ValueError) as ctx:
            evaluator.execute_flight(
                model=model,
                unit=unit,
                rq="rq1",
                harness="loop",
                simulate=True,
                baseline=True,
            )
        self.assertIn("loop", str(ctx.exception))
        self.assertIn("baseline", str(ctx.exception))

    def test_baseline_cli_rejection_of_loop(self) -> None:
        """CUJ: CLI immediately rejects deprecated loop harness."""
        evaluator = BenchmarkEvaluator()

        # 1. Explicit --harness=loop
        ret = evaluator.run_cli(["--baseline", "--harness=loop", "--dry-run"])
        self.assertEqual(ret, 1)

    def test_baseline_cli_successful_simulation(self) -> None:
        """CUJ: CLI dispatches simulated baseline flight with autonomous harness."""
        evaluator = BenchmarkEvaluator()
        ret = evaluator.run_cli(
            [
                "--baseline",
                "--suite=dag_engine",
                "--models=gemini-flash",
                "--harness=antigravity",
                "--simulation",
                "--units=1",
            ]
        )
        self.assertEqual(ret, 0)

    def test_baseline_artifact_archival_directory(self) -> None:
        """CUJ: Archiving successful baseline flight saves into -baseline folder with metadata header."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            evaluator = BenchmarkEvaluator()
            evaluator._repo_root = repo_root

            model = evaluator.get_model_catalog()["gemini-flash"]
            unit = benchmark.BenchmarkUnit(
                suite="dag_engine",
                task_id="dag_engine",
                unit_dir="parts/dag_engine",
                target_address="//parts/dag_engine#lib",
            )

            # Provision source files in temp unit dir
            unit_full = repo_root / "parts" / "dag_engine"
            lib_dir = unit_full / "lib"
            tests_dir = unit_full / "tests"
            lib_dir.mkdir(parents=True, exist_ok=True)
            tests_dir.mkdir(parents=True, exist_ok=True)
            (lib_dir / "dag_engine.py").write_text(
                "class DAG: pass\n", encoding="utf-8"
            )
            (tests_dir / "dag_engine_test.py").write_text(
                "def test_dag(): pass\n", encoding="utf-8"
            )

            measurements = benchmark.FlightMeasurements(
                inbound_tokens_uncached=1000,
                inbound_tokens_cached=2000,
                outbound_tokens=500,
                step_latencies_seconds=[1.2],
                wall_clock_seconds=5.0,
                role_rounds={"baseline": 1},
            )
            measurements.compute_totals(model)
            outcomes = benchmark.VerificationOutcomes(
                spec_linter_pass=True,
                pyright_errors=0,
                unit_tests_passed=10,
                unit_tests_failed=0,
                line_coverage_pct=95.0,
                branch_coverage_pct=90.0,
            )
            record = benchmark.FlightRecord(
                flight_id="flight_test_baseline_001",
                timestamp="2026-10-23T11:00:00Z",
                rq="RQ1",
                model={
                    "identifier": model.identifier,
                    "tier": model.tier,
                    "default_harness": "antigravity",
                },
                benchmark_unit={"task_id": unit.task_id, "suite": unit.suite},
                methodology="baseline",
                stages_executed=["baseline"],
                measurements=measurements,
                verification_outcomes=outcomes,
            )

            res = evaluator.archive_flight_artifacts(record, unit)
            self.assertIsNotNone(res)
            assert res is not None
            lib_dest, test_dest = res
            self.assertIn("gemini-flash-baseline", lib_dest)
            lib_content = Path(lib_dest).read_text(encoding="utf-8")
            self.assertIn("Methodology: baseline", lib_content)
            self.assertIn(
                "Role Execution Rounds:   baseline: 1 (Total: 1)", lib_content
            )

    def test_baseline_flight_prompt_includes_low_spec(self) -> None:
        """CUJ: Baseline flight dispatches unified clean command targeting the baseline fused role."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            evaluator = BenchmarkEvaluator()
            evaluator._repo_root = repo_root

            model = evaluator.get_model_catalog()["gemini-flash"]
            unit = benchmark.BenchmarkUnit(
                suite="dag_engine",
                task_id="dag_engine",
                unit_dir="parts/dag_engine",
                target_address="//parts/dag_engine#lib",
            )

            # Provision source low-level spec in unit dir
            unit_full = repo_root / "parts" / "dag_engine"
            low_dir = unit_full / "low"
            low_dir.mkdir(parents=True, exist_ok=True)
            (low_dir / "dag_engine.pyi").write_text(
                "class DAG: ...\n", encoding="utf-8"
            )

            dispatched_cmds = []

            def fake_subprocess_run(cmd, *args, **kwargs):
                dispatched_cmds.append(cmd)
                return MagicMock(
                    returncode=0,
                    stdout="AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE\n",
                    stderr="",
                )

            with (
                mock.patch("subprocess.run", side_effect=fake_subprocess_run),
                mock.patch(
                    "autofab.parts.benchmark.lib.benchmark_impl._VerificationGate.evaluate"
                ) as mock_gate,
                mock.patch(
                    "autofab.parts.benchmark.lib.benchmark_impl._LogHarvester.harvest_from_antigravity",
                    return_value=(100, 200, 50, [1.0], {"baseline": 1}),
                ),
            ):
                mock_gate.return_value = benchmark.VerificationOutcomes(
                    spec_linter_pass=True,
                    pyright_errors=0,
                    unit_tests_passed=5,
                    unit_tests_failed=0,
                )
                record = evaluator.execute_flight(
                    model=model,
                    unit=unit,
                    rq="RQ1",
                    harness="antigravity",
                    baseline=True,
                    wait_for_convergence=False,
                    antigravity_dispatch="none",
                )

            clean_cmd = next(
                (c for c in dispatched_cmds if len(c) > 1 and "clean" in c), None
            )
            self.assertIsNotNone(clean_cmd)
            assert clean_cmd is not None
            self.assertIn("--role", clean_cmd)
            self.assertIn("baseline", clean_cmd)
            self.assertIn("--baseline", clean_cmd)
            self.assertEqual(record.methodology, "baseline")
            self.assertEqual(record.stages_executed, ["baseline"])

    def test_antigravity_baseline_transcript_harvesting(self) -> None:
        """CUJ: Harvesting baseline worker subagent transcript with cache_read_tokens and ignoring parent caller transcript."""
        from autofab.parts.benchmark.lib.benchmark_impl import (  # cleanroom: allow-private-import
            _LogHarvester,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            brain_dir = Path(tmp_dir) / "brain"
            parent_id = "00000000-0000-0000-0000-000000000001"
            worker_id = "00000000-0000-0000-0000-000000000002"

            w_log_dir = brain_dir / worker_id / ".system_generated" / "logs"
            w_log_dir.mkdir(parents=True, exist_ok=True)
            w_transcript = w_log_dir / "transcript.jsonl"
            w_lines = [
                json.dumps(
                    {
                        "source": "SYSTEM",
                        "type": "SYSTEM_MESSAGE",
                        "content": "You are an autonomous software developer working in scope 'benchmark_1'.",
                    }
                ),
                json.dumps(
                    {
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 2000,
                        "cache_read_tokens": 10000,
                        "output_tokens": 500,
                        "duration_ms": 1500,
                    }
                ),
            ]
            w_transcript.write_text("\n".join(w_lines) + "\n", encoding="utf-8")

            p_log_dir = brain_dir / parent_id / ".system_generated" / "logs"
            p_log_dir.mkdir(parents=True, exist_ok=True)
            p_transcript = p_log_dir / "transcript.jsonl"
            p_lines = [
                json.dumps(
                    {
                        "source": "SYSTEM",
                        "type": "SYSTEM_MESSAGE",
                        "content": f"AUTONOMOUS ANTIGRAVITY BASELINE DIRECTIVE for benchmark_1: Invoke {app_info.APP_NAME}_baseline_worker.",
                    }
                ),
                json.dumps(
                    {
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 50000,
                        "cache_read_tokens": 50000,
                        "output_tokens": 5000,
                    }
                ),
            ]
            p_transcript.write_text("\n".join(p_lines) + "\n", encoding="utf-8")
            os.utime(p_transcript, (time.time() + 10.0, time.time() + 10.0))

            u_in, c_in, out_tok, lats, rounds = _LogHarvester.harvest_from_antigravity(
                brain_dir, 0.0, scope="benchmark_1", baseline=True
            )
            self.assertEqual(u_in, 2000)
            self.assertEqual(c_in, 10000)
            self.assertEqual(out_tok, 500)
            self.assertEqual(lats, [1.5])
            self.assertEqual(rounds, {"baseline": 1})
            self.assertTrue(
                _LogHarvester._is_antigravity_baseline_complete(
                    brain_dir, 0.0, scope="benchmark_1"
                )
            )

    def test_antigravity_coordinator_and_workers_harvesting(self) -> None:
        """CUJ: Harvesting telemetry across coordinator and role worker subagent transcripts."""
        from autofab.parts.benchmark.lib.benchmark_impl import (  # cleanroom: allow-private-import
            _LogHarvester,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            brain_dir = Path(tmp_dir) / "brain"
            coord_id = "00000000-0000-0000-0000-000000000010"
            worker1_id = "00000000-0000-0000-0000-000000000011"
            worker2_id = "00000000-0000-0000-0000-000000000012"

            # Coordinator transcript includes invoke_subagent prompt referencing role worker
            c_log_dir = brain_dir / coord_id / ".system_generated" / "logs"
            c_log_dir.mkdir(parents=True, exist_ok=True)
            c_transcript = c_log_dir / "transcript.jsonl"
            c_lines = [
                json.dumps(
                    {
                        "step_index": 0,
                        "source": "SYSTEM",
                        "type": "SYSTEM_MESSAGE",
                        "content": f"Clean all dirty nodes in benchmark_1 using {app_info.APP_NAME}_coordinator.",
                    }
                ),
                json.dumps(
                    {
                        "step_index": 1,
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 1000,
                        "cache_read_tokens": 2000,
                        "output_tokens": 100,
                    }
                ),
                json.dumps(
                    {
                        "step_index": 2,
                        "source": "MODEL",
                        "type": "GENERIC",
                        "content": f'Created the following subagents:\n{{"conversationId": "{worker1_id}"}}\n{{"conversationId": "{worker2_id}"}}',
                    }
                ),
                json.dumps(
                    {
                        "step_index": 3,
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 500,
                        "cache_read_tokens": 1000,
                        "output_tokens": 50,
                        "tool_calls": [
                            {
                                "name": "invoke_subagent",
                                "args": {
                                    "Prompt": f"You are an autonomous {app_info.APP_TITLE} 'lib' worker for scope 'benchmark_1'."
                                },
                            }
                        ],
                    }
                ),
            ]
            c_transcript.write_text("\n".join(c_lines) + "\n", encoding="utf-8")

            # Worker 1: lib
            w1_log_dir = brain_dir / worker1_id / ".system_generated" / "logs"
            w1_log_dir.mkdir(parents=True, exist_ok=True)
            w1_transcript = w1_log_dir / "transcript.jsonl"
            w1_lines = [
                json.dumps(
                    {
                        "step_index": 0,
                        "source": "SYSTEM",
                        "type": "SYSTEM_MESSAGE",
                        "content": f"You are an autonomous {app_info.APP_TITLE} 'lib' worker for scope 'benchmark_1'.",
                    }
                ),
                json.dumps(
                    {
                        "step_index": 1,
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 4000,
                        "cache_read_tokens": 8000,
                        "output_tokens": 300,
                    }
                ),
            ]
            w1_transcript.write_text("\n".join(w1_lines) + "\n", encoding="utf-8")

            # Worker 2: pretense
            w2_log_dir = brain_dir / worker2_id / ".system_generated" / "logs"
            w2_log_dir.mkdir(parents=True, exist_ok=True)
            w2_transcript = w2_log_dir / "transcript.jsonl"
            w2_lines = [
                json.dumps(
                    {
                        "step_index": 0,
                        "source": "SYSTEM",
                        "type": "SYSTEM_MESSAGE",
                        "content": f"You are an autonomous {app_info.APP_TITLE} 'pretense' worker for scope 'benchmark_1'.",
                    }
                ),
                json.dumps(
                    {
                        "step_index": 1,
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "input_tokens": 3000,
                        "cache_read_tokens": 6000,
                        "output_tokens": 200,
                    }
                ),
            ]
            w2_transcript.write_text("\n".join(w2_lines) + "\n", encoding="utf-8")

            u_in, c_in, out_tok, lats, rounds = _LogHarvester.harvest_from_antigravity(
                brain_dir, 0.0, scope="benchmark_1", baseline=False
            )
            # Total across coord (1500) + w1 (4000) + w2 (3000) = 8500
            self.assertEqual(u_in, 8500)
            # Total cached: coord (3000) + w1 (8000) + w2 (6000) = 17000
            self.assertEqual(c_in, 17000)
            # Total output: coord (150) + w1 (300) + w2 (200) = 650
            self.assertEqual(out_tok, 650)
            self.assertEqual(rounds, {"lib": 1, "pretense": 1})

    def test_baseline_pretense_simulation(self) -> None:
        """CUJ: Executing a simulated baseline flight with pretense enabled."""
        evaluator = BenchmarkEvaluator()
        catalog = evaluator.get_model_catalog()
        model = catalog["gemini-flash"]
        unit = evaluator.get_suite_catalog()["dag_engine"][0]

        record = evaluator.execute_flight(
            model=model,
            unit=unit,
            rq="rq1",
            harness="antigravity",
            simulate=True,
            baseline=True,
            pretense=True,
        )

        self.assertTrue(record.flight_id.endswith("_pretense_baseline"))
        self.assertEqual(record.methodology, "pretense_baseline")
        self.assertEqual(record.stages_executed, ["baseline"])
        self.assertEqual(record.measurements.role_rounds, {"baseline": 1})
        self.assertTrue(record.verification_outcomes.spec_linter_pass)
        self.assertGreater(record.verification_outcomes.unit_tests_passed, 0)

    def test_baseline_pretense_artifact_archival_directory(self) -> None:
        """CUJ: Archiving successful baseline pretense flight saves into -pretense-baseline folder with pretense_<N>.py."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            evaluator = BenchmarkEvaluator()
            evaluator._repo_root = repo_root

            model = evaluator.get_model_catalog()["gemini-flash"]
            unit = benchmark.BenchmarkUnit(
                suite="dag_engine",
                task_id="dag_engine",
                unit_dir="parts/dag_engine",
                target_address="//parts/dag_engine#lib",
            )

            unit_full = repo_root / "parts" / "dag_engine"
            lib_dir = unit_full / "lib"
            pretense_dir = unit_full / "pretense"
            lib_dir.mkdir(parents=True, exist_ok=True)
            pretense_dir.mkdir(parents=True, exist_ok=True)
            (lib_dir / "dag_engine.py").write_text(
                "class DAG: pass\n", encoding="utf-8"
            )
            (pretense_dir / "dag_engine_impl_pretense.py").write_text(
                "class TestDAGUnit: pass\n", encoding="utf-8"
            )

            measurements = benchmark.FlightMeasurements(
                inbound_tokens_uncached=1000,
                inbound_tokens_cached=2000,
                outbound_tokens=500,
                step_latencies_seconds=[1.2],
                wall_clock_seconds=5.0,
                role_rounds={"baseline": 1},
            )
            measurements.compute_totals(model)
            outcomes = benchmark.VerificationOutcomes(
                spec_linter_pass=True,
                pyright_errors=0,
                unit_tests_passed=10,
                unit_tests_failed=0,
                line_coverage_pct=95.0,
                branch_coverage_pct=90.0,
            )
            record = benchmark.FlightRecord(
                flight_id="flight_test_pretense_baseline_001",
                timestamp="2026-10-25T11:00:00Z",
                rq="RQ1",
                model={
                    "identifier": model.identifier,
                    "tier": model.tier,
                    "default_harness": "antigravity",
                },
                benchmark_unit={"task_id": unit.task_id, "suite": unit.suite},
                methodology="pretense_baseline",
                stages_executed=["baseline"],
                measurements=measurements,
                verification_outcomes=outcomes,
            )

            res = evaluator.archive_flight_artifacts(record, unit)
            self.assertIsNotNone(res)
            assert res is not None
            lib_dest, test_dest = res
            self.assertIn("gemini-flash-pretense-baseline", lib_dest)
            self.assertTrue(test_dest.endswith("pretense_1.py"))
            lib_content = Path(lib_dest).read_text(encoding="utf-8")
            self.assertIn("Methodology: pretense_baseline", lib_content)
            self.assertIn(
                "Role Execution Rounds:   baseline: 1 (Total: 1)", lib_content
            )

    def test_baseline_pretense_workspace_setup_and_scaffolding(self) -> None:
        """CUJ: Baseline pretense flight dispatches unified clean command targeting pretense_baseline fused role."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            evaluator = BenchmarkEvaluator()
            evaluator._repo_root = repo_root

            model = evaluator.get_model_catalog()["gemini-flash"]
            unit = benchmark.BenchmarkUnit(
                suite="dag_engine",
                task_id="dag_engine",
                unit_dir="parts/dag_engine",
                target_address="//parts/dag_engine#lib",
            )

            # Provision source low-level spec in unit dir
            unit_full = repo_root / "parts" / "dag_engine"
            low_dir = unit_full / "low"
            low_dir.mkdir(parents=True, exist_ok=True)
            (low_dir / "dag_engine.pyi").write_text(
                "class DAG: ...\n", encoding="utf-8"
            )

            # Provision guides in repo_root
            guides_dir = repo_root / "autofab_py" / "guides"
            guides_dir.mkdir(parents=True, exist_ok=True)
            (guides_dir / "pretense.md").write_text(
                "# Pretense Guide\n", encoding="utf-8"
            )
            (guides_dir / "low_to_lib.md").write_text(
                "# Low to Lib Guide\n", encoding="utf-8"
            )

            # Provision pretense runtime dir in repo_root
            (repo_root / "pretense").mkdir(parents=True, exist_ok=True)

            dispatched_cmds = []

            def fake_subprocess_run(cmd, *args, **kwargs):
                dispatched_cmds.append(cmd)
                return MagicMock(
                    returncode=0,
                    stdout="AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE\n",
                    stderr="",
                )

            with (
                mock.patch("subprocess.run", side_effect=fake_subprocess_run),
                mock.patch(
                    "autofab.parts.benchmark.lib.benchmark_impl._VerificationGate.evaluate"
                ) as mock_gate,
                mock.patch(
                    "autofab.parts.benchmark.lib.benchmark_impl._LogHarvester.harvest_from_antigravity",
                    return_value=(100, 200, 50, [1.0], {"baseline": 1}),
                ),
            ):
                mock_gate.return_value = benchmark.VerificationOutcomes(
                    spec_linter_pass=True,
                    pyright_errors=0,
                    unit_tests_passed=5,
                    unit_tests_failed=0,
                )
                record = evaluator.execute_flight(
                    model=model,
                    unit=unit,
                    rq="RQ1",
                    harness="antigravity",
                    baseline=True,
                    pretense=True,
                    wait_for_convergence=False,
                    antigravity_dispatch="none",
                )

            clean_cmd = next(
                (c for c in dispatched_cmds if len(c) > 1 and "clean" in c), None
            )
            self.assertIsNotNone(clean_cmd)
            assert clean_cmd is not None
            self.assertIn("--role", clean_cmd)
            self.assertIn("pretense_baseline", clean_cmd)
            self.assertIn("--baseline", clean_cmd)
            self.assertIn("--pretense", clean_cmd)
            self.assertEqual(record.methodology, "pretense_baseline")
            self.assertEqual(record.stages_executed, ["baseline"])

    def test_is_antigravity_baseline_complete_lifecycle(self) -> None:
        """Verifies _is_antigravity_baseline_complete requires candidate transcripts and conclusion."""
        from autofab.parts.benchmark.lib.benchmark_impl import (  # cleanroom: allow-private-import
            _LogHarvester,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            brain = Path(tmp_dir)
            t_start = 1000.0

            # 1. Empty brain dir -> False (worker hasn't started)
            self.assertFalse(
                _LogHarvester._is_antigravity_baseline_complete(
                    brain, t_start, scope="flight_1"
                )
            )

            # 2. Worker session started, but still running (tool_calls present)
            worker_dir = brain / "worker_conv_1" / ".system_generated" / "logs"
            worker_dir.mkdir(parents=True, exist_ok=True)
            t_file = worker_dir / "transcript.jsonl"
            t_file.write_text(
                json.dumps(
                    {
                        "type": "USER_INPUT",
                        "content": "You are an autonomous software developer working in scope 'flight_1'",
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "PLANNER_RESPONSE",
                        "tool_calls": [{"name": "run_command"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            os.utime(t_file, (1050.0, 1050.0))
            self.assertFalse(
                _LogHarvester._is_antigravity_baseline_complete(
                    brain, t_start, scope="flight_1"
                )
            )

            # 3. Worker session completed (final PLANNER_RESPONSE without tool calls)
            with open(t_file, "a", encoding="utf-8") as f:
                f.write(
                    json.dumps({"type": "PLANNER_RESPONSE", "content": "Work complete"})
                    + "\n"
                )
            os.utime(t_file, (1060.0, 1060.0))
            self.assertTrue(
                _LogHarvester._is_antigravity_baseline_complete(
                    brain, t_start, scope="flight_1"
                )
            )

    def test_dsh_baseline_workspace_configuration(self) -> None:
        """Verifies that DSH baseline workspace configuration creates dsh_patch.yml and AGENTS.md under agent_session."""
        with tempfile.TemporaryDirectory() as td:
            flight_scope_dir = Path(td)
            state_dir = Path(app_info.resolve_state_dir(str(flight_scope_dir)))
            state_dir.mkdir(parents=True, exist_ok=True)
            patch_file = state_dir / "dsh_patch.yml"

            dsh_asm = importlib.import_module("autofab.parts.dsh.lib.dsh_asm")
            dsh_asm.__initialize__()

            agent_sess_mod = importlib.import_module("autofab.parts.agent.lib.session")
            dsh_ws_mod = importlib.import_module("autofab.parts.dsh.lib.dsh_workspace")
            with enter_phase(agent_sess_mod.agent_session) as sess_scope:
                ws_cfg = sess_scope.get(dsh_ws_mod.DshWorkspaceConfigurer)
                rep = ws_cfg.configure_role_workspace(
                    workspace_dir=str(flight_scope_dir),
                    role_name="baseline",
                    model_name="deepseek-flash",
                )
                self.assertIsNotNone(rep)

            self.assertTrue(patch_file.exists())
            patch_text = patch_file.read_text(encoding="utf-8")
            self.assertIn("danger-full-access", patch_text)
            self.assertIn("deepseek-flash", patch_text)

            agents_file = flight_scope_dir / "AGENTS.md"
            self.assertTrue(agents_file.exists())

    def test_generate_report_status_and_failures(self) -> None:
        """CUJ: Formatting summary report with PASS and [FAILED] status indicators and failure diagnostics."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            evaluator = BenchmarkEvaluator()
            evaluator._repo_root = repo_root

            passing_record = benchmark.FlightRecord(
                flight_id="flight_pass",
                timestamp="2026-10-27T00:00:00Z",
                rq="RQ1",
                model={"identifier": "test-model", "tier": 1},
                benchmark_unit={"task_id": "task_pass"},
                methodology=app_info.APP_NAME,
                stages_executed=["lib", "test"],
                measurements=benchmark.FlightMeasurements(),
                verification_outcomes=benchmark.VerificationOutcomes(
                    spec_linter_pass=True,
                    pyright_errors=0,
                    unit_tests_passed=10,
                    unit_tests_failed=0,
                ),
            )
            failing_record = benchmark.FlightRecord(
                flight_id="flight_fail",
                timestamp="2026-10-27T00:00:00Z",
                rq="RQ1",
                model={"identifier": "test-model", "tier": 1},
                benchmark_unit={"task_id": "task_fail"},
                methodology="pretense",
                stages_executed=["lib", "pretense"],
                measurements=benchmark.FlightMeasurements(),
                verification_outcomes=benchmark.VerificationOutcomes(
                    spec_linter_pass=True,
                    pyright_errors=2,
                    unit_tests_passed=0,
                    unit_tests_failed=0,
                ),
            )

            report = evaluator.generate_report([passing_record, failing_record])
            self.assertIn("| Status |", report)
            self.assertIn("**PASS**", report)
            self.assertIn("**[FAILED]**", report)
            self.assertIn("Flight Failures & Diagnostics", report)
            self.assertIn("flight_fail", report)
            self.assertIn("0 unit tests passed", report)
            self.assertIn("2 pyright type error(s)", report)

    def test_run_cli_returns_one_on_flight_verification_failure(self) -> None:
        """CUJ: run_cli returns exit code 1 when an executed flight fails verification gates."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            evaluator = BenchmarkEvaluator()
            evaluator._repo_root = repo_root

            failing_flight = benchmark.FlightRecord(
                flight_id="flight_failed_eval",
                timestamp="2026-10-27T00:00:00Z",
                rq="RQ1",
                model={"identifier": "qwen-moe", "tier": 1},
                benchmark_unit={"task_id": "dag_engine"},
                methodology="pretense",
                stages_executed=["lib", "pretense"],
                measurements=benchmark.FlightMeasurements(),
                verification_outcomes=benchmark.VerificationOutcomes(
                    spec_linter_pass=True,
                    pyright_errors=0,
                    unit_tests_passed=0,
                    unit_tests_failed=0,
                ),
            )

            with patch.object(evaluator, "execute_flight", return_value=failing_flight):
                ret = evaluator.run_cli(
                    ["--suite=dag_engine", "--models=qwen-moe-q6", "--units=1"]
                )
                self.assertEqual(ret, 1)

    def test_run_cli_rejects_comma_separated_models(self) -> None:
        """Scenario 17: run_cli strictly rejects comma-separated model lists."""
        evaluator = BenchmarkEvaluator()
        ret_models = evaluator.run_cli(
            ["--dry-run", "--models=deepseek-flash,qwen-moe"]
        )
        self.assertEqual(ret_models, 1)

        ret_model = evaluator.run_cli(["--dry-run", "--model=deepseek-flash,qwen-moe"])
        self.assertEqual(ret_model, 1)

    def test_run_cli_accepts_single_model_via_model_flag(self) -> None:
        """Scenario 17: run_cli accepts single model target via --model or --models."""
        evaluator = BenchmarkEvaluator()
        ret_model = evaluator.run_cli(
            ["--dry-run", "--suite=cpython", "--model=deepseek-flash", "--units=1"]
        )
        self.assertEqual(ret_model, 0)

        ret_models = evaluator.run_cli(
            ["--dry-run", "--suite=cpython", "--models=deepseek-flash", "--units=1"]
        )
        self.assertEqual(ret_models, 0)

    def test_baseline_combined_simulation(self) -> None:
        """CUJ: Executing a simulated baseline flight with combined methodology."""
        evaluator = BenchmarkEvaluator()
        catalog = evaluator.get_model_catalog()
        model = catalog["gemini-flash"]
        unit = evaluator.get_suite_catalog()["dag_engine"][0]

        record = evaluator.execute_flight(
            model=model,
            unit=unit,
            rq="rq1",
            harness="antigravity",
            simulate=True,
            baseline=True,
            method="combined",
        )

        self.assertTrue(record.flight_id.endswith("_combined_baseline"))
        self.assertEqual(record.methodology, "combined_baseline")
        self.assertEqual(record.stages_executed, ["baseline"])
        self.assertEqual(record.measurements.role_rounds, {"baseline": 1})
        self.assertTrue(record.verification_outcomes.spec_linter_pass)
        self.assertGreater(record.verification_outcomes.unit_tests_passed, 0)

    def test_combined_non_baseline_simulation(self) -> None:
        """CUJ: Executing a simulated flight with combined methodology."""
        evaluator = BenchmarkEvaluator()
        catalog = evaluator.get_model_catalog()
        model = catalog["gemini-flash"]
        unit = evaluator.get_suite_catalog()["dag_engine"][0]

        record = evaluator.execute_flight(
            model=model,
            unit=unit,
            rq="rq1",
            harness="antigravity",
            simulate=True,
            baseline=False,
            method="combined",
        )

        self.assertTrue(record.flight_id.endswith("_combined"))
        self.assertEqual(record.methodology, "combined")
        self.assertIn("lib", record.stages_executed)
        self.assertIn("test", record.stages_executed)
        self.assertIn("pretense", record.stages_executed)
        self.assertTrue(record.verification_outcomes.spec_linter_pass)
        self.assertGreater(record.verification_outcomes.unit_tests_passed, 0)

    def test_baseline_combined_artifact_archival_directory(self) -> None:
        """CUJ: Archiving successful baseline combined flight saves into -combined-baseline folder with test_<N>.py and pretense_<N>.py."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            evaluator = BenchmarkEvaluator()
            evaluator._repo_root = repo_root

            model = evaluator.get_model_catalog()["gemini-flash"]
            unit = benchmark.BenchmarkUnit(
                suite="dag_engine",
                task_id="dag_engine",
                unit_dir="parts/dag_engine",
                target_address="//parts/dag_engine#lib",
            )

            unit_full = repo_root / "parts" / "dag_engine"
            lib_dir = unit_full / "lib"
            tests_dir = unit_full / "tests"
            pretense_dir = unit_full / "pretense"
            lib_dir.mkdir(parents=True, exist_ok=True)
            tests_dir.mkdir(parents=True, exist_ok=True)
            pretense_dir.mkdir(parents=True, exist_ok=True)
            (lib_dir / "dag_engine.py").write_text(
                "class DAG: pass\n", encoding="utf-8"
            )
            (tests_dir / "dag_engine_test.py").write_text(
                "def test_dag(): pass\n", encoding="utf-8"
            )
            (pretense_dir / "dag_engine_impl_pretense.py").write_text(
                "class TestDAGUnit: pass\n", encoding="utf-8"
            )

            measurements = benchmark.FlightMeasurements(
                inbound_tokens_uncached=1000,
                inbound_tokens_cached=2000,
                outbound_tokens=500,
                step_latencies_seconds=[1.2],
                wall_clock_seconds=5.0,
                role_rounds={"combined_baseline": 1},
            )
            measurements.compute_totals(model)
            outcomes = benchmark.VerificationOutcomes(
                spec_linter_pass=True,
                pyright_errors=0,
                unit_tests_passed=15,
                unit_tests_failed=0,
                line_coverage_pct=95.0,
                branch_coverage_pct=90.0,
            )
            record = benchmark.FlightRecord(
                flight_id="flight_test_combined_baseline_001",
                timestamp="2026-10-25T11:00:00Z",
                rq="RQ1",
                model={
                    "identifier": model.identifier,
                    "tier": model.tier,
                    "default_harness": "antigravity",
                },
                benchmark_unit={"task_id": unit.task_id, "suite": unit.suite},
                methodology="combined_baseline",
                stages_executed=["combined_baseline"],
                measurements=measurements,
                verification_outcomes=outcomes,
            )

            res = evaluator.archive_flight_artifacts(record, unit, method="combined")
            self.assertIsNotNone(res)
            assert res is not None
            lib_dest, test_dest = res
            self.assertIn("gemini-flash-combined-baseline", lib_dest)
            self.assertTrue(test_dest.endswith("test_1.py"))
            dest_dir = Path(lib_dest).parent
            self.assertTrue((dest_dir / "pretense_1.py").is_file())
            lib_content = Path(lib_dest).read_text(encoding="utf-8")
            self.assertIn("Methodology: combined_baseline", lib_content)

    def test_run_cli_method_and_aliases_parsing(self) -> None:
        """Scenario 18: run_cli accepts --method {standard, pretense, combined} and --standard, --pretense, --combined aliases."""
        evaluator = BenchmarkEvaluator()
        # --method options
        for flag in [
            "--method=standard",
            "--method=pretense",
            "--method=combined",
            "--standard",
            "--pretense",
            "--combined",
        ]:
            ret = evaluator.run_cli(
                [
                    "--dry-run",
                    "--suite=cpython",
                    "--model=deepseek-flash",
                    "--units=1",
                    flag,
                ]
            )
            self.assertEqual(ret, 0, f"Failed for flag: {flag}")

    def test_has_materialized_artifacts_combined(self) -> None:
        """Verifies _has_materialized_artifacts requires lib, test, and pretense when method is combined."""
        from autofab.parts.benchmark.lib.benchmark_impl import (
            _has_materialized_artifacts,
        )

        with tempfile.TemporaryDirectory() as td:
            u_dir = Path(td)
            (u_dir / "lib").mkdir()
            (u_dir / "lib" / "foo.py").write_text("class Foo: pass\n")
            self.assertFalse(_has_materialized_artifacts(u_dir, method="combined"))

            (u_dir / "tests").mkdir()
            (u_dir / "tests" / "foo_test.py").write_text("def test_foo(): pass\n")
            self.assertFalse(_has_materialized_artifacts(u_dir, method="combined"))
            self.assertTrue(_has_materialized_artifacts(u_dir, method="standard"))

            (u_dir / "pretense").mkdir()
            (u_dir / "pretense" / "foo_pretense.py").write_text(
                "class FooPretense: pass\n"
            )
            self.assertTrue(_has_materialized_artifacts(u_dir, method="combined"))
            self.assertTrue(_has_materialized_artifacts(u_dir, method="pretense"))

    def test_run_cli_dsh_web_flag(self) -> None:
        """Scenario 19: run_cli accepts --dsh-web and sets AUTOFAB_DSH_WEB environment."""
        evaluator = BenchmarkEvaluator()
        orig_env = os.environ.get("AUTOFAB_DSH_WEB")
        try:
            if "AUTOFAB_DSH_WEB" in os.environ:
                del os.environ["AUTOFAB_DSH_WEB"]
            ret = evaluator.run_cli(
                [
                    "--dry-run",
                    "--suite=cpython",
                    "--model=deepseek-flash",
                    "--units=1",
                    "--dsh-web",
                ]
            )
            self.assertEqual(ret, 0)
            self.assertEqual(os.environ.get("AUTOFAB_DSH_WEB"), "1")
        finally:
            if orig_env is not None:
                os.environ["AUTOFAB_DSH_WEB"] = orig_env
            elif "AUTOFAB_DSH_WEB" in os.environ:
                del os.environ["AUTOFAB_DSH_WEB"]

    def test_run_cli_dsh_desktop_flag(self) -> None:
        """Scenario 19: run_cli accepts --dsh-desktop and sets AUTOFAB_DSH_WEB environment to '0'."""
        evaluator = BenchmarkEvaluator()
        orig_env = os.environ.get("AUTOFAB_DSH_WEB")
        try:
            os.environ["AUTOFAB_DSH_WEB"] = "1"
            ret = evaluator.run_cli(
                [
                    "--dry-run",
                    "--suite=cpython",
                    "--model=deepseek-flash",
                    "--units=1",
                    "--dsh-desktop",
                ]
            )
            self.assertEqual(ret, 0)
            self.assertEqual(os.environ.get("AUTOFAB_DSH_WEB"), "0")
        finally:
            if orig_env is not None:
                os.environ["AUTOFAB_DSH_WEB"] = orig_env
            elif "AUTOFAB_DSH_WEB" in os.environ:
                del os.environ["AUTOFAB_DSH_WEB"]

    def test_run_cli_default_experiment_on_non_baseline(self) -> None:
        """Scenario 20: run_cli defaults active experiment to structured_blame for non-baseline flights."""
        evaluator = BenchmarkEvaluator()
        orig_env = os.environ.get("AUTOFAB_EXPERIMENT")
        try:
            if "AUTOFAB_EXPERIMENT" in os.environ:
                del os.environ["AUTOFAB_EXPERIMENT"]
            ret = evaluator.run_cli(
                ["--dry-run", "--suite=cpython", "--model=deepseek-flash", "--units=1"]
            )
            self.assertEqual(ret, 0)
            self.assertEqual(os.environ.get("AUTOFAB_EXPERIMENT"), "structured_blame")
        finally:
            experiments.clear_active_experiments()
            if orig_env is not None:
                os.environ["AUTOFAB_EXPERIMENT"] = orig_env
            elif "AUTOFAB_EXPERIMENT" in os.environ:
                del os.environ["AUTOFAB_EXPERIMENT"]

    def test_run_cli_no_experiment_flag(self) -> None:
        """Scenario 20: run_cli accepts --no-experiment to disable default experiment."""
        evaluator = BenchmarkEvaluator()
        orig_env = os.environ.get("AUTOFAB_EXPERIMENT")
        try:
            os.environ["AUTOFAB_EXPERIMENT"] = "structured_blame"
            ret = evaluator.run_cli(
                [
                    "--dry-run",
                    "--suite=cpython",
                    "--model=deepseek-flash",
                    "--units=1",
                    "--no-experiment",
                ]
            )
            self.assertEqual(ret, 0)
            self.assertNotIn("AUTOFAB_EXPERIMENT", os.environ)
        finally:
            experiments.clear_active_experiments()
            if orig_env is not None:
                os.environ["AUTOFAB_EXPERIMENT"] = orig_env
            elif "AUTOFAB_EXPERIMENT" in os.environ:
                del os.environ["AUTOFAB_EXPERIMENT"]

    def test_run_cli_baseline_does_not_default_experiment(self) -> None:
        """Scenario 20: run_cli does not default active experiment when --baseline is passed."""
        evaluator = BenchmarkEvaluator()
        orig_env = os.environ.get("AUTOFAB_EXPERIMENT")
        try:
            if "AUTOFAB_EXPERIMENT" in os.environ:
                del os.environ["AUTOFAB_EXPERIMENT"]
            ret = evaluator.run_cli(
                [
                    "--dry-run",
                    "--suite=cpython",
                    "--model=deepseek-flash",
                    "--units=1",
                    "--baseline",
                    "--harness=simulation",
                ]
            )
            self.assertEqual(ret, 0)
            self.assertNotIn("AUTOFAB_EXPERIMENT", os.environ)
        finally:
            experiments.clear_active_experiments()
            if orig_env is not None:
                os.environ["AUTOFAB_EXPERIMENT"] = orig_env
            elif "AUTOFAB_EXPERIMENT" in os.environ:
                del os.environ["AUTOFAB_EXPERIMENT"]

    def test_run_cli_disable_experiment_flag(self) -> None:
        """Scenario 20: run_cli accepts --disable_experiment to disable a specific default experiment."""
        evaluator = BenchmarkEvaluator()
        orig_env = os.environ.get("AUTOFAB_EXPERIMENT")
        try:
            ret = evaluator.run_cli(
                [
                    "--dry-run",
                    "--suite=cpython",
                    "--model=deepseek-flash",
                    "--units=1",
                    "--disable_experiment=structured_blame",
                ]
            )
            self.assertEqual(ret, 0)
            self.assertNotIn("AUTOFAB_EXPERIMENT", os.environ)
        finally:
            experiments.clear_active_experiments()
            if orig_env is not None:
                os.environ["AUTOFAB_EXPERIMENT"] = orig_env
            elif "AUTOFAB_EXPERIMENT" in os.environ:
                del os.environ["AUTOFAB_EXPERIMENT"]

    @patch(
        "autofab.parts.benchmark.lib.benchmark_impl._cleanup_dsh_scope_conversations"
    )
    def test_flight_scope_provision_cleans_dsh_conversations(
        self, mock_cleanup: Any
    ) -> None:
        """Requirement: MUST delete existing DSH conversations matching scope when provisioning flight scope."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            orig_scope_dir = repo_root / "benchmarks" / "parts"
            orig_scope_dir.mkdir(parents=True, exist_ok=True)
            unit_dir = orig_scope_dir / "sample"
            (unit_dir / "high").mkdir(parents=True, exist_ok=True)
            (unit_dir / "high" / "sample.md").write_text("# Spec", encoding="utf-8")
            unit = benchmark.BenchmarkUnit(
                suite="sample_suite",
                task_id="sample_task",
                unit_dir="benchmarks/parts/sample",
                target_address="//benchmarks/parts/sample#sample",
                description="Sample unit for flight scope cleanup test",
            )
            scope, _ = _provision_flight_scope(repo_root, unit, "flight_cleanup_test")
            self.assertEqual(scope, "benchmark_1")
            mock_cleanup.assert_called_with("benchmark_1")


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-19T18:45:00Z
# LAST_CHANGED: 2026-11-09T23:45:00Z
# CHANGE: Test DSH conversation cleanup on flight scope provisioning
# SPEC_QA_AUDIT: 2026-10-19T19:35:00Z
# --- END CLEANROOM METADATA ---
