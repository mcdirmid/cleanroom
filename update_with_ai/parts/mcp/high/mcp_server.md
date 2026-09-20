# mcp_server interface component

imports: mcp_session

## Purpose

The mcp_server interface component defines the FastMCP application host, JSON-RPC tool dispatching into session scopes, and hook IPC endpoint routing.

Running Cleanroom as an MCP server requires bridging external client protocols to internal lifecycle-governed session tools while simultaneously serving lifecycle hook requests from external processes. Without a coordinated server host, tool execution turns cannot resolve their corresponding sub-agent scopes, and lifecycle hooks cannot query access gates. The mcp_server interface component establishes an ambient system server that hosts the FastMCP application, registers lifecycle and domain tools, mounts hook validation endpoints, and runs the server transport loop.

**Out of scope:** The mcp_server interface component does not construct dependency graphs, evaluate static linters, or compute file diffs; these are handled by other components.

## Types and Behavior

The *mcp server* is a system service that coordinates tool exposure, session turn scope activation, and hook IPC hosting.

The mcp server:

- Exposes a *register role agent tool* that accepts a role address, a unit root, and a conversation identifier, registering the session with the role session manager.

- Exposes a *deregister role agent tool* that accepts a conversation identifier, deregistering the session with the role session manager.

- Exposes domain tools from the session tool manager, routing incoming tool calls to the active session scope for the caller conversation identifier.

- Hosts a *hook validation endpoint* that accepts access validation requests and delegates to the access gate.

- Hosts a *directory filter endpoint* that accepts directory sanitization requests and delegates to the access gate.

- Can *start* the server on a specified *transport* mode, hosting tool handlers and hook endpoints.

- Can *stop* the server, cleanly closing all active sessions and shutting down endpoints.
