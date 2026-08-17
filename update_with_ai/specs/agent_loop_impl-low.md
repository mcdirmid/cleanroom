<!-- Dependencies (md files to read alongside this one):
  - agent_loop-low.md
  - tool_provider-low.md
-->

# Implementation LLS: agent_loop_impl

## Data Types

```python
from agent_loop import (
    AgentLoop,
    AgentResult,
    HistoryEntry,
    ToolCall,
    LoggerCallback,
    LogEvent,
    Usage,
    CumulativeUsage,
    FinalAnswer,
)
from tool_provider import (
    ToolDefinition,
    ToolResult,
    ToolExecutor,
    Signal,
    Continue,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
    TerminateSuccessResult,
    ToolFailure,
    T_tool,
)
```

```python
class AgentLoopImpl(AgentLoop): ...
```

## Config

The implementation is constructed with the `agent_loop` interface's `AgentLoopConfig` (see Interface LLS Data Types). It bundles no imported capabilities.

**HLS Justification:** Configured with connection parameters and an optional reminder generator (per the `agent_loop` interface contract).

## Behavioral Description

`AgentLoopImpl` fulfills the `AgentLoop` Protocol by wrapping an OpenAI API client.

**Responsibilities:**

The implementation produces one of the outcomes specified by the `agent_loop` interface. On a normal run:
- It sends the conversation and tools to the OpenAI API, tracks cumulative usage, and appends assistant responses.
- It interprets the API response: if the response contains tool calls, it delegates to `tool_executor` and appends results; otherwise it produces a `FinalAnswer` or, if the `termination_reminder_generator` is configured, injects a reminder and continues.

The implementation handles these outcomes:
- **`FinalAnswer`** — returned when the model produces an answer (no tool calls).
- **`(TerminateAgentWithSuccess, history)`** — returned when `tool_executor` produces `TerminateAgentWithSuccess` (the signal's value is a `TerminateSuccessResult`).
- **`(TerminateAgentWithFailure[T_tool], history)`** — returned when `tool_executor` produces `TerminateAgentWithFailure[T_tool]` (the signal's value describes the failure).
- **`(error, history)`** — returned when an API call fails, the API returns a malformed response, `tool_executor` raises an exception, or the maximum iterations are exceeded.

The implementation injects at most one reminder per run (when a reminder generator is configured) by appending it to the conversation as a message — no session reset, no history clearing — strips internal metadata fields before API calls, and invokes the logger after each history update.

**Error Handling:**

Returns `(error, history)` on any failure. Logger callback exceptions are caught and ignored.

**HLS Justification:** Exports the agent loop and uses the OpenAI API.

## Invariants

- No state persists between calls
- At most one tool result per unique `content_id` with `stub_previous=True` in the conversation (others are stubbed)
- At most one reminder injected per run
- Stubbed messages retain their position in the conversation
- `tool_provider` stubbing semantics are preserved exactly


## Non-Concerns

- **Message history representation:** Any representation that preserves chronological order and message positions is acceptable.
- **Retry behavior:** Whether failed API calls are retried is unspecified; any failure signals the run's failure.

