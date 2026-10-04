# bazel_loop_impl implementation component

imports: bazel_manifest_loader, dag_storage, loop_cleaner, loop_node_cleaner, runner_logger
implements: loop

## Intent

Executing multi-stage agent workflows requires coordinating target loading, dirty state evaluation, and topological cleaning across the graph. The bazel_loop_impl implementation component coordinates this end-to-end lifecycle: loading workspace targets into graph storage, dispatching topological cleaning passes using loop cleaner and node cleaner, routing feedback across node boundaries, and capturing execution progress through structured runner logging.

By resolving targets from workspace directories or runfiles trees, halting execution immediately upon node failure or post-cleaning dirtiness, and streaming telemetry to standard output and transcript logs, the component ensures robust, auditable build execution.

## Factored Contracts

### Contracts

- Target labels are resolved against workspace directories to populate graph storage when executing a cleaning pass. [resolve_targets_from_workspace_directories]
- Target labels are resolved against runfiles trees to populate graph storage when executing a cleaning pass. [resolve_targets_from_runfiles_trees]
- Cleaning halts immediately with a failing build result when node cleaning fails. [halt_and_fail_when_node_cleaning_fails]
- Cleaning halts immediately with a failing build result when any reachable node remains dirty after cleaning. [halt_and_fail_when_node_remains_dirty]
- Cleaning halts immediately with a failing build result when an unexpected failure occurs during cleaning. [halt_and_fail_on_unexpected_failure]
- A failing build result captures the failure reason in the build summary. [capture_failure_reason_in_summary]
- Telemetry capturing execution events is streamed to standard output. [stream_telemetry_events_to_stdout]
- Telemetry capturing execution events is streamed to transcript files. [stream_telemetry_events_to_transcript]
- Telemetry capturing pass duration is streamed to standard output and transcript files. [stream_pass_duration_telemetry]
- Telemetry capturing build outcome is streamed to standard output and transcript files. [stream_build_outcome_telemetry]

## Woven Contracts

- Targets are resolved from workspace or runfiles directories to initialize graph storage before topological cleaning starts. [resolve_targets_from_workspace_directories, resolve_targets_from_runfiles_trees, bazel_manifest_loader: [retrieve_manifest_for_node, populate_agent_storage], dag_storage: [access_dag_dependencies]]
- If node cleaning fails, reachable nodes remain dirty, or unexpected errors occur, cleaning halts immediately and emits a failed build result with summary diagnostics. [halt_and_fail_when_node_cleaning_fails, halt_and_fail_when_node_remains_dirty, halt_and_fail_on_unexpected_failure, capture_failure_reason_in_summary, loop: [produce_build_result]]
- Execution events, duration, and final results stream continuously to stdout and transcript files through the runner logger. [stream_telemetry_events_to_stdout, stream_telemetry_events_to_transcript, stream_pass_duration_telemetry, stream_build_outcome_telemetry, runner_logger: [consume_log_events]]
