# sandbox interface component

imports: tool_provider, model_config

## Purpose

The sandbox interface component coordinates the execution environment for an agent session, provisioning startup context, materializing starter templates, and tracking file modifications.

Agent sessions operate across heterogeneous tools spanning file inspection, editing, guide step mode, and outcome control. If these capabilities are exposed as disconnected services, orchestrators must duplicate initialization logic, manage race conditions during startup template creation, and manually assemble startup context. The sandbox interface component establishes a unified session coordination boundary that packages startup tool executions, ensures template materialization precedes agent execution, and exposes session-wide file modification state.

**Out of scope:** The sandbox interface component does not schedule multi-node graph traversal, evaluate external model responses, or manage agent memory transcripts; these are handled by other components.

## Types and Behavior

A *startup tool execution* packages a *tool name*, *wire parameter bindings*, and a *response* for an initial tool invocation at session start. In agent conversation transcripts, tool responses cannot exist in isolation; transcript schemas require that every tool response correlates to an antecedent assistant tool request. Packaging the tool name and wire parameter bindings alongside the response allows orchestrators to forge both the synthetic tool request and response turns when seeding the session transcript.

The *sandbox* is an agent session service configured with whether to use step mode to communicate a guide progressively and whether to perform startup reads to inspect declared files at session start, coordinating startup context and workspace file management for an agent session.

The sandbox:

- Exposes *startup tool executions* as an ordered sequence of initial tool executions based on active configuration, ordering startup reads deterministically by file alias short name.

- Can *materialize startup templates* into missing read-write files at session start without overwriting existing files.

- Exposes whether workspace file *modifications* occurred during the session.
