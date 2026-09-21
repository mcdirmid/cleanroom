# mcp_server interface component

imports: mcp_session

## Purpose

The mcp_server interface component defines the FastMCP application host, JSON-RPC tool dispatching into session scopes, and hook IPC endpoint routing.

Running Cleanroom as an MCP server requires bridging external client protocols to internal lifecycle-governed session tools while simultaneously serving lifecycle hook requests from external processes. Without a coordinated server host, tool execution turns cannot resolve their corresponding sub-agent scopes, and lifecycle hooks cannot query access gates. The mcp_server interface component establishes an ambient system server that hosts the FastMCP application, registers lifecycle and domain tools, mounts hook validation endpoints, and runs the server transport loop.

**Out of scope:** The mcp_server interface component does not construct dependency graphs, evaluate static linters, or compute file diffs; these are handled by other components.

## Types and Behavior

The *mcp server* is a system service that coordinates tool exposure, session turn scope activation, and hook IPC hosting.

The mcp server:

- Exposes a *register role agent tool* that accepts a role address, a unit root, and a conversation identifier, registering the subagent session.

- Exposes a *deregister role agent tool* that accepts a conversation identifier, deregistering the subagent session.

- Exposes a *shutdown tool* that terminates the server and removes the workspace sentinel.

- Exposes domain tools accepting a conversation identifier, executing incoming tool calls within the active session scope for the caller conversation identifier.

- Hosts a *hook validation endpoint* that accepts access validation requests, producing access decisions.

- Hosts a *directory filter endpoint* that accepts directory sanitization requests, producing sanitized directory listings.

- Server startup executes the transport loop for a specified *transport* mode, hosting tool handlers and hook endpoints while recording the server process identifier, port, and registered subagent conversation identifiers in an active workspace sentinel.

- Active registered subagents in the workspace sentinel update when a role agent is registered or deregistered.

- Server termination cleanly closes active sessions, shuts down endpoints, and removes the workspace sentinel.
