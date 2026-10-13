<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T21:57:18Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Replace the single-item bullet list with declarative prose and name the modification state
CODE_HASH: 8a7f8982f2fd
SPEC_QA_AUDIT: 2026-10-12T21:57:18Z
-->

# sandbox interface component

## Purpose

The sandbox interface component coordinates the execution environment for an agent session, tracking file modifications.

Agent sessions operate across heterogeneous tools spanning file inspection, editing, and outcome control. If these capabilities are exposed as disconnected services, orchestrators must duplicate initialization logic and manually track workspace mutations. The sandbox interface component establishes a unified session coordination boundary that exposes session-wide file modification state.

**Out of scope:** The sandbox interface component does not schedule multi-node graph traversal, evaluate external model responses, or manage agent memory transcripts; these are handled by other components.

## Types and Behavior

An agent session's *sandbox* coordinates state for an agent session and exposes whether workspace file *modifications* occurred during the session, so that outcome controls can require documentation of changed files before a session concludes.
