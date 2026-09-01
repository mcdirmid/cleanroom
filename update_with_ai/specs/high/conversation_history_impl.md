# conversation_history_impl

imports: tool_provider, conversation_history
types from tool_provider: tool result
types from conversation_history: conversation history factory, conversation history, message, stub, model request
implements: conversation history factory

## Purpose

Formats conversation history according to model provider role schemas, stripping internal underscore-prefixed metadata and inserting synthetic tool calls to preserve API role alternation invariants.

## Behavior

- Creating a *conversation history* through a *conversation history factory* yields a fresh *conversation history*.
- *Messages* in a *model request* are formatted according to model provider roles for system, user, assistant, and tool messages.
- *Messages* in a *model request* omit internal metadata fields starting with an underscore.
- Tool result notes are included in visible tool *message* content within a *model request*.
- An unprompted presented *tool result* is preceded in a *conversation history* by a synthetic assistant tool invocation *message* addressing the corresponding tool name.
