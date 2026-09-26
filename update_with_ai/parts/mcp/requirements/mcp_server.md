# mcp_server interface component

imports: mcp_session

## Assumptions and Requirements

### Requirements

1. Exposes a register role agent tool that accepts a role address, a unit root, and a conversation identifier, registering the subagent session.
2. Exposes a deregister role agent tool that accepts a conversation identifier, deregistering the subagent session.
3. Exposes a shutdown tool that terminates the server and removes the workspace sentinel.
4. Exposes domain tools accepting a conversation identifier, executing incoming tool calls within the active session scope for the caller conversation identifier.
5. Hosts hook validation and directory filter endpoints, producing access decisions and sanitized directory listings.
6. Server startup begins the transport loop and writes the workspace sentinel, updating registered subagents on registration and deregistration, and server termination cleanly closes active sessions, shuts down endpoints, and removes the sentinel.

## Grounding Facts

### Knowledge Needed

- Registered tools inventory and schemas.
- Active session scope for conversation identifier.
- Workspace sentinel file path.

### Actions Needed

- Register subagent session.
- Deregister subagent session.
- Terminate server and remove workspace sentinel.
- Dispatch domain tool execution within session scope.
- Validate hook access and filter directory listings.
