# Interface LLS: tool_provider

## Data Types

```python
from typing import Any, Protocol, Union, TypeVar, Generic, Literal
from dataclasses import dataclass
```

```python
T_tool = TypeVar("T_tool")
```

The opaque value type passed through from tool execution to the tool call outcome. Each `ToolProvider[T_tool]` implementation resolves `T_tool` to a concrete type (typically `str`). The provider does not inspect, transform, or interpret values of this type. Implementations must state the concrete type they resolve `T_tool` to.

```python
ToolName = str
```

```python
ToolArguments = dict[str, Any]
```

```python
ContentId = str
```

An opaque identifier for a tool result. Producers may assign meaning to the value (e.g., a file path); consumers of `ContentId` should treat it as opaque unless they know the specific producer's semantics.

```python
ToolDefinition = dict[str, Any]
```

A tool definition describes a tool's name, parameters, and purpose, in the tool-calling JSON Schema dialect accepted by the language model.

Tool-result content is intentionally heterogeneous: each tool defines its own content type (file text, structured JSON, diffs), so there is no single pass-through type variable to bind; the interface passes content through without inspection, and each tool pins its content type in its operation spec.

```python
ToolResultContent = Any
```

```python
@dataclass
class ToolResult:
    content: ToolResultContent
    content_id: ContentId | None
    stub_previous: bool
    note: str = ""
    type: Literal["tool_result"] = "tool_result"
```

`content_id` is `None` if the result is never stubbed. `stub_previous` `True` stubs all previous non-stubbed results with the same `content_id`. `note` carries producer-generated guidance for the model (e.g., how much content remains and how to continue reading); it is rendered into the model-visible message by the consuming agent loop, and does not replace `content`.

```python
class TerminateSuccessResult(Protocol):
    pass
```

Abstract result carried by a successful termination signal. Concrete results describe the session outcome: changes to broadcast to reverse dependencies, feedback to deliver to specific dependencies, or no change. Tool providers form the relevant result for their termination tool and place it in `TerminateAgentWithSuccess.value`.

```python
@dataclass
class Continue:
    type: Literal["continue"] = "continue"
```

```python
@dataclass
class TerminateAgentWithSuccess:
    value: TerminateSuccessResult
    type: Literal["terminate_success"] = "terminate_success"
```

```python
@dataclass
class TerminateAgentWithFailure(Generic[T_tool]):
    value: T_tool
    type: Literal["terminate_failure"] = "terminate_failure"
```

```python
@dataclass
class ToolFailure(Generic[T_tool]):
    value: T_tool
    type: Literal["tool_failure"] = "tool_failure"
```

`Continue` indicates execution should continue; `TerminateAgentWithSuccess` successful termination carrying a `TerminateSuccessResult`; `TerminateAgentWithFailure[T_tool]` failure termination; `ToolFailure[T_tool]` a failed tool call. Each variant carries a `type` discriminator.

```python
Signal = Union[
    Continue,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure[T_tool],
    ToolFailure[T_tool],
]
```

`TerminateAgentWithSuccess` and `TerminateAgentWithFailure[T_tool]` are termination signals. Termination is terminal: once a provider session produces a termination signal, that session produces no further tool results. `ToolFailure[T_tool]` is a **tool failure** — a failed tool call caused by a contract violation (e.g., invalid arguments, a policy violation, or a termination tool invoked incorrectly). A tool failure is not a termination and does not end the session: the failure value guides the agent and the loop continues. It is distinct from a run-level agent failure, which is the loop's concern, not the provider's. A correctly-invoked termination tool is not a `ToolFailure`: the termination tool produces a termination signal with the appropriate result.

```python
ToolCallOutcome = Union[ToolResult, Signal[T_tool]]
```

A tool call produces either a `ToolResult` or a `Signal[T_tool]`, never both.

```python
ToolExecutor = Callable[[ToolName, ToolArguments], ToolCallOutcome[T_tool]]
```

Executes a single tool call and returns a `ToolResult` or a `Signal[T_tool]`. The executor operates per-tool (one call at a time), not in batches.

```python
class ToolProvider(Protocol[T_tool]):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def execute_tool(self, name: ToolName, arguments: ToolArguments) -> ToolCallOutcome[T_tool]: ...
```

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]
```

**Purpose:** Returns the list of all available tool definitions.

**Preconditions:** None.

**Postconditions:**
- Returns a list of tool definitions
- Each definition conforms to the tool-calling JSON Schema dialect accepted by the language model
- The list may be empty
- The list represents all tools the provider can execute

**Failure Handling:** Always succeeds.

**HLS Justification:** "The client may: Request the list of available tool definitions"


### `execute_tool`

```python
def execute_tool(self, name: ToolName, arguments: ToolArguments) -> ToolCallOutcome[T_tool]
```

**Purpose:** Executes a single tool call and produces either a tool result or a termination signal.

**Preconditions:**
- The tool name must correspond to a definition returned by `get_tool_definitions()`
- The arguments must conform to the tool's parameter schema
- The provider must not have previously produced a termination signal (terminal)

**Postconditions:**
- If the tool call is valid and executes successfully:
  - Produces exactly one `ToolCallOutcome[T_tool]`
  - The outcome is either a `ToolResult` or a `Signal[T_tool]` (`Continue`, `TerminateAgentWithSuccess`, `TerminateAgentWithFailure[T_tool]`, or `ToolFailure[T_tool]`)
  - If the outcome is a `ToolResult`:
    - Contains the content produced by the tool
    - Contains a `content_id` or `None`
    - Contains a `stub_previous` flag
    - If `stub_previous` is `True`, all previous non-stubbed results with the same `content_id` become stubbed before this new result is produced
    - If `stub_previous` is `False`, previous results with the same `content_id` remain unchanged
    - Stubbing preserves the original position of messages in the conversation
  - If the outcome is a `Signal[T_tool]`:
    - `Continue` indicates execution should continue
    - `TerminateAgentWithSuccess` indicates successful termination carrying a `TerminateSuccessResult`; `TerminateAgentWithFailure[T_tool]` indicates failure termination with a value of type `T_tool`
    - `ToolFailure[T_tool]` indicates a failed tool call with a value of type `T_tool` (not a termination; the session continues)
    - The component does not inspect, transform, or interpret the termination value

**Failure Handling:**
- Invalid tool name (not returned by `get_tool_definitions`) → Return `ToolFailure[T_tool]` with an error message identifying the tool.
- Invalid arguments (not conforming to the tool's schema) → Return `ToolFailure[T_tool]` with an error message describing the validation failure.
- Partial success is not possible; handled errors leave state unchanged.

**Ordering:**
- Termination signals are atomic and final
- Tool failures are not termination signals; after a `ToolFailure[T_tool]`, the session continues
- Stubbing occurs before the new result is produced
- If `stub_previous` is `True`, all previous non-stubbed results with the same `content_id` are stubbed as part of producing this result

Once a termination signal is produced:
- No further tool results are produced
- Subsequent calls to `execute_tool` violate the terminal precondition (behavior unspecified)

**HLS Justification:** "The client may: Execute a tool call."


## Invariants

- The provider may maintain state across tool calls within a single session
- The provider does not persist state across sessions
- Termination signals are atomic—once signaled, the provider produces no further tool results
- The provider validates all inputs against the tool's schema before execution
- Stubbing preserves the original position of messages in the conversation
- The provider does not inspect, transform, or interpret termination values of type `T_tool`

## Non-Concerns

- **Provider state corruption:** Unhandled by this interface; providers may handle it explicitly by extending their own interface spec.

