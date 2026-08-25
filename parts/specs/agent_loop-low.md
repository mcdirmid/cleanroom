<!-- Dependencies (md files to read alongside this one):
  - tool_provider-low.md
-->

# Interface LLS: agent_loop

## Data Types
```python
from typing import Any, Callable, Literal, Protocol, TypeAlias

from tool_provider import ExecutionSignal, SupersessionFlag, ToolDefinition, ToolFailure, ToolProvider, ToolResult, TerminationResult
ConversationMessage: TypeAlias = dict
SystemPrompt: TypeAlias = str
UserPrompt: TypeAlias = str
TerminationPayload: TypeAlias = Any
LoggerCallback: TypeAlias = Callable[[EventName, dict[str, Any]], None]
EventName: TypeAlias = Literal[
    "message_added", "message_stubbed", "tool_called", "tool_result",
    "api_response", "response_truncated", "reminder_injected",
    "run_terminated", "error"
]

@dataclass
class APIUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass
class RunResult:
    success: bool
    signal: ExecutionSignal | None
    termination_value: TerminationPayload | None
    conversation: list[ConversationMessage]
    error: str | None
    usage: APIUsage | None
    cumulative_usage: APIUsage | None
    final_context_size: int | None

class AgentLoop(Protocol):
    def run(self, system_prompt: SystemPrompt, user_prompt: UserPrompt,
            tool_provider: ToolProvider,
            session_start_tool_results: list[ToolResult] | None = None,
            logger: LoggerCallback | None = None) -> RunResult: ...
```

**ConversationMessage:** An entry in the conversation history, produced by the model (role="assistant") or by tool execution (role="tool").

**SystemPrompt:** The static opening section of the conversation context, supplied per run; it is never modified during the run.

**UserPrompt:** The user's initial prompt for the run.

**TerminationPayload:** The opaque value carried by a successful termination signal. It enters via tool execution and exits via the run result unchanged; the component does not inspect, transform, or interpret it.

**LoggerCallback:** An optional callback invoked chronologically for events during a run.

**APIUsage:** Token usage for a single API request (prompt tokens, completion tokens, total tokens).

**RunResult:** The result of an agent run: success/failure flag, execution signal (or None on failure), termination value (if any), full conversation history, error message (if failed), per-request usage, cumulative usage, and final context size.

## Term definitions

- **run** → term definition: a single agent execution session
- **termination value** → the `TerminationPayload` alias
- **conversation** → term definition: the chronological history of conversation messages maintained for a run and provided with the run result
- **conversation message** → the `ConversationMessage` alias
- **system prompt** → the `SystemPrompt` alias
- **truncated response** → term definition: a model response that stops because the generation limit was reached, before completing naturally; it is not a complete answer
- **continuation prompt** → term definition: the message appended to the conversation so that generation resumes from where a truncated response stopped
- **degenerate response** → term definition: a truncated response whose content is a single character repeated; it carries no meaningful content and is not resumed
- **tool definition** → the `ToolDefinition` alias
- **tool result** → the `ToolResult` alias
- **supersession flag** → the `SupersessionFlag` alias
- **stub** → term definition: a placeholder that replaces a superseded tool result's content when the supersession flag is set; the consumer handles stubbing, not the provider
- **signal** → the `ExecutionSignal` alias
- **termination result** → the `TerminationResult` alias
- **tool failure** → the `ToolFailure` alias

## Component-Provided Operations

### `run`

```python
def run(self, system_prompt: SystemPrompt, user_prompt: UserPrompt,
        tool_provider: ToolProvider,
        session_start_tool_results: list[ToolResult] | None = None,
        logger: LoggerCallback | None = None) -> RunResult: ...
```

**Purpose:** Request an agent run. Processes a user prompt through an iterative loop of LLM chat completion (with tool calling) and tool execution, guarding against wasted cycles and runaway repetition, until a termination signal is produced, a failure occurs, or the iteration limit is reached.

**Preconditions:** The tool provider is initialized and can produce tool definitions and execute tool calls in the tool_provider format. The tool execution logic produces results that supersede at most one earlier result. The language model supports chat completion with tool calling.

**Postconditions:** Returns a `RunResult` with one of the following outcomes:
- A termination signal with its carried `termination_value` (success), or a failure signal (`terminate_failure`), each with the full conversation history. There is no free-text final answer.
- If the run fails (language model service failure, malformed response, tool execution exception, degenerate response, or iteration limit exceeded), returns a failure result with `success=False`, leaving state unchanged.
- A loop reminder is injected at most once per run when the model repeats itself without progress. If repetition continues beyond the repetition limit, a failure result is returned.
- A truncated response is not treated as a complete answer. When a truncated response is not a degenerate response, generation resumes with a follow-up request; tool calls present in a truncated response are not executed.
- A termination reminder is injected when the model stops without signaling termination and the loop continues; the run completes only via a termination signal or the iteration limit.
- The advance tool is exempt from repetition tracking.
- The termination reminder is not triggered by tool failures.
- A logger callback, if provided, is invoked chronologically for the following events; per-request and cumulative token usage are included in applicable events; logger callback exceptions are caught and ignored:
  - **message added:** message appended to conversation — data: message
  - **message stubbed:** tool result stubbed (superseded) — data: stubbed message, replacement message
  - **tool called:** model requests tools — data: tool calls
  - **tool result:** tool results received — data: results (in tool_provider format)
  - **API response:** API response received — data: usage (prompt, completion, total tokens)
  - **response truncated:** model response stops at generation limit — data: message, usage
  - **reminder injected:** reminder injected into conversation — data: message
  - **run terminated:** termination signaled — data: termination value, usage, cumulative usage, final context size
  - **error:** failure occurs — data: error, usage (if any), cumulative usage (if any), last context size (if any)

**Failure Handling:**
- Language model service failure: returns `RunResult(success=False, error="...", ...)`.
- Malformed response: returns `RunResult(success=False, error="...", ...)`.
- Tool execution exception: returns `RunResult(success=False, error="...", ...)`.
- Degenerate response (single repeated character): returns `RunResult(success=False, error="...", ...)`.
- Iteration limit exceeded: returns `RunResult(success=False, error="...", ...)`.
- Repetition limit exceeded: returns `RunResult(success=False, error="...", ...)`.
- All failures leave state unchanged and include the conversation history accumulated so far.

**HLS Justification:** Contract → Operations → "Request an agent run"; Contract → Guarantees → all guarantee statements.

## Invariants

- Final termination is atomic: once a termination signal occurs, no further API calls or tool executions occur.
- Each run is independent; no state persists across runs.

## Non-Concerns
- **Timer implementation:** The exact timeout mechanism is unspecified. — Bounded by the HLS non-concern; the component delegates timing to the language model service.
- **Model API version:** The specific API version is unspecified. — Bounded by the HLS non-concern; the component uses whatever API version the language model service supports.
- **Stub text:** The exact text of a stub placeholder is unspecified. — Bounded by the HLS non-concern; the stub placeholder is an implementation detail that does not affect observable behavior.
