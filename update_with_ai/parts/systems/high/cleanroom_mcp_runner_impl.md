# cleanroom_mcp_runner_impl implementation component

imports: mcp_server, runner_logger
implements: cleanroom_mcp_runner

## Purpose

The cleanroom_mcp_runner_impl implementation component realizes the cleanroom mcp runner service to parse execution parameters and launch the Cleanroom Model Context Protocol server.

Sub-agent orchestration across external client environments requires consistent argument handling and clean delegation to server lifecycle interfaces. The cleanroom_mcp_runner_impl implementation component translates command-line argument sequences into typed runner options, initializes server network bindings, and logs startup milestones to ensure reliable server deployment.

**Out of scope:** The cleanroom_mcp_runner_impl implementation component does not parse build manifests, enforce file locks, or schedule tasks; these are handled by other components.

## Types and Behavior

The cleanroom mcp runner operates as a system service executing the Cleanroom Model Context Protocol server.

Executing the runner validates runner options and executes the server using the configured transport. When standard input/output transport is requested, the runner executes the server over standard input/output. When Server-Sent Events transport is requested, the runner configures server host and port parameters, logs startup progress, and executes the server over Server-Sent Events. The runner sets the batch size in the execution environment.

Parsing arguments converts command-line argument tokens into a runner options record:

- The transport resolves from `--transport`, accepting `stdio` or `sse`, defaulting to `stdio`.

- The host resolves from `--host`, defaulting to `127.0.0.1`.

- The port resolves from `--port` as an integer, defaulting to 8765.

- The batch size resolves from `--batch-size` as an integer, defaulting to 10.

Parsing arguments signals an error when invalid or unknown options are provided.
