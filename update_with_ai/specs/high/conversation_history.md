# conversation_history

imports: tool_provider (tool results, presented tool results, tool call, session)
terms (from tool_provider): tool result, supersession flag, presented tool result, stub, tool call, session
terms (owned): conversation history, history entry, rendered message, stub mapping, system prompt

## Purpose

Manages the chronological message history for an agent session: converts internal history entries to model-ready request messages, strips internal metadata, and applies in-place stubbing to superseded tool results to preserve prefix caching.

## Terms

- Conversation history: the chronological sequence of history entries accumulated during an agent session.
- History entry: a single message record in the conversation history, carrying a role, content, and optional internal metadata.
- Rendered message: a message formatted for transmission to the language model API, with internal metadata removed and tool result notes rendered into visible content.
- Stub mapping: the per-session association between each file path or tool command and the index of its current live tool result in the conversation history.
- System prompt: the static instructions provided to configure the model for the session.

## Contract

**Inputs**

- Per session: a user prompt, a system prompt, assistant messages, tool call records, tool results, and session-start tool results.

**Operations**

- Initialize the conversation history with an optional user prompt and session-start tool results.
- Append a user message, assistant message, or reminder message to the conversation history.
- Append a tool result or presented tool result to the conversation history, updating the stub mapping and replacing any superseded prior result in place.
- Provide the conversation history entries.
- Provide rendered messages formatted for the language model request.

**Guarantees**

- Conversation history order is chronological.
- The conversation is append-only except for stubbing: when a tool result has the supersession flag set, the earlier live result for the same file path or tool command is replaced in place with the static stub before the new result is added.
- A stub is permanent for the session; stubbed messages retain their positions in the conversation history.
- At most one earlier result is superseded per superseding tool result.
- Rendered messages strip internal metadata fields before presentation to the language model.
- Tool result notes are rendered into the visible content of rendered messages.
- A presented tool result that the model did not initiate is preceded by a synthetic tool call record.
- No history state persists across sessions.

**Assumptions**

- Tool results follow the tool_provider format.
- A tool result supersedes at most one earlier result.

## Non-concerns

- Stub text: the exact wording of the static stub placeholder is unspecified.
- Internal metadata keys: the naming convention for internal metadata fields is an implementation detail.
