<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - conversation_history.md
-->

# Implementation LLS: conversation_history_impl

## Data Types
```python
from conversation_history import ConversationHistory, ConversationHistoryFactory

class _ConversationHistoryImpl(ConversationHistory):
    def __init__(self) -> None: ...

class ConversationHistoryFactoryImpl(ConversationHistoryFactory):
    def __init__(self) -> None: ...
```

## Behavioral Description

- `ConversationHistoryFactoryImpl.create_conversation_history` constructs a fresh `_ConversationHistoryImpl`.
- The internal `_ConversationHistoryImpl` formats messages using model provider role strings (`system`, `user`, `assistant`, `tool`).
- Strips internal metadata fields starting with an underscore (`_`) before producing `ModelRequest`.
- Tool result notes are included in visible tool message content within a `ModelRequest`.
- Precedes unprompted presented tool results with a synthetic assistant tool call message to preserve role alternation invariants.
- Replaces superseded tool result contents in place with static stub markers (`...`).

## Invariants

- HistoryMessage history preserves chronological order.
