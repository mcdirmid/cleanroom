<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
-->

# Interface LLS: conversation_history

## Data Types
```python
from typing import Any, Callable, Literal, Protocol, TypeAlias
from tool_provider import ToolResult, PresentedToolResult, ToolCall

HistoryEntry: TypeAlias = dict[str, Any]

LogEvent: TypeAlias = Literal[
    "message_added",
    "message_stubbed",
    "tool_called",
    "tool_result",
    "api_response",
    "response_truncated",
    "run_terminated",
    "reminder_injected",
    "error",
]

LoggerCallback: TypeAlias = Callable[[LogEvent, dict[str, Any]], None]

RenderedMessage: TypeAlias = dict[str, Any]

StubMapping: TypeAlias = dict[tuple[str, str], int]

class ConversationHistory(Protocol):
    def reset(self) -> None: ...
    def initialize(self, prompt: str, session_start_results: list[PresentedToolResult] | None = None, logger: LoggerCallback | None = None) -> None: ...
    def append_message(self, message: HistoryEntry, logger: LoggerCallback | None = None) -> None: ...
    def add_tool_result(self, tool_call: ToolCall | None, result: ToolResult | PresentedToolResult, logger: LoggerCallback | None = None) -> None: ...
    def get_history(self) -> list[HistoryEntry]: ...
    def get_rendered_messages(self, system_prompt: str | None = None) -> list[RenderedMessage]: ...
```

A rendered message is a dictionary formatted for the language model chat completion request, with internal metadata fields removed and tool result notes rendered into visible content.

A stub mapping associates a target key (file path or tool command) with the index of its current live tool result in the conversation history.

## Term definitions

- **conversation history** → the `list[HistoryEntry]` sequence returned by `get_history`
- **history entry** → the `HistoryEntry` alias (definition in Data Types)
- **rendered message** → the `RenderedMessage` alias (definition in Data Types)
- **stub mapping** → the `StubMapping` alias (definition in Data Types)
- **system prompt** → term definition from high/conversation_history.md
- **tool result** → the `ToolResult` type from tool_provider
- **supersession flag** → the `supersedes` boolean field of ToolResult from tool_provider
- **presented tool result** → the `PresentedToolResult` type from tool_provider
- **stub** → term definition from tool_provider
- **tool call** → the `ToolCall` alias from tool_provider
- **session** → term definition from tool_provider

## Component-Provided Operations

### `reset`

```python
def reset(self) -> None
```

**Purpose:** Resets the conversation history, stub mappings, and synthetic call counters to an empty state.

**Preconditions:** None

**Postconditions:**
- History entries list is empty
- Stub mapping is empty
- Synthetic tool call counter is zero

**Failure Handling:** None

**HLS Justification:** "No history state persists across runs."

### `initialize`

```python
def initialize(self, prompt: str, session_start_results: list[PresentedToolResult] | None = None, logger: LoggerCallback | None = None) -> None
```

**Purpose:** Initializes a fresh conversation for a run with an optional user prompt and session-start results.

**Preconditions:**
- `prompt` is a string (if non-empty, appended as the initial user message)
- `session_start_results` when provided is a list of `PresentedToolResult` values

**Postconditions:**
- Resets previous run state
- If `prompt` is non-empty, appends a user message `{"role": "user", "content": prompt}` to history and emits `message_added` logger event
- If `session_start_results` are provided, each result is presented with its tool call and appended to history, applying in-place stubbing if configured

**Failure Handling:** None

**HLS Justification:** "Initialize the conversation history with an optional user prompt and session-start tool results."

### `append_message`

```python
def append_message(self, message: HistoryEntry, logger: LoggerCallback | None = None) -> None
```

**Purpose:** Appends a message entry to the conversation history and notifies the logger.

**Preconditions:**
- `message` contains a valid role and optional content or tool calls

**Postconditions:**
- Appends the message to the conversation history
- Emits `message_added` logger event

**Failure Handling:** None

**HLS Justification:** "Append a user message, assistant message, or reminder message to the conversation history."

### `add_tool_result`

```python
def add_tool_result(self, tool_call: ToolCall | None, result: ToolResult | PresentedToolResult, logger: LoggerCallback | None = None) -> None
```

**Purpose:** Appends a tool result to the conversation history, replacing any prior superseded result in place.

**Preconditions:**
- `result` is a `ToolResult` or `PresentedToolResult`
- If `result` is a `ToolResult`, `tool_call` must not be None

**Postconditions:**
- If `result` is a `PresentedToolResult`, generates a synthetic tool call identifier and appends an assistant tool call message before the tool message
- Constructs the tool message with role `tool`, `tool_call_id`, `content`, and internal metadata (`_note`, `_tool_name`, `_arguments`)
- If the result's `supersedes` flag is set: replaces the content of the earlier live result for the same key in place with static stub text, marks it stubbed, drops its note, and emits `message_stubbed` logger event
- Appends the new tool message to history and emits `message_added` logger event

**Failure Handling:** None

**HLS Justification:** "Append a tool result or presented tool result to the conversation history, updating the stub mapping and replacing any superseded prior result in place."

### `get_history`

```python
def get_history(self) -> list[HistoryEntry]
```

**Purpose:** Provides the full list of conversation history entries in chronological order.

**Preconditions:** None

**Postconditions:**
- Returns the conversation history list

**Failure Handling:** None

**HLS Justification:** "Provide the conversation history entries."

### `get_rendered_messages`

```python
def get_rendered_messages(self, system_prompt: str | None = None) -> list[RenderedMessage]
```

**Purpose:** Formats the conversation history into rendered message dictionaries ready for language model requests.

**Preconditions:**
- `system_prompt` when provided is a string

**Postconditions:**
- Returns rendered message dictionaries with internal metadata stripped
- If `system_prompt` is provided, prepends a system message
- In tool messages, appends `_note` to visible content when present

**Failure Handling:** None

**HLS Justification:** "Provide rendered messages formatted for the language model request."

## Invariants

- Chronological message ordering is preserved
- Append-only except for in-place stubbing of superseded tool results
- A stubbed message's content never changes once set
- No state persists across runs

## Non-Concerns

- **Stub text:** The exact wording of the static stub text is unspecified.
- **Metadata field naming:** The naming convention for internal metadata fields is an implementation detail.
