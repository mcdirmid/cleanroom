# agent_loop_guard_impl implementation component

imports: tool_provider
implements: agent_loop_guard

## Purpose

The agent_loop_guard_impl implementation component realizes threshold-based tracking for identical tool calls and file modification oscillations.

Detecting loops requires maintaining state across consecutive turns to distinguish productive tool retries from unproductive oscillations. The agent_loop_guard_impl implementation component records parameter signatures for identical invocations and coordinate spans for file modifications, injecting advisory guidance at early reminder boundaries and terminating runaway loops at fatal limits.

**Out of scope:** The agent_loop_guard_impl implementation component does not modify files on disk, format model role schemas, or record unbuffered log transcripts; these are handled by other components.

## Types and Behavior

The loop guard tracks consecutive executions of identical tools with identical arguments. When consecutive identical tool executions reach the reminder threshold, the loop guard produces a loop reminder. When consecutive identical tool executions reach the fatal threshold, the loop guard produces a loop failure communicating session failure.

The loop guard also tracks consecutive edits to the same file and line range, producing a loop reminder at the reminder threshold and a loop failure at the fatal threshold.

Any tool execution demonstrating forward progress resets repetition counters in the loop guard.
