<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 86187ee83c1b
-->

# sandbox interface component

## Purpose

The sandbox interface component coordinates the execution environment for an agent session, tracking file modifications.

Agent sessions operate across heterogeneous tools spanning file inspection, editing, and outcome control. If these capabilities are exposed as disconnected services, orchestrators must duplicate initialization logic and manually track workspace mutations. The sandbox interface component establishes a unified session coordination boundary that exposes session-wide file modification state.

**Out of scope:** The sandbox interface component does not schedule multi-node graph traversal, evaluate external model responses, or manage agent memory transcripts; these are handled by other components.

## Types and Behavior

An agent session's *sandbox* coordinates file modification tracking for the session.

The sandbox provides workspace coordination for the active session.

The sandbox:

- Exposes whether workspace file *modifications* occurred during the session.
