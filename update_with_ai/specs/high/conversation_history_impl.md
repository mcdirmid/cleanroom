# conversation_history_impl

fulfills: conversation_history
imports: tool_provider (tool results, presented tool results, tool call, session)
terms (from conversation_history): conversation history, history entry, rendered message, stub mapping, system prompt
terms (from tool_provider): tool result, supersession flag, presented tool result, stub, tool call, session

## Deltas

- Formats messages for the OpenAI chat completion API (user, assistant, tool, and system message parameters).
- Strips internal metadata fields (prefixed with an underscore) when converting history entries to OpenAI parameters.
- [state] Tracks the mapping between each file path or tool command and its current live tool result index; replaces earlier results with static stub text upon supersession.
- [ordering] A presented tool result carries its tool call; the implementation generates a fresh synthetic tool call identifier and appends an assistant tool call message immediately before appending the tool message.
- [state] Resets all message lists, stub mappings, and synthetic call counters on initialization so no state persists between sessions.
- [external] The OpenAI API (openai_api) message parameter schemas.

## Non-concerns

- Stub text: the static stub text replaces superseded content in place.
