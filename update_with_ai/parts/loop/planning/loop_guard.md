<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:28:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 552c58f25cc6
-->

# loop_guard interface component

imports: tool_provider

## Intent

Language models occasionally get trapped repeating identical tool calls or oscillating between identical file edits without making progress. The loop_guard interface component monitors consecutive repetitions during an agent session, issuing corrective reminders at early thresholds and producing fatal loop failures to terminate stuck runs.

By distinguishing repetitive oscillations from productive tool invocations, the loop guard conserves token budgets and execution time while providing actionable recovery prompts.

## Factored Contracts

### Typing

- A loop reminder provides diagnostic feedback warning an agent of detected repetition.
- A loop failure signals that an agent session has failed due to unresolvable repetition.
- A loop failure carries an explanation.

### Contracts

- The loop guard evaluates consecutive executions of identical tools. [evaluate_consecutive_tools]
- The loop guard evaluates consecutive executions of identical file edits. [evaluate_consecutive_edits]
- The loop guard produces a loop reminder when consecutive repetitions reach a warning threshold. [produce_loop_reminder_at_warning]
- The loop guard produces a loop failure communicating session termination when consecutive repetitions reach a fatal threshold. [produce_loop_failure_at_fatal]
- The loop guard clears repetition tracking when a tool execution demonstrates forward progress. [clear_repetition_on_progress]

## Woven Contracts

- Repetition monitoring evaluates consecutive identical tool executions and file edits, issuing reminders at warning limits and aborting at fatal limits. [evaluate_consecutive_tools, evaluate_consecutive_edits, produce_loop_reminder_at_warning, produce_loop_failure_at_fatal]
- Tool invocations that produce state changes or forward progress reset internal repetition tracking. \[clear_repetition_on_progress, tool_provider: [call_by_name]\]
