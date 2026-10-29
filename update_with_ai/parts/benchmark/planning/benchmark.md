# benchmark interface component

## Intent

Evaluating language models across automated coding and neural compilation workflows requires consistent empirical measurement of token expenditure, context caching economics, execution latencies, and financial costs alongside deterministic verification outcomes. Without uniform contracts, benchmarking pipelines suffer from divergent token accounting, hidden reasoning token omissions, and ungrounded code generation claims. The benchmark interface component establishes the formal types, behavioral contracts, and knowledge provisions for evaluating model efficiency across capability tiers and benchmark suites.

By establishing standard data models for model specifications, benchmark units, flight telemetry, verification outcomes, and flight traces, the component guarantees that all benchmark flights generate reproducible, publication-ready empirical records.

## Factored Contracts

### Typing

- A model specification carries an identifier, a tier number, a tier label, a provider name, an uncached input rate, a cached input rate, an output rate, an optional endpoint, an optional quantization, and a default harness.
- A benchmark unit carries a suite name, a task identifier, a unit directory, a target address, and optional metadata including archetype description, specification line count, target library line count, and description.
- A flight telemetry record carries non-cached inbound tokens, cached inbound tokens, outbound tokens, total tokens, financial cost, step latencies, wall clock seconds, and role execution rounds mapping role short names to execution round counts.
- A verification outcome record carries a specification linter pass status, a type error count, a unit tests passed count, a unit tests failed count, a line coverage percentage, a branch coverage percentage, a mutation score percentage, and a convergence status.
- A flight trace carries a flight identifier, an ISO timestamp, a research question tag, a model specification dictionary, a benchmark unit dictionary, a methodology name, stages executed, a flight telemetry record, and a verification outcome record.
- A system's benchmark evaluator coordinates benchmark flight execution and report generation.

### Contracts

- A model specification computes financial cost from non-cached inbound tokens, cached inbound tokens, and outbound tokens according to its rate card. [compute_financial_cost]
- A system's benchmark evaluator provides model and suite catalogs mapping identifiers to specifications and units. [provide_catalogs]
- A system's benchmark evaluator provisions an ephemeral flight scope directory preserving the package structure of the benchmark unit's enclosing scope to isolate role workspaces and prevent concurrent flight collisions. [provision_flight_scope]
- A system's benchmark evaluator executes a benchmark flight for a designated model specification and benchmark unit across Cleanroom, Pretense, baseline, or combined pretense-baseline methodologies, provisioning companion implementation guides (`guides/low_to_lib.md` and either `guides/pretense.md` or `guides/low_to_test.md`), providing the low-level specification and instructing the baseline agent to implement the two-file library structure in `lib/` (consulting `guides/low_to_lib.md`), test `_impl.py` (or author pretense suites in `pretense/`), and achieve 100% test coverage with opt-outs for baseline flights, provisioning pretense runtime tools and scaffolding when combined, supporting optional custom results directory destinations. [execute_benchmark_flight]
- A system's benchmark evaluator evaluates verification outcomes through two-pass verification gates. [evaluate_verification_outcomes]
- A system's benchmark evaluator produces a flight trace recording empirical telemetry and verification outcomes. [produce_flight_trace]
- A system's benchmark evaluator formats flight traces into a summary report highlighting passing and failing flight status alongside verification outcomes. [format_summary_report]
- A system's benchmark evaluator archives synthesized library, test, and Cleanroom event log files into sequential run files with embedded flight telemetry metrics exclusively for successful flights that pass verification gates and achieve clean DAG convergence with exit code zero. [archive_flight_artifacts]
- A system's benchmark evaluator drains pre-existing library and test files from the benchmark unit directory within the flight scope, marks specifications clean up to specification QA within the flight scope, and tears down the ephemeral flight scope alongside provisioned role workspaces upon flight completion, removing them for successful flights passing verification gates and converging cleanly, and preserving the flight scope directory as `<flight_scope>.failed` along with associated role workspaces under `<flight_scope>.failed/role_workspaces` on failure. [drain_benchmark_unit_workspace]
- The component maintains a suite catalog and provides telemetry log harvesting from Cleanroom run logs and subagent session transcripts. [harvest_telemetry_logs]

### Woven Contracts

- The benchmark evaluator executes benchmark flights, provisions flight scopes, evaluates verification gates, computes rate card costs, archives flight artifacts, drains workspaces, and produces flight traces and formatted summary reports. [compute_financial_cost, provide_catalogs, provision_flight_scope, execute_benchmark_flight, evaluate_verification_outcomes, produce_flight_trace, format_summary_report, archive_flight_artifacts, drain_benchmark_unit_workspace, harvest_telemetry_logs]

## Grounding

### Knowledge Provisions

- Model specifications, financial rate cards, benchmark unit catalog, flight telemetry schemas, and benchmark evaluation service. [benchmark_evaluation_service]

### Knowledge Requirements

- Language model execution harness and filesystem verification execution.
  - Deferred: Provided by runtime implementation in benchmark_impl.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-19T18:45:00Z
LAST_CHANGED: 2026-10-27T22:45:00Z
CHANGE: Specify failed flight scope preservation with role workspaces, failure status reporting, and non-zero exit code on verification failure
SPEC_QA_AUDIT: 2026-10-19T18:45:00Z
-->
