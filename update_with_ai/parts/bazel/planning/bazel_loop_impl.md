<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-05T05:28:31Z
CHANGE: Add feedback and change recording contracts and woven interactions
CODE_HASH: c4d7db19747c
-->

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
- Missing source files across the target subgraph are materialized from declared templates when marking a subgraph clean. [materialize_subgraph_templates_on_mark_clean]
- Node metadata headers are stamped with the current timestamp as the last cleaned timestamp when marking a subgraph clean. [stamp_last_cleaned_on_mark_clean]
- Missing last changed timestamps and default change descriptions are initialized when marking a subgraph clean. [initialize_missing_metadata_on_mark_clean]
- Unacted feedback is cleared when marking a subgraph clean. [clear_feedback_on_mark_clean]
- Deleting the last cleaned timestamp from a target node source file metadata header marks the target node dirty. [delete_last_cleaned_marks_target_dirty]
- Caller-supplied feedback is injected into the target node source file metadata in graph storage when recording feedback. [inject_caller_feedback_on_record_feedback]
- Injected feedback identifies the blamed dependency node. [injected_feedback_identifies_blamed_dependency]
- Injected feedback identifies the diagnostic reason. [injected_feedback_identifies_diagnostic_reason]
- A caller-supplied change message is recorded against a target node in graph storage when recording changes. [record_change_message_against_target]
- Recording changes clears the last cleaned timestamp of the target node in graph storage. [record_changes_clears_last_cleaned]
- Recording changes updates the change description of the target node in graph storage to dynamically invalidate downstream dependencies. [record_changes_updates_change_description]

### Woven Contracts

- Targets are resolved from workspace or runfiles directories to initialize graph storage before topological cleaning starts. [resolve_targets_from_workspace_directories, resolve_targets_from_runfiles_trees, bazel_manifest_loader: [retrieve_manifest_for_node, populate_agent_storage], dag_storage: [access_dag_dependencies]]
- If node cleaning fails, reachable nodes remain dirty, or unexpected errors occur, cleaning halts immediately and emits a failed build result with summary diagnostics. [halt_and_fail_when_node_cleaning_fails, halt_and_fail_when_node_remains_dirty, halt_and_fail_on_unexpected_failure, capture_failure_reason_in_summary, loop: [produce_build_result]]
- Execution events, duration, and final results stream continuously to stdout and transcript files through the runner logger. [stream_telemetry_events_to_stdout, stream_telemetry_events_to_transcript, stream_pass_duration_telemetry, stream_build_outcome_telemetry, runner_logger: [consume_log_events]]
- Marking an acyclic subgraph clean materializes missing source files from declared templates, stamps clean timestamps, and clears feedback across all reachable nodes. [materialize_subgraph_templates_on_mark_clean, stamp_last_cleaned_on_mark_clean, initialize_missing_metadata_on_mark_clean, clear_feedback_on_mark_clean, bazel_manifest_loader: [retrieve_manifest_for_node], dag_storage: [access_dag_dependencies, clear_node_messages], loop: [mark_subgraph_clean]]
- Marking a target node dirty removes its last cleaned timestamp from in-band source metadata. [delete_last_cleaned_marks_target_dirty, dag_storage: [mark_node_dirty], loop: [mark_node_dirty]]
- Recording feedback injects caller-supplied feedback into target node source file metadata identifying the blamed dependency node and diagnostic reason. [inject_caller_feedback_on_record_feedback, injected_feedback_identifies_blamed_dependency, injected_feedback_identifies_diagnostic_reason, loop: [inject_feedback_message], dag_storage: [record_feedback_messages]]
- Recording changes writes a change message against a target node in graph storage, clearing its clean timestamp and invalidating downstream dependencies. [record_change_message_against_target, record_changes_clears_last_cleaned, record_changes_updates_change_description, loop: [record_node_change_message], dag_storage: [record_change_messages, mark_dirty_on_change_message]]

## Grounding

### Knowledge Provisions

- End-to-end Bazel target loop orchestration, pass telemetry streaming, and state mutation. [bazel_loop_service]

### Inherited Deferred Requirements

- Subgraph cleaning pass execution in dependency order.
  - Grounded: [loop_cleaner: [loop_cleaner_service], loop_node_cleaner: [node_cleaner_service]]
- In-band source metadata mutation for clean and dirty states.
  - Grounded: [dag_storage: [dag_storage_service]]

### Knowledge Requirements

- Target loading and graph initialization prior to cleaning passes.
  - Grounded: [bazel_manifest_loader: [manifest_loading_service], dag_storage: [dag_storage_service]]
- Runner logging for pass telemetry streaming to stdout and transcript.
  - Grounded: [runner_logger: [runner_logging_service]]
