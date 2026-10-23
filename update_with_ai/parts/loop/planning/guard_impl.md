# guard_impl implementation component

## Intent

Detecting loops requires maintaining state across consecutive turns to distinguish productive tool retries from unproductive oscillations. The guard_impl implementation component records parameter signatures for identical invocations and coordinate spans for file modifications, injecting advisory guidance at early warning boundaries and terminating runaway loops at fatal limits.

By enforcing an explicit warning threshold of two repetitions and fatal thresholds for stubborn loops, the implementation keeps agent runs focused and prevents cost overruns.

## Factored Contracts

### Contracts

- The loop guard tracks consecutive executions of identical tools with identical arguments. [track_identical_tool_executions]
- The loop guard tracks consecutive edits to the same file and line range using the session's editing tool. [track_consecutive_file_range_edits]
- When consecutive identical tool executions reach the warning threshold of two repetitions, the loop guard produces a loop reminder. [remind_tool_repetition_at_two]
- The tool repetition reminder directs the agent to modify files using the session's editing tool or conclude the round with blame or fail. [direct_action_or_conclude_round]
- The tool repetition reminder advises the agent that no new information will be revealed until session read-write files are updated. [advise_no_new_info_until_files_updated]
- The tool repetition reminder warns that repeating without modifying files will trigger fatal termination. [warn_repetition_triggers_fatal]
- When consecutive identical tool executions reach the fatal threshold, the loop guard produces a loop failure communicating session failure. [fail_tool_repetition_at_fatal]
- When consecutive edits target the same file and line range, the loop guard produces a loop reminder when they reach the warning threshold of two repetitions. [remind_edit_repetition_at_two]
- When consecutive edits target the same file and line range, the loop guard produces a loop failure at the fatal threshold. [fail_edit_repetition_at_fatal]
- Any tool execution demonstrating forward progress resets repetition counters in the loop guard. [reset_counters_on_forward_progress]

### Woven Contracts

- Repeating identical tool calls or line-bounded edits triggers advisory reminders at two repetitions and fatal failure when reaching the fatal limit. [track_identical_tool_executions, track_consecutive_file_range_edits, remind_tool_repetition_at_two, direct_action_or_conclude_round, advise_no_new_info_until_files_updated, warn_repetition_triggers_fatal, fail_tool_repetition_at_fatal, remind_edit_repetition_at_two, fail_edit_repetition_at_fatal, guard: [produce_loop_reminder_at_warning, produce_loop_failure_at_fatal]]
- Tool executions demonstrating progress clear repetition counters to allow legitimate iterative development. [reset_counters_on_forward_progress, guard: [clear_repetition_on_progress]]

## Grounding

### Knowledge Provisions

- Repetition tracking and loop prevention across consecutive tool executions and file edits. [loop_guard_service]

### Inherited Deferred Requirements

- Consecutive tool signature and file edit span tracking.
  - Grounded: [loop_guard_service, tool_provider: [tool_execution_capability]]
- Threshold evaluation for warning reminders and fatal aborts.
  - Grounded: [loop_guard_service]

### Knowledge Requirements

- Identification of the session's editing tool and its coordinate parameters.
  - Grounded: [loop_guard_service, file_editor: [editing_tool_capability]]
- Repetition counter reset on forward progress.
  - Grounded: [loop_guard_service]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-21T20:00:00Z
LAST_CHANGED: 2026-10-21T20:00:00Z
CHANGE: Ground editing tool capability from file_editor for edit tracking and reminder direction
SPEC_QA_AUDIT: 2026-10-21T20:00:00Z
-->
