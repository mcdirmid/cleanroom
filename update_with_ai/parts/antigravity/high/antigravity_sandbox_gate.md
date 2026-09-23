# antigravity_sandbox_gate interface component

imports: antigravity_run_logger

## Purpose

The antigravity_sandbox_gate interface component defines the pre-tool gating service that enforces Cleanroom sandboxing and role confinement within Antigravity.

Autonomous coding agents executing within IDE environments risk unauthorized shell execution and out-of-scope file modifications if unconstrained. The antigravity_sandbox_gate interface component defines the gating decisions and inspection services that intercept tool calls, validate commands against whitelists, and gate file access via Model Context Protocol servers.

**Out of scope:** The antigravity_sandbox_gate interface component does not schedule worker batches, parse syntax trees, or compute token costs; these are handled by other components.

## Types and Behavior

A *gating decision* record represents the outcome of evaluating a tool call, exposing a *decision* status, a *reason*, and an optional *overwrite* mapping.

The *antigravity sandbox gate* is a system service that validates subagent tool invocations before execution. The antigravity sandbox gate provides:

- A *process hook input* operation that evaluates a raw JSON *payload* string and returns a gating decision.

- A *validate worker command* operation that inspects a *command line* and determines whether execution is permitted.

- A *validate coordinator command* operation that inspects a *command line* and determines whether coordinator execution is permitted.

- An *is coordinator caller* operation that verifies whether a conversation *identifier* belongs to a coordinator subagent.

- An *is role worker caller* operation that verifies whether a conversation *identifier* belongs to a role worker subagent.

- A *save worker session* operation that associates a worker *identifier* with a session *identifier*.

- A *remove worker session* operation that disassociates a worker identifier.

- A *read worker sessions* operation that returns all active worker session associations.
