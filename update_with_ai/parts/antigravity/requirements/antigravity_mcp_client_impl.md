# antigravity_mcp_client_impl implementation component

implements: antigravity_mcp_client

## Assumptions and Requirements

### Requirements

1. Calling a tool connects to the server at the configured host and port, transmitting a JSON-encoded request specifying tool name and arguments.
2. When the server responds with a success status, the client extracts and returns the content text.
3. When communication fails or the server returns an error, the client returns an error diagnostic string.
4. Registering a session dispatches the server registration tool binding session identifier, role, and unit.
5. Deregistering a session notifies the server to release resources associated with the session.
6. Retrieving work invokes the domain get work tool within the session scope, returning task descriptions and incoming change notifications.
7. Running check files executes batch verification across all files assigned to the session.
8. Submitting commits modifications for an open target with the provided change summary.
9. Recording blame flags an upstream defect with an explanation.
10. Shutting down sends the server shutdown command.
11. Querying the next batch executes the server wave resolution tool for the resolved target unit.

## Grounding Facts

### Knowledge Needed

- Server host address and port number.
- Tool request payload schemas.
- Session parameters.
- Target modification details.
- Blame defect details.

### Actions Needed

- Transmit JSON-encoded tool request to server.
- Parse server response text or extract error diagnostics.
- Dispatch registration, deregistration, get-work, check-files, submit, blame, shutdown, and wave resolution tools.
