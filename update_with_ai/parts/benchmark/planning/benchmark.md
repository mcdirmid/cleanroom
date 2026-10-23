# benchmark interface component

## Intent

Evaluating language models across automated coding and neural compilation workflows requires consistent empirical measurement of token expenditure, context caching economics, execution latencies, and financial costs alongside deterministic verification outcomes. Without uniform contracts, benchmarking pipelines suffer from divergent token accounting, hidden reasoning token omissions, and ungrounded code generation claims. The benchmark interface component establishes the formal types, behavioral contracts, and knowledge provisions for evaluating model efficiency across capability tiers and benchmark suites.

By establishing standard data models for model specifications, benchmark units, flight telemetry, verification outcomes, and flight traces, the component guarantees that all benchmark flights generate reproducible, publication-ready empirical records.

## Factored Contracts

### Typing

- A model specification carries an identifier, a tier number, a tier label, a provider name, an uncached input rate, a cached input rate, an output rate, an optional endpoint, an optional quantization, and a default harness.
- A benchmark unit carries a suite name, a task identifier, a unit directory, a target address, and optional metadata including archetype description, specification line count, target library line count, and description.
- A flight telemetry record carries non-cached inbound tokens, cached inbound tokens, outbound tokens, total tokens, financial cost, step latencies, wall clock seconds, and role execution rounds mapping role short names to execution round counts.
- A verification outcome record carries a specification linter pass status, a type error count, a unit tests passed count, a unit tests failed count, a line coverage percentage, a branch coverage percentage, and a mutation score percentage.
- A flight trace carries a flight identifier, an ISO timestamp, a research question tag, a model specification dictionary, a benchmark unit dictionary, a methodology name, stages executed, a flight telemetry record, and a verification outcome record.
- A system's benchmark evaluator coordinates benchmark flight execution and report generation.

### Contracts

- A model specification computes financial cost from non-cached inbound tokens, cached inbound tokens, and outbound tokens according to its rate card. [compute_financial_cost]
- A system's benchmark evaluator provides model and suite catalogs mapping identifiers to specifications and units. [provide_catalogs]
- A system's benchmark evaluator provisions an ephemeral flight scope directory preserving the package structure of the benchmark unit's enclosing scope to isolate role workspaces and prevent concurrent flight collisions. [provision_flight_scope]
- A system's benchmark evaluator executes a benchmark flight for a designated model specification and benchmark unit across Cleanroom or baseline methodologies, providing the low-level specification and instructing the baseline agent to implement the two-file library structure in `lib/`, test `_impl.py`, and achieve 100% test coverage with opt-outs for baseline flights, supporting optional custom results directory destinations. [execute_benchmark_flight]
- A system's benchmark evaluator evaluates verification outcomes through two-pass verification gates. [evaluate_verification_outcomes]
- A system's benchmark evaluator produces a flight trace recording empirical telemetry and verification outcomes. [produce_flight_trace]
- A system's benchmark evaluator formats flight traces into a summary report. [format_summary_report]
- A system's benchmark evaluator archives synthesized library, test, and Cleanroom event log files into sequential run files with embedded flight telemetry metrics exclusively for successful flights that pass verification gates. [archive_flight_artifacts]
- A system's benchmark evaluator drains pre-existing library and test files from the benchmark unit directory within the flight scope, marks specifications clean up to specification QA within the flight scope, and tears down the ephemeral flight scope alongside provisioned role workspaces upon flight completion. [drain_benchmark_unit_workspace]
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
LAST_CHANGED: 2026-10-22T23:10:00Z
CHANGE: Update benchmark unit typing to make descriptive metadata optional
SPEC_QA_AUDIT: 2026-10-19T18:45:00Z
-->
