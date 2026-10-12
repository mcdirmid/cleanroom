<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Split detection from threshold outcomes into declarative statements
CODE_HASH: de33d286b482
SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
-->

# loop_guard interface component

imports: tool_provider

## Purpose

The loop_guard interface component detects and breaks repetitive agent loops to conserve execution cycles and prevent runaway runs.

Language models occasionally get trapped repeating identical tool calls or oscillating between identical file edits without making progress. The loop_guard interface component monitors consecutive repetitions during an agent session, issuing corrective reminders at early thresholds and producing fatal loop failures to terminate stuck runs.

**Out of scope:** The loop_guard interface component does not orchestrate model turns, dispatch tool executions, or format network payloads; these are handled by other components.

## Types and Behavior

A *loop reminder* is diagnostic *feedback* warning an agent of detected repetition. A *loop failure* is an outcome signaling that an agent session has failed due to unresolvable repetition, carrying an *explanation*.

An agent session's *loop guard* tracks repetitive execution patterns across turns.

The loop guard evaluates consecutive executions of identical tools and consecutive edits to the same file location.

The loop guard produces a loop reminder when consecutive repetitions reach a warning threshold, and produces a loop failure communicating session termination when consecutive repetitions reach a fatal threshold.

The loop guard clears repetition tracking when a tool execution demonstrates forward progress.
