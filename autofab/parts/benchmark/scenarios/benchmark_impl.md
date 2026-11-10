# Concrete scenarios for `benchmark_impl` (implementation)

## Scenario 1 — Model catalog lookup and tier resolution

Given: the system's benchmark evaluator initializes with the model catalog loaded from declarative configuration files.

1. The caller queries model `qwen-35b`.
   Observed: returns model specification with identifier `qwen3.6-35b-a3b`, tier 1, provider `omlx`, endpoint `http://localhost:8000/v1`, and zero token rates.

1. The caller queries model `deepseek-v41-flash`.
   Observed: returns model specification with identifier `deepseek-v4.1-flash`, tier 2, provider `deepseek`, and budget token rates.

## Scenario 2 — Suite catalog lookup and unit filtering

Given: the system's benchmark evaluator initializes with the canonical suite catalog discovered from benchmark parts.

1. The caller queries suite `dag_engine`.
   Observed: returns benchmark unit for `dag_engine`.

1. The caller queries suite `dag_engine_lite` or `semver_solver`.
   Observed: returns benchmark unit matching the discovered benchmark part.

## Scenario 3 — Simulated benchmark flight execution

Given: the benchmark evaluator executes a simulated flight for model `qwen3.6-35b-a3b` and unit `dag_engine` under `RQ1`.

1. The caller triggers flight execution with simulation mode enabled.
   Observed: returns a completed flight trace with scaled synthetic telemetry, zero cost, passing verification gates, and a valid ISO timestamp and flight identifier.

## Scenario 4 — Telemetry harvesting from runner logs

Given: a directory containing Autofab round log files (e.g. `.autofab_round_*.log`) reporting prompt tokens, cache percentages, output tokens, step durations, and role names.

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
   Observed: produces a structured Markdown table summarizing flight identifier, model, tier, task, status (marking PASS or FAILED with defect diagnostics), token metrics, cost, time, and test results.

## Scenario 8 — Flight artifact archival, scope isolation, and specification clean marking

Given: a completed flight for model `qwen-35b` on benchmark unit `dag_engine` with synthesized `lib/`, `tests/`, and `.autofab.log` files in the ephemeral flight scope.

1. The benchmark evaluator provisions the flight scope.
   Observed: allocates a concise unique flight scope directory (e.g. `benchmark_1`), deletes all existing conversations that have `[benchmark_1]` in their titles from DeepSeek Harness, copies the target unit directory and configuration into `<flight_scope>/parts/<unit>`, explicitly configures the methodology pipeline as `pipeline = "pretense"` or `pipeline = "standard"`, rewrites benchmark package imports to reference the flight scope package while disallowing bare parts imports, drains pre-existing `lib/` and `tests/` directories, and marks specifications clean up to `spec_qa` within the flight scope to isolate code and test generation.

1. The benchmark evaluator archives the artifacts.
   Observed: creates `lib_1.py`, `test_1.py`, and `autofab_1.log` under `benchmarks/results/dag_engine/qwen-35b/`, embedding flight telemetry comments in `lib_1.py`.

1. The caller checks the benchmark unit workspace and flight scope.
   Observed: the unit's `lib/` and `tests/` directories have been drained clean, and the ephemeral flight scope directory has been removed.

1. A second run is executed concurrently for the same model and benchmark.
   Observed: provisions a separate ephemeral flight scope, operates without cross-flight collision, and creates `lib_2.py`, `test_2.py`, and `autofab_2.log` in the results directory without colliding with run 1.

1. A third run fails verification gates or fails DAG convergence (such as having failing unit tests, zero unit tests passed, type errors, or non-zero exit code).
   Observed: the benchmark evaluator skips artifact archival, preserves the flight scope directory as `<flight_scope>.failed`, preserves associated role workspaces under `<flight_scope>.failed/<role_workspaces>`, emits diagnostics to stderr, avoids writing results files, and returns 1 from `run_cli`.

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
   Observed: persists `.autofab/active_flight.json` recording flight metadata, invokes `autofab clean` which dispatches coordination via `agentapi`, monitors DAG convergence, cleans up active flight state on completion, and evaluates verification gates.

## Scenario 12 — Traditional single-agent baseline flight execution and loop prohibition

Given: the benchmark evaluator and CLI argument parser.

1. The caller runs `autofab benchmark` with `--baseline` and `--harness loop`.
   Observed: rejects execution with an exit code of 1 and outputs an error indicating the loop harness is not supported for baseline benchmarks.

1. The caller runs a baseline flight in simulation mode or with an autonomous harness (such as Antigravity or DSH).
   Observed: routes execution through the unified Autofab clean orchestrator targeting the fused role (`baseline` or `pretense_baseline`), returns a flight record with methodology `baseline` (or `pretense_baseline`), stages executed `["baseline"]`, exactly one role round tallied under `baseline`, and archives passing artifacts under a baseline results destination.

## Scenario 13 — Pretense benchmark flight execution and verification

Given: the benchmark evaluator and CLI argument parser.

1. The caller runs `autofab benchmark` with `--method pretense` (or alias `--pretense`).
   Observed: the flight executes synthesis and testing using Pretense state machines, fakes, and property fuzzing across pretense roles or baseline prompts, verification gates evaluate Pretense test execution (`uv run pretense --no-fuzz --cov`) and statement coverage, methodology is `pretense`, and passing artifacts are archived with `-pretense` destination suffix.

## Scenario 14 — Pretense baseline benchmark flight execution and verification

Given: the benchmark evaluator and CLI argument parser.

1. The caller runs `autofab benchmark` with `--baseline` and `--method pretense` (or alias `--pretense`).
   Observed: routes execution through the unified Autofab clean orchestrator targeting the fused role `pretense_baseline`, verification gates evaluate Pretense test execution (`uv run pretense --no-fuzz --cov`) and statement coverage, methodology is `pretense_baseline`, and passing artifacts are archived with `-pretense-baseline` destination suffix.

## Scenario 15 — Headless coordination announcement and real-time output streaming

Given: a benchmark flight executing under a headless harness (such as `dsh` or `simulation`).

1. The benchmark evaluator launches the autofab runner subprocess.
   Observed: announces the headless coordination initiation banner to standard output, flushes output immediately, and streams progress lines in real time to standard output.

## Scenario 16 — Fail-fast when Antigravity harness is selected outside of Antigravity

Given: an execution environment where `ANTIGRAVITY_AGENT` is not set.

1. The benchmark evaluator executes a flight with harness set to `antigravity`.
   Observed: raises ValueError rejecting the Antigravity harness and explaining that the Antigravity agentic environment is required.

## Scenario 17 — Single model per flight and strict rejection of comma-separated models

Given: the benchmark evaluator and CLI argument parser.

1. The caller runs `autofab benchmark` or `bin/evaluate_model_efficiency.py` passing a comma-separated model string (e.g. `--model=deepseek-flash,qwen-moe` or `--models=deepseek-flash,qwen-moe`).
   Observed: rejects execution with exit code 1 and outputs an error indicating that comma-separated model lists are prohibited and only a single model may be targeted per flight.

1. The caller runs with `--model <name>` targeting a single model.
   Observed: resolves the single target model specification and executes the benchmark flight.

## Scenario 18 — Combined benchmark flight execution and baseline verification

Given: the benchmark evaluator and CLI argument parser.

1. The caller runs `autofab benchmark` with `--method combined` (or alias `--combined`).
   Observed: provisions the flight scope with `pipeline = "combined"`, executes dual-branch convergence covering both standard unit testing and Pretense fuzzing, verification gates validate static types across library, tests, and pretense, standard pytest execution, and Pretense test execution (`uv run pretense --no-fuzz --cov`), methodology is `combined`, and passing artifacts are archived with `-combined` destination suffix containing `lib_<N>.py`, `test_<N>.py`, and `pretense_<N>.py`.

1. The caller runs `autofab benchmark` with `--baseline` and `--method combined` (or alias `--combined`).
   Observed: routes execution through the unified Autofab clean orchestrator targeting the fused role `combined_baseline`, evaluates composite verification gates, methodology is `combined_baseline`, and passing artifacts are archived with `-combined-baseline` destination suffix.

## Scenario 19 — DSH Web loopback bridge execution via --dsh-web and Desktop override via --dsh-desktop

Given: the benchmark evaluator and CLI argument parser.

1. The caller runs `autofab benchmark` with `--dsh-web`.
   Observed: sets the DSH Web loopback bridge environment variable or forwards `--dsh-web` to the subagent runner subprocess, enabling DeepSeek subagent execution and telemetry retrieval via the DSH Web loopback bridge.

1. The caller runs `autofab benchmark` with `--dsh-desktop`.
   Observed: explicitly unsets the DSH Web loopback bridge environment variable or forwards `--dsh-desktop` to the subagent runner subprocess, forcing DeepSeek Harness Desktop RPC execution even when DSH Web is configured as the default.

## Scenario 20 — Active experiment flight execution and artifact archival suffixing

Given: the benchmark evaluator and CLI argument parser.

1. The caller runs `autofab benchmark` with `--experiment structured_blame`.
   Observed: propagates active experiment identifier to execution environment (`AUTOFAB_EXPERIMENT=structured_blame`), evaluates conditional markdown directives during flight scope and workspace provisioning, and archives passing artifacts with `-[experiment]` suffix appended to the results destination folder (e.g. `benchmarks/results/semver_solver/deepseek-flash-structured_blame/`).
1. The caller runs `autofab benchmark` on a non-baseline evaluation without specifying `--experiment`.
   Observed: defaults active experiment to `structured_blame`, activates the experiment in the environment, and appends `-structured_blame` to the results directory.
1. The caller runs `autofab benchmark` with `--disable_experiment structured_blame` (or `--no-experiment`).
   Observed: explicitly disables active experiments and archives results without an experiment suffix.
1. The caller runs `autofab benchmark --baseline` without specifying `--experiment`.
   Observed: preserves control baseline evaluation without activating default experiments.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-19T18:45:00Z
LAST_CHANGED: 2026-11-09T23:32:00Z
CHANGE: Delete existing conversations matching benchmark_N on flight start
SPEC_QA_AUDIT: 2026-10-19T19:35:00Z
-->
