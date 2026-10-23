"""Unit tests for benchmark_impl aligned with grounding specifications."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.benchmark.lib import benchmark
from update_with_ai.parts.benchmark.lib.benchmark_impl import (
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
        cost_ds = deepseek.compute_cost(uncached_in=1000000, cached_in=2000000, out=1000000)
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
                self.assertEqual(record.measurements.role_rounds, {"lib": 1, "test": 1, "qa": 1, "coverage": 1})
                self.assertTrue(record.verification_outcomes.spec_linter_pass)
                self.assertGreater(record.verification_outcomes.unit_tests_passed, 0)

                # Test JSON trace serialization
                json_file_path = evaluator.save_flight_json(record, str(repo_root / "logs"))
                json_file = Path(json_file_path)
                self.assertTrue(json_file.is_file())
                data = json.loads(json_file.read_text(encoding="utf-8"))
                self.assertEqual(data["flight_id"], record.flight_id)
                self.assertEqual(data["measurements"]["outbound_tokens"], record.measurements.outbound_tokens)
                self.assertEqual(data["measurements"]["role_rounds"], {"lib": 1, "test": 1, "qa": 1, "coverage": 1})

                # Test report generation
                report_md = evaluator.generate_report([record], output_path=str(repo_root / "reports" / "test.md"))
                self.assertIn("Cleanroom Empirical Benchmark Flight Report", report_md)
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

                    json_path = evaluator.save_flight_json(flight, str(repo_root / "logs"))
                    self.assertTrue(os.path.isfile(json_path))

                    # Test dry-run CLI execution
                    exit_code = evaluator.run_cli(["--dry-run", "--suite=cpython", "--models=qwen-moe-q6", "--units=1"])
                    self.assertEqual(exit_code, 0)

    def test_main_lifecycle_phase_execution(self) -> None:
        """CUJ: Executing CLI entrypoint through system lifecycle phase initialization."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            old_bwd = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            try:
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = str(repo_root)
                exit_code = main(
                    argv=["--dry-run", "--suite=cpython", "--models=qwen-moe-q6", "--units=1"],
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

                (lib_dir / "dag_engine_impl.py").write_text("class DAG: pass\n", encoding="utf-8")
                (tests_dir / "dag_engine_impl_test.py").write_text("def test_dag(): pass\n", encoding="utf-8")

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
                methodology="cleanroom",
                stages_executed=["lib", "test"],
                measurements=measurements,
                verification_outcomes=outcomes,
            )

            # First run: should produce lib_1.py and test_1.py
            archived1 = evaluator.archive_flight_artifacts(record1, unit, results_dir=str(results_dir))
            self.assertIsNotNone(archived1)
            assert archived1 is not None
            lib_p1, test_p1 = archived1
            self.assertTrue(os.path.isfile(lib_p1))
            self.assertTrue(os.path.isfile(test_p1))
            self.assertTrue(lib_p1.endswith("lib_1.py"))
            self.assertTrue(test_p1.endswith("test_1.py"))

            # Verify metrics comments in lib_1.py
            lib_content1 = Path(lib_p1).read_text(encoding="utf-8")
            self.assertIn("Cleanroom Empirical Benchmark Flight Metrics", lib_content1)
            self.assertIn("Run Index: 1", lib_content1)
            self.assertIn("Flight ID: flight_test_001", lib_content1)
            self.assertIn("Role Execution Rounds:   coverage: 1, lib: 2, qa: 2, test: 1 (Total: 6)", lib_content1)
            self.assertIn("class DAG: pass", lib_content1)

            # Second run: should produce lib_2.py and test_2.py
            record2 = benchmark.FlightRecord(
                flight_id="flight_test_002",
                timestamp="2026-10-19T20:05:00Z",
                rq="RQ1",
                model=record1.model,
                benchmark_unit=record1.benchmark_unit,
                methodology="cleanroom",
                stages_executed=["lib", "test"],
                measurements=measurements,
                verification_outcomes=outcomes,
            )
            archived2 = evaluator.archive_flight_artifacts(record2, unit, results_dir=str(results_dir))
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
                json.dumps({"source": "USER", "type": "USER_INPUT", "content": "Clean all dirty nodes in benchmarks using cleanroom_coordinator."}),
                json.dumps({
                    "source": "MODEL",
                    "type": "GENERIC",
                    "content": json.dumps([
                        {"role": "Cleanroom lib Worker", "conversationId": worker1_id},
                        {"role": "Cleanroom test Worker", "conversationId": worker2_id},
                    ]),
                }),
                json.dumps({"source": "MODEL", "type": "PLANNER_RESPONSE", "input_tokens": 1000, "cache_read_tokens": 5000, "output_tokens": 200}),
            ]
            coord_transcript.write_text("\n".join(coord_lines) + "\n", encoding="utf-8")

            w1_log_dir = brain_dir / worker1_id / ".system_generated" / "logs"
            w1_log_dir.mkdir(parents=True, exist_ok=True)
            # Worker 1 executes 3 PLANNER_RESPONSE steps across 2 dispatch waves (Round 1 and Round 2)
            w1_lines = [
                json.dumps({"source": "SYSTEM", "type": "SYSTEM_MESSAGE", "content": "You are an autonomous Cleanroom 'lib' worker. Immediately run bin/get_work."}),
                json.dumps({"source": "MODEL", "type": "PLANNER_RESPONSE", "input_tokens": 1000, "cache_read_tokens": 5000, "output_tokens": 250}),
                json.dumps({"source": "MODEL", "type": "PLANNER_RESPONSE", "input_tokens": 1000, "cache_read_tokens": 5000, "output_tokens": 250}),
                json.dumps({"source": "SYSTEM", "type": "SYSTEM_MESSAGE", "content": "Ready nodes detected in global DAG. Immediately run bin/get_work."}),
                json.dumps({"source": "MODEL", "type": "PLANNER_RESPONSE", "input_tokens": 1000, "cache_read_tokens": 5000, "output_tokens": 250}),
            ]
            (w1_log_dir / "transcript.jsonl").write_text("\n".join(w1_lines) + "\n", encoding="utf-8")

            w2_log_dir = brain_dir / worker2_id / ".system_generated" / "logs"
            w2_log_dir.mkdir(parents=True, exist_ok=True)
            w2_lines = [
                json.dumps({"source": "SYSTEM", "type": "SYSTEM_MESSAGE", "content": "You are an autonomous Cleanroom 'test' worker. Immediately run bin/get_work."}),
                json.dumps({"source": "MODEL", "type": "PLANNER_RESPONSE", "input_tokens": 1500, "cache_read_tokens": 8000, "output_tokens": 300}),
            ]
            (w2_log_dir / "transcript.jsonl").write_text("\n".join(w2_lines) + "\n", encoding="utf-8")

            repo_root = Path(tmp_dir) / "repo"
            logs_dir = repo_root / "logs" / "benchmarks"
            logs_dir.mkdir(parents=True, exist_ok=True)
            flight_id = "flight_test_harvest_antigravity"
            flight_json = {
                "flight_id": flight_id,
                "timestamp": "2026-10-20T20:00:00+00:00",
                "rq": "RQ1",
                "model": {"identifier": "qwen-moe-q6", "tier": 1, "provider": "ollama", "default_harness": "antigravity"},
                "benchmark_unit": {
                    "suite": "test",
                    "task_id": "cpython_datetime",
                    "archetype": "cpython",
                    "spec_loc": 10,
                    "target_lib_loc": 10,
                    "unit_dir": "benchmarks/sample",
                },
                "methodology": "cleanroom",
                "stages_executed": ["lib", "test"],
                "measurements": {"wall_clock_seconds": 12.0},
                "verification_outcomes": {},
            }
            (logs_dir / f"{flight_id}.json").write_text(json.dumps(flight_json), encoding="utf-8")

            with patch.dict(os.environ, {
                "BUILD_WORKSPACE_DIRECTORY": str(repo_root),
                "ANTIGRAVITY_APP_DATA_DIR": str(tmp_dir),
            }), patch("update_with_ai.parts.benchmark.lib.benchmark_impl.subprocess.run") as mock_run:
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
                    "methodology": "cleanroom",
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
                (logs_dir / f"{flight_id}.json").write_text(json.dumps(initial_json), encoding="utf-8")

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
            (lib_dir / "sample.py").write_text("def sample_func() -> int:\n    return 42\n", encoding="utf-8")

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
                "model": {"identifier": "qwen-moe-q6", "tier": 1, "provider": "ollama", "default_harness": "loop"},
                "benchmark_unit": {
                    "suite": unit.suite,
                    "task_id": unit.task_id,
                    "archetype": unit.archetype,
                    "spec_loc": unit.spec_loc,
                    "target_lib_loc": unit.target_lib_loc,
                    "unit_dir": unit.unit_dir,
                },
                "methodology": "cleanroom",
                "stages_executed": ["lib", "test"],
                "measurements": {"wall_clock_seconds": 5.0},
                "verification_outcomes": {},
            }
            (logs_dir / f"{flight_id}.json").write_text(json.dumps(flight_json), encoding="utf-8")

            with patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": str(root)}):
                with patch("update_with_ai.parts.benchmark.lib.benchmark_impl.subprocess.run") as mock_run:
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
            (orig_scope_dir / "cleanroom.toml").write_text('methodology = "//update_python_with_ai"\n', encoding="utf-8")
            (repo_root / "benchmarks" / "__init__.py").write_text("", encoding="utf-8")

            unit_dir = orig_scope_dir / "sample_part"
            (unit_dir / "high").mkdir(parents=True, exist_ok=True)
            (unit_dir / "high" / "sample.md").write_text("# sample", encoding="utf-8")
            (unit_dir / "lib").mkdir(parents=True, exist_ok=True)
            (unit_dir / "lib" / "sample.py").write_text("old code", encoding="utf-8")
            (unit_dir / "tests").mkdir(parents=True, exist_ok=True)
            (unit_dir / "tests" / "sample_test.py").write_text("old test", encoding="utf-8")

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
            flight_scope, flight_unit_dir = _provision_flight_scope(repo_root, unit, flight_id)

            self.assertEqual(flight_scope, "benchmark_1")
            self.assertTrue(flight_unit_dir.is_dir())
            self.assertTrue((repo_root / flight_scope / "parts" / "cleanroom.toml").is_file())
            self.assertTrue((flight_unit_dir / "high" / "sample.md").is_file())
            rewritten_md = (flight_unit_dir / "high" / "sample.md").read_text(encoding="utf-8")
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
            role_ws = repo_root / "role_workspaces" / f"cleanroom_lib_{flight_scope}"
            role_ws.mkdir(parents=True, exist_ok=True)
            (role_ws / "dummy.txt").write_text("dummy", encoding="utf-8")

            # Teardown
            _teardown_flight_scope(repo_root, flight_scope)
            _teardown_flight_scope(repo_root, scope2)
            self.assertFalse((repo_root / flight_scope).is_dir())
            self.assertFalse((repo_root / scope2).is_dir())
            self.assertFalse(role_ws.is_dir())

    def test_flight_scope_marks_clean_up_to_spec_qa(self) -> None:
        """CUJ: Provisioning an ephemeral flight scope marks specifications clean up to spec_qa."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            orig_scope_dir = repo_root / "benchmarks" / "parts"
            orig_scope_dir.mkdir(parents=True, exist_ok=True)
            (orig_scope_dir / "cleanroom.toml").write_text('methodology = "//update_python_with_ai"\n', encoding="utf-8")

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
                flight_scope, flight_unit_dir = _provision_flight_scope(repo_root, unit, flight_id)
                mock_run.assert_called_once()
                args, kwargs = mock_run.call_args
                cmd = args[0]
                self.assertEqual(cmd[:4], ["uv", "run", "cleanroom", "mark-clean"])
                self.assertTrue(cmd[4].endswith("#spec_qa"))

    def test_archive_cleanroom_event_log(self) -> None:
        """CUJ: Archiving Cleanroom event log (.cleanroom.log) alongside synthesized flight artifacts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            with patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": str(repo_root)}):
                evaluator = BenchmarkEvaluator()
                unit_dir = repo_root / "benchmarks" / "parts" / "dag_engine"
                lib_dir = unit_dir / "lib"
                tests_dir = unit_dir / "tests"
                lib_dir.mkdir(parents=True, exist_ok=True)
                tests_dir.mkdir(parents=True, exist_ok=True)
                (lib_dir / "dag_engine.py").write_text("class DAG: pass\n", encoding="utf-8")
                (tests_dir / "dag_engine_test.py").write_text("def test_dag(): pass\n", encoding="utf-8")

                # Create .cleanroom.log in the unit parent (parts directory)
                (repo_root / "benchmarks" / ".cleanroom.log").write_text("[CHANGE] lib/dag_engine.py: Implemented DAG\n", encoding="utf-8")

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
                    model={"identifier": model.identifier, "tier": model.tier, "provider": model.provider, "default_harness": "loop"},
                    benchmark_unit={"task_id": unit.task_id, "suite": unit.suite},
                    methodology="cleanroom",
                    stages_executed=["lib", "test"],
                    measurements=benchmark.FlightMeasurements(),
                    verification_outcomes=benchmark.VerificationOutcomes(
                        spec_linter_pass=True,
                        pyright_errors=0,
                        unit_tests_passed=10,
                        unit_tests_failed=0,
                    ),
                )

                archived = evaluator.archive_flight_artifacts(record, unit, results_dir=str(results_dir))
                self.assertIsNotNone(archived)
                log_archive = results_dir / unit.task_id / f"{model.identifier.replace('/', '_')}+loop" / "cleanroom_1.log"
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
                    model={"identifier": "test-model", "tier": 1, "default_harness": "loop"},
                    benchmark_unit={"task_id": unit.task_id, "suite": unit.suite},
                    methodology="cleanroom",
                    stages_executed=["lib", "test"],
                    measurements=benchmark.FlightMeasurements(),
                    verification_outcomes=benchmark.VerificationOutcomes(
                        spec_linter_pass=True,
                        unit_tests_passed=10,
                        unit_tests_failed=0,
                        pyright_errors=0,
                    ),
                )
                self.assertIsNone(evaluator.archive_flight_artifacts(record, unit, results_dir=str(results_dir)))
                self.assertFalse(results_dir.exists())

                # Populate source files
                lib_dir = repo_root / "benchmarks" / "parts" / "dag_engine" / "lib"
                tests_dir = repo_root / "benchmarks" / "parts" / "dag_engine" / "tests"
                lib_dir.mkdir(parents=True, exist_ok=True)
                tests_dir.mkdir(parents=True, exist_ok=True)
                (lib_dir / "dag_engine.py").write_text("# lib", encoding="utf-8")
                (tests_dir / "dag_engine_test.py").write_text("# test", encoding="utf-8")

                # Case 2: Unit tests failed
                record.verification_outcomes.unit_tests_failed = 1
                self.assertIsNone(evaluator.archive_flight_artifacts(record, unit, results_dir=str(results_dir)))
                self.assertFalse(results_dir.exists())

                # Case 3: Pyright errors
                record.verification_outcomes.unit_tests_failed = 0
                record.verification_outcomes.pyright_errors = 2
                self.assertIsNone(evaluator.archive_flight_artifacts(record, unit, results_dir=str(results_dir)))
                self.assertFalse(results_dir.exists())

                # Case 4: Zero passing unit tests
                record.verification_outcomes.pyright_errors = 0
                record.verification_outcomes.unit_tests_passed = 0
                self.assertIsNone(evaluator.archive_flight_artifacts(record, unit, results_dir=str(results_dir)))
                self.assertFalse(results_dir.exists())

    def test_antigravity_flight_active_flight_and_dispatch(self) -> None:
        """Verifies Antigravity flight passes --antigravity-dispatch and manages active_flight.json."""
        from unittest.mock import patch, MagicMock
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            (repo_root / "parts" / "cleanroom.toml").parent.mkdir(parents=True, exist_ok=True)
            (repo_root / "parts" / "cleanroom.toml").write_text('methodology = "update_with_ai"\n', encoding="utf-8")
            (repo_root / "update_with_ai" / "parts" / "dag_engine" / "high").mkdir(parents=True, exist_ok=True)
            (repo_root / "update_with_ai" / "parts" / "dag_engine" / "lib").mkdir(parents=True, exist_ok=True)
            (repo_root / "update_with_ai" / "parts" / "dag_engine" / "tests").mkdir(parents=True, exist_ok=True)
            (repo_root / "update_with_ai" / "parts" / "dag_engine" / "high" / "dag_engine.md").write_text("# Spec\n", encoding="utf-8")

            evaluator = BenchmarkEvaluator()
            evaluator._repo_root = repo_root

            model = evaluator.get_model_catalog()["gemini-3.8-flash"]
            unit = benchmark.BenchmarkUnit(
                suite="dag-engine",
                task_id="dag_engine",
                archetype="dag_engine",
                spec_loc=200,
                target_lib_loc=300,
                unit_dir=str(repo_root / "update_with_ai" / "parts" / "dag_engine"),
                target_address="//update_with_ai/parts/dag_engine:dag_engine",
                description="Generalized DAG engine",
            )

            dispatched_cmds = []
            def fake_subprocess_run(cmd, *args, **kwargs):
                dispatched_cmds.append(cmd)
                return MagicMock(returncode=0, stdout="AUTONOMOUS ANTIGRAVITY COORDINATION DIRECTIVE\n", stderr="")

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
                clean_cmd = next((c for c in dispatched_cmds if len(c) > 1 and c[1] == "clean"), None)
                self.assertIsNotNone(clean_cmd)
                assert clean_cmd is not None
                self.assertIn("--antigravity-dispatch", clean_cmd)
                self.assertIn("message", clean_cmd)
                self.assertFalse((repo_root / ".cleanroom" / "active_flight.json").exists())


if __name__ == "__main__":
    unittest.main()

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-19T18:45:00Z
# LAST_CHANGED: 2026-10-21T14:15:00Z
# CHANGE: Test ephemeral flight scope provisioning, teardown, and event log archival
# SPEC_QA_AUDIT: 2026-10-19T19:35:00Z
# --- END CLEANROOM METADATA ---
