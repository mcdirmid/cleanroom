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

The implementation is constructed with the `agent_loop` interface's `AgentLoopConfig` (see Interface LLS Data Types). It bundles no imported capabilities. The `continuation_prompt` field (default `None`) supplies the continuation prompt; when `None`, the pinned default continuation prompt is used.

**HLS Justification:** Configured with connection parameters and an optional reminder generator (per the `agent_loop` interface contract).

## Behavioral Description

`AgentLoopImpl` fulfills the `AgentLoop` Protocol by wrapping the OpenAI API.

**Responsibilities:**

The implementation produces one of the outcomes specified by the `agent_loop` interface. On a normal run:
- It sends the conversation and tools to the OpenAI API, tracks cumulative usage, and appends assistant responses.
- It interprets the API response: if the response contains tool calls, it delegates to `tool_executor` and appends results; otherwise it produces a `FinalAnswer` or, if the `termination_reminder_generator` is configured, injects a reminder and continues.
- It detects loop repetition: when the same tool call (name and arguments) repeats 4 consecutive times, it injects a reminder urging progress (edit or terminate) once per run, and continues.

The implementation handles these outcomes:
- **`FinalAnswer`** — returned when the model produces an answer (no tool calls).
- **`(TerminateAgentWithSuccess, history)`** — returned when `tool_executor` produces `TerminateAgentWithSuccess` (the signal's value is a `TerminateSuccessResult`).
- **`(TerminateAgentWithFailure[T_tool], history)`** — returned when `tool_executor` produces `TerminateAgentWithFailure[T_tool]` (the signal's value describes the failure).
- **`(error, history)`** — returned when an API call fails, the API returns a malformed response, `tool_executor` raises an exception, or the maximum iterations are exceeded.

The implementation injects at most one reminder per run (when a reminder generator is configured) by appending it to the conversation as a message — no session reset, no history clearing — strips internal metadata fields before API calls, and invokes the logger after each history update.

When the API response's finish reason is `length` (the response stopped at the token limit), the implementation does not treat the response as a final answer: it appends the assistant message (its content; any tool calls are omitted), appends the continuation prompt (the configured `continuation_prompt`, or the pinned default when none is configured) as a user message, and continues the loop with a follow-up request. Tool calls present in a truncated response are never passed to `tool_executor`. A truncated response with neither content nor tool calls is not appended; only the continuation prompt follows.

A truncated response whose content is degenerate — non-empty and all characters identical — is not resumed: the implementation returns `(error, history)` and does not append the truncated message or the continuation prompt, and emits the `error` event (not `response_truncated`).

**Error Handling:**

Returns `(error, history)` on any failure. Logger callback exceptions are caught and ignored. A response whose finish reason is `content_filter` is an incomplete response and returns `(error, history)` with error text pinned to `Incomplete response: content_filter`. A degenerate truncated response returns `(error, history)` with error text pinned to `Degenerate truncated response: single character repeated`.

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
- **Default continuation prompt:** Pinned to `Your previous response was cut off because it exceeded the output limit. Continue from where you left off.` — used when `continuation_prompt` is `None`; tests may assert it.

