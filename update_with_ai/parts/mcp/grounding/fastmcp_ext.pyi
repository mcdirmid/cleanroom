'''
# External Specification: fastmcp_ext

## External Mechanics & API Documentation

The `fastmcp_ext` external component specifies the third-party FastMCP SDK and Model Context Protocol wire boundary for Cleanroom. External boundary specifications define no standalone library code; rather, dependent implementation components (specifically `mcp_server_impl`) import and invoke the official `mcp` and `mcp.server.fastmcp` modules directly.

**FastMCP Application Construction & Hosting**

- **Class**: `mcp.server.fastmcp.FastMCP` (from `from mcp.server.fastmcp import FastMCP`).
- **Initialization Parameters**:
  - `name: str`: Application identifier name for the FastMCP server (e.g. `"cleanroom"`).
  - `instructions: Optional[str]`: System instructions and capability overview communicated to connected MCP clients.
  - `host: str`: Local network interface binding address; defaults to `"127.0.0.1"`.
  - `port: int`: TCP port for network transports (e.g. `8765` for HTTP/SSE or hook loopback endpoints).
  - `debug: bool`: Logging verbosity and exception traceback propagation.

**Tool Registration & Discovery**

- **Method**: `server.add_tool(fn, name=None, description=None)`.
- **Callable Schema & Signature**:
  - FastMCP inspects Python callable type annotations and `__doc__` docstrings to generate JSON schema definitions for tool parameters.
  - Parameter injection: If a tool function declares a parameter annotated with `mcp.server.fastmcp.Context`, FastMCP automatically injects the active request context object at runtime rather than expecting it in the client tool arguments.
- **Dynamic Tool Listing**: FastMCP automatically serves `tools/list` JSON-RPC requests, advertising registered tool names, descriptions, and input schemas to connected desktop agents.

**Request Context & Client Session Correlation**

- **Class**: `mcp.server.fastmcp.Context` (from `from mcp.server.fastmcp import Context`).
- **Context Properties & Accessors**:
  - `ctx.session`: References the underlying `mcp.server.session.ServerSession` managing the active JSON-RPC transport stream.
  - `ctx.request_context`: Underlying transport request context containing `.meta` and `.session`.
  - `ctx.client_id: Optional[str]`: Connected client identifier if provided in protocol metadata.
  - `ctx.request_id: str`: Unique JSON-RPC request identifier for message correlation.
  - `ctx.report_progress(progress, total=None, message=None)`: Emits out-of-band progress notifications to the client.

**Model Sampling Protocol (sampling/createMessage)**

- **Method**: `session.create_message(messages, max_tokens, system_prompt=None, ...)`.
- **Sampling Parameters**:
  - `messages: list[mcp.types.SamplingMessage]`: Chronological prompt message sequence, where each message provides `role: "user" | "assistant"` and `content: TextContent(type="text", text=prompt)`.
  - `max_tokens: int`: Maximum completion token budget allocated for the sampled turn.
  - `system_prompt: Optional[str]`: Optional system instruction overriding client default behavior.
- **Return Value**: `mcp.types.CreateMessageResult` carrying generated model text in `.content` and completion metadata.

**Transport Execution & Server Lifecycle**

- **Standard I/O Transport**: `server.run(transport="stdio")` or `server.run_stdio_async()` hosts the server over standard input and output pipes for parent process execution.
- **Server-Sent Events (SSE) Transport**: `server.run(transport="sse")` or `server.run_sse_async()` hosts HTTP endpoints for bidirectional streaming.
- **Custom HTTP Routes**: `server.custom_route(path, methods)` mounts additional HTTP routes (such as Hook IPC validation endpoints) directly on the underlying Starlette/Uvicorn server.

## Build Dependencies

- `requirement("mcp")`
- `requirement("starlette")`

## Usage Snippets

### `FastMCP Application Setup with Context-Aware Tools and Custom Routes`

```python
from typing import Any, Mapping, Optional
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import SamplingMessage, TextContent

mcp = FastMCP("cleanroom")

@mcp.tool()
async def register_role_agent(role: str, unit_root: str, ctx: Context) -> str:
    """Registers an Antigravity role sub-agent session."""
    conversation_id = str(ctx.client_id or "default")
    return f"Registered role {role} for conversation {conversation_id}"

async def wake_subagent_via_sampling(ctx: Context, prompt: str) -> None:
    """Dispatches a warm-cache wakeup turn to the sub-agent via MCP Sampling."""
    session = ctx.session
    await session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=prompt),
            )
        ],
        max_tokens=256,
    )
```
'''
