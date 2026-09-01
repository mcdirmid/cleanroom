<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - dag_node_cleaner.md
  - sandbox.md
  - conversation_history.md
  - agent_runner.md
  - build_graph_storage.md
  - runner_logger.md
-->

# Interface LLS: agent_node_cleaner

## Data Types
```python
from typing import Protocol, Sequence
from dag_storage import NodeId, PendingMessage
from dag_node_cleaner import NodeCleaner, NodeCleaningOutcome

class AgentNodeCleaner(NodeCleaner, Protocol):
    def clean_node(self, node: NodeId, pending_messages: Sequence[PendingMessage]) -> NodeCleaningOutcome: ...
```

- `AgentNodeCleaner` → corresponds to *agent node cleaner*: a *node cleaner* that drives an agent run within a *sandbox* to clean a *node*.

## Term definitions

- **agent node cleaner** → term definition: a *node cleaner* that cleans a *node* by executing an *agent runner* within a *sandbox*

## Component-Provided Operations

### `clean_node`

```python
def clean_node(self, node: NodeId, pending_messages: Sequence[PendingMessage]) -> NodeCleaningOutcome: ...
```

**Purpose:** (AgentNodeCleaner) Cleans an individual node by initializing a sandbox, executing an agent run, and deriving outcome messages.

**Preconditions:**
- `node` is a valid node in the storage graph.

**Postconditions:**
- Drives an agent run within the target node's sandbox.
- If the agent run terminates with success and workspace file modifications occurred, produces `ChangeMessage` instances for downstream reverse dependencies.
- If the agent run terminates via blame tool, produces a `FeedbackMessage` for the targeted dependency node.
- If the agent run terminates with failure, raises an execution exception and leaves the node dirty.

**Failure Handling:** Unsuccessful agent runs fail the cleaning step and leave the node dirty.

**HLS Justification:** "An *agent node cleaner* cleans a dirty *node* by driving an *agent runner* within a *sandbox*."

## Invariants

- Emits change messages only when workspace file modifications actually occurred.
- Unsuccessful agent terminations leave the node in a dirty state.
