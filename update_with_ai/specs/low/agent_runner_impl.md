<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - conversation_history.md
  - loop_guard.md
  - runner_logger.md
  - agent_runner.md
  - openai_ext.md
-->

# Implementation LLS: agent_runner_impl

## Data Types
```python
from openai_ext import OpenAiExt, ModelName
from agent_runner import AgentRunner

class AgentRunnerImpl(AgentRunner):
    def __init__(self, openai_ext: OpenAiExt, model: ModelName) -> None: ...
```

## Behavioral Description

- `AgentRunnerImpl` drives prompt turns by formatting requests from `history`, transmitting `CompletionRequest`s to `openai_ext`, and dispatching returned tool calls to `tool_provider`.
- Records assistant responses and tool results with correlated tool call identifiers back into `history` and logs execution progress events to `logger` when provided.
- When tool execution produces a `ToolFailure`, the agent runner appends the failure feedback to the `ConversationHistory` and continues the run.
- When a model response is truncated at the generation limit, the agent runner resumes generation with a continuation turn.
- Injects `LoopReminder` or terminates with `LoopFailure` when `loop_guard` triggers.
- If iteration count exceeds `iteration_limit`, concludes with a failure `AgentOutcome`.

## Invariants

- Terminates immediately upon producing an `AgentOutcome`.
- Tool failures append feedback and allow execution to continue.
- Truncated model responses trigger automatic continuation turns.
