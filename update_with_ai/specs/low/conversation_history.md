<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
-->

# Interface LLS: conversation_history

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence, Mapping, Any, Optional, Union
from dataclasses import dataclass
from tool_provider import ToolResult, Tool

MessageRole: TypeAlias = str
MessageContent: TypeAlias = str
MetadataField: TypeAlias = str
MetadataContent: TypeAlias = Any
MetadataMapping: TypeAlias = Mapping[MetadataField, MetadataContent]

@dataclass(frozen=True)
class HistoryMessage:
    role: MessageRole
    content: MessageContent
    metadata: Optional[MetadataMapping] = None

@dataclass(frozen=True)
class HistoryStub(HistoryMessage):
    role: MessageRole = "tool"
    content: MessageContent = "..."

@dataclass(frozen=True)
class ModelRequest:
    messages: Sequence[HistoryMessage]
    tools: Optional[Sequence[Tool]] = None

class ConversationHistory(Protocol):
    def initialize(self, initial_messages: Sequence[HistoryMessage]) -> None: ...
    def append(self, item: Union[HistoryMessage, ToolResult]) -> None: ...
    def get_model_request(self) -> ModelRequest: ...
    def get_messages(self) -> Sequence[HistoryMessage]: ...

class ConversationHistoryFactory(Protocol):
    def create_conversation_history(self) -> ConversationHistory: ...
```

- `MessageRole` → corresponds to message role (system, user, assistant, tool).
- `MessageContent` → corresponds to content of a message.
- `MetadataField` → corresponds to metadata field name.
- `MetadataContent` → corresponds to metadata value content.
- `MetadataMapping` → corresponds to message metadata mapping.
- `HistoryMessage` → corresponds to *message*: an entry in a *conversation history*.
- `HistoryStub` → corresponds to *stub*: a placeholder *message* replacing superseded content in a *conversation history*.
- `ModelRequest` → corresponds to *model request*: a formatted sequence of *messages* prepared for transmission to a language model.
- `ConversationHistory` → corresponds to *conversation history*: a chronological sequence of *messages* for an agent run.
- `ConversationHistoryFactory` → corresponds to *conversation history factory*: a provider that constructs fresh *conversation histories*.

## Term definitions

- **message** → the `HistoryMessage` alias
- **stub** → the `HistoryStub` alias
- **model request** → the `ModelRequest` alias
- **conversation history** → term definition: a chronological sequence of *messages* for an agent run
- **conversation history factory** → term definition: a provider that constructs fresh *conversation histories*

## Component-Provided Operations

### `initialize`

```python
def initialize(self, initial_messages: Sequence[HistoryMessage]) -> None: ...
```

**Purpose:** (ConversationHistory) Initializes a fresh conversation history with starting messages.

**Preconditions:** None.

**Postconditions:**
- Sets history entries to `initial_messages` in chronological order.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Initial *messages* can initialize a *conversation history*."

### `append`

```python
def append(self, item: Union[HistoryMessage, ToolResult]) -> None: ...
```

**Purpose:** (ConversationHistory) Appends a message or tool result to the conversation history, replacing superseded results with stubs in place.

**Preconditions:** None.

**Postconditions:**
- Appends `item` in chronological order.
- If `item` is a `ToolResult` that supersedes an earlier result for the same resource, the earlier result is replaced in place with a `Stub`.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Appending *messages* and *tool results* adds them to a *conversation history* in chronological order."

### `get_model_request`

```python
def get_model_request(self) -> ModelRequest: ...
```

**Purpose:** (ConversationHistory) Formats the conversation history into a model request ready for language model transmission.

**Preconditions:** None.

**Postconditions:**
- Returns a `ModelRequest` containing chronological messages with internal metadata stripped.

**Failure Handling:** Always succeeds.

**HLS Justification:** "A *conversation history* provides a *model request* for a language model."

### `get_messages`

```python
def get_messages(self) -> Sequence[HistoryMessage]: ...
```

**Purpose:** (ConversationHistory) Retrieves the unformatted sequence of messages in history.

**Preconditions:** None.

**Postconditions:**
- Returns the chronological sequence of history messages.

**Failure Handling:** Always succeeds.

**HLS Justification:** "A *conversation history* is a chronological sequence of *messages*."

### `create_conversation_history`

```python
def create_conversation_history(self) -> ConversationHistory: ...
```

**Purpose:** (ConversationHistoryFactory) Creates a fresh conversation history instance.

**Preconditions:** None.

**Postconditions:**
- Returns a fresh `ConversationHistory`.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Creating a *conversation history* through a *conversation history factory* yields a fresh *conversation history*."

## Invariants

- HistoryMessage history is strictly append-only except for in-place supersession stubbing.
- In-place stubbing preserves prompt caching prefix alignment.
