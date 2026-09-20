# mcp_gate interface component

imports: mcp_session

## Purpose

The mcp_gate interface component defines workspace path normalization, tool execution gating, and directory filtering for desktop agent lifecycle hooks.

In desktop environments, language model agents access the workspace using native file inspection, editing, and listing tools. Without real-time access control gating, sub-agents can inspect blinded contract implementations, modify files outside their active targets, or corrupt files locked after submission. The mcp_gate interface component establishes a centralized system service that validates intercepted tool invocations against session permissions and filters directory listings to preserve role blindness.

**Out of scope:** The mcp_gate interface component does not read files from disk, execute static linters, or manage agent turn history; these are handled by other components.

## Types and Behavior

An *access decision* is data representing the authorization result for an intercepted tool invocation.

An access decision provides:

- Whether the invocation *is allowed* to proceed.

- An explanatory *reason* detailing why access was permitted or denied.

The *access gate* is a system service that validates intercepted file access requests and sanitizes directory listings.

The access gate:

- Can *validate access* for a conversation identifier, an intercepted *tool name*, and a target *file path*, producing an access decision.

- Can *filter directory listing* for a conversation identifier, a target *directory path*, and a sequence of child *entries*, producing a sanitized sequence of allowable entries.
