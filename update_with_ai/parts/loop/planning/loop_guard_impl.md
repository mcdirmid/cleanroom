# loop_guard_impl implementation component

imports: tool_provider
implements: loop_guard

## Intent

Detecting loops requires maintaining state across consecutive turns to distinguish productive tool retries from unproductive oscillations. The loop_guard_impl implementation component records parameter signatures for identical invocations and coordinate spans for file modifications, injecting advisory guidance at early reminder boundaries and terminating runaway loops at fatal limits.

By enforcing an explicit reminder threshold of two repetitions and fatal thresholds for stubborn loops, the implementation keeps agent runs focused and prevents cost overruns.

## Factored Contracts

### Contracts

- The loop guard tracks consecutive executions of identical tools with identical arguments. [track_identical_tool_executions]
- The loop guard tracks consecutive edits to the same file and line range. [track_consecutive_file_range_edits]
- When consecutive identical tool executions reach the reminder threshold of two repetitions, the loop guard produces a loop reminder. [remind_tool_repetition_at_two]
- The tool repetition reminder advises the agent that no new information will be revealed until session files are updated. [advise_no_new_info_until_files_updated]
- The tool repetition reminder warns that repeating without modifying files will trigger fatal termination. [warn_repetition_triggers_fatal]
- When consecutive identical tool executions reach the fatal threshold, the loop guard produces a loop failure. [fail_tool_repetition_at_fatal]
- When consecutive edits target the same file and line range, the loop guard produces a loop reminder at two repetitions. [remind_edit_repetition_at_two]
- When consecutive edits target the same file and line range, the loop guard produces a loop failure at the fatal threshold. [fail_edit_repetition_at_fatal]
- Any tool execution demonstrating forward progress resets repetition counters in the loop guard. [reset_counters_on_forward_progress]

### Woven Contracts

- Repeating identical tool calls or line-bounded edits triggers advisory reminders at two repetitions and fatal failure when reaching the fatal limit. [track_identical_tool_executions, track_consecutive_file_range_edits, remind_tool_repetition_at_two, advise_no_new_info_until_files_updated, warn_repetition_triggers_fatal, fail_tool_repetition_at_fatal, remind_edit_repetition_at_two, fail_edit_repetition_at_fatal, loop_guard: [produce_loop_reminder_at_warning, produce_loop_failure_at_fatal]]
- Tool executions demonstrating progress clear repetition counters to allow legitimate iterative development. [reset_counters_on_forward_progress, loop_guard: [clear_repetition_on_progress]]

## Grounding

### Knowledge Provisions

- Repetition tracking and loop prevention across consecutive tool executions and file edits. [loop_guard_service]

### Inherited Deferred Requirements

- Consecutive tool signature and file edit span tracking.
  - Grounded: [loop_guard_service, tool_provider: [tool_execution_capability]]
- Threshold evaluation for warning reminders and fatal aborts.
  - Grounded: [loop_guard_service]

### Knowledge Requirements

- Repetition counter reset on forward progress.
  - Grounded: [loop_guard_service]
