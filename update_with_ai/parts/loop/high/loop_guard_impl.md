<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Remove the interface-restated tracking sentence, canonicalize threshold names, and split reminder and failure conditions
CODE_HASH: 443d00eec2cf
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# loop_guard_impl implementation component

imports: tool_provider
implements: loop_guard

## Purpose

The loop_guard_impl implementation component realizes threshold-based tracking for identical tool calls and file modification oscillations.

Detecting loops requires maintaining state across consecutive turns to distinguish productive tool retries from unproductive oscillations. The loop_guard_impl implementation component records parameter signatures for identical invocations and coordinate spans for file modifications, injecting advisory guidance at early warning boundaries and terminating runaway loops at fatal limits.

**Out of scope:** The loop_guard_impl implementation component does not modify files on disk, format model role schemas, or record unbuffered log transcripts; these are handled by other components.

## Types and Behavior

The loop guard tracks consecutive executions of identical tools with identical arguments, and consecutive edits to the same file and line range.

Tool execution evaluation:

- Produces a loop reminder when consecutive identical tool executions reach the warning threshold of two repetitions, advising the agent that no new information will be revealed by repeated tool execution until session read-write files are updated and that repeating the tool call without modifying files will trigger fatal loop termination.

- Produces a loop failure communicating session failure when consecutive identical tool executions reach the fatal threshold.

- Produces a loop reminder when consecutive edits to the same file and line range reach the warning threshold of two repetitions.

- Produces a loop failure when consecutive edits to the same file and line range reach the fatal threshold.

A tool execution demonstrating forward progress resets the repetition counters of the loop guard.
