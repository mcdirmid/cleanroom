<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
-->

# Interface LLS: agent_node_tool_executor

## Data Types
```python
from typing import Any, Dict, List, Protocol
from tool_provider import ToolCallOutcome, ToolDefinition, PresentedToolResult

class AgentNodeToolExecutor(Protocol):
    def get_tool_definitions(self) -> List[ToolDefinition]: ...
    def execute_tool(self, name: str, args: Dict[str, Any]) -> ToolCallOutcome: ...
    def get_session_start_reads(self) -> List[PresentedToolResult]: ...
```

## Term definitions

- **node tool execution** → term definition: dispatching agent tool calls to underlying sandbox operations and formatting presented outcomes
- **session-start delivery** → term definition: retrieving pre-injected session-start tool results from the sandbox to seed the initial conversation

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> List[ToolDefinition]
```

**Purpose:** Return tool definitions provided by the underlying sandbox.

**Preconditions:** None.

**Postconditions:**
- Returns list of ToolDefinition schemas.

**Failure Handling:** None.

**HLS Justification:** "Retrieve tool definitions."

### `execute_tool`

```python
def execute_tool(self, name: str, args: Dict[str, Any]) -> ToolCallOutcome
```

**Purpose:** Execute a tool call by dispatching to the sandbox.

**Preconditions:** None.

**Postconditions:**
- Returns ToolCallOutcome resulting from tool execution.

**Failure Handling:** Returns ToolFailure on unknown tool or argument mismatch.

**HLS Justification:** "Execute tool call."

### `get_session_start_reads`

```python
def get_session_start_reads(self) -> List[PresentedToolResult]
```

**Purpose:** Retrieve session-start tool results from the sandbox.

**Preconditions:** None.

**Postconditions:**
- Returns list of PresentedToolResult objects.

**Failure Handling:** None.

**HLS Justification:** "Retrieve session-start tool results."

## Invariants

- Tool dispatch matches tool name to sandbox method.
- Unknown tool names produce a tool failure.
