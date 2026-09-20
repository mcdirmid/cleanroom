# mcp_asm assembly component

assembles: mcp_cache_arbiter_impl, mcp_gate_impl, mcp_server_impl, mcp_session_impl
imports: agent_config, agent_node_config, agent_session, dag_storage, dag_subgraph, fastmcp_ext, filesystem_ext, sandbox_file_editor, sandbox_file_reader, tool_provider
implements: mcp_cache_arbiter, mcp_gate, mcp_server, mcp_session

## Purpose

The mcp_asm assembly component aggregates session lifecycle management, access gating, cache arbitration, and FastMCP server hosting into the mcp subsystem assembly.

Integrating sub-agent orchestration into desktop environments requires seamless coordination among session scope lifecycles, real-time hook confinement, fifteen-minute cache awareness, and external FastMCP transport loops. Without an integrated assembly, servers and hook endpoints must manually wire session singletons and access gates across process boundaries, risking inconsistent lock states and unmonitored idle sessions. The mcp_asm assembly component unites the concrete implementation components into a cohesive subsystem, closing the mcp interfaces while declaring required dependencies on the sandbox core, agent configurations, and graph storage.

**Out of scope:** The mcp_asm assembly component does not run Bazel test runners, generate code diffs, or format markdown templates; these are handled by other components.

## Types and Behavior

The *mcp assembly* unites the concrete implementation components that realize sub-agent session lifecycles, hook access control, cache-aware task routing, and FastMCP server hosting. The assembly initializes its constituent implementation components and registers their singleton services with the system lifecycle prototype.

The mcp assembly aggregates the following implementation components:

- The role session manager implementation from mcp_session_impl, closing the mcp session interface to manage multi-turn sub-agent session scopes and active session registries.

- The access gate implementation from mcp_gate_impl, closing the mcp gate interface to validate intercepted file tool calls and sanitize directory listings.

- The cache arbiter implementation from mcp_cache_arbiter_impl, closing the mcp cache arbiter interface to evaluate the fifteen-minute cache eviction window and route sampling directives.

- The mcp server implementation from mcp_server_impl, closing the mcp server interface to host the FastMCP application, expose lifecycle and domain tools, and mount hook IPC endpoints.
