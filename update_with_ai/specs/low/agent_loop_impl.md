<!-- Dependencies (md files to read alongside this one):
  - agent_loop.md
  - agent_loop_config.md
  - conversation_history.md
  - loop_guard.md
-->

# Implementation LLS: agent_loop_impl

## Data Types
```python
from conversation_history import ConversationHistory
from loop_guard import LoopGuard
from agent_loop import AgentLoop
from agent_loop_config import AgentLoopConfig

class AgentLoopImpl(AgentLoop):
    def __init__(self, config: AgentLoopConfig, conversation_history: ConversationHistory | None = None, loop_guard: LoopGuard | None = None): ...
```

The run's configuration is the `AgentLoopConfig` from `agent_loop_config`,
supplied when the loop is constructed, along with optional `ConversationHistory` and `LoopGuard` instances.

## Behavioral Description

`AgentLoopImpl` fulfills the `AgentLoop` Protocol by orchestrating language model requests via the OpenAI API while delegating history management and repetition guardrails to dedicated subcomponents.

**`run_agent`:**
Runs the agent loop per the `agent_loop` contract:
- Resets and initializes `conversation_history` and `loop_guard` at the start of each run.
- Pre-injects `session_start_results` via `conversation_history.initialize`.
- In each iteration:
  - Requests tool definitions from `tool_executor.get_tool_definitions()`.
  - Obtains rendered messages from `conversation_history.get_rendered_messages(system_prompt)`.
  - Calls OpenAI API chat completions with model, temperature, timeout, and max tokens.
  - Measures request duration and extracts token usage (input, cached input, non-cached input, output, total), accumulating metrics across iterations.
  - If the response finish reason is `length`: checks for degenerate content via `loop_guard.check_degenerate_response`; if degenerate, signals loop failure; otherwise appends the truncated message, appends the continuation prompt, and resumes generation.
  - If the response finish reason is `stop`: if content is present, retrieves the termination reminder from `loop_guard.get_termination_reminder()`, appends it to history, and continues.
  - If the response finish reason is `tool_calls`: evaluates each tool call via `loop_guard.record_tool_call(tool_call)`. If a degenerate loop is detected, returns loop failure. If a reminder is returned, injects the reminder into history. Dispatches tool calls to `tool_executor(name, args)` and handles outcomes (`Continue`, `TerminateAgentWithSuccess`, `TerminateAgentWithFailure`, `ToolFailure`, or `list[ToolResult]`). Appends tool results to `conversation_history`.
  - Emits logger events (`api_response`, `tool_called`, `tool_result`, `run_terminated`, `error`) chronologically.

**Error Handling:**
Returns `(error, history)` on API errors, tool executor unhandled exceptions, iteration limits, or degenerate loops.

**HLS Justification:** Exports the agent loop and coordinates subcomponents.

## Invariants

- No state persists between calls
- Conversation formatting and in-place stubbing are delegated to conversation_history
- Repetition tracking and guardrails are delegated to loop_guard
- Logger events are emitted after state updates

## Non-Concerns

- **Default continuation prompt:** Pinned to `Your previous response was cut off because it exceeded the output limit. Continue from where you left off.`
