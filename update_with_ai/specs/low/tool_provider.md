<!-- Dependencies (md files to read alongside this one):
-->

# Interface LLS: tool_provider

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence, Mapping, Any, Optional, Union
from dataclasses import dataclass

AgentIdentifier: TypeAlias = str
ToolName: TypeAlias = str
ToolPurpose: TypeAlias = str
ParameterSchema: TypeAlias = Mapping[str, Any]
ToolArguments: TypeAlias = Mapping[str, Any]
ToolResultContent: TypeAlias = str
ProducerGuidance: TypeAlias = str
FailureFeedback: TypeAlias = str
FailureError: TypeAlias = str
TerminationReason: TypeAlias = str

@dataclass(frozen=True)
class ToolMetadata:
    name: ToolName
    purpose: ToolPurpose
    parameters_schema: ParameterSchema

@dataclass(frozen=True)
class ToolResult:
    content: ToolResultContent = ""
    guidance: Optional[ProducerGuidance] = None

@dataclass(frozen=True)
class ToolFailure(ToolResult):
    feedback: FailureFeedback = ""
    error: FailureError = ""
    is_failure: bool = True

@dataclass(frozen=True)
class TerminationOutcome(ToolResult):
    reason: TerminationReason = ""
    is_terminal: bool = True

ToolOutcome: TypeAlias = Union[ToolResult, ToolFailure, TerminationOutcome]

class Tool(Protocol):
    def get_metadata(self) -> ToolMetadata: ...
    def execute(self, arguments: ToolArguments) -> ToolOutcome: ...

class ToolProvider(Protocol):
    def get_tools(self) -> Sequence[Tool]: ...
```

- `AgentIdentifier` → corresponds to *agent*: an autonomous entity that discovers and calls *tools* to accomplish a task.
- `ToolName` → corresponds to tool name.
- `ToolPurpose` → corresponds to tool purpose.
- `ParameterSchema` → corresponds to parameters schema of a tool.
- `ToolArguments` → corresponds to arguments supplied by an agent.
- `ToolResultContent` → corresponds to content produced by a tool.
- `ProducerGuidance` → corresponds to producer-generated guidance.
- `FailureFeedback` → corresponds to recovery feedback in a *tool failure*.
- `FailureError` → corresponds to error message string.
- `TerminationReason` → corresponds to termination reason string.
- `ToolMetadata` → corresponds to *tool metadata*: describes a *tool*'s name, purpose, and expected arguments.
- `ToolResult` → corresponds to *tool result*: the successful outcome of executing a *tool*, carrying produced content and optional guidance.
- `ToolFailure` → corresponds to *tool failure*: an execution outcome signaling that a *tool* could not execute or complete, carrying feedback to guide recovery.
- `TerminationOutcome` → corresponds to *termination outcome*: a *tool result* communicating that execution has completed.
- `Tool` → corresponds to *tool*: an executable capability described by *tool metadata* that performs actions when executed with arguments supplied by an *agent*.
- `ToolProvider` → corresponds to *tool provider*: a provider of available *tools* to an *agent*.

## Term definitions

- **agent** → term definition: an autonomous entity that discovers and calls *tools* to accomplish a task
- **tool provider** → term definition: a provider of available *tools* to an *agent*
- **tool** → term definition: an executable capability described by *tool metadata* that performs actions when executed with arguments supplied by an *agent*
- **tool metadata** → the `ToolMetadata` alias
- **tool result** → the `ToolResult` alias
- **tool failure** → the `ToolFailure` alias
- **termination outcome** → the `TerminationOutcome` alias

## Component-Provided Operations

### `get_tools`

```python
def get_tools(self) -> Sequence[Tool]: ...
```

**Purpose:** (ToolProvider) Retrieves the sequence of all available tools provided by this provider.

**Preconditions:** None.

**Postconditions:**
- Returns a sequence of `Tool` instances available for agent execution.

**Failure Handling:** Always succeeds; returns an empty sequence if no tools are available.

**HLS Justification:** "Available *tools* can be retrieved from a *tool provider* for an *agent*."

### `get_metadata`

```python
def get_metadata(self) -> ToolMetadata: ...
```

**Purpose:** (Tool) Retrieves the descriptor specifying the tool's name, purpose, and expected parameter schema.

**Preconditions:** None.

**Postconditions:**
- Returns the `ToolMetadata` describing the tool.

**Failure Handling:** Always succeeds.

**HLS Justification:** "*Tool metadata* can be retrieved from a *tool*, describing its name, purpose, and expected arguments to an *agent*."

### `execute`

```python
def execute(self, arguments: ToolArguments) -> ToolOutcome: ...
```

**Purpose:** (Tool) Executes the tool with arguments supplied by an agent matching its tool metadata.

**Preconditions:** None.

**Postconditions:**
- Returns a `ToolResult` (or `TerminationOutcome`) on successful execution.
- If execution encounters invalid arguments, policy violations, or unmet prerequisites, returns a `ToolFailure` without modifying state.

**Failure Handling:** Invalid arguments or execution errors produce a `ToolFailure` carrying actionable recovery feedback.

**HLS Justification:** "A *tool* can be executed with arguments supplied by an *agent* matching its *tool metadata*."

## Invariants

- A `TerminationOutcome` is terminal and atomic; once emitted, execution concludes and no further tool results are produced.
- A `ToolFailure` never modifies workspace or session state and allows the agent to self-correct and continue.
