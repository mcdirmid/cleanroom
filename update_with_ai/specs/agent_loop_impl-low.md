<!-- Dependencies (md files to read alongside this one):
  - agent_loop-low.md
  - tool_provider-low.md
-->

# Implementation LLS: agent_loop_impl

## Data Types
```python
from agent_loop import (
    AgentLoop,
    AgentLoopConfig,
    AgentResult,
    HistoryEntry,
    ToolCall,
    LoggerCallback,
    LogEvent,
    Usage,
    CumulativeUsage,
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

class AgentLoopImpl(AgentLoop):
    def __init__(self, config: AgentLoopConfig): ...
```

Constructed with the `agent_loop` interface's `AgentLoopConfig` (see Interface LLS Data Types); it bundles no imported capabilities. The `continuation_prompt` field (default `None`) supplies the continuation prompt; when `None`, the pinned default continuation prompt is used.

## Behavioral Description

`AgentLoopImpl` fulfills the `AgentLoop` Protocol by wrapping the OpenAI API.

**Responsibilities:**

The implementation produces one of the outcomes specified by the `agent_loop` interface. On a normal run:
- It maintains the conversation (a list of `HistoryEntry`) and the stubbing state — the mapping from each file or tool command to its current live (non-stubbed) result — for the duration of the run.
- It sends the system prompt (when provided), the conversation, and the tools to the OpenAI API, tracks cumulative usage, and appends assistant responses.
- It interprets the API response: if the response contains tool calls, it delegates to `tool_executor` and routes the results; if the response stops with free text and no tool calls (there is no final answer), it injects the termination reminder (the configured generator's message, or the pinned default) and continues the loop.
- It detects loop repetition: when the same tool call (name and arguments) repeats 4 consecutive times, it injects a reminder urging progress (edit or terminate) once per run, and continues. When `replace_lines` targets the same file and line range 4 consecutive times (even with different content), it injects a range-specific reminder (text pinned in Non-Concerns) urging a fresh numbered read and offering to finish the run; at most one reminder is injected per run across both detectors. When either repetition count reaches 8 consecutive, the run returns `(error, history)` (a loop failure) instead of continuing — a degenerate loop ends the run rather than spinning to the iteration limit (error texts pinned in Non-Concerns).

**Tool-result stubbing:**

- A tool result is appended to the conversation: the model-visible tool message content is the result's `content` with the result's `note` appended.
- When the result's `supersedes` flag is set, the earlier non-stubbed result for the same file or tool command is located via the stubbing state; its content is replaced in place with the pinned stub text (see Non-Concerns), the message keeps its position, the `message_stubbed` logger event is emitted (data: the stubbed message and the replacement message), and the new result becomes the live result for that file or tool command.
- A result with the `supersedes` flag unset is appended without stubbing; at most one earlier result is superseded per result.
- A stub is static once set: a stubbed message's content never changes for the remainder of the run. Stubbed messages keep their positions, so the conversation up to the most recent live result for a file or tool command is byte-identical across requests, preserving the model service's prefix caching.
- The `supersedes` flag is bookkeeping; it is never sent to the language model service in raw form.

The implementation handles these outcomes (there is no `FinalAnswer`):
- **`(TerminateAgentWithSuccess, history)`** — returned when `tool_executor` produces `TerminateAgentWithSuccess` (the signal's value is a `TerminateSuccessResult`).
- **`(TerminateAgentWithFailure[T_tool], history)`** — returned when `tool_executor` produces `TerminateAgentWithFailure[T_tool]` (the signal's value describes the failure).
- **`(error, history)`** — returned when an API call fails, the API returns a malformed response, `tool_executor` raises an exception, or the maximum iterations are exceeded.

When the model stops with free text and no tool calls, the implementation injects the termination reminder by appending it to the conversation as a message — no session reset, no history clearing — and continues the loop; the run completes only via a termination signal or the iteration limit. The reminder uses the configured `termination_reminder_generator`'s message when present, or the pinned default; the loop-repetition reminders (identical calls, same-range edits) are injected at most once per run. The logger is invoked after each history update.

When the API response's finish reason is `length` (the response stopped at the token limit), the implementation does not treat the response as complete: it appends the assistant message (its content; any tool calls are omitted), appends the continuation prompt (the configured `continuation_prompt`, or the pinned default when none is configured) as a user message, and continues the loop with a follow-up request. Tool calls present in a truncated response are never passed to `tool_executor`. A truncated response with neither content nor tool calls is not appended; only the continuation prompt follows.

A truncated response whose content is degenerate — non-empty and all characters identical — is not resumed: the implementation returns `(error, history)` and does not append the truncated message or the continuation prompt, and emits the `error` event (not `response_truncated`).

**Error Handling:**

Returns `(error, history)` on any failure. Logger callback exceptions are caught and ignored. A response whose finish reason is `content_filter` is an incomplete response and returns `(error, history)` with error text pinned to `Incomplete response: content_filter`. A degenerate truncated response returns `(error, history)` with error text pinned to `Degenerate truncated response: single character repeated`. A degenerate loop — the same tool call (name and arguments) repeated 8 consecutive times, or `replace_lines` targeting the same file and line range 8 consecutive times — returns `(error, history)` with error text pinned to `Degenerate loop: same tool call repeated 8 consecutive times` (identical calls) or `Degenerate loop: replace_lines targeted the same file and line range 8 consecutive times` (same-range edits).

**HLS Justification:** Exports the agent loop and uses the OpenAI API.

## Invariants

- No state persists between calls
- The system prompt is never modified during the run
- A result with the `supersedes` flag set stubs the earlier non-stubbed result for the same file or tool command (at most one); stubbed messages keep their positions
- A stub is static once set: a stubbed message's content never changes for the remainder of the run
- A tool failure never supersedes an earlier result
- A degenerate loop (8 consecutive identical tool calls, or 8 consecutive `replace_lines` calls on the same file and line range) fails the run
- At most one reminder injected per run

## Non-Concerns

- **Message history representation:** Any representation that preserves chronological order and message positions is acceptable.
- **Retry behavior:** Whether failed API calls are retried is unspecified; any failure signals the run's failure.
- **Default continuation prompt:** Pinned to `Your previous response was cut off because it exceeded the output limit. Continue from where you left off.` — used when `continuation_prompt` is `None`; tests may assert it.
- **Default termination reminder:** Pinned to `You must signal termination by calling succeed(), fail(), or blame() to end the run.` — used when `termination_reminder_generator` is `None`; tests may assert it.
- **Stub text:** Pinned to `Content removed because newer version is available.` — the content replacing a superseded result in place; tests may assert it.
- **Same-range reminder text:** Pinned to `You have edited lines {start}-{end} of '{file}' {count} times in a row without progress. Re-read the file (read_file('{file}', include_line_numbers=True)) and reassess — the line numbers are stale after a write — or finish the run with succeed(), fail(), or blame().` — tests may assert its substance (the range, the file, `include_line_numbers=True`, and the finish-the-run option).
- **Degenerate-loop error texts:** Pinned to `Degenerate loop: same tool call repeated 8 consecutive times` (the identical-call detector) and `Degenerate loop: replace_lines targeted the same file and line range 8 consecutive times` (the same-range detector) — tests may assert them.
