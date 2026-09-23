# antigravity_mcp_client_impl implementation component

implements: antigravity_mcp_client

## Purpose

The antigravity_mcp_client_impl implementation component realizes HTTP client communication with the Cleanroom Model Context Protocol server.

Subagents and orchestration harnesses need to invoke server operations over HTTP transport without manual socket handling or transport protocol boilerplate. The antigravity_mcp_client_impl implementation component formats JSON tool request payloads, dispatches HTTP POST requests to server endpoints, and parses server response envelopes.

**Out of scope:** The antigravity_mcp_client_impl implementation component does not enforce file edit locks, evaluate test coverage, or maintain subagent conversation records; these are handled by other components.

## Types and Behavior

The antigravity mcp client operates as a system service executing HTTP client requests against the server.

Calling a tool connects to the server at the configured host and port, transmitting a JSON-encoded request specifying tool name and arguments. When the server responds with a success status, the client extracts and returns the content text. When communication fails or the server returns an error, the client returns an error diagnostic string.

Registering a session dispatches the server registration tool binding session identifier, role, and unit. Deregistering a session notifies the server to release resources associated with the session.

Retrieving work invokes the domain get work tool within the session scope, returning task descriptions and incoming change notifications. Running check files executes batch verification across all files assigned to the session.

Submitting commits modifications for an open target with the provided change summary. Recording blame flags an upstream defect with an explanation.

Shutting down sends the server shutdown command. Querying the next batch executes the server wave resolution tool for the resolved target unit.
