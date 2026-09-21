# mcp_server_impl implementation component

imports: dag_storage, dag_subgraph, fastmcp_ext, mcp_cache_arbiter, mcp_gate, mcp_session, tool_provider
implements: mcp_server

## Purpose

The mcp_server_impl implementation component realizes FastMCP tool registration, conversation scope activation, Hook HTTP endpoints, and sampling execution.

FastMCP tools must transparently bind incoming JSON-RPC calls to the caller session scope without requiring sub-agents to pass redundant credentials or manually manage context scopes. Without automated scope resolution per turn, multi-turn tool handlers cannot access session-isolated singletons or release locks upon termination. The mcp_server_impl implementation component integrates FastMCP application setup, context-based conversation identification, tool turn scope activation, and loopback HTTP routing for Antigravity hooks into a unified server process.

**Out of scope:** The mcp_server_impl implementation component does not parse Python abstract syntax trees, execute Bazel actions, or format markdown templates; these are handled by other components.

## Types and Behavior

The mcp server initializes a FastMCP application instance configured with host and port parameters resolved from the execution environment for Server-Sent Events transport, and configures tool registrations.

Conversation identifier extraction resolves the caller conversation identifier from the FastMCP request context session identifier or metadata attributes. When the request context does not supply a conversation identifier, the tool invocation accepts an explicit conversation identifier parameter. When no explicit conversation identifier is supplied and exactly one active session is registered, the invocation resolves to that active session.

Lifecycle tools manage sub-agent session bounds:

- The register role agent tool resolves the conversation identifier and registers the session, returning structured registration confirmation.

- The deregister role agent tool resolves the conversation identifier and closes and removes the session, returning structured deregistration confirmation.

- The shutdown tool terminates the server, removes the workspace sentinel, and stops the process.

Domain tool execution dispatches turns into session scopes:

- Registered domain tools are dynamically exported from installed session tools upon session registration, server start, and domain tool execution.

- Domain tool execution requires an active session matching the caller conversation identifier, failing with an error response when no matching session is registered.

- Domain tool execution executes within the active session scope for the caller conversation identifier, updating the session activity timestamp, exporting newly installed domain tools, and returning the output content.

- Tool execution transitions session status to idle when get work produces an idle response, or active when tasks are retrieved, synchronizing submitted nodes to dag storage and recording visits on dag subgraph when submission succeeds, and attributing defect feedback to the blame target owning node in dag storage when blame succeeds.

Hook IPC routes serve intercepted requests:

- An access validation HTTP route receives requests containing a conversation identifier, tool name, and file path, returning JSON-serialized access decisions.

- A directory filter HTTP route receives requests containing a conversation identifier, directory path, and directory entries, returning JSON-serialized filtered entries.

Server startup begins the transport loop in standard input and output mode or Server-Sent Events mode, launching a background monitoring task that evaluates the cache arbiter to dispatch sampling directives when idle sessions have ready work. Server termination cancels background tasks, terminates the transport loop, and deregisters all active sessions.
