# sandbox interface component

## Purpose

The sandbox interface component coordinates the execution environment for an agent session, materializing starter templates and tracking file modifications.

Agent sessions operate across heterogeneous tools spanning file inspection, editing, and outcome control. If these capabilities are exposed as disconnected services, orchestrators must duplicate initialization logic, manage race conditions during startup template creation, and manually track workspace mutations. The sandbox interface component establishes a unified session coordination boundary that ensures template materialization precedes agent execution and exposes session-wide file modification state.

**Out of scope:** The sandbox interface component does not schedule multi-node graph traversal, evaluate external model responses, or manage agent memory transcripts; these are handled by other components.

## Types and Behavior

An agent session's *sandbox* coordinates starter template materialization and file modification tracking for the session.

The sandbox provides workspace coordination for the active session.

The sandbox:

- Can *materialize startup templates* into missing read-write files at session start without overwriting existing files.

- Exposes whether workspace file *modifications* occurred during the session.
