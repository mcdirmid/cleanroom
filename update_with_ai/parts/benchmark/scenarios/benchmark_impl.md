# Concrete scenarios for `benchmark_impl` (implementation)

## Scenario 1 — Model catalog lookup and tier resolution

Given: the system's benchmark evaluator initializes with the model catalog loaded from declarative configuration files.

1. The caller queries model `qwen-35b`.
   Observed: returns model specification with identifier `qwen3.6-35b-a3b`, tier 1, provider `omlx`, endpoint `http://localhost:8000/v1`, and zero token rates.

2. The caller queries model `deepseek-v41-flash`.
   Observed: returns model specification with identifier `deepseek-v4.1-flash`, tier 2, provider `deepseek`, and budget token rates.

## Scenario 2 — Suite catalog lookup and unit filtering

Given: the system's benchmark evaluator initializes with the canonical suite catalog discovered from benchmark parts.

1. The caller queries suite `dag_engine`.
   Observed: returns benchmark unit for `dag_engine`.

2. The caller queries suite `dag_engine_lite` or `semver_solver`.
   Observed: returns benchmark unit matching the discovered benchmark part.

## Scenario 3 — Simulated benchmark flight execution

Given: the benchmark evaluator executes a simulated flight for model `qwen3.6-35b-a3b` and unit `dag_engine` under `RQ1`.

1. The caller triggers flight execution with simulation mode enabled.
   Observed: returns a completed flight trace with scaled synthetic telemetry, zero cost, passing verification gates, and a valid ISO timestamp and flight identifier.

## Scenario 4 — Telemetry harvesting from runner logs

Given: a directory containing Cleanroom round log files `.cleanroom_round_*.log` (or `.cleanroom_turn_*.log`) reporting prompt tokens, cache percentages, output tokens, step durations, and role names.

1. The log harvester extracts telemetry from log files modified since flight start.
   Observed: accurately aggregates uncached inbound tokens, cached inbound tokens, outbound tokens, step latency float lists, and role execution round counts per role short name.

## Scenario 5 — Verification gate evaluation

Given: a benchmark unit directory containing high specifications, library code, and test suites.

1. The verification gate runs static and runtime checks with dynamically assembled package and support paths.
   Observed: reports spec linter pass status, pyright error count, and unit test pass/fail counts without missing import errors for repository support libraries.

## Scenario 6 — Flight trace JSON persistence

Given: a completed flight trace and a target logs directory.

1. The benchmark evaluator serializes the flight trace to disk.
   Observed: creates `<flight_id>.json` under `logs/benchmarks/` with formatted JSON content matching Section 7 schema.

## Scenario 7 — Markdown report generation

Given: a list of completed flight records and an optional output file path.

1. The benchmark evaluator generates the markdown report.
   Observed: produces a structured Markdown table summarizing flight identifier, model, tier, task, token metrics, cost, time, and test results.

## Scenario 8 — Flight artifact archival, scope isolation, and specification clean marking

Given: a completed flight for model `qwen-35b` on benchmark unit `dag_engine` with synthesized `lib/`, `tests/`, and `.cleanroom.log` files in the ephemeral flight scope.

1. The benchmark evaluator provisions the flight scope.
   Observed: allocates a concise unique flight scope directory (e.g. `benchmark_1`), copies the target unit directory and configuration into `<flight_scope>/parts/<unit>`, rewrites benchmark package imports to reference the flight scope package while disallowing bare parts imports, drains pre-existing `lib/` and `tests/` directories, and marks specifications clean up to `spec_qa` within the flight scope to isolate code and test generation.

2. The benchmark evaluator archives the artifacts.
   Observed: creates `lib_1.py`, `test_1.py`, and `cleanroom_1.log` under `benchmarks/results/dag_engine/qwen-35b+omlx/`, embedding flight telemetry comments in `lib_1.py`.

3. The caller checks the benchmark unit workspace and flight scope.
   Observed: the unit's `lib/` and `tests/` directories have been drained clean, and the ephemeral flight scope directory has been removed.

4. A second run is executed concurrently for the same model and benchmark.
   Observed: provisions a separate ephemeral flight scope, operates without cross-flight collision, and creates `lib_2.py`, `test_2.py`, and `cleanroom_2.log` in the results directory without colliding with run 1.

5. A third run fails verification gates (such as having failing unit tests or type errors).
   Observed: the benchmark evaluator skips artifact archival, avoids writing results files, and returns None.

## Scenario 9 — Dry-run execution bypasses artifact archival and draining

Given: a benchmark unit and a caller requesting a dry-run flight.

1. The benchmark evaluator executes the flight with dry-run mode enabled.
   Observed: returns a completed flight record with simulated parameters without writing files to the results directory or draining the unit workspace.

## Scenario 10 — Subagent session transcript harvesting for Antigravity harness

Given: an Antigravity brain directory containing a parent caller transcript, a coordinator subagent transcript, and worker subagent transcripts reporting planner responses with input tokens, cache read tokens, output tokens, and assigned role names, where the last worker subagent transcript has a newer modification timestamp than the coordinator transcript.

1. The log harvester extracts telemetry from the subagent transcripts for a flight commencing after a designated timestamp.
   Observed: identifies the coordinator subagent transcript rather than the newer worker transcript or parent caller transcript, accurately aggregates uncached inbound tokens, cached inbound tokens, and outbound tokens across coordinator and role worker conversations, excludes the coordinator from role execution rounds, and tallies role execution rounds per target role based on worker dispatch waves rather than planner response steps.

## Scenario 11 — Antigravity Desktop IPC coordination dispatch and active flight persistence

Given: an active Antigravity environment with `ANTIGRAVITY_CONVERSATION_ID` set.

1. The benchmark evaluator executes a flight under the `antigravity` harness.
   Observed: persists `.cleanroom/active_flight.json` recording flight metadata, invokes `bin/cleanroom clean` which dispatches coordination via `agentapi`, monitors DAG convergence, cleans up active flight state on completion, and evaluates verification gates.

## Scenario 12 — Traditional single-agent baseline flight execution and loop prohibition

Given: the benchmark evaluator and CLI argument parser.

1. The caller runs `cleanroom benchmark` with `--baseline` and `--harness loop`.
   Observed: rejects execution with an exit code of 1 and outputs an error indicating the loop harness is not supported for baseline benchmarks.

2. The caller runs a baseline flight in simulation mode or with an autonomous harness.
   Observed: the agent is provided with and instructed to inspect the low-level specification stubs (`low/*.pyi`), implement the two-file library structure in `lib/`, test `_impl.py`, and achieve 100% test coverage with opt-outs, returns a flight record with methodology `baseline`, stages executed `["baseline"]`, exactly one role round tallied under `baseline`, and archives passing artifacts under a baseline results destination.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-19T18:45:00Z
LAST_CHANGED: 2026-10-23T11:10:00Z
CHANGE: Add scenario 12 for baseline flight execution and loop harness prohibition
SPEC_QA_AUDIT: 2026-10-19T19:35:00Z
-->
