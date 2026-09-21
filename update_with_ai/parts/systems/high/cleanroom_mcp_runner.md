# cleanroom_mcp_runner interface component

## Purpose

The cleanroom_mcp_runner interface component defines the server execution service that starts and runs the Cleanroom Model Context Protocol server.

Executing autonomous sub-agent orchestration across external desktop client environments requires a controlled execution entry point that parses invocation options, establishes system lifecycle phase bounds, and maintains server availability across transport loops. The cleanroom_mcp_runner interface component defines the system service and options for starting the MCP server over standard input/output or Server-Sent Events transports.

**Out of scope:** The cleanroom_mcp_runner interface component does not implement protocol serialization, manage file sandboxing, or evaluate dependency graphs; these are handled by other components.

## Types and Behavior

A *runner options* record provides execution parameters for running the server, exposing a *transport*, a *host*, a *port*, and a *batch size*.

The *cleanroom mcp runner* is a system service that executes the Cleanroom Model Context Protocol server. The cleanroom mcp runner provides:

- A *run* operation that executes the server using runner options.

- A *parse arguments* operation that parses command-line *arguments* into runner options.
