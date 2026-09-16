# loop_guard_impl implementation component

imports: tool_provider
implements: loop_guard

## Purpose

The loop_guard_impl implementation component realizes threshold-based tracking for identical tool calls and file modification oscillations.

Detecting loops requires maintaining state across consecutive turns to distinguish productive tool retries from unproductive oscillations. The loop_guard_impl implementation component records parameter signatures for identical invocations and coordinate spans for file modifications, injecting advisory guidance at early reminder boundaries and terminating runaway loops at fatal limits.

**Out of scope:** The loop_guard_impl implementation component does not modify files on disk, format model role schemas, or record unbuffered log transcripts; these are handled by other components.

## Types and Behavior

The loop guard tracks consecutive executions of identical tools with identical arguments and consecutive edits to the same file and line range. Repetition tracking evaluates consecutive identical executions against configured thresholds. Tool execution evaluation:

- Produces a loop reminder advising the agent that no new information will be revealed by repeated tool execution until session read-write files are updated and that repeating the tool call without modifying files will trigger fatal loop termination, when consecutive identical tool executions reach the reminder threshold of two repetitions.

- Produces a loop failure communicating session failure when consecutive identical tool executions reach the fatal threshold.

- Produces a loop reminder at the reminder threshold of two repetitions when consecutive edits target the same file and line range.

- Produces a loop failure at the fatal threshold when consecutive edits target the same file and line range.

Any tool execution demonstrating forward progress resets repetition counters in the loop guard.
