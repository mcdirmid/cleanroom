# agent_conversation_history_impl implementation component

imports: tool_provider
implements: agent_conversation_history

## Purpose

The agent_conversation_history_impl implementation component realizes provider role formatting, metadata stripping, and synthetic tool invocation injection for model conversation requests.

Language model APIs impose strict role alternation invariants and reject internal orchestration fields. The agent_conversation_history_impl implementation component formats messages according to provider role schemas, strips internal metadata fields, preserves visible diagnostic notes, and pairs unprompted tool responses with antecedent synthetic assistant invocations to preserve API protocol compliance.

**Out of scope:** The agent_conversation_history_impl implementation component does not transmit network payloads to remote endpoints, enforce repetition guards, or record unbuffered log files; these are handled by other components.

## Types and Behavior

The conversation history formats messages in a model request according to model provider roles for system, user, assistant, and tool messages.

When assembling a model request from messages in the agent conversation history:

- Messages omit internal metadata fields starting with an underscore.

- Tool execution response notes and content from the tool provider are included in visible tool message content.

- An unprompted tool response presented at session start is preceded in the conversation history by a synthetic assistant tool invocation message addressing the corresponding tool name.
