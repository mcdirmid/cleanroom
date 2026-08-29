# agent_node_tool_executor_impl

fulfills: agent_node_tool_executor
imports: agent_node_tool_executor (node tool execution, session-start delivery), tool_provider (tool definition, tool result, presented tool result, tool failure, tool call)
terms (from agent_node_tool_executor): node tool execution, session-start delivery
terms (from tool_provider): tool definition, tool result, presented tool result, tool failure, tool call

## Deltas

- Implements agent_node_tool_executor adapting a Sandbox instance.
- Wraps sandbox method calls into unified tool execution outcomes.
- Collects session-start reads from the sandbox and exposes them for initial agent loop seeding.

## Non-concerns

- Subprocess management: handled by sandbox.
- LLM interaction: handled by agent_loop.
