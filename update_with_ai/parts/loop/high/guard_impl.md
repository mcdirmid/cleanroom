# guard_impl implementation component

imports: tool_provider, file_editor
implements: guard

## Purpose

The guard_impl implementation component realizes threshold-based tracking for identical tool calls and file modification oscillations.

Detecting loops requires maintaining state across consecutive turns to distinguish productive tool retries from unproductive oscillations. The guard_impl implementation component records parameter signatures for identical invocations and coordinate spans for file modifications, injecting advisory guidance at early warning boundaries and terminating runaway loops at fatal limits.

**Out of scope:** The guard_impl implementation component does not modify files on disk, format model role schemas, or record unbuffered log transcripts; these are handled by other components.

## Types and Behavior

The loop guard tracks consecutive executions of identical tools with identical arguments, and consecutive edits to the same file and line range using the session's editing tool.

Tool execution evaluation:

- Produces a loop reminder when consecutive identical tool executions reach the warning threshold of two repetitions, directing the agent to modify files using the session's editing tool or conclude the round with blame or fail, advising the agent that no new information will be revealed by repeated tool execution until session read-write files are updated, and warning that repeating the tool call without modifying files will trigger fatal loop termination.

- Produces a loop failure communicating session failure when consecutive identical tool executions reach the fatal threshold.

- Produces a loop reminder when consecutive edits to the same file and line range reach the warning threshold of two repetitions.

- Produces a loop failure when consecutive edits to the same file and line range reach the fatal threshold.

A tool execution demonstrating forward progress resets the repetition counters of the loop guard.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-21T20:00:00Z
LAST_CHANGED: 2026-10-21T20:00:00Z
CHANGE: Contract session editing tool usage for tracking edits and directing file modification in reminder
SPEC_QA_AUDIT: 2026-10-21T20:00:00Z
-->
