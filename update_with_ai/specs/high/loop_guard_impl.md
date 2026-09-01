# loop_guard_impl

imports: tool_provider, loop_guard
types from tool_provider: tool
types from loop_guard: loop guard, loop reminder, loop failure
implements: loop guard

## Behavior

- A *loop guard* tracks consecutive executions of identical *tools* with identical arguments.
- A *loop guard* produces a *loop reminder* when consecutive identical tool executions reach the reminder threshold.
- A *loop guard* produces a *loop failure* communicating session failure when consecutive identical tool executions reach the fatal threshold.
- A *loop guard* tracks consecutive edits to the same file and line range, producing a reminder at the reminder threshold and a *loop failure* at the fatal threshold.
- A tool execution demonstrating forward progress resets repetition counters in a *loop guard*.
