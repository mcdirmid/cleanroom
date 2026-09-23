# antigravity_asm assembly component

assembles: antigravity_coordinator_impl, antigravity_mcp_client_impl, antigravity_run_logger_impl, antigravity_sandbox_gate_impl, antigravity_telemetry_impl
implements: antigravity_coordinator, antigravity_mcp_client, antigravity_run_logger, antigravity_sandbox_gate, antigravity_telemetry

## Purpose

The antigravity_asm assembly component aggregates the coordinator, telemetry, sandbox gate, run logger, and mcp client implementations into the unified Cleanroom Antigravity platform assembly.

Coordinating multi-agent Cleanroom execution within Antigravity requires integrating pre-tool sandboxing, transcript logging, API telemetry, Model Context Protocol communication, and deterministic wave scheduling into a cohesive system. The antigravity_asm assembly component binds these constituent implementations, closing all platform interfaces.

**Out of scope:** The antigravity_asm assembly component does not parse command-line flags, execute bazel builds, or generate source code; these are handled by other components.

## Types and Behavior

The *antigravity assembly* unites the platform implementations into a complete subsystem. The antigravity assembly initializes its constituent implementations, registering singleton services with the system lifecycle registry.

The antigravity assembly aggregates the following constituents:

- The coordinator implementation from antigravity_coordinator_impl, closing the antigravity coordinator interface to calculate wave schedules and manage worker pools.

- The mcp client implementation from antigravity_mcp_client_impl, closing the antigravity mcp client interface to dispatch domain tool requests to the server.

- The run logger implementation from antigravity_run_logger_impl, closing the antigravity run logger interface to record execution milestones.

- The sandbox gate implementation from antigravity_sandbox_gate_impl, closing the antigravity sandbox gate interface to intercept and validate tool requests.

- The telemetry implementation from antigravity_telemetry_impl, closing the antigravity telemetry interface to measure token usage and API costs.
