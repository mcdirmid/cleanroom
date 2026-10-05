<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T02:07:35Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 7edbb62787ca
-->

# loop_conversation interface component

imports: tool_provider

## Intent

Repeated tool executions cause message context to explode and degrade model performance. The loop_conversation interface component manages message accumulation across turns, formatting model-ready request sequences while replacing superseded tool results with compact stubs in place to preserve prompt caching and bound token growth.

By tracking message roles, correlating tool calls, and stubbing obsolete tool payload exchanges, the conversation service preserves critical context while avoiding context window exhaustion.

## Factored Contracts

### Typing

- A conversation message is an entry in an agent conversation.
- A conversation message has a role.
- A conversation message has text content.
- A conversation message has a tool call id.
- A conversation message has a tool name.
- A conversation message has a reminder.
- A conversation message has serialized tool arguments.
- A conversation message indicates whether the message is a stub.
- A model request is a formatted sequence of messages prepared for transmission to a language model.

### Contracts

- The conversation is initialized with initial messages. [initialize_with_initial_messages]
- Initial messages include task instructions. [initial_messages_include_task_instructions]
- A caller supplies messages when appending to a conversation. [append_messages_supplied]
- The conversation appends messages produced by tool execution. [append_messages_to_conversation]
- The conversation appends tool responses produced by tool execution. [append_tool_responses_to_conversation]
- The conversation stubs previous responses identified by a suppression key. [stub_previous_responses_by_key]
- The conversation stubs correlating tool arguments identified by a suppression key. [stub_correlating_tool_args_by_key]
- The conversation provides a model request for transmission to a language model. [provide_model_request]

## Woven Contracts

- Initializing conversation populates starting message history with task instructions. [initialize_with_initial_messages, initial_messages_include_task_instructions]
- Appending updates conversation history with model messages and tool responses. \[append_messages_supplied, append_messages_to_conversation, append_tool_responses_to_conversation, tool_provider: [call_by_name]\]
- When subsequent tools matching a suppression key execute, previous tool outputs and correlating arguments are replaced with stubs in place. [stub_previous_responses_by_key, stub_correlating_tool_args_by_key]
- Formatted conversation history is exported as a model request for provider transmission. [provide_model_request]
