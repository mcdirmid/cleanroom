# agent_node_tool_executor

imports: tool_provider (tool definition, tool result, presented tool result, tool failure, tool call), dag_clean_logic (cleaning)
terms (from tool_provider): tool definition, tool result, presented tool result, tool failure, tool call
terms (from dag_clean_logic): cleaning
terms (owned): node tool execution, session-start delivery

## Purpose

Adapts sandbox operations into an agent-loop-compatible tool executor, providing tool definitions, tool dispatch, and session-start tool result delivery.

## Terms

- Node tool execution: dispatching agent tool calls to underlying sandbox operations and formatting presented outcomes.
- Session-start delivery: retrieving pre-injected session-start tool results from the sandbox to seed the initial conversation.

## Contract

**Inputs**

- Collaborators: sandbox (providing file operations, guide delivery, and run control tools).
- Per tool call: tool name and argument dictionary.

**Operations**

- Retrieve tool definitions.
- Execute tool call.
- Retrieve session-start tool results.

**Guarantees**

- Dispatches tool invocations by name to the corresponding sandbox operations.
- Intercepts unknown tool names and signals tool failures listing valid available tools.
- Retrieves session-start reads from the sandbox for initial prompt delivery.

**Assumptions**

- The sandbox provides valid tool definitions matching its supported operations.

## Non-concerns

- Agent loop iteration: executing LLM prompts and turn sequences is handled by agent_loop.
- Cleaning logic: mapping termination signals to DAG outcomes is handled by agent_node_clean_logic.
