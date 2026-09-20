# mcp_server_impl implementation component

imports: fastmcp_ext, mcp_cache_arbiter, mcp_gate, mcp_session, tool_provider
implements: mcp_server

## Purpose

The mcp_server_impl implementation component realizes FastMCP tool registration, conversation scope activation, Hook HTTP endpoints, and sampling execution.

FastMCP tools must transparently bind incoming JSON-RPC calls to the caller session scope without requiring sub-agents to pass redundant credentials or manually manage context scopes. Without automated scope resolution per turn, multi-turn tool handlers cannot access session-isolated singletons or release locks upon termination. The mcp_server_impl implementation component integrates FastMCP application setup, context-based conversation identification, tool turn scope activation, and loopback HTTP routing for Antigravity hooks into a unified server process.

**Out of scope:** The mcp_server_impl implementation component does not parse Python abstract syntax trees, execute Bazel actions, or format markdown templates; these are handled by other components.

## Types and Behavior

The mcp server initializes a FastMCP application instance and configures tool registrations.

Conversation identifier extraction resolves the caller conversation identifier from the FastMCP request context session identifier or metadata attributes. When the request context does not supply a conversation identifier, the tool invocation accepts an explicit conversation identifier parameter.

Lifecycle tools manage sub-agent session bounds:

- The register role agent tool resolves the conversation identifier and delegates to the role session manager to register the session, returning structured registration confirmation.

- The deregister role agent tool resolves the conversation identifier and delegates to the role session manager to close and remove the session, returning structured deregistration confirmation.

Domain tool execution dispatches turns into session scopes:

- Registered domain tools include the get work tool, check file tool, submit tool, blame tool, and fail tool.

- For each domain tool invocation, the mcp server resolves the caller conversation identifier, touches the session timestamp in the role session manager, and retrieves the session lifecycle scope.

- If no session is registered for the conversation identifier, domain tool execution returns an error response indicating an unregistered session.

- The retrieved scope is activated using the scope activate context manager for the duration of the tool execution turn.

- Inside the activated scope, the tool is executed on the session tool manager using the supplied argument mapping, transitioning session status to idle when get work produces an idle response, or active when tasks are retrieved, and returning the output content.

Hook IPC routes serve intercepted requests:

- An access validation HTTP route receives requests containing a conversation identifier, tool name, and file path, delegating to the access gate and returning JSON-serialized access decisions.

- A directory filter HTTP route receives requests containing a conversation identifier, directory path, and directory entries, delegating to the access gate and returning JSON-serialized filtered entries.

Starting the server begins the transport loop in standard input and output mode or Server-Sent Events mode, launching a background monitoring task that evaluates the cache arbiter to dispatch sampling directives when idle sessions have ready work. Stopping the server cancels background tasks, terminates the transport loop, and deregisters all active sessions from the role session manager.
