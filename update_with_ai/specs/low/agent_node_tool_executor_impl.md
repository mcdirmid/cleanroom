<!-- Dependencies (md files to read alongside this one):
  - agent_node_tool_executor.md
  - sandbox.md
-->

# Implementation LLS: agent_node_tool_executor_impl

## Data Types
```python
from agent_node_tool_executor import AgentNodeToolExecutor
from sandbox import Sandbox

class AgentNodeToolExecutorImpl(AgentNodeToolExecutor):
    def __init__(self, sandbox: Sandbox) -> None: ...
```

## Behavioral Description

Implements `AgentNodeToolExecutor` adapting a `Sandbox` instance.
Dispatches tool invocations by name to corresponding sandbox operations.
Formats tool call outcomes into presented tool results.
Exposes session-start reads from the sandbox for agent loop initialization.

## Invariants

- Tool calls for unprovided sandbox operations produce tool failures.
- Session-start reads are collected from the sandbox without mutating session state.
