# benchmark_impl implementation component

imports: model_config_ext, app_info_ext
implements: benchmark

## Purpose

The benchmark_impl implementation component realizes empirical benchmark execution, multi-harness dispatch, telemetry log harvesting, two-pass verification gates, and comparative report formatting.

Autonomous model benchmarking requires executing isolated flights across local hardware engines and cloud API harnesses, extracting precise token usage and step latencies from execution logs, running deterministic static and runtime verification gates, and producing publication-ready JSON traces and summary tables. The benchmark_impl implementation component provides concrete adapters for local runtime endpoints, external subagent harnesses, and simulated flights, parsing round and step logs to harvest token and timing metrics, running linters and test suites, and formatting structured markdown and JSON outputs.

**Out of scope:** The benchmark_impl implementation component does not modify source files or provision physical workspace permissions; these are handled by other components.

**Delegated:** Reading declarative model configuration files and rate card schemas is delegated to model_config_ext; user configuration directory resolution is delegated to app_info_ext.

## Types and Behavior

A system's *benchmark evaluator* realizes model efficiency evaluation and verification report generation as a system service.

The benchmark evaluator maintains a model catalog mapping model keys to model specifications loaded dynamically from declarative configuration files across local, budget, mid-tier, and frontier capability tiers, and a suite catalog discovered from the benchmark parts directory mapping each constituent part directory name to a benchmark unit suite.

The benchmark evaluator provides access to the active model catalog mapping model identifiers and aliases to model specifications.

The benchmark evaluator executes a benchmark flight for a designated model specification and benchmark unit under a selected research question tag and harness mode, capturing wall clock elapsed time and generating a unique flight identifier and ISO timestamp. To support concurrent benchmark execution without cross-flight contamination, the evaluator provisions a concise sequential ephemeral flight scope directory (e.g. `benchmark_1`, allocating the next unique sequential index), preserving the package structure of the benchmark unit's enclosing scope (copying scope configuration and the target unit into `<flight_scope>/parts/<unit>`), rewriting benchmark imports across copied sources to reference the flight scope package while disallowing bare parts imports, ensuring role workspaces derive dynamically as `<repo_name>_<role_name>_<flight_scope>`. If an indexed flight scope directory does not exist in the repository root, any orphaned role workspaces associated with that index are safely purged to allow clean sequential reuse. When executing under an asynchronous subagent harness, the evaluator emits the coordination directive, supports native platform IPC dispatch via `agentapi` or active flight state persistence, and monitors clean convergence across the flight scope until completion or timeout before evaluating verification gates and archiving artifacts.

The benchmark evaluator harvests flight telemetry by parsing round and step log files modified after flight commencement or subagent session transcripts from an active subagent harness environment. For subagent harness flights, the evaluator identifies coordinator and child role worker conversations, extracting non-cached inbound tokens, cached inbound tokens, outbound tokens, and step duration latencies from planner response entries across all participant conversations, while tallying role execution rounds exclusively across target role workers based on dispatch waves and excluding the coordinator session from role rounds. The evaluator computes total tokens and financial cost using the model specification's rate card.

The benchmark evaluator evaluates verification outcomes by executing two-pass verification gates against the target benchmark unit directory within the active flight scope, assessing specification linters, static type checks, unit test results, statement coverage, and mutation testing scores. The verification gate dynamically resolves constituent package and runtime support paths relative to the active repository root into the execution environment so that inter-module imports and lifecycle support libraries resolve cleanly without hardcoded directory paths.

When simulated execution is requested, the benchmark evaluator produces synthetic telemetry scaled to the benchmark unit archetype size and marks verification gates as passing.

The benchmark evaluator serializes each flight trace to a structured JSON file matching the canonical schema under a benchmark logs directory.

The benchmark evaluator formats flight traces into a markdown summary report presenting model tiers, token metrics, financial costs, wall clock durations, and verification outcomes, saving the report to a designated output path when provided.

The benchmark evaluator archives synthesized library, test, and Cleanroom event log files produced by the model into a results directory structured by benchmark identifier and a combined model-and-harness identifier (`benchmarks/results/<benchmark-id>/<model-name+harness-name>/`) exclusively for successful flights that pass verification gates (zero unit test failures, at least one passing unit test, zero type errors, and passing specification linters). When dry-run mode is active or when a flight fails verification gates or fails to materialize synthesized library or test files, the evaluator skips artifact archival. For multi-file library implementations in successful flights, the evaluator preserves all constituent non-dunder implementation files within `lib_<N>.py`. The evaluator determines the next available sequential run index, writes the library file as `lib_<N>.py` with a header comment capturing flight telemetry metrics, financial cost, wall-clock duration, role execution rounds, and verification outcomes, writes the test file as `test_<N>.py`, and, when present, copies the Cleanroom event log `.cleanroom.log` from the flight scope as `cleanroom_<N>.log`.

The benchmark evaluator drains pre-existing library and test files from the target benchmark unit directory within the flight scope before executing a flight, cleans up orphaned flight scope directories and associated role workspaces from prior flights, marks specifications clean up to specification QA within the flight scope to ensure only library implementation, unit tests, and QA verification are evaluated, and tears down the ephemeral flight scope directory after flight completion and archival alongside any provisioned role workspaces under the role workspaces container to ensure isolated evaluation without cross-flight contamination.

The benchmark evaluator processes command-line arguments to resolve target models, benchmark suites (using part directory names from benchmark parts or all discovered suites), tier filters, research question tags, unit count limits, harvest flight identifiers, and execution modes, executing the resolved benchmark matrix and reporting results.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-19T18:45:00Z
LAST_CHANGED: 2026-10-22T23:10:00Z
CHANGE: Derive benchmark suites from part directory names in benchmark parts and accept discovered suite names in CLI
SPEC_QA_AUDIT: 2026-10-19T19:35:00Z
-->
