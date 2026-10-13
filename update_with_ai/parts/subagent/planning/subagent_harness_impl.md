<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_harness_impl planning specification
CODE_HASH: cf2aa4e91aa3
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# subagent_harness_impl implementation component

## Intent

The subagent_harness_impl implementation component realizes the command harness adapter and harness resolution services for executing external subagent processes across isolated role workspaces.

## Factored Contracts

### Typing

- The command harness adapter realization implements CommandHarnessAdapter and operates within agent_session.
- The harness resolver realization implements HarnessResolver and operates within agent_session.

### Contracts

- The realization constructs instructional task prompts detailing role, scope, targets, verification, and submit or blame actions. [construct_role_workflow_prompt]
- The realization captures initial pending targets prior to process execution. [capture_pre_execution_pending_work]
- The realization executes the configured subagent command template with workspace directory and prompt substitutions. [execute_subagent_command_template]
- The realization monitors subagent process lifecycle, enforcing configured timeout limits. [monitor_subagent_process_lifecycle]
- The realization inspects the blame buffer file for reported upstream defects. [inspect_blame_buffer_records]
- The realization computes submitted targets from the set difference of pre-turn and post-turn pending work items. [compute_submitted_work_targets]
- The realization extracts token metrics from log output and calculates financial costs. [tally_log_token_metrics]
- The realization synthesizes role turn results containing status, submitted items, blamed items, telemetry, and error diagnostics. [formulate_turn_outcome_result]
- The realization resolves platform-specific command templates or simulation mode. [resolve_platform_command_templates]

### Woven Contracts

- When executing a role subagent turn, the realization constructs role prompts, captures pre-execution pending targets, executes the subagent command template, monitors process lifecycle, inspects blame buffers, computes submitted targets, tallies token metrics, and formulates turn outcome results. [construct_role_workflow_prompt, capture_pre_execution_pending_work, execute_subagent_command_template, monitor_subagent_process_lifecycle, inspect_blame_buffer_records, compute_submitted_work_targets, tally_log_token_metrics, formulate_turn_outcome_result, subagent_harness: [format_subagent_task_prompt, capture_initial_pending_targets, spawn_subagent_process, await_subagent_process_lifecycle, inspect_workspace_blame_buffer, determine_submitted_targets, extract_process_token_telemetry, synthesize_role_turn_result], subagent_coordinator: [execute_wave_roles]]

## Grounding

### Knowledge Provisions

- Subagent prompt template construction logic. [prompt_construction_mechanics]
- Process execution, monitoring, and timeout handling. [process_execution_mechanics]
- Workspace buffer inspection and diff analysis. [buffer_inspection_mechanics]

### Inherited Deferred Requirements

- Cleanroom file conventions and buffer file names.
  - Grounded: [buffer_inspection_mechanics]
- Subagent process execution and outcome synthesis.
  - Grounded: [prompt_construction_mechanics, process_execution_mechanics, buffer_inspection_mechanics]

### Knowledge Requirements

- Coordinator harness adapter protocols and turn result types.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
