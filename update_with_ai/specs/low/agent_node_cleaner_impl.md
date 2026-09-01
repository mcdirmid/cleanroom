<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - dag_node_cleaner.md
  - sandbox.md
  - conversation_history.md
  - agent_runner.md
  - build_graph_storage.md
  - runner_logger.md
  - agent_node_cleaner.md
-->

# Implementation LLS: agent_node_cleaner_impl

## Data Types
```python
from typing import Optional
from sandbox import SandboxFactory
from conversation_history import ConversationHistoryFactory
from agent_runner import AgentRunner
from runner_logger import RunnerLogger
from build_graph_storage import BuildGraphStorage
from agent_node_cleaner import AgentNodeCleaner

class AgentNodeCleanerImpl(AgentNodeCleaner):
    def __init__(
        self,
        runner: AgentRunner,
        sandbox_factory: SandboxFactory,
        conversation_history_factory: ConversationHistoryFactory,
        storage: BuildGraphStorage,
        logger: Optional[RunnerLogger] = None,
    ) -> None: ...
```

## Behavioral Description

- `AgentNodeCleanerImpl` retrieves the `NodeDefinition`, `TaskPrompt`, and `SandboxConfig` for a dirty `node` from `storage`.
- Creates a `Sandbox` via `SandboxFactory` configured from the retrieved `SandboxConfig` and materializes startup templates.
- Seeds a fresh `ConversationHistory` from `ConversationHistoryFactory` with the `TaskPrompt`, the `StartupInteraction` from the `Sandbox` (pairing session-start reads with synthetic `read_file` tool calls and initial step delivery with a synthetic `advance` tool call), and incoming `PendingMessage` records.
- Executes `AgentRunner` within the configured node sandbox with `RunnerLogger`.
- When an `AgentOutcome` signals a change result, formats change summaries into `ChangeMessage` instances if workspace file modifications occurred.
- When an `AgentOutcome` signals blame, formats blame feedback into `FeedbackMessage` instances addressed to blamed dependencies.
- When an `AgentOutcome` signals run failure or verification failure, raises an execution failure and leaves the `node` dirty.
- Produces no messages when a task without modifications succeeds with no pending feedback.

## Invariants

- Cleaning failure leaves the target node in a dirty state.
- Emits change messages only when workspace file modifications actually occurred and verification passed.
- Conversation history pairs session-start reads with synthetic `read_file` tool calls and initial step delivery with a synthetic `advance` tool call.
