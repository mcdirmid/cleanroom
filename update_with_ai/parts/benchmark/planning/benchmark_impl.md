# benchmark_impl implementation component

## Intent

Executing empirical benchmark flights across divergent language model providers and local runtime engines requires an automated orchestration pipeline that abstracts subagent harnesses, extracts granular telemetry from execution logs, applies rigorous static and runtime verification gates, and formats comparative evaluation reports. The benchmark_impl implementation component coordinates these operations as a unified system service.

By standardizing on a model catalog loaded dynamically from declarative configuration files with published rate cards, a suite catalog spanning standard library and heavyweight systems archetypes, an automated log harvester, and two-pass verification gates, the component provides robust infrastructure for empirical research and continuous efficiency tracking.

## Factored Contracts

### Typing

- A system's benchmark evaluator coordinates benchmark flight execution, log harvesting, verification evaluation, and reporting.
- A model catalog maps model identifiers to model specifications.
- A suite catalog maps suite names to benchmark units.

### Contracts

- The benchmark evaluator maintains a model catalog mapping model keys to model specifications loaded dynamically from declarative configuration files across capability tiers. [maintain_model_catalog]
- The benchmark evaluator provides access to the active model catalog. [provide_model_catalog]
- The benchmark evaluator maintains a suite catalog discovered dynamically from benchmark parts directory names organizing benchmark units across target suites. [maintain_suite_catalog]
- The benchmark evaluator provisions a concise sequential ephemeral flight scope directory (e.g. benchmark_1) preserving the package structure of the benchmark unit's enclosing scope, copying scope configuration and the target unit into the flight scope, rewriting benchmark imports across copied sources to reference the flight scope package while disallowing bare parts imports, and purging orphaned role workspaces when the flight scope directory is absent, to isolate role workspaces and prevent concurrent flight collisions. [provision_flight_scope]
- The benchmark evaluator executes a benchmark flight for a designated model specification and benchmark unit under a research question tag and harness mode, supporting platform IPC dispatch via agentapi and active flight state persistence while monitoring clean convergence for asynchronous subagent harness flights, routing baseline flights through the unified Cleanroom clean orchestrator targeting the designated fused role (`pretense_baseline` or `baseline`) with relaxed intra-fuse prerequisites, verifying and harvesting all constituent units across the fused role without custom non-fused developer code paths, and recording the methodology as `pretense_baseline` (or `baseline`). [execute_benchmark_flight]
- The benchmark evaluator captures wall clock elapsed time and generates a unique flight identifier and ISO timestamp for each flight. [capture_flight_timing_and_identifier]
- The benchmark evaluator harvests flight telemetry by parsing round and step log files modified after flight commencement or subagent session transcripts from an active subagent harness environment, distinguishing coordinator and baseline developer subagent transcripts from individual role worker transcripts and parent caller sessions. [harvest_flight_telemetry]
- The benchmark evaluator extracts non-cached inbound tokens, cached inbound tokens (including `cache_read_tokens` and `cached_tokens` fields), outbound tokens, and step duration latencies from participant conversations, and tallies role execution rounds across target role worker dispatch waves while excluding coordinator sessions from role rounds, recording exactly one execution round under the baseline role for baseline flights. [extract_token_and_latency_metrics]
- The benchmark evaluator computes total tokens and financial cost using the model specification's rate card. [compute_flight_totals_and_cost]
- The benchmark evaluator evaluates verification outcomes through two-pass verification gates against the target benchmark unit directory within the active flight scope, assessing Pretense test verification (`uv run pretense`) when pretense is requested or pytest otherwise, dynamically assembling constituent package and support paths into the execution environment. [evaluate_verification_outcomes]
- When simulated execution is requested, the benchmark evaluator produces synthetic telemetry scaled to the benchmark unit archetype size and marks verification gates as passing. [simulate_benchmark_flight]
- The benchmark evaluator serializes each flight trace to a structured JSON file matching the canonical schema under a benchmark logs directory. [serialize_flight_trace_json]
- The benchmark evaluator formats flight traces into a markdown summary report presenting model tiers, status indicators (marking PASS or FAILED with defect diagnostics), token metrics, financial costs, wall clock durations, and verification outcomes. [format_markdown_summary_report]
- The benchmark evaluator archives synthesized library, test, and Cleanroom event log files into sequential run files under the benchmark results directory exclusively for successful flights that pass verification gates (zero unit test failures, at least one passing test, zero type errors, passing specification linters, and clean DAG convergence with exit code zero), embedding flight telemetry comments in the library file, appending -baseline to the results directory for baseline flights, appending -pretense when pretense is requested, appending -pretense-baseline when both are combined, preserving multi-file implementations in lib_<N>.py, archiving .cleanroom.log when present as cleanroom_<N>.log, and skipping archival when dry-run mode is active or when a flight fails verification gates. [archive_flight_artifacts]
- The benchmark evaluator drains pre-existing library and test files from the target benchmark unit directory within the flight scope before execution, sweeps orphaned prior flight directories and role workspaces, marks specifications clean up to specification QA within the flight scope (synchronizing in-band specification metadata and running `cleanroom mark-clean <flight_unit> --up-to spec_qa`) to ensure only library implementation, unit tests, and QA verification are evaluated, and tears down the ephemeral flight scope directory alongside provisioned role workspaces upon flight completion, deleting them for passing flights that converge cleanly, and relocating the flight scope to `<flight_scope>.failed` while preserving associated role workspaces under `<flight_scope>.failed/role_workspaces` on failure. [drain_benchmark_unit_workspace]
- The benchmark evaluator processes command-line arguments to resolve target models, benchmark suites using discovered benchmark part names, tier filters, research question tags, unit count limits, harvest flight identifiers, baseline evaluation flags disallowing the loop harness, pretense evaluation flags, and execution modes, executing the matrix, reporting results, and returning exit code 0 when all flights pass verification or 1 when any flight fails. [process_command_line_arguments]

### Woven Contracts

- Benchmark execution coordinates flight dispatch, flight scope provisioning, log harvesting, rate calculation, verification evaluation, artifact archival, workspace draining, JSON trace serialization, and report formatting. [maintain_model_catalog, provide_model_catalog, maintain_suite_catalog, provision_flight_scope, execute_benchmark_flight, capture_flight_timing_and_identifier, harvest_flight_telemetry, extract_token_and_latency_metrics, compute_flight_totals_and_cost, evaluate_verification_outcomes, simulate_benchmark_flight, archive_flight_artifacts, drain_benchmark_unit_workspace, serialize_flight_trace_json, format_markdown_summary_report, process_command_line_arguments]

## Grounding

### Knowledge Provisions

- Automated benchmark flight execution, dynamic model catalog loading, verification evaluation, and reporting service. [benchmark_evaluation_service]

### Inherited Deferred Requirements

- Language model execution harness and filesystem verification execution.
  - Grounded: [benchmark_evaluation_service]

### Knowledge Requirements

- Declarative model configurations and rate cards.
  - Grounded: [model_config_ext: [model_configuration_schema_extraction]]
- User configuration directory and paths.
  - Grounded: [app_info_ext: [user_configuration_paths]]
- Target model and benchmark unit parameters.
  - Grounded: [caller input, benchmark_evaluation_service]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-19T18:45:00Z
LAST_CHANGED: 2026-10-27T22:45:00Z
CHANGE: Specify robust failed flight directory preservation with role workspaces, prominent failure reporting, and non-zero exit code on verification failure
SPEC_QA_AUDIT: 2026-10-19T19:35:00Z
-->
