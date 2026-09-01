# loop_guard

imports: tool_provider
types from tool_provider: tool

## Purpose

Detects and breaks repetitive, unproductive agent loops to conserve execution cycles and prevent runaway runs.

Language models occasionally get trapped repeating identical tool calls or oscillating between identical file edits without making progress. Loop guard monitors consecutive repetitions, issuing corrective reminders at early thresholds and producing fatal loop failures to terminate stuck runs.

## Types

- A *loop guard* is a monitor that tracks repetitive execution patterns during an agent run
- A *loop reminder* is feedback warning an agent of detected repetition
- A *loop failure* is an outcome signaling that an agent run has failed due to unresolvable repetition

## Behavior

- A *loop guard* evaluates consecutive executions of identical *tools* and edits.
- Consecutive repetitions reaching a warning threshold produce a *loop reminder*.
- Consecutive repetitions reaching a fatal threshold produce a *loop failure* communicating that the agent run should fail.
- Executing a tool that demonstrates progress clears repetition tracking in a *loop guard*.
