# fastmcp_ext external component

## Purpose

The fastmcp_ext external component defines the external FastMCP application and Model Context Protocol boundary for hosting language model tools and dispatching execution turns.

Directly coupling internal domain services to language model desktop orchestrators creates network protocol fragility, transport coupling, and mismatched turn semantics. The fastmcp_ext external component establishes an external boundary that encapsulates FastMCP application hosting, request context extraction, tool registration, and sampling message delivery over standard Model Context Protocol transports.

**Out of scope:** The fastmcp_ext external component does not evaluate file permissions, manage session scopes, or monitor graph progress; these are handled by other components.

## Grounding Gaps Covered

The fastmcp_ext component provides the external domain knowledge and protocol mechanics required to host FastMCP services and interact with Model Context Protocol clients:

- Application hosting and transport lifecycle: Encapsulates the FastMCP application instance, configuration options, standard input and output transport loops, Server-Sent Events transport endpoints, custom Starlette HTTP request and JSON response routing, and clean shutdown handling.

- Request context extraction: Obtains the invocation context for incoming tool calls, extracting the client session identifier and conversation metadata to correlate requests with specific sub-agent sessions.

- Tool registration mechanics: Translates domain tool definitions into FastMCP tool handlers, registering inspectable callable routines configured with parameter signatures, documentation descriptions, and JSON schema constraints.

- Model sampling protocol: Encapsulates asynchronous message creation requests dispatched to connected clients, formatting prompt text and message sequences to trigger sub-agent turns or notify coordinators.

- Wire protocol error translation: Translates protocol exceptions, cancellation signals, and transport timeouts into structured JSON-RPC error responses.
