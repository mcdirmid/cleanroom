<!-- Dependencies (md files to read alongside this one): -->
# Interface LLS: tool_provider
## Data Types

```python
from dataclasses import dataclass
from typing import Optional, Protocol, TypeAlias
@dataclass
class ToolDefinition:
    name: str
    parameters: object
    description: str

@dataclass
class ToolResult:
    content: str
    supersession_flag: bool
    note: Optional[str]

@dataclass
class TerminationResult:
    outcome: str
    feedback: Optional[str] = None

ToolFailure: TypeAlias = str

@dataclass
class ToolSession:
    tool_calls: list
    results: list

ReplacementStub: TypeAlias = str

class ToolProvider(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def execute_tool_call(self, tool_name: str, tool_arguments: object) -> tuple[str, list[ToolResult], Optional[TerminationResult], Optional[ToolFailure]]: ...
```

- **Signal values**: the indicator of whether execution continues, terminates, or fails; the values are `continue`, `terminate the run with success`, `terminate the run with failure`, and `tool failure`.
- **Termination outcome values**: the possible outcomes of a successfully terminated session — `completed with no changes`, `completed with changes to propagate`, or `attributed to dependencies with feedback for correction`.
- **ToolDefinition**: a JSON schema describing a tool's name, parameters, and purpose, in the tool-calling dialect accepted by the language model.
- **ToolResult**: a structured outcome produced by executing a tool call — the content produced, a supersession flag, and an optional note carrying producer-generated guidance for the model. The note does not replace the content; the consuming agent loop renders it into the model-visible message.
- **TerminationResult**: the outcome of a successfully terminated session, carried by the successful termination signal.
- **ToolFailure**: a signal that a tool call could not do meaningful work — wrong arguments, wrong format, an unknown tool, a policy violation, or a termination tool invoked incorrectly; the operation is not executed and the session continues.
- **ToolSession**: the sequence of tool calls and outcomes of a single run, continuing until a termination signal is produced.
- **Error state preservation**: errors leave the provider's state unchanged; stubbing preserves the original position of messages in the conversation.

## Component-Provided Operations

### `get_tool_definitions`

**Purpose:** Request and return the list of available tool definitions.

**Preconditions:** None.

**Postconditions:** Returns the complete list of tool definitions available in the current session. Each tool definition conforms to the schema format defined by this interface.

**Failure Handling:** None documented — error handling is not documented.

**HLS Justification:** "Request the list of available tool definitions." (HLS: Operations)

### `execute_tool_call`

**Purpose:** Execute a tool call given the tool name and arguments.

**Preconditions:** None.

**Postconditions:**
- All inputs are validated against the tool's schema before execution; an invalid tool call signals tool failure without executing the operation.
- Each tool call produces exactly one outcome: either one or more tool results, or a signal (continue, terminate with success, terminate with failure, or tool failure).
- Tool results contain the content, the supersession flag, and the note.
- A tool result never carries the stub text: the stub text appears only when earlier results are replaced in the conversation.
- When a result's supersession flag is set, the earlier non-stubbed result for the same file or tool command is stubbed in place with a static stub.
- A stub is static once set: a stubbed result's placeholder never changes for the remainder of the session.
- The flag unset (False) stubs nothing.
- A result supersedes at most one earlier result.
- A successful termination signal always carries a termination result; a failure termination signal carries a value describing the failure.
- Termination is atomic: once a termination signal is produced, no further tool results are produced.
- Errors leave the provider's state unchanged; stubbing preserves the original position of messages in the conversation.
- The provider does not interpret tool results; it produces them.

**Failure Handling:**
- `ToolFailure` is returned when: wrong arguments, wrong format, an unknown tool, a policy violation, or a termination tool invoked incorrectly.
- A check that failed or a result rejected with feedback is a tool result carrying the feedback, never a tool failure.
- The tool failure signal does not execute the operation and does not end the session.

**HLS Justification:** "Execute a tool call." (HLS: Operations)

## Invariants

- The observable structure of a tool result is limited to its semantic content, the supersession flag, and the note.
