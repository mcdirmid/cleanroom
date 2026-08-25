<!-- Dependencies (md files to read alongside this one):
  - (none)
-->

# Interface LLS: tool_provider

## Data Types
```python
from typing import Any, Literal, Protocol, TypeAlias
from dataclasses import dataclass

SupersessionFlag: TypeAlias = bool

ExecutionSignal: TypeAlias = Literal["continue", "terminate_success", "terminate_failure", "tool_failure"]

TerminationResult: TypeAlias = Literal["completed_with_no_changes", "completed_with_changes_to_propagate", "attributed_to_dependencies_with_feedback"]

@dataclass
class ToolResult:
    content: str
    supersession_flag: SupersessionFlag
    note: str

ToolFailure: TypeAlias = str

@dataclass
class ToolDefinition:
    name: str
    parameters: Any
    purpose: str

@dataclass
class ToolCall:
    tool_name: str
    arguments: Any

class ToolProvider(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def execute_tool_call(self, tool_call: ToolCall) -> tuple[list[ToolResult] | None, ExecutionSignal, TerminationResult | ToolFailure | None]: ...
```

**ToolResult:** A structured outcome produced by executing a tool call, containing the content produced, a supersession flag, and an optional note carrying producer-generated guidance for the model. The note does not replace the content; the consuming agent loop renders it into the model-visible message.

**SupersessionFlag:** A boolean flag indicating whether the result supersedes the earlier non-stubbed result for the same file or tool command. A result without the flag never supersedes an earlier result. When set, the earlier non-stubbed result is replaced by a static stub. The flag unset stubs nothing. A result supersedes at most one earlier result.

**ExecutionSignal:** A literal union of execution states: "continue" (execution proceeds), "terminate_success" (session ends successfully), "terminate_failure" (session ends with a failure), or "tool_failure" (the tool call could not do meaningful work).

**TerminationResult:** The outcome carried by "terminate_success": "completed_with_no_changes", "completed_with_changes_to_propagate", or "attributed_to_dependencies_with_feedback".

**ToolFailure:** A signal indicating a tool call could not do meaningful work — wrong arguments, wrong format, an unknown tool, a policy violation, or a termination tool invoked incorrectly. The operation is not executed and the session continues.

**ToolDefinition:** A JSON schema describing a tool's name, parameters, and purpose, in the tool-calling dialect accepted by the language model.

**ToolCall:** A tool invocation consisting of a tool name and tool arguments.

## Term definitions

- **tool definition** → the `ToolDefinition` alias
- **tool result** → the `ToolResult` alias
- **supersession flag** → the `SupersessionFlag` alias
- **stub** → a placeholder that replaces a superseded tool result's content when the supersession flag is set; the consumer handles stubbing, not the provider.
- **signal** → the `ExecutionSignal` alias
- **termination result** → the `TerminationResult` alias
- **tool failure** → the `ToolFailure` alias
- **session** → term definition: The sequence of tool calls and outcomes of a single run, continuing until a termination signal is produced.

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]: ...
```

**Purpose:** Request the list of available tool definitions.

**Preconditions:** None.

**Postconditions:** Returns the full list of available `ToolDefinition` objects. Tool definitions conform to the schema format defined by this interface.

**Failure Handling:** No failures are expected; if the provider has no tool definitions, an empty list is returned.

**HLS Justification:** Contract → Operations → "Request the list of available tool definitions."

### `execute_tool_call`

```python
def execute_tool_call(self, tool_call: ToolCall) -> tuple[list[ToolResult] | None, ExecutionSignal, TerminationResult | ToolFailure | None]: ...
```

**Purpose:** Execute a tool call by name with the provided arguments.

**Preconditions:** None.

**Postconditions:** Produces exactly one outcome: one or more `ToolResult` objects, or an `ExecutionSignal`. The `ToolResult` structure and the `SupersessionFlag` behavior are defined in the Data Types section. A successful termination signal always carries a `TerminationResult`; a failure termination signal carries a value describing the failure. Termination is atomic: once a termination signal is produced, no further tool results are produced.

**Failure Handling:** If the tool call arguments are invalid (wrong arguments, wrong format, unknown tool, policy violation, or termination tool invoked incorrectly), returns `(None, "tool_failure", None)`. Invalid tool calls do not execute the operation. Errors leave the provider's state unchanged. A rejected result with feedback is a `ToolResult`, never a `ToolFailure`.

**HLS Justification:** Contract → Operations → "Execute a tool call"; Contract → Guarantees → input validation and tool failure signaling.

## Invariants

- A tool failure signals an immediate problem that prevented meaningful work.
- The provider does not interpret tool results; it produces them.
- May maintain state across tool calls within a single session; no state persists across sessions.

## Non-Concerns

- **Tool result structure:** Only the semantic content, the supersession flag, and the note are observable. — The HLS states this as a non-concern; the provider does not interpret or validate the content structure.
- **Termination signal routing:** The consumer routes termination signals appropriately and interprets the carried termination result. — The HLS states this as an assumption; the provider does not handle routing.
- **Result stubbing:** The consumer stubs the earlier result when a result's flag is set, identifying it by the file or tool command the result concerns. — The HLS states this as an assumption; the provider does not handle stubbing.
