# Concrete scenarios for `benchmark` (interface)

## Scenario 1 — Model specification properties and rate card computation

Given: a model specification for `qwen3.6-35b-a3b` in tier 1 with uncached input rate 0.0, cached input rate 0.0, and output rate 0.0.

1. The caller computes financial cost for 100,000 uncached inbound tokens, 200,000 cached inbound tokens, and 50,000 outbound tokens.
   Observed: cost is $0.0000.

Given: a model specification for `deepseek-v4.1-flash` in tier 2 with uncached input rate 0.15, cached input rate 0.03, and output rate 0.60 per 1M tokens.

2. The caller computes financial cost for 1,000,000 uncached inbound tokens, 2,000,000 cached inbound tokens, and 500,000 outbound tokens.
   Observed: cost is $0.5100 ($0.15 + $0.06 + $0.30).

## Scenario 2 — Benchmark unit metadata representation

Given: a benchmark unit for `dag_engine` in suite `dag_engine` with unit dir `benchmarks/parts/dag_engine`, target address `//benchmarks/parts/dag_engine#dag_engine_impl`, and optional archetype, spec loc, and description.

1. The caller inspects the benchmark unit fields.
   Observed: suite is `dag_engine`, task identifier is `dag_engine`, unit dir is `benchmarks/parts/dag_engine`, and target address is `//benchmarks/parts/dag_engine#dag_engine_impl`.

## Scenario 3 — Flight telemetry recording and totals computation

Given: a flight telemetry record with 10,000 uncached inbound tokens, 40,000 cached inbound tokens, 5,000 outbound tokens, step latencies `[2.5, 3.0, 1.8]`, and role execution rounds `{"lib": 2, "test": 1, "qa": 2, "coverage": 1}`.

1. The caller computes totals using the model specification.
   Observed: total tokens is 55,000, financial cost is computed according to the model rate card, and role execution rounds reflect 6 total rounds across 4 distinct roles.

## Scenario 4 — Verification outcomes record

Given: a verification outcome record reporting spec linter pass true, 0 pyright errors, 15 unit tests passed, 0 unit tests failed, line coverage 96.4%, branch coverage 92.1%, mutation score 88.5%, and convergence status true.

1. The caller inspects the quality gate status.
   Observed: spec linter pass is true, pyright errors is 0, convergence status is true, and all unit tests passed.

## Scenario 5 — Flight trace structure

Given: a flight trace for flight `flight_test_001` with model `qwen3.6-35b-a3b`, unit `cpython_heapq`, and research question `RQ1`.

1. The caller converts the flight trace to a dictionary.
   Observed: the dictionary contains `flight_id`, `timestamp`, `rq`, `model`, `benchmark_unit`, `measurements`, and `verification_outcomes` keys matching the canonical schema.

## Scenario 6 — Flight artifact archival and workspace draining

Given: a completed flight record and benchmark unit with synthesized library, test, and Cleanroom event log files.

1. The caller requests artifact archival.
   Observed: returns paths to archived library and test files under the results directory with sequential run indexing and embedded telemetry metrics, archiving the Cleanroom event log when present.

2. The caller requests unit workspace draining.
   Observed: the unit directory library and test locations are purged clean, and ephemeral flight scopes are torn down.

3. The caller requests artifact archival for a flight record whose verification outcomes indicate failure.
   Observed: returns None and skips writing files to the results directory.

4. The caller completes a failed flight and tears down the flight scope.
   Observed: skips artifact archival, preserves the ephemeral flight scope directory as `<flight_scope>.failed` with associated role workspaces under `<flight_scope>.failed/role_workspaces`, and reports failure status in the summary report.

## Scenario 8 — Baseline flight recording and execution

Given: a benchmark evaluator and a baseline flight request with an autonomous subagent harness.

1. The caller executes a baseline flight.
   Observed: the caller provides the low-level specification and instructs the agent to consult it, create the two-file library structure in `lib/`, test `_impl.py`, and achieve 100% test coverage with opt-outs, exactly one execution round is tallied under role `baseline`, stages executed reflects baseline, and methodology is `baseline`.

2. The caller attempts baseline execution under the loop harness.
   Observed: rejects execution or raises an error because the loop harness does not support single-agent baseline evaluation.

## Scenario 9 — Querying suite catalogs and harvesting telemetry logs

Given: the benchmark evaluator service and a suite catalog containing suite `dag_engine`.

1. The caller queries the suite catalog for suite `dag_engine`.
   Observed: returns a sequence of benchmark units including `dag_engine`.

2. The caller executes log harvesting on a completed Cleanroom role log.
   Observed: returns inbound token counts, outbound token counts, step latencies, and role execution rounds parsed from execution log events.

## Scenario 10 — Pretense benchmark flight recording and execution

Given: a benchmark evaluator and a flight request with the pretense flag enabled.

1. The caller executes a benchmark flight with pretense enabled.
   Observed: the flight executes synthesis and testing using Pretense state machines, fakes, and property fuzzing across pretense roles or baseline prompts, verification gates evaluate Pretense test execution and statement coverage, methodology is `pretense`, and stages executed reflect pretense pipeline roles.

## Scenario 11 — Pretense baseline benchmark flight execution

Given: a benchmark evaluator and a flight request with both `--baseline` and `--pretense` enabled.

1. The caller executes a baseline pretense flight.
   Observed: the evaluator provisions the pretense package and companion guide into the baseline workspace root, pre-scaffolds the starter pretense suite, instructs the baseline agent to implement `lib/` and author state machine models, transitions, fake synthesis, unit tests, and property fuzz tests in `pretense/` verifying with `uv run pretense`, exactly one execution round is tallied under role `baseline`, stages executed reflects baseline, methodology is `pretense_baseline`, and passing artifacts are archived under `-pretense-baseline`.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-19T18:45:00Z
LAST_CHANGED: 2026-10-27T22:45:00Z
CHANGE: Specify failed flight scope preservation with role workspaces, failure status reporting, and non-zero exit code on verification failure
-->
