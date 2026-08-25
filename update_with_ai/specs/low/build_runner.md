<!-- Dependencies (md files to read alongside this one):
  - dag_cleaner.md
  - dag_storage.md
  - dag_clean_logic.md
  - agent_loop.md
  - build_node_loader.md
  - build_agent_config.md
  - sandbox.md
-->

# Interface LLS: build_runner

## Data Types
```python
from typing import Protocol, List, Optional
from dag_storage import NodeId
from dag_cleaner import CleaningResult
from dag_clean_logic import CleanResult, ChangeResult, FeedbackResult, NoChangeResult, FailureResult

class BuildRunner(Protocol):
    def run_dag(self, root_node: NodeId, workspace_root: str, config_target: Optional[str] = None) -> CleaningResult: ...
    def inject_feedback(self, node_id: NodeId, workspace_root: str, messages: List[str]) -> CleaningResult: ...
    def add_change(self, node_id: NodeId, workspace_root: str, change: str = "check") -> CleaningResult: ...
    def broadcast_change(self, node_id: NodeId, workspace_root: str, change: str) -> CleaningResult: ...
```

## Term definitions

- **result** → the `CleaningResult` alias (definition in Data Types)
- **node** → the `NodeId` alias from dag_storage
- **pending message** → the `PendingMessages` alias from dag_storage
- **subgraph** → term definition from dag_storage
- **dirty** → term definition from dag_clean_logic
- **cleaning** → term definition from dag_clean_logic
- **change message** → term definition from dag_clean_logic
- **feedback message** → term definition from dag_clean_logic
- **run** → term definition from agent_loop
- **manifest** → term definition from build_node_loader
- **agent configuration** → the `AgentConfig` type from build_agent_config
- **config target** → the `ConfigTarget` alias from build_agent_config
- **step mode** → term definition from sandbox
- **blame** → term definition from sandbox

## Component-Provided Operations

### `run_dag`

```python
def run_dag(self, root_node: NodeId, workspace_root: str, config_target: Optional[str] = None) -> CleaningResult
```

**Purpose:** Run a topological cleaning pass starting from `root_node`, producing output (changes or feedback) for all dirty nodes in the subgraph rooted at `root_node`.

**Preconditions:**
- `root_node` is a valid node label
- `workspace_root` points to a valid workspace with manifest files
- `config_target`, when provided, is a valid `agent_config` target whose generated module is available (in runfiles or bazel-bin); when omitted, the agent configuration is selected by the `AGENT_CONFIG_TARGET` environment variable and then the `//agent_configs:default` convention (see `build_agent_config` Interface LLS)
- The environment provides an API key for the selected agent configuration (its pinned variable or AGENT_API_KEY)

**Postconditions:**
- Returns `(True, CleanResult)` on success (where `CleanResult` is a `ChangeResult`, `FeedbackResult`, or `NoChangeResult` from `dag_clean_logic`).
- Returns `(False, CleanResult)` on failure (where `CleanResult` is a `FailureResult` from `dag_clean_logic`).
  - Cleaning failure: a node's clean returned a `FailureResult`.
  - Termination limit exceeded: message cycle or non-clearing dirty state.
  - Feedback target outside the subgraph.
  - Graph contains a cycle (subgraph cannot be topologically ordered).
- On failure: the offending node's messages remain unchanged; previously cleaned nodes retain changes; processing halts.
- All output (changes and feedback) is delivered to the appropriate target nodes' message stores.
- A full agent transcript is written to a log file.

**Failure Handling:**
- All expected failures from the underlying DAG cleaning propagate as `(False, CleanResult)`.
- Logging continues regardless of success or failure (the log file is always written). The log file is created after component assembly; a failure during assembly (e.g., graph construction) propagates without a log file.
- Log output includes compact one-line event summaries to stdout (covering `tool_called`, `api_response`, `run_terminated`, `error` events) and a verbose full transcript to a log file; the transcript records each request's conversation state.
- Log file path is determined by (in priority order): 1) The `CLEANROOM_AGENT_LOG` environment variable (absolute path or a name relative to the log base directory), 2) `agent_loop.log` in the log base directory.
- The log base directory is the Bazel workspace directory (`BUILD_WORKSPACE_DIRECTORY`, else `BUILD_WORKING_DIRECTORY`) when present, otherwise the current working directory.

**HLS Justification:** "The client may request cleaning of a subgraph rooted at a target node."

### `inject_feedback`

```python
def inject_feedback(self, node_id: NodeId, workspace_root: str, messages: List[str]) -> CleaningResult
```

**Purpose:** Deliver feedback messages to a node's own pending message store, marking the node dirty for a subsequent cleaning pass.

**Preconditions:**
- `node_id` is a valid node label in the workspace
- `workspace_root` points to a valid workspace with manifest files
- `messages` is a list of feedback strings

**Postconditions:**
- Each message is added to the node's pending messages (the same store the DAG reads)
- A subsequent call to `run_dag` with this `node_id` (or any ancestor) will re-process the node as dirty
- Returns `(True, CleanResult)` on success (a `NoChangeResult` from `dag_clean_logic`).
- Returns `(False, CleanResult)` on failure (a `FailureResult` from `dag_clean_logic`) — the node does not exist in the graph.

**Failure Handling:**
- If the node does not exist in the graph, returns `(False, CleanResult)` (a `FailureResult`) without modifying any state.

**HLS Justification:** "Deliver feedback messages to a node's pending message store."

### `add_change`

```python
def add_change(self, node_id: NodeId, workspace_root: str, change: str = "check") -> CleaningResult
```

**Purpose:** Deliver a change message to a node's own pending message store, marking the node dirty for a subsequent cleaning pass. The node may succeed without changing when cleaned.

**Preconditions:**
- `node_id` is a valid node label in the workspace
- `workspace_root` points to a valid workspace with manifest files
- `change` is a change text; when omitted, the change text `check` applies

**Postconditions:**
- A change-kind `NodeMessage` (the given `change` text, or `check` when omitted) is added to the node's pending messages (the same store the DAG reads)
- A subsequent call to `run_dag` with this `node_id` (or any ancestor) will re-process the node as dirty
- Returns `(True, CleanResult)` on success (a `NoChangeResult` from `dag_clean_logic`).
- Returns `(False, CleanResult)` on failure (a `FailureResult` from `dag_clean_logic`) — the node does not exist in the graph.

**Failure Handling:**
- If the node does not exist in the graph, returns `(False, CleanResult)` (a `FailureResult`) without modifying any state.

**HLS Justification:** "Add a change message to a specific node's message store (marking the node dirty for a subsequent run)."

### `broadcast_change`

```python
def broadcast_change(self, node_id: NodeId, workspace_root: str, change: str) -> CleaningResult
```

**Purpose:** Pretend the node was cleaned with changes: broadcast a change message to the node's known reverse dependencies and clear the node's data, without cleaning the node.

**Preconditions:**
- `node_id` is a valid node label in the workspace
- `workspace_root` points to a valid workspace with manifest files
- `change` is a change text

**Postconditions:**
- A change-kind `NodeMessage` composed of the node's declared source file name followed by the change text is added to the pending set of each of the node's known reverse dependencies (as recorded in the message store)
- The node's pending messages and known reverse dependencies are cleared
- Returns `(True, CleanResult)` on success (a `NoChangeResult` from `dag_clean_logic`).
- Returns `(False, CleanResult)` on failure (a `FailureResult` from `dag_clean_logic`) — the node does not exist in the graph.

**Failure Handling:**
- If the node does not exist in the graph, returns `(False, CleanResult)` (a `FailureResult`) without modifying any state.

**HLS Justification:** "Broadcast a change from a specific node to its known reverse dependencies."


## Invariants

- The runner assembles all components internally; the client provides no component instances
- The runner owns the full lifecycle of all components it creates (graph storage, agent loop, DAG)
- The log file is always written, regardless of success or failure
- The runner does not expose component APIs; the interface is `run_dag`, `inject_feedback`, `add_change`, and `broadcast_change` only


## Non-Concerns

- **Component wiring strategy:** How the runner assembles (graph storage, agent loop, DAG) is specified in the implementation spec only; the interface contract specifies only the operational behavior.

