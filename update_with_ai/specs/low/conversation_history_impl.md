<!-- Dependencies (md files to read alongside this one):
  - conversation_history.md
  - openai_api.md
-->

# Implementation LLS: conversation_history_impl

## Data Types
```python
from conversation_history import ConversationHistory

class ConversationHistoryImpl(ConversationHistory):
    def __init__(self) -> None: ...
```

The implementation maintains internal message lists and stubbing dictionaries.

## Behavioral Description

`ConversationHistoryImpl` fulfills the `ConversationHistory` Protocol by maintaining conversation messages and formatting them for the OpenAI chat completion API.

- **Initialization and Reset:** Resets history entries list, stub tracking mapping, and synthetic tool-call counter.
- **Message Conversion:** Converts internal `HistoryEntry` dictionaries to OpenAI message schemas (`ChatCompletionUserMessageParam`, `ChatCompletionAssistantMessageParam`, `ChatCompletionToolMessageParam`, `ChatCompletionSystemMessageParam`).
- **Internal Metadata Stripping:** Strips any dictionary key prefixed with `_` before sending to the language model API.
- **Tool Result Note Rendering:** In tool messages, appends `_note` to visible `content` so the agent sees execution guidance.
- **In-Place Stubbing:** When adding a tool result with `supersedes=True`, looks up the prior live result index for the target key (file path or tool command). Replaces the prior result's content with the static stub string, marks it stubbed (`_stubbed=True`), drops its `_note`, and emits `message_stubbed` logger event.
- **Presented Tool Results:** When a result is a `PresentedToolResult`, assigns a unique synthetic tool call ID (`call_auto_<n>`), appends an assistant tool call message, and then appends the tool message.

## Invariants

- Chronological message ordering is preserved
- Prior messages are never modified except by in-place stub replacement of superseded tool results
- A stubbed message's content never changes once set
- No state persists between runs

## Non-Concerns

- **Stub text:** Pinned to `Content removed because newer version is available.`
