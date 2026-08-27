<!-- Dependencies (md files to read alongside this one):
-->

# Interface LLS: tool_provider

## Data Types
```python
from typing import Any, Protocol, Union, TypeVar, Generic, Literal, TypeAlias
from dataclasses import dataclass

T_tool = TypeVar("T_tool")

ToolName: TypeAlias = str

ToolArguments: TypeAlias = dict[str, Any]

ToolDefinition: TypeAlias = dict[str, Any]

ToolResultContent: TypeAlias = Any

@dataclass
class ToolResult:
    content: ToolResultContent
    supersedes: bool
    note: str = ""
    type: Literal["tool_result"] = "tool_result"

@dataclass
class PresentedToolResult:
    name: ToolName
    arguments: ToolArguments
    result: ToolResult
    type: Literal["presented_tool_result"] = "presented_tool_result"

class TerminateSuccessResult(Protocol):
    pass

@dataclass
class Continue:
    type: Literal["continue"] = "continue"

@dataclass
class TerminateAgentWithSuccess:
    value: TerminateSuccessResult
    type: Literal["terminate_success"] = "terminate_success"

@dataclass
class TerminateAgentWithFailure(Generic[T_tool]):
    value: T_tool
    type: Literal["terminate_failure"] = "terminate_failure"

@dataclass
class ToolFailure(Generic[T_tool]):
    value: T_tool
    type: Literal["tool_failure"] = "tool_failure"

Signal: TypeAlias = Union[
    Continue,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure[T_tool],
    ToolFailure[T_tool],
]

ToolCallOutcome: TypeAlias = Union[list[ToolResult | PresentedToolResult], Signal[T_tool]]

class ToolExecutor(Protocol[T_tool]):
    def __call__(self, name: ToolName, arguments: ToolArguments) -> ToolCallOutcome[T_tool]: ...
    def get_tool_definitions(self) -> list[ToolDefinition]: ...

class ToolProvider(Protocol[T_tool]):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def execute_tool(self, name: ToolName, arguments: ToolArguments) -> ToolCallOutcome[T_tool]: ...
```

The opaque value type passed through from tool execution to the tool call outcome. Each `ToolProvider[T_tool]` implementation resolves `T_tool` to a concrete type. The provider does not inspect, transform, or interpret values of this type. Implementations must state the concrete type they resolve `T_tool` to.

A tool definition describes a tool's name, parameters, and purpose, in the tool-calling JSON Schema dialect accepted by the language model.

Tool-result content is intentionally heterogeneous: each tool defines its own content type (file text, structured JSON, diffs), so there is no single pass-through type variable to bind; the interface passes content through without inspection, and each tool pins its content type in its operation spec.

`supersedes` is `True` when the result supersedes the earlier non-stubbed result for the same file or tool command — the producing component's declaration; the consuming agent loop stubs that result (at most one) before rendering the new one. `supersedes` is `False` for results that never supersede an earlier result. `content` is rendered into the agent conversation. `note` carries producer-generated guidance for the model (e.g., the status of an operation); it is rendered into the model-visible message by the consuming agent loop, and does not replace `content`.

Abstract result carried by a successful termination signal. Concrete results describe the session outcome: changes to broadcast to reverse dependencies, feedback to deliver to specific dependencies, or no change. Tool providers form the relevant result for their termination tool and place it in `TerminateAgentWithSuccess.value`.

`Continue` indicates execution should continue; `TerminateAgentWithSuccess` successful termination carrying a `TerminateSuccessResult`; `TerminateAgentWithFailure[T_tool]` failure termination; `ToolFailure[T_tool]` a failed tool call. Each variant carries a `type` discriminator. A tool failure never carries the stub text and never supersedes an earlier result.

`TerminateAgentWithSuccess` and `TerminateAgentWithFailure[T_tool]` are termination signals. Termination is terminal: once a provider session produces a termination signal, that session produces no further tool results. `ToolFailure[T_tool]` is a **tool failure** — a signal that the tool call could not do meaningful work because of an immediate problem: wrong arguments, wrong format, an unknown tool, a policy violation, or a termination tool invoked incorrectly; the operation is not executed and the session continues. A tool failure is not a termination and does not end the session: the failure value guides the agent and the loop continues. A result rejected with feedback is a `ToolResult` carrying the feedback, never a `ToolFailure`. A correctly-invoked termination tool is not a `ToolFailure`: the termination tool produces a termination signal with the appropriate result. It is distinct from a run-level agent failure, which is the loop's concern, not the provider's.

A tool call produces either a sequence of one or more results (`ToolResult` or `PresentedToolResult` values) or a `Signal[T_tool]`, never both. A `PresentedToolResult` pairs a result with the tool call it is presented with when the model did not make that call: the producing component provides the call's name and arguments, and the consuming agent loop assigns the call's id. Results are rendered in the order produced.

Executes a single tool call and returns a sequence of one or more tool results or a `Signal[T_tool]`. The executor operates per-tool (one call at a time), not in batches.

## Term definitions

- **tool definition** → the `ToolDefinition` alias (definition in Data Types)
- **tool result** → the `ToolResult` type (definition in Data Types)
- **presented tool result** → the `PresentedToolResult` type (definition in Data Types)
- **supersession flag** → term definition: whether the result supersedes the earlier non-stubbed result for the same file or tool command; which results carry the flag is declared by the producing component, and a result without the flag never supersedes an earlier result (realized as the `ToolResult.supersedes` field)
- **stub** → term definition: replacing a superseded tool result's content with a placeholder; the stub text is applied by the consuming agent loop, and a `ToolResult` never carries it
- **signal** → the `Signal` alias (definition in Data Types)
- **termination result** → the `TerminateSuccessResult` type (definition in Data Types)
- **tool failure** → the `ToolFailure` type (definition in Data Types)
- **session** → term definition: the sequence of tool calls and outcomes of a single run, continuing until a termination signal is produced

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

**Purpose:** Executes a single tool call and produces either a sequence of tool results or a signal.

**Preconditions:**
- The tool name must correspond to a definition returned by `get_tool_definitions()`
- The arguments must conform to the tool's parameter schema
- The provider must not have previously produced a termination signal (terminal)

**Postconditions:**
- If the tool call is valid and executes successfully:
  - Produces exactly one `ToolCallOutcome[T_tool]`
  - The outcome is either a sequence of one or more results (`ToolResult` or `PresentedToolResult` values) or a `Signal[T_tool]` (`Continue`, `TerminateAgentWithSuccess`, `TerminateAgentWithFailure[T_tool]`, or `ToolFailure[T_tool]`)
  - If the outcome is a sequence of results, each result:
    - Contains the content produced by the tool
    - Contains a `supersedes` flag: `True` when the result supersedes the earlier non-stubbed result for the same file or tool command (the producing component's declaration), `False` otherwise
    - Contains a note (possibly empty)
    - When `supersedes` is `True`: the earlier non-stubbed result for the same file or tool command is stubbed by the consuming agent loop before the new result is rendered; at most one earlier result is superseded per result
    - When `supersedes` is `False`: no earlier result is superseded
    - The result never carries the stub text; the stub text appears only when the consuming agent loop replaces an earlier result
  - The sequence is rendered in the order produced; a `PresentedToolResult` is rendered with the tool call it carries (its name and arguments) immediately before its result
  - If the outcome is a `Signal[T_tool]`:
    - `Continue` indicates execution should continue
    - `TerminateAgentWithSuccess` indicates successful termination carrying a `TerminateSuccessResult`; `TerminateAgentWithFailure[T_tool]` indicates failure termination with a value of type `T_tool`
    - `ToolFailure[T_tool]` indicates a failed tool call with a value of type `T_tool` (not a termination; the session continues); a tool failure never supersedes an earlier result
    - The component does not inspect, transform, or interpret the termination value

**Failure Handling:**
- Invalid tool name (not returned by `get_tool_definitions`) → Return `ToolFailure[T_tool]` with an error message identifying the tool.
- Invalid arguments (not conforming to the tool's schema) → Return `ToolFailure[T_tool]` with an error message describing the validation failure.
- Partial success is not possible; handled errors leave state unchanged.

**Ordering:**
- Termination signals are atomic and final
- Tool failures are not termination signals; after a `ToolFailure[T_tool]`, the session continues
- Stubbing the superseded result (when `supersedes` is `True`) occurs before the new result is rendered; at most one earlier result is superseded per result

Once a termination signal is produced:
- No further tool results are produced
- Subsequent calls to `execute_tool` violate the terminal precondition (behavior unspecified)

**HLS Justification:** "The client may: Execute a tool call."


## Invariants

- The provider may maintain state across tool calls within a single session
- The provider does not persist state across sessions
- Termination signals are atomic—once signaled, the provider produces no further tool results
- The provider validates all inputs against the tool's schema before execution
- A result with `supersedes` set supersedes the earlier non-stubbed result for the same file or tool command; a result with `supersedes` unset supersedes nothing
- A result supersedes at most one earlier result
- A `ToolResult` never carries the stub text: the stub text appears only when the consuming agent loop replaces an earlier result in the conversation
- The provider does not inspect, transform, or interpret termination values of type `T_tool`

## Non-Concerns

- **Provider state corruption:** Unhandled by this interface; providers may handle it explicitly by extending their own interface spec.
- **Tool result structure:** the semantic content, supersession flag, and note are observable; the presented form additionally carries the tool's name and arguments for attribution (per presented tool result).
- **Consumer routing:** the consumer routes termination signals, interprets the carried termination result, and stubs superseded results — an assumption on the consumer, recorded per the HLS.
- **Executor protocol:** the `ToolExecutor` protocol (one tool call at a time; call ids assigned by the consuming agent loop) serves the closure's delegation of tool execution to a provided executor; the interface pins it so consumers can inject execution.
