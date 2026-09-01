<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - conversation_history.md
  - loop_guard.md
  - runner_logger.md
-->

# Interface LLS: agent_runner

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence, Optional
from dataclasses import dataclass
from tool_provider import ToolProvider, TerminationOutcome
from conversation_history import ConversationHistory, HistoryMessage
from loop_guard import LoopGuard
from runner_logger import RunnerLogger, LogEvent

IterationLimit: TypeAlias = int

@dataclass(frozen=True)
class AgentOutcome:
    termination: TerminationOutcome
    history: Sequence[HistoryMessage]

class AgentRunner(Protocol):
    def run(
        self,
        tool_provider: ToolProvider,
        history: ConversationHistory,
        logger: Optional[RunnerLogger] = None,
        loop_guard: Optional[LoopGuard] = None,
        iteration_limit: IterationLimit = 20,
    ) -> AgentOutcome: ...
```

- `IterationLimit` → corresponds to *iteration limit*: a bound on the maximum number of model interaction turns permitted in a run.
- `AgentOutcome` → corresponds to *agent outcome*: the final result of an agent run, carrying the *termination outcome* and the *conversation history*.
- `AgentRunner` → corresponds to *agent runner*: an orchestration service that drives an iterative agent run.

## Term definitions

- **iteration limit** → the `IterationLimit` alias
- **agent outcome** → the `AgentOutcome` alias
- **agent runner** → term definition: an orchestration service that drives an iterative agent run

## Component-Provided Operations

### `run`

```python
def run(
    self,
    tool_provider: ToolProvider,
    history: ConversationHistory,
    logger: Optional[RunnerLogger] = None,
    loop_guard: Optional[LoopGuard] = None,
    iteration_limit: IterationLimit = 20,
) -> AgentOutcome: ...
```

**Purpose:** (AgentRunner) Executes an iterative agent turn loop until a termination outcome is produced or the iteration limit is reached.

**Preconditions:**
- `tool_provider` is initialized with available tools.
- `history` contains initial run prompt messages.

**Postconditions:**
- Drives model-tool turns iteratively by sending model requests, correlating tool results with originating tool call identifiers, and appending messages and tool results to `history`.
- Emits execution progress events for model turns and tool invocations.
- Evaluates repetitions with `loop_guard` when provided, terminating on fatal repetition.
- Returns an `AgentOutcome` upon encountering a `TerminationOutcome` or reaching `iteration_limit`.

**Failure Handling:** Iteration limit exhaustion returns an `AgentOutcome` carrying a failure termination.

**HLS Justification:** "An *agent runner* drives turns by sending a *model request* to a language model and executing requested *tools*."

## Invariants

- A run terminates atomically upon emitting an `AgentOutcome`.
- Tool calls and model responses are appended chronologically to history.
