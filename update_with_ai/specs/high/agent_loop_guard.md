# agent_loop_guard interface component

imports: tool_provider

## Purpose

The agent_loop_guard interface component detects and breaks repetitive agent loops to conserve execution cycles and prevent runaway runs.

Language models occasionally get trapped repeating identical tool calls or oscillating between identical file edits without making progress. The agent_loop_guard interface component monitors consecutive repetitions during an agent session, issuing corrective reminders at early thresholds and producing fatal loop failures to terminate stuck runs.

**Out of scope:** The agent_loop_guard interface component does not orchestrate model turns, dispatch tool executions, or format network payloads; these are handled by other components.

## Types and Behavior

A *loop reminder* is diagnostic feedback warning an agent of detected repetition. A *loop failure* is an outcome signaling that an agent session has failed due to unresolvable repetition.

The *loop guard* is an *agent session* service that tracks repetitive execution patterns across turns. The loop guard:

- Evaluates consecutive executions of identical tools and file edits in a tool provider.

- Produces a loop reminder when consecutive repetitions reach a warning threshold.

- Produces a loop failure communicating session termination when consecutive repetitions reach a fatal threshold.

- Clears repetition tracking when a tool execution demonstrates forward progress.
